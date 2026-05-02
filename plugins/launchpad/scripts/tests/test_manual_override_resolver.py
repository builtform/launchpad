"""Tests for lp_pick_stack.manual_override_resolver (Phase 2 §4.1 Step 4)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.manual_override_resolver import (
    ALLOWED_ROLES,
    ManualOverrideError,
    resolve_manual,
)


# --- single layer ---


def test_single_valid_layer(tmp_path: Path):
    layers = resolve_manual(
        [{"stack": "fastapi", "role": "backend", "path": "."}],
        tmp_path,
    )
    assert len(layers) == 1
    assert layers[0]["stack"] == "fastapi"
    assert layers[0]["options"] == {}


def test_options_preserved(tmp_path: Path):
    layers = resolve_manual(
        [{"stack": "rails", "role": "fullstack", "path": ".", "options": {"database": "postgresql"}}],
        tmp_path,
    )
    assert layers[0]["options"] == {"database": "postgresql"}


# --- VALID_COMBINATIONS gate ---


def test_invalid_combination_rejected(tmp_path: Path):
    with pytest.raises(ManualOverrideError) as exc:
        resolve_manual(
            [{"stack": "astro", "role": "backend", "path": "."}],
            tmp_path,
        )
    assert "VALID_COMBINATIONS" in str(exc.value)


def test_role_not_in_enum_rejected(tmp_path: Path):
    with pytest.raises(ManualOverrideError) as exc:
        resolve_manual(
            [{"stack": "astro", "role": "iot", "path": "."}],
            tmp_path,
        )
    assert "ALLOWED_ROLES" in str(exc.value)


# --- path validation ---


def test_path_traversal_rejected(tmp_path: Path):
    from path_validator import PathValidationError

    with pytest.raises(PathValidationError):
        resolve_manual(
            [{"stack": "fastapi", "role": "backend", "path": "../escape"}],
            tmp_path,
        )


def test_absolute_path_rejected(tmp_path: Path):
    from path_validator import PathValidationError

    with pytest.raises(PathValidationError):
        resolve_manual(
            [{"stack": "fastapi", "role": "backend", "path": "/etc/passwd"}],
            tmp_path,
        )


# --- cross-layer rules ---


def test_path_uniqueness_violation(tmp_path: Path):
    with pytest.raises(ManualOverrideError) as exc:
        resolve_manual(
            [
                {"stack": "next", "role": "fullstack", "path": "."},
                {"stack": "next", "role": "fullstack", "path": "."},
            ],
            tmp_path,
        )
    assert "path uniqueness" in str(exc.value)


def test_fullstack_precludes_split(tmp_path: Path):
    (tmp_path / "apps").mkdir()
    with pytest.raises(ManualOverrideError) as exc:
        resolve_manual(
            [
                {"stack": "rails", "role": "fullstack", "path": "."},
                {"stack": "fastapi", "role": "backend", "path": "apps"},
            ],
            tmp_path,
        )
    assert "fullstack" in str(exc.value)


def test_mobile_standalone(tmp_path: Path):
    (tmp_path / "apps").mkdir()
    with pytest.raises(ManualOverrideError) as exc:
        resolve_manual(
            [
                {"stack": "expo", "role": "mobile", "path": "."},
                {"stack": "fastapi", "role": "backend", "path": "apps"},
            ],
            tmp_path,
        )
    assert "mobile" in str(exc.value)


# --- input shape ---


def test_empty_layer_set_rejected(tmp_path: Path):
    with pytest.raises(ManualOverrideError):
        resolve_manual([], tmp_path)


def test_missing_required_key(tmp_path: Path):
    with pytest.raises(ManualOverrideError) as exc:
        resolve_manual(
            [{"stack": "fastapi", "role": "backend"}],  # no path
            tmp_path,
        )
    assert "path" in str(exc.value)


def test_non_string_value_rejected(tmp_path: Path):
    with pytest.raises(ManualOverrideError):
        resolve_manual(
            [{"stack": "fastapi", "role": "backend", "path": 42}],  # type: ignore[dict-item]
            tmp_path,
        )


def test_options_must_be_mapping(tmp_path: Path):
    with pytest.raises(ManualOverrideError):
        resolve_manual(
            [{"stack": "fastapi", "role": "backend", "path": ".", "options": "not a dict"}],
            tmp_path,
        )


def test_allowed_roles_enum_completeness():
    # The 8 roles in HANDSHAKE §4 schema enum
    expected = {
        "frontend", "backend", "frontend-main", "frontend-dashboard",
        "fullstack", "mobile", "backend-managed", "desktop",
    }
    assert ALLOWED_ROLES == expected
