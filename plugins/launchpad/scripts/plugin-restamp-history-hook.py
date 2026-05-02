#!/usr/bin/env python3
"""commit-msg hook → `.harness/observations/restamp-history.jsonl`.

Per OPERATIONS §0 strip-back-aware Layer 9 P3-2 closure: the commit-msg hook
MUST be wired to a Python script (not shell) so injection-defense is
enforceable via the same write protocol as `scaffold-rejection-<ts>.jsonl`.

Injection defenses (Phase 7 §4.9 acceptance):

  1. **`\\n` / `\\r\\n` rejection**: subject lines containing literal newline
     or CR+LF bytes are hard-rejected (exit non-zero, no JSONL line written).
  2. **`json.dumps`**: writer uses canonical JSON serialization
     (sort_keys + tight separators + ensure_ascii) — never f-strings or
     manual string concat.
  3. **`0o600`**: file mode locked at user-only via `os.fchmod(fd, 0o600)`.
  4. **`flock`**: `.harness/observations/.restamp-history.lock` sentinel +
     `fcntl.LOCK_EX` for write serialization.
  5. **`pid` + `pid_start_time`**: forensic identity stamped on every entry
     via `pid_identity.get_pid_start_time()`.

The `prev_entry_sha256` chain field (BL-215) is DEFERRED to v2.2 per
HANDSHAKE §1.5 strip-back. v2.0 ships baseline injection-defense only.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pid_identity import get_pid_start_time  # noqa: E402

SCHEMA_VERSION = "1.0"
RESTAMP_FILENAME = "restamp-history.jsonl"
LOCK_FILENAME = ".restamp-history.lock"


def _utc_now_iso_sec() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _harness_obs_dir(repo_root: Path) -> Path:
    return repo_root / ".harness" / "observations"


def validate_subject(subject: str) -> str | None:
    """Return None if subject is acceptable; an error reason string otherwise.

    Rejects:
      - Literal `\\n` (LF) byte anywhere in the subject.
      - Literal `\\r\\n` (CR+LF) byte sequence anywhere in the subject.
      - Literal `\\r` (lone CR) byte.

    A clean commit subject is a single line; anything containing newline-class
    bytes is treated as an injection attempt.
    """
    if not isinstance(subject, str):
        return "subject must be a string"
    if "\n" in subject:
        return "subject contains literal LF (\\n) — injection-rejected"
    if "\r" in subject:
        return "subject contains literal CR (\\r) — injection-rejected"
    return None


def append_entry(repo_root: Path, payload: dict) -> Path:
    """Atomic append of `payload` to restamp-history.jsonl.

    flock-serialized; mode 0o600 enforced. Returns the path written.
    """
    obs = _harness_obs_dir(repo_root)
    obs.mkdir(parents=True, exist_ok=True)
    target = obs / RESTAMP_FILENAME
    lock_path = obs / LOCK_FILENAME

    line = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    encoded = line.encode("utf-8")

    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            os.fchmod(lock_fd, 0o600)
        except OSError:
            pass
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        fd = os.open(str(target), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)

    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="commit-msg hook: validates the subject and appends a "
                    "restamp-history.jsonl entry. Rejects on \\n/\\r\\n "
                    "injection (exit non-zero, no JSONL write).",
    )
    parser.add_argument(
        "commit_msg_path",
        help="Path to the commit-msg file (lefthook passes this as $1).",
    )
    parser.add_argument(
        "--repo-root", type=Path, default=None,
        help="Override the repo root (defaults to the current working "
             "directory; tests use this).",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root if args.repo_root is not None else Path.cwd()
    msg_path = Path(args.commit_msg_path)
    if not msg_path.is_file():
        print(f"restamp-hook: commit-msg file not found: {msg_path}",
              file=sys.stderr)
        return 1

    raw_bytes = msg_path.read_bytes()
    # Determine the subject's raw bytes — everything up to the first LF byte.
    # If the file contains an embedded CR before the first LF, that's a CR
    # injection in the subject line itself.
    lf_idx = raw_bytes.find(b"\n")
    subject_bytes = raw_bytes[:lf_idx] if lf_idx >= 0 else raw_bytes
    subject = subject_bytes.decode("utf-8", errors="replace")

    # Reject if the subject's bytes contain ANY CR (lone or part of a CRLF).
    if b"\r" in subject_bytes:
        print(
            "restamp-hook: REJECTED — subject contains literal CR (\\r) — "
            "injection-rejected",
            file=sys.stderr,
        )
        return 1
    # Reject if there are MULTIPLE LF-terminated lines BEFORE the body
    # separator (\n\n). A valid commit message's subject is a single line.
    raw = raw_bytes.decode("utf-8", errors="replace")
    pre_body = raw.split("\n\n", 1)[0]
    # pre_body is the subject plus any single trailing LF; multiple LFs
    # before the body separator means the subject was split across lines.
    pre_body_lines = [ln for ln in pre_body.split("\n") if ln]
    if len(pre_body_lines) > 1:
        print(
            "restamp-hook: REJECTED — subject contains literal LF (\\n) — "
            "injection-rejected",
            file=sys.stderr,
        )
        return 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": _utc_now_iso_sec(),
        "pid": os.getpid(),
        "pid_start_time": get_pid_start_time(),
        "subject": subject,
    }
    try:
        path = append_entry(repo_root, payload)
    except OSError as exc:
        print(f"restamp-hook: write failed: {exc}", file=sys.stderr)
        return 1
    print(f"restamp-hook: appended to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
