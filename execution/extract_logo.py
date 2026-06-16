"""
extract_logo.py — isolate a brand's logo MARK and derive its WORDMARK.

Why this exists
---------------
Client brand images almost always arrive as a *lockup*: the graphic mark, the
company name, a tagline, sometimes a photographed sign on a wall. Cropping a
rectangle out of that lockup (and shipping the background with it) is the bug
this tool fixes. Here we do two separate, honest jobs:

  mark      Isolate ONLY the graphic mark (e.g. the hands+star icon) into a
            clean transparent PNG — no name text, no tagline, no background.

  wordmark  Persist the company name's typographic spec (font family, weight,
            size, colour, letter-spacing) that the orchestrator derived by
            looking at the image, so the name can be rebuilt as *live HTML
            text* in a matched web font (crisp, recolourable, accessible).

3-layer fit: the orchestrator (Claude) analyses the image and supplies the
parameters (which hue is the mark, what the background colour is, which Google
font matches the name). This script is the deterministic Layer-3 worker — it
does the pixel masking / flood-fill and the manifest/spec bookkeeping. It never
guesses brand identity: bad params -> it fails loudly, it does not invent a mark.

Dependencies: Pillow + numpy + scipy (all local, no API keys, no OpenCV/rembg).

Usage
-----
  python execution/extract_logo.py mark \
      --src assets/images/clinic_logo.jpg \
      --out assets/images/logo_mark.png \
      --hue-range 40,150 --sat-min 0.25 --val-min 0.30 \
      [--box x,y,w,h] [--bg near-white | --bg-color "#RRGGBB" --bg-tol 28] \
      [--pad 8] [--no-trim]

  python execution/extract_logo.py wordmark \
      --line "Healing Hands" --family "Quicksand" --weight 700 \
      --size-px 30 --color "#1AA7B8" --letter-spacing -0.01em \
      [--out .tmp/wordmark_spec.json]
"""

from __future__ import annotations

import sys
from pathlib import Path

import _common as C


# ---------------------------------------------------------------------------
# Tiny arg parser — matches the project's keep-it-simple, no-argparse style.
# ---------------------------------------------------------------------------
def parse_flags(argv: list[str]) -> dict:
    """--key value  /  --flag (boolean)  ->  {"key": value, "flag": True}."""
    out: dict[str, object] = {}
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--"):
            key = tok[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                out[key] = argv[i + 1]
                i += 2
            else:
                out[key] = True
                i += 1
        else:
            i += 1
    return out


def _need(libs: str):
    C.die(
        f"Missing image libraries ({libs}). Install with:\n"
        f"    python -m pip install Pillow numpy scipy"
    )


def hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        C.die(f"Bad hex colour: '{s}' (want #RRGGBB)")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Manifest bookkeeping — the manifest is a JSON *array*; upsert by path.
# ---------------------------------------------------------------------------
def manifest_upsert(entry: dict) -> None:
    path = C.TMP / "images_manifest.json"
    data = C.read_json(path, default=[])
    if not isinstance(data, list):
        data = []
    data = [e for e in data if e.get("path") != entry["path"]]
    data.append(entry)
    C.write_json(path, data)
    C.log(f"images_manifest.json updated -> {entry['path']} ({entry['suggested_use']})")


# ---------------------------------------------------------------------------
# mark — isolate the graphic mark into a transparent PNG
# ---------------------------------------------------------------------------
def cmd_mark(argv: list[str]) -> None:
    if not (C.have_module("PIL") and C.have_module("numpy") and C.have_module("scipy")):
        _need("Pillow / numpy / scipy")
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    f = parse_flags(argv)
    src = f.get("src")
    out = f.get("out")
    if not src or not out:
        C.die("mark needs --src <image> and --out <png>")

    src_path = (C.ROOT / str(src)) if not Path(str(src)).is_absolute() else Path(str(src))
    out_path = (C.ROOT / str(out)) if not Path(str(out)).is_absolute() else Path(str(out))
    if not src_path.exists():
        C.die(f"Source image not found: {src_path}")

    img = Image.open(src_path).convert("RGB")
    rgb = np.asarray(img, dtype=np.uint8)
    H, W = rgb.shape[:2]

    # Optional pre-crop to a region the orchestrator already located.
    ox, oy = 0, 0
    if f.get("box"):
        try:
            bx, by, bw, bh = (int(v) for v in str(f["box"]).split(","))
        except ValueError:
            C.die("--box must be 'x,y,w,h' (integers)")
        bx, by = max(0, bx), max(0, by)
        rgb = rgb[by : by + bh, bx : bx + bw]
        ox, oy = bx, by
        H, W = rgb.shape[:2]
        C.log(f"Pre-cropped to box {bx},{by},{bw},{bh} -> {W}x{H}")

    # --- 1. Locate the mark by hue (the mark colour is distinct from text/bg) ---
    hsv = np.asarray(Image.fromarray(rgb).convert("HSV"), dtype=np.float32)
    hue = hsv[..., 0] * (360.0 / 255.0)        # 0..360 degrees
    sat = hsv[..., 1] / 255.0                   # 0..1
    val = hsv[..., 2] / 255.0                   # 0..1

    hlo, hhi = (40.0, 150.0)
    if f.get("hue-range"):
        hlo, hhi = (float(v) for v in str(f["hue-range"]).split(","))
    sat_min = float(f.get("sat-min", 0.25))
    val_min = float(f.get("val-min", 0.30))

    mark_mask = (hue >= hlo) & (hue <= hhi) & (sat >= sat_min) & (val >= val_min)
    if mark_mask.sum() < 50:
        C.die(
            "Hue mask caught almost nothing — wrong --hue-range/--sat-min for this "
            "image. Inspect the source and adjust, or pass an explicit --box. "
            "(Refusing to emit a junk mark.)"
        )

    # Largest connected blob of mark-coloured pixels = the icon (drops stray specks).
    dil = ndimage.binary_dilation(mark_mask, iterations=2)
    labels, n = ndimage.label(dil)
    if n == 0:
        C.die("No connected mark region found.")
    sizes = ndimage.sum(np.ones_like(labels), labels, index=range(1, n + 1))
    biggest = int(np.argmax(sizes)) + 1
    ys, xs = np.where(labels == biggest)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()

    pad = int(f.get("pad", 8))
    y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
    y1, x1 = min(H - 1, y1 + pad), min(W - 1, x1 + pad)
    crop = rgb[y0 : y1 + 1, x0 : x1 + 1]
    ch, cw = crop.shape[:2]
    C.log(f"Mark bbox in source: x={ox + x0} y={oy + y0} w={cw} h={ch}")

    # Re-expand the working crop to give the flood-fill a solid background buffer
    # around all sides of the mark. Without this buffer the flood-fill can eat into
    # the pale anti-aliased glow of the mark (it leaks through when the crop border
    # is only a few pixels away from the mark edge).
    buf = int(f.get("pad", 8)) + 12          # extra 12px on each side
    ey0 = max(0, y0 - buf)
    ey1 = min(H - 1, y1 + buf)
    ex0 = max(0, x0 - buf)
    ex1 = min(W - 1, x1 + buf)
    crop = rgb[ey0 : ey1 + 1, ex0 : ex1 + 1]
    ch, cw = crop.shape[:2]
    C.log(f"Background-removal crop (expanded): {cw}x{ch}")

    # --- 2. Background -> transparent by flood-fill from the crop border ------
    # Only background CONNECTED to the edge is removed, so an enclosed light
    # detail (e.g. the white star inside the icon) is preserved.
    #
    # Key insight: the default criterion must be TIGHT (sat < 0.05) — not the
    # broader sat < 0.18 — because the pale anti-aliased glow around a logo mark
    # has saturation ≈ 0.10–0.15, which a loose threshold incorrectly removes,
    # making the mark look narrower than the source.  True background is neutral
    # white with saturation ≈ 0.  If the background is a solid non-white colour,
    # pass --bg-color / --bg-tol to override.
    c_hsv = np.asarray(Image.fromarray(crop).convert("HSV"), dtype=np.float32)
    c_sat = c_hsv[..., 1] / 255.0
    c_val = c_hsv[..., 2] / 255.0

    if f.get("bg-color"):
        br, bg_, bb = hex_to_rgb(str(f["bg-color"]))
        tol = float(f.get("bg-tol", 28))
        diff = np.sqrt(((crop.astype(np.float32) - np.array([br, bg_, bb])) ** 2).sum(-1))
        bg_like = diff <= tol
    else:  # default: TRUE neutral-white only (low saturation AND high value)
        bg_like = (c_sat < 0.05) & (c_val > 0.88)

    border = np.zeros((ch, cw), dtype=bool)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    bg_labels, bn = ndimage.label(bg_like)
    edge_ids = set(np.unique(bg_labels[border])) - {0}
    background = np.isin(bg_labels, list(edge_ids)) if edge_ids else np.zeros_like(bg_like)

    alpha = np.where(background, 0.0, 255.0).astype(np.float32)
    # Feather the cut edge ~1px so the mark doesn't look stamped-out.
    alpha = ndimage.gaussian_filter(alpha, sigma=0.6)

    out_rgba = np.dstack([crop, alpha.astype(np.uint8)])
    result = Image.fromarray(out_rgba, "RGBA")

    # --- 3. Trim fully-transparent margins -----------------------------------
    if not f.get("no-trim"):
        bbox = result.getbbox()
        if bbox:
            result = result.crop(bbox)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path, "PNG")
    opaque = int((np.asarray(result)[..., 3] > 10).sum())
    C.log(f"Saved {out_path}  ({result.width}x{result.height}, {opaque} opaque px)")

    rel = out_path.relative_to(C.ROOT).as_posix() if out_path.is_relative_to(C.ROOT) else str(out_path)
    src_rel = src_path.name
    manifest_upsert(
        {
            "path": rel,
            "source": "extracted",
            "derived_from": src_rel,
            "suggested_use": "logo_mark",
        }
    )


# ---------------------------------------------------------------------------
# wordmark — persist the derived typographic spec for the company name
# ---------------------------------------------------------------------------
def cmd_wordmark(argv: list[str]) -> None:
    f = parse_flags(argv)
    line = f.get("line")
    family = f.get("family")
    if not line or not family:
        C.die('wordmark needs at least --line "Company Name" and --family "Font"')

    try:
        weight = int(f.get("weight", 700))
    except ValueError:
        C.die("--weight must be an integer (e.g. 700)")

    spec = {
        "line": str(line),
        "family": str(family),
        "weight": weight,
        "size_px": int(f.get("size-px", 30)) if str(f.get("size-px", "")).strip() else None,
        "color": str(f["color"]) if f.get("color") else None,
        "letter_spacing": str(f["letter-spacing"]) if f.get("letter-spacing") else "normal",
        "derived_from": str(f.get("derived-from", "")) or None,
        "derived_at": C.now(),
    }
    out = f.get("out") or (C.TMP / "wordmark_spec.json")
    out_path = Path(str(out)) if Path(str(out)).is_absolute() else (C.ROOT / str(out))
    C.write_json(out_path, spec)
    C.log(f"Wrote wordmark spec -> {out_path}")

    # Emit copy-paste-ready snippets so the header rebuild is mechanical.
    fam_q = str(family).replace(" ", "+")
    print("\n--- Google Fonts <link> (add to <head>) ---")
    print(
        f'<link href="https://fonts.googleapis.com/css2?family={fam_q}:wght@'
        f'{weight}&display=swap" rel="stylesheet" />'
    )
    print("\n--- .logo-wordmark CSS ---")
    ls = spec["letter_spacing"]
    size = f"{spec['size_px']}px" if spec["size_px"] else "1.35rem"
    color = spec["color"] or "var(--text)"
    print(
        ".logo-wordmark {\n"
        f"  font-family: '{family}', sans-serif;\n"
        f"  font-weight: {weight};\n"
        f"  font-size: {size};\n"
        f"  color: {color};\n"
        f"  letter-spacing: {ls};\n"
        "}"
    )


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    C.ensure_dirs()
    if not argv:
        C.die("Usage: extract_logo.py <mark|wordmark> [flags]  (see file header)")
    cmd, rest = argv[0], argv[1:]
    if cmd == "mark":
        cmd_mark(rest)
    elif cmd == "wordmark":
        cmd_wordmark(rest)
    else:
        C.die(f"Unknown subcommand '{cmd}'. Use 'mark' or 'wordmark'.")


if __name__ == "__main__":
    main(sys.argv[1:])
