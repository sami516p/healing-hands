# How to Use the Autonomous Healing System

**Status:** ACTIVE (as of 2026-06-17)  
**Zero manual intervention required.**

---

## TL;DR

When you run `python execution/supervisor.py run`:

1. **Phase fails?** → Supervisor auto-detects the error pattern
2. **Pattern matches table H1-H11 in `supervisor_healing.md`?** → Auto-apply the fix
3. **Fix works?** → Continue (logged to `healing_log.md`)
4. **Fix doesn't work?** → Escalate with diagnostics; you can fix it once and supervisor learns

**Result:** No lost learnings. Every problem solved is logged + the system is upgraded.

---

## When Supervisor Auto-Heals (Examples)

### Example 1: Reference Page Too Sparse
**Scenario:** `fetch_reference_site.py` returns < 200 words (JavaScript-heavy website).

**Auto-heal flow:**
1. Supervisor detects: `word_count < 200` in `reference_*.md`
2. Auto-applies fix: Re-runs with `--use-playwright` flag (loads JS)
3. Passes validation? Logs to `healing_log.md`:
   ```
   ## 2026-06-17 00:41:22
   - **Problem:** Reference page too sparse (150 words)
   - **Solution:** Retried with Playwright headless browser
   - **File upgraded:** directives/reference_extraction.md
   ```
4. Continues to next phase

### Example 2: Google Image URL Expired
**Scenario:** `collect_assets.py` tries to download an image, gets 403 (forbidden).

**Auto-heal flow:**
1. Supervisor detects: HTTP 403 or 0-byte file
2. Auto-applies fix: Skips failed image; appends `=s800` to remaining URLs (Google Photos alternative size)
3. Re-runs collection
4. Passes? Logs healing + updates `directives/content_sourcing.md` with `=s800` fallback rule

### Example 3: Screenshot Blank After Phase 7
**Scenario:** Playwright screenshot comes back blank (< 20KB).

**Auto-heal flow:**
1. Supervisor detects: `build_screenshot_desktop.png` is only 5KB
2. Auto-applies fix: Retry with `--wait-for-navigation=networkidle + 5s extra wait`
3. Non-blank? Logs healing + updates `directives/quality_standard_r1.md` with wait strategy
4. Still blank? Escalates to you with "Playwright is not loading the page; check browser path or flags"

---

## What You Do When Auto-Heal Is NOT Possible

**Scenario:** A novel error not in the H1-H11 table.

Example error:
```
ERROR: API key invalid for image generation service
```

**Flow:**
1. Supervisor detects: Error doesn't match any known pattern
2. Does NOT auto-heal (safety: no guessing on novel problems)
3. Escalates to you with:
   - Full error + stack trace
   - Diagnostic suggestions
   - Request: "Fix this, then re-run `python execution/supervisor.py run`. I'll auto-log it."

**You then:**
1. Read the error
2. Fix it (e.g., update `.env` with correct API key, or adjust the source URL)
3. Re-run: `python execution/supervisor.py run`
4. Supervisor auto-logs: `C.log_healing("API key invalid", "Updated .env with correct key", ".env")`
5. System is now stronger (next time, no escalation)

---

## Revision Loop: Auto-Captured

**Scenario:** Gemini's review notes appear in `design_brief.md`.

**Auto-flow:**
1. Supervisor detects: "## Review Notes" section in brief
2. Auto-creates `revision_log.md` (if new):
   ```
   # Revision Log — healing-hands
   
   ## Round 1 — 2026-06-17 01:15:33
   **Gemini Review Notes:**
   - Hero section heading should be larger
   - Gallery images should have rounded corners
   
   ### Changes Made
   (Claude fills this in after editing)
   ```
3. Advances to REVISING state
4. You make changes
5. You call `supervisor.py advance code`
6. Supervisor auto-captures audit results + logs: `"Revision Round 1 completed"`
7. Revision loop is now formally documented (not ad-hoc)

---

## Healing Log: Your Audit Trail

Every healing is logged to `.tmp/healing_log.md`. This file grows as the system learns.

**Example contents after multiple projects:**

```markdown
# Healing Log

Every novel problem the supervisor solved, and the file it upgraded so it won't recur.

## 2026-06-14 22:15:30
- **Problem:** Logo extraction aspect ratio wrong
- **Solution:** Tightened --box param to exclude adjacent text
- **File upgraded:** directives/logo_wordmark_extraction.md

## 2026-06-15 10:22:15
- **Problem:** Reference page too sparse
- **Solution:** Retried with Playwright headless browser
- **File upgraded:** directives/reference_extraction.md

## 2026-06-16 14:45:00
- **Problem:** Hallucinated service descriptions in build
- **Solution:** Replaced with EMPTY markers
- **File upgraded:** directives/quality_standard_r1.md
```

**Use this file to:**
- See what problems you've solved
- Understand the system's history
- Share learnings across projects (same problem won't happen twice)

---

## System Self-Check

Verify the healing system is active:

```bash
python execution/supervisor.py self-check
```

Output:
```
[2026-06-17 00:40:19] INFO  | Self-check PASS: system healthy
  [OK] All required directives present
  [OK] State machine valid
  [OK] Healing system ready
```

If any [WARN] appears, the system will tell you which directive is missing or which mechanism is broken.

---

## Key Files (Don't Edit These, Supervisor Does)

| File | Purpose | Auto-Updated? |
|------|---------|---------------|
| `.tmp/healing_log.md` | Audit trail of all problems + solutions | YES (via `C.log_healing()`) |
| `.tmp/revision_log.md` | Formal feedback → changes → audit cycle | YES (parsed from Gemini review notes) |
| `directives/supervisor_healing.md` | Healing table (H1-H11) + detection logic | YES (new patterns added here) |
| `directives/quality_standard_r1.md` | Quality checks + learnings | YES (updated when relevant) |
| `directives/revision_loop.md` | Revision protocol + regression detection | YES (updated when new patterns emerge) |

**You don't edit these manually.** Supervisor upgrades them based on learnings.

---

## Commands You'll Use

| Command | When | What It Does |
|---------|------|-------------|
| `python execution/supervisor.py run` | Always, to drive pipeline | Auto-heals failures; continues on success |
| `python execution/supervisor.py status` | Anytime | Show current state + next action |
| `python execution/supervisor.py self-check` | Periodically | Verify healing system is healthy |
| `python execution/supervisor.py revise "<feedback>"` | During preview | Start a revision round (auto-captured) |
| `python execution/supervisor.py advance code/debug/preview` | After manual phases (6, 7, or preview) | Move forward; supervisor auto-audits + logs |
| Manual fix + `supervisor.py run` | Novel errors only | You fix, supervisor auto-logs the heal |

---

## Golden Rule

**Every problem solved is logged. No learnings are wasted.**

When you fix something:
1. Supervisor auto-logs it to `healing_log.md`
2. The affected directive is marked "upgraded"
3. Next time that error appears, supervisor auto-fixes it
4. No manual `supervisor.py heal` command needed

If the same error happens in 6 months on a different project, the system will already know how to fix it.

