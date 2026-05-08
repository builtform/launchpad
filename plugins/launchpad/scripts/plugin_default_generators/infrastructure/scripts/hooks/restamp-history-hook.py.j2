#!/usr/bin/env python3
"""commit-msg hook — restamp-history.jsonl appender (downstream wrapper).

v2.1 Codex PR #50 P1.A (D1) downstream-only template wrapper around the
upstream `plugin-restamp-history-hook.py`. Introduces a subject-line
allowlist (the upstream hook has injection-only defenses; the downstream
template adds prefix-acceptance so projects can enforce conventional
commit subjects + the `wip(slice-x):` checkpoint pattern).

Allowlist (regex): `^(feat|fix|chore|docs|refactor|test|style|perf|ci|wip)\\b`
followed by an optional `(scope)` and a `:` separator. Subjects not
matching are rejected with exit code 65 (EX_DATAERR) and a remediation
message naming the accepted prefixes.

Newline-class injection rejection (`\\n` / `\\r\\n` / `\\r`) is delegated
to the upstream hook subprocess invocation.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Conventional-commit prefixes plus `wip` (for slice-checkpoint pattern).
ALLOWED_SUBJECT_PREFIX_RE = re.compile(
    r"^(feat|fix|chore|docs|refactor|test|style|perf|ci|wip)"
    r"(\([^\)]*\))?"
    r"!?:\s+\S",
)

# Path to the upstream hook script. Downstream projects ship this template
# at `scripts/hooks/restamp-history-hook.py`; the upstream hook lives at
# `plugins/launchpad/scripts/plugin-restamp-history-hook.py` (sibling
# directory under any LaunchPad-installed project).
DEFAULT_UPSTREAM_HOOK = Path("plugins/launchpad/scripts/plugin-restamp-history-hook.py")


def _read_subject(commit_msg_path: Path) -> str:
    raw_bytes = commit_msg_path.read_bytes()
    lf_idx = raw_bytes.find(b"\n")
    subject_bytes = raw_bytes[:lf_idx] if lf_idx >= 0 else raw_bytes
    return subject_bytes.decode("utf-8", errors="replace")


def _validate_prefix(subject: str) -> str | None:
    """Return None if the subject matches the allowlist; an error otherwise."""
    if ALLOWED_SUBJECT_PREFIX_RE.match(subject):
        return None
    return (
        "subject does not match the allowed conventional-commit prefix list. "
        "Accepted prefixes: feat, fix, chore, docs, refactor, test, style, "
        "perf, ci, wip — followed by optional `(scope)` and `: <description>`. "
        f"Got: {subject!r}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "commit-msg hook (downstream wrapper): enforces "
            "conventional-commit subject prefix + delegates injection "
            "defense + restamp-history.jsonl append to the upstream hook."
        ),
    )
    parser.add_argument(
        "commit_msg_path",
        help="Path to the commit-msg file (lefthook passes this as $1).",
    )
    parser.add_argument(
        "--upstream-hook",
        type=Path,
        default=DEFAULT_UPSTREAM_HOOK,
        help="Override the upstream hook path (tests pin this).",
    )
    args = parser.parse_args(argv)

    msg_path = Path(args.commit_msg_path)
    if not msg_path.is_file():
        print(
            f"restamp-hook (downstream): commit-msg file not found: {msg_path}",
            file=sys.stderr,
        )
        return 1

    subject = _read_subject(msg_path)
    err = _validate_prefix(subject)
    if err is not None:
        print(f"restamp-hook (downstream): REJECTED — {err}", file=sys.stderr)
        return 65  # EX_DATAERR

    # Delegate injection defense + JSONL append to the upstream hook.
    upstream = args.upstream_hook
    if not upstream.is_file():
        # Graceful degrade: prefix accepted; upstream hook absent (e.g.,
        # the project has not installed the LaunchPad plugin); skip the
        # JSONL append. Exit 0 so the commit proceeds.
        return 0
    completed = subprocess.run(
        [sys.executable, str(upstream), str(msg_path)],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
