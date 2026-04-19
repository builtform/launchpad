#!/usr/bin/env python3
"""Copy .claude/commands/**.md → plugin/commands/<prefix><name>.md with cross-ref rewrites.

Auto-generates rewrite rules from source filesystem (commands + agents), so new
commands don't need manual rule additions.

Rewrites applied:
  - /commit            → /lp-commit
  - /harness:build     → /lp-harness-build   (flatten harness/ subdir)
  - security-auditor   → lp-security-auditor (bare agent name for Task tool)

Markdown-aware: only rewrites slash-command references inside prose or
slash-command-invocation lines inside code fences. Other code content
(URLs, filesystem paths) is left untouched.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FENCE_RE = re.compile(r"^(```|~~~)", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
FM_NAME_RE = re.compile(r"^(name:\s*)([^\s\n]+)\s*$", re.MULTILINE)
# Matches "/name" with word boundary that excludes dash/slash/colon so we don't
# rewrite /already-prefixed or /some/path/file.
SLASH_BOUNDARY_PRE = r"(?<![\w\-:/])"
SLASH_BOUNDARY_POST = r"(?![\w\-:])"
# Matches bare agent names (no leading slash) — need tighter word boundary
AGENT_BOUNDARY_PRE = r"(?<![\w\-/:.])"
AGENT_BOUNDARY_POST = r"(?![\w\-:])"

HARNESS_COMMANDS = {"build", "plan", "define", "kickoff"}


def collect_command_names(src: Path) -> list[str]:
    top_level = [p.stem for p in src.glob("*.md")]
    return sorted(top_level)


def collect_agent_names(agents_dir: Path) -> list[str]:
    return sorted(p.stem for p in agents_dir.rglob("*.md"))


def build_rules(cmds: list[str], agents: list[str], prefix: str) -> list[tuple[re.Pattern, str]]:
    rules: list[tuple[re.Pattern, str]] = []

    # Harness subdir flattening rules first (more specific)
    for name in HARNESS_COMMANDS:
        pat = re.compile(rf"{SLASH_BOUNDARY_PRE}/harness:{re.escape(name)}{SLASH_BOUNDARY_POST}")
        rules.append((pat, f"/{prefix}harness-{name}"))

    # Top-level commands
    for name in cmds:
        pat = re.compile(rf"{SLASH_BOUNDARY_PRE}/{re.escape(name)}{SLASH_BOUNDARY_POST}")
        rules.append((pat, f"/{prefix}{name}"))

    # Agent names (bare, not slash-prefixed — used in Task tool subagent_type, agents.yml, etc.)
    for name in agents:
        pat = re.compile(rf"{AGENT_BOUNDARY_PRE}{re.escape(name)}{AGENT_BOUNDARY_POST}")
        rules.append((pat, f"{prefix}{name}"))

    return rules


def split_by_fences(text: str) -> list[tuple[str, bool]]:
    """Return list of (span_text, in_fence) tuples."""
    parts: list[tuple[str, bool]] = []
    in_fence = False
    buf: list[str] = []
    for line in text.splitlines(keepends=True):
        if FENCE_RE.match(line):
            if buf:
                parts.append(("".join(buf), in_fence))
                buf = []
            parts.append((line, in_fence))
            in_fence = not in_fence
            continue
        buf.append(line)
    if buf:
        parts.append(("".join(buf), in_fence))
    return parts


def apply_rules(text: str, rules: list[tuple[re.Pattern, str]]) -> str:
    for pat, repl in rules:
        text = pat.sub(repl, text)
    return text


def rewrite_content(content: str, rules: list[tuple[re.Pattern, str]]) -> str:
    parts = split_by_fences(content)
    out: list[str] = []
    for span, in_fence in parts:
        if not in_fence:
            # Prose: apply all rules freely
            out.append(apply_rules(span, rules))
        else:
            # In code fence: rewrite only lines that look like slash-command invocations
            # (line begins with optional whitespace then `/`, or contains `/lp-`-prone refs)
            rewritten_lines: list[str] = []
            for line in span.splitlines(keepends=True):
                stripped = line.lstrip()
                if stripped.startswith("/"):
                    rewritten_lines.append(apply_rules(line, rules))
                else:
                    rewritten_lines.append(line)
            out.append("".join(rewritten_lines))
    return "".join(out)


def rewrite_frontmatter_name(content: str, new_name: str) -> str:
    """Rewrite the frontmatter `name:` field to match the new filename.

    Adds a `name:` line if none exists. Leaves rest of frontmatter + body intact.
    """
    m = FRONTMATTER_RE.match(content)
    if not m:
        # No frontmatter — inject one with just the name
        return f"---\nname: {new_name}\n---\n{content}"
    fm = m.group(1)
    if FM_NAME_RE.search(fm):
        new_fm = FM_NAME_RE.sub(rf"\g<1>{new_name}", fm, count=1)
    else:
        new_fm = f"name: {new_name}\n{fm}"
    return f"---\n{new_fm}\n---\n{content[m.end():]}"


def rewrite_file(src_file: Path, dst_file: Path, rules: list[tuple[re.Pattern, str]], new_name: str) -> None:
    content = src_file.read_text(encoding="utf-8")
    content = rewrite_frontmatter_name(content, new_name)
    content = rewrite_content(content, rules)
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    dst_file.write_text(content, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help=".claude/commands source root")
    ap.add_argument("--dst", required=True, help="plugin/commands destination")
    ap.add_argument("--prefix", default="lp-", help="Command prefix")
    ap.add_argument(
        "--agents-src",
        default=".claude/agents",
        help="Source agents dir (for rule generation)",
    )
    ap.add_argument(
        "--drop",
        action="append",
        default=[],
        help="Source command basenames to DROP (not copy)",
    )
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    # Collect rule inputs
    cmds = collect_command_names(src)
    agents = collect_agent_names(Path(args.agents_src))
    rules = build_rules(cmds, agents, args.prefix)

    count = 0

    # Top-level commands
    for md in sorted(src.glob("*.md")):
        if md.stem in args.drop:
            print(f"  dropped: {md.name}", file=sys.stderr)
            continue
        new_name = f"{args.prefix}{md.stem}"
        target = dst / f"{new_name}.md"
        rewrite_file(md, target, rules, new_name)
        count += 1

    # Harness subdir — flatten
    harness_dir = src / "harness"
    if harness_dir.is_dir():
        for md in sorted(harness_dir.glob("*.md")):
            new_name = f"{args.prefix}harness-{md.stem}"
            target = dst / f"{new_name}.md"
            rewrite_file(md, target, rules, new_name)
            count += 1

    print(f"  commands: {count} files rewritten to {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
