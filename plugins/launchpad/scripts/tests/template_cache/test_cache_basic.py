"""Template cache basic + perf tests (Phase 4 plan §3.7 rules 1-3, 5b, 7).

Covers cache layout, fetch / cache-hit, atomic write, .ready sentinel,
manifest write, TTL, cache-hit perf budget, cold-fill perf budget. Marked
`slow` per DA6 lock — requires real disk + filesystem walk timing.
"""
from __future__ import annotations

import datetime as _dt
import os
import stat
import time
from pathlib import Path

import pytest

from template_cache import (
    CACHE_TTL_DAYS,
    READY_SENTINEL,
    TemplateCacheError,
    _store,
    cache_root,
    entry_path,
    fetch,
    verify,
)

pytestmark = pytest.mark.slow

REPO = "https://github.com/example-org/example-repo"
SHA = "a" * 40


def test_cache_root_uses_env_override(cache_root_tmp: Path):
    assert cache_root() == cache_root_tmp


def test_cache_root_default_is_under_home_directory(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LAUNCHPAD_CACHE_DIR", raising=False)
    root = cache_root()
    assert root == Path.home() / ".launchpad" / "template-cache"


def test_fetch_creates_entry_with_ready_sentinel(
    cache_root_tmp, synthetic_fetcher
):
    target = fetch(REPO, SHA, fetcher=synthetic_fetcher())
    assert target.is_dir()
    assert (target / READY_SENTINEL).is_file()
    assert (target / "package.json").is_file()


def test_fetch_writes_expected_files_manifest(
    cache_root_tmp, synthetic_fetcher
):
    target = fetch(REPO, SHA, fetcher=synthetic_fetcher())
    import json

    manifest = json.loads(
        (target / _store.EXPECTED_FILES_FILE).read_text(encoding="utf-8")
    )
    files = set(manifest["files"])
    assert "package.json" in files
    assert "README.md" in files
    assert "src/index.ts" in files
    assert READY_SENTINEL not in files


def test_fetch_returns_existing_entry_on_cache_hit(
    cache_root_tmp, synthetic_fetcher
):
    fetcher = synthetic_fetcher()
    first = fetch(REPO, SHA, fetcher=fetcher)
    call_count = {"n": 0}

    def fetcher_should_not_run(target: Path) -> None:
        call_count["n"] += 1

    second = fetch(REPO, SHA, fetcher=fetcher_should_not_run)
    assert first == second
    assert call_count["n"] == 0


def test_fetch_raises_on_malformed_sha(cache_root_tmp, synthetic_fetcher):
    with pytest.raises(TemplateCacheError) as exc:
        fetch(REPO, "not-a-sha", fetcher=synthetic_fetcher())
    assert exc.value.reason == "malformed_sha"


def test_fetch_raises_on_non_github_url(cache_root_tmp, synthetic_fetcher):
    with pytest.raises(TemplateCacheError) as exc:
        fetch("https://gitlab.com/x/y", SHA, fetcher=synthetic_fetcher())
    assert exc.value.reason == "non_github_repo"


def test_verify_returns_false_for_absent_entry(cache_root_tmp):
    assert verify(REPO, SHA) is False


def test_verify_returns_true_for_ready_entry(cache_root_tmp, prepopulate_entry):
    prepopulate_entry(REPO, SHA)
    assert verify(REPO, SHA) is True


def test_verify_returns_false_when_ready_sentinel_missing(
    cache_root_tmp, prepopulate_entry
):
    prepopulate_entry(REPO, SHA, with_ready=False)
    assert verify(REPO, SHA) is False


def test_verify_returns_false_when_compromised_sentinel_present(
    cache_root_tmp, prepopulate_entry
):
    prepopulate_entry(REPO, SHA, compromised=True)
    assert verify(REPO, SHA) is False


def test_verify_returns_false_when_extra_files_appear(
    cache_root_tmp, prepopulate_entry
):
    entry = prepopulate_entry(REPO, SHA, files={"hello.txt": b"hi\n"})
    (entry / "EXTRA_FILE.txt").write_text("snuck in\n", encoding="utf-8")
    assert verify(REPO, SHA) is False


def test_verify_returns_false_when_manifest_files_missing(
    cache_root_tmp, prepopulate_entry
):
    entry = prepopulate_entry(REPO, SHA, files={"hello.txt": b"hi\n"})
    (entry / "hello.txt").unlink()
    assert verify(REPO, SHA) is False


def test_verify_returns_false_past_ttl(
    cache_root_tmp, prepopulate_entry
):
    entry = prepopulate_entry(REPO, SHA)
    long_ago = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(
        days=CACHE_TTL_DAYS + 1
    )
    (entry / _store.FETCHED_AT_FILE).write_text(
        long_ago.isoformat().replace("+00:00", "Z") + "\n", encoding="utf-8"
    )
    assert verify(REPO, SHA) is False


def test_entry_directory_mode_is_0o700(
    cache_root_tmp, synthetic_fetcher
):
    target = fetch(REPO, SHA, fetcher=synthetic_fetcher())
    actual_mode = stat.S_IMODE(os.stat(target).st_mode)
    assert actual_mode == 0o700


def test_cache_root_created_with_locks_subdir(
    cache_root_tmp, synthetic_fetcher
):
    fetch(REPO, SHA, fetcher=synthetic_fetcher())
    assert cache_root_tmp.is_dir()
    assert (cache_root_tmp / _store.LOCKS_SUBDIR).is_dir()


def test_cold_fill_thousand_files_under_three_seconds(
    cache_root_tmp, synthetic_fetcher
):
    big_tree = {f"src/file_{i:04d}.txt": b"x" * 64 for i in range(1000)}
    fetcher = synthetic_fetcher(big_tree)
    start = time.monotonic()
    fetch(REPO, SHA, fetcher=fetcher)
    elapsed = time.monotonic() - start
    assert elapsed < 3.0, f"cold fill took {elapsed:.3f}s; budget 3.0s"


def test_cache_hit_verify_under_twenty_milliseconds(
    cache_root_tmp, synthetic_fetcher
):
    fetch(REPO, SHA, fetcher=synthetic_fetcher())
    samples = []
    for _ in range(5):
        start = time.monotonic()
        verify(REPO, SHA)
        samples.append((time.monotonic() - start) * 1000.0)
    median = sorted(samples)[len(samples) // 2]
    assert median < 20.0, f"cache-hit verify median {median:.2f}ms; budget 20ms"
