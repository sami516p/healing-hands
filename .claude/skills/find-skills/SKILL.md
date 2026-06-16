---
name: find-skills
description: List and search the available custom skills in the current session.
---

# Find Skills — Skill Directory

## Purpose
Quickly discover which custom Claude Code skills are available right now and
what each one does, across both the user and project scopes. Useful when you
forget a skill's exact name or want to confirm a capability exists before
reaching for it.

## When to invoke
- When you (or the user) ask "what skills do I have?" or "is there a skill for X?".
- Before starting work, to confirm the relevant skill is installed and named
  as expected.

## Steps
1. From the project root, run:
   ```
   python .claude/skills/find-skills/list.py
   ```
2. To filter, pass a case-insensitive keyword (matched against name +
   description):
   ```
   python .claude/skills/find-skills/list.py design
   ```
3. Read the grouped output and invoke the skill you need.

## How it works
- USER scope: scans `~/.claude/skills/*/SKILL.md`.
- PROJECT scope: walks up from the current directory to the nearest
  `.claude/skills/*/SKILL.md` and scans that.
- Frontmatter is parsed line-by-line (reads `name:` and `description:` between
  the `---` fences) — no yaml dependency. Files are read as utf-8.

## Output
A readable list grouped by scope, each line showing `name — description`,
optionally narrowed by the keyword filter.
