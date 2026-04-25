#!/usr/bin/env python3
"""Regression test: every script reference in a plugin command/skill must be
plugin-root-relative, not repo-root-relative.

When the plugin is installed via `/plugin install`, Claude Code clones only
the plugin's source path (./plugins/launchpad) to ~/.claude/plugins/cache/...
Anything referenced via bare `scripts/plugin-*.py` would be missing.

The canonical pattern (dair-cc-plugins, Anthropic examples) is to use
`${CLAUDE_PLUGIN_ROOT}/scripts/...` which resolves to the plugin's install
cache at runtime.

This test walks every .md in plugins/launchpad/{commands,skills,agents}/
and fails if it finds a bare `scripts/plugin-*` or `scripts/plugin_stack_adapters`
reference without a preceding `${CLAUDE_PLUGIN_ROOT}`.

Run:
  python3 plugins/launchpad/scripts/tests/test_plugin_install_paths.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent.parent

# Patterns that would break after install if not prefixed with ${CLAUDE_PLUGIN_ROOT}
BARE_SCRIPT_RE = re.compile(
    r"(?<![\w\${/])scripts/(plugin-[\w\-]+\.(py|sh)|plugin_stack_adapters|plugin-default-generators)"
)


def scan_file(path: Path) -> list[str]:
    """Return a list of violations found in this file."""
    violations: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        # Skip lines that already use CLAUDE_PLUGIN_ROOT
        if "CLAUDE_PLUGIN_ROOT" in line:
            continue
        m = BARE_SCRIPT_RE.search(line)
        if m:
            violations.append(f"{path}:{lineno}: bare reference '{m.group(0)}' (use ${{CLAUDE_PLUGIN_ROOT}}/{m.group(0)})")
    return violations


def main() -> int:
    if not PLUGIN_DIR.is_dir():
        print(f"FAIL: plugin dir not found at {PLUGIN_DIR}")
        return 1

    all_violations: list[str] = []
    for sub in ("commands", "skills", "agents"):
        for md in (PLUGIN_DIR / sub).rglob("*.md"):
            all_violations.extend(scan_file(md))

    if all_violations:
        print(f"FAIL: {len(all_violations)} bare script reference(s) found:")
        for v in all_violations[:20]:
            print(f"  {v}")
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        print("")
        print("Fix: replace 'scripts/plugin-*' with '${CLAUDE_PLUGIN_ROOT}/scripts/plugin-*'")
        return 1

    total_files = sum(1 for _ in PLUGIN_DIR.rglob("*.md"))
    print(f"PASS: plugin install paths ({total_files} markdown files scanned, 0 bare references)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
