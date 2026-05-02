"""Tests for knowledge_anchor_loader (HANDSHAKE §9.2)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from knowledge_anchor_loader import read_and_verify


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_happy_returns_buffer(tmp_path: Path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    f = plugins / "pattern.md"
    body = b"# pattern\nbody\n"
    f.write_bytes(body)

    out = read_and_verify(f, _sha(body), plugins)
    assert out == body


def test_checksum_mismatch_raises(tmp_path: Path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    f = plugins / "pattern.md"
    f.write_bytes(b"hello")
    with pytest.raises(ValueError) as exc:
        read_and_verify(f, _sha(b"world"), plugins)
    assert "checksum mismatch" in str(exc.value)


def test_path_outside_plugins_root_rejected(tmp_path: Path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    f = other / "pattern.md"
    f.write_bytes(b"x")
    with pytest.raises(ValueError) as exc:
        read_and_verify(f, _sha(b"x"), plugins)
    assert "escapes plugins root" in str(exc.value)


def test_symlink_pointing_outside_plugins_rejected(tmp_path: Path):
    """A symlink in plugins/ pointing OUTSIDE plugins resolves to an external
    path; the cwd-containment check rejects it."""
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_bytes(b"x")
    sym = plugins / "evil.md"
    sym.symlink_to(outside)
    with pytest.raises(ValueError) as exc:
        read_and_verify(sym, _sha(b"x"), plugins)
    assert "escapes plugins root" in str(exc.value)


def test_ancestor_symlink_rejected(tmp_path: Path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    # Create a real subdirectory outside plugins, then symlink it inside.
    real_subdir = tmp_path / "real_dir"
    real_subdir.mkdir()
    (real_subdir / "pattern.md").write_bytes(b"x")
    sym_subdir = plugins / "linked"
    sym_subdir.symlink_to(real_subdir, target_is_directory=True)
    with pytest.raises(ValueError):
        read_and_verify(sym_subdir / "pattern.md", _sha(b"x"), plugins)


def test_missing_file_raises(tmp_path: Path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    with pytest.raises(FileNotFoundError):
        read_and_verify(plugins / "nope.md", "0" * 64, plugins)
