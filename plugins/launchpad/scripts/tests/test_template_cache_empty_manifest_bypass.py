"""v2.1 Codex PR #50 post-review P2 regression: empty-manifest cache bypass.

Asserts cache verification rejects a cache entry whose
`.expected_files.json` declares an empty `files` array but whose
directory contains an unexpected payload file. Previously the empty
expected set short-circuited the extra-file check entirely.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from template_cache._store import (  # noqa: E402
    EXPECTED_FILES_FILE,
    FETCHED_AT_FILE,
    READY_SENTINEL,
    _entry_files_match_manifest,
)


def _seed_cache_entry(entry_dir: Path, files: list[str]) -> None:
    entry_dir.mkdir(parents=True, exist_ok=True)
    (entry_dir / EXPECTED_FILES_FILE).write_text(
        json.dumps({"files": files}), encoding="utf-8",
    )
    (entry_dir / READY_SENTINEL).write_text("ok\n", encoding="utf-8")
    (entry_dir / FETCHED_AT_FILE).write_text("2026-01-01T00:00:00Z\n", encoding="utf-8")


def test_empty_manifest_with_extra_file_rejects(tmp_path):
    """Empty `files: []` + injected payload file → verification False."""
    entry = tmp_path / "entry"
    _seed_cache_entry(entry, files=[])
    # Inject an extra payload file the manifest doesn't list.
    (entry / "injected.txt").write_text("attacker-controlled\n", encoding="utf-8")
    assert _entry_files_match_manifest(entry) is False


def test_empty_manifest_with_no_extras_passes(tmp_path):
    """Empty `files: []` + truly empty cache tree → verification True
    (sentinel files don't count as payload)."""
    entry = tmp_path / "entry"
    _seed_cache_entry(entry, files=[])
    assert _entry_files_match_manifest(entry) is True


def test_populated_manifest_matching_disk_passes(tmp_path):
    """Populated `files: [...]` + matching disk content → verification True."""
    entry = tmp_path / "entry"
    _seed_cache_entry(entry, files=["a.txt", "sub/b.txt"])
    (entry / "a.txt").write_text("a\n", encoding="utf-8")
    sub = entry / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("b\n", encoding="utf-8")
    assert _entry_files_match_manifest(entry) is True


def test_populated_manifest_with_missing_disk_file_rejects(tmp_path):
    entry = tmp_path / "entry"
    _seed_cache_entry(entry, files=["a.txt", "b.txt"])
    (entry / "a.txt").write_text("a\n", encoding="utf-8")
    # b.txt absent on disk
    assert _entry_files_match_manifest(entry) is False


def test_populated_manifest_with_extra_disk_file_rejects(tmp_path):
    entry = tmp_path / "entry"
    _seed_cache_entry(entry, files=["a.txt"])
    (entry / "a.txt").write_text("a\n", encoding="utf-8")
    (entry / "extra.txt").write_text("extra\n", encoding="utf-8")
    assert _entry_files_match_manifest(entry) is False
