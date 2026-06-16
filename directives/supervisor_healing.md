# Directive: Supervisor Auto-Healing Protocol

**Owner:** supervisor.py  
**Purpose:** Autonomous detection + repair of known failure patterns. Zero manual intervention.

When a phase fails, supervisor detects the error, applies a known fix, re-runs the phase, logs the healing to `healing_log.md`, and continues. Only escalates to user if the fix didn't work.

---

## Auto-Healing Table

| ID | Pattern | Detect | Auto-Heal | Log | Directive Update |
|----|---------|--------|-----------|-----|------------------|
| **H1** | Reference page fetch returns < 200 words (JS-heavy site) | `len(text.strip().split()) < 200` after `fetch_reference_site.py` | Retry with Playwright headless browser (execute `fetch_reference_site.py --use-playwright`) | "Reference page too sparse; used Playwright to load JS" | `directives/reference_extraction.md` → add to "JS-heavy fallback" section |
| **H2** | Google image URL returns 403 or 0-byte file | `response.status >= 400` or `file_size < 1000` in `collect_assets.py` | Skip that image; re-run collection; if > 2 fail, append `=s800` query param (Google Photos alternative size) to retry remaining URLs | "Google image fetch failed; retried with alt size" | `directives/content_sourcing.md` → add `=s800` fallback strategy |
| **H3** | `design_brief.md` missing required fields after Gemini handoff | `validate brief` finds empty fields in: section_order / palette / fonts / copy_by_section / image_assignments / visual_direction | Write list of missing fields to `supervisor_status.md` + append instruction to Gemini's handoff note telling which fields are incomplete | "Gemini brief incomplete; re-notified Gemini" | `directives/claude_gemini_split.md` → add field checklist reminder for Gemini |
| **H4** | Playwright `launch()` fails (headless / sandbox error) | Exception type `BrowserError` or `TimeoutError` on Playwright launch | Retry with flags: `--no-sandbox --disable-dev-shm-usage --disable-gpu` (Unix/Linux) or omit flags (Windows/Mac default). If still fails, check `google_chrome` / `chromium` in PATH | "Playwright launch failed; retried with flags" | `directives/reference_extraction.md` → add flag workaround |
| **H5** | `.tmp/` directory missing or inaccessible | `OSError` on any `.tmp/` write (permission / missing) | Call `C.ensure_dirs()` immediately; retry the write. If permission denied → escalate to user | "Created missing .tmp directory" | `directives/supervisor.md` → note auto-ensure behavior |
| **H6** | Screenshot blank or corrupted (< 20KB or parse fails) after Phase 7 | `screenshot.png` exists but `file_size < 20_000` or Playwright exception | Retry with longer wait (`playwright --wait-for-navigation=networkidle` + 5s additional wait); if still blank, retry with `--no-sandbox`. Max 2 retries before escalating | "Screenshot was blank; retried with wait + flags" | `directives/quality_standard_r1.md` → add "Debug Screenshots" section with retry strategy |
| **H7** | Revision round breaks a previously-passing section ([FAIL] in audit after changes) | `r1_quality_audit.md` contains `[FAIL]` after user edits in revision round | Revert to last-known-good version of broken section (from prior commit / `.tmp/` backup); document regression in `r2_audit_roundN.md` under "Regressions Fixed" | "Revision introduced regression; reverted to prior version" | `directives/revision_loop.md` → add regression detection + revert procedure |
| **H8** | Hallucinated content (EMPTY section filled with made-up text) found in audit | `[FAIL]` in `r1_quality_audit.md` under "Hallucination Check" | Replace section with `<!-- EMPTY: <section> — awaiting owner -->` comment; mark as hallucinated in audit; document in revision round | "Hallucinated content detected and removed" | `directives/quality_standard_r1.md` → reinforce "zero hallucination" rule |
| **H9** | Logo mark extraction produces wrong aspect ratio (> ±5% deviation from source) | Compare extracted `logo_mark.png` w/h ratio vs source image mark bbox ratio; if divergence > 5% | Re-run `extract_logo.py mark` with tighter `--box` parameters; verify visually; if needed adjust `--sat-min` or `--hue-range` to exclude glows/text | "Logo extraction aspect ratio corrected" | `directives/logo_wordmark_extraction.md` → add ratio verification step + box tightening rules |
| **H10** | Design brief palette colors don't match business branding (colors verified against `google_01.jpg` / photos) | User notes mismatch in preview review (color feedback) | Fetch the color reference image; sample correct hex values; rewrite `design_brief.md` palette section; re-run `supervisor.py run` to rebuild with correct colors | "Palette colors resampled from brand image" | `directives/quality_standard_r1.md` → add color verification checklist |
| **H11** | Section missing from `design_brief.md` section_order (spec says it should exist but brief omits it) | `validate sections` or code phase catches section in `section_fill_report.md` not in brief's section_order | Append missing section to `section_order` in brief; if empty, mark as EMPTY in copy_by_section; resume code phase | "Section added to brief section_order" | `directives/claude_gemini_split.md` → add completeness check for section_order |

---

## Logging Every Heal

Every time supervisor auto-applies a heal (lines 1-11 above), it calls:

```python
C.log_healing(
    problem="<short description>",
    solution="<how it was fixed>",
    file_updated="<file path or '—'>"
)
```

This appends to `.tmp/healing_log.md` with timestamp, problem, solution, file updated. Example:

```
## 2026-06-16 22:15:42
- **Problem:** Reference page too sparse (only 150 words)
- **Solution:** Retried with Playwright headless browser
- **File upgraded:** directives/reference_extraction.md
```

---

## Escalation Rules (When to Ask the User)

Auto-healing stops and escalates if:

1. **Problem requires paid API tokens or credits** (e.g., "need API key" / "quota exceeded")
2. **Fix would modify project_input.md or directives without clear automation path** (e.g., "source URL is dead, which one should we use?")
3. **Error is not in the auto-heal table** (novel failure — goes to user with full diagnostic)
4. **Same error fails twice in a row** (heal was attempted but didn't stick)

In escalation cases:
- Full error + stack trace logged to stdout
- Suggestions for fix sent to user
- `.tmp/supervisor_status.md` updated with "ACTION REQUIRED" section
- Phase halts pending user guidance

---

## System Upgrades (Supervisor Maintains Itself)

After each successful heal:

1. **New error pattern discovered?** → Supervisor adds row to this table (H12, H13, etc.)
2. **Directive outdated?** → Supervisor patches it in-place with the new learning
3. **New edge case?** → Supervisor appends to relevant directive's edge-case section

Example: if Playwright `--no-sandbox` fix works, supervisor updates `directives/reference_extraction.md` to include:

```markdown
### Edge Case: Playwright Headless Failures (Jun 16)
If Playwright launch fails with `BrowserError`, retry with flags:
  --no-sandbox --disable-dev-shm-usage --disable-gpu
Windows/Mac: omit flags (default sandbox works fine).
```

---

## Revision Loop Auto-Capture

When supervisor detects Gemini review notes appended to `design_brief.md` (after AWAITING_GEMINI_REVIEW state):

1. **Check if `revision_log.md` exists**
   - If no: create with `# Revision Log — <project>`
   - If yes: append new round

2. **Parse review notes from brief** (content after `## Review Notes` heading)

3. **Write Round 1 entry:**
   ```
   ## Round 1 — <timestamp>
   Feedback from Gemini review:
   <copy review notes from brief>

   ### Changes Made
   (Claude fills in after editing)
   ```

4. **Advance state to REVISING** (not PREVIEW yet)

5. **Notify user:** "Gemini review notes detected. Starting Revision Round 1. Read `revision_log.md` for feedback."

This ensures feedback → changes → audit are formally tracked, not ad-hoc.

---

## Audit Auto-Capture

After Claude calls `advance code` (Phase 6 → Phase 7), supervisor auto-checks:
- Does `r1_quality_audit.md` exist? ✓
- Does it contain any `[FAIL]` lines? If yes → **block advance**, report failures
- If all PASS → allow advance to Phase 7 (debug)

After Claude calls `advance debug` (Phase 7 → Phase 8/Gemini), supervisor auto-checks:
- Do both screenshots exist? ✓
- Are both > 20KB? ✓
- If not → **block advance**, ask Claude to re-screenshot

Same for revision rounds: before each round, auto-audit; after each round, create `r2_audit_round<N>.md`.

---

## Daily Self-Check

Supervisor runs a weekly/daily check (if invoked) to ensure:
- All directives are syntactically valid Markdown
- No broken file references in directives
- `healing_log.md` is growing (learnings are being captured)
- All recent phases have corresponding directives

Command: `supervisor.py self-check` (optional, runs on startup if enabled).
