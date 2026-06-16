#!/usr/bin/env python3
"""List and search available custom Claude Code skills.

Usage:
    python list.py [keyword]

Enumerates skills from the USER scope (~/.claude/skills/*/SKILL.md) and the
PROJECT scope (nearest .claude/skills/*/SKILL.md walking up from cwd). Prints
name + description grouped by scope. Optional keyword does a case-insensitive
substring filter on name + description. Standard library only — frontmatter is
parsed line-by-line, no yaml dependency.
"""

import sys
from pathlib import Path


def parse_frontmatter(skill_md):
    """Read name/description from the leading --- fenced block.

    Line-based parse: find the opening '---', read 'name:' and 'description:'
    until the closing '---'. Returns (name, description); falls back to the
    folder name if 'name:' is absent.
    """
    name = skill_md.parent.name
    description = ""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return name, description

    lines = text.splitlines()
    in_fence = False
    seen_open = False
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            if not seen_open:
                seen_open = True
                in_fence = True
                continue
            else:
                break  # closing fence
        if not in_fence:
            # No frontmatter fence at all; stop scanning.
            if not seen_open:
                break
            continue
        lower = stripped.lower()
        if lower.startswith("name:"):
            val = stripped.split(":", 1)[1].strip()
            if val:
                name = val
        elif lower.startswith("description:"):
            description = stripped.split(":", 1)[1].strip()
    return name, description


def find_user_scope():
    """~/.claude/skills/*/SKILL.md"""
    base = Path.home() / ".claude" / "skills"
    return collect_skills(base)


def find_project_scope():
    """Nearest .claude/skills walking up from cwd."""
    cur = Path.cwd().resolve()
    candidates = [cur] + list(cur.parents)
    for d in candidates:
        base = d / ".claude" / "skills"
        if base.is_dir():
            return base, collect_skills(base)
    return None, []


def collect_skills(base):
    """Return sorted list of (name, description, path) under base."""
    out = []
    if not base or not base.is_dir():
        return out
    for skill_md in sorted(base.glob("*/SKILL.md")):
        name, desc = parse_frontmatter(skill_md)
        out.append((name, desc, skill_md))
    return out


def matches(keyword, name, desc):
    if not keyword:
        return True
    k = keyword.lower()
    return k in name.lower() or k in desc.lower()


def print_group(title, base, skills, keyword):
    print("== {} ==".format(title))
    if base is not None:
        print("({})".format(base))
    filtered = [s for s in skills if matches(keyword, s[0], s[1])]
    if not filtered:
        print("  (none)" if not skills else "  (no matches for '{}')".format(keyword))
    for name, desc, _path in filtered:
        if desc:
            print("  {} — {}".format(name, desc))
        else:
            print("  {}".format(name))
    print("")


def main():
    keyword = sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else None

    if keyword:
        print("Filtering skills by: '{}'\n".format(keyword))

    user_base = Path.home() / ".claude" / "skills"
    user_skills = find_user_scope()
    print_group("USER skills", user_base, user_skills, keyword)

    proj_base, proj_skills = find_project_scope()
    print_group("PROJECT skills", proj_base, proj_skills, keyword)


if __name__ == "__main__":
    main()
