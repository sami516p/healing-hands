# Directive: Supervisor — Rules, Validation Schema, Self-Annealing Protocol

## Role
The supervisor is the head of the entire pipeline. It runs everything, validates every phase output, writes handoff notes, heals failures it has never seen, and keeps this directive (and every other file) upgraded when it learns something new. It is the executor of the self-annealing principle in `agent.md`.

## Core Commands

| Command | When to run |
|---------|-------------|
| `supervisor.py init <name>` | Before every project (archives previous, cleans deck) |
| `supervisor.py run` | After init; after each Gemini handoff; after each `advance` |
| `supervisor.py status` | Anytime you need to know where the pipeline is |
| `supervisor.py validate <phase>` | After any phase completes, before advancing |
| `supervisor.py handoff <kind>` | Before switching to Gemini (always, no exceptions) |
| `supervisor.py advance <code\|debug\|preview>` | After Claude manually does Phase 6 or 7; after user finishes preview edits |
| `supervisor.py validate preview` | During preview to check HTML is still valid |
| `supervisor.py archive` | Seals and cleans; called automatically by `run` at end |
| `supervisor.py revise "<feedback>"` | When user wants changes after seeing preview (from PREVIEW state only) |
| `supervisor.py heal "<problem>" "<solution>" "<file>"` | After solving a novel failure |

## Validation Schema (per phase)

| Phase key | Required outputs | Pass criteria |
|-----------|-----------------|---------------|
| `discovery` | `.tmp/business_manifest.json` | Exists; has `sources` key |
| `assets` | `.tmp/images_manifest.json` | Exists |
| `reference` | `.tmp/reference_*.md` | At least one file present |
| `sections` | `.tmp/section_fill_report.md` | Exists |
| `brief` | `.tmp/design_brief.md` | Exists; contains: `section_order`, `palette`, `fonts`, `copy_by_section`, `image_assignments`, `visual_direction` |
| `code` | `index.html`, `css/style.css`, `.tmp/r1_quality_audit.md` | All 6 mechanical checks pass; `r1_quality_audit.md` exists with zero [FAIL] lines |
| `debug` | `.tmp/build_screenshot_desktop.png`, `.tmp/build_screenshot_mobile.png` | Both exist; both > 20KB |
| `revise` | `.tmp/revision_log.md` | Exists; has at least one `## Round` heading |
| `preview` | `index.html` | Exists; ≥ 500 chars; contains `<html>`, `<head>`, `<body>` tags |

## Known Healing Table (fast path)
When a phase fails with one of these known patterns, apply the fix immediately without escalating.

| # | What breaks | Detect | Heal |
|---|-------------|--------|------|
| H1 | Reference fetch < 200 words (JS-heavy) | `word_count < 200` | Retry with Playwright; if still < 200 → screenshot (Mode B) |
| H2 | Google image URL expired (403 or 0-byte) | `status ≥ 400` or `file < 1KB` | Re-run Google photo collection only; append `=s800` as alternative size |
| H3 | `design_brief.md` missing required fields | `validate brief` FAIL | Write precise list of missing fields into `supervisor_status.md`; user tells Gemini to re-read and complete |
| H4 | Playwright won't launch (headless error) | Exception on `launch()` | Retry with `--no-sandbox --disable-dev-shm-usage`; if still fails, log browser path check |
| H5 | `.tmp/` directory missing | `OSError` on any `.tmp/` write | Auto-create via `ensure_dirs()` before any script runs |
| H6 | Screenshot blank (< 20KB) after Phase 7 | `build_screenshot_desktop.png` or `build_screenshot_mobile.png` size check | Re-run Playwright with 5s wait; retry with `--no-sandbox`; if still blank → H4 path |
| H7 | Revision changes broke a previously-working section | [FAIL] appears in `r1_quality_audit.md` after revision | Fix the regression; update `r1_quality_audit.md`; document regression + fix in `r2_audit_roundN.md` |

## Novel Healing Protocol (problems NOT in the table above)

When the supervisor encounters a new failure:

1. **Read** the error message and stack trace in full.
2. **Diagnose** the root cause — network, selector change, auth, encoding, missing dependency, changed API response structure, etc.
3. **Attempt a fix** autonomously:
   - Adjust script arguments or selectors.
   - Try an alternate source or alternate library.
   - Work *around* the problem (e.g. if one platform's HTML changed, try a different CSS selector path).
4. **Test the fix.** Re-run the failing phase. Confirm outputs pass `validate`.
5. **On success — permanently upgrade the system:**
   - Append a new row to the **Known Healing Table** above (columns: #, What breaks, Detect, Heal).
   - Patch the failing `execution/` script so it handles the new case automatically.
   - If a directive misled the phase, refine the directive.
   - Log the heal: `supervisor.py heal "<problem>" "<solution>" "<file_updated>"`.
   - Report to the user: *"Hit X, solved by Y, updated <file> so it won't recur."*
6. **If the fix involves paid credits or tokens**, or the problem is genuinely unsolvable:
   - Report the full diagnostic to the user.
   - Ask for guidance before proceeding.

## Self-Maintaining: System-Wide Upgrades

The supervisor is responsible for keeping ALL files in this system accurate and improving over time, not just its own directive. Examples of when to act:

| Discovery | Action |
|-----------|--------|
| New file type produced by a phase that should be archived | Append it to the **Archive Checklist** below |
| A directive's instructions led to a misunderstood step | Edit that directive to be clearer |
| An execution script's edge case was fixed | Note the fix in the corresponding directive's edge-case table |
| A new platform or source type proves useful | Add it to `directives/business_discovery.md` |

Every system-wide change is logged in `.tmp/healing_log.md` and reported to the user.

## Archive Checklist (append-only — supervisor extends this as it learns)

The following are moved to `archives/{name}/{timestamp}/` on archive:

- `.tmp/` → `archives/{name}/{timestamp}/.tmp/`
- `assets/images/` → `archives/{name}/{timestamp}/assets/images/`
- `inputs/project_input.md` → `archives/{name}/{timestamp}/inputs/project_input.md` (copied, not moved)
- `index.html` → `archives/{name}/{timestamp}/index.html`
- `css/` → `archives/{name}/{timestamp}/css/`
- `js/` → `archives/{name}/{timestamp}/js/`

**Archive folder rule (mandatory):** Each project gets its own named folder: `archives/{project_name}/{timestamp}/`. Multiple runs/versions of the same project nest as separate timestamp subfolders. This ensures any old project can be reopened without ambiguity.

**What is NOT archived (stays in place):**
- `directives/` — the instruction set, never project-specific
- `execution/` — the tooling, never project-specific
- `agent.md`, `claude.md`, `gemini.md` — system config
- `supervisor.py` and all system files

**Deleted during `_reset_workspace()` (NOT archived — regenerated fresh per project):**
- `.git/` — each project gets its own git history
- `.vercel/` — each project gets its own Vercel project link

## Reporting Style
Every phase transition is printed to stdout with a timestamp and the next action. At Gemini pause points, the banner is clear and explicit:
- Who the next actor is
- What file to read
- What command to run on return

The user should never need to guess what to do next.
