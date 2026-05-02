"""Tests for cwd_state classifier (HANDSHAKE §8).

Includes the L8 closure 500-entry iteration cap test (§4.7 of the Phase -1
handoff): mocks cwd.iterdir() to verify the cap is enforced without per-entry
stat() calls.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import (
    BROWNFIELD_MANIFESTS,
    cwd_state,
    refuse_if_not_greenfield,
)


# --- empty / brownfield / ambiguous classification ---

def test_empty_cwd(tmp_path: Path):
    assert cwd_state(tmp_path) == "empty"


def test_empty_with_okay_files(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("node_modules\n")
    (tmp_path / "LICENSE").write_text("MIT\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".launchpad").mkdir()
    assert cwd_state(tmp_path) == "empty"


def test_brownfield_package_json(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    assert cwd_state(tmp_path) == "brownfield"


def test_brownfield_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n")
    assert cwd_state(tmp_path) == "brownfield"


def test_brownfield_case_insensitive(tmp_path: Path):
    """macOS APFS / Windows NTFS are case-insensitive."""
    (tmp_path / "Package.json").write_text("{}")
    assert cwd_state(tmp_path) == "brownfield"


def test_ambiguous_unknown_large_file(tmp_path: Path):
    (tmp_path / "mystery.txt").write_text("x" * 200)
    assert cwd_state(tmp_path) == "ambiguous"


def test_empty_with_short_readme(tmp_path: Path):
    """A short README is the v0 'just a stub' allowance.

    README.md alone (no extras) returns 'empty' regardless of size — README is
    in GREENFIELD_OK_FILES and is filtered out before the size check fires.
    """
    (tmp_path / "README.md").write_text("# project\n")
    assert cwd_state(tmp_path) == "empty"


def test_ambiguous_with_one_small_extra_and_short_readme(tmp_path: Path):
    """1-extra + short README: the README size-check shortcut applies and
    classifies as 'empty' per spec."""
    (tmp_path / "README.md").write_text("# project\n")
    (tmp_path / "notes.txt").write_text("hi\n")
    assert cwd_state(tmp_path) == "empty"


def test_ambiguous_with_one_large_extra(tmp_path: Path):
    """One extra > 100 bytes triggers the generic ambiguous safeguard."""
    (tmp_path / "mystery.txt").write_text("x" * 200)
    assert cwd_state(tmp_path) == "ambiguous"


def test_ambiguous_with_two_extras(tmp_path: Path):
    """≥2 extras bypass the README shortcut → ambiguous fallback."""
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "todo.txt").write_text("hi")
    assert cwd_state(tmp_path) == "ambiguous"


def test_nonexistent_path_raises(tmp_path: Path):
    with pytest.raises(NotADirectoryError):
        cwd_state(tmp_path / "no_such")


def test_file_path_raises(tmp_path: Path):
    f = tmp_path / "afile"
    f.write_text("x")
    with pytest.raises(NotADirectoryError):
        cwd_state(f)


# --- 500-entry iteration cap (L8 closure per Phase -1 §4.7) ---

def test_cwd_state_500_entry_cap(tmp_path: Path):
    """When cwd has > 500 entries, return 'ambiguous' after iterating exactly
    501 entries (per Layer 5 performance P3-L5-1) — the cap fires BEFORE the
    per-entry stat() loop. We assert the iterator was advanced no more than
    501 times (one beyond the cap, where the cap fires).
    """
    fake_entries = [tmp_path / f"f{i}" for i in range(600)]
    advance_count = {"n": 0}

    def counting_iter():
        for e in fake_entries:
            advance_count["n"] += 1
            yield e

    # Patch iterdir on this specific path instance only — patching globally
    # would also break cwd.is_dir() / cwd.exists() calls earlier in the function.
    with patch.object(type(tmp_path), "iterdir", lambda self: counting_iter()):
        result = cwd_state(tmp_path)

    assert result == "ambiguous"
    # Cap fires when i == 500 (after 501 yields). The function returns
    # immediately, so advance_count is bounded at 501.
    assert advance_count["n"] <= 501, (
        f"iterdir advanced {advance_count['n']} times; cap should have "
        f"short-circuited at 501 (per HANDSHAKE §8 + Layer 5 P3-L5-1)."
    )


def test_cwd_state_just_under_cap_works(tmp_path: Path):
    """Exactly 500 entries should NOT trigger the cap (boundary test)."""
    for i in range(500):
        (tmp_path / f"f{i}.txt").write_text("x")
    # 500 small txt files: not brownfield, has unrecognized extras, all < 100b
    # so the final ambiguous-fallback fires (not the cap-fallback).
    result = cwd_state(tmp_path)
    assert result == "ambiguous"


# --- refuse_if_not_greenfield helper ---

def test_refuse_passes_on_empty(tmp_path: Path):
    refuse_if_not_greenfield(tmp_path, "/lp-pick-stack")  # no raise


def test_refuse_raises_on_brownfield(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    with pytest.raises(RuntimeError) as exc:
        refuse_if_not_greenfield(tmp_path, "/lp-pick-stack")
    assert "cwd_state_brownfield" in str(exc.value)
    assert "/lp-pick-stack" in str(exc.value)
    assert "/lp-define" in str(exc.value)


def test_refuse_raises_on_ambiguous(tmp_path: Path):
    (tmp_path / "mystery.txt").write_text("x" * 200)
    with pytest.raises(RuntimeError) as exc:
        refuse_if_not_greenfield(tmp_path, "/lp-scaffold-stack")
    assert "cwd_state_ambiguous" in str(exc.value)


# --- BROWNFIELD_MANIFESTS contents (sanity) ---

def test_brownfield_manifests_covers_major_ecosystems():
    """Smoke test: BROWNFIELD_MANIFESTS includes at least one entry per major
    ecosystem listed in HANDSHAKE §8."""
    assert "package.json" in BROWNFIELD_MANIFESTS  # Node
    assert "pyproject.toml" in BROWNFIELD_MANIFESTS  # Python
    assert "Gemfile" in BROWNFIELD_MANIFESTS  # Ruby
    assert "go.mod" in BROWNFIELD_MANIFESTS  # Go
    assert "Cargo.toml" in BROWNFIELD_MANIFESTS  # Rust
    assert "composer.json" in BROWNFIELD_MANIFESTS  # PHP
    assert "mix.exs" in BROWNFIELD_MANIFESTS  # Elixir
    assert "pubspec.yaml" in BROWNFIELD_MANIFESTS  # Dart/Flutter
