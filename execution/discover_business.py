"""
discover_business.py — Phase 1: find a business's entire online presence.

Reads inputs/project_input.md. If a Google Business/Maps URL is given, opens it
with Playwright to pull the authoritative website link, description, and photo
URLs. Then uses keyless web search (ddgs / DuckDuckGo) to find the existing
website, Facebook, Instagram, JustDial/Sulekha, and recent news.

The big prize: an EXISTING WEBSITE. If found it is ranked priority 1, type
'liquid_gold' — a pre-curated content source the rest of the pipeline leans on.

Output: .tmp/business_manifest.json
"""

from __future__ import annotations

import re
import sys
from urllib.parse import urlparse

import _common as C

SOCIAL_HOSTS = ("facebook.com", "fb.com", "instagram.com", "twitter.com",
                "x.com", "linkedin.com", "youtube.com", "pinterest.com")
DIRECTORY_HOSTS = ("justdial.com", "sulekha.com", "yelp.com", "tripadvisor.com",
                   "zomato.com", "swiggy.com", "practo.com", "urbancompany.com")
AGGREGATOR_HOSTS = ("google.com", "goo.gl", "maps.google", "bing.com",
                    "wikipedia.org", "indiamart.com")


def classify(url: str) -> str:
    host = (urlparse(url).netloc or "").lower().replace("www.", "")
    if any(h in host for h in SOCIAL_HOSTS):
        return "social"
    if any(h in host for h in DIRECTORY_HOSTS):
        return "directory"
    if any(h in host for h in AGGREGATOR_HOSTS):
        return "aggregator"
    return "website"


def social_name(url: str) -> str:
    host = (urlparse(url).netloc or "").lower().replace("www.", "")
    for key in ("facebook", "instagram", "justdial", "sulekha", "linkedin",
                "youtube", "twitter", "yelp", "zomato", "tripadvisor"):
        if key in host:
            return key
    return host.split(".")[0] if host else "link"


# ---------------------------------------------------------------------------
# Keyless web search via ddgs / duckduckgo_search
# ---------------------------------------------------------------------------
def web_search(query: str, max_results: int = 8) -> list[dict]:
    DDGS = None
    try:
        from ddgs import DDGS as _D
        DDGS = _D
    except ImportError:
        try:
            from duckduckgo_search import DDGS as _D
            DDGS = _D
        except ImportError:
            return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:  # noqa: BLE001
        C.log(f"search failed for '{query}': {e}", "WARN")
        return []


# Generic words that don't help confirm we found the RIGHT business. "Healing
# Hands", "Parel", "Mumbai" are distinctive; "clinic"/"best"/"care" are not.
RELEVANCE_STOPWORDS = {
    "the", "and", "for", "with", "clinic", "clinics", "centre", "center",
    "care", "best", "hospital", "hospitals", "and", "dr", "doctor", "ltd",
    "pvt", "private", "limited",
}


def relevance_tokens(*parts: str) -> set[str]:
    """Distinctive lowercase tokens (name + location) used to confirm a search
    hit is actually the business we're after — not a same-host coincidence."""
    words = re.findall(r"[a-z0-9]+", " ".join(parts).lower())
    return {w for w in words if len(w) > 2 and w not in RELEVANCE_STOPWORDS}


def _result_blob(r: dict) -> str:
    return " ".join(
        str(r.get(k, "")) for k in ("title", "body", "snippet", "href", "url", "link")
    ).lower()


def is_relevant(r: dict, tokens: set[str]) -> bool:
    """A hit is relevant only if at least one distinctive business token appears
    in its title/snippet/url. Kills garbage host-matches (e.g. the first random
    instagram.com result for a query) before they pollute the manifest."""
    if not tokens:
        return True
    return any(t in _result_blob(r) for t in tokens)


def first_match(results: list[dict], wanted_host: str,
                tokens: set[str] | None = None) -> str | None:
    tokens = tokens or set()
    for r in results:
        url = r.get("href") or r.get("url") or r.get("link") or ""
        if wanted_host in (urlparse(url).netloc or "").lower() and is_relevant(r, tokens):
            return url
    return None


# ---------------------------------------------------------------------------
# Google Business Profile extraction (best-effort)
# ---------------------------------------------------------------------------
def scrape_google_profile(url: str) -> dict:
    out = {"website": None, "description": None, "photos": [], "phone": None,
           "address": None, "note": ""}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out["note"] = "playwright not installed"
        return out

    for variant in ({}, {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, **variant)
                page = browser.new_page(viewport={"width": 1280, "height": 900},
                                        locale="en-US")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)

                # Website link (authority button on the profile).
                for sel in ('a[data-item-id="authority"]',
                            'a[aria-label*="Website"]',
                            'a[data-tooltip="Open website"]'):
                    try:
                        el = page.query_selector(sel)
                        if el:
                            href = el.get_attribute("href")
                            if href and classify(href) == "website":
                                out["website"] = href
                                break
                    except Exception:  # noqa: BLE001
                        continue

                # Phone + address (best-effort via aria-labels).
                try:
                    ph = page.query_selector('button[data-item-id^="phone"]')
                    if ph:
                        out["phone"] = (ph.get_attribute("aria-label") or "").replace("Phone: ", "").strip() or None
                    addr = page.query_selector('button[data-item-id="address"]')
                    if addr:
                        out["address"] = (addr.get_attribute("aria-label") or "").replace("Address: ", "").strip() or None
                except Exception:  # noqa: BLE001
                    pass

                # Photos: collect lh3 googleusercontent image URLs.
                try:
                    page.wait_for_timeout(1000)
                    html = page.content()
                    photos = re.findall(r"https://lh3\.googleusercontent\.com/[a-zA-Z0-9_\-/=.]+", html)
                    # de-dup, drop tiny icons (very short)
                    seen, clean = set(), []
                    for u in photos:
                        base = u.split("=")[0]
                        if base in seen or len(base) < 60:
                            continue
                        seen.add(base)
                        clean.append(base)
                    out["photos"] = clean[:30]
                except Exception:  # noqa: BLE001
                    pass

                browser.close()
                out["note"] = "ok"
                return out
        except Exception as e:  # noqa: BLE001
            out["note"] = f"playwright error: {e}"
            continue
    return out


# ---------------------------------------------------------------------------
# Main discovery
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    C.ensure_dirs()
    pin = C.parse_project_input()
    biz = pin["business"]
    name = biz.get("name", "").strip()
    location = biz.get("location", "").strip()
    google_url = biz.get("google_url", "").strip()

    if not name:
        C.log("No business name in project_input.md — cannot discover.", "ERROR")
        sys.exit(1)

    C.log(f"Discovering presence for: {name} ({location or 'no location'})")
    manifest = {
        "business_name": name,
        "type": biz.get("type", ""),
        "location": location,
        "discovered_at": C.now(),
        "google_profile_url": google_url or None,
        "phone": None,
        "address": None,
        "description": None,
        "google_photos": [],
        "sources": {},
    }

    existing_website = None

    # 1) Google profile (if URL provided)
    if google_url:
        C.log("Reading Google Business Profile…")
        g = scrape_google_profile(google_url)
        manifest["phone"] = g.get("phone")
        manifest["address"] = g.get("address")
        manifest["google_photos"] = g.get("photos", [])
        if g.get("website"):
            existing_website = g["website"]
            C.log(f"Website on Google profile: {existing_website}")
        C.log(f"Google profile photos found: {len(manifest['google_photos'])} (note: {g.get('note')})")
        manifest["sources"]["google_profile"] = {
            "url": google_url, "priority": 2, "type": "google",
            "photos": len(manifest["google_photos"]),
        }

    q_base = f"{name} {location}".strip()
    # Distinctive tokens to confirm a search hit is really THIS business.
    tokens = relevance_tokens(name, location)

    # 2) Existing website (if not already found via Google)
    if not existing_website:
        C.log("Searching for an existing official website…")
        results = web_search(f"{q_base} official website")
        for r in results:
            url = r.get("href") or r.get("url") or r.get("link") or ""
            if url and classify(url) == "website":
                existing_website = url
                break

    if existing_website:
        manifest["sources"]["existing_website"] = {
            "url": existing_website, "priority": 1, "type": "liquid_gold",
        }
        C.log(f"LIQUID GOLD — existing website: {existing_website}", "INFO")
    else:
        C.log("No existing website found. Will build purely from collected sources.", "WARN")

    # 3) Social + directory profiles
    lookups = [
        ("facebook", f"{q_base} facebook", "facebook.com", 3, "social"),
        ("instagram", f"{q_base} instagram", "instagram.com", 3, "social"),
        ("justdial", f"{q_base} justdial", "justdial.com", 4, "directory"),
        ("sulekha", f"{q_base} sulekha", "sulekha.com", 4, "directory"),
    ]
    for key, query, host, prio, typ in lookups:
        results = web_search(query, max_results=6)
        url = first_match(results, host, tokens)
        if url:
            manifest["sources"][key] = {"url": url, "priority": prio, "type": typ}
            C.log(f"Found {key}: {url}")
        else:
            C.log(f"No relevant {key} match (skipped same-host coincidences).")

    # 4) Recent news (kept as references, never invented)
    news = web_search(f"{q_base} news", max_results=5)
    news_links = []
    for r in news:
        url = r.get("href") or r.get("url") or r.get("link") or ""
        title = r.get("title") or ""
        if url and classify(url) not in ("aggregator",) and is_relevant(r, tokens):
            news_links.append({"title": title[:120], "url": url})
    if news_links:
        manifest["sources"]["news"] = {"priority": 5, "type": "news", "items": news_links[:5]}
        C.log(f"News mentions: {len(news_links[:5])}")

    C.write_json(C.TMP / "business_manifest.json", manifest)
    C.log(f"Wrote .tmp/business_manifest.json — {len(manifest['sources'])} source groups.")


if __name__ == "__main__":
    main(sys.argv[1:])
