# Healing System Troubleshooting

**For when something doesn't auto-heal as expected.**

---

## Problem: Auto-Heal Was Applied But Phase Still Fails

**Symptom:** Supervisor logs `[HEAL] Auto-heal applied. Retrying phase...` but then escalates to user anyway.

**Why:** The fix attempted was partially correct, but the underlying issue persists.

**Solution:**
1. Check `.tmp/healing_log.md` — which heal was applied?
2. Manually diagnose the error (read the full error message)
3. Determine if the auto-fix was insufficient or the problem is different
4. Apply a targeted fix:
   - Adjust execution script arguments (e.g., different `--hue-range` for logo extraction)
   - Use an alternate source (e.g., different image URL)
   - Patch the script itself (e.g., add a retry loop, change timeout)
5. Re-run: `python execution/supervisor.py run`
6. Supervisor auto-logs the second attempt

**Example:**
```
[2026-06-17 01:20:15] [HEAL] Auto-heal applied. Retrying phase...
[2026-06-17 01:20:18] WARN | Phase 'Reference extraction' failed (rc=1). Retrying once.
[2026-06-17 01:20:22] WARN | Phase 'Reference extraction' failed (rc=1).
! PHASE FAILED: Reference extraction
```

→ Read error. Auto-heal (H1: Playwright retry) didn't work.
→ Diagnose: maybe Playwright needs different flags, or the site uses a different JS framework.
→ Fix manually: update `directives/reference_extraction.md` with new flags or alternate strategy.
→ Re-run: `supervisor.py run`
→ Works this time? Supervisor logs it.

---

## Problem: Healing Log Not Growing

**Symptom:** You've run projects but `.tmp/healing_log.md` is empty or missing.

**Why:**
1. All phases have been passing (no failures = no heals)
2. Or: heals were applied but `C.log_healing()` wasn't called (bug in supervisor.py)

**Check:**
```bash
ls -lrt .tmp/healing_log.md  # Does it exist?
cat .tmp/healing_log.md      # Is it empty?
```

**If missing/empty but you solved problems:**
- Old behavior (before 2026-06-17): heals weren't logged automatically
- New behavior (after 2026-06-17): all heals are logged
- To backfill: manually run `supervisor.py heal "<old_problem>" "<old_solution>" "<file>"` for each

**If phases are passing:**
- That's good! No failures = no heals needed
- Healing log will grow on the next project that hits an error

---

## Problem: Revision Log Not Auto-Created

**Symptom:** Gemini added review notes to `design_brief.md`, but `revision_log.md` wasn't created.

**Why:**
1. Supervisor didn't detect the review notes (check format)
2. Or: supervisor.py has a bug in the regex parsing

**Check:**
1. Open `.tmp/design_brief.md`
2. Find the review notes section — it should look like:
   ```markdown
   ## Review Notes
   - Hero section needs larger heading
   - Gallery should have rounded corners
   ```
   (Case-insensitive, heading must contain "Review Notes")

**If format is wrong:**
- Manually create `.tmp/revision_log.md`:
  ```markdown
  # Revision Log — <project_name>
  
  ## Round 1 — 2026-06-17 01:15:33
  **Gemini Review Notes:**
  [paste Gemini's feedback here]
  
  ### Changes Made
  (Fill after editing)
  ```
- Re-run: `supervisor.py run`
- Supervisor will continue from REVISING state

**If format is right but supervisor still didn't parse it:**
- Bug in `_auto_create_revision_log()` regex
- Manual workaround: create the file above, then run `supervisor.py run`
- Report to Claude for supervisor.py fix

---

## Problem: Escalated Error Is Not in Healing Table (H1-H11)

**Symptom:**
```
! PHASE FAILED: <phase>
...error details...
This needs healing. Per directives/supervisor_healing.md:
   1. See 'Auto-Healing Table' — if your error matches a pattern...
   2. If escalated here, the error is novel.
```

**Why:** Your error doesn't match H1-H11. It's a new problem the system hasn't learned yet.

**What to do:**
1. **Diagnose:** Read the error carefully. Is it:
   - Network timeout? → likely a timing issue (increase timeout)
   - Missing file? → source changed (use alternate source)
   - API error? → credentials/quota (fix .env, ask Claude for guidance)
   - Parsing error? → site structure changed (adjust CSS selector)
   - Other? → ask Claude for guidance

2. **Fix:** Adjust the execution script or .env or source, then re-run `supervisor.py run`

3. **Supervisor logs it automatically** (now that it's fixed, supervisor will log to `healing_log.md`)

4. **Optional:** Update `directives/supervisor_healing.md` with a new row (H12, H13, etc.) so this error auto-heals next time
   - OR: Report to Claude, who can add it to the healing table

---

## Problem: Supervisor Crashed During Healing Attempt

**Symptom:**
```
Traceback (most recent call last):
  File "execution/supervisor.py", line X, in _auto_heal
    ...exception...
```

**Why:** Bug in supervisor.py's healing logic (edge case, unexpected error format, etc.)

**What to do:**
1. Note the line number + error
2. The phase still failed (healing attempt crashed)
3. **Manual fix needed:**
   - Fix the underlying issue (same as "Problem: Escalated Error Is Not in Healing Table")
   - Re-run: `supervisor.py run`
4. **Report to Claude** with the error trace so supervisor.py can be patched

---

## Problem: Same Error Happened Twice (Should Have Been Learned)

**Symptom:**
- Project 1: phase failed, supervisor auto-healed it, logged to `healing_log.md`
- Project 2: same phase fails with same error, supervisor escalates again (should have auto-healed!)

**Why:**
1. Error detection pattern (H1-H11) is too specific and doesn't match slightly-different error format
2. Or: supervisor.py bug (healing logic not being called for this phase)

**What to do:**
1. Check `healing_log.md` — was the error logged last time?
2. If yes, the detection pattern is too strict
3. **Adjust the detection pattern:**
   - Open `directives/supervisor_healing.md`
   - Find the relevant row (H1-H11)
   - Update the "Detect" column to match this new error format too
   - Re-run: `supervisor.py run` (should auto-heal now)
4. If no, the error wasn't logged last time → re-check last project

---

## Problem: `.tmp/` Directory Gets Corrupted

**Symptom:**
```
OSError: [Errno 2] No such file or directory: '.tmp/some_file'
```

**Why:** `.tmp/` directory was deleted mid-run or permissions are wrong

**Solution:**
- Supervisor auto-creates `.tmp/` on startup (H5 auto-heal)
- If error persists: `python -c "import os; os.makedirs('.tmp', exist_ok=True)"`
- Re-run: `supervisor.py run`

---

## Quick Decision Tree

```
Phase fails?
├─ Error matches H1-H11 in supervisor_healing.md?
│  ├─ YES → Supervisor auto-heals
│  │        ├─ Works? Continue.
│  │        └─ Still fails? See "Auto-Heal Failed But Phase Still Fails"
│  └─ NO → Novel error (escalate)
│           ├─ Diagnose (API? timeout? source? selector?)
│           ├─ Fix manually (update script / .env / source)
│           ├─ Re-run: supervisor.py run
│           └─ Supervisor auto-logs the heal
└─ Supervisor crashes?
   └─ Bug in healing logic. Report + manually fix underlying issue.
```

---

## Reporting Issues

If you suspect a supervisor.py bug:

1. Note the error trace + line number
2. What phase was running?
3. What was the underlying error (before healing attempt)?
4. Did manual fix work?

Report to Claude with these details for a patch.

