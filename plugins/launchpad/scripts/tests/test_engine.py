"""Tests for lp_pick_stack.engine (Phase 2 §4.1 orchestrator)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.engine import (
    COMMAND_NAME,
    Outcome,
    PipelineResult,
    run_pipeline,
)


VALID_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}


# --- happy path ---


def test_run_pipeline_static_blog_astro(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript-first islands",
        write_telemetry=False,
    )
    assert result.success
    assert result.outcome == Outcome.ACCEPTED
    assert result.matched_category_id == "static-blog-astro"
    assert result.decision_path is not None
    assert result.decision_path.exists()
    assert result.rationale_path is not None
    assert result.rationale_path.exists()


def test_pipeline_writes_valid_decision_json(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    assert result.success
    data = json.loads(result.decision_path.read_text())
    # All required fields per HANDSHAKE §4
    for key in ("version", "layers", "monorepo", "matched_category_id",
                "rationale_path", "rationale_sha256", "rationale_summary",
                "generated_by", "generated_at", "nonce", "bound_cwd",
                "sha256"):
        assert key in data
    # brainstorm_session_id MUST NOT be present (BL-235 deferred)
    assert "brainstorm_session_id" not in data


# --- ambiguity cluster ---


def test_pipeline_ambiguity_cluster_requires_choice(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="Blog using both TypeScript and Hugo for build speed",
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "category_selection_required"
    assert len(result.candidates) >= 2


def test_pipeline_ambiguity_resolved_with_choice(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="Blog using both TypeScript and Hugo for build speed",
        chosen_category_id="static-blog-hugo",
        write_telemetry=False,
    )
    assert result.success, result.message
    assert result.matched_category_id == "static-blog-hugo"


# --- no-match ---


def test_pipeline_no_match(tmp_path: Path):
    # Q1 + Q4 combo with no describe text → zero matches (no category fires
    # on desktop-app + elixir at v2.0)
    result = run_pipeline(
        tmp_path,
        {
            "Q1": "desktop-app",
            "Q2": "yes-needed",
            "Q3": "no",
            "Q4": "elixir",
            "Q5": "container",
        },
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "category_no_match"


# --- manual override ---


def test_pipeline_manual_override(tmp_path: Path):
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


def test_pipeline_manual_override_invalid_combination(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        manual_override=True,
        manual_layer_specs=[
            {"stack": "astro", "role": "backend", "path": "."},  # invalid combo
        ],
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "manual_override_invalid"


# --- --no-rationale ---


def test_pipeline_no_rationale_flag(tmp_path: Path):
    from lp_pick_stack.decision_writer import EMPTY_FILE_SHA256

    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        no_rationale=True,
        write_telemetry=False,
    )
    assert result.success, result.message
    assert result.rationale_path is None  # not written
    assert not (tmp_path / ".launchpad" / "rationale.md").exists()
    data = json.loads(result.decision_path.read_text())
    assert data["rationale_sha256"] == EMPTY_FILE_SHA256


# --- duplicate-write refusal ---


def test_pipeline_refuses_when_decision_exists(tmp_path: Path):
    # First run succeeds
    first = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    assert first.success
    # Second run hits rationale.md O_EXCL refusal first
    second = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    assert not second.success
    assert second.reason == "scaffold_decision_already_exists"


# --- input validation ---


def test_pipeline_rejects_invalid_answers(tmp_path: Path):
    bad = {**VALID_ANSWERS, "Q1": "quantum-shape"}
    result = run_pipeline(tmp_path, bad, write_telemetry=False)
    assert not result.success
    assert result.reason == "answer_validation_failed"


# --- result shape ---


def test_pipeline_result_carries_elapsed(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    assert result.elapsed_seconds >= 0


def test_command_name_constant():
    assert COMMAND_NAME == "/lp-pick-stack"


@pytest.mark.parametrize(
    ("case", "choice", "reason", "matched_id"),
    [
        ("A", None, "category_selection_required", None),
        ("D", None, "category_selection_required", None),
        ("D", "polyglot-next-hono", None, "polyglot-next-hono"),
        ("D", "static-blog-astro", "category_choice_invalid", None),
        ("E", None, None, "polyglot-next-hono"),
        ("A", "polyglot-next-hono", None, "polyglot-next-hono"),
    ],
)
def test_pipeline_category_selection(tmp_path: Path, case, choice, reason, matched_id):
    from test_matcher import _CASE_A, _CASE_D, _INFORMED_DESCRIPTION
    from lp_pick_stack.engine import _load_category_patterns
    from lp_pick_stack.matcher import shortlist_categories

    answers = {
        "A": _CASE_A,
        "D": _CASE_D,
        "E": dict(_CASE_D, describe=_INFORMED_DESCRIPTION),
    }[case]
    expected = shortlist_categories(answers, _load_category_patterns(None))
    result = run_pipeline(tmp_path, answers, chosen_category_id=choice)
    assert result.reason == reason
    assert result.matched_category_id == matched_id
    assert result.success == (matched_id is not None)
    if reason:
        assert result.outcome == Outcome.ABORTED
        assert result.candidates == expected
        assert not (tmp_path / ".launchpad" / "scaffold-decision.json").exists()
        assert not (tmp_path / ".harness" / "observations").exists()
        if case == "D":
            assert [c.id for c in result.candidates] == [
                "polyglot-next-hono", "saas-next-supabase", "multi-frontend-astro-next",
            ]
    else:
        decision = json.loads(result.decision_path.read_text())
        alternatives = next(s["bullets"] for s in decision["rationale_summary"] if s["section"] == "alternatives")
        others = [c for c in expected if c.id != matched_id]
        assert len(alternatives) == len(others)
        for candidate, bullet in zip(others, alternatives, strict=True):
            assert bullet == f"{candidate.name} ({candidate.id}): also qualified for these answers, not chosen."
            assert 31 <= len(bullet) <= 240
            assert "<" not in bullet and ">" not in bullet and "`" not in bullet
