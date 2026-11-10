"""Ambiguity-cluster handling test (Phase 2 §4.4 T4).

When a category selection needs a choice, the engine returns the full
shortlist with its cluster metadata. The user's chosen id selects from
that entire shortlist, including candidates in different clusters.

This is the load-bearing test for HANDSHAKE §4 rule 7 (ambiguity clusters)
+ pick-stack plan §3.1 Step 5 (tiebreak prompt).
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


def _ambiguous_describe() -> str:
    """Describe text that triggers ≥2 categories in static-blog-trio."""
    return "Static blog using TypeScript islands and Hugo for build speed"


def test_ambiguity_surfaces_without_choice(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description=_ambiguous_describe(),
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "category_selection_required"
    assert len(result.candidates) >= 2
    # No decision file written
    assert not (tmp_path / ".launchpad" / "scaffold-decision.json").exists()


def test_ambiguity_resolved_with_chosen_id(tmp_path: Path):
    # Pre-resolve the chosen_category_id; engine writes the decision
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description=_ambiguous_describe(),
        chosen_category_id="static-blog-hugo",
        write_telemetry=False,
    )
    assert result.success, result.message
    assert result.matched_category_id == "static-blog-hugo"


def test_invalid_chosen_category_id_rejected(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description=_ambiguous_describe(),
        chosen_category_id="not-in-cluster",
        write_telemetry=False,
    )
    assert not result.success
    assert result.reason == "category_choice_invalid"


def test_candidates_carry_cluster_metadata(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description=_ambiguous_describe(),
        write_telemetry=False,
    )
    candidates = {c.id: c for c in result.candidates}
    assert candidates["static-blog-astro"].cluster == "static-blog-trio"
    assert candidates["static-blog-hugo"].cluster == "static-blog-trio"
