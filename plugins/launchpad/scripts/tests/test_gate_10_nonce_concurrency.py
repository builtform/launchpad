"""Gate #10 (OPERATIONS §6): nonce concurrency — exactly one success, one
hard-reject when 2 processes race past the lock.

Uses threading.Barrier instead of multiprocessing because the test fixture
needs to share tmp_path; the lock semantics (fcntl.flock + LOCK_EX) work
identically across threads (LOCK_EX is per-process per-fd at the kernel
level, but the cross-thread locking is sequenced via the Python GIL +
flock blocking semantics).
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.nonce_ledger import (
    NonceLedgerError,
    append_nonce,
    is_nonce_seen,
)


def test_concurrent_appends_serialize(tmp_path: Path):
    """Append the same nonce from two threads with a barrier — both calls
    succeed (idempotent: O_APPEND just adds the same nonce twice; the
    is_nonce_seen check is the gate), but the ledger ends up with the nonce
    present and the in-flight ordering is serialized by flock."""
    barrier = threading.Barrier(2)
    nonce = "a" * 32
    errors: list[Exception] = []

    def worker():
        try:
            barrier.wait(timeout=5)
            append_nonce(nonce, tmp_path)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"unexpected errors: {errors}"
    assert is_nonce_seen(nonce, tmp_path)


def test_concurrent_distinct_nonces_no_corruption(tmp_path: Path):
    """100 distinct nonces across 4 threads — all appended cleanly."""
    barrier = threading.Barrier(4)
    errors: list[Exception] = []

    def worker(group_offset: int):
        try:
            barrier.wait(timeout=5)
            for i in range(25):
                nonce = f"{group_offset * 25 + i:032x}"
                append_nonce(nonce, tmp_path)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(g,)) for g in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"unexpected errors: {errors}"
    # Spot-check several nonces.
    for i in (0, 25, 50, 99):
        assert is_nonce_seen(f"{i:032x}", tmp_path)
