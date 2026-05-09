#!/usr/bin/env python3
"""Backlog orphan check (slip-prevention gate).

For a given release version, every BL header in `docs/tasks/BACKLOG.md`
labeled for that release MUST be either:

  1. Marked closed via a `**Status**:` line whose value contains one of
     `shipped`, `closed`, `re-targeted`, `deferred`, `superseded`, OR
  2. Referenced by `BL-<num>` in the matching `## [<version>]` block of
     `CHANGELOG.md`.

If neither condition holds, the BL is an *orphan*: labeled for the
release but invisible at ship time. v2.1.0 ship preparation surfaced
five such orphans (BL-212, BL-218, BL-237, BL-245, BL-246, plus the
already-discovered BL-236) which slipped because the architecture-doc to
implementation-plan handoff dropped them and no automated gate caught
the loss.

Usage::

    plugin-backlog-orphan-check.py --release 2.1.0
    plugin-backlog-orphan-check.py --release 2.1.0 --verbose

Exit 0 when clean; exit 1 with a per-orphan report when any BL is
labeled for the release without a status marker or CHANGELOG reference.

Version matching:
  * BL header `v2.1` matches `MAJOR.MINOR.0` only (i.e. `v2.1` -> 2.1.0)
  * BL header `v2.1.1` matches `2.1.1` exactly
  * BL header `v2.1 / v2.1.1` (slash- or comma-separated) matches either
  * Patch slips MUST be made explicit by re-labeling the BL header
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BACKLOG = REPO_ROOT / "docs" / "tasks" / "BACKLOG.md"
DEFAULT_CHANGELOG = REPO_ROOT / "CHANGELOG.md"

BL_HEADER_RE = re.compile(
    r"^#### BL-(?P<num>\d+)\s*-\s*(?P<versions>v[\d.]+(?:[\s/,]+v[\d.]+)*)",
    re.MULTILINE,
)
STATUS_LINE_RE = re.compile(
    r"^\*\*Status[^*]*\*\*:\s*(?P<value>[^\n]+)",
    re.MULTILINE,
)
CLOSED_VALUES = ("shipped", "closed", "re-targeted", "deferred", "superseded")
CHANGELOG_VERSION_RE = re.compile(r"^## \[(?P<version>[\d.]+)\]", re.MULTILINE)


def parse_versions(label: str) -> list[str]:
    """Return all v-prefixed versions from a header like ``v2.1 / v2.1.1``."""
    return [m.lstrip("v") for m in re.findall(r"v[\d.]+", label)]


def version_matches_release(label_version: str, release: str) -> bool:
    """Treat `2.1` as `2.1.0`; require exact match for explicit patches."""
    if label_version == release:
        return True
    if label_version.count(".") == 1:
        return f"{label_version}.0" == release
    return False


def extract_bl_body(backlog_text: str, bl_num: str) -> str:
    pattern = re.compile(
        rf"^#### BL-{bl_num}\s.*?(?=^#### BL-|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(backlog_text)
    return match.group(0) if match else ""


def has_close_marker(body: str) -> str | None:
    """Return the matched close-marker phrase if present, else None."""
    for m in STATUS_LINE_RE.finditer(body):
        value = m.group("value").lower()
        for keyword in CLOSED_VALUES:
            if keyword in value:
                return f"Status line: {m.group(0).splitlines()[0]}"
    return None


def changelog_block(text: str, release: str) -> str:
    """Return the body of the ``## [<release>]`` section, or empty."""
    versions = list(CHANGELOG_VERSION_RE.finditer(text))
    for i, m in enumerate(versions):
        if m.group("version") == release:
            start = m.end()
            end = versions[i + 1].start() if i + 1 < len(versions) else len(text)
            return text[start:end]
    return ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", required=True, help="e.g. 2.1.0")
    p.add_argument("--backlog", default=str(DEFAULT_BACKLOG), type=Path)
    p.add_argument("--changelog", default=str(DEFAULT_CHANGELOG), type=Path)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    backlog_text = args.backlog.read_text(encoding="utf-8")
    changelog_text = args.changelog.read_text(encoding="utf-8")
    release_block = changelog_block(changelog_text, args.release)

    orphans: list[tuple[str, str]] = []
    closed: list[tuple[str, str]] = []

    for header in BL_HEADER_RE.finditer(backlog_text):
        bl_num = header.group("num")
        labels = parse_versions(header.group("versions"))
        if not any(version_matches_release(v, args.release) for v in labels):
            continue

        body = extract_bl_body(backlog_text, bl_num)
        marker = has_close_marker(body)
        if marker:
            closed.append((bl_num, marker))
            continue

        if re.search(rf"\bBL-{bl_num}\b", release_block):
            closed.append(
                (bl_num, f"CHANGELOG [{args.release}] references BL-{bl_num}")
            )
            continue

        orphans.append((bl_num, header.group(0).strip()))

    if args.verbose:
        for n, why in closed:
            print(f"  ok  BL-{n}: {why}", file=sys.stderr)

    if not orphans:
        print(
            f"backlog-orphan-check: PASS ({len(closed)} BLs labeled for {args.release}, all closed/deferred)"
        )
        return 0

    print(
        f"backlog-orphan-check: FAIL ({len(orphans)} BL(s) labeled for {args.release} "
        f"without status marker or CHANGELOG reference):\n",
        file=sys.stderr,
    )
    for bl_num, header in orphans:
        print(f"  BL-{bl_num}", file=sys.stderr)
        print(f"    header: {header}", file=sys.stderr)
        print(
            f"    fix: add a `**Status**: ...` line under the header in "
            f"{args.backlog.relative_to(REPO_ROOT)}, OR reference `BL-{bl_num}` "
            f"inside the `## [{args.release}]` block of "
            f"{args.changelog.relative_to(REPO_ROOT)}.\n",
            file=sys.stderr,
        )
    print(
        "Slip-prevention rationale: BL-236 was labeled v2.1 in BACKLOG.md "
        "but never implemented or deferred during the v2.1 cycle. Discovered "
        "post-hoc on 2026-05-07. This gate prevents a recurrence.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
