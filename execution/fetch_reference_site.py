"""
fetch_reference_site.py — Phase 3: reference extraction, two modes.

Mode A (preferred): GET the HTML, parse structure deterministically.
  requests + BeautifulSoup; if the page is JS-heavy (body < 500 words), re-render
  with Playwright. Extract: section order/landmarks, nav, font families
  (regex over linked CSS — no cssutils needed), color palette, image hosting
  patterns, grid hints.

Mode B (fallback): BACKTRACK from how it looks.
  If Mode A yields too little (anti-bot, canvas/SPA, auth wall), capture a
  full-page Playwright screenshot -> reference_{domain}.png and mark the .md as
  visual-backtrack. Gemini reconstructs the section structure from the image
  in Phase 5.

Usage:
  python execution/fetch_reference_site.py                 # uses design refs from project_input.md
  python execution/fetch_reference_site.py --url https://a.com --url https://b.com
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from urllib.parse import urlparse, urljoin

import _common as C

MIN_WORDS = 500          # below this, treat Mode A HTML as JS-heavy -> render
MIN_OK_WORDS = 200       # below this even after render -> Mode B (screenshot)
SECTION_HINTS = ("hero", "about", "service", "gallery", "portfolio", "team",
                 "staff", "testimonial", "review", "pricing", "price", "contact",
                 "booking", "book", "feature", "faq", "footer", "header", "banner",
                 "cta", "intro", "work", "product")


def domain_of(url: str) -> str:
    net = urlparse(url).netloc or "site"
    return net.replace("www.", "").replace(":", "_")


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


# ---------------------------------------------------------------------------
# Mode A — HTTP fetch
# ---------------------------------------------------------------------------
def http_fetch(url: str) -> tuple[str | None, str]:
    """Returns (html, note). html is None on hard failure."""
    try:
        import requests
    except ImportError:
        return None, "requests not installed"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=25)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}"
        return r.text, f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001 - network is inherently broad
        return None, f"requests error: {e}"


def fetch_css_text(soup, base_url: str) -> str:
    """Concatenate inline <style> + linked stylesheets (best-effort)."""
    try:
        import requests
    except ImportError:
        requests = None
    css_parts: list[str] = []
    for style in soup.find_all("style"):
        css_parts.append(style.get_text() or "")
    if requests is not None:
        links = soup.find_all("link", rel=lambda v: v and "stylesheet" in v)
        for link in links[:6]:  # cap to keep it fast
            href = link.get("href")
            if not href:
                continue
            css_url = urljoin(base_url, href)
            try:
                rr = requests.get(css_url, timeout=15)
                if rr.status_code < 400:
                    css_parts.append(rr.text)
            except Exception:  # noqa: BLE001
                continue
    return "\n".join(css_parts)


# ---------------------------------------------------------------------------
# Mode A — Playwright render fallback
# ---------------------------------------------------------------------------
def render_with_playwright(url: str, screenshot_path=None) -> tuple[str | None, str]:
    """Render the page; optionally screenshot. Returns (html, note)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "playwright not installed"

    launch_variants = [
        {},
        {"args": ["--no-sandbox", "--disable-dev-shm-usage"]},
    ]
    last_err = ""
    for variant in launch_variants:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, **variant)
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.goto(url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(1500)
                html = page.content()
                if screenshot_path is not None:
                    try:
                        page.screenshot(path=str(screenshot_path), full_page=True)
                    except Exception as e:  # noqa: BLE001
                        last_err = f"screenshot failed: {e}"
                browser.close()
                return html, "rendered" + (f" ({last_err})" if last_err else "")
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            continue
    return None, f"playwright error: {last_err}"


# ---------------------------------------------------------------------------
# Extraction from parsed HTML
# ---------------------------------------------------------------------------
def extract_sections(soup) -> list[dict]:
    sections = []
    order = 0
    for el in soup.find_all(["header", "nav", "section", "main", "footer", "div"]):
        tag = el.name
        ident = el.get("id", "")
        classes = " ".join(el.get("class", []) or [])
        blob = f"{ident} {classes}".lower()

        is_landmark = tag in ("header", "nav", "section", "main", "footer")
        is_hinted = any(h in blob for h in SECTION_HINTS)
        if not (is_landmark or is_hinted):
            continue
        # Skip deeply nested divs that are clearly not top-level sections.
        if tag == "div" and not is_hinted:
            continue

        heading = ""
        h = el.find(["h1", "h2", "h3"])
        if h:
            heading = re.sub(r"\s+", " ", h.get_text()).strip()[:80]
        label = ident or classes.split(" ")[0] or tag
        order += 1
        sections.append({
            "order": order,
            "tag": tag,
            "label": label[:60],
            "heading": heading,
        })
        if order >= 40:
            break
    return sections


def extract_nav(soup) -> list[str]:
    nav = soup.find("nav") or soup.find("header")
    items: list[str] = []
    if nav:
        for a in nav.find_all("a"):
            t = re.sub(r"\s+", " ", a.get_text()).strip()
            if t and len(t) < 30:
                items.append(t)
    # de-dup preserving order
    seen = set()
    out = []
    for it in items:
        if it.lower() not in seen:
            seen.add(it.lower())
            out.append(it)
    return out[:15]


def extract_fonts(css_text: str, soup) -> list[str]:
    fonts: list[str] = []
    # Google Fonts links: family=Name+Two|Name+Three
    for link in soup.find_all("link", href=True):
        href = link["href"]
        if "fonts.googleapis.com" in href:
            for m in re.findall(r"family=([^&:]+)", href):
                fam = m.replace("+", " ").split(":")[0].strip()
                if fam:
                    fonts.append(fam)
    # font-family declarations in CSS
    for decl in re.findall(r"font-family\s*:\s*([^;}{]+)", css_text, flags=re.I):
        first = decl.split(",")[0].strip().strip("'\"")
        if (first and len(first) < 40
                and not first.startswith(("var(", "$", "#{"))
                and "default-font" not in first.lower()):
            fonts.append(first)
    # de-dup, drop generic families
    generic = {"inherit", "initial", "sans-serif", "serif", "monospace", "system-ui"}
    seen, out = set(), []
    for f in fonts:
        k = f.lower()
        if k in generic or k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out[:8]


def extract_colors(css_text: str, html: str) -> dict:
    # CSS custom properties (design tokens)
    tokens = {}
    for name, val in re.findall(r"(--[a-z0-9\-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\))",
                               css_text, flags=re.I):
        tokens[name] = val
    # Frequent hex colors across CSS + inline
    hexes = re.findall(r"#[0-9a-fA-F]{6}\b", css_text + " " + html)
    common = [c.lower() for c, _ in Counter(h.lower() for h in hexes).most_common(10)]
    return {"tokens": dict(list(tokens.items())[:20]), "palette": common}


def extract_image_patterns(soup, base_url: str) -> dict:
    hosts = Counter()
    samples: list[str] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        full = urljoin(base_url, src)
        host = urlparse(full).netloc
        if host:
            hosts[host] += 1
        if len(samples) < 8:
            samples.append(full)
    return {"hosts": dict(hosts.most_common(6)), "samples": samples}


def detect_grid(css_text: str) -> list[str]:
    hints = []
    if re.search(r"display\s*:\s*grid", css_text, re.I):
        hints.append("CSS Grid")
    if re.search(r"display\s*:\s*flex", css_text, re.I):
        hints.append("Flexbox")
    if re.search(r"\bcol-(?:xs|sm|md|lg|xl)?-?\d", css_text, re.I) or "bootstrap" in css_text.lower():
        hints.append("Bootstrap-like columns")
    if re.search(r"max-width\s*:\s*(1[01]\d\d|1200|1240|1280)px", css_text, re.I):
        hints.append("container max-width ~1200px")
    return hints or ["(not detected)"]


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------
def write_report(url: str, mode: str, note: str, data: dict | None,
                 screenshot_rel: str | None) -> None:
    dom = domain_of(url)
    path = C.TMP / f"reference_{dom}.md"
    lines = [f"# Reference: {url}", "", f"- **Extracted:** {C.now()}", f"- **mode:** {mode}",
             f"- **note:** {note}"]
    if screenshot_rel:
        lines.append(f"- **screenshot:** {screenshot_rel}  (visual-backtrack — Gemini reconstructs structure from this)")
    lines.append("")

    if mode == "visual-backtrack":
        lines += [
            "## Structure could not be parsed from HTML.",
            "",
            f"A full-page screenshot was saved to `{screenshot_rel}`.",
            "**Gemini (Phase 5):** reconstruct this site's section order and layout "
            "from the screenshot and record it in the design brief.",
            "",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        C.log(f"Wrote {path.relative_to(C.ROOT)} (visual-backtrack)")
        return

    d = data or {}
    # Sections
    lines.append("## Section order")
    secs = d.get("sections", [])
    if secs:
        for s in secs:
            head = f' — "{s["heading"]}"' if s["heading"] else ""
            lines.append(f"{s['order']}. `{s['tag']}` · {s['label']}{head}")
    else:
        lines.append("(none detected)")
    lines.append("")

    # Nav
    lines.append("## Navigation")
    nav = d.get("nav", [])
    lines.append(" · ".join(nav) if nav else "(none detected)")
    lines.append("")

    # Fonts
    lines.append("## Fonts")
    fonts = d.get("fonts", [])
    if fonts:
        for f in fonts:
            lines.append(f"- {f}")
    else:
        lines.append("(none detected)")
    lines.append("")

    # Colors
    lines.append("## Colors")
    colors = d.get("colors", {})
    pal = colors.get("palette", [])
    if pal:
        lines.append("**Palette (most frequent):** " + ", ".join(pal))
    toks = colors.get("tokens", {})
    if toks:
        lines.append("")
        lines.append("**Design tokens (CSS custom properties):**")
        for k, v in toks.items():
            lines.append(f"- `{k}`: {v}")
    if not pal and not toks:
        lines.append("(none detected)")
    lines.append("")

    # Layout
    lines.append("## Layout system")
    for h in d.get("grid", []):
        lines.append(f"- {h}")
    lines.append("")

    # Images
    lines.append("## Image hosting pattern")
    imgs = d.get("images", {})
    hosts = imgs.get("hosts", {})
    if hosts:
        for h, n in hosts.items():
            lines.append(f"- {h}  ({n} imgs)")
    samples = imgs.get("samples", [])
    if samples:
        lines.append("")
        lines.append("**Sample image URLs:**")
        for s in samples[:5]:
            lines.append(f"- {s}")
    if not hosts and not samples:
        lines.append("(none detected)")
    lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    C.log(f"Wrote {path.relative_to(C.ROOT)} (mode A, {len(secs)} sections)")


# ---------------------------------------------------------------------------
# Per-URL pipeline
# ---------------------------------------------------------------------------
def process_url(url: str) -> bool:
    C.log(f"Reference: {url}")
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        C.die("beautifulsoup4 not installed — cannot parse reference HTML.")
        return False

    html, note = http_fetch(url)
    rendered = False

    # JS-heavy? render.
    if html is not None:
        soup = BeautifulSoup(html, "html.parser")
        body_text = soup.get_text(" ", strip=True)
        if word_count(body_text) < MIN_WORDS:
            C.log(f"Thin HTML ({word_count(body_text)} words) — rendering with Playwright.")
            r_html, r_note = render_with_playwright(url)
            if r_html:
                html, note, rendered = r_html, f"{note}; {r_note}", True
    else:
        C.log(f"HTTP fetch failed ({note}) — rendering with Playwright.")
        r_html, r_note = render_with_playwright(url)
        if r_html:
            html, note, rendered = r_html, f"{note}; {r_note}", True

    # Still nothing usable -> Mode B (visual backtrack).
    if html is None:
        return _visual_backtrack(url, f"no HTML ({note})")

    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(" ", strip=True)
    if word_count(body_text) < MIN_OK_WORDS:
        return _visual_backtrack(url, f"too little text ({word_count(body_text)} words)")

    base = url
    css_text = fetch_css_text(soup, base)
    data = {
        "sections": extract_sections(soup),
        "nav": extract_nav(soup),
        "fonts": extract_fonts(css_text, soup),
        "colors": extract_colors(css_text, html),
        "grid": detect_grid(css_text),
        "images": extract_image_patterns(soup, base),
    }
    # If structure is suspiciously empty, also drop a screenshot to aid Gemini.
    if not data["sections"]:
        _visual_backtrack(url, "no sections parsed; structure unclear", keep_report=False)
    write_report(url, "html" + ("+rendered" if rendered else ""), note, data,
                 screenshot_rel=_existing_screenshot_rel(url))
    return True


def _existing_screenshot_rel(url: str):
    png = C.TMP / f"reference_{domain_of(url)}.png"
    return str(png.relative_to(C.ROOT)) if png.exists() else None


def _visual_backtrack(url: str, why: str, keep_report: bool = True) -> bool:
    dom = domain_of(url)
    png = C.TMP / f"reference_{dom}.png"
    C.log(f"Mode B (visual backtrack): {why}")
    _html, note = render_with_playwright(url, screenshot_path=png)
    if png.exists():
        if keep_report:
            write_report(url, "visual-backtrack", f"{why}; {note}", None,
                         screenshot_rel=str(png.relative_to(C.ROOT)))
        return True
    # Couldn't even screenshot — record the failure honestly (no fabrication).
    if keep_report:
        write_report(url, "failed", f"{why}; screenshot also failed ({note})", None, None)
        C.log("Could not fetch or screenshot — flag to user; do not fabricate structure.", "WARN")
    return False


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    C.ensure_dirs()
    urls: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--url" and i + 1 < len(argv):
            urls.append(argv[i + 1]); i += 2
        else:
            i += 1
    if not urls:
        urls = C.parse_project_input()["design_references"]

    if not urls:
        C.log("No design references found (project_input.md '## Design References' is empty).", "WARN")
        C.log("Nothing to extract. Add reference URLs or pass --url.", "WARN")
        return

    ok_any = False
    for u in urls:
        try:
            ok_any = process_url(u) or ok_any
        except Exception as e:  # noqa: BLE001
            C.log(f"Unexpected error on {u}: {e}", "ERROR")
    if not ok_any:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
