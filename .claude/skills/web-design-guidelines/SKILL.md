---
name: web-design-guidelines
description: Audit HTML/CSS against web interface guidelines; auto-invoke during Phase 4 QA of every demo build before deploying.
---

# Web Design Guidelines — Static QA Audit

## Purpose
Catch common accessibility, SEO, and structural problems in a demo build
BEFORE it ships. It statically analyzes the generated `index.html` and
`css/style.css` and reports PASS / WARN / FAIL per check, so Phase 4 QA is
consistent and never relies on eyeballing.

## When to invoke
- During Phase 4 QA of every demo build, before running deploy.
- Any time after editing `index.html` or `css/style.css` and you want a quick
  structural sanity check.

## Steps
1. From the project root, run:
   ```
   python .claude/skills/web-design-guidelines/audit.py
   ```
   Optionally point at non-default paths:
   ```
   python .claude/skills/web-design-guidelines/audit.py --html index.html --css css/style.css
   ```
2. Read the per-check output. Missing files are reported as FAIL with a message
   (the script still exits 0 — it is a report, not a gate).
3. Resolve every FAIL and review each WARN before advancing the phase.

## Checks
- `html lang`        — `<html lang=...>` present (FAIL if missing)
- `viewport meta`    — `<meta name=viewport>` present (FAIL if missing)
- `title`            — non-empty `<title>` (FAIL if empty/missing)
- `meta description` — present (WARN if missing)
- `single h1`        — exactly one `<h1>` (FAIL otherwise)
- `heading order`    — no skipped heading levels h1->h2->h3 (WARN on skips)
- `img alt`          — every `<img>` has non-empty alt (FAIL, lists offenders)
- `EMPTY markers`    — flags `<!-- EMPTY` unfilled sections (WARN, lists them)
- `font stacks`      — distinct font-family stacks in CSS (WARN if > 3)
- `nav landmark`     — a `<nav>` element present (WARN if missing)

Ends with a summary line of PASS / WARN / FAIL counts.

## Notes
This is STATIC analysis (HTML/CSS parsing only). It does not render the page,
so it cannot catch runtime layout, contrast-in-context, or interaction issues.
Pair it with a live Playwright pass (the run-audit workflow / Phase 7 debug
screenshot) for full coverage.

## Output
A PASS/WARN/FAIL report printed to stdout. Use it as the Phase 4 checklist:
zero FAILs before deploy.
