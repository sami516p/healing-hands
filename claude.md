# Agent Instructions

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work. Commented well.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. System is now stronger

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` - Python scripts (the deterministic tools)
- `directives/` - SOPs in Markdown (the instruction set)
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.

---

# Claude Code — Role on This Project

> The section above is the shared base. Below is your specific lane.

## Your Lane: Phases 0–4, 6, 7

You own all execution phases. Gemini owns Phases 5 (design brief + image generation) and 8 (visual review). Do not cross into Gemini's lane.

| Phase | Your action |
|-------|-------------|
| 0. Init | `python execution/supervisor.py init <project-name>` |
| 1. Business discovery | `python execution/discover_business.py` |
| 2. Asset collection | `python execution/collect_assets.py collect` |
| 3. Reference extraction | `python execution/fetch_reference_site.py` |
| 4. Section reconciliation | `python execution/collect_assets.py reconcile` |
| — | `python execution/supervisor.py handoff gemini-brief` → tell user to switch |
| 6. Code generation | Read `.tmp/design_brief.md` + `reference_*.md` → build `index.html` + `css/style.css` → `supervisor.py advance code` |
| 7. Debug | Playwright screenshot → `.tmp/build_screenshot.png`; fix issues → `supervisor.py advance debug` |

**Or let the supervisor drive everything:** `python execution/supervisor.py run`

## Non-Negotiable Rules

1. **Always validate before advancing.** `supervisor.py validate <phase>` — never skip.
2. **Always handoff before switching to Gemini.** `supervisor.py handoff gemini-brief` / `handoff gemini-review` — the file is the only channel.
3. **Never hallucinate. Ever.** Unfillable section → build structure, leave `<!-- EMPTY: {section} — awaiting owner -->`. Missing image → EMPTY marker. No data = empty, not invented.
4. **`design_brief.md` is the authoritative spec for code.** Follow it exactly — don't invent sections, change the palette, or reorder.
5. **Liquid gold is primary.** If `.tmp/existing_site_content.md` exists, start there for every section's copy.
6. **Check `execution/` before writing any new script.** Only create if none exists.
7. **Self-anneal when things break.** Fix → test → `supervisor.py heal` → update directive.

## Supervisor Quick Reference
```
python execution/supervisor.py init <name>
python execution/supervisor.py run
python execution/supervisor.py status
python execution/supervisor.py validate <discovery|assets|reference|sections|brief|code>
python execution/supervisor.py handoff gemini-brief
python execution/supervisor.py handoff gemini-review
python execution/supervisor.py advance code
python execution/supervisor.py advance debug
python execution/supervisor.py heal "<problem>" "<solution>" "<file>"
```