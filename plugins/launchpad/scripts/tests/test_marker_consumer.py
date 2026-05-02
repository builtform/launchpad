"""Tests for lp_scaffold_stack.marker_consumer (Phase 3 S4)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.marker_consumer import (
    CONSUMED_PREFIX,
    CONSUMED_RETENTION,
    consume_marker,
    marker_path,
    marker_present,
)


def _write_empty_marker(tmp_path: Path) -> Path:
    lp = tmp_path / ".launchpad"
    lp.mkdir(parents=True, exist_ok=True)
    p = marker_path(tmp_path)
    p.write_bytes(b"")
    return p


def test_consume_marker_present(tmp_path: Path):
    p = _write_empty_marker(tmp_path)
    assert marker_present(tmp_path) is True
    consumed = consume_marker(tmp_path)
    assert consumed is not None
    assert consumed.name.startswith(CONSUMED_PREFIX)
    assert not p.exists()
    assert marker_present(tmp_path) is False


def test_consume_marker_absent_returns_none(tmp_path: Path):
    assert marker_present(tmp_path) is False
    assert consume_marker(tmp_path) is None


def test_retention_cap(tmp_path: Path):
    """Repeatedly write+consume markers; retention prunes older ones."""
    for i in range(CONSUMED_RETENTION + 3):
        _write_empty_marker(tmp_path)
        consume_marker(tmp_path)
        # Force unique timestamps for reliable retention ordering.
        time.sleep(1.05)
    lp = tmp_path / ".launchpad"
    consumed = list(lp.glob(f"{CONSUMED_PREFIX}*"))
    assert len(consumed) <= CONSUMED_RETENTION


def test_no_payload_parsing_at_v20(tmp_path: Path):
    """BL-235 strip-back: marker is empty positive-presence sentinel; no
    payload parsing happens at consume."""
    p = _write_empty_marker(tmp_path)
    # Even garbage content doesn't matter at v2.0.
    consume_marker(tmp_path)
    assert not p.exists()
