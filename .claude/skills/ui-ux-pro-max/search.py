#!/usr/bin/env python3
"""Design-system recommendation engine.

Usage:
    python search.py "<niche or vibe>"

Scores curated design systems from data/design_systems.json against the
query and prints the top 2-3 recommendations (palette, fonts, section order,
vibe, rationale). Deterministic and case-insensitive. Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "design_systems.json"

# Scoring weights.
NICHE_WEIGHT = 10      # strong: query matches a declared niche
TAG_WEIGHT = 4         # medium: query word overlaps vibe/tags
TOKEN_WEIGHT = 1       # small: partial token overlap anywhere


def tokenize(text):
    """Lower-case word tokens from a string."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def load_systems():
    """Load the curated design systems (utf-8)."""
    if not DATA_FILE.exists():
        print("ERROR: dataset not found at {}".format(DATA_FILE))
        sys.exit(1)
    with DATA_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("systems", [])


def score_system(query, system):
    """Return a deterministic relevance score for one system."""
    q = query.lower().strip()
    q_tokens = set(tokenize(query))
    score = 0

    # Strong: full-phrase or token match against declared niches.
    niches = [n.lower() for n in system.get("niches", [])]
    for niche in niches:
        if q == niche or q in niche or niche in q:
            score += NICHE_WEIGHT
        elif q_tokens & set(tokenize(niche)):
            score += NICHE_WEIGHT // 2

    # Medium: overlap against vibe + tags.
    tag_tokens = set()
    for tag in system.get("vibe", []):
        tag_tokens |= set(tokenize(tag))
    if q_tokens & tag_tokens:
        score += TAG_WEIGHT * len(q_tokens & tag_tokens)

    # Small: any token overlap with the name.
    name_tokens = set(tokenize(system.get("name", "")))
    if q_tokens & name_tokens:
        score += TOKEN_WEIGHT * len(q_tokens & name_tokens)

    return score


def format_system(system, rank, score):
    pal = system.get("palette", {})
    fonts = system.get("fonts", {})
    lines = []
    lines.append("{}. {}  (score {})".format(rank, system.get("name", "?"), score))
    lines.append("   niches : {}".format(", ".join(system.get("niches", []))))
    lines.append("   palette: bg {}  surface {}  text {}  primary {}  accent {}".format(
        pal.get("bg", "-"), pal.get("surface", "-"), pal.get("text", "-"),
        pal.get("primary", "-"), pal.get("accent", "-")))
    lines.append("   fonts  : heading '{}'  /  body '{}'".format(
        fonts.get("heading", "-"), fonts.get("body", "-")))
    lines.append("   sections: {}".format(" > ".join(system.get("section_patterns", []))))
    lines.append("   vibe   : {}".format(", ".join(system.get("vibe", []))))
    lines.append("   why    : {}".format(system.get("rationale", "")))
    return "\n".join(lines)


def print_usage(systems):
    print("Usage: python search.py \"<niche or vibe>\"")
    print("Example: python search.py \"luxury spa\"")
    print("")
    print("Available niches:")
    seen = []
    for s in systems:
        for n in s.get("niches", []):
            if n not in seen:
                seen.append(n)
    for n in seen:
        print("  - {}".format(n))


def main():
    parser = argparse.ArgumentParser(
        description="Recommend a design system for a niche or vibe.",
        add_help=True)
    parser.add_argument("query", nargs="?", help="niche or vibe, e.g. \"dental clinic\"")
    args = parser.parse_args()

    systems = load_systems()

    if not args.query or not args.query.strip():
        print_usage(systems)
        return

    scored = []
    for idx, s in enumerate(systems):
        scored.append((score_system(args.query, s), idx, s))
    # Sort by score desc, then original order for determinism.
    scored.sort(key=lambda t: (-t[0], t[1]))

    top = [t for t in scored if t[0] > 0][:3]
    if not top:
        top = scored[:2]  # fall back to first systems if nothing matched
        print("No strong match for '{}'. Showing closest general options:\n".format(args.query))
    else:
        print("Top recommendations for '{}':\n".format(args.query))

    for rank, (score, _idx, system) in enumerate(top, start=1):
        print(format_system(system, rank, score))
        print("")

    print("Follow the #1 recommendation's palette, fonts, and section order unless")
    print("the design brief explicitly overrides them.")


if __name__ == "__main__":
    main()
