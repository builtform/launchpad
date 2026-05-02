"""--no-rationale flag end-to-end test (Phase 2 §4.4 T6).

When the user passes `--no-rationale`, the engine MUST:

- Skip writing rationale.md
- Set rationale_sha256 to the empty-file sha256 (per Phase 2 handoff §6
  acceptance criterion: "rationale_sha256 is empty-string-hash")
- Still write a valid scaffold-decision.json with degraded-mode summary
- Set the rationale_summary array to a degraded-mode placeholder satisfying
  HANDSHAKE §4 rule 7 (≥1 non-empty bullet)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.decision_writer import EMPTY_FILE_SHA256
from lp_pick_stack.engine import Outcome, run_pipeline


VALID_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}


def test_no_rationale_skips_file_write(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        no_rationale=True,
        write_telemetry=False,
    )
    assert result.success
    assert result.rationale_path is None
    assert not (tmp_path / ".launchpad" / "rationale.md").exists()


def test_no_rationale_decision_file_still_written(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        no_rationale=True,
        write_telemetry=False,
    )
    assert result.decision_path is not None
    assert result.decision_path.exists()


def test_no_rationale_sha256_is_empty_file_hash(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        no_rationale=True,
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    assert data["rationale_sha256"] == EMPTY_FILE_SHA256
    assert data["rationale_sha256"] == hashlib.sha256(b"").hexdigest()


def test_no_rationale_summary_has_degraded_bullets(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        no_rationale=True,
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    summary = data["rationale_summary"]
    # All 6 sections present
    assert len(summary) == 6
    # ≥1 non-empty bullet (rule 7)
    nonempty = [s for s in summary if s["bullets"]]
    assert nonempty
    # Notes section signals --no-rationale
    notes = next(s for s in summary if s["section"] == "notes")
    assert any("no-rationale" in b for b in notes["bullets"])


def test_no_rationale_decision_round_trip_sha256(tmp_path: Path):
    from decision_integrity import canonical_hash

    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        no_rationale=True,
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    sha = data.pop("sha256")
    assert canonical_hash(data) == sha


def test_no_rationale_outcome_still_accepted(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        no_rationale=True,
        write_telemetry=False,
    )
    assert result.outcome == Outcome.ACCEPTED
