#!/usr/bin/env python3
"""Static web-design / accessibility audit for a demo build.

Usage:
    python audit.py [--html index.html] [--css css/style.css]

Checks index.html + css/style.css against common web interface guidelines and
prints PASS / WARN / FAIL per check plus a summary. Static analysis only — pair
with a live Playwright pass (run-audit) for runtime checks. Always exits 0.
Standard library only.
"""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

counts = {PASS: 0, WARN: 0, FAIL: 0}


def report(status, label, note=""):
    counts[status] += 1
    suffix = "  {}".format(note) if note else ""
    print("[{}] {}{}".format(status, label, suffix))


class DOMCollector(HTMLParser):
    """Collect the structural facts we need for the checks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_attrs = None
        self.metas = []          # list of dict(attrs)
        self.title_parts = []
        self._in_title = False
        self.headings = []       # ("h1".."h6")
        self.images = []         # list of dict(attrs)
        self.has_nav = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        tag = tag.lower()
        if tag == "html":
            self.html_attrs = d
        elif tag == "meta":
            self.metas.append(d)
        elif tag == "title":
            self._in_title = True
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(tag)
        elif tag == "img":
            self.images.append(d)
        elif tag == "nav":
            self.has_nav = True

    def handle_startendtag(self, tag, attrs):
        # Self-closing tags (e.g. <meta />, <img />).
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)

    @property
    def title_text(self):
        return "".join(self.title_parts).strip()


def read_text(path):
    """Read a file as utf-8; return None if missing/unreadable."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def meta_by_name(metas, name):
    name = name.lower()
    for m in metas:
        if m.get("name", "").lower() == name:
            return m
    return None


def audit_html(html_path, html_text):
    dom = DOMCollector()
    dom.feed(html_text)

    # (a) <html lang=...>
    if dom.html_attrs is not None and dom.html_attrs.get("lang", "").strip():
        report(PASS, "html lang", "lang='{}'".format(dom.html_attrs.get("lang")))
    else:
        report(FAIL, "html lang", "missing lang attribute on <html>")

    # (b) viewport meta
    if meta_by_name(dom.metas, "viewport"):
        report(PASS, "viewport meta")
    else:
        report(FAIL, "viewport meta", "no <meta name=viewport>")

    # (c) non-empty <title>
    if dom.title_text:
        report(PASS, "title", "'{}'".format(dom.title_text[:60]))
    else:
        report(FAIL, "title", "missing or empty <title>")

    # (d) description meta (WARN if missing)
    desc = meta_by_name(dom.metas, "description")
    if desc and desc.get("content", "").strip():
        report(PASS, "meta description")
    else:
        report(WARN, "meta description", "missing — add for SEO/social")

    # (e) exactly one <h1>
    h1_count = dom.headings.count("h1")
    if h1_count == 1:
        report(PASS, "single h1")
    elif h1_count == 0:
        report(FAIL, "single h1", "no <h1> found")
    else:
        report(FAIL, "single h1", "{} <h1> elements (expected 1)".format(h1_count))

    # (f) heading order has no skipped levels
    skips = []
    prev = 0
    for h in dom.headings:
        level = int(h[1])
        if prev and level > prev + 1:
            skips.append("h{}->h{}".format(prev, level))
        prev = level
    if not dom.headings:
        report(WARN, "heading order", "no headings found")
    elif skips:
        report(WARN, "heading order", "skipped levels: {}".format(", ".join(skips)))
    else:
        report(PASS, "heading order")

    # (g) every <img> has non-empty alt
    offenders = []
    for i, img in enumerate(dom.images):
        if "alt" not in img or not img.get("alt", "").strip():
            src = img.get("src", "?")
            offenders.append(src if src != "?" else "img#{}".format(i + 1))
    if not dom.images:
        report(PASS, "img alt", "no images")
    elif offenders:
        report(FAIL, "img alt", "missing/empty alt: {}".format(", ".join(offenders[:8])))
    else:
        report(PASS, "img alt", "{} images all have alt".format(len(dom.images)))

    # (h) <!-- EMPTY markers (unfilled sections)
    empty_markers = re.findall(r"<!--\s*EMPTY[^>]*?-->", html_text, re.IGNORECASE)
    if empty_markers:
        sample = [m.strip() for m in empty_markers[:6]]
        report(WARN, "EMPTY markers",
               "{} unfilled section(s): {}".format(len(empty_markers), " | ".join(sample)))
    else:
        report(PASS, "EMPTY markers", "none")

    # (j) nav landmark
    if dom.has_nav:
        report(PASS, "nav landmark")
    else:
        report(WARN, "nav landmark", "no <nav> element found")


def audit_css(css_path, css_text):
    # (i) distinct font-family stacks
    stacks = set()
    for m in re.finditer(r"font-family\s*:\s*([^;}}]+)", css_text, re.IGNORECASE):
        stack = re.sub(r"\s+", " ", m.group(1)).strip().strip("'\"").lower()
        if stack:
            stacks.add(stack)
    n = len(stacks)
    if n == 0:
        report(WARN, "font stacks", "no font-family declared in CSS")
    elif n <= 3:
        report(PASS, "font stacks", "{} distinct".format(n))
    else:
        report(WARN, "font stacks", "{} distinct (>3 — consider consolidating)".format(n))


def main():
    parser = argparse.ArgumentParser(
        description="Static web-design/accessibility audit (always exits 0).")
    parser.add_argument("--html", default="index.html", help="path to HTML file")
    parser.add_argument("--css", default="css/style.css", help="path to CSS file")
    args = parser.parse_args()

    print("== Web Design Guidelines Audit (static analysis) ==")
    print("html: {}   css: {}\n".format(args.html, args.css))

    html_text = read_text(args.html)
    if html_text is None:
        report(FAIL, "html file", "not found: {}".format(args.html))
    else:
        audit_html(args.html, html_text)

    css_text = read_text(args.css)
    if css_text is None:
        report(FAIL, "css file", "not found: {}".format(args.css))
    else:
        audit_css(args.css, css_text)

    print("\nSummary: {} PASS, {} WARN, {} FAIL".format(
        counts[PASS], counts[WARN], counts[FAIL]))
    print("(Static analysis only — run the live Playwright pass for runtime checks.)")

    # Always a report: exit 0 regardless of findings.
    sys.exit(0)


if __name__ == "__main__":
    main()
