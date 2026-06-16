# Directive: Web Project Workflow

## Purpose
Master SOP for building any client website. Defines the full phase sequence, who owns each phase, what the handoff files are, and what "done" means at each step.

## Inputs (fill once, in inputs/project_input.md)
- Business name, type, location, details
- Google Maps / Business URL (optional but strongly recommended)
- Design reference URLs (structure, fonts, copy feel, sections to mirror)
- Image reference URLs (style to imitate when generating)
- Images to generate (exact requests, one per line)
- Hard requirements (must-include sections, must-avoid elements)

## Phase Sequence

| # | Label | Owner | Script / Action | Output |
|---|-------|-------|-----------------|--------|
| 0 | Init | Supervisor | `supervisor.py init <name>` | Clean workspace; previous project archived |
| 1 | Business Discovery | Claude Code | `discover_business.py` | `.tmp/business_manifest.json` |
| 2 | Asset Collection | Claude Code | `collect_assets.py collect` | `.tmp/existing_site_content.md`, `.tmp/google_profile.md`, `assets/images/`, `.tmp/images_manifest.json` |
| 3 | Reference Extraction | Claude Code | `fetch_reference_site.py` | `.tmp/reference_{domain}.md` (+ `.png` if visual backtrack) |
| 4 | Section Reconciliation | Claude Code | `collect_assets.py reconcile` | `.tmp/section_fill_report.md` |
| — | Validate + Handoff #1 | Supervisor | `supervisor.py handoff gemini-brief` | `.tmp/supervisor_status.md`; pipeline pauses |
| 5 | Design Brief + Images | **Gemini** | Read status file; write `.tmp/design_brief.md`; generate images | `.tmp/design_brief.md`, `assets/images/generated_*.png` |
| — | Validate Brief | Supervisor | `supervisor.py run` (on resume) | Validates brief fields; advances state |
| 6 | Code Generation | Claude Code | Read brief + references; build site | `index.html`, `css/style.css` |
| 7 | Debug | Claude Code | Playwright screenshot; fix issues | `.tmp/build_screenshot.png` |
| — | Validate + Handoff #2 | Supervisor | `supervisor.py handoff gemini-review` | `.tmp/supervisor_status.md`; pipeline pauses |
| 8 | Visual Review | **Gemini** | Review screenshot; append `## Review Notes` to `design_brief.md` | Notes in `design_brief.md` |
| — | Preview | **You** | Site at localhost:8000 (auto-launched); edit files; run `advance preview` when done | Edited site files |
| R | Revision (repeat until satisfied) | **Claude Code** | `revise "<feedback>"` → edit code → `advance code` | Updated `index.html`/`css/style.css`; `.tmp/revision_log.md`; `.tmp/r2_audit_roundN.md` |
| 10 | Deploy | Supervisor (`deploy.py`) | GitHub push + `vercel --prod` (auto after `advance preview`) | `.tmp/deployment_urls.md`; live GitHub + Vercel URLs |
| 11 | Archive | Supervisor | `supervisor.py run` (auto after DEPLOYED) | Project sealed in `archives/{name}/{timestamp}/`; deck clean |

## Handoff Files (the contract between Claude and Gemini)

| File | Written by | Read by | Contents |
|------|-----------|---------|----------|
| `.tmp/supervisor_status.md` | Supervisor | Gemini | Which files to read, required fields, flags, handoff instructions |
| `.tmp/design_brief.md` | Gemini | Claude Code | section_order, palette, fonts, copy_by_section, image_assignments, visual_direction |
| `.tmp/section_fill_report.md` | Claude Code | Gemini | Which sections have real data (FILLED) vs EMPTY |
| `.tmp/images_manifest.json` | Claude Code | Both | All collected + generated images: path, source, suggested_use |
| `.tmp/r1_quality_audit.md` | Claude Code | Supervisor | Self-audit of Round 1 quality — must have zero [FAIL] lines |
| `.tmp/revision_log.md` | Claude Code (via `revise`) | Claude Code | Feedback rounds + changes made audit trail |
| `.tmp/r2_audit_roundN.md` | Claude Code | Supervisor | Per-round revision audit (R1 carry-forward + scope compliance) |

## Acceptance Criteria (per phase)

- **Post-Code (R1):** `r1_quality_audit.md` exists with zero [FAIL] lines; all 6 mechanical checks pass; both screenshots > 20KB
- **Post-Revise:** same as Post-Code; additionally: revision scope compliant (only named elements changed); `r2_audit_roundN.md` exists
- **Post-1:** `business_manifest.json` exists with ≥ 1 source
- **Post-2:** `images_manifest.json` exists; at least some content file written
- **Post-3:** At least one `reference_*.md` exists (or `.png` if visual-backtrack)
- **Post-4:** `section_fill_report.md` exists with a row per section
- **Post-5:** `design_brief.md` contains all 6 required fields
- **Post-6:** `index.html` ≥ 500 chars; `css/style.css` ≥ 200 chars
- **Post-10:** `.tmp/deployment_urls.md` exists; GitHub repo live; Vercel URL accessible
- **Post-11:** `archives/{name}/{timestamp}/` folder exists; `.tmp/`, `.git/`, `.vercel/`, and `assets/images/` are clean

## Hard Rules (apply at every phase)
1. **Never hallucinate.** If data doesn't exist, leave the slot empty. Never invent names, prices, quotes, images, or awards.
2. **Supervisor is the source of truth.** Never advance a phase without running `validate`. Never switch to Gemini without running `handoff`.
3. **Reference links are never dropped.** Every URL in `project_input.md` is read, honored, and extracted. If extraction fails, a screenshot fallback is taken. If the screenshot fails, the failure is logged — not silently ignored.
4. **Liquid gold is primary.** If `existing_site_content.md` exists, it is the first content source for every section — Claude and Gemini both start there.
