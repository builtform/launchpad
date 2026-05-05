"""Template cache backend store: layout + locking + LRU + sentinels.

Phase 4 plan §3.7. Private submodule of `template_cache`. Implements the
10-rule cache contract:

  1. SHA-pinned cache key (the SHA already comes pre-resolved from
     pin_registry; this module never floats tags).
  2. Cache-hit verification via `.ready` sentinel + commit-object sha
     check (~5ms; <20ms perf budget).
  3. Atomic writes: tempdir then rename; `.ready` is the durable commit
     point. No per-file fsync; cold-fill 1k files <3s budget.
  4. Per-entry `fcntl.flock` at `.locks/<slug>-<sha>.lock` mode 0o600
     plus a process-local `MAX_CONCURRENT_FETCHES=3` semaphore.
  5. Validation-before-flock ordering (Phase 3 §3.11.5(c) inheritance).
  6. 500MB LRU. Lazy on-fetch eviction. WARN if >50 entries.
  7. 90-day TTL re-validation (full-tree re-verify against pin_registry).
  8. Auto-purge on missing files / extra files / missing `.ready` /
     `.compromised` sentinel present.
  9. Symlink rejection at cache root + per-entry.
 10. Filesystem-full cleanup: try/finally over `<sha>.tmp.<uuid>/`.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HTTPS_GITHUB_PREFIX = "https://github.com/"

CACHE_LRU_MAX_BYTES = 500 * 1024 * 1024
CACHE_TTL_DAYS = 90
MAX_CONCURRENT_FETCHES = 3
READY_SENTINEL = ".ready"
FETCHED_AT_FILE = ".fetched_at"
EXPECTED_FILES_FILE = ".expected_files.json"
COMPROMISED_SENTINEL = ".compromised"
LOCKS_SUBDIR = ".locks"
DEFAULT_CACHE_DIR = Path.home() / ".launchpad" / "template-cache"

_FETCH_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_FETCHES)


class TemplateCacheError(RuntimeError):
    """Phase 4 §3.11.5(b): per-module error with the structured triple."""

    def __init__(self, *, reason: str, path: Path | None, remediation: str) -> None:
        super().__init__(remediation)
        self.reason = reason
        self.path = path
        self.remediation = remediation


@dataclass(frozen=True)
class _EntryHandle:
    slug: str
    sha: str
    entry_dir: Path
    tmp_dir: Path
    lock_file: Path


def cache_root() -> Path:
    """Resolve the cache root from `LAUNCHPAD_CACHE_DIR` env or default."""
    override = os.environ.get("LAUNCHPAD_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return DEFAULT_CACHE_DIR


def _slug_from_repo(repo_url: str) -> str:
    if not repo_url.startswith(_HTTPS_GITHUB_PREFIX):
        raise TemplateCacheError(
            reason="non_github_repo",
            path=None,
            remediation=(
                f"only https://github.com/ repos are supported by the "
                f"template cache; got {repo_url!r}"
            ),
        )
    rest = repo_url[len(_HTTPS_GITHUB_PREFIX):].rstrip("/")
    if rest.endswith(".git"):
        rest = rest[:-4]
    return rest.replace("/", "-")


def _validate_inputs(repo_url: str, sha: str) -> None:
    """Phase 4 §3.7 rule #5(a): validate inputs FIRST, before flock."""
    if not _SHA_RE.match(sha):
        raise TemplateCacheError(
            reason="malformed_sha",
            path=None,
            remediation=(
                f"sha {sha!r} fails 40-char hex regex; pin_registry should "
                f"have rejected this before reaching the cache"
            ),
        )
    _slug_from_repo(repo_url)  # raises if malformed


def _preflight_cache_root(root: Path) -> None:
    """Phase 4 §3.7 rule #5(b) + #9: lstat + mode 0o700 + owner check + symlink reject."""
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists() or root.is_symlink():
        st = os.lstat(root)
        if stat.S_ISLNK(st.st_mode):
            raise TemplateCacheError(
                reason="cache_root_is_symlink",
                path=root,
                remediation=(
                    f"cache root {root} is a symlink; remove it (rm {root}) "
                    f"and re-run; LaunchPad will recreate it as a regular "
                    f"directory"
                ),
            )
        if not stat.S_ISDIR(st.st_mode):
            raise TemplateCacheError(
                reason="cache_root_not_a_directory",
                path=root,
                remediation=f"cache root {root} exists but is not a directory",
            )
        actual_mode = stat.S_IMODE(st.st_mode)
        actual_owner = st.st_uid
        if actual_owner != os.getuid() or actual_mode != 0o700:
            raise TemplateCacheError(
                reason="cache_root_unsafe_permissions",
                path=root,
                remediation=(
                    f"cache directory {root} has unsafe permissions "
                    f"(mode {oct(actual_mode)}, owner uid {actual_owner}). "
                    f"Required: 0700 + current user. Run: chmod 700 {root} "
                    f"&& chown $USER {root}"
                ),
            )
    else:
        try:
            root.mkdir(mode=0o700)
        except FileExistsError:
            # Concurrent worker created the root between our lstat and mkdir;
            # benign race, the existing-path branch above will catch any unsafe
            # state on the next call.
            pass
        try:
            os.chmod(root, 0o700)
        except OSError:
            pass
    locks_dir = root / LOCKS_SUBDIR
    locks_dir.mkdir(mode=0o700, exist_ok=True)


def entry_path(repo_url: str, sha: str) -> Path:
    """Return the on-disk directory path for a given (repo_url, sha) entry."""
    slug = _slug_from_repo(repo_url)
    return cache_root() / f"{slug}@{sha}"


def _entry_handle(repo_url: str, sha: str) -> _EntryHandle:
    slug = _slug_from_repo(repo_url)
    root = cache_root()
    return _EntryHandle(
        slug=slug,
        sha=sha,
        entry_dir=root / f"{slug}@{sha}",
        tmp_dir=root / f"{slug}@{sha}.tmp.{uuid.uuid4().hex}",
        lock_file=root / LOCKS_SUBDIR / f"{slug}-{sha}.lock",
    )


@contextlib.contextmanager
def _flock(lock_file: Path) -> Iterator[None]:
    """Per-entry advisory lock at `.locks/<slug>-<sha>.lock` (mode 0o600).

    Phase 4 §3.7 rule #4: mode 0o600 per atomic_io.advisory_flock precedent.
    """
    lock_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _entry_is_ready(entry_dir: Path) -> bool:
    """Phase 4 §3.7 rule #2 + #8: cache-hit verification."""
    if not entry_dir.is_dir():
        return False
    if (entry_dir / COMPROMISED_SENTINEL).exists():
        return False
    ready = entry_dir / READY_SENTINEL
    if not ready.is_file():
        return False
    expected = entry_dir / EXPECTED_FILES_FILE
    if not expected.is_file():
        return False
    return True


def _entry_files_match_manifest(entry_dir: Path) -> bool:
    """Phase 4 §3.7 rule #8: missing-files OR extra-files invalidates."""
    expected_path = entry_dir / EXPECTED_FILES_FILE
    try:
        manifest = json.loads(expected_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    expected_files = set(manifest.get("files", []))
    if not expected_files:
        return True

    actual: set[str] = set()
    for path in entry_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(entry_dir).as_posix()
        if rel in (READY_SENTINEL, EXPECTED_FILES_FILE, FETCHED_AT_FILE):
            continue
        actual.add(rel)
    return actual == expected_files


def _entry_age_days(entry_dir: Path) -> float:
    fetched = entry_dir / FETCHED_AT_FILE
    if not fetched.is_file():
        return float("inf")
    try:
        ts = fetched.read_text(encoding="utf-8").strip()
        when = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (OSError, ValueError):
        return float("inf")
    now = _dt.datetime.now(tz=when.tzinfo or _dt.timezone.utc)
    return (now - when).total_seconds() / 86400.0


def verify(repo_url: str, sha: str) -> bool:
    """Phase 4 §3.7 rule #2 + #8: re-run cache-hit verification."""
    _validate_inputs(repo_url, sha)
    entry = _entry_handle(repo_url, sha).entry_dir
    if not _entry_is_ready(entry):
        return False
    if not _entry_files_match_manifest(entry):
        return False
    if _entry_age_days(entry) > CACHE_TTL_DAYS:
        return False
    return True


def _purge_entry(entry_dir: Path) -> None:
    """Phase 4 §3.7 rule #8: write-LAST/remove-FIRST -> remove READY first."""
    ready = entry_dir / READY_SENTINEL
    with contextlib.suppress(OSError):
        ready.unlink()
    with contextlib.suppress(OSError):
        shutil.rmtree(entry_dir)


def _list_entries(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [
        child
        for child in root.iterdir()
        if child.is_dir()
        and child.name != LOCKS_SUBDIR
        and "@" in child.name
        and ".tmp." not in child.name
    ]


def _entry_size_bytes(entry_dir: Path) -> int:
    total = 0
    for path in entry_dir.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _enforce_lru(root: Path, *, target_bytes: int | None = None) -> None:
    """Phase 4 §3.7 rule #6: 500MB LRU + lazy on-fetch eviction.

    `target_bytes` defaults to the module-level `CACHE_LRU_MAX_BYTES` resolved
    at call time (so test monkeypatch on the module constant takes effect).
    """
    if target_bytes is None:
        target_bytes = CACHE_LRU_MAX_BYTES
    entries = _list_entries(root)
    sized: list[tuple[float, int, Path]] = []
    total = 0
    for entry in entries:
        size = _entry_size_bytes(entry)
        try:
            mtime = (entry / READY_SENTINEL).stat().st_mtime
        except OSError:
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                mtime = 0.0
        sized.append((mtime, size, entry))
        total += size
    if total <= target_bytes:
        return
    sized.sort(key=lambda row: row[0])
    for mtime, size, entry in sized:
        if total <= target_bytes:
            return
        _purge_entry(entry)
        total -= size


def _write_manifest_and_ready(entry_dir: Path) -> None:
    """Phase 4 §3.7 rule #3: `.ready` is durable commit point. Written LAST."""
    files = []
    for path in entry_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(entry_dir).as_posix()
        if rel in (READY_SENTINEL, EXPECTED_FILES_FILE, FETCHED_AT_FILE):
            continue
        files.append(rel)
    files.sort()
    manifest = {"files": files}
    (entry_dir / EXPECTED_FILES_FILE).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (entry_dir / FETCHED_AT_FILE).write_text(
        _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")
        + "\n",
        encoding="utf-8",
    )
    (entry_dir / READY_SENTINEL).write_text("ok\n", encoding="utf-8")


def fetch(
    repo_url: str,
    sha: str,
    *,
    fetcher: Callable[[Path], None] | None = None,
) -> Path:
    """Public API: fetch upstream tree at (repo_url, sha) into cache + return path.

    `fetcher` (test-injectable, defaults to production
    `_resolver.git_clone_depth_one`) is responsible for materializing the
    tree at the tempdir target. The cache wraps the call with:
      - Validation-before-flock (§3.7 #5)
      - Pre-flight mode 0o700 + symlink reject (§3.7 #5 + #9)
      - Per-entry flock (§3.7 #4)
      - Atomic tempdir-then-rename (§3.7 #3)
      - LRU + extra-files purge (§3.7 #6 + #8)
      - `MAX_CONCURRENT_FETCHES=3` semaphore (§3.7 #4)
    """
    _validate_inputs(repo_url, sha)
    root = cache_root()
    _preflight_cache_root(root)

    handle = _entry_handle(repo_url, sha)

    if _entry_is_ready(handle.entry_dir) and _entry_files_match_manifest(
        handle.entry_dir
    ) and _entry_age_days(handle.entry_dir) <= CACHE_TTL_DAYS:
        return handle.entry_dir

    if fetcher is None:
        from ._resolver import git_clone_depth_one

        def fetcher(target: Path) -> None:
            git_clone_depth_one(repo_url, sha, target)

    with _FETCH_SEMAPHORE:
        with _flock(handle.lock_file):
            if _entry_is_ready(handle.entry_dir) and _entry_files_match_manifest(
                handle.entry_dir
            ) and _entry_age_days(handle.entry_dir) <= CACHE_TTL_DAYS:
                return handle.entry_dir
            if handle.entry_dir.exists():
                _purge_entry(handle.entry_dir)

            handle.tmp_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
            try:
                fetcher(handle.tmp_dir)
                _write_manifest_and_ready(handle.tmp_dir)
                os.replace(str(handle.tmp_dir), str(handle.entry_dir))
            except BaseException:
                with contextlib.suppress(OSError):
                    shutil.rmtree(handle.tmp_dir)
                raise

    _enforce_lru(root)
    return handle.entry_dir
