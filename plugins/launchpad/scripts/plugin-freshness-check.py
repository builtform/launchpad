#!/usr/bin/env python3
"""Freshness gate for plugin-shipped catalog/pattern + contract docs
(OPERATIONS §4).

Validates `last_validated:` ≤ 30 days on:
  - plugins/launchpad/scaffolders.yml (top-level + per-entry)
  - plugins/launchpad/scaffolders/<stack>-pattern.md (frontmatter)
  - plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml
    (top-level + per-entry override)
  - plugins/launchpad/scripts/lp_pick_stack/data/pillar-framework.md
    (frontmatter)
  - docs/architecture/SCAFFOLD_HANDSHAKE.md (frontmatter)
  - docs/architecture/SCAFFOLD_OPERATIONS.md (frontmatter)

Per Layer 2 F-02 + Phase -1 promotion: this script runs ADVISORY on every
PR for the entire 22-34-week dev window so behavior is well-exercised before
Phase 7.5 promotes it to a gating check.

Per OPERATIONS §4 single-30d-window simplification (Layer 3 P1-B): tier-based
freshness (90d/30d/14d) is BL-213 deferred to v2.1 if observed drift demands it.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent

DEFAULT_WINDOW_DAYS = 30

# Files required to carry `last_validated:` per OPERATIONS §4.
TARGET_FILES = (
    "plugins/launchpad/scaffolders.yml",
    "plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml",
    "plugins/launchpad/scripts/lp_pick_stack/data/pillar-framework.md",
    "docs/architecture/SCAFFOLD_HANDSHAKE.md",
    "docs/architecture/SCAFFOLD_OPERATIONS.md",
)

# Glob patterns for per-entry pattern docs.
TARGET_GLOBS = (
    "plugins/launchpad/scaffolders/*-pattern.md",
)

LAST_VALIDATED_RE = re.compile(
    r"^\s*last_validated\s*:\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?\s*$",
    re.MULTILINE,
)


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _extract_last_validated(text: str) -> str | None:
    m = LAST_VALIDATED_RE.search(text)
    return m.group(1) if m else None


def _enumerate_targets() -> list[Path]:
    out: list[Path] = []
    for rel in TARGET_FILES:
        p = REPO_ROOT / rel
        if p.exists():
            out.append(p)
    for glob in TARGET_GLOBS:
        for p in REPO_ROOT.glob(glob):
            out.append(p)
    return out


def check_freshness(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    advisory: bool = True,
    today: date | None = None,
) -> int:
    """Return 0 on PASS, 1 on FAIL (when not advisory).

    Advisory mode prints findings but always returns 0 (PR-context default
    during the v2.0 dev window). Gating mode (Phase 7.5 ship) returns 1 on
    any drift > window_days.
    """
    today_d = today or _today_utc()
    targets = _enumerate_targets()
    findings: list[str] = []

    for path in targets:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(f"{path.relative_to(REPO_ROOT)}: read error: {exc}")
            continue
        last = _extract_last_validated(text)
        if last is None:
            findings.append(
                f"{path.relative_to(REPO_ROOT)}: missing `last_validated:` "
                f"frontmatter"
            )
            continue
        try:
            last_d = _parse_date(last)
        except ValueError:
            findings.append(
                f"{path.relative_to(REPO_ROOT)}: `last_validated: {last}` is "
                f"not a valid YYYY-MM-DD"
            )
            continue
        age = (today_d - last_d).days
        if age > window_days:
            findings.append(
                f"{path.relative_to(REPO_ROOT)}: stale (last_validated={last}, "
                f"age={age}d, window={window_days}d)"
            )

    if findings:
        label = "ADVISORY" if advisory else "FAIL"
        print(f"freshness check {label} ({len(findings)} finding(s)):",
              file=sys.stderr)
        for f in findings:
            print(f"  {f}", file=sys.stderr)
        if not advisory:
            return 1

    if not findings:
        print(f"freshness check: PASS ({len(targets)} target(s) within "
              f"{window_days}d)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window-days", type=int, default=DEFAULT_WINDOW_DAYS,
        help=f"Freshness window in days (default: {DEFAULT_WINDOW_DAYS})",
    )
    parser.add_argument(
        "--gating", action="store_true",
        help="Gating mode: exit 1 on stale; default is advisory (always exit 0).",
    )
    parser.add_argument(
        "--today", type=str, default=None,
        help="Override today's date as YYYY-MM-DD (for testing/Phase 7.5 lock).",
    )
    args = parser.parse_args()

    today = _parse_date(args.today) if args.today else None
    return check_freshness(
        window_days=args.window_days,
        advisory=not args.gating,
        today=today,
    )


if __name__ == "__main__":
    sys.exit(main())
