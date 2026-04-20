#!/usr/bin/env python3
"""Copy .claude/skills/<name>/ → plugin/skills/<prefix><name>/ with rewrites.

Treats each top-level directory under .claude/skills/ as a skill bundle.
Applies the same command + agent + path rewrites that plugin-command-rewrites.py
applies to command files, so SKILL.md prose pointing at /commit, agent names,
or .claude/ source paths gets transformed to the plugin equivalents.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
NAME_RE = re.compile(r"^(name:\s*)([\w\-./]+)\s*$", re.MULTILINE)


def load_rewrite_lib(script_dir: Path):
    """Load plugin-command-rewrites.py as a module (hyphenated filename).

    We use importlib rather than a plain import so the rewrite helpers can
    live in a hyphenated entry-point script consistent with other plugin-*
    shell scripts. The alternative — extracting to an underscore-named lib
    module — is a larger refactor we can defer.
    """
    rewrites_path = script_dir / "plugin-command-rewrites.py"
    spec = importlib.util.spec_from_file_location("plugin_command_rewrites", rewrites_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {rewrites_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rewrite_skill_frontmatter_name(skill_md: Path, new_name: str) -> str:
    content = skill_md.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(content)
    if not m:
        raise ValueError(f"Missing YAML frontmatter in {skill_md}")
    fm = m.group(1)
    if NAME_RE.search(fm):
        new_fm = NAME_RE.sub(rf"\g<1>{new_name}", fm, count=1)
    else:
        new_fm = f"name: {new_name}\n{fm}"
    return f"---\n{new_fm}\n---\n{content[m.end():]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help=".claude/skills source root")
    ap.add_argument("--dst", required=True, help="plugin/skills destination")
    ap.add_argument("--prefix", default="lp-", help="Skill dir prefix")
    ap.add_argument("--commands-src", required=True,
                    help=".claude/commands source root (for rewrite-rule generation)")
    ap.add_argument("--agents-src", required=True,
                    help=".claude/agents source root (for rewrite-rule generation)")
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    # Load shared rewrite helpers + build rules once (cmds/agents don't change
    # during a single build).
    lib = load_rewrite_lib(Path(__file__).resolve().parent)
    cmds = lib.collect_command_names(Path(args.commands_src))
    agents = lib.collect_agent_names(Path(args.agents_src))
    rules = lib.build_rules(cmds, agents, args.prefix)

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

        # SKILL.md: frontmatter (authoritative name) + body rewrites.
        content = rewrite_skill_frontmatter_name(skill_md, new_name)
        content = lib.rewrite_content(content, rules)
        content = lib.apply_path_rewrites(content)
        skill_md.write_text(content, encoding="utf-8")

        # Reference files (references/, scripts/, etc. within the skill
        # bundle) also contain /command refs that need rewriting — e.g.
        # `/port-skill`, `/create-skill`. Walk all .md files under the
        # skill directory except SKILL.md itself.
        for ref in sorted(target.rglob("*.md")):
            if ref.resolve() == skill_md.resolve():
                continue
            ref_content = ref.read_text(encoding="utf-8")
            ref_content = lib.rewrite_content(ref_content, rules)
            ref_content = lib.apply_path_rewrites(ref_content)
            ref.write_text(ref_content, encoding="utf-8")

        count += 1

    print(f"  skills: {count} bundles copied to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
