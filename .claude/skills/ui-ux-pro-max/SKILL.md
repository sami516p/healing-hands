---
name: ui-ux-pro-max
description: A design-system recommendation engine; invoke at the START of any demo website design work or design-system decision, before touching HTML or CSS.
---

# UI/UX Pro Max — Design System Recommender

## Purpose
Turn a business niche or desired vibe into a concrete, tasteful design system:
an accessible color palette, a real Google Font pairing, a sensible section
order, and a one-line rationale. This removes guesswork and keeps every demo
build visually coherent and on-brand for its industry.

## When to invoke
- At the very START of design work for a new demo site (Phase 5 design brief,
  or before writing any markup in Phase 6).
- Any time a design-system decision comes up: "what palette/fonts for a
  barbershop?", "what sections should a dental clinic site have?".
- BEFORE touching `index.html` or `css/style.css`. The recommendation is the
  spec; the build must follow it.

## Steps
1. Identify the business niche or vibe (e.g. `salon`, `luxury spa`,
   `dental clinic`, `barbershop`, `medspa`, `wellness`).
2. From the project root, run:
   ```
   python .claude/skills/ui-ux-pro-max/search.py "<niche or vibe>"
   ```
   With no argument it prints usage plus the list of available niches.
3. Read the top result. It reports:
   - palette hexes for `bg`, `surface`, `text`, `primary`, `accent`
   - a heading/body Google Font pairing
   - the recommended ordered section list
   - vibe tags and a one-line rationale
4. Adopt the #1 recommendation as the design system. Feed its palette and fonts
   into the design brief / CSS variables, and use its section order as the page
   skeleton.
5. Only deviate if the design brief (`design_brief.md`) explicitly overrides a
   choice — the brief is authoritative when it conflicts.

## Data
Recommendations come from the curated dataset
`data/design_systems.json` (real hexes, real Google Font names, ordered
section patterns). This is curated design reference data — extend it with new
tasteful entries as the library grows; never invent business facts here.

## Output
A chosen palette, font pairing, and section order that the subsequent
HTML/CSS build follows exactly.
