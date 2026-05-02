"""End-to-end /lp-pick-stack pipeline test (Phase 2 §4.4 T1).

Exercises the full Step 0-6 pipeline:

- Greenfield gate accepts an empty cwd
- Funnel validation accepts canonical answers
- Matcher selects the expected category
- Rationale.md written with O_CREAT|O_EXCL
- extract_summary populates the structured summary
- Integrity envelope sealed + scaffold-decision.json written atomically
- Round-trip: re-loading and re-canonicalizing matches the on-disk sha256

This is the load-bearing test for the Phase 2 6-step pipeline; failure here
indicates the engine assembly is broken (vs. unit-test failures which point
at an individual module).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash
from lp_pick_stack.engine import Outcome, run_pipeline
from lp_pick_stack.rationale_summary_extractor import SECTION_ORDER


VALID_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}


def test_e2e_static_blog_astro(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript-first islands",
        write_telemetry=False,
    )
    assert result.success
    assert result.outcome == Outcome.ACCEPTED
    assert result.matched_category_id == "static-blog-astro"


def test_e2e_files_persist_to_launchpad_dir(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    assert (tmp_path / ".launchpad" / "scaffold-decision.json").exists()
    assert (tmp_path / ".launchpad" / "rationale.md").exists()


def test_e2e_decision_passes_round_trip_sha256(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    sha = data.pop("sha256")
    assert canonical_hash(data) == sha


def test_e2e_rationale_sha256_matches_file_bytes(tmp_path: Path):
    import hashlib

    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    rationale_bytes = result.rationale_path.read_bytes()
    expected = hashlib.sha256(rationale_bytes).hexdigest()
    data = json.loads(result.decision_path.read_text())
    assert data["rationale_sha256"] == expected


def test_e2e_rationale_summary_has_all_six_sections(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    sections = [s["section"] for s in data["rationale_summary"]]
    assert sections == list(SECTION_ORDER)


def test_e2e_rationale_summary_satisfies_rule_7(tmp_path: Path):
    """HANDSHAKE §4 rule 7: ≥1 section MUST contain ≥1 non-empty bullet."""
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    nonempty = [s for s in data["rationale_summary"] if s["bullets"]]
    assert nonempty, "rule 7 violation: all rationale_summary sections empty"


def test_e2e_bound_cwd_triple_matches_runtime(tmp_path: Path):
    import os

    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    expected_realpath = os.path.realpath(str(tmp_path))
    expected_stat = os.stat(expected_realpath)
    assert data["bound_cwd"]["realpath"] == expected_realpath
    assert data["bound_cwd"]["st_dev"] == expected_stat.st_dev
    assert data["bound_cwd"]["st_ino"] == expected_stat.st_ino


def test_e2e_nonce_is_uuid_hex(tmp_path: Path):
    import re

    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    assert re.fullmatch(r"^[0-9a-f]{32}$", data["nonce"])


def test_e2e_two_runs_yield_distinct_nonces(tmp_path: Path):
    # Each run on a fresh tmp dir produces a fresh UUIDv4 nonce
    import tempfile

    nonces = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as td:
            result = run_pipeline(
                Path(td),
                VALID_ANSWERS,
                project_description="A static blog with TypeScript islands",
                write_telemetry=False,
            )
            data = json.loads(result.decision_path.read_text())
            nonces.append(data["nonce"])
    assert nonces[0] != nonces[1]


def test_e2e_generated_by_field(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    assert data["generated_by"] == "/lp-pick-stack"


def test_e2e_rationale_path_field(tmp_path: Path):
    result = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript islands",
        write_telemetry=False,
    )
    data = json.loads(result.decision_path.read_text())
    assert data["rationale_path"] == ".launchpad/rationale.md"
