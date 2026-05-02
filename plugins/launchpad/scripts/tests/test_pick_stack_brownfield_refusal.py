"""Brownfield-cwd refusal test (Phase 2 §4.4 T3).

When cwd_state.cwd_state(cwd) == "brownfield" or "ambiguous", the engine MUST
refuse at Step 0 BEFORE any decision-file write occurs (HANDSHAKE §8 +
pick-stack plan §3.1 Step 0.5).

Refusal carries a structured reason that the markdown command surfaces with
a hint pointing at /lp-define (the brownfield happy path).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.engine import Outcome, run_pipeline


VALID_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}


def test_brownfield_cwd_refused(tmp_path: Path):
    # Plant a brownfield manifest
    (tmp_path / "package.json").write_text('{"name": "existing-project"}')
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog",
        write_telemetry=False,
    )
    assert not result.success
    assert result.outcome == Outcome.ABORTED
    assert result.reason == "cwd_state_brownfield_or_ambiguous"
    # Engine never wrote a decision file
    assert not (tmp_path / ".launchpad" / "scaffold-decision.json").exists()
    assert not (tmp_path / ".launchpad" / "rationale.md").exists()


def test_brownfield_message_points_at_lp_define(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "existing"}')
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog",
        write_telemetry=False,
    )
    assert "/lp-define" in result.message


def test_ambiguous_cwd_refused(tmp_path: Path):
    # Plant an unrecognized large file (>100 bytes) → ambiguous
    (tmp_path / "mystery.dat").write_bytes(b"x" * 500)
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog",
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "cwd_state_brownfield_or_ambiguous"


def test_skip_greenfield_gate_for_test_hook(tmp_path: Path):
    """The skip_greenfield_gate hook lets unit tests bypass the gate."""
    (tmp_path / "package.json").write_text('{"name": "existing"}')
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        skip_greenfield_gate=True,
        write_telemetry=False,
    )
    # With the gate skipped, the engine proceeds to match + write
    assert result.success or result.reason != "cwd_state_brownfield_or_ambiguous"


def test_greenfield_passes_gate(tmp_path: Path):
    # Empty cwd → "empty" → gate passes → engine proceeds to match
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    assert result.success
