"""
collect_assets.py — Phases 2 and 4.

  python execution/collect_assets.py collect    # Phase 2: gather content + images
  python execution/collect_assets.py reconcile  # Phase 4: map reference sections -> data

Phase 2 (collect) processes discovered sources in PRIORITY order:
  P1 Liquid Gold  : the business's own website -> full content extraction
                    (.tmp/existing_site_content.md) + image downloads
  P2 Google       : profile photos -> assets/images/google_*.jpg (+ google_profile.md)
  P3 Social/News  : best-effort snippets -> .tmp/social_profiles.md
Output: assets/images/ + .tmp/images_manifest.json

Phase 4 (reconcile) builds the master section list from reference_*.md (+ must-include
from project_input.md) and fills each section from real data ONLY, in order:
liquid gold -> google -> social -> news. Sections with no real data are marked
EMPTY. Output: .tmp/section_fill_report.md. NEVER fabricates content.
"""

from __future__ import annotations

import re
import sys
from urllib.parse import urlparse, urljoin

import _common as C

# Reuse the robust fetch/render helpers from the reference script (same dir).
try:
    from fetch_reference_site import http_fetch, render_with_playwright, word_count
except Exception:  # noqa: BLE001 - fall back to local minimal versions
    def http_fetch(url):  # type: ignore
        try:
            import requests
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            return (r.text, f"HTTP {r.status_code}") if r.status_code < 400 else (None, f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            return None, str(e)

    def render_with_playwright(url, screenshot_path=None):  # type: ignore
        return None, "unavailable"

    def word_count(t):  # type: ignore
        return len(re.findall(r"\w+", t or ""))


PRICE_RE = re.compile(r"(?:₹|Rs\.?|INR)\s?\d[\d,]*\+?", re.I)

# Canonical sections we know how to reconcile, with keyword hints.
CANON = {
    "hero": ["hero", "banner", "intro", "welcome"],
    "about": ["about", "story", "who we are", "mission"],
    "services": ["service", "menu", "treatment", "pricing", "price", "offer"],
    "team": ["team", "staff", "stylist", "therapist", "expert", "our people"],
    "gallery": ["gallery", "portfolio", "work", "photos"],
    "testimonials": ["testimonial", "review", "client", "feedback"],
    "awards": ["award", "certified", "recognition", "press"],
    "contact": ["contact", "visit", "location", "book", "appointment", "hours"],
}


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
def download(url: str, dest, referer: str | None = None) -> bool:
    try:
        import requests
    except ImportError:
        return False
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if referer:
        headers["Referer"] = referer
    try:
        r = requests.get(url, headers=headers, timeout=30, stream=True)
        if r.status_code >= 400:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            for chunk in r.iter_content(8192):
                fh.write(chunk)
        return dest.stat().st_size > 1024  # ignore tiny/blank
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Liquid gold — full content extraction from the existing website
# ---------------------------------------------------------------------------
def extract_existing_site(url: str, manifest_images: list) -> bool:
    from bs4 import BeautifulSoup

    html, note = http_fetch(url)
    if html is None or word_count(BeautifulSoup(html, "html.parser").get_text(" ", strip=True)) < 200:
        r_html, r_note = render_with_playwright(url)
        if r_html:
            html, note = r_html, f"{note}; {r_note}"
    if html is None:
        C.log(f"Liquid gold fetch failed ({note}) — skipping.", "WARN")
        return False

    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text().strip() if soup.title else "")
    meta = soup.find("meta", attrs={"name": "description"})
    desc = (meta.get("content", "").strip() if meta else "")

    headings = [re.sub(r"\s+", " ", h.get_text()).strip()
                for h in soup.find_all(["h1", "h2", "h3"])]
    headings = [h for h in headings if h][:60]

    paras = [re.sub(r"\s+", " ", p.get_text()).strip()
             for p in soup.find_all("p")]
    paras = [p for p in paras if len(p) > 40][:80]

    items = [re.sub(r"\s+", " ", li.get_text()).strip()
             for li in soup.find_all("li")]
    items = [i for i in items if 3 < len(i) < 120][:120]

    prices = sorted(set(PRICE_RE.findall(html)))

    # Images
    img_urls = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        img_urls.append(urljoin(url, src))
    # de-dup, cap
    seen, clean = set(), []
    for u in img_urls:
        if u in seen:
            continue
        seen.add(u)
        clean.append(u)
    clean = clean[:25]

    downloaded = 0
    for idx, iu in enumerate(clean, 1):
        ext = _ext_of(iu)
        dest = C.IMAGES / f"site_{idx:02d}{ext}"
        if download(iu, dest, referer=url):
            downloaded += 1
            manifest_images.append({
                "path": str(dest.relative_to(C.ROOT)).replace("\\", "/"),
                "source": "liquid_gold", "origin": iu, "suggested_use": "gallery",
            })

    # Write the content file (real data only).
    lines = [f"# Liquid Gold — Existing Site Content", "",
             f"- **Source:** {url}", f"- **Fetched:** {C.now()}", f"- **note:** {note}",
             "", "> PRIMARY content source. Copy here is usable near-verbatim.", ""]
    if title:
        lines += ["## Page title", title, ""]
    if desc:
        lines += ["## Meta description", desc, ""]
    if headings:
        lines += ["## Headings"] + [f"- {h}" for h in headings] + [""]
    if prices:
        lines += ["## Prices found"] + [f"- {p}" for p in prices] + [""]
    if items:
        lines += ["## List items (often services / features)"] + [f"- {i}" for i in items] + [""]
    if paras:
        lines += ["## Paragraphs"] + [f"{p}\n" for p in paras] + [""]
    lines += [f"## Images downloaded", f"{downloaded} image(s) -> assets/images/site_*", ""]

    (C.TMP / "existing_site_content.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    C.log(f"Liquid gold: {len(headings)} headings, {len(items)} list items, "
          f"{len(prices)} prices, {downloaded} images.")
    return True


def _ext_of(url: str) -> str:
    path = urlparse(url).path.lower()
    for e in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"):
        if path.endswith(e):
            return ".jpg" if e == ".jpeg" else e
    return ".jpg"


# ---------------------------------------------------------------------------
# Google photos
# ---------------------------------------------------------------------------
def collect_google(manifest: dict, manifest_images: list) -> None:
    photos = manifest.get("google_photos", [])
    if not photos:
        C.log("No Google photos to collect.")
        return
    downloaded = 0
    for idx, base in enumerate(photos, 1):
        full = base + ("=s1600" if "=s" not in base else "")
        dest = C.IMAGES / f"google_{idx:02d}.jpg"
        if download(full, dest, referer="https://www.google.com/"):
            downloaded += 1
            manifest_images.append({
                "path": str(dest.relative_to(C.ROOT)).replace("\\", "/"),
                "source": "google_profile", "origin": full, "suggested_use": "gallery",
            })
    C.log(f"Google photos downloaded: {downloaded}/{len(photos)}")

    lines = ["# Google Business Profile", "", f"- **Fetched:** {C.now()}"]
    if manifest.get("phone"):
        lines.append(f"- **Phone:** {manifest['phone']}")
    if manifest.get("address"):
        lines.append(f"- **Address:** {manifest['address']}")
    lines += ["", f"## Photos", f"{downloaded} image(s) -> assets/images/google_*", ""]
    (C.TMP / "google_profile.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Social / news — snippets only (honest about login walls)
# ---------------------------------------------------------------------------
def collect_social(manifest: dict) -> None:
    sources = manifest.get("sources", {})
    lines = ["# Social & Directory Profiles", "", f"- **Compiled:** {C.now()}",
             "", "> Snippets only. FB/IG content is largely login-walled; "
             "nothing here is invented — empty means nothing was retrievable.", ""]
    found_any = False
    for key in ("facebook", "instagram", "justdial", "sulekha"):
        if key in sources:
            found_any = True
            lines += [f"## {key.title()}", f"- URL: {sources[key]['url']}", ""]
    if "news" in sources:
        found_any = True
        lines += ["## News mentions"]
        for it in sources["news"].get("items", []):
            lines.append(f"- [{it['title']}]({it['url']})")
        lines.append("")
    if not found_any:
        lines += ["(no social, directory, or news sources discovered)"]
    (C.TMP / "social_profiles.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    C.log("Wrote social_profiles.md")


# ---------------------------------------------------------------------------
# Phase 2 driver
# ---------------------------------------------------------------------------
def cmd_collect() -> None:
    C.ensure_dirs()
    manifest = C.read_json(C.TMP / "business_manifest.json")
    if not manifest:
        C.log("business_manifest.json missing — run discovery first.", "ERROR")
        sys.exit(1)

    images: list = []
    sources = manifest.get("sources", {})

    # P1 liquid gold
    if "existing_website" in sources:
        C.log("P1 — Liquid Gold (existing website)…")
        extract_existing_site(sources["existing_website"]["url"], images)
    else:
        C.log("P1 — no existing website; skipping liquid gold.")

    # P2 google
    C.log("P2 — Google profile photos…")
    collect_google(manifest, images)

    # P3 social/news
    C.log("P3 — Social / directory / news…")
    collect_social(manifest)

    C.write_json(C.TMP / "images_manifest.json", images)
    C.log(f"images_manifest.json: {len(images)} image(s).")


# ---------------------------------------------------------------------------
# Phase 4 — section reconciliation (NO hallucination)
# ---------------------------------------------------------------------------
def _reference_section_labels() -> list[str]:
    labels = []
    for ref in C.TMP.glob("reference_*.md"):
        text = ref.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"## Section order\s*(.+?)(?:\n## |\Z)", text, re.S)
        if not m:
            continue
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("("):
                continue
            # "1. `tag` · label — "heading""
            piece = re.sub(r"^\d+\.\s*", "", line)
            piece = piece.replace("`", "")
            labels.append(piece.lower())
    return labels


def _canon_sections() -> list[str]:
    """Union of canonical sections implied by references + must-include + defaults."""
    found = set()
    ref_blob = " ".join(_reference_section_labels())
    pin = C.parse_project_input()
    must_blob = " ".join(pin["must_include"]).lower()
    blob = ref_blob + " " + must_blob

    for canon, hints in CANON.items():
        if any(h in blob for h in hints) or canon in blob:
            found.add(canon)
    # Sensible defaults so we never ship a skeleton site.
    found.update({"hero", "about", "services", "gallery", "contact"})
    # Preserve canonical order.
    return [s for s in CANON if s in found]


def _load_corpus() -> list[tuple[str, str]]:
    """(source_label, text) for each collected content file that exists."""
    corpus = []
    mapping = [
        ("liquid_gold", C.TMP / "existing_site_content.md"),
        ("google", C.TMP / "google_profile.md"),
        ("social", C.TMP / "social_profiles.md"),
    ]
    for label, path in mapping:
        if path.exists():
            corpus.append((label, path.read_text(encoding="utf-8", errors="ignore").lower()))
    return corpus


def cmd_reconcile() -> None:
    C.ensure_dirs()
    sections = _canon_sections()
    corpus = _load_corpus()
    images = C.read_json(C.TMP / "images_manifest.json", []) or []
    manifest = C.read_json(C.TMP / "business_manifest.json", {}) or {}

    rows = []
    for sec in sections:
        hints = CANON[sec]
        status, source, note = "EMPTY", "—", ""

        # Special cases backed by structured data.
        if sec == "gallery" and images:
            status, source, note = "FILLED", "images", f"{len(images)} images available"
        elif sec == "contact" and (manifest.get("phone") or manifest.get("address")):
            bits = [b for b in (manifest.get("phone"), manifest.get("address")) if b]
            status, source, note = "FILLED", "google", "; ".join(bits)[:50]
        else:
            for label, text in corpus:
                if any(h in text for h in hints):
                    status, source = "FILLED", label
                    if sec == "services":
                        prices = PRICE_RE.findall(text)
                        note = f"{len(prices)} prices" if prices else "service text found"
                    break
            if status == "EMPTY":
                note = "no real data — owner to provide"

        rows.append((sec, status, source, note))

    # Write report
    lines = ["# Section Fill Report", "", f"- **Generated:** {C.now()}",
             "- Sections derived from the design reference(s) + must-include.",
             "- FILLED = backed by real collected data. EMPTY = build the section, "
             "leave content blank with a marker, NEVER invent.", "",
             "| Section | Status | Source | Notes |",
             "|---------|--------|--------|-------|"]
    n_empty = 0
    for sec, status, source, note in rows:
        if status == "EMPTY":
            n_empty += 1
        lines.append(f"| {sec} | {status} | {source} | {note} |")
    lines += ["", f"**{len(rows) - n_empty} filled, {n_empty} empty.**"]
    if n_empty:
        lines += ["", "### EMPTY sections — leave a marker for the owner:",
                  *[f"- `<!-- EMPTY: {s} — awaiting owner -->`" for s, st, *_ in rows if st == "EMPTY"]]

    (C.TMP / "section_fill_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    C.log(f"section_fill_report.md: {len(rows)} sections, {n_empty} empty.")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    mode = argv[0] if argv else "collect"
    if mode == "collect":
        cmd_collect()
    elif mode == "reconcile":
        cmd_reconcile()
    else:
        C.die(f"unknown mode '{mode}' (use: collect | reconcile)")


if __name__ == "__main__":
    main(sys.argv[1:])
