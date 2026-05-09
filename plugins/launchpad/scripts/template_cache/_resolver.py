"""Template cache resolver: dual-resolved SHAs + git_clone_depth_one fetcher.

Phase 4 plan §3.2 + §3.8. Private submodule of `template_cache`. Adapters do
NOT import resolver directly; they go through `template_cache.fetch()`. Tests
inject a stub via the `fetcher=` kwarg or by overriding
`template_cache._resolver.resolve_sha`.

Production behavior:
  - `resolve_sha(repo_url, tag)`: dual-resolution via `git ls-remote` + GitHub
    REST. Both must return the same commit-object SHA. Mismatch raises
    `ResolverError(reason='dual_resolution_mismatch')`.
  - `git_clone_depth_one(repo_url, sha, target)`: depth-1 clone + checkout
    via `safe_run_long`, materializing the upstream tree at `target`. Used
    as the production default fetcher.

Test behavior: tests override `resolve_sha` via monkeypatch in conftest, and
inject custom fetchers (synthesizing minimal trees) directly through the
`fetcher=` parameter on `fetch()`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from safe_run import safe_run, safe_run_long

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HTTPS_GITHUB_PREFIX = "https://github.com/"


class AttestationStatus(StrEnum):
    UNSIGNED = "unsigned"
    VERIFIED = "verified"


class ResolverError(RuntimeError):
    """Phase 4 §3.11.5(b): structured triple for engine-boundary bridging.

    v2.1 Codex PR #50 P0 (D9.1) reason taxonomy reference: the resolver
    itself never produces `disallowed_entry_in_fetched_template`; that
    taxonomy code is owned by `_store._walk_for_disallowed_entries` and
    surfaces via `TemplateCacheError` after the fetcher returns. Documented
    here so downstream callers grep this module for "disallowed_entry_*"
    reasons and find the intentional split.
    """

    def __init__(self, *, reason: str, path: Path | None, remediation: str) -> None:
        super().__init__(remediation)
        self.reason = reason
        self.path = path
        self.remediation = remediation


@dataclass(frozen=True)
class ResolvedTag:
    sha: str
    repo_url: str
    tag: str
    attestation: AttestationStatus


def _split_repo(repo_url: str) -> tuple[str, str]:
    if not repo_url.startswith(_HTTPS_GITHUB_PREFIX):
        raise ResolverError(
            reason="non_github_repo",
            path=None,
            remediation=(
                f"only https://github.com/ repos are supported by the "
                f"template cache resolver; got {repo_url!r}"
            ),
        )
    rest = repo_url[len(_HTTPS_GITHUB_PREFIX) :].rstrip("/")
    if rest.endswith(".git"):
        rest = rest[:-4]
    parts = rest.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ResolverError(
            reason="malformed_repo_url",
            path=None,
            remediation=(f"expected https://github.com/owner/repo; got {repo_url!r}"),
        )
    return parts[0], parts[1]


def resolve_sha(repo_url: str, tag: str) -> ResolvedTag:
    """Dual-resolve `tag` to a commit SHA via git ls-remote + GitHub REST.

    The cache uses pre-resolved SHAs from `pin_registry.py` at runtime; this
    helper exists for tests + future tag-drift detection. It is intentionally
    NOT called inside `fetch()`: the v2.1 cache only ever sees pinned SHAs.
    """
    owner, repo = _split_repo(repo_url)

    rc1, sha_via_ls = _git_ls_remote_resolve(repo_url, tag)
    if rc1 != 0 or not _SHA_RE.match(sha_via_ls):
        raise ResolverError(
            reason="ls_remote_failed",
            path=None,
            remediation=(
                f"git ls-remote {repo_url} returned rc={rc1} sha={sha_via_ls!r}"
            ),
        )

    rc2, sha_via_rest = _gh_rest_resolve(owner, repo, tag)
    if rc2 != 0 or not _SHA_RE.match(sha_via_rest):
        raise ResolverError(
            reason="gh_rest_failed",
            path=None,
            remediation=(
                f"gh api git/refs/tags/{tag} returned rc={rc2} sha={sha_via_rest!r}"
            ),
        )

    if sha_via_ls != sha_via_rest:
        raise ResolverError(
            reason="dual_resolution_mismatch",
            path=None,
            remediation=(
                f"git ls-remote returned {sha_via_ls!r} but GitHub REST "
                f"returned {sha_via_rest!r} for {repo_url}@{tag}; abort and "
                f"investigate before recording in pin_registry"
            ),
        )

    return ResolvedTag(
        sha=sha_via_ls,
        repo_url=repo_url,
        tag=tag,
        attestation=_check_attestation(owner, repo, sha_via_ls),
    )


def _git_ls_remote_resolve(repo_url: str, tag: str) -> tuple[int, str]:
    try:
        result = safe_run(
            ["git", "ls-remote", repo_url, f"refs/tags/{tag}^{{}}"],
            cwd=Path.cwd(),
            timeout=30.0,
        )
    except Exception:
        return 1, ""
    line = result.stdout.decode("utf-8", errors="replace").strip().splitlines()
    if not line:
        try:
            result2 = safe_run(
                ["git", "ls-remote", repo_url, f"refs/tags/{tag}"],
                cwd=Path.cwd(),
                timeout=30.0,
            )
        except Exception:
            return 1, ""
        line = result2.stdout.decode("utf-8", errors="replace").strip().splitlines()
        if not line:
            return 1, ""
    sha = line[0].split("\t", 1)[0].strip()
    return 0, sha


def _gh_rest_resolve(owner: str, repo: str, tag: str) -> tuple[int, str]:
    try:
        result = safe_run(
            ["gh", "api", f"repos/{owner}/{repo}/git/refs/tags/{tag}"],
            cwd=Path.cwd(),
            timeout=30.0,
        )
    except Exception:
        return 1, ""
    body = result.stdout.decode("utf-8", errors="replace")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return 1, ""
    obj = payload.get("object")
    if not isinstance(obj, dict):
        return 1, ""
    obj_sha = obj.get("sha", "")
    obj_type = obj.get("type")
    if obj_type == "tag":
        rc, deref = _gh_rest_deref_annotated(owner, repo, obj_sha)
        return rc, deref
    return 0, obj_sha


def _gh_rest_deref_annotated(owner: str, repo: str, tag_sha: str) -> tuple[int, str]:
    try:
        result = safe_run(
            ["gh", "api", f"repos/{owner}/{repo}/git/tags/{tag_sha}"],
            cwd=Path.cwd(),
            timeout=30.0,
        )
    except Exception:
        return 1, ""
    body = result.stdout.decode("utf-8", errors="replace")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return 1, ""
    obj = payload.get("object")
    if not isinstance(obj, dict):
        return 1, ""
    return 0, obj.get("sha", "")


def _check_attestation(owner: str, repo: str, sha: str) -> AttestationStatus:
    try:
        result = safe_run(
            ["gh", "api", f"repos/{owner}/{repo}/attestations/sha:{sha}"],
            cwd=Path.cwd(),
            timeout=30.0,
        )
    except Exception:
        return AttestationStatus.UNSIGNED
    try:
        payload = json.loads(
            result.stdout.decode("utf-8", errors="replace").splitlines()[0]
        )
    except (json.JSONDecodeError, IndexError):
        return AttestationStatus.UNSIGNED
    attestations = payload.get("attestations") if isinstance(payload, dict) else None
    if isinstance(attestations, list) and len(attestations) > 0:
        return AttestationStatus.VERIFIED
    return AttestationStatus.UNSIGNED


def git_clone_depth_one(repo_url: str, sha: str, target: Path) -> Literal[True]:
    """Production fetcher: depth-1 clone + checkout `sha` into `target`.

    Phase 4 plan §3.8: invoked via `safe_run_long` so SIGINT propagates
    through the process group with the ladder cleanup. Caller is responsible
    for ensuring `target` is empty + on the same filesystem as the cache.
    """
    if not _SHA_RE.match(sha):
        raise ResolverError(
            reason="malformed_sha",
            path=target,
            remediation=f"sha {sha!r} fails 40-char hex regex",
        )
    target.mkdir(parents=True, exist_ok=True)

    def _run_or_raise(argv: list[str], cwd: Path, step: str) -> None:
        # Codex PR #50 P1: safe_run_long returns CompletedProcess WITHOUT
        # raising on non-zero. Without this guard, a failed git operation
        # would let _store.fetch() mark the cache entry as ready over an
        # empty/partial scaffold.
        result = safe_run_long(argv, cwd=cwd)
        if result.returncode != 0:
            tail = (result.stderr or b"").decode("utf-8", errors="replace")[-512:]
            raise ResolverError(
                reason=f"git_{step}_failed",
                path=target,
                remediation=(
                    f"git {step} exited {result.returncode} for "
                    f"{repo_url}@{sha[:8]}: {tail.strip() or '(no stderr)'}"
                ),
            )

    _run_or_raise(
        ["git", "clone", "--depth", "1", "--no-tags", repo_url, str(target)],
        cwd=target.parent,
        step="clone",
    )
    _run_or_raise(
        ["git", "fetch", "--depth", "1", "origin", sha],
        cwd=target,
        step="fetch",
    )
    _run_or_raise(
        ["git", "checkout", "--detach", sha],
        cwd=target,
        step="checkout",
    )
    return True
