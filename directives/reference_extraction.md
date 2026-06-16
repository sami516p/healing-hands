# Directive: Reference Extraction

## Purpose
Extract the structural DNA of a design reference website so Claude can reproduce its layout, typographic system, and color palette — not its content — in the new site. This is the mechanism that prevents mediocre layouts.

## Script
```
python execution/fetch_reference_site.py [--url https://site.com ...]
```
If no `--url` is given, URLs are read from `## Design References` in `inputs/project_input.md`.

## Two-Mode Operation

### Mode A — HTML extraction (always attempted first)
1. `requests.get()` the URL.
2. If the body has < 500 words (JS-heavy SPA/React/Next): re-render with Playwright.
3. Parse with BeautifulSoup, extract:
   - **Section order**: all `<header>`, `<nav>`, `<section>`, `<main>`, `<footer>`, and any `<div>` whose id/class matches a known section hint (hero, about, services, gallery, team, testimonials, contact, etc.).
   - **Navigation**: `<a>` text inside `<nav>` or `<header>`.
   - **Fonts**: Google Fonts `family=` params + `font-family:` declarations in linked CSS (regex, no cssutils needed). Skip `var()`, SCSS `$` variables, and generic families.
   - **Color palette**: CSS custom properties (`--color-*`) + most-frequent hex values across CSS and inline styles.
   - **Layout system**: Detect CSS Grid, Flexbox, Bootstrap columns, container max-width.
   - **Image hosting**: domain + sample URLs from `<img>` tags.
4. Write to `.tmp/reference_{domain}.md`.

### Mode B — Visual backtrack (fallback, when Mode A yields < 200 words of body text)
1. Capture a **full-page Playwright screenshot** → `.tmp/reference_{domain}.png`.
2. Write `.tmp/reference_{domain}.md` marked `mode: visual-backtrack`.
3. The `supervisor_status.md` handoff note tells Gemini to **reconstruct the section structure from the PNG** when writing the design brief.

## Edge Cases

| Situation | Action |
|-----------|--------|
| Anti-bot / Cloudflare blocks HTML | Mode B: screenshot immediately, log reason |
| Auth wall (login required) | Mark `reference_{domain}.md` as `mode: auth-wall`; log for user; do not fabricate structure |
| JS SPA with < 200 words even after Playwright | Mode B: screenshot |
| Screenshot also fails | Write `mode: failed` to `.md`; log precise error; never invent structure |
| Multiple reference URLs | Process each independently → one `reference_{domain}.md` per domain |

## Output Schema (reference_{domain}.md)
```
## Section order
1. `<tag>` · <id or class> — "<heading text>"
...

## Navigation
Link 1 · Link 2 · ...

## Fonts
- Font Family Name
...

## Colors
**Palette (most frequent):** #aaa, #bbb ...
**Design tokens:** --color-primary: #aaa ...

## Layout system
- CSS Grid
- Flexbox
- container max-width ~1200px

## Image hosting pattern
- domain (N imgs)
```

## Self-annealing note
If you encounter a new extraction failure pattern not covered above, fix it, add a row to the edge-case table above, and log it via `supervisor.py heal`. The script itself should be patched to handle the new case automatically next time.
