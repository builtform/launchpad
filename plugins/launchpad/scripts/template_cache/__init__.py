"""Template cache: SHA-pinned upstream tree storage with atomic writes,
per-entry locking, 500MB LRU, and 90-day TTL.

Phase 4 plan §3.7. Public API:

  - `fetch(repo_url, sha, *, fetcher=None, walk_scope=None) -> Path`:
    returns path to a cached upstream tree at `sha`. If the entry is
    missing, calls `fetcher(target)` to populate it (production default:
    depth-1 git clone via safe_run_long). Cache hits verify the durable
    `.ready` sentinel + commit-object sha integrity in <20ms before
    returning. `walk_scope` (relative POSIX subpath) restricts the
    D9.1 disallowed-entry walk to the subtree the caller will copy
    out (v2.1.4 BL-328); pass None for whole-tree walks.

  - `verify(repo_url, sha, *, walk_scope=None) -> bool`: re-runs the
    cache-hit verification on an already-resolved entry. Returns False
    for missing / stale / compromised entries.

Cache root resolves to `~/.launchpad/template-cache/` by default. Tests +
sandboxed environments override via the `LAUNCHPAD_CACHE_DIR` env var
(documented for v2.1 in the lint-rules doc, not in user-facing docs per
plan §8 out-of-scope).

Errors raised by both functions inherit from `TemplateCacheError`, carry the
structured triple `.reason / .path / .remediation` documented in Phase 4
§3.11.5(b), and bridge cleanly via `bridge_to_scaffold_error` at the engine
boundary.
"""

from __future__ import annotations

from ._resolver import (
    AttestationStatus,
    ResolverError,
    git_clone_depth_one,
    resolve_sha,
)
from ._store import (
    CACHE_LRU_MAX_BYTES,
    CACHE_TTL_DAYS,
    MAX_CONCURRENT_FETCHES,
    READY_SENTINEL,
    TemplateCacheError,
    cache_root,
    entry_path,
    fetch,
    verify,
)

__all__ = [
    "AttestationStatus",
    "CACHE_LRU_MAX_BYTES",
    "CACHE_TTL_DAYS",
    "MAX_CONCURRENT_FETCHES",
    "READY_SENTINEL",
    "ResolverError",
    "TemplateCacheError",
    "cache_root",
    "entry_path",
    "fetch",
    "git_clone_depth_one",
    "resolve_sha",
    "verify",
]
