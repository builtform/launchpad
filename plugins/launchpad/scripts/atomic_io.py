"""Atomic write helpers + advisory flock wrapper (V3 plan sections 10.4 + 12.3).

Three primitives:

  - `atomic_write_excl(target, encoded, mode=0o600)` — write-once-only via
    O_WRONLY|O_CREAT|O_EXCL plus fsync plus F_FULLFSYNC on darwin plus
    parent-directory fsync. Raises FileExistsError if target already exists.
    Used by /lp-pick-stack scaffold-decision.json, /lp-scaffold-stack
    rationale.md, and other write-once kernel artifacts.

  - `atomic_write_replace(target, encoded, mode=0o600)` — write-then-rename
    via tempfile in same directory plus fsync plus os.replace. Allows
    overwriting an existing target. Used by /lp-bootstrap manifest writes
    (Phase 3 plus) and /lp-update-identity refresh (Phase 10 plus).

  - `advisory_flock(path)` — context manager wrapping fcntl.flock(LOCK_EX)
    around read-modify-write windows on plugin-managed YAML/JSON. No-op on
    platforms without fcntl. Used by /lp-define and /lp-update-identity to
    serialize concurrent-session edits to .launchpad/config.yml and
    scaffold-decision.json.

Durability contract per HANDSHAKE section 4 rule 10 (nonce-ledger writer
precedent): every write fsyncs the file descriptor, applies F_FULLFSYNC on
darwin where available, and fsyncs the parent directory inode so the rename
or create entry is durable. Errors from F_FULLFSYNC and parent-dir fsync are
swallowed — these are best-effort durability hardening, not correctness gates.

The helpers are intentionally narrow: callers that need to compute a hash
over the bytes they wrote, or seal a payload via canonical_hash, do that
themselves and pass the encoded bytes in. Keeping the helpers I/O-only
preserves testability (no payload-shape coupling).
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterator


__all__ = [
    "atomic_write_excl",
    "atomic_write_replace",
    "advisory_flock",
]


def _fsync_parent(target: Path) -> None:
    """Best-effort fsync of the parent directory inode.

    A successful fsync of the file descriptor does not guarantee the
    directory entry is durable — POSIX only requires this when the parent
    directory is also fsynced. We swallow OSErrors because some filesystems
    (FAT, certain network mounts) do not permit O_DIRECTORY or directory
    fsync; the file content is still durable, only the rename ordering
    guarantee is degraded.
    """
    parent = target.parent
    try:
        dirfd = os.open(str(parent), os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        try:
            os.fsync(dirfd)
        except OSError:
            pass
    finally:
        os.close(dirfd)


def _full_fsync_darwin(fd: int) -> None:
    """Apply F_FULLFSYNC on darwin; no-op elsewhere or on unsupported FS.

    F_FULLFSYNC is darwin-specific and asks the disk controller to flush
    its write cache (matches the durability semantics of fsync on Linux ext4
    with default mount options). Errors are swallowed: the file is still
    durable per POSIX fsync, F_FULLFSYNC is hardening on top.
    """
    if sys.platform != "darwin":
        return
    try:
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    except (OSError, AttributeError):
        pass


def atomic_write_excl(
    target: Path,
    encoded: bytes,
    *,
    mode: int = 0o600,
) -> None:
    """Atomically create a new file at `target` with O_CREAT|O_EXCL durability.

    Parents are created (mkdir parents=True, exist_ok=True) before the open.
    File mode is 0o600 by default (owner read/write only) per HANDSHAKE
    section 4 rule 10; callers may override for files that need broader
    permissions. fchmod runs after open as a defensive belt-and-braces step
    because some platforms ignore the open-time mode.

    Raises FileExistsError if target already exists. Callers translate this
    into a domain-specific error (e.g., DecisionWriteError with reason
    `scaffold_decision_already_exists`).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        str(target),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        mode,
    )
    try:
        try:
            os.fchmod(fd, mode)
        except OSError:
            pass
        os.write(fd, encoded)
        os.fsync(fd)
        _full_fsync_darwin(fd)
    finally:
        os.close(fd)
    _fsync_parent(target)


def atomic_write_replace(
    target: Path,
    encoded: bytes,
    *,
    mode: int = 0o600,
) -> None:
    """Atomically replace `target` via tempfile-in-same-dir plus os.replace.

    Writes `encoded` into a tempfile inside `target.parent` (so os.replace
    is atomic on the same filesystem), fsyncs the tempfile, applies
    F_FULLFSYNC on darwin, then atomically renames into place. Parent
    directory is fsynced after the rename so the directory entry is durable.

    Allows overwriting an existing `target`. The rename is atomic on POSIX
    — readers either see the old content or the new, never a partial write.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp = Path(tmp_name)
    try:
        try:
            try:
                os.fchmod(fd, mode)
            except OSError:
                pass
            os.write(fd, encoded)
            os.fsync(fd)
            _full_fsync_darwin(fd)
        finally:
            os.close(fd)
        os.replace(str(tmp), str(target))
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    _fsync_parent(target)


@contextlib.contextmanager
def advisory_flock(path: Path) -> Iterator[None]:
    """Acquire fcntl.LOCK_EX on `path` for the body of the `with`.

    Used to serialize read-modify-write windows on plugin-managed YAML/JSON
    when a brownfield project may have concurrent /lp-define or
    /lp-update-identity sessions. The lock is advisory: it only prevents
    other processes that ALSO call advisory_flock from racing — external
    writers (a user's editor saving the file in another window) bypass it.

    `path` is created with mode 0o600 if absent so the flock target is
    stable across runs even on a fresh project. Lock release happens via
    fd close; we explicitly LOCK_UN first as a courtesy on platforms where
    fd close does not always release immediately.

    No-op on platforms without working fcntl (Windows runtime support is
    out of scope at v2.x; the helper raises ImportError at import time on
    such platforms which makes the omission visible rather than silent).
    """
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
