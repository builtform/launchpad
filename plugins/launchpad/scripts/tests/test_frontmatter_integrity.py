#!/usr/bin/env python3
"""Frontmatter integrity check — every command, agent, and skill frontmatter
`name:` field matches the filename (or directory, for skills).

Earlier renames missed some command frontmatter names. This test prevents
that regression from recurring.

v2.1.3 addition: every skill SKILL.md frontmatter MUST be parseable by
`yaml.safe_load`. Codex P1 on PR #66 commit 6b97e9d caught
`lp-frontend-design/SKILL.md` failing YAML parse because the unquoted
`description:` value contained `Triggers on:` mid-string — YAML
interprets the second colon as a nested mapping. The regex-only check
below missed this because the regex doesn't enforce YAML validity. A
non-parseable frontmatter means downstream tooling (including Claude
Code's `user-invocable` field handling) silently fails to read the
intended metadata.

Run:
  python3 plugins/launchpad/scripts/tests/test_frontmatter_integrity.py
"""
from __future__ import annotations

import re
import importlib.util
import sys
from pathlib import Path

import yaml

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(\S+)", re.MULTILINE)


def run_canonical_corpus_integrity(root: Path) -> tuple[int, int, int]:
    """Run the one additive metadata/body integrity authority."""
    module_path = root / "plugins" / "launchpad" / "scripts" / "plugin-codex-corpus.py"
    spec = importlib.util.spec_from_file_location(
        "plugin_codex_corpus_for_frontmatter_integrity", module_path
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load plugin-codex-corpus.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    audit = module.audit_corpus(root / "plugins" / "launchpad")
    return (
        sum(entry.kind == "command" for entry in audit.entries),
        sum(entry.kind == "agent" for entry in audit.entries),
        sum(entry.kind == "skill" for entry in audit.entries),
    )


def get_name(path: Path) -> str | None:
    content = path.read_text(encoding="utf-8")
    m = FM_RE.match(content)
    if not m:
        return None
    nm = NAME_RE.search(m.group(1))
    return nm.group(1) if nm else None


def parse_frontmatter_yaml(path: Path) -> tuple[dict | None, str | None]:
    """Parse `path`'s frontmatter via yaml.safe_load. Returns (data, None)
    on success or (None, error_message) on failure."""
    content = path.read_text(encoding="utf-8")
    m = FM_RE.match(content)
    if not m:
        return None, "no frontmatter delimiters"
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return None, f"YAML parse error: {type(e).__name__}: {e}"
    if not isinstance(data, dict):
        return None, f"frontmatter is not a mapping (got {type(data).__name__})"
    return data, None


def main() -> int:
    errors: list[str] = []
    # File lives at <repo>/plugins/launchpad/scripts/tests/<file> — 5 .parent's to repo root
    root = Path(__file__).resolve().parents[4]

    # Commands: filename stem == frontmatter name
    cmd_count = 0
    for f in sorted(root.glob("plugins/launchpad/commands/lp-*.md")):
        if not f.read_bytes().startswith(b"---\n"):
            continue
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

    # Skills: SKILL.md name == directory name (required) + frontmatter must
    # be yaml.safe_load-parseable (v2.1.3 addition; closes Codex P1 on
    # PR #66 commit 6b97e9d). The YAML check catches unquoted descriptions
    # with mid-string colons that would silently break downstream metadata
    # readers (e.g., Claude Code's `user-invocable` field handling).
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
        # NEW: yaml.safe_load parseability check
        data, parse_err = parse_frontmatter_yaml(sm)
        if parse_err is not None:
            errors.append(f"skill {sm}: frontmatter not YAML-parseable: {parse_err}")
        elif data is not None and "name" not in data:
            # Regex above already catches missing name, but record-via-YAML
            # too so the failure mode is obvious if regex passes but yaml.safe_load
            # returns a different shape (defensive).
            errors.append(f"skill {sm}: yaml.safe_load returned mapping without `name` key")

    if errors:
        print("FAIL: frontmatter integrity")
        for e in errors:
            print(f"  - {e}")
        return 1

    try:
        corpus_counts = run_canonical_corpus_integrity(root)
    except Exception as exc:
        code = getattr(exc, "code", "INTEGRITY_MISMATCH")
        print(f"FAIL: canonical corpus integrity [{code}]: {exc}")
        return 1

    if corpus_counts != (cmd_count, agent_count, skill_count):
        print(
            "FAIL: canonical corpus count mismatch "
            f"(frontmatter={cmd_count, agent_count, skill_count}, corpus={corpus_counts})"
        )
        return 1

    print(f"PASS: frontmatter integrity ({cmd_count} commands, {agent_count} agents, {skill_count} skills)")
    return 0


def test_frontmatter_integrity() -> None:
    """Pytest wrapper so the test runs in `pytest` invocations (full suite,
    lefthook pre-commit, CI). Without this wrapper, pytest collects the file
    by name-pattern but finds no `def test_*` functions and silently runs
    zero tests — defeating the YAML-parseability gate that this file
    provides. Closes the second half of the Codex P1 recommendation on
    PR #66 commit 6b97e9d."""
    assert main() == 0, "frontmatter integrity check failed; see stdout"


if __name__ == "__main__":
    sys.exit(main())
