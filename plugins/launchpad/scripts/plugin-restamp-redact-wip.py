#!/usr/bin/env python3
"""Pre-squash filter for `.harness/observations/restamp-history.jsonl`.

v2.1 Codex PR #50 (Slice E commit pattern). Strips entries whose
`subject` matches `^wip\\(slice-[a-z]+\\):` from the JSONL audit log,
writing the filtered result via `atomic_write_replace`. The audit log
is committed; `git reset --soft` does NOT retroactively redact it, so
this script is a separate pre-squash step.

Tightened regex: `^wip\\(slice-[a-z]+\\):` (NOT `^wip[\\(:]`) so
hypothetical non-checkpoint entries like `wip(experiment):` are
preserved.

Exit codes:
  0   success (including no-op when JSONL absent — fresh-project case is success)
  65  malformed JSONL (EX_DATAERR)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SLICE_WIP_RE = re.compile(r"^wip\(slice-[a-z]+\):")
RESTAMP_RELPATH = Path(".harness") / "observations" / "restamp-history.jsonl"


def filter_jsonl(text: str) -> tuple[str, int]:
    """Return (filtered_text, dropped_count). Raise ValueError on malformed."""
    out_lines: list[str] = []
    dropped = 0
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            entry = json.loads(raw_line)
        except ValueError as exc:
            raise ValueError(f"line {lineno}: {exc}") from exc
        subject = entry.get("subject") if isinstance(entry, dict) else None
        if isinstance(subject, str) and SLICE_WIP_RE.match(subject):
            dropped += 1
            continue
        out_lines.append(raw_line)
    filtered = "\n".join(out_lines)
    if filtered:
        filtered += "\n"
    return filtered, dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strip wip(slice-x):-prefixed entries from restamp-history.jsonl.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: current working directory).",
    )
    args = parser.parse_args(argv)

    target = args.repo_root / RESTAMP_RELPATH
    if not target.is_file():
        # Fresh project (no audit log yet); no-op success.
        print(f"plugin-restamp-redact-wip: no JSONL at {target}; nothing to filter")
        return 0

    text = target.read_text(encoding="utf-8")
    try:
        filtered, dropped = filter_jsonl(text)
    except ValueError as exc:
        print(
            f"plugin-restamp-redact-wip: malformed JSONL at {target}: {exc}",
            file=sys.stderr,
        )
        return 65

    if dropped == 0:
        print(
            f"plugin-restamp-redact-wip: no wip(slice-...): entries found at {target}"
        )
        return 0

    # Atomic replace via os.replace from a sibling .tmp.
    sys.path.insert(0, str(args.repo_root / "plugins" / "launchpad" / "scripts"))
    from atomic_io import atomic_write_replace

    atomic_write_replace(
        target, filtered.encode("utf-8"), mode=0o600, trusted_root=args.repo_root
    )
    print(
        f"plugin-restamp-redact-wip: redacted {dropped} wip(slice-...): "
        f"entries from {target}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
