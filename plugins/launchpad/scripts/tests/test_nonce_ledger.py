"""Tests for lp_scaffold_stack.nonce_ledger (Phase 3 S3)."""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.nonce_ledger import (
    NonceLedgerError,
    _BAK_RETENTION_COUNT,
    _FORMAT_HEADER,
    _ROLLOVER_BYTES,
    append_nonce,
    is_nonce_seen,
    ledger_path,
    lock_path,
)

NONCE_A = "a" * 32
NONCE_B = "b" * 32
NONCE_C = "c" * 32


def test_append_then_read_back(tmp_path: Path):
    assert is_nonce_seen(NONCE_A, tmp_path) is False
    append_nonce(NONCE_A, tmp_path)
    assert is_nonce_seen(NONCE_A, tmp_path) is True
    assert is_nonce_seen(NONCE_B, tmp_path) is False


def test_format_header_present_after_first_op(tmp_path: Path):
    append_nonce(NONCE_A, tmp_path)
    text = ledger_path(tmp_path).read_text(encoding="utf-8")
    assert text.startswith(_FORMAT_HEADER)


def test_replay_rejection(tmp_path: Path):
    append_nonce(NONCE_A, tmp_path)
    append_nonce(NONCE_B, tmp_path)
    assert is_nonce_seen(NONCE_A, tmp_path)
    assert is_nonce_seen(NONCE_B, tmp_path)


def test_invalid_nonce_format_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        append_nonce("not-uuid", tmp_path)
    with pytest.raises(ValueError):
        is_nonce_seen("AAAA" + "a" * 28, tmp_path)


def test_lock_file_present(tmp_path: Path):
    append_nonce(NONCE_A, tmp_path)
    assert lock_path(tmp_path).exists()
    # Lock file must NOT contain the nonce (it's a sentinel only).
    assert NONCE_A not in lock_path(tmp_path).read_text(encoding="utf-8")


def test_v0_migration(tmp_path: Path):
    """Pre-write a v0 (header-less) ledger; first read migrates it."""
    lp = tmp_path / ".launchpad"
    lp.mkdir(parents=True, exist_ok=True)
    ledger = lp / ".scaffold-nonces.log"
    # 3 valid UUID lines, no header.
    ledger.write_text(
        f"{NONCE_A}\n{NONCE_B}\n{NONCE_C}\n",
        encoding="utf-8",
    )
    # First op triggers migration.
    assert is_nonce_seen(NONCE_A, tmp_path) is True
    text = ledger.read_text(encoding="utf-8")
    assert text.startswith(_FORMAT_HEADER)
    # All 3 prior nonces preserved.
    assert NONCE_A in text and NONCE_B in text and NONCE_C in text


def test_v0_migration_orphan_tmp_cleanup(tmp_path: Path):
    """Pre-write a header-less ledger + a stray .migration-tmp.<old-pid>."""
    lp = tmp_path / ".launchpad"
    lp.mkdir(parents=True, exist_ok=True)
    ledger = lp / ".scaffold-nonces.log"
    ledger.write_text(f"{NONCE_A}\n", encoding="utf-8")
    orphan = lp / ".scaffold-nonces.log.migration-tmp.99999"
    orphan.write_text("orphan content from prior crash\n", encoding="utf-8")
    assert orphan.exists()
    is_nonce_seen(NONCE_A, tmp_path)
    assert not orphan.exists(), "orphan migration-tmp should be cleaned up"
    assert NONCE_A in ledger.read_text(encoding="utf-8")


def test_format_header_unsupported(tmp_path: Path):
    lp = tmp_path / ".launchpad"
    lp.mkdir(parents=True, exist_ok=True)
    ledger = lp / ".scaffold-nonces.log"
    ledger.write_text("# nonce-ledger-format: v9\n", encoding="utf-8")
    with pytest.raises(NonceLedgerError) as exc:
        is_nonce_seen(NONCE_A, tmp_path)
    assert exc.value.reason == "nonce_ledger_format_unsupported"


def test_rollover_at_threshold(tmp_path: Path, monkeypatch):
    """Reduce the rollover threshold via monkeypatch and verify .bak file
    appears."""
    import lp_scaffold_stack.nonce_ledger as mod
    monkeypatch.setattr(mod, "_ROLLOVER_BYTES", 200)
    # Each record is 33 bytes; 200/33 ≈ 7 records before rollover.
    for i in range(10):
        nonce = f"{i:032x}"
        append_nonce(nonce, tmp_path)
    lp = tmp_path / ".launchpad"
    baks = list(lp.glob(".scaffold-nonces.log.bak.*"))
    assert baks, "expected at least one rollover .bak file"


def test_bak_window_consultation(tmp_path: Path, monkeypatch):
    """A nonce in a recently-rotated .bak should still be detected as seen."""
    import lp_scaffold_stack.nonce_ledger as mod
    monkeypatch.setattr(mod, "_ROLLOVER_BYTES", 100)
    # Force rollover by appending many nonces.
    for i in range(8):
        append_nonce(f"{i:032x}", tmp_path)
    # Nonce 0 is in the .bak now (likely). Verify it's still detected.
    assert is_nonce_seen(f"{0:032x}", tmp_path) is True


def test_bak_retention_cap(tmp_path: Path, monkeypatch):
    import lp_scaffold_stack.nonce_ledger as mod
    monkeypatch.setattr(mod, "_ROLLOVER_BYTES", 50)
    # Append enough to trigger many rollovers.
    for i in range(60):
        append_nonce(f"{i:032x}", tmp_path)
    lp = tmp_path / ".launchpad"
    baks = list(lp.glob(".scaffold-nonces.log.bak.*"))
    assert len(baks) <= _BAK_RETENTION_COUNT


def test_concurrent_appends_lock(tmp_path: Path):
    """Two threaded appends — both succeed and both nonces present."""
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def append(n: str):
        try:
            barrier.wait(timeout=5)
            append_nonce(n, tmp_path)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=append, args=(NONCE_A,))
    t2 = threading.Thread(target=append, args=(NONCE_B,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert not errors, f"unexpected errors: {errors}"
    assert is_nonce_seen(NONCE_A, tmp_path)
    assert is_nonce_seen(NONCE_B, tmp_path)


def test_filesystem_whitelist_unknown_tolerated(tmp_path: Path):
    """If FS detection returns 'unknown', the ledger op proceeds (tolerated
    at v2.0 strip-back per HANDSHAKE §1.5)."""
    import lp_scaffold_stack.nonce_ledger as mod
    mod._FS_TYPE_CACHE.clear()
    # Force unknown detection.
    real_detect = mod._detect_filesystem_type
    mod._detect_filesystem_type = lambda p: "unknown"
    try:
        append_nonce(NONCE_A, tmp_path)
        assert is_nonce_seen(NONCE_A, tmp_path)
    finally:
        mod._detect_filesystem_type = real_detect
        mod._FS_TYPE_CACHE.clear()


def test_filesystem_whitelist_rejected(tmp_path: Path):
    """A known-bad FS type hard-rejects per HANDSHAKE §4 rule 10."""
    import lp_scaffold_stack.nonce_ledger as mod
    mod._FS_TYPE_CACHE.clear()
    real_detect = mod._detect_filesystem_type
    mod._detect_filesystem_type = lambda p: "9p"
    try:
        with pytest.raises(NonceLedgerError) as exc:
            append_nonce(NONCE_A, tmp_path)
        assert exc.value.reason == "platform_unsupported_filesystem"
    finally:
        mod._detect_filesystem_type = real_detect
        mod._FS_TYPE_CACHE.clear()
