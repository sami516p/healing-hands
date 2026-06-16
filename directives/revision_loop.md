# Directive: Revision Loop — Round 2+

## Purpose
The revision loop is a surgical edit pass. It is NOT a rebuild. It does NOT re-read discovery files, Google profiles, reference sites, or any Phase 1–4 output. It reads exactly 3 files and edits the existing code.

---

## Trigger
User runs:
```
python execution/supervisor.py revise "<feedback>"
```
From `PREVIEW` state. Supervisor stops the preview server, records feedback in `.tmp/revision_log.md`, sets state to `REVISING`, and shows the Claude action banner.

---

## Reading Order (mandatory — no substitutions)

Claude reads ONLY these 3 files for every revision round:

1. `.tmp/design_brief.md` — the visual law. Colors, fonts, section spec. Still authoritative.
2. `.tmp/revision_log.md` — all feedback rounds in chronological order, latest at bottom.
3. `index.html` + `css/style.css` — the current code to modify.

That is all. No re-reading of discovery files, no re-reading of reference sites, no Phase 1–4 outputs.

---

## Change Scope Rules

**Touch ONLY what the feedback names.** If feedback says "fix the gallery grid", touch only `#gallery` and its CSS. Do not touch the hero, nav, footer, or any other section.

Every changed line must be traceable to either:
- The latest round's feedback, OR
- `design_brief.md` (as the corrective authority)

If feedback is ambiguous ("make it look better"), interpret the simplest, most conservative reading. Do not restructure unless restructuring was explicitly asked for.

**Never:**
- Restructure sections not mentioned in the feedback
- Rename sections or IDs
- Add sections not in `design_brief.md`
- Remove sections
- Add images not present in `images_manifest.json`
- Fill EMPTY-marked sections (they stay EMPTY until the owner provides content)
- Introduce new font families or colors not in the design brief

---

## Round 1 Standards Carry Forward

After applying feedback, ALL Round 1 checks must still pass:
- All mechanical checks (section coverage, no broken images, viewport meta, etc.)
- All design checks (hero quality, typography, color, section padding, CTA density, mobile)

A revision that fixes one thing but breaks another does not pass. Fix regressions before advancing.

---

## Audit Requirement (mandatory before `advance code`)

For each revision round, Claude writes TWO files:

### 1. Update `.tmp/r1_quality_audit.md`
Re-run the full R1 audit. If anything that was passing is now failing (regression), it must be fixed and the audit updated.

### 2. Write `.tmp/r2_audit_round{N}.md` (new file per round)
```
# R2 Audit — Round N — <project>

## R1 Standards Still Passing
- [PASS/FAIL] All 6 mechanical checks
- [PASS/FAIL] Typography
- [PASS/FAIL] Color
- [PASS/FAIL] Hero
- [PASS/FAIL] Section quality
- [PASS/FAIL] CTA density
- [PASS/FAIL] Contact links
- [PASS/FAIL] Image handling
- [PASS/FAIL] Logo mark proportions: extracted PNG w/h ratio within ±5% of source mark bbox; `.logo-img` width/height hardcoded
- [PASS/FAIL] Design system consistency
- [PASS/FAIL] Social proof
- [PASS/FAIL] Mobile 375px

## Revision Scope Compliance
- [PASS/FAIL] Every item in Round N feedback addressed
- [PASS/FAIL] No sections modified outside feedback scope
- [PASS/FAIL] No new EMPTY markers introduced
- [PASS/FAIL] Screenshots taken (desktop + mobile, both > 20KB)

## Changes Made
| Feedback Item | What Changed | File + Approx Line |
|---|---|---|
| ... | ... | ... |

## Regressions Found and Fixed
<List any unintentional breakage and what was done to fix it. "None" if clean.>
```

---

## Screenshot Requirement (same as Round 1)

Take two Playwright screenshots after completing edits:
- `.tmp/build_screenshot_desktop.png` — viewport 1440×900
- `.tmp/build_screenshot_mobile.png` — viewport 375×812

Both must be > 20KB.

---

## Documenting in `revision_log.md`

After making changes, fill in the `### Changes Made` subsection under the current round heading. Map each change to a feedback item. This creates an audit trail showing what changed per round.

---

## When Done

Run: `python execution/supervisor.py advance code`

The supervisor validates:
1. `r1_quality_audit.md` exists with zero `[FAIL]` lines
2. 6 mechanical checks pass
3. Both screenshots > 20KB

If all pass → supervisor routes back to `PREVIEW` (bypasses Gemini review). Preview server restarts. User sees the updated site.

If any fail → `advance code` is blocked. Fix → re-audit → re-advance.

---

## To Deploy Without More Changes

From PREVIEW state: `python execution/supervisor.py advance preview`
This skips revision entirely and deploys directly.

---

## The No-Reread Rule (critical)

The revision loop's speed comes from NOT re-reading everything. The design brief + revision log + existing code contain all the information needed for a targeted edit. Re-reading discovery files is wasted time and risks confusing the edit with stale source content. Never do it.
