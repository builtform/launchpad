"""Shared JSONL appender for `.harness/observations/v2-pipeline-*.jsonl`
(OPERATIONS §5).

Owns the analytics path ONLY: `v2-pipeline-*.jsonl` + `.telemetry.lock` +
`.prune-progress`. Forensic JSONL writes (security-events, scaffold-rejection,
recovery-partial, restamp-history) are owned by `forensic_writer.py` per
Layer 5 architecture P2-A2 SRP split — `forensic_writer.py` is BL-223
deferred to v2.2 per HANDSHAKE §1.5 strip-back.

Honors the `.launchpad/config.yml` `telemetry: off` opt-out: when off, the
writer is a no-op (does not create the directory or any files).
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# JSONL line cap: PIPE_BUF on Linux is 4096; OPERATIONS §5 forces atomic
# single-os.write append safety.
MAX_LINE_BYTES = 4096

# Default 30-day retention; aggregator may override via --retention-days.
DEFAULT_RETENTION_DAYS = 30


def _harness_obs_dir(repo_root: Path) -> Path:
    return repo_root / ".harness" / "observations"


def _telemetry_off(repo_root: Path) -> bool:
    """Return True if `.launchpad/config.yml` has `telemetry: off`.

    No YAML parser dependency: a single-line grep is enough at this layer
    (the field is one of two values: `local` or `off`). If the file is
    missing or unreadable, telemetry defaults to ON (matches the documented
    default in OPERATIONS §5 "Opt-out").
    """
    cfg = repo_root / ".launchpad" / "config.yml"
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("telemetry:"):
            value = stripped.split(":", 1)[1].strip().split("#", 1)[0].strip()
            return value == "off"
    return False


def _utc_now_iso_sec() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _open_lock(lock_path: Path) -> int:
    """Open the `.telemetry.lock` sentinel `O_CREAT|O_RDWR, 0o600` and apply
    explicit `os.fchmod(0o600)` for umask defense.

    The lock file is opened on every operation; never renamed, never unlinked,
    never rotated.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        pass
    return fd


def write_telemetry_entry(
    repo_root: Path,
    payload: dict,
    *,
    timestamp_basename: str | None = None,
) -> Path | None:
    """Append `payload` to `.harness/observations/v2-pipeline-<ts>.jsonl`.

    - Honors `telemetry: off` opt-out (no-op when off).
    - Stamps `schema_version: "1.0"` if the caller did not.
    - Stamps `timestamp` (ISO 8601 UTC sec-precision) if the caller did not.
    - JSONL canonicalization: sort_keys + tight separators + ensure_ascii.
    - Single `os.write` ≤ MAX_LINE_BYTES.
    - flock on `.telemetry.lock`; mode 0o600.

    Returns the path written to, or None if telemetry is opted out.
    """
    if _telemetry_off(repo_root):
        return None

    if not isinstance(payload, dict):
        raise TypeError(
            f"write_telemetry_entry requires dict payload, got {type(payload).__name__}"
        )

    payload = dict(payload)  # local copy; do not mutate caller's dict
    payload.setdefault("schema_version", "1.0")
    payload.setdefault("timestamp", _utc_now_iso_sec())

    obs = _harness_obs_dir(repo_root)
    obs.mkdir(parents=True, exist_ok=True)

    if timestamp_basename is None:
        timestamp_basename = _utc_now_iso_sec().replace(":", "-")
    target = obs / f"v2-pipeline-{timestamp_basename}.jsonl"

    line = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    encoded = line.encode("utf-8")
    if len(encoded) > MAX_LINE_BYTES:
        raise ValueError(
            f"telemetry line {len(encoded)} bytes exceeds MAX_LINE_BYTES={MAX_LINE_BYTES}"
        )

    lock_fd = _open_lock(obs / ".telemetry.lock")
    try:
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
        # Directory fsync for durability of the create.
        try:
            dirfd = os.open(str(obs), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except OSError:
            # Some filesystems disallow directory fsync; best-effort here.
            pass
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)

    return target


def _entry_age_days(line: str, now_epoch: float) -> float | None:
    """Parse the `timestamp` field from a JSONL line and return age in days.

    Returns None on parse failure or missing timestamp (caller decides
    whether to drop unparseable lines; v0 lines without `schema_version`
    are silently skipped per OPERATIONS §5 lenient-policy carve-out).
    """
    try:
        rec = json.loads(line)
    except (ValueError, TypeError):
        return None
    ts = rec.get("timestamp")
    if not isinstance(ts, str):
        return None
    try:
        # Accept the canonical sec-precision Z form.
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (now_epoch - dt.timestamp()) / 86400.0


def prune_telemetry(
    repo_root: Path,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    _now_epoch: float | None = None,
) -> int:
    """Per-file atomic rewrite: keep entries newer than retention_days.

    - Lock-acquisition ordering: `os.stat` for ENOENT detection happens AFTER
      `LOCK_EX` acquisition (per OPERATIONS §5 + Layer 8 ordering pin).
    - Cross-file progress in `.prune-progress`: written after each successful
      per-file rename so a crash mid-prune resumes on next invocation.
    - On completion, atomic-rename `.prune-progress` to `.prune-progress.completed.<ts>`,
      retain max 5.

    Returns the number of files pruned. No-op when telemetry is opted out.
    """
    if _telemetry_off(repo_root):
        return 0

    obs = _harness_obs_dir(repo_root)
    if not obs.exists():
        return 0

    now_epoch = _now_epoch if _now_epoch is not None else time.time()

    # Build the work list under the lock so concurrent writers can't race in
    # a partial view.
    lock_fd = _open_lock(obs / ".telemetry.lock")
    pruned = 0
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        progress_path = obs / ".prune-progress"
        completed: set[str] = set()
        try:
            with progress_path.open("r", encoding="utf-8") as f:
                completed = {ln.strip() for ln in f if ln.strip()}
        except FileNotFoundError:
            pass

        files = sorted(obs.glob("v2-pipeline-*.jsonl"))
        for f in files:
            if f.name in completed:
                continue
            try:
                st = os.stat(f)
            except FileNotFoundError:
                # ENOENT after lock — manually cleaned between cycles. Skip.
                completed.add(f.name)
                continue

            with open(f, "r", encoding="utf-8") as fh:
                lines = fh.readlines()

            kept = []
            for ln in lines:
                age = _entry_age_days(ln, now_epoch)
                if age is None or age <= retention_days:
                    kept.append(ln)

            tmp_name = f".{f.name}.tmp.{os.getpid()}"
            tmp = obs / tmp_name
            tmp_fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                try:
                    os.fchmod(tmp_fd, 0o600)
                except OSError:
                    pass
                if kept:
                    os.write(tmp_fd, "".join(kept).encode("utf-8"))
                os.fsync(tmp_fd)
            finally:
                os.close(tmp_fd)
            os.rename(tmp, f)
            try:
                dirfd = os.open(str(obs), os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dirfd)
                finally:
                    os.close(dirfd)
            except OSError:
                pass

            completed.add(f.name)
            pruned += 1

            # Persist progress after each successful rename.
            with progress_path.open("w", encoding="utf-8") as ph:
                for name in sorted(completed):
                    ph.write(name + "\n")
                ph.flush()
                try:
                    os.fsync(ph.fileno())
                except OSError:
                    pass

        # All files done — atomic-rename the progress file to a .completed
        # marker; retain max 5.
        if progress_path.exists():
            done_name = f".prune-progress.completed.{_utc_now_iso_sec().replace(':', '-')}"
            try:
                os.rename(progress_path, obs / done_name)
            except OSError:
                pass
            done_files = sorted(obs.glob(".prune-progress.completed.*"))
            for old in done_files[:-5]:
                try:
                    old.unlink()
                except OSError:
                    pass
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)

    return pruned


__all__ = [
    "DEFAULT_RETENTION_DAYS",
    "MAX_LINE_BYTES",
    "prune_telemetry",
    "write_telemetry_entry",
]
