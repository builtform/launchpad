"""Template cache concurrency + eviction + sentinel tests.

Phase 4 plan §3.7 rules 1-10 (this file owns rules 4, 5, 6, 8, 9, 10).
Marked `slow` per DA6 lock — requires multi-threaded contention + perf-bound
LRU walks.
"""
from __future__ import annotations

import os
import shutil
import stat
import threading
import time
from pathlib import Path

import pytest

from template_cache import (
    CACHE_LRU_MAX_BYTES,
    MAX_CONCURRENT_FETCHES,
    READY_SENTINEL,
    TemplateCacheError,
    _store,
    fetch,
    verify,
)

pytestmark = pytest.mark.slow

REPO = "https://github.com/example-org/example-repo"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


# --- rule #5: validation-before-flock ordering ---------------------------


def test_malformed_sha_raises_before_creating_any_lock_file(
    cache_root_tmp, synthetic_fetcher
):
    with pytest.raises(TemplateCacheError) as exc:
        fetch(REPO, "not-a-sha", fetcher=synthetic_fetcher())
    assert exc.value.reason == "malformed_sha"
    assert not (cache_root_tmp / _store.LOCKS_SUBDIR).exists()


def test_non_github_url_raises_before_creating_any_lock_file(
    cache_root_tmp, synthetic_fetcher
):
    with pytest.raises(TemplateCacheError):
        fetch("https://example.com/repo", SHA_A, fetcher=synthetic_fetcher())
    assert not (cache_root_tmp / _store.LOCKS_SUBDIR).exists()


def test_cache_root_pre_flight_creates_root_with_mode_0o700(
    cache_root_tmp, synthetic_fetcher
):
    fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    actual_mode = stat.S_IMODE(os.stat(cache_root_tmp).st_mode)
    assert actual_mode == 0o700


def test_cache_root_with_unsafe_permissions_raises(
    cache_root_tmp, synthetic_fetcher
):
    cache_root_tmp.mkdir(mode=0o755, parents=True)
    with pytest.raises(TemplateCacheError) as exc:
        fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    assert exc.value.reason == "cache_root_unsafe_permissions"


def test_cache_root_as_symlink_is_rejected(
    cache_root_tmp, synthetic_fetcher, tmp_path
):
    real_dir = tmp_path / "real-cache-target"
    real_dir.mkdir(mode=0o700)
    cache_root_tmp.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(real_dir, cache_root_tmp)
    with pytest.raises(TemplateCacheError) as exc:
        fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    assert exc.value.reason == "cache_root_is_symlink"


# --- rule #4: per-entry locking + MAX_CONCURRENT_FETCHES ------------------


def test_lock_file_lives_in_locks_subdir_with_mode_0o600(
    cache_root_tmp, synthetic_fetcher
):
    fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    locks = list((cache_root_tmp / _store.LOCKS_SUBDIR).glob("*.lock"))
    assert len(locks) == 1
    actual_mode = stat.S_IMODE(os.stat(locks[0]).st_mode)
    assert actual_mode == 0o600


def test_lock_file_persists_after_entry_purge(
    cache_root_tmp, synthetic_fetcher
):
    target = fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    shutil.rmtree(target)
    locks = list((cache_root_tmp / _store.LOCKS_SUBDIR).glob("*.lock"))
    assert len(locks) == 1, "rule #4: lock file must survive entry deletion"


def test_concurrent_threads_serialize_through_flock(
    cache_root_tmp, synthetic_fetcher
):
    started = threading.Barrier(3)
    fetcher_calls = []
    fetcher_lock = threading.Lock()

    def slow_fetcher(target: Path) -> None:
        with fetcher_lock:
            fetcher_calls.append(time.monotonic())
        time.sleep(0.05)
        (target / "a.txt").write_text("ok\n", encoding="utf-8")

    def worker():
        started.wait()
        fetch(REPO, SHA_A, fetcher=slow_fetcher)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
    assert len(fetcher_calls) == 1, (
        f"only the first thread should run the fetcher (got {len(fetcher_calls)})"
    )


def test_max_concurrent_fetches_constant_is_three():
    assert MAX_CONCURRENT_FETCHES == 3


def test_concurrent_distinct_entries_capped_at_three(
    cache_root_tmp, synthetic_fetcher
):
    in_flight = []
    in_flight_lock = threading.Lock()
    peak = {"n": 0}

    def slow_fetcher(target: Path) -> None:
        with in_flight_lock:
            in_flight.append(1)
            peak["n"] = max(peak["n"], len(in_flight))
        time.sleep(0.1)
        with in_flight_lock:
            in_flight.pop()
        (target / "a.txt").write_text("ok\n", encoding="utf-8")

    def worker(sha: str):
        fetch(REPO, sha, fetcher=slow_fetcher)

    threads = [
        threading.Thread(target=worker, args=(c * 40,))
        for c in "abcdef"
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)
    assert peak["n"] <= MAX_CONCURRENT_FETCHES, (
        f"semaphore breached: peak in-flight {peak['n']}"
    )


# --- rule #8: auto-purge / sentinel handling -------------------------------


def test_compromised_sentinel_triggers_re_fetch(
    cache_root_tmp, synthetic_fetcher, prepopulate_entry
):
    prepopulate_entry(REPO, SHA_A, compromised=True)
    fetcher_called = {"n": 0}

    def fetcher(target: Path) -> None:
        fetcher_called["n"] += 1
        (target / "ok.txt").write_text("re-fetched\n", encoding="utf-8")

    fetch(REPO, SHA_A, fetcher=fetcher)
    assert fetcher_called["n"] == 1


def test_extra_files_invalidate_entry_via_verify(
    cache_root_tmp, prepopulate_entry
):
    entry = prepopulate_entry(REPO, SHA_A, files={"a.txt": b"a\n"})
    (entry / "rogue.txt").write_text("?", encoding="utf-8")
    assert verify(REPO, SHA_A) is False


def test_missing_files_invalidate_entry_via_verify(
    cache_root_tmp, prepopulate_entry
):
    entry = prepopulate_entry(REPO, SHA_A, files={"a.txt": b"a\n", "b.txt": b"b\n"})
    (entry / "b.txt").unlink()
    assert verify(REPO, SHA_A) is False


def test_purge_removes_ready_first_then_directory(
    cache_root_tmp, synthetic_fetcher
):
    target = fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    assert (target / READY_SENTINEL).exists()
    _store._purge_entry(target)
    assert not target.exists()


def test_unready_entry_replaced_on_next_fetch(
    cache_root_tmp, synthetic_fetcher, prepopulate_entry
):
    prepopulate_entry(REPO, SHA_A, with_ready=False)
    fetcher_calls = {"n": 0}

    def fetcher(target: Path) -> None:
        fetcher_calls["n"] += 1
        (target / "fresh.txt").write_text("fresh\n", encoding="utf-8")

    fetch(REPO, SHA_A, fetcher=fetcher)
    assert fetcher_calls["n"] == 1


# --- rule #10: filesystem-full / fetcher-exception cleanup ----------------


def test_fetcher_exception_cleans_up_tempdir(
    cache_root_tmp,
):
    def failing_fetcher(target: Path) -> None:
        (target / "partial.txt").write_text("partial\n", encoding="utf-8")
        raise RuntimeError("simulated network failure")

    with pytest.raises(RuntimeError):
        fetch(REPO, SHA_A, fetcher=failing_fetcher)

    leftover = [
        p for p in cache_root_tmp.iterdir()
        if p.is_dir() and ".tmp." in p.name
    ]
    assert leftover == [], f"tmp dirs leaked: {leftover}"


def test_fetcher_exception_does_not_create_entry_dir(
    cache_root_tmp,
):
    def failing_fetcher(target: Path) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        fetch(REPO, SHA_A, fetcher=failing_fetcher)
    assert not (cache_root_tmp / f"example-org-example-repo@{SHA_A}").exists()


# --- rule #6: 500MB LRU + lazy eviction ------------------------------------


def test_lru_constant_is_500_megabytes():
    assert CACHE_LRU_MAX_BYTES == 500 * 1024 * 1024


def test_lru_evicts_oldest_entry_when_total_exceeds_threshold(
    cache_root_tmp, monkeypatch, synthetic_fetcher
):
    # Each entry below is ~16KB blob + manifest/ready/fetched_at ~100 bytes;
    # target threshold of 40KB keeps two entries and evicts the oldest one.
    monkeypatch.setattr(_store, "CACHE_LRU_MAX_BYTES", 40 * 1024)

    def big_fetcher(target: Path) -> None:
        (target / "blob.bin").write_bytes(b"x" * 16384)

    a = fetch(REPO, SHA_A, fetcher=big_fetcher)
    time.sleep(0.02)
    b = fetch(REPO, SHA_B, fetcher=big_fetcher)
    time.sleep(0.02)
    c = fetch(REPO, SHA_C, fetcher=big_fetcher)

    assert c.exists(), "newest entry must survive LRU"
    assert b.exists(), "second-newest entry must survive LRU"
    assert not a.exists(), "oldest entry must have been evicted"


def test_lru_no_op_when_total_under_threshold(
    cache_root_tmp, synthetic_fetcher
):
    fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    fetch(REPO, SHA_B, fetcher=synthetic_fetcher())
    entries = [
        p for p in cache_root_tmp.iterdir()
        if p.is_dir() and "@" in p.name and ".tmp." not in p.name and p.name != ".locks"
    ]
    assert len(entries) == 2


def test_lru_preserves_only_entries_with_ready_sentinel(
    cache_root_tmp, synthetic_fetcher
):
    target = fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    entries = _store._list_entries(cache_root_tmp)
    assert target in entries


# --- rule #9 + cross-cutting: symlink + locks subdir layout ---------------


def test_locks_subdir_stays_under_root(
    cache_root_tmp, synthetic_fetcher
):
    fetch(REPO, SHA_A, fetcher=synthetic_fetcher())
    locks_dir = cache_root_tmp / _store.LOCKS_SUBDIR
    assert locks_dir.exists()
    assert locks_dir.parent == cache_root_tmp


def test_entry_path_does_not_collide_across_repos(cache_root_tmp):
    from template_cache import entry_path

    p1 = entry_path("https://github.com/a/b", SHA_A)
    p2 = entry_path("https://github.com/c/d", SHA_A)
    assert p1 != p2


def test_entry_slug_strips_dot_git_suffix(cache_root_tmp, synthetic_fetcher):
    target = fetch(REPO + ".git", SHA_A, fetcher=synthetic_fetcher())
    assert target.name == f"example-org-example-repo@{SHA_A}"


def test_validation_before_flock_does_not_acquire_when_inputs_invalid(
    cache_root_tmp, synthetic_fetcher
):
    with pytest.raises(TemplateCacheError):
        fetch(REPO, "BAD", fetcher=synthetic_fetcher())
    locks_dir = cache_root_tmp / _store.LOCKS_SUBDIR
    assert not locks_dir.exists() or list(locks_dir.glob("*")) == []
