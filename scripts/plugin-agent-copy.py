#!/usr/bin/env python3
"""Flatten .claude/agents/**/*.md into plugin/agents/<prefix><name>.md.

Applies prefix to filename, rewrites the frontmatter `name:` field, AND
applies command/agent/path rewrites to body prose (e.g. /review →
/lp-review, `.claude/commands/commit.md` → `${CLAUDE_PLUGIN_ROOT}/commands/
lp-commit.md`). Fails on basename collisions across subdirectories.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
NAME_RE = re.compile(r"^(name:\s*)([\w\-./]+)\s*$", re.MULTILINE)


def load_rewrite_lib(script_dir: Path):
    """Load plugin-command-rewrites.py as a module (hyphenated filename)."""
    rewrites_path = script_dir / "plugin-command-rewrites.py"
    spec = importlib.util.spec_from_file_location("plugin_command_rewrites", rewrites_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {rewrites_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    ap.add_argument("--commands-src", required=True,
                    help=".claude/commands source root (for rewrite-rule generation)")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    # Load shared rewrite helpers + build rules once.
    lib = load_rewrite_lib(Path(__file__).resolve().parent)
    cmds = lib.collect_command_names(Path(args.commands_src))
    agents_for_rules = lib.collect_agent_names(src)
    rules = lib.build_rules(cmds, agents_for_rules, args.prefix)

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
        content = rewrite_frontmatter(content, new_name)
        content = lib.rewrite_content(content, rules)
        content = lib.apply_path_rewrites(content)
        target.write_text(content, encoding="utf-8")
        count += 1

    print(f"  agents: {count} files copied to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
