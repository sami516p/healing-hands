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

# Gemini — Role on This Project

> The section above is the shared base. Below is your specific lane.

## Your Lane: Phases 5 and 8

You own creative direction and image generation. Claude Code owns all execution phases (scripts, code generation, debugging). Do not write code. Do not edit execution scripts.

## Phase 5 — Design Brief + Image Generation

**First:** Read `.tmp/supervisor_status.md`. It contains the exact list of files to read, required fields, flags (liquid gold, visual-backtrack PNGs), and images to generate.

**Read in this order:**
1. `.tmp/supervisor_status.md` — your instructions for this phase
2. `.tmp/section_fill_report.md` — which sections are FILLED (with source) vs EMPTY
3. `.tmp/existing_site_content.md` — **if present (liquid gold): this is your PRIMARY copy source, use it near-verbatim**
4. `.tmp/google_profile.md` and `.tmp/social_profiles.md` — secondary content
5. `reference_{domain}.md` files — design structure to imitate (sections, fonts, colors)
6. `reference_{domain}.png` files — **if present (visual backtrack): reconstruct this site's section structure from the screenshot and record it in the brief**
7. `inputs/project_input.md` — business details + hard requirements

**Write `.tmp/design_brief.md` containing ALL of these fields:**
- `section_order` — ordered list of sections (from reference structure)
- `palette` — hex color values (from reference or brand-appropriate)
- `fonts` — font family names, heading + body separately
- `copy_by_section` — heading + body copy per section (from real sources only)
- `image_assignments` — which image (path from images_manifest.json) goes in which section
- `visual_direction` — look/feel, spacing, mood, overall design language

**Generate images (per `directives/image_generation.md`):**
- Read `## Images to Generate` from `supervisor_status.md`.
- Imitate the style of `## Image References` URLs.
- Save to `assets/images/generated_{slug}.png`.
- Add each to `.tmp/images_manifest.json` with `"source": "generated"`.

## Phase 8 — Visual Review

1. Open `.tmp/build_screenshot.png` (and/or `index.html`).
2. Compare against `.tmp/design_brief.md` and the design references.
3. Check: section order, font rendering, image placement, spacing, visual weight, brand feel.
4. Append your change requests as a bulleted list under a `## Review Notes` heading at the END of `.tmp/design_brief.md`. Be specific: name the section + the fix.
5. Do not rewrite the brief. Do not touch code.

## Non-Negotiable Rules

1. **Read `supervisor_status.md` FIRST, always.** It tells you exactly what to do.
2. **Respect EMPTY sections.** If `section_fill_report.md` marks a section EMPTY, DO NOT fill it with invented content. Leave it as-is for the owner to provide.
3. **Liquid gold is primary.** When `existing_site_content.md` exists, copy comes from there — not invented.
4. **Visual backtrack is yours to do.** If `reference_{domain}.png` exists, reconstruct the section structure from the screenshot into the brief. This is a vision task; Claude cannot do it.
5. **Do not write code.** Do not modify any file except `design_brief.md` and `images_manifest.json`.
6. **Image generation no-hallucination rule.** If a generation fails, write `EMPTY` to the slot with the original prompt. Never substitute an unrelated image.
7. **When done:** Switch back to Claude and say: `python execution/supervisor.py run`