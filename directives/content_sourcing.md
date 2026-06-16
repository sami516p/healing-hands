# Directive: Content Sourcing (No-Hallucination Rule)

## Purpose
Define how sections get filled and what happens when they can't be. This is the rule that prevents the "mediocre, generic website" failure mode: content must come from real collected data, or the section is explicitly left empty for the owner to fill — never fabricated.

## Section Reconciliation (Phase 4)
```
python execution/collect_assets.py reconcile
```

### How sections are determined
The master section list comes from:
1. The `## Section order` entries in each `reference_{domain}.md` — the structure of the design the user liked.
2. The `## Hard Requirements / Must include` list in `project_input.md`.
3. Sensible defaults (hero, about, services, gallery, contact) — these are always included.

### Fill priority (per section)
Try each source in this order; stop at the first one that has relevant data:

1. **Liquid gold** — `existing_site_content.md` (the business's own website)
2. **Google** — `google_profile.md` (description, hours, address, photos)
3. **Social** — `social_profiles.md` (FB/IG bios, JustDial service listings)
4. **News/web** — search snippet text (titles + URLs only; NOT used as body copy)

### Output: section_fill_report.md

| Section | Status | Source | Notes |
|---------|--------|--------|-------|
| hero | FILLED | liquid_gold | tagline + hero image |
| services | FILLED | google+liquid | prices from existing site |
| team | EMPTY | — | no stylist info anywhere |
| awards | EMPTY | — | none found — owner to provide |

## The Hard No-Hallucination Rule

> **If a section has no real data after all sources are exhausted:**
> - Build the section's HTML structure (wrapper, heading placeholder, grid/cards if appropriate).
> - Leave all content fields empty with an HTML comment marker:
>   `<!-- EMPTY: team — awaiting owner -->`
> - Log the section as EMPTY in `section_fill_report.md`.
> - **NEVER invent names, prices, quotes, team bios, awards, testimonials, or any facts.**
> - Report the EMPTY list in the Gemini handoff so Gemini also knows not to fill it.

This rule applies to **both Claude Code and Gemini**. An empty-but-structurally-built section is always better than an invented one. The owner fills it in one pass when you show them the draft.

## Content That IS Allowed
- Exact text from `existing_site_content.md` (the business wrote it)
- Business description from Google profile
- Phone, address, hours from Google profile
- Star rating + verbatim review snippets from Google (attributed)
- Service names found in JustDial/Sulekha listings (prices only if explicitly stated)
- Any images physically downloaded (not AI descriptions of images)

## Content That Is NEVER Allowed
- Invented service names, prices, or descriptions
- Fabricated team member names, titles, or bios
- Invented testimonials or review text
- Made-up awards, certifications, or accolades
- Any claim not directly traceable to a real collected source
