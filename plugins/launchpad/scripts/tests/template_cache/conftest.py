"""Shared fixtures for template_cache tests (Phase 4 plan §3.7).

DA4 = c artifacts:
  - `cache_root_tmp` redirects the cache to `tmp_path` via the
    `LAUNCHPAD_CACHE_DIR` env override.
  - `synthetic_fetcher` returns a fetcher callable that materializes a small
    deterministic tree at the tempdir target without touching the network.
  - `prepopulate_entry` builds a cache entry directly (skipping fetch()) so
    tests can assert on cache-hit behavior without spinning a fetch.

Also reusable from Slice C adapter tests (~50 tests amortized over Slice B's
42-test budget).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from template_cache import _store


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


@pytest.fixture
def synthetic_fetcher() -> Callable[[dict[str, bytes] | None], Callable[[Path], None]]:
    def _make(content: dict[str, bytes] | None = None) -> Callable[[Path], None]:
        files = content or {
            "package.json": b'{"name": "stub", "version": "0.0.0"}\n',
            "README.md": b"# stub upstream\n",
            "src/index.ts": b'export const stub = true;\n',
        }

        def fetcher(target: Path) -> None:
            for rel, body in files.items():
                p = target / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(body)

        return fetcher

    return _make


@pytest.fixture
def prepopulate_entry(cache_root_tmp: Path) -> Callable[..., Path]:
    """Build a cache entry directly (bypassing fetch()) for cache-hit tests."""

    def _build(
        repo_url: str,
        sha: str,
        files: dict[str, bytes] | None = None,
        *,
        with_ready: bool = True,
        compromised: bool = False,
    ) -> Path:
        cache_root_tmp.mkdir(mode=0o700, parents=True, exist_ok=True)
        (cache_root_tmp / _store.LOCKS_SUBDIR).mkdir(
            mode=0o700, parents=True, exist_ok=True
        )
        slug = _store._slug_from_repo(repo_url)
        entry = cache_root_tmp / f"{slug}@{sha}"
        entry.mkdir(mode=0o700, parents=True, exist_ok=True)

        body = files or {"hello.txt": b"hi\n"}
        for rel, content in body.items():
            p = entry / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)

        manifest_files = sorted(body.keys())
        (entry / _store.EXPECTED_FILES_FILE).write_text(
            json.dumps({"files": manifest_files}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (entry / _store.FETCHED_AT_FILE).write_text(
            "2026-05-05T00:00:00Z\n", encoding="utf-8"
        )
        if with_ready:
            (entry / _store.READY_SENTINEL).write_text("ok\n", encoding="utf-8")
        if compromised:
            (entry / _store.COMPROMISED_SENTINEL).write_text(
                "see GHSA-XXXX\n", encoding="utf-8"
            )
        return entry

    return _build
