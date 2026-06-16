# Directive: Claude / Gemini Split Protocol

## The Contract
Claude Code and Gemini share the same project folder. Files are the only communication channel. Neither AI talks to the other directly — they talk through files the supervisor validates. This is what prevents the "AI ignored the reference and went its own way" failure.

## Lane Ownership

| Phase | Owner | What they do | What they must NOT do |
|-------|-------|-------------|----------------------|
| 0. Init | Supervisor | Archive + reset workspace | — |
| 1. Business discovery | **Claude Code** | Run `discover_business.py` | Invent sources or URLs |
| 2. Asset collection | **Claude Code** | Run `collect_assets.py collect` | Invent content; skip liquid gold |
| 3. Reference extraction | **Claude Code** | Run `fetch_reference_site.py` | Skip any reference URL from project_input |
| 4. Section reconciliation | **Claude Code** | Run `collect_assets.py reconcile` | Mark a section FILLED with invented data |
| — | **Supervisor** | Validate + write handoff + PAUSE | Advance without validating |
| 5. Design brief + images | **Gemini** | Write design_brief.md; generate images | Write code; edit scripts; invent EMPTY content |
| — | **Supervisor** | Validate brief + RESUME | Resume without validating brief |
| 6. Code generation | **Claude Code** | Build index.html + css/style.css | Deviate from design_brief.md |
| 7. Debug | **Claude Code** | Screenshot + fix | Modify design_brief.md |
| — | **Supervisor** | Validate + handoff + PAUSE | — |
| 8. Visual review | **Gemini** | Append `## Review Notes` to design_brief.md | Rewrite brief; touch code |
| R. Revision | **Claude Code** | Read revision_log.md + make targeted edits to index.html/css | Re-read Phase 1–4 files; restructure sections not in feedback; fill EMPTY sections; add unlisted images |
| 9. Archive | **Supervisor** | Seal + clean | — |

## Handoff Protocol

### Claude → Gemini (before Phase 5)
1. Claude Code completes Phases 1–4.
2. Run: `python execution/supervisor.py handoff gemini-brief`
3. Supervisor writes `.tmp/supervisor_status.md` with exact instructions.
4. User switches to Gemini in Antigravity. Tell it: **"Read .tmp/supervisor_status.md and do your phase."**
5. Gemini reads the file; writes `design_brief.md`; generates images.
6. User switches back. Run: `python execution/supervisor.py run`

### Gemini → Claude (before Phase 6)
1. Supervisor validates `design_brief.md` on resume.
2. If valid: Claude Code reads the brief and builds the site.
3. If invalid (missing fields): supervisor reports exactly which fields are missing; user asks Gemini to fill them.

### Claude → Gemini (before Phase 8)
Same pattern: `handoff gemini-review` → user switches → Gemini reviews screenshot → user switches back → `run`.

## Non-Negotiable Rules for Both AIs

**Claude Code:**
- `design_brief.md` is the authoritative specification for code generation. Follow it exactly.
- Never advance a phase without `supervisor.py validate`.
- Never switch to Gemini without `supervisor.py handoff`.
- Unfillable section = build the structure, leave EMPTY with a marker. Never invent.
- `existing_site_content.md` is the primary content source when it exists.

**Gemini:**
- Read `supervisor_status.md` FIRST before doing anything in Phase 5 or Phase 8.
- `section_fill_report.md` is the authority on what's EMPTY — do not override it.
- If `liquid_gold_available` is flagged in status: `existing_site_content.md` is your primary copy source.
- If a `reference_*.png` exists: reconstruct that site's section structure from the screenshot.
- Do not write code. Do not edit execution scripts. Do not modify any file except `design_brief.md` and `images_manifest.json`.
- Phase 8: append change requests only. Do not rewrite the brief.

## The Filing Rule
**Handoff is always a file, never verbal.** If Gemini needs to communicate a design decision to Claude, it belongs in `design_brief.md`. If Claude needs to communicate a content gap to Gemini, it belongs in `section_fill_report.md`. The supervisor's `supervisor_status.md` is the bridge.

## Revision Handoff Protocol

Revision rounds are Claude-only — no Gemini involvement. The loop:

1. User runs `supervisor.py revise "<feedback>"` from PREVIEW state
2. Supervisor records feedback in `.tmp/revision_log.md`, sets state to REVISING, prints Claude action banner
3. Claude reads `.tmp/design_brief.md` + `.tmp/revision_log.md` + existing code (ONLY these 3 files)
4. Claude makes targeted edits — touches ONLY elements named in the feedback
5. Claude writes/updates `.tmp/r1_quality_audit.md` (zero [FAIL] required)
6. Claude writes `.tmp/r2_audit_roundN.md` (R1 carry-forward + scope compliance)
7. Claude takes both screenshots (1440px + 375px)
8. Claude runs `supervisor.py advance code`
9. Supervisor validates → routes to PREVIEW (bypasses Gemini review)
10. Loop repeats until user runs `supervisor.py advance preview` to deploy

**What triggers Gemini review vs. revision loop:**
- First build (Phase 8): Gemini reviews via handoff (`supervisor.py handoff gemini-review`)
- Subsequent rounds: Claude revision loop only — no Gemini involvement
- The presence of `.tmp/revision_log.md` is the flag that tells the supervisor to route `DEBUG_DONE → PREVIEW` instead of `DEBUG_DONE → AWAITING_GEMINI_REVIEW`
