# Directive: Round 1 Quality Standard — Shipping Quality

## Purpose
This is the creative director. Every item is a binary PASS/FAIL. Claude must pass ALL items before running `supervisor.py advance code`. No exceptions. No half-measures.

A website that passes this checklist is deployable to a real client. A website that fails is not.

---

## A. Mechanical Checks (auto-enforced by supervisor)

These run automatically when Claude calls `advance code`. Claude cannot advance if any fail.

1. **Section coverage** — every slug in `design_brief.md` `section_order` has a matching `id=` in `index.html`
2. **EMPTY markers** — sections marked EMPTY in `section_fill_report.md` have `<!-- EMPTY:` comment in HTML
3. **Responsive meta** — `<meta name="viewport"` present in `<head>`
4. **No broken local images** — every `src="assets/..."` path referenced in HTML exists on disk
5. **Screenshots non-blank** — `.tmp/build_screenshot_desktop.png` > 20KB AND `.tmp/build_screenshot_mobile.png` > 20KB
6. **HTML structure** — `<nav>` or `<header>` present; element with `id` containing `hero` present; `<footer>` present

---

## B. Design Quality Checks (Claude self-audits, writes `.tmp/r1_quality_audit.md`)

Claude self-audits EVERY item below before calling `advance code`. Writes results to `.tmp/r1_quality_audit.md`. Any `[FAIL]` blocks advance — fix first, then re-audit.

### Typography
- [ ] Max 2 font families. No 3+ font families. Deliberate pairing only.
- [ ] H1 ≥ 36px. Body text ≥ 16px. No Times New Roman or default browser serif for body.
- [ ] Line-height on all `<p>` text ≥ 1.6.
- [ ] Max-width on body text ≤ 70ch. No full-width wall-of-text paragraphs.
- [ ] Clear visual hierarchy: H1 is the single largest, most dominant text on the page.

### Color
- [ ] Palette comes ONLY from `design_brief.md`. No colors introduced that aren't in the brief.
- [ ] Body text on its background passes WCAG AA (4.5:1 contrast ratio). No grey-on-grey.
- [ ] Primary brand color used for all CTAs. Secondary used for accents. Not randomly swapped.

### Hero Section (non-negotiable)
- [ ] Hero section is minimum 60vh height.
- [ ] Hero contains: H1 headline, sub-headline or short descriptor, and at least one CTA button.
- [ ] Hero background is an image (from `assets/`) or a gradient — NOT plain white or flat solid.
- [ ] CTA is a styled `<button>` or styled `<a class="btn">` — not a bare text hyperlink.

### Section Quality (applies to every section)
- [ ] No section is heading + paragraph alone. Every section has at least ONE visual element: image, icon row, card grid, blockquote with avatar, stat counter, or similar.
- [ ] Section padding ≥ 80px top AND bottom. No cramped content.
- [ ] Clear visual break between adjacent sections (alternating background, divider, or strong whitespace).

### CTA Density
- [ ] At least 2 CTAs visible above the fold (hero + nav).
- [ ] Every service/offering section has a link to contact or booking.
- [ ] No dead ends: user is never more than 1 click from a contact method.

### Contact Accessibility
- [ ] Phone number uses `href="tel:..."` — not plain text.
- [ ] Email address uses `href="mailto:..."` — not plain text.

### Image Handling
- [ ] All images inside containers use `object-fit: cover`. No stretched or squished images.
- [ ] No image element forced wider than its natural dimensions with `width: 100%` on a small source.
- [ ] **Logo mark proportions**: if a logo mark PNG was produced by `extract_logo.py mark`, verify its w/h ratio matches the source brand image mark (within ±5%). Method: open the extracted PNG, note w/h ratio; open the source image, measure the mark's tight color bbox w/h. If ratio diverges > 5%, re-run extraction and hardcode corrected `width` + `height` on `.logo-img`.

### Design System Consistency
- [ ] Border-radius is the same value (or an intentional scale) across all cards, buttons, and inputs.
- [ ] Button style is consistent: one primary variant, optional secondary — not 4 different random styles.
- [ ] If icons are used: all same style (all filled OR all outline — never mixed).

### Social Proof
- [ ] If testimonials exist in sources: rendered as styled cards or blockquotes with name, avatar/initial, and body — not a plain `<p>` tag.
- [ ] If no testimonials in sources: EMPTY marker present — never invented.

### Mobile at 375px
- [ ] Navigation collapses to hamburger or stacked links — no horizontal overflow.
- [ ] Hero headline is fully readable (no clipping, no font overflow).
- [ ] All buttons are tap-friendly: min-height 44px.
- [ ] No horizontal scrollbar at 375px.

---

## C. Self-Audit File Format

Claude writes `.tmp/r1_quality_audit.md` BEFORE calling `advance code`. Supervisor checks it.

```
# R1 Quality Audit — <project name>

## Mechanical Checks
- [PASS/FAIL] Section coverage
- [PASS/FAIL] EMPTY markers
- [PASS/FAIL] Responsive meta
- [PASS/FAIL] No broken local images
- [PASS/FAIL] Screenshots non-blank (desktop + mobile)
- [PASS/FAIL] HTML structure (nav/header, hero id, footer)

## Design Checks
- [PASS/FAIL] Typography: max 2 families, H1 ≥ 36px, body ≥ 16px, line-height ≥ 1.6, max-width ≤ 70ch
- [PASS/FAIL] Color: brief-only palette, WCAG AA contrast, consistent CTA color
- [PASS/FAIL] Hero: ≥ 60vh, H1 + CTA, non-white/non-flat background
- [PASS/FAIL] Section quality: visual element per section, ≥ 80px padding, visual breaks
- [PASS/FAIL] CTA density: 2+ above fold, every service section linked, no dead ends
- [PASS/FAIL] Contact: tel: and mailto: links
- [PASS/FAIL] Image handling: object-fit cover, no stretch
- [PASS/FAIL] Design system: consistent radius, button styles, icon style
- [PASS/FAIL] Social proof: cards/blockquotes or EMPTY marker
- [PASS/FAIL] Mobile 375px: nav collapses, hero readable, 44px buttons, no h-scroll

## FAILs — Fixed Before Advancing
<For each FAIL: name the element/selector and describe the fix applied>
```

**The rule:** If `r1_quality_audit.md` contains any `[FAIL]` line, `advance code` is blocked by the supervisor. Fix → update the audit → advance.

---

## D. Screenshot Requirements

Phase 7 (debug) requires TWO screenshots, not one:
- `.tmp/build_screenshot_desktop.png` — viewport 1440×900
- `.tmp/build_screenshot_mobile.png` — viewport 375×812

Both must be > 20KB (proves they are not blank error pages).

Both are taken with Playwright before calling `advance debug`.

---

## E. Reading Order for Phase 6

Before writing a single line of HTML, Claude reads in this order:
1. `directives/quality_standard_r1.md` — this file (the standard to hit)
2. `.tmp/design_brief.md` — the visual spec from Gemini
3. All `reference_*.md` files — structure and layout patterns to borrow
4. `.tmp/existing_site_content.md` (if exists) — the liquid gold primary copy source
5. `.tmp/section_fill_report.md` — what is FILLED vs EMPTY

This is the only reading order. Do not skip steps.
