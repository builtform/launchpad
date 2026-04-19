#!/usr/bin/env python3
"""Copy .claude/skills/<name>/ → plugin/skills/<prefix><name>/ with frontmatter rewrite.

Treats each top-level directory under .claude/skills/ as a skill bundle.
Rewrites SKILL.md frontmatter `name:` field to match the new directory.
Preserves all support files inside the skill directory verbatim.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
NAME_RE = re.compile(r"^(name:\s*)([\w\-./]+)\s*$", re.MULTILINE)


def rewrite_skill_name(skill_md: Path, new_name: str) -> None:
    content = skill_md.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(content)
    if not m:
        raise ValueError(f"Missing YAML frontmatter in {skill_md}")
    fm = m.group(1)
    if NAME_RE.search(fm):
        new_fm = NAME_RE.sub(rf"\g<1>{new_name}", fm, count=1)
    else:
        new_fm = f"name: {new_name}\n{fm}"
    skill_md.write_text(f"---\n{new_fm}\n---\n{content[m.end():]}", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help=".claude/skills source root")
    ap.add_argument("--dst", required=True, help="plugin/skills destination")
    ap.add_argument("--prefix", default="lp-", help="Skill dir prefix")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    count = 0
    for skill_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        # Source already prefixed (plugin-exclusive skill authored in source
        # under its final name, e.g. lp-instructions/) — keep name as-is.
        if skill_dir.name.startswith(args.prefix):
            new_name = skill_dir.name
        else:
            new_name = f"{args.prefix}{skill_dir.name}"
        target = dst / new_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill_dir, target)
        skill_md = target / "SKILL.md"
        if not skill_md.exists():
            print(f"ERROR: {skill_dir} has no SKILL.md", file=sys.stderr)
            return 1
        rewrite_skill_name(skill_md, new_name)
        count += 1

    print(f"  skills: {count} bundles copied to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
