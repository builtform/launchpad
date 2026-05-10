#!/usr/bin/env python3
"""Validate all GitHub Actions `uses:` refs are 40-char hex SHA pins.

Replaces the inline grep-based lefthook check that only caught `@vN`
tags. This script catches ALL non-SHA refs: `@main`, `@master`,
`@release`, `@v2.0.2`, semver tags, branch names, etc.

Exit 0 if all refs are valid SHA pins (or no workflow files found).
Exit 1 if any violation is found, printing each to stderr.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_USES_RE = re.compile(r"uses:\s*([^#\s]+)")

SCAN_DIRS = [
    ".github/workflows/",
    "plugins/launchpad/scripts/plugin_default_generators/infrastructure/github/workflows/",
]


def _extract_ref(uses_value: str) -> str | None:
    """Extract the ref portion after `@` from a `uses:` value.

    Returns None for local actions (`./path`) or Docker actions
    (`docker://`), which don't have pinnable refs.
    """
    if uses_value.startswith("./") or uses_value.startswith("docker://"):
        return None
    if "@" not in uses_value:
        return None
    return uses_value.rsplit("@", 1)[1]


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (lineno, uses_value, ref) violations."""
    violations: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return violations
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _USES_RE.search(line)
        if not m:
            continue
        uses_value = m.group(1).strip()
        ref = _extract_ref(uses_value)
        if ref is None:
            continue
        if not _SHA_RE.match(ref):
            violations.append((lineno, uses_value, ref))
    return violations


def main() -> int:
    cwd = Path.cwd()
    all_violations: list[tuple[str, int, str, str]] = []

    for scan_dir in SCAN_DIRS:
        d = cwd / scan_dir
        if not d.is_dir():
            continue
        for wf in sorted(d.rglob("*.yml")):
            for lineno, uses_value, ref in scan_file(wf):
                relpath = str(wf.relative_to(cwd))
                all_violations.append((relpath, lineno, uses_value, ref))
        for wf in sorted(d.rglob("*.yaml")):
            for lineno, uses_value, ref in scan_file(wf):
                relpath = str(wf.relative_to(cwd))
                all_violations.append((relpath, lineno, uses_value, ref))
        for wf in sorted(d.rglob("*.yml.j2")):
            for lineno, uses_value, ref in scan_file(wf):
                relpath = str(wf.relative_to(cwd))
                all_violations.append((relpath, lineno, uses_value, ref))

    if not all_violations:
        return 0

    print(
        "ERROR: GitHub Actions refs must be 40-char SHA pins (not tags or branches):",
        file=sys.stderr,
    )
    for relpath, lineno, uses_value, ref in all_violations:
        print(f"  {relpath}:{lineno}: {uses_value} (ref={ref!r})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
