#!/usr/bin/env python3
"""Frontmatter integrity check — every command, agent, and skill frontmatter
`name:` field matches the filename (or directory, for skills).

Earlier renames missed some command frontmatter names. This test prevents
that regression from recurring.

Run:
  python3 plugins/launchpad/scripts/tests/test_frontmatter_integrity.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(\S+)", re.MULTILINE)


def get_name(path: Path) -> str | None:
    content = path.read_text(encoding="utf-8")
    m = FM_RE.match(content)
    if not m:
        return None
    nm = NAME_RE.search(m.group(1))
    return nm.group(1) if nm else None


def main() -> int:
    errors: list[str] = []
    # File lives at <repo>/plugins/launchpad/scripts/tests/<file> — 5 .parent's to repo root
    root = Path(__file__).resolve().parents[4]

    # Commands: filename stem == frontmatter name
    cmd_count = 0
    for f in sorted(root.glob("plugins/launchpad/commands/lp-*.md")):
        cmd_count += 1
        name = get_name(f)
        if name is None:
            # Commands don't strictly require a name field, but if present it must match
            continue
        if name != f.stem:
            errors.append(f"command {f}: frontmatter name={name!r} != stem {f.stem!r}")

    # Agents: filename stem == frontmatter name (required)
    agent_count = 0
    for f in sorted(root.glob("plugins/launchpad/agents/**/lp-*.md")):
        agent_count += 1
        name = get_name(f)
        if name is None:
            errors.append(f"agent {f}: missing frontmatter name field")
        elif name != f.stem:
            errors.append(f"agent {f}: frontmatter name={name!r} != stem {f.stem!r}")

    # Skills: SKILL.md name == directory name (required)
    skill_count = 0
    for d in sorted(root.glob("plugins/launchpad/skills/lp-*")):
        if not d.is_dir():
            continue
        skill_count += 1
        sm = d / "SKILL.md"
        if not sm.exists():
            errors.append(f"skill {d}: missing SKILL.md")
            continue
        name = get_name(sm)
        if name is None:
            errors.append(f"skill {sm}: missing frontmatter name field")
        elif name != d.name:
            errors.append(f"skill {sm}: frontmatter name={name!r} != dir {d.name!r}")

    if errors:
        print("FAIL: frontmatter integrity")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"PASS: frontmatter integrity ({cmd_count} commands, {agent_count} agents, {skill_count} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
