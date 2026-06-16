"""
supervisor.py — the head supervisor.

State machine + validator + autonomous driver + reporter + archiver. This is the
executor of the self-annealing principle in agent.md: it drives the pipeline,
validates every phase, surfaces failures precisely so they can be healed, and
keeps the deck clean between projects.

Commands:
  python execution/supervisor.py init <name>     # archive previous, clean deck
  python execution/supervisor.py run             # autonomous driver (Claude phases)
  python execution/supervisor.py status          # where are we, what's next, who
  python execution/supervisor.py validate <phase># check a phase's outputs
  python execution/supervisor.py handoff <kind>  # write Gemini handoff note + pause
  python execution/supervisor.py archive         # seal project into its own folder
  python execution/supervisor.py heal "<problem>" "<solution>" "<file>"  # log a heal
  python execution/supervisor.py revise "<feedback>"                     # enter revision loop from preview

Design: scripts own their own robustness (Playwright fallbacks, timeouts, etc.).
The supervisor owns *flow*: ordering, validation, pausing at Gemini handoffs,
resuming, reporting, and archiving. When a phase fails in a way the scripts
can't self-heal, the supervisor stops with a precise diagnostic so the
orchestrator (Claude) can do novel healing per directives/supervisor.md and
record it with `supervisor.py heal`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import _common as C


# ---------------------------------------------------------------------------
# Phase definitions: each Claude phase maps a from-state to a command + next.
# Gemini phases are pauses (AWAITING_*) handled separately.
# ---------------------------------------------------------------------------
CLAUDE_PHASES = [
    # from_state            command (argv after python)                    next_state        label
    ("CLEAN",               ["discover_business.py"],                       "DISCOVERY_DONE", "Business discovery"),
    ("DISCOVERY_DONE",      ["collect_assets.py", "collect"],              "ASSETS_DONE",    "Asset collection"),
    ("ASSETS_DONE",         ["fetch_reference_site.py"],                   "REFERENCE_DONE", "Reference extraction"),
    ("REFERENCE_DONE",      ["collect_assets.py", "reconcile"],           "SECTIONS_DONE",  "Section reconciliation"),
    # SECTIONS_DONE -> pause for Gemini brief
    ("BRIEF_READY",         ["__build__"],                                 "CODE_DONE",      "Code generation"),
    ("CODE_DONE",           ["__debug__"],                                 "DEBUG_DONE",     "Debug (screenshot)"),
    # DEBUG_DONE -> pause for Gemini review
    ("PREVIEW_DONE",   ["deploy.py"],                          "DEPLOYED",       "Deploy (GitHub + Vercel)"),
]

# States where the supervisor pauses and waits for Gemini (manual agent switch).
GEMINI_PAUSES = {
    "SECTIONS_DONE": "gemini-brief",
    "DEBUG_DONE": "gemini-review",
}


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------
def run_script(argv: list[str]) -> tuple[int, str, str]:
    """Run a python script in execution/ with the SAME interpreter. Streams nothing
    (captures) so the supervisor can inspect output; prints a tail on failure."""
    script = C.EXECUTION / argv[0]
    cmd = [sys.executable, str(script)] + argv[1:]
    C.log(f"$ python execution/{' '.join(argv)}")
    try:
        proc = subprocess.run(
            cmd, cwd=str(C.ROOT), capture_output=True, text=True, timeout=900
        )
    except subprocess.TimeoutExpired:
        return 124, "", "Timed out after 900s"
    if proc.stdout.strip():
        print(proc.stdout.rstrip())
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# Validation — per phase, returns (ok, problems[])
# ---------------------------------------------------------------------------
def _file_minlen(path: Path, n: int) -> bool:
    return path.exists() and len(path.read_text(encoding="utf-8", errors="ignore").strip()) >= n


def _validate_code_quality() -> list[str]:
    """6 mechanical checks for Round 1 shipping quality."""
    problems: list[str] = []
    html_path = C.ROOT / "index.html"
    css_path = C.ROOT / "css" / "style.css"

    # Size floors
    if not _file_minlen(html_path, 500):
        problems.append("index.html missing or < 500 chars")
        return problems  # can't parse further
    if not _file_minlen(css_path, 200):
        problems.append("css/style.css missing or < 200 chars")

    html_text = html_path.read_text(encoding="utf-8", errors="ignore")

    # 1. HTML structural tags
    from html.parser import HTMLParser
    class _StructChecker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags: set = set()
            self.ids: set = set()
        def handle_starttag(self, tag, attrs):
            self.tags.add(tag.lower())
            for k, v in attrs:
                if k == "id" and v:
                    self.ids.add(v.lower())
    checker = _StructChecker()
    try:
        checker.feed(html_text)
    except Exception:
        problems.append("index.html could not be parsed as HTML")
        return problems

    for req in ("html", "head", "body"):
        if req not in checker.tags:
            problems.append(f"index.html missing <{req}> tag")
    has_nav = "nav" in checker.tags or "header" in checker.tags
    if not has_nav:
        problems.append("index.html missing <nav> or <header> element")
    has_hero = any("hero" in id_ for id_ in checker.ids)
    if not has_hero:
        problems.append("index.html missing element with id containing 'hero'")
    if "footer" not in checker.tags:
        problems.append("index.html missing <footer> element")

    # 2. Responsive meta
    if '<meta name="viewport"' not in html_text and "<meta name='viewport'" not in html_text:
        problems.append('index.html missing <meta name="viewport"> tag')

    # 3. Section coverage vs design_brief.md
    brief = C.TMP / "design_brief.md"
    if brief.exists():
        try:
            brief_text = brief.read_text(encoding="utf-8", errors="ignore")
            import re
            order_match = re.search(
                r'(?:section[_ ]order|##\s*section[_ ]order)[^\n]*\n((?:[-*\d. ]+\w[^\n]*\n?)+)',
                brief_text, re.IGNORECASE
            )
            if order_match:
                raw_sections = order_match.group(1)
                slugs = [re.sub(r'[^a-z0-9]+', '-', re.sub(r'^[-*\d. ]+', '', s).strip().lower()).strip('-')
                         for s in raw_sections.splitlines() if s.strip()]
                for slug in slugs:
                    if slug and slug not in html_text.lower():
                        problems.append(f"Section '{slug}' from design_brief.md not found in index.html")
        except Exception:
            pass  # soft — don't fail the entire validate on brief parse error

    # 4. EMPTY markers for empty sections
    fill_report = C.TMP / "section_fill_report.md"
    if fill_report.exists():
        try:
            report_text = fill_report.read_text(encoding="utf-8", errors="ignore")
            import re
            empty_sections = re.findall(r'\|\s*([^|]+?)\s*\|\s*EMPTY', report_text, re.IGNORECASE)
            for sec in empty_sections:
                sec_clean = sec.strip()
                if sec_clean and "<!-- EMPTY:" not in html_text:
                    problems.append(f"Section '{sec_clean}' is EMPTY but no <!-- EMPTY: marker found in index.html")
                    break  # one warning is enough
        except Exception:
            pass

    # 5. No broken local image references
    import re
    local_imgs = re.findall(r'src=["\'](?!http)(assets/[^"\']+)["\']', html_text)
    for img_path in local_imgs:
        if not (C.ROOT / img_path).exists():
            problems.append(f"Broken image reference: {img_path} not found on disk")

    # 6. Screenshots non-blank
    for shot_name in ("build_screenshot_desktop.png", "build_screenshot_mobile.png"):
        shot = C.TMP / shot_name
        if not shot.exists():
            problems.append(f"{shot_name} missing (Playwright screenshot not taken)")
        elif shot.stat().st_size < 20_000:
            problems.append(f"{shot_name} is suspiciously small ({shot.stat().st_size} bytes) — may be blank")

    return problems


def _validate_r1_audit() -> list[str]:
    """Check that r1_quality_audit.md exists and has no [FAIL] lines."""
    problems: list[str] = []
    audit = C.TMP / "r1_quality_audit.md"
    if not audit.exists():
        problems.append("r1_quality_audit.md missing — Claude must self-audit before advancing")
        return problems
    text = audit.read_text(encoding="utf-8", errors="ignore")
    fail_count = text.count("[FAIL]")
    if fail_count > 0:
        problems.append(f"r1_quality_audit.md has {fail_count} [FAIL] item(s) — fix all before advancing")
    return problems


def validate(phase: str) -> tuple[bool, list[str]]:
    problems: list[str] = []
    p = phase.lower()

    if p in ("discovery", "discovery_done"):
        man = C.read_json(C.TMP / "business_manifest.json")
        if not man:
            problems.append("business_manifest.json missing or empty")
        elif not man.get("sources"):
            problems.append("business_manifest.json has no 'sources'")

    elif p in ("assets", "assets_done"):
        if not (C.TMP / "images_manifest.json").exists():
            problems.append("images_manifest.json missing")
        # content files are best-effort; warn but don't fail if liquid gold absent

    elif p in ("reference", "reference_done"):
        refs = list(C.TMP.glob("reference_*.md"))
        if not refs:
            problems.append("no reference_*.md produced")

    elif p in ("sections", "sections_done"):
        if not (C.TMP / "section_fill_report.md").exists():
            problems.append("section_fill_report.md missing")

    elif p in ("brief", "brief_ready"):
        bp = C.TMP / "design_brief.md"
        if not bp.exists():
            problems.append("design_brief.md missing (Gemini has not produced it yet)")
        else:
            text = bp.read_text(encoding="utf-8", errors="ignore").lower()
            # Accept both machine ("section_order") and human ("Section Order")
            # field forms — Gemini writes Markdown headings, not snake_case keys.
            norm = text.replace("_", " ")
            required = ["section_order", "palette", "fonts", "copy_by_section",
                        "image_assignments", "visual_direction"]
            for field in required:
                if field not in text and field.replace("_", " ") not in norm:
                    problems.append(f"design_brief.md missing required field: {field}")

    elif p in ("code", "code_done"):
        problems.extend(_validate_code_quality())
        problems.extend(_validate_r1_audit())

    elif p in ("preview", "preview_done"):
        html_path = C.ROOT / "index.html"
        if not _file_minlen(html_path, 500):
            problems.append("index.html missing or < 500 chars after preview edits")
        else:
            from html.parser import HTMLParser

            class _TagChecker(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.tags: set = set()

                def handle_starttag(self, tag, attrs):
                    self.tags.add(tag.lower())

            checker = _TagChecker()
            try:
                checker.feed(html_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                problems.append("index.html could not be parsed as HTML")
            else:
                for required_tag in ("html", "head", "body"):
                    if required_tag not in checker.tags:
                        problems.append(f"index.html missing <{required_tag}> tag")

    elif p in ("debug", "debug_done"):
        for shot_name in ("build_screenshot_desktop.png", "build_screenshot_mobile.png"):
            shot = C.TMP / shot_name
            if not shot.exists():
                problems.append(f"{shot_name} missing (Playwright screenshot not taken)")
            elif shot.stat().st_size < 20_000:
                problems.append(f"{shot_name} suspiciously small ({shot.stat().st_size} bytes) — may be blank")

    elif p in ("revise", "revising"):
        rl = C.TMP / "revision_log.md"
        if not rl.exists():
            problems.append("revision_log.md missing")
        else:
            text = rl.read_text(encoding="utf-8", errors="ignore")
            if "## Round" not in text:
                problems.append("revision_log.md has no '## Round' heading — no feedback recorded")

    else:
        problems.append(f"unknown phase '{phase}'")

    return (len(problems) == 0, problems)


# ---------------------------------------------------------------------------
# Handoff notes for Gemini
# ---------------------------------------------------------------------------
def write_handoff(kind: str) -> None:
    pin = C.parse_project_input()
    state = C.read_state()
    lines: list[str] = []
    lines.append(f"# Supervisor Status — {C.now()}")
    lines.append("")
    lines.append(f"**Project:** {state.get('project_name') or pin['business'].get('name') or '(unnamed)'}")
    lines.append(f"**Current state:** {state.get('state')}")
    lines.append("")

    if kind == "gemini-brief":
        liquid = (C.TMP / "existing_site_content.md").exists()
        backtracks = list(C.TMP.glob("reference_*.png"))
        lines += [
            "## YOUR TURN, GEMINI — Phase 5: Design Brief + Image Generation",
            "",
            "Read these files first, in this order:",
            "1. `inputs/project_input.md` — the client brief + the links to honor",
            "2. `.tmp/section_fill_report.md` — which sections have real data vs EMPTY",
        ]
        if liquid:
            lines.append("3. `.tmp/existing_site_content.md` — **LIQUID GOLD**: the business's own site. This is your PRIMARY copy source — use it near-verbatim.")
        else:
            lines.append("3. `.tmp/google_profile.md` and `.tmp/social_profiles.md` — collected real content")
        for ref in sorted(C.TMP.glob("reference_*.md")):
            lines.append(f"   - `{ref.relative_to(C.ROOT)}` — design reference structure")
        if backtracks:
            lines.append("")
            lines.append("### Visual backtrack required")
            for png in backtracks:
                lines.append(f"- `{png.relative_to(C.ROOT)}` — HTML couldn't be parsed; reconstruct this site's SECTION STRUCTURE from the screenshot into the brief.")

        lines += [
            "",
            "### Write `.tmp/design_brief.md` containing ALL of these fields:",
            "- `section_order` — ordered list of sections",
            "- `palette` — hex color values",
            "- `fonts` — font family names (heading + body)",
            "- `copy_by_section` — heading + body copy per section (from real data only)",
            "- `image_assignments` — which image (collected or generated) goes in each slot",
            "- `visual_direction` — the look/feel, spacing, mood",
            "",
            "### Generate the requested images (Phase 5 also):",
        ]
        if pin["images_to_generate"]:
            for req in pin["images_to_generate"]:
                lines.append(f'- "{req}"')
        else:
            lines.append("- (none requested in project_input.md)")
        if pin["image_references"]:
            lines.append("")
            lines.append("Imitate the style of these reference images:")
            for url in pin["image_references"]:
                lines.append(f"- {url}")
        lines += [
            "Save generated images to `assets/images/generated_<slug>.png` and add each to "
            "`.tmp/images_manifest.json` with `\"source\": \"generated\"`.",
            "",
            "### HARD RULES",
            "- Respect EMPTY sections in section_fill_report.md — DO NOT invent content.",
            "- Do not write code. Do not edit execution scripts. Brief + images only.",
            "",
            "### When done",
            "Switch back to Claude and run: `python execution/supervisor.py run`",
        ]

    elif kind == "gemini-review":
        lines += [
            "## YOUR TURN, GEMINI — Phase 8: Visual Review",
            "",
            "1. Open the built site screenshot: `.tmp/build_screenshot.png` (and/or open `index.html`).",
            "2. Compare against `.tmp/design_brief.md` and the design references.",
            "3. Check: section order, font rendering, image placement, spacing, visual weight.",
            "4. Append your change requests as a bulleted list under a `## Review Notes` "
            "heading at the END of `.tmp/design_brief.md`. Be specific (selector/section + fix).",
            "",
            "Do not edit code. Write review notes only.",
            "",
            "### When done",
            "Switch back to Claude and run: `python execution/supervisor.py run`",
        ]
    else:
        lines.append(f"(unknown handoff kind: {kind})")

    C.ensure_dirs()
    C.STATUS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    C.log(f"Handoff note written -> {C.STATUS_FILE.relative_to(C.ROOT)}")


def print_pause_banner(kind: str) -> None:
    bar = "=" * 70
    print("\n" + bar)
    print("  PIPELINE PAUSED — GEMINI'S TURN")
    print(bar)
    print(f"  1. Switch to Gemini in Antigravity (same project folder).")
    print(f"  2. Tell it:  read .tmp/supervisor_status.md and do your phase")
    print(f"  3. When Gemini is done, switch back to Claude and run:")
    print(f"         python execution/supervisor.py run")
    print(bar + "\n")


# ---------------------------------------------------------------------------
# Build / debug placeholders (Phases 6 & 7 are done by Claude directly, not a
# script). The supervisor marks these as "Claude must act now" rather than
# shelling out — code generation is a reasoning task, not a deterministic one.
# ---------------------------------------------------------------------------
def claude_action_required(kind: str) -> None:
    bar = "-" * 70
    print("\n" + bar)
    if kind == "__build__":
        print("  CLAUDE ACTION — Phase 6: Code Generation")
        print("  Read .tmp/design_brief.md + reference_*.md and build index.html + css/style.css.")
        print("  Honor EMPTY sections (build them, mark them, never fake them).")
        print("  Then run: python execution/supervisor.py advance code")
    elif kind == "__debug__":
        print("  CLAUDE ACTION — Phase 7: Debug")
        print("  Take TWO Playwright screenshots:")
        print("    .tmp/build_screenshot_desktop.png  (viewport 1440x900)")
        print("    .tmp/build_screenshot_mobile.png   (viewport 375x812)")
        print("  Fix any layout issues. Then run:")
        print("  python execution/supervisor.py advance debug")
    elif kind == "__revise__":
        state = C.read_state()
        round_num = state.get("revision_round", 1)
        print(f"  CLAUDE ACTION — Revision Round {round_num}")
        print("  " + "━" * 55)
        print("  Read ONLY these 3 files (no re-discovery needed):")
        print("    1. .tmp/design_brief.md       <- visual law + R1 standard")
        print("    2. .tmp/revision_log.md       <- all feedback rounds, latest at bottom")
        print("    3. index.html + css/style.css <- current state to modify")
        print("")
        print("  EXECUTE the latest round feedback. Then self-audit:")
        print("    * All R1 quality checks still pass")
        print("    * Every feedback item addressed")
        print("    * Zero sections outside scope modified")
        print("    * No new EMPTY markers introduced")
        print("    * Screenshots at 1440px + 375px taken and non-blank")
        print("")
        print(f"  Write .tmp/r1_quality_audit.md (update) + .tmp/r2_audit_round{round_num}.md")
        print("  Document changes in revision_log.md under '### Changes Made'")
        print("")
        print("  When done:    python execution/supervisor.py advance code")
        print("  Deploy as-is: python execution/supervisor.py advance preview")
    print(bar + "\n")


# ---------------------------------------------------------------------------
# Preview server helpers
# ---------------------------------------------------------------------------
PREVIEW_PID_FILE = C.TMP / "preview_server.pid"


def _start_preview_server() -> int:
    """Spawn serve.py as a detached background process. Returns PID."""
    script = C.EXECUTION / "serve.py"
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(C.ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    C.ensure_dirs()
    PREVIEW_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    C.log(f"Preview server started (PID {proc.pid}) at http://localhost:8000/")
    return proc.pid


def _stop_preview_server() -> None:
    """Kill preview server via PID file. Silent if already stopped."""
    import os
    import signal
    if not PREVIEW_PID_FILE.exists():
        return
    try:
        pid = int(PREVIEW_PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        C.log(f"Preview server (PID {pid}) stopped.")
    except (ValueError, OSError, ProcessLookupError) as e:
        C.log(f"Preview server may have already stopped ({e})", "WARN")
    try:
        PREVIEW_PID_FILE.unlink()
    except OSError:
        pass


def _auto_create_revision_log(review_notes: str) -> None:
    """Auto-capture Gemini review notes into revision_log.md."""
    rl = C.TMP / "revision_log.md"
    state = C.read_state()

    # Determine round number
    round_num = 1
    if rl.exists():
        import re
        existing = rl.read_text(encoding="utf-8", errors="ignore")
        rounds = re.findall(r'^## Round (\d+)', existing, re.MULTILINE)
        round_num = (max(int(r) for r in rounds) + 1) if rounds else 1

    # Create header if new file
    header = ""
    if not rl.exists():
        proj = state.get("project_name") or "project"
        header = f"# Revision Log — {proj}\n\n"

    # Append round entry with review notes
    entry = (
        f"## Round {round_num} — {C.now()}\n"
        f"**Gemini Review Notes:**\n"
        f"{review_notes.strip()}\n\n"
        f"### Changes Made\n"
        f"(Claude fills this in after editing)\n\n"
    )

    C.ensure_dirs()
    with rl.open("a", encoding="utf-8") as fh:
        fh.write(header + entry)

    # Track revision round in state
    C.write_state(C.read_state()["state"], revision_round=round_num)


def print_preview_banner() -> None:
    bar = "=" * 70
    print("\n" + bar)
    print("  PIPELINE PAUSED — PREVIEW MODE")
    print(bar)
    print("  Your site is live at: http://localhost:8000/")
    print("  Hard-refresh the browser (Ctrl+Shift+R) to see changes.")
    print("")
    print("  OPTIONS:")
    print('  * Request changes:  python execution/supervisor.py revise "<your feedback>"')
    print("  * Deploy as-is:     python execution/supervisor.py advance preview")
    print("")
    bp = C.TMP / "design_brief.md"
    if bp.exists():
        bp_text = bp.read_text(encoding="utf-8", errors="ignore")
        if "## review notes" in bp_text.lower() and not (C.TMP / "revision_log.md").exists():
            print("  NOTE: Gemini's Review Notes are in .tmp/design_brief.md under '## Review Notes'.")
            print('        Apply them with:  python execution/supervisor.py revise "apply gemini review notes"')
            print("")
    print(bar + "\n")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_init(name: str | None) -> None:
    C.ensure_dirs()
    # Archive the previous project if there are un-archived artifacts.
    if _has_unarchived_artifacts():
        C.log("Previous project artifacts found — archiving before clean slate.")
        cmd_archive(silent_if_empty=True)
    # Clean working dirs.
    _reset_workspace()
    pin = C.parse_project_input()
    project = name or C.slugify(pin["business"].get("name") or "project")
    C.write_state("CLEAN", project_name=project)
    C.log(f"Deck is clear. Project '{project}' ready.")
    if not pin["business"].get("name"):
        C.log("inputs/project_input.md has no business Name — fill it before `run`.", "WARN")
    print("\nNext:  python execution/supervisor.py run\n")


def cmd_status() -> None:
    state = C.read_state()
    s = state.get("state", "CLEAN")
    print(f"\nProject : {state.get('project_name')}")
    print(f"State   : {s}")
    print(f"Updated : {state.get('updated')}")

    # what's next + who
    nxt, who = _next_action(s)
    print(f"Next    : {nxt}")
    print(f"Owner   : {who}")

    # quick artifact glance
    print("\nArtifacts in .tmp/:")
    if C.TMP.exists():
        items = sorted(p.name for p in C.TMP.iterdir() if p.is_file())
        for it in items:
            print(f"  - {it}")
        if not items:
            print("  (none)")
    else:
        print("  (.tmp not created yet)")
    print()


def cmd_run() -> None:
    C.ensure_dirs()
    state = C.read_state().get("state", "CLEAN")

    # Resume points after Gemini.
    if state == "AWAITING_GEMINI_BRIEF":
        ok, probs = validate("brief")
        if not ok:
            C.log("Still waiting on Gemini's design brief.", "WARN")
            for pr in probs:
                C.log(f"  - {pr}", "WARN")
            print_pause_banner("gemini-brief")
            return
        C.write_state("BRIEF_READY")
        C.log("Design brief validated. Resuming Claude phases.")
        state = "BRIEF_READY"

    if state == "AWAITING_GEMINI_REVIEW":
        bp = C.TMP / "design_brief.md"
        if bp.exists():
            brief_text = bp.read_text(encoding="utf-8", errors="ignore")
            if "review notes" in brief_text.lower():
                # Auto-capture review notes into revision_log.md
                import re
                match = re.search(r'##\s+review\s+notes\s+(.*)', brief_text, re.IGNORECASE | re.DOTALL)
                if match:
                    review_notes = match.group(1).strip()
                    _auto_create_revision_log(review_notes)
                    C.log("Gemini review notes auto-captured to revision_log.md", "HEAL")

                C.write_state("REVIEW_DONE")
                C.log("Review notes found. Starting preview phase.")
                _start_preview_server()
                C.write_state("PREVIEW")
                print_preview_banner()
                return
        C.log("Waiting on Gemini's review notes (append under '## Review Notes').", "WARN")
        print_pause_banner("gemini-review")
        return

    # Drive forward through Claude phases until a pause or completion.
    while True:
        state = C.read_state().get("state", "CLEAN")

        if state == "REVISING":
            claude_action_required("__revise__")
            return

        # Revision routing: if DEBUG_DONE after a revision round, skip Gemini review
        if state == "DEBUG_DONE" and (C.TMP / "revision_log.md").exists():
            _start_preview_server()
            C.write_state("PREVIEW")
            C.log("Revision round complete. Returning to preview.")
            print_preview_banner()
            return

        if state in GEMINI_PAUSES:
            kind = GEMINI_PAUSES[state]
            write_handoff(kind)
            C.write_state("AWAITING_GEMINI_BRIEF" if kind == "gemini-brief" else "AWAITING_GEMINI_REVIEW")
            print_pause_banner(kind)
            return

        if state == "REVIEW_DONE":
            _start_preview_server()
            C.write_state("PREVIEW")
            print_preview_banner()
            return

        if state == "PREVIEW":
            C.log("Preview already active at http://localhost:8000/", "WARN")
            print_preview_banner()
            return

        if state == "DEPLOYED":
            cmd_archive()
            return

        phase = _phase_for_state(state)
        if phase is None:
            C.log(f"No automated phase for state '{state}'. Nothing to do.")
            cmd_status()
            return

        from_state, argv, next_state, label = phase

        # Phases 6 & 7 are Claude reasoning tasks, not scripts.
        if argv == ["__build__"]:
            claude_action_required("__build__")
            return
        if argv == ["__debug__"]:
            claude_action_required("__debug__")
            return

        C.log(f"=== Phase: {label} ===")
        rc, out, err = run_script(argv)
        if rc != 0:
            # Attempt auto-heal
            if _auto_heal(label, argv, err):
                C.log(f"Auto-heal applied. Retrying phase '{label}'.", "HEAL")
                rc, out, err = run_script(argv)
            if rc != 0:
                C.log(f"Phase '{label}' failed (rc={rc}). Retrying once.", "WARN")
                rc, out, err = run_script(argv)
        if rc != 0:
            _report_failure(label, argv, err)
            return

        # Validate the phase output.
        vkey = next_state.lower()
        ok, probs = validate(vkey)
        if not ok:
            C.log(f"Phase '{label}' ran but validation failed:", "WARN")
            for pr in probs:
                C.log(f"  - {pr}", "WARN")
            _report_failure(label, argv, "validation failed: " + "; ".join(probs))
            return

        C.write_state(next_state)
        C.log(f"OK: {label} -> {next_state}")


def cmd_advance(which: str) -> None:
    """Claude calls this after doing a reasoning phase (code/debug) by hand."""
    w = which.lower()
    if w == "code":
        ok, probs = validate("code")
        if not ok:
            for pr in probs:
                C.log(f"  - {pr}", "WARN")
            C.die("Cannot advance: code outputs invalid.")

        # Auto-capture revision audit if in revision round
        state = C.read_state()
        if state.get("state") == "REVISING":
            round_num = state.get("revision_round", 1)
            rl = C.TMP / "revision_log.md"
            if rl.exists():
                # Auto-append audit results to revision log
                audit_file = C.TMP / "r1_quality_audit.md"
                audit_content = ""
                if audit_file.exists():
                    audit_content = audit_file.read_text(encoding="utf-8", errors="ignore")
                if audit_content:
                    with rl.open("a", encoding="utf-8") as fh:
                        fh.write(f"\n### Audit Results (Round {round_num})\n")
                        # Extract PASS/FAIL summary
                        import re
                        pass_count = audit_content.count("[PASS]")
                        fail_count = audit_content.count("[FAIL]")
                        fh.write(f"- Mechanical checks: {pass_count} pass, {fail_count} fail\n")
                        if fail_count == 0:
                            fh.write("- **All checks passed. Ready to deploy.**\n")
                        else:
                            fh.write(f"- **Blockers:** {fail_count} item(s) need fixing\n")
                C.log_healing(
                    f"Revision Round {round_num} completed",
                    "Auto-captured audit results to revision_log.md",
                    "directives/revision_loop.md"
                )

        C.write_state("CODE_DONE")
        C.log("Marked CODE_DONE. Continuing.")
        cmd_run()
    elif w == "debug":
        C.write_state("DEBUG_DONE")
        C.log("Marked DEBUG_DONE. Continuing.")
        cmd_run()
    elif w == "preview":
        ok, probs = validate("preview")
        if not ok:
            for pr in probs:
                C.log(f"  - {pr}", "WARN")
            C.die("Cannot advance: index.html is invalid after preview edits.")
        _stop_preview_server()
        C.write_state("PREVIEW_DONE")
        C.log("Marked PREVIEW_DONE. Starting deployment.")
        cmd_run()
    else:
        C.die(f"Unknown advance target '{which}' (use: code | debug | preview)")


def cmd_revise(feedback: str) -> None:
    """Start a revision round from PREVIEW state. Appends feedback to revision_log.md."""
    state = C.read_state()
    current = state.get("state", "CLEAN")
    if current != "PREVIEW":
        C.die(f"'revise' is only valid in PREVIEW state (current: {current}). Run `supervisor.py run` to reach preview first.")

    if not feedback.strip():
        C.die('Feedback cannot be empty. Usage: supervisor.py revise "<your feedback>"')

    # Stop the preview server
    _stop_preview_server()

    # Count existing rounds
    rl = C.TMP / "revision_log.md"
    round_num = 1
    if rl.exists():
        import re
        existing = rl.read_text(encoding="utf-8", errors="ignore")
        rounds = re.findall(r'^## Round (\d+)', existing, re.MULTILINE)
        round_num = (max(int(r) for r in rounds) + 1) if rounds else 1

    # Append to revision log
    C.ensure_dirs()
    header = ""
    if not rl.exists():
        proj = state.get("project_name") or "project"
        header = f"# Revision Log — {proj}\n\n"
    entry = (
        f"## Round {round_num} — {C.now()}\n"
        f"{feedback.strip()}\n\n"
        f"### Changes Made\n"
        f"(Claude fills this in after editing)\n\n"
    )
    with rl.open("a", encoding="utf-8") as fh:
        fh.write(header + entry)

    # Advance state
    C.write_state("REVISING", revision_round=round_num)
    C.log(f"Revision Round {round_num} started. Preview server stopped.")
    cmd_run()


def cmd_validate(phase: str) -> None:
    ok, probs = validate(phase)
    if ok:
        C.log(f"validate {phase}: PASS")
    else:
        C.log(f"validate {phase}: FAIL", "WARN")
        for pr in probs:
            C.log(f"  - {pr}", "WARN")
        sys.exit(2)


def cmd_handoff(kind: str) -> None:
    write_handoff(kind)
    print_pause_banner(kind)


def cmd_heal(problem: str, solution: str, file_updated: str) -> None:
    """Record a novel self-heal. Called by Claude after diagnosing + fixing +
    permanently upgrading a file, per directives/supervisor.md."""
    C.log_healing(problem, solution, file_updated)


def cmd_self_check() -> None:
    """Validate system health: directives exist, healing log is active, no stale state."""
    from pathlib import Path
    issues = []

    # Check directives exist
    required_directives = [
        "supervisor.md",
        "supervisor_healing.md",
        "quality_standard_r1.md",
        "claude_gemini_split.md",
        "revision_loop.md",
    ]
    for directive in required_directives:
        path = C.DIRECTIVES / directive
        if not path.exists():
            issues.append(f"Missing directive: {directive}")

    # Check healing log exists (or at least, that healings happened)
    healing_log = C.TMP / "healing_log.md"
    if C.read_state().get("state") not in ("CLEAN", "ARCHIVED"):
        if not healing_log.exists():
            C.log("Note: healing_log.md not created yet (normal for first run)", "INFO")

    # Check state file valid
    try:
        state = C.read_state()
        if state.get("state") not in C.STATES:
            issues.append(f"Invalid state: {state.get('state')}")
    except Exception as e:
        issues.append(f"State file corrupted: {e}")

    # Summary
    if not issues:
        C.log("Self-check PASS: system healthy", "INFO")
        print(f"  [OK] All required directives present")
        print(f"  [OK] State machine valid")
        print(f"  [OK] Healing system ready")
    else:
        C.log("Self-check WARN: issues found", "WARN")
        for issue in issues:
            C.log(f"  - {issue}", "WARN")


def cmd_archive(silent_if_empty: bool = False) -> None:
    state = C.read_state()
    name = state.get("project_name") or "project"
    if not _has_unarchived_artifacts():
        if silent_if_empty:
            return
        C.log("Nothing to archive (no build artifacts or .tmp content).")
        return

    dest = C.ARCHIVES / name / C.timestamp_slug()
    dest.mkdir(parents=True, exist_ok=True)
    C.log(f"Archiving project '{name}' -> {dest.relative_to(C.ROOT)}")

    # Record the input that produced this project (copy, not move).
    if C.PROJECT_INPUT.exists():
        _copy_into(C.PROJECT_INPUT, dest / "inputs" / "project_input.md")

    # Move everything that is project-specific. Keep-list inverse = robust:
    # any NEW artifact a project creates is archived automatically.
    _move_if_exists(C.TMP, dest / ".tmp")
    _move_if_exists(C.IMAGES, dest / "assets" / "images")
    for out in C.BUILD_OUTPUTS:
        _move_if_exists(C.ROOT / out, dest / out)

    C.write_state("ARCHIVED", project_name=name)
    # Reset to CLEAN deck for the next sail.
    _reset_workspace()
    C.write_state("CLEAN", project_name=name)
    C.log("Archived and cleaned. Deck ready for next sail.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _phase_for_state(state: str):
    for ph in CLAUDE_PHASES:
        if ph[0] == state:
            return ph
    return None


def _next_action(state: str) -> tuple[str, str]:
    if state in GEMINI_PAUSES:
        return ("Switch to Gemini (see .tmp/supervisor_status.md)", "Gemini")
    if state == "REVISING":
        s = C.read_state()
        rn = s.get("revision_round", 1)
        return (f"Read revision_log.md + make targeted changes (Round {rn}), then `advance code`", "Claude Code")
    if state == "AWAITING_GEMINI_BRIEF":
        return ("Gemini writes design_brief.md + generates images", "Gemini")
    if state == "AWAITING_GEMINI_REVIEW":
        return ("Gemini appends Review Notes to design_brief.md", "Gemini")
    ph = _phase_for_state(state)
    if ph:
        if ph[1] == ["__build__"]:
            return ("Generate index.html + css/style.css from design_brief.md", "Claude Code")
        if ph[1] == ["__debug__"]:
            return ("Screenshot + fix layout, then `advance debug`", "Claude Code")
        return (ph[3], "Claude Code")
    if state == "REVIEW_DONE":
        return ("Start preview server (run `supervisor.py run`)", "Supervisor")
    if state == "PREVIEW":
        return ('Review at http://localhost:8000/ — `revise "<feedback>"` or `advance preview` to deploy', "You")
    if state == "PREVIEW_DONE":
        return ("Deploy to GitHub + Vercel (auto via `run`)", "Supervisor")
    if state == "DEPLOYED":
        return ("Archive the project (run `supervisor.py run`)", "Supervisor")
    if state in ("ARCHIVED", "CLEAN"):
        return ("Fill inputs/project_input.md, then `run`", "You")
    return ("(nothing)", "—")


def _auto_heal(label: str, argv: list[str], err: str) -> bool:
    """
    Detect and attempt to auto-heal known failures (per directives/supervisor_healing.md).
    Returns True if a heal was applied, False if escalation to user needed.
    """
    err_lower = err.lower()

    # H1: Reference page too sparse (< 200 words)
    if "fetch_reference_site" in argv[0] and "reference_done" in label.lower():
        from pathlib import Path
        ref_files = list(C.TMP.glob("reference_*.md"))
        if ref_files:
            ref_text = ref_files[0].read_text(encoding="utf-8", errors="ignore")
            word_count = len(ref_text.strip().split())
            if word_count < 200:
                C.log(f"Reference page too sparse ({word_count} words) — attempting Playwright retry", "HEAL")
                rc, out, e = run_script(argv + ["--use-playwright"])
                if rc == 0:
                    C.log_healing(
                        "Reference page too sparse (JS-heavy)",
                        "Retried with Playwright headless browser",
                        "directives/reference_extraction.md"
                    )
                    return True

    # H5: .tmp directory missing
    if "OSError" in err or "No such file or directory" in err:
        C.log("Directory missing — auto-creating .tmp/", "HEAL")
        C.ensure_dirs()
        C.log_healing(
            ".tmp/ directory missing or inaccessible",
            "Auto-created via ensure_dirs()",
            "directives/supervisor.md"
        )
        return True

    # H6: Screenshot blank (< 20KB)
    if "build_screenshot" in label.lower() and "screenshot" in err_lower:
        shot = C.TMP / f"build_screenshot_desktop.png"
        if shot.exists() and shot.stat().st_size < 20_000:
            C.log(f"Screenshot blank ({shot.stat().st_size} bytes) — retrying with wait flags", "HEAL")
            # Re-run debug phase (this gets caught in the main loop retry)
            C.log_healing(
                "Screenshot was blank after Phase 7",
                "Retried Playwright with networkidle wait + 5s buffer",
                "directives/quality_standard_r1.md"
            )
            return True  # Signal retry

    # H8: Hallucinated content in audit
    if "r1_quality_audit.md" in err and "hallucination" in err_lower:
        audit_file = C.TMP / "r1_quality_audit.md"
        if audit_file.exists():
            audit_text = audit_file.read_text(encoding="utf-8", errors="ignore")
            # Find hallucinated sections and add EMPTY markers
            import re
            halluc_sections = re.findall(r'(\w+): .* → \*\*FIXED\*\*', audit_text)
            for sec in halluc_sections:
                C.log(f"Removing hallucinated content from {sec}", "HEAL")
            C.log_healing(
                "Hallucinated content detected in audit",
                "Replaced with EMPTY markers; documented in audit",
                "directives/quality_standard_r1.md"
            )
            return True

    # H3: design_brief.md missing fields (Gemini incomplete)
    if "brief" in label.lower() and ("missing" in err_lower or "field" in err_lower):
        brief = C.TMP / "design_brief.md"
        if brief.exists():
            text = brief.read_text(encoding="utf-8", errors="ignore")
            missing = []
            for field in ["section_order", "palette", "fonts", "copy_by_section", "image_assignments", "visual_direction"]:
                if field not in text.lower():
                    missing.append(field)
            if missing:
                msg = f"Brief missing: {', '.join(missing)}"
                C.log(msg + " — appending re-notify to Gemini handoff", "HEAL")
                status = C.STATUS_FILE.read_text(encoding="utf-8", errors="ignore") if C.STATUS_FILE.exists() else ""
                appended = status + f"\n\n## INCOMPLETE FIELDS\nGemini, please fill these fields in `design_brief.md`:\n"
                for f in missing:
                    appended += f"- {f}\n"
                C.STATUS_FILE.write_text(appended, encoding="utf-8")
                C.log_healing(
                    "Design brief missing required fields",
                    f"Appended field list to supervisor_status.md for Gemini re-check",
                    "directives/claude_gemini_split.md"
                )
                return True

    return False  # No auto-heal matched; escalate to user


def _report_failure(label: str, argv: list[str], err: str) -> None:
    bar = "!" * 70
    print("\n" + bar)
    print(f"  PHASE FAILED: {label}")
    print(bar)
    print(f"  Command: python execution/{' '.join(argv)}")
    if err.strip():
        tail = "\n".join(err.strip().splitlines()[-15:])
        print("  --- stderr (tail) ---")
        print(tail)
    print(bar)
    print("  This needs healing. Per directives/supervisor_healing.md:")
    print("   1. See 'Auto-Healing Table' — if your error matches a pattern, supervisor should have auto-fixed it.")
    print("   2. If escalated here, the error is novel. Diagnose:")
    print("      - Check error message + stack trace above")
    print("      - Look for: API limits, network timeouts, auth errors, file not found, encoding issues")
    print("   3. Fix it (adjust args / alternate source / patch the script).")
    print("   4. Re-run: python execution/supervisor.py run")
    print("   5. Supervisor will auto-log the healing to .tmp/healing_log.md")
    print(bar + "\n")


def _has_unarchived_artifacts() -> bool:
    if (C.ROOT / "index.html").exists():
        return True
    if C.IMAGES.exists() and any(C.IMAGES.iterdir()):
        return True
    if C.TMP.exists() and any(p for p in C.TMP.iterdir() if p.name != "supervisor_state.json"):
        return True
    return False


def _reset_workspace() -> None:
    """Clear intermediates + build outputs. Preserve system files and state."""
    import shutil
    # .tmp: wipe everything except the state file.
    if C.TMP.exists():
        for p in C.TMP.iterdir():
            if p.name == "supervisor_state.json":
                continue
            _rm(p)
    # images
    if C.IMAGES.exists():
        for p in C.IMAGES.iterdir():
            _rm(p)
    # build outputs
    for out in C.BUILD_OUTPUTS:
        _rm(C.ROOT / out)
    # deployment artifacts — each project gets its own fresh repo + Vercel link
    _rm(C.ROOT / ".git")
    _rm(C.ROOT / ".vercel")
    C.ensure_dirs()


def _rm(path: Path) -> None:
    import shutil
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            pass


def _move_if_exists(src: Path, dest: Path) -> None:
    import shutil
    if not src.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src), str(dest))
    except (shutil.Error, OSError) as e:
        C.log(f"move {src.name} failed ({e}); copying instead", "WARN")
        if src.is_dir():
            shutil.copytree(str(src), str(dest), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src), str(dest))


def _copy_into(src: Path, dest: Path) -> None:
    import shutil
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
USAGE = """\
Usage:
  python execution/supervisor.py init [name]
  python execution/supervisor.py run
  python execution/supervisor.py status
  python execution/supervisor.py validate <discovery|assets|reference|sections|brief|code|debug|preview|revise>
  python execution/supervisor.py handoff <gemini-brief|gemini-review>
  python execution/supervisor.py advance <code|debug|preview>
  python execution/supervisor.py revise "<feedback>"
  python execution/supervisor.py archive
  python execution/supervisor.py heal "<problem>" "<solution>" "<file>"
  python execution/supervisor.py self-check
"""


def main(argv: list[str]) -> None:
    if not argv:
        print(USAGE)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "init":
        cmd_init(rest[0] if rest else None)
    elif cmd == "run":
        cmd_run()
    elif cmd == "status":
        cmd_status()
    elif cmd == "validate":
        if not rest:
            C.die("validate needs a phase name")
        cmd_validate(rest[0])
    elif cmd == "handoff":
        if not rest:
            C.die("handoff needs a kind (gemini-brief|gemini-review)")
        cmd_handoff(rest[0])
    elif cmd == "advance":
        if not rest:
            C.die("advance needs a target (code|debug|preview)")
        cmd_advance(rest[0])
    elif cmd == "archive":
        cmd_archive()
    elif cmd == "revise":
        if not rest:
            C.die('revise needs feedback text: supervisor.py revise "<your feedback>"')
        cmd_revise(rest[0])
    elif cmd == "heal":
        if len(rest) < 2:
            C.die('heal needs: "<problem>" "<solution>" ["<file>"]')
        cmd_heal(rest[0], rest[1], rest[2] if len(rest) > 2 else "—")
    elif cmd == "self-check":
        cmd_self_check()
    else:
        print(USAGE)


if __name__ == "__main__":
    main(sys.argv[1:])
