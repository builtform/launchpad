"""Tests for path_validator (HANDSHAKE §6).

Covers both the shape-only check (`_validate_path_shape`) and the
filesystem-bound check (`_validate_filesystem_safety`), plus the public
`validate_relative_path` orchestrator.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from path_validator import (
    PathValidationError,
    _validate_filesystem_safety,
    _validate_path_shape,
    validate_relative_path,
)


# --- _validate_path_shape ---

def test_shape_accepts_simple_relative():
    _validate_path_shape("apps/web", "p")


def test_shape_accepts_dotted_filename():
    _validate_path_shape("apps/web/package.json", "p")


def test_shape_accepts_dash_underscore():
    _validate_path_shape("packages/my-pkg/file_name.ts", "p")


def test_shape_rejects_non_str():
    with pytest.raises(PathValidationError):
        _validate_path_shape(123, "p")  # type: ignore[arg-type]


def test_shape_rejects_empty():
    with pytest.raises(PathValidationError):
        _validate_path_shape("", "p")


def test_shape_rejects_null_byte():
    with pytest.raises(PathValidationError):
        _validate_path_shape("apps/we\x00b", "p")


def test_shape_rejects_disallowed_chars():
    for bad in ("apps/we b", "apps/web*", "apps/web|x", "apps/web;ls"):
        with pytest.raises(PathValidationError):
            _validate_path_shape(bad, "p")


def test_shape_rejects_absolute():
    with pytest.raises(PathValidationError):
        _validate_path_shape("/etc/passwd", "p")


def test_shape_rejects_parent_traversal():
    for bad in ("..", "../etc", "apps/../etc", "apps/../../escape"):
        with pytest.raises(PathValidationError):
            _validate_path_shape(bad, "p")


def test_shape_rejects_git():
    with pytest.raises(PathValidationError):
        _validate_path_shape(".git/config", "p")


def test_shape_rejects_node_modules():
    with pytest.raises(PathValidationError):
        _validate_path_shape("node_modules/foo", "p")


def test_shape_rejects_env_files():
    with pytest.raises(PathValidationError):
        _validate_path_shape(".env", "p")
    with pytest.raises(PathValidationError):
        _validate_path_shape(".env.local", "p")


def test_shape_rejects_launchpad_dotfiles():
    with pytest.raises(PathValidationError):
        _validate_path_shape(".launchpad/.first-run-marker", "p")


def test_shape_field_name_in_error():
    try:
        _validate_path_shape("", "layers[0].path")
    except PathValidationError as exc:
        assert exc.field_name == "layers[0].path"
        assert "layers[0].path" in str(exc)


# --- _validate_filesystem_safety ---

def test_fs_accepts_inside_cwd(tmp_path: Path):
    candidate = _validate_filesystem_safety("apps/web", tmp_path, "p")
    assert candidate == (tmp_path / "apps" / "web").resolve()


def test_fs_rejects_symlink_escaping_cwd(tmp_path: Path):
    """A symlink pointing OUTSIDE cwd resolves to an outside path and is
    rejected by the cwd-containment check."""
    outside = tmp_path.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    project = tmp_path / "project"
    project.mkdir()
    sym = project / "escape"
    sym.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathValidationError):
        _validate_filesystem_safety("escape/file.txt", project, "p")


def test_fs_resolved_path_inside(tmp_path: Path):
    (tmp_path / "apps").mkdir()
    candidate = _validate_filesystem_safety("apps/web", tmp_path, "p")
    assert candidate.is_relative_to(tmp_path.resolve())


# --- validate_relative_path orchestrator ---

def test_validate_relative_path_happy(tmp_path: Path):
    out = validate_relative_path("apps/web", tmp_path, "p")
    assert out.is_relative_to(tmp_path.resolve())


def test_validate_relative_path_shape_failure_short_circuits(tmp_path: Path):
    # Should raise on shape, not reach FS check.
    with pytest.raises(PathValidationError):
        validate_relative_path("../etc/passwd", tmp_path, "p")


def test_validate_relative_path_passes_field_name(tmp_path: Path):
    try:
        validate_relative_path("", tmp_path, "manual_override.layer.path")
    except PathValidationError as exc:
        assert exc.field_name == "manual_override.layer.path"
