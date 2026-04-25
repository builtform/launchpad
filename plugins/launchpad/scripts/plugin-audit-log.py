#!/usr/bin/env python3
"""Append-only audit log for autonomous-mode invocations.

Records one line per autonomous execution at `.launchpad/audit.log`:

    <ISO-8601 timestamp> user=<git-user> head=<commit-sha> commands_sha=<content-sha> command=<invoked>

Design:
  - Gitignored by default — local debug log, not a tracked artifact.
    Committing it creates merge conflicts on multi-contributor repos and
    leaks developer-activity timelines in public OSS repos.
  - Team repos that WANT PR-review visibility set `audit: { committed: true }`
    in .launchpad/config.yml — opt-in. The gitignore line is inside the
    repo's top-level .gitignore and is authored by /lp-define's config
    scaffolding; flipping the flag doesn't auto-remove the ignore line
    (user's choice when they decide to track).
  - Entries record the CONTENT hash of config.yml's commands section, NOT
    the commit SHA. Content hash survives rebase/amend/squash; commit SHA
    does not.
  - commands_sha is truncated to 16 hex chars in the log for readability.
    The full 64-char hash is available via plugin-config-hash.py. The CI
    override env var (LP_CONFIG_REVIEWED) accepts either form: the full
    64-char hash (preferred) or the 16-char prefix (convenience — matches
    what this log displays).
  - No rotation. One line per invocation gives ~100K invocations per 10MB;
    practical problem doesn't exist. If a repo ever approaches that volume,
    the user can truncate manually.

Usage:
  plugin-audit-log.py --command=lp-build [--repo-root PATH]

Exit 0 on success; 1 on failure (missing config.yml, write-permission issue).
"""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _git_user(repo_root: Path) -> str:
    """Prefer the local repo git user.email, fall back to user.name, else
    $USER, else 'unknown'."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "config", "user.email"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
        out = subprocess.run(
            ["git", "-C", str(repo_root), "config", "user.name"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except FileNotFoundError:
        pass
    return os.environ.get("USER", "unknown")


def _git_head(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()[:12]  # short sha is enough for forensics
    except FileNotFoundError:
        pass
    return "no-git"


def _commands_sha(repo_root: Path) -> str:
    """Invoke plugin-config-hash.py; returns 'no-commands' if absent/error."""
    script = SCRIPT_DIR / "plugin-config-hash.py"
    try:
        out = subprocess.run(
            [sys.executable, str(script), f"--repo-root={repo_root}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()[:16]  # 16-hex-char prefix is plenty
    except Exception:
        pass
    return "no-commands"


def _sanitize_field(raw: str) -> str:
    """Escape characters that would corrupt or forge a one-line audit
    entry. Every interpolated field gets this treatment, not just `command`.
    git user.email / user.name are user-controlled (via local git config or
    a hostile commit author trailer) and could otherwise smuggle newlines or
    control characters into the log to fake separate entries or hide rows.
    """
    if raw is None:
        return ""
    out_chars: list[str] = []
    for ch in str(raw):
        # Newlines and CRs would split the line.
        if ch == "\n":
            out_chars.append("\\n")
        elif ch == "\r":
            out_chars.append("\\r")
        # Field separator we choose (' ') is fine to keep, but any other
        # control character (DEL, \t, \0, ANSI escapes) gets percent-escaped
        # so nothing renders as terminal control or breaks log parsing.
        elif ord(ch) < 0x20 or ord(ch) == 0x7f:
            out_chars.append(f"\\x{ord(ch):02x}")
        else:
            out_chars.append(ch)
    return "".join(out_chars)


def append_entry(repo_root: Path, command: str) -> Path:
    """Append a single line to .launchpad/audit.log. Creates the file if
    missing; never truncates or rotates. Returns the log path."""
    log_dir = repo_root / ".launchpad"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "audit.log"

    timestamp = _sanitize_field(
        datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    )
    user = _sanitize_field(_git_user(repo_root))
    head = _sanitize_field(_git_head(repo_root))
    sha = _sanitize_field(_commands_sha(repo_root))
    safe_cmd = _sanitize_field(command)

    line = (
        f"{timestamp} user={user} head={head} commands_sha={sha} command={safe_cmd}\n"
    )
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)

    return log_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--command", required=True, help="name of the invoking command (e.g. lp-build)")
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    args = ap.parse_args()

    try:
        path = append_entry(Path(args.repo_root).resolve(), args.command)
        print(str(path))
        return 0
    except Exception as e:
        print(f"audit-log error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
