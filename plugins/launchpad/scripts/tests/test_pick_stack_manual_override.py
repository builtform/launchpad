"""Manual-override branch test (Phase 2 §4.4 T5).

When the user picks `[m]anual override`, the engine must:

- Validate every (stack, role) tuple against VALID_COMBINATIONS
- Validate every path against path_validator
- Set matched_category_id = "manual-override" (HANDSHAKE §4 rule 4)
- Write a fully-integrity-bound scaffold-decision.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.engine import Outcome, run_pipeline


# Manual-override doesn't depend on funnel matching, but the engine still
# validates Q1-Q5 — pass an arbitrary valid set.
VALID_ANSWERS = {
    "Q1": "web-app",
    "Q2": "yes-needed",
    "Q3": "no",
    "Q4": "python",
    "Q5": "container",
}


def test_manual_override_single_layer(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        manual_override=True,
        manual_layer_specs=[
            {"stack": "fastapi", "role": "backend", "path": "."},
        ],
        write_telemetry=False,
    )
    assert result.success, result.message
    assert result.outcome == Outcome.MANUAL_OVERRIDE
    assert result.matched_category_id == "manual-override"


def test_manual_override_writes_decision_with_correct_id(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        manual_override=True,
        manual_layer_specs=[{"stack": "fastapi", "role": "backend", "path": "."}],
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    assert data["matched_category_id"] == "manual-override"
    assert data["layers"] == [{"stack": "fastapi", "role": "backend", "path": ".", "options": {}}]


def test_manual_override_invalid_combo_rejected(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        manual_override=True,
        manual_layer_specs=[{"stack": "astro", "role": "backend", "path": "."}],
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "manual_override_invalid"


def test_manual_override_path_traversal_rejected(tmp_path: Path):
    """A traversal attempt is caught by path_validator inside resolve_manual."""
    with pytest.raises(Exception):  # PathValidationError propagates
        run_pipeline(
            tmp_path,
            VALID_ANSWERS,
            manual_override=True,
            manual_layer_specs=[
                {"stack": "fastapi", "role": "backend", "path": "../escape"},
            ],
            write_telemetry=False,
        )


def test_manual_override_empty_layer_set_rejected(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        manual_override=True,
        manual_layer_specs=[],
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "manual_override_invalid"


def test_manual_override_multilayer_polyglot(tmp_path: Path):
    """Polyglot: next (fullstack) + fastapi (backend) at distinct paths.

    Uses skip_greenfield_gate so the pre-created subdirectories don't trip
    the cwd-state ambiguous classifier (which is a separate concern from
    the cross-layer rule under test here).
    """
    (tmp_path / "apps").mkdir()
    (tmp_path / "services").mkdir()
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        manual_override=True,
        manual_layer_specs=[
            {"stack": "next", "role": "fullstack", "path": "apps"},
            {"stack": "fastapi", "role": "backend", "path": "services"},
        ],
        skip_greenfield_gate=True,
        write_telemetry=False,
    )
    # fullstack-precludes-split rejects this combo per pick-stack §3.4
    assert not result.success
    assert result.reason == "manual_override_invalid"
    assert "fullstack" in result.message


def test_manual_override_writes_rationale_md(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        manual_override=True,
        manual_layer_specs=[{"stack": "fastapi", "role": "backend", "path": "."}],
        write_telemetry=False,
    )
    assert result.rationale_path is not None
    assert result.rationale_path.exists()
    body = result.rationale_path.read_text()
    assert "matched_category_id: manual-override" in body
