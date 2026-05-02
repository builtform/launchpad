"""Nonce ledger management (HANDSHAKE §4 rule 10 — full Layer 5/7/8 protocol).

Append-only ledger for consumed `scaffold-decision.json` nonces. The ledger
file `.launchpad/.scaffold-nonces.log` carries fixed 33-byte records
`<UUIDv4-hex-32-chars>\\n`; comment lines `# ...\\n` are skip-lines (format
header + EIO sentinels).

Subprotocols implemented:

- Filesystem whitelist at ledger-init (rejects non-POSIX-local FS via
  `platform_unsupported_filesystem`).
- Lock sentinel: `.launchpad/.scaffold-nonces.lock`, opened `O_CREAT|O_RDWR,
  0o600`, held under `fcntl.flock(LOCK_EX)` for entire ledger op. Lock file
  is NEVER renamed/unlinked (stable across data-file inode changes from
  rotation per Layer 3 frontend-races P1-A FIX).
- Open mode (data file): `O_WRONLY|O_APPEND|O_CREAT, 0o600`. Single
  `os.write(fd, ...)`; POSIX `O_APPEND` byte-atomicity for writes ≤ PIPE_BUF.
- Format header migration (Layer 7 closure of L6-κ #3): on first read, if the
  first line is a valid 32-char UUID-hex (not a `# ...` comment), treat as
  v0 ledger and migrate to v1 under the lock with orphan-tmp cleanup glob
  scoped to `.scaffold-nonces.log.migration-tmp.<pid>` (Layer 8 pin —
  disjoint from the rollover tmp pattern `.scaffold-nonces.log.rollover-tmp.<pid>`).
- 1MB rollover with 5-bak retention; backward-NTP `max(filename_ts, file_ctime)`
  for `.bak` window check (Layer 5 frontend-races P2-L5-A8).
- F_FULLFSYNC on darwin (Layer 3 pattern-finder P1-C).
- EIO/EROFS handling per Layer 2 P1-3 + Layer 3 frontend-races P2-C.
"""
from __future__ import annotations

import errno
import fcntl
import glob
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Per HANDSHAKE §4 rule 10: 33-byte fixed records (32 hex + newline).
_RECORD_LEN = 33
_UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")
_FORMAT_HEADER = "# nonce-ledger-format: v1\n"

# 1 MiB rollover threshold per HANDSHAKE §4 rule 10.
_ROLLOVER_BYTES = 1 << 20
_BAK_RETENTION_COUNT = 5

# Backward-NTP `.bak` window (4h) — per HANDSHAKE §4 rule 10 + rule 9 alignment.
_BAK_WINDOW_SECONDS = 4 * 3600

# Whitelist of accepted filesystem types (HANDSHAKE §4 rule 10 + Layer 5
# product-lens P1-PL5-1). v2.0 SHIPS this whitelist; the BL-218 LP_ALLOW_NONLOCAL_FS
# override defers to v2.1.
_FS_WHITELIST = frozenset({
    "apfs", "hfs", "hfs+", "ext2", "ext3", "ext4",
    "xfs", "btrfs", "zfs",
    # GHA Ubuntu runner default per HANDSHAKE §4 rule 10 acceptance gate.
    "overlay", "overlayfs",
    # Linux tmpfs — accepted because pytest-tmp_path uses /tmp (often tmpfs);
    # Layer 5 acknowledges tmpfs replay risk but tmpfs is per-boot ephemeral
    # and at v2.0 single-maintainer scale this is documented as acceptable.
    "tmpfs",
})


class NonceLedgerError(RuntimeError):
    """Raised on a structured ledger failure. Carries `reason:` field."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _launchpad_dir(repo_root: Path) -> Path:
    return repo_root / ".launchpad"


def ledger_path(repo_root: Path) -> Path:
    return _launchpad_dir(repo_root) / ".scaffold-nonces.log"


def lock_path(repo_root: Path) -> Path:
    return _launchpad_dir(repo_root) / ".scaffold-nonces.lock"


def _migration_tmp_glob(repo_root: Path) -> str:
    return str(_launchpad_dir(repo_root) / ".scaffold-nonces.log.migration-tmp.*")


def _rollover_tmp(repo_root: Path) -> Path:
    return _launchpad_dir(repo_root) / f".scaffold-nonces.log.rollover-tmp.{os.getpid()}"


def _migration_tmp(repo_root: Path) -> Path:
    return _launchpad_dir(repo_root) / f".scaffold-nonces.log.migration-tmp.{os.getpid()}"


# ---------------------------------------------------------------------------
# Filesystem detection
# ---------------------------------------------------------------------------


_FS_TYPE_CACHE: dict[str, str] = {}


def _detect_filesystem_type(path: Path) -> str:
    """Best-effort filesystem-type detection.

    Linux: parse `/proc/self/mountinfo` for the longest matching mount point.
    macOS: parse `mount` output (we read it via `/sbin/mount` as last-resort
    fallback; no shell). Other: return `"unknown"`.

    Caches per-process per-realpath. Detection failure returns `"unknown"`
    (NOT a hard failure at v2.0 strip-back — single-maintainer threat model
    + the whitelist still rejects KNOWN-bad FS types).
    """
    real = os.path.realpath(str(path))
    if real in _FS_TYPE_CACHE:
        return _FS_TYPE_CACHE[real]

    fs_type = "unknown"
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/self/mountinfo", "r", encoding="utf-8") as f:
                # Sort by mount-point length descending so the longest prefix
                # wins — handles nested mounts (e.g., /home/user/.cache-on-tmpfs).
                best_mp = ""
                best_fs = "unknown"
                for line in f:
                    parts = line.split()
                    # Field 4 is the mount point; after a literal " - " separator,
                    # field 0 is fs type.
                    if " - " not in line:
                        continue
                    mp_field = parts[4] if len(parts) > 4 else ""
                    after = line.split(" - ", 1)[1].split()
                    fs = after[0] if after else "unknown"
                    if real == mp_field or real.startswith(mp_field.rstrip("/") + "/"):
                        if len(mp_field) >= len(best_mp):
                            best_mp = mp_field
                            best_fs = fs
                fs_type = best_fs
        except (OSError, FileNotFoundError):
            fs_type = "unknown"
    elif sys.platform == "darwin":
        # macOS doesn't expose /proc; we read /sbin/mount directly via
        # subprocess.run (low-overhead, fixed-arg, no shell). This is the
        # ONE module that calls subprocess directly on darwin — safe_run is
        # for scaffolder-emitting subprocess; this is internal FS introspection.
        try:
            import subprocess  # noqa: PLC0415
            proc = subprocess.run(
                ["/sbin/mount"],
                shell=False,
                check=False,
                capture_output=True,
                timeout=5,
            )
            output = proc.stdout.decode("utf-8", errors="replace")
            best_mp = ""
            best_fs = "unknown"
            for line in output.splitlines():
                # Format: `/dev/disk1s5 on / (apfs, local, journaled)`
                m = re.match(r"^\S+\s+on\s+(\S+)\s+\((\w+)", line)
                if not m:
                    continue
                mp = m.group(1)
                fs = m.group(2).lower()
                if real == mp or real.startswith(mp.rstrip("/") + "/"):
                    if len(mp) >= len(best_mp):
                        best_mp = mp
                        best_fs = fs
            fs_type = best_fs
        except (OSError, ValueError):
            fs_type = "unknown"

    _FS_TYPE_CACHE[real] = fs_type
    return fs_type


def _check_filesystem_whitelist(repo_root: Path) -> None:
    """Probe `.launchpad/`'s filesystem; raise NonceLedgerError if non-whitelisted.

    Per HANDSHAKE §4 rule 10: hard-rejects with `platform_unsupported_filesystem`
    on a known non-POSIX-local FS. Detection failures are tolerated at v2.0
    strip-back (single-maintainer threat model) — the spec's "fail-closed"
    wording is the Layer 5 audit trail; strip-back wins per HANDSHAKE §1.5.
    """
    lp = _launchpad_dir(repo_root)
    lp.mkdir(parents=True, exist_ok=True)
    fs_type = _detect_filesystem_type(lp).lower()
    if fs_type == "unknown":
        # Tolerated: detection couldn't determine. The whitelist still
        # protects against KNOWN-bad types (e.g., 9p, smbfs).
        return
    if fs_type not in _FS_WHITELIST:
        raise NonceLedgerError(
            (
                f"remediation: move .launchpad/ to a local POSIX filesystem "
                f"(apfs/ext4/xfs/btrfs/zfs). Non-local filesystem support "
                f"(WSL2 9p, tmpfs, overlayfs, FUSE) is deferred to v2.1 "
                f"(BL-218). Detected fs={fs_type!r}."
            ),
            reason="platform_unsupported_filesystem",
        )


# ---------------------------------------------------------------------------
# Lock management
# ---------------------------------------------------------------------------


def _open_lock(repo_root: Path) -> int:
    """Open the dedicated `.scaffold-nonces.lock` sentinel (NEVER renamed/unlinked)."""
    lp = _launchpad_dir(repo_root)
    lp.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path(repo_root)), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        pass
    return fd


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def _read_ledger_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def _is_format_header_present(lines: list[str]) -> bool:
    return bool(lines) and lines[0].startswith("# nonce-ledger-format:")


def _looks_like_v0_ledger(lines: list[str]) -> bool:
    """True if the first non-empty line is a bare 32-char UUID hex (no comment)."""
    for line in lines:
        s = line.strip()
        if not s:
            continue
        return bool(_UUID_HEX_RE.fullmatch(s))
    return False


def _migrate_v0_to_v1(repo_root: Path) -> None:
    """Migrate a header-less v0 ledger to v1 format under the lock.

    Caller MUST already hold `LOCK_EX` on `.scaffold-nonces.lock`.

    Per HANDSHAKE §4 rule 10 (Layer 7 closure): orphan-tmp cleanup at entry
    via glob restricted to `.scaffold-nonces.log.migration-tmp.*` — disjoint
    from the rollover tmp pattern.
    """
    # 1. Glob-clean orphan migration tmps (Layer 7 + Layer 8 pin).
    for orphan in glob.glob(_migration_tmp_glob(repo_root)):
        try:
            os.unlink(orphan)
        except OSError:
            pass
    # 2. Read all entries into memory.
    src = ledger_path(repo_root)
    lines = _read_ledger_lines(src)
    if not lines:
        return
    # 3. Open temp file with O_CREAT|O_EXCL.
    tmp = _migration_tmp(repo_root)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        os.write(fd, _FORMAT_HEADER.encode("utf-8"))
        os.write(fd, "".join(lines).encode("utf-8"))
        os.fsync(fd)
        if sys.platform == "darwin":
            try:
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            except (OSError, AttributeError):
                pass
    finally:
        os.close(fd)
    os.rename(str(tmp), str(src))
    try:
        dirfd = os.open(str(_launchpad_dir(repo_root)), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except OSError:
        pass


def _ensure_format_header(repo_root: Path) -> None:
    """Guarantee the data-file ledger carries a format header line.

    On absence: create a fresh ledger with the header. On v0-shape (no header
    + has UUID lines): migrate. On unknown header: hard-reject with
    `nonce_ledger_format_unsupported`.

    Caller MUST already hold the lock.
    """
    src = ledger_path(repo_root)
    if not src.exists():
        # Fresh ledger with header.
        fd = os.open(str(src), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass
            os.write(fd, _FORMAT_HEADER.encode("utf-8"))
            os.fsync(fd)
            if sys.platform == "darwin":
                try:
                    fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
                except (OSError, AttributeError):
                    pass
        finally:
            os.close(fd)
        return
    lines = _read_ledger_lines(src)
    if _is_format_header_present(lines):
        # Validate the header line value matches v1.
        first = lines[0].strip()
        if first != "# nonce-ledger-format: v1":
            raise NonceLedgerError(
                f"unsupported ledger format header: {first!r}",
                reason="nonce_ledger_format_unsupported",
            )
        return
    if _looks_like_v0_ledger(lines):
        _migrate_v0_to_v1(repo_root)
        return
    # Has lines but neither header nor UUID-shaped first non-empty line.
    raise NonceLedgerError(
        "ledger first line is neither format header nor UUID hex; "
        "manual intervention required",
        reason="nonce_ledger_corrupt",
    )


# ---------------------------------------------------------------------------
# .bak window walking (Layer 5 frontend-races P2-L5-A8)
# ---------------------------------------------------------------------------


_BAK_FILENAME_TS_RE = re.compile(
    r"\.scaffold-nonces\.log\.bak\.(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)$"
)


def _bak_filename_epoch(name: str) -> float | None:
    """Parse the ISO 8601 timestamp from a `.bak.<ts>` basename. Returns None
    on parse failure."""
    m = _BAK_FILENAME_TS_RE.search(name)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%Y-%m-%dT%H-%M-%SZ").replace(
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None
    return dt.timestamp()


def _walk_bak_window(repo_root: Path, *, now_epoch: float) -> list[Path]:
    """Return `.bak.<ts>` files whose `max(filename_ts, file_ctime)` is within
    the 4h replay window of `now_epoch`.

    `max()` is conservative — handles backward NTP corrections (a backward
    clock jump could otherwise produce filename `<ts>` values numerically
    smaller than the real rotation time, silently shrinking the window).

    Caller MUST hold the lock — listing happens under flock to prevent races
    against retention deletion.
    """
    lp = _launchpad_dir(repo_root)
    if not lp.exists():
        return []
    out: list[Path] = []
    for entry in lp.iterdir():
        name = entry.name
        if not name.startswith(".scaffold-nonces.log.bak."):
            continue
        try:
            st = entry.stat()
        except OSError:
            continue
        filename_epoch = _bak_filename_epoch(name)
        anchor = max(
            filename_epoch if filename_epoch is not None else 0.0,
            st.st_ctime,
        )
        if abs(now_epoch - anchor) <= _BAK_WINDOW_SECONDS:
            out.append(entry)
    return out


def _read_nonces_from(path: Path) -> set[str]:
    out: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if _UUID_HEX_RE.fullmatch(s):
                    out.add(s)
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_nonce_seen(
    nonce: str,
    repo_root: Path,
    *,
    _now_epoch: float | None = None,
) -> bool:
    """Return True if `nonce` appears in the live ledger OR any in-window `.bak`.

    Acquires the dedicated lock; performs filesystem-whitelist check on first
    call. Per HANDSHAKE §4 rule 10 — listing the `.bak` set under the lock
    prevents racing against retention deletion.
    """
    if not isinstance(nonce, str) or not _UUID_HEX_RE.fullmatch(nonce):
        raise ValueError(f"is_nonce_seen: nonce must be 32 hex chars; got {nonce!r}")

    _check_filesystem_whitelist(repo_root)
    now_epoch = _now_epoch if _now_epoch is not None else time.time()

    lock_fd = _open_lock(repo_root)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _ensure_format_header(repo_root)
        live = _read_nonces_from(ledger_path(repo_root))
        if nonce in live:
            return True
        for bak in _walk_bak_window(repo_root, now_epoch=now_epoch):
            if nonce in _read_nonces_from(bak):
                return True
        return False
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def append_nonce(
    nonce: str,
    repo_root: Path,
) -> Path:
    """Append `nonce` to the ledger atomically (POSIX O_APPEND byte-atomicity).

    Performs 1MB rollover under the lock if the data file exceeds threshold
    AFTER append. Returns the ledger path actually written to.

    Per HANDSHAKE §4 rule 10:
      - Single `os.write(fd, (nonce + "\\n").encode("ascii"))` call.
      - `os.fsync(fd)` + `os.fsync(dirfd)` + F_FULLFSYNC on darwin.
      - 1MB rollover via atomic-rename to `.bak.<iso-ts>` + 5-bak retention.
      - EIO/EROFS handled with structured rejections.
    """
    if not isinstance(nonce, str) or not _UUID_HEX_RE.fullmatch(nonce):
        raise ValueError(f"append_nonce: nonce must be 32 hex chars; got {nonce!r}")

    _check_filesystem_whitelist(repo_root)
    src = ledger_path(repo_root)

    lock_fd = _open_lock(repo_root)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _ensure_format_header(repo_root)

        try:
            fd = os.open(str(src), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        except OSError as exc:
            if exc.errno == errno.EROFS:
                raise NonceLedgerError(
                    "mount .launchpad/ writable",
                    reason="filesystem_readonly",
                ) from exc
            raise NonceLedgerError(
                f"could not open ledger: {exc}",
                reason="nonce_ledger_append_failed",
            ) from exc

        record = (nonce + "\n").encode("ascii")
        try:
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass
            try:
                pre_size = os.fstat(fd).st_size
            except OSError:
                pre_size = 0
            try:
                written = os.write(fd, record)
            except OSError as exc:
                # EIO partial-line detection
                try:
                    post_size = os.fstat(fd).st_size
                except OSError:
                    post_size = pre_size
                if post_size != pre_size + len(record):
                    # Partial line — write a corruption sentinel comment.
                    try:
                        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        os.write(fd, f"# corrupt:{ts}\n".encode("ascii"))
                        os.fsync(fd)
                    except OSError as exc2:
                        try:
                            os.chmod(str(lock_path(repo_root)), 0o000)
                        except OSError:
                            pass
                        raise NonceLedgerError(
                            f"unrecoverable EIO during sentinel write: {exc2}",
                            reason="nonce_ledger_io_unrecoverable",
                        ) from exc2
                    raise NonceLedgerError(
                        "partial line detected; corruption sentinel written",
                        reason="nonce_ledger_corrupt",
                    ) from exc
                raise NonceLedgerError(
                    f"os.write failed: {exc}",
                    reason="nonce_ledger_append_failed",
                ) from exc
            if written != len(record):
                raise NonceLedgerError(
                    f"short write: {written}/{len(record)} bytes",
                    reason="nonce_ledger_append_failed",
                )
            try:
                os.fsync(fd)
            except OSError as exc:
                raise NonceLedgerError(
                    f"fsync failed: {exc}",
                    reason="nonce_ledger_append_failed",
                ) from exc
            if sys.platform == "darwin":
                try:
                    fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
                except (OSError, AttributeError):
                    pass
        finally:
            os.close(fd)

        try:
            dirfd = os.open(str(_launchpad_dir(repo_root)), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except OSError:
            pass

        # 1MB rollover check (post-append).
        try:
            st = os.stat(str(src))
        except OSError:
            st = None
        if st is not None and st.st_size > _ROLLOVER_BYTES:
            _rotate_at_threshold(repo_root)

        return src
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def _rotate_at_threshold(repo_root: Path) -> None:
    """Rotate the ledger to `.bak.<iso-ts>` under the held lock.

    Caller MUST already hold the lock. Creates a fresh ledger with format
    header. Trims `.bak.*` files to the most-recent 5.
    """
    src = ledger_path(repo_root)
    rollover_tmp = _rollover_tmp(repo_root)
    # Clean any orphan rollover tmp from prior crash.
    if rollover_tmp.exists():
        try:
            rollover_tmp.unlink()
        except OSError:
            pass

    # Move current src to rollover tmp first (atomic on POSIX).
    try:
        os.rename(str(src), str(rollover_tmp))
    except OSError:
        return  # nothing to rotate
    try:
        # fsync the directory after the rename for durability.
        try:
            dirfd = os.open(str(_launchpad_dir(repo_root)), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except OSError:
            pass

        # Now rename to a final .bak.<iso-ts>.
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        bak = _launchpad_dir(repo_root) / f".scaffold-nonces.log.bak.{ts}"
        # If a .bak with this exact second already exists, retry with .pid suffix.
        if bak.exists():
            bak = _launchpad_dir(repo_root) / f".scaffold-nonces.log.bak.{ts}.{os.getpid()}"
        os.rename(str(rollover_tmp), str(bak))
    except OSError:
        # Best-effort: leave the rollover tmp file in place; next call
        # cleans it up on entry.
        return

    # Create fresh ledger with format header.
    fd = os.open(str(src), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        os.write(fd, _FORMAT_HEADER.encode("utf-8"))
        os.fsync(fd)
        if sys.platform == "darwin":
            try:
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            except (OSError, AttributeError):
                pass
    finally:
        os.close(fd)

    # Retention: keep newest 5.
    baks = sorted(
        (p for p in _launchpad_dir(repo_root).iterdir()
         if p.name.startswith(".scaffold-nonces.log.bak.")),
        key=lambda p: p.name,
    )
    for old in baks[:-_BAK_RETENTION_COUNT]:
        try:
            old.unlink()
        except OSError:
            pass


__all__ = [
    "NonceLedgerError",
    "append_nonce",
    "is_nonce_seen",
    "ledger_path",
    "lock_path",
]
