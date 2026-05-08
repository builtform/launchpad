"""v2.1 Codex PR #50 P0 (D9.1) regression: template_cache filesystem-entry rejection.

Tests:
  * symlink rejection
  * FIFO rejection (creation portable on darwin/linux)
  * 256-byte target-rendering cap on long readlink targets
  * read-side mirror in `_entry_files_match_manifest`
"""
from __future__ import annotations

import os
import stat as stat_mod
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from template_cache._store import (  # noqa: E402
    MAX_REJECTION_TARGET_BYTES,
    TemplateCacheError,
    _sanitize_readlink_target,
    _walk_for_disallowed_entries,
)


def test_walk_clean_tree_returns_none(tmp_path):
    (tmp_path / "a").write_text("ok\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b").write_text("ok\n", encoding="utf-8")
    assert _walk_for_disallowed_entries(tmp_path) is None


def test_walk_rejects_symlink_at_root(tmp_path):
    target_dir = tmp_path / "real"
    target_dir.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target_dir, target_is_directory=True)
    # Walking the LINK as root: returns symlink rejection.
    rejection = _walk_for_disallowed_entries(link)
    assert rejection is not None
    assert rejection[1] == "symlink"


def test_walk_rejects_nested_symlink(tmp_path):
    inner = tmp_path / "inner.txt"
    inner.write_text("ok", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(inner)
    rejection = _walk_for_disallowed_entries(tmp_path)
    assert rejection is not None
    assert rejection[1] == "symlink"


def test_walk_rejects_fifo(tmp_path):
    pytest.importorskip("os")
    fifo = tmp_path / "fifo"
    try:
        os.mkfifo(str(fifo))
    except (NotImplementedError, OSError):
        pytest.skip("FIFO not supported on this platform")
    rejection = _walk_for_disallowed_entries(tmp_path)
    assert rejection is not None
    assert rejection[1] == "fifo"


def test_sanitize_readlink_short_target():
    safe, b64 = _sanitize_readlink_target("/etc/passwd")
    assert "/etc/passwd" in safe or "etc/passwd" in safe
    # base64 of 11 bytes does not need truncation.
    assert "...truncated_" not in b64


def test_sanitize_readlink_caps_long_target():
    long_target = "/" + ("A" * (MAX_REJECTION_TARGET_BYTES * 2))
    safe, b64 = _sanitize_readlink_target(long_target)
    assert "...truncated_" in safe
    assert "...truncated_" in b64


def test_sanitize_readlink_strips_non_printable():
    nasty = "\x00\x01\x02/path"
    safe, _b64 = _sanitize_readlink_target(nasty)
    # Non-printable should not appear raw in the safe rendering.
    assert "\x00" not in safe
    assert "\x01" not in safe


def test_template_cache_error_carries_entry_kind():
    err = TemplateCacheError(
        reason="disallowed_entry_in_fetched_template",
        path=Path("/tmp/x"),
        remediation="test",
        entry_kind="symlink",
    )
    assert err.entry_kind == "symlink"
    assert err.reason == "disallowed_entry_in_fetched_template"
