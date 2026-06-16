# Directive: Logo Mark + Wordmark Extraction

**Tool:** `execution/extract_logo.py` (subcommands `mark`, `wordmark`)
**When:** Phase 6 (code generation), before building the header, whenever a client
brand image (logo lockup, photographed sign, social avatar) is available in
`assets/images/`. Produces the two header brand assets: an isolated graphic mark
and a typographic spec for the company name.

---

## Why this exists (the mistake it prevents)

Brand images arrive as a **lockup**: graphic mark + company name + tagline, often
photographed on a wall *behind a person*. The wrong move — and the bug that
created this directive — is to crop a rectangle out of that lockup and ship it as
"the logo": you end up using the wall/background as a logo, with the name baked
into a fuzzy raster sitting next to a second copy of the same name.

The right move is two **separate, honest** derivations:

1. **Mark** → isolate ONLY the graphic icon into a clean transparent PNG (no name
   text, no tagline, no background).
2. **Wordmark** → identify the name's typography (font family / weight / size /
   colour) and rebuild the name as **live HTML text** in a matched web font.

## Layer split

- **Orchestrator (you):** look at the image. Decide (a) which hue is the mark vs.
  the text, (b) what the background colour is, (c) which Google font matches the
  name and its weight/size/colour. These are judgement calls — vision, not code.
- **Script (deterministic):** does the pixel masking + flood-fill + PNG/manifest
  bookkeeping for the mark, and validates + persists the wordmark spec. It never
  guesses brand identity; bad params make it fail loudly (it will not emit a junk
  mark). Deps: Pillow + numpy + scipy — all local, no API keys.

---

## Step 1 — Isolate the mark

Analyse the source first (crop/zoom the brand image with the Read tool). Identify:
- the **mark's colour** as an HSV hue window (the mark hue differs from the name
  text hue and the background — that separation is what makes isolation reliable);
- the **background** (near-white by default, or an explicit colour for a
  photographed wall);
- any enclosed light detail (e.g. a white star inside the icon) — it is preserved
  automatically because background is removed by **edge flood-fill**, not by a
  colour-keep mask.

```
python execution/extract_logo.py mark \
    --src assets/images/<brand_image> \
    --out assets/images/logo_mark.png \
    --hue-range <lo,hi> --sat-min <0..1> --val-min <0..1> \
    [--box x,y,w,h]            # pre-crop if the lockup is busy / self-anneal path
    [--bg near-white | --bg-color "#RRGGBB" --bg-tol 28] \
    [--pad 8] [--no-trim]
```

Defaults (`--hue-range 40,150 --sat-min 0.25 --val-min 0.30`) target a
lime/green/yellow mark and exclude teal/cyan text and white background.

**Verify with the Read tool**: open `logo_mark.png`. It must contain only the
icon, on transparency, edges clean, enclosed details intact, **no name text**. If
the mask grabbed text or missed the icon → adjust `--hue-range`/`--sat-min`, or
constrain with `--box`, and re-run. The script auto-upserts the result into
`.tmp/images_manifest.json` as `{source: "extracted", suggested_use: "logo_mark"}`.

## Step 2 — Derive the wordmark

Read the name's letterforms (zoom in). Match to the closest Google font — the
diagnostic that usually decides it:
- **double-story `a`** (bowl + top arch) → Nunito / Nunito Sans / Varela Round;
  **single-story `a`** → Quicksand / Comfortaa.
- check `g` (single vs double story), terminal roundness, and weight.

Sample the name's colour from the image (don't eyeball the hex). Then:

```
python execution/extract_logo.py wordmark \
    --line "Company Name" --family "Nunito" --weight 800 \
    --size-px 20 --color "#RRGGBB" --letter-spacing "-0.01em" \
    --derived-from "<brand_image>"
```

It writes `.tmp/wordmark_spec.json` and prints a copy-paste Google Fonts `<link>`
and `.logo-wordmark` CSS block.

## Step 3 — Rebuild the header

- `<img class="logo-img" src="assets/images/logo_mark.png">` (the isolated mark).
- Company name as **live text** in the matched font — load the printed `<link>`
  in `<head>`, apply the printed CSS to `.logo-wordmark`. Mirror the original
  lockup's layout (e.g. stack the name on two lines beside the mark if the source
  stacks it).
- Keep the footer/text-only wordmark on the same family/weight for consistency.

---

## Hard rules

- **No hallucinated brand.** If the source has no usable mark, or extraction can't
  produce a clean icon, leave `<!-- EMPTY: logo mark — awaiting owner -->` in the
  header. Never invent a mark or substitute an unrelated graphic.
- **Live text, not raster name.** The company name is HTML text in a matched font
  (crisp, recolourable for dark/light headers, accessible) — not a cropped image.
- **Match, then state confidence.** The web font is a *close visual match*, not the
  client's licensed original; note the chosen family so it can be refined.

## Self-anneal notes

- 2026-06-16 (initial): First use on Healing Hands. Source `clinic_logo.jpg` was
  itself a crop of the wall sign behind the owner (from `google_01.jpg`). Name
  matched to **Nunito 800** (double-story `a` ruled out Quicksand/Comfortaa);
  colour sampled `#06A1BD`.

- 2026-06-16 (proportion fix): First extraction (`--sat-min 0.25`, default
  `sat<0.18` background) produced 111×168 (ratio 0.66), visually too narrow vs
  the source. Root cause: TWO bugs compounding.
  1. `sat-min 0.25` cuts the pale anti-aliased outer-glow of the hands (sat≈0.12).
  2. Default background criterion `sat<0.18` also matches that same glow layer
     (sat≈0.14), so the flood-fill eats the glow from the crop border inward.
  Fix: `--sat-min 0.12` to include the glow in the mark location step, AND
  change default bg criterion to `sat < 0.05` (true neutral-white only). Also
  expand the background-removal crop by `pad + 12` on all sides (so there is a
  genuine buffer of pure background between the crop border and the glow edge —
  without this buffer, the flood-fill leaks through JPEG-compressed edge pixels).
  Corrected run: `--box 0,0,185,235 --hue-range 40,150 --sat-min 0.12
  --val-min 0.20 --pad 8` → 128×171, ratio 0.749. CSS hardcoded to
  `height:46px; width:35px`.
  Check added to `quality_standard_r1.md` and `revision_loop.md`: extracted
  mark w/h ratio must be within ±5% of source mark bbox ratio.

- 2026-06-16 (teal-bar fix): Second extraction (`--box 0,0,185,235`) produced
  128×171 PNG that appeared correct by ratio but contained a **teal vertical bar
  on the right** — the first ~10px of the "H" from "Healing Hands" text (starts
  at x≈175 in source). Bug: crop extended to x=184 of the 400×400 source, teal
  "H" pixels (sat>0.05) were NOT background so flood-fill left them; they
  appeared as a teal strip in the output, inflating perceived width (ratio 0.749
  instead of true 0.661).
  Fix: `--box 0,0,170,235` — stops 5px before teal text start at x≈175.
  Result: 113×171, ratio 0.661, no artifact. CSS updated to `height:46px;
  width:30px` (46×0.661=30.4≈30px).
  Rule: always ensure `--box` right edge ≤ (mark right edge + ~5px), never into
  adjacent text. Verify extracted PNG visually before hardcoding CSS.
