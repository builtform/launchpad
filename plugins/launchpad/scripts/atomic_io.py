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
import warnings
from collections.abc import Iterator, Mapping
from pathlib import Path

__all__ = [
    "atomic_write_excl",
    "atomic_write_replace",
    "atomic_write_replace_batch",
    "advisory_flock",
]


def _assert_path_safe(
    target: Path,
    trusted_root: Path | None,
) -> None:
    """Reject `target` if a symlink redirection escapes `trusted_root`.

    Three security checks (all load-bearing per the v2.1.0 atomic_io
    symlink-rejection plan §2.1):

      1. Reject if `target` itself is a symlink (closes the primary attack
         vector where `cwd/.launchpad/scaffold-decision.json -> /tmp/loot`
         defeats an ancestor-only walk).
      2. Walk the parent chain from `target.parent` up to `trusted_root`
         inclusive; reject if any ancestor is a symlink. Defeats
         `.github -> /tmp/outside` and similar ancestor redirection.
      3. Defense-in-depth: assert `target_abs.parent.resolve()` is a
         descendant of `trusted_root.resolve()`. Catches the
         absolute-path-through-symlink case where `target.parent` itself
         is not a symlink but its resolved path escapes `trusted_root`.

    When `trusted_root is None`, defaults to `Path.cwd().resolve()` and
    emits a `RuntimeWarning` so production-path accidental misuse is loud.
    Production callers MUST pass an explicit `trusted_root`.

    Pure assertion; returns `None`. Threat model is workspace-boundary
    protection (NOT multi-tenant filesystem-level attacker); TOCTOU
    between this check and the subsequent mkdir/mkstemp/os.open is
    acknowledged accept-residual at v2.1.0.
    """
    if trusted_root is None:
        warnings.warn(
            "atomic_io: trusted_root not passed; defaulting to Path.cwd() "
            "-- production callers MUST pass explicit trusted_root.",
            RuntimeWarning,
            stacklevel=2,
        )
    trusted_abs = (trusted_root or Path.cwd()).resolve()
    target_abs = target if target.is_absolute() else (trusted_abs / target)
    # Check 1: target itself.
    if target_abs.is_symlink():
        raise OSError(f"atomic_io: refused write through symlinked target {target!r}")
    # Check 2: walk parent chain up to trusted_root inclusive. We compare
    # `current.resolve()` against `trusted_abs` because the unresolved
    # chain may traverse system-level symlinks (e.g., macOS
    # `/var -> /private/var`); without the resolve-step the walk would
    # never see the trusted_root sentinel and march all the way to `/`.
    current = target_abs.parent
    while True:
        try:
            current_resolved = current.resolve()
        except OSError as err:
            # Component disappeared mid-walk; refuse fail-closed.
            raise OSError(
                f"atomic_io: parent chain of {target!r} could not be resolved"
            ) from err
        if not current_resolved.is_relative_to(trusted_abs):
            # Walked above trusted_root — Check 3 below is the
            # authoritative escape-detector, so leave that to it.
            break
        if current.is_symlink():
            raise OSError(
                f"atomic_io: refused write through symlinked ancestor "
                f"{current!r} of target {target!r}"
            )
        if current_resolved == trusted_abs or current == current.parent:
            break
        current = current.parent
    # Check 3: defense-in-depth (absolute-path-through-symlink case).
    try:
        target_abs.parent.resolve().relative_to(trusted_abs)
    except (ValueError, OSError) as exc:
        raise OSError(
            f"atomic_io: target parent {target_abs.parent!r} escapes "
            f"trusted_root {trusted_abs!r}"
        ) from exc


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


def _write_all(fd: int, data: bytes) -> None:
    """POSIX-safe full-write loop.

    `write(2)` is permitted to perform a short write — on certain
    filesystems and signal scenarios, `os.write(fd, data)` returns a
    value smaller than `len(data)`. The bare-call sites prior to
    v2.1.0 silently truncated. Per v2.1.0 completion plan §4.1: loop
    until all bytes are flushed; `OSError` propagates so callers can
    rollback the partial write.
    """
    mv = memoryview(data)
    written = 0
    while written < len(mv):
        n = os.write(fd, mv[written:])
        if n == 0:
            raise OSError(
                "atomic_io._write_all: os.write returned 0 with "
                f"{len(mv) - written} bytes remaining"
            )
        written += n


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
    trusted_root: Path | None = None,
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

    Symlink-rejection: `_assert_path_safe(target, trusted_root)` runs
    before mkdir to refuse writes through symlinked ancestors or a
    symlinked target. `O_NOFOLLOW` is added to the open flags as
    belt-and-braces (defends if the pre-check is bypassed). Production
    callers MUST pass an explicit `trusted_root`.
    """
    _assert_path_safe(target, trusted_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        str(target),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        mode,
    )
    try:
        try:
            os.fchmod(fd, mode)
        except OSError:
            pass
        _write_all(fd, encoded)
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
    trusted_root: Path | None = None,
) -> None:
    """Atomically replace `target` via tempfile-in-same-dir plus os.replace.

    Writes `encoded` into a tempfile inside `target.parent` (so os.replace
    is atomic on the same filesystem), fsyncs the tempfile, applies
    F_FULLFSYNC on darwin, then atomically renames into place. Parent
    directory is fsynced after the rename so the directory entry is durable.

    Allows overwriting an existing `target`. The rename is atomic on POSIX
    — readers either see the old content or the new, never a partial write.

    Symlink-rejection: `_assert_path_safe(target, trusted_root)` runs
    before mkdir/mkstemp to refuse writes through symlinked ancestors or
    a symlinked target. Production callers MUST pass an explicit
    `trusted_root`.
    """
    _assert_path_safe(target, trusted_root)
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
            _write_all(fd, encoded)
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


def atomic_write_replace_batch(
    batch: Mapping[Path, bytes],
    *,
    modes: Mapping[Path, int] | None = None,
    default_mode: int = 0o600,
    trusted_root: Path | None = None,
) -> None:
    """Two-phase atomic write of `batch` (v2.1 Codex PR #50 post-review P1).

    Phase 1 — stage (atomic — partial failure leaves all targets untouched):
      For each `(target, content)` pair, write content into a sibling
      `.<basename>.<random>.tmp` in the target's parent dir; fsync;
      fchmod to the per-target mode (or `default_mode`). If any stage
      fails, unlink ALL staged tempfiles and raise — original target
      files on disk are byte-for-byte unchanged.

    Phase 2 — rename (best-effort — same-FS atomic renames make full-batch
    failure rare but not impossible):
      Atomic-rename each staged tempfile to its final path. Same-FS
      rename is guaranteed because the tempfile lives in the target's
      parent dir. If a rename fails mid-batch, the failed tempfile
      remains on disk as `.tmp` and any prior renames remain at final
      paths — the operator surface is the propagated `OSError`.

    Replaces the prior sequential `atomic_write_replace` loop in
    `RendererBase.write_batch()`, which committed each write
    immediately and could leave the batch in a partial state when a
    later write failed. Lint allowlist rule applies to this helper
    too — see `plugin-v2-handshake-lint.py
    ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS`.
    """
    modes = modes or {}
    staged: list[tuple[Path, Path]] = []
    in_flight_tmp: Path | None = None
    try:
        for target, content in batch.items():
            # Symlink-rejection: refuse-all on first symlinked ancestor or
            # target. Runs BEFORE mkstemp so no tempfiles are staged on
            # rejection. Production callers MUST pass an explicit
            # `trusted_root`; the optional default emits a RuntimeWarning.
            _assert_path_safe(target, trusted_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = modes.get(target, default_mode)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=str(target.parent),
            )
            in_flight_tmp = Path(tmp_name)
            try:
                try:
                    os.fchmod(fd, mode)
                except OSError:
                    pass
                _write_all(fd, content)
                os.fsync(fd)
                _full_fsync_darwin(fd)
            finally:
                os.close(fd)
            staged.append((target, in_flight_tmp))
            in_flight_tmp = None
    except BaseException:
        # Clean up the in-flight tmp (created by mkstemp but not yet
        # appended to `staged` — happens when fchmod / os.write / fsync
        # raises mid-staging). Then unlink all already-staged tmp files
        # so the caller observes byte-for-byte unchanged target files.
        if in_flight_tmp is not None:
            with contextlib.suppress(OSError):
                in_flight_tmp.unlink()
        for _target, tmp in staged:
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise

    for target, tmp in staged:
        os.replace(str(tmp), str(target))
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
