#!/usr/bin/env python3
"""Flatten .claude/agents/**/*.md into plugin/agents/<prefix><name>.md.

Applies prefix to filename and rewrites the frontmatter `name:` field.
Fails on basename collisions across subdirectories.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
NAME_RE = re.compile(r"^(name:\s*)([\w\-./]+)\s*$", re.MULTILINE)


def rewrite_frontmatter(content: str, new_name: str) -> str:
    m = FRONTMATTER_RE.match(content)
    if not m:
        raise ValueError("Missing YAML frontmatter")
    fm = m.group(1)
    if NAME_RE.search(fm):
        new_fm = NAME_RE.sub(rf"\g<1>{new_name}", fm, count=1)
    else:
        new_fm = f"name: {new_name}\n{fm}"
    return f"---\n{new_fm}\n---\n{content[m.end():]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help=".claude/agents source root")
    ap.add_argument("--dst", required=True, help="plugin/agents destination")
    ap.add_argument("--prefix", default="lp-", help="Filename prefix")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    seen: dict[str, Path] = {}
    count = 0

    for agent_file in sorted(src.rglob("*.md")):
        stem = agent_file.stem
        if stem in seen:
            print(
                f"ERROR: duplicate agent basename '{stem}':\n"
                f"  {seen[stem]}\n"
                f"  {agent_file}",
                file=sys.stderr,
            )
            return 1
        seen[stem] = agent_file

        new_name = f"{args.prefix}{stem}"
        target = dst / f"{new_name}.md"
        content = agent_file.read_text(encoding="utf-8")
        rewritten = rewrite_frontmatter(content, new_name)
        target.write_text(rewritten, encoding="utf-8")
        count += 1

    print(f"  agents: {count} files copied to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
