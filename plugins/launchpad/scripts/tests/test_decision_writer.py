"""Tests for lp_pick_stack.decision_writer (Phase 2 §4.1 Step 6)."""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash
from lp_pick_stack.decision_writer import (
    DECISION_FILENAME,
    DecisionWriteError,
    EMPTY_FILE_SHA256,
    RATIONALE_FILENAME,
    build_decision_payload,
    compute_bound_cwd,
    seal_decision_payload,
    write_decision_atomic,
    write_decision_file,
    write_rationale_atomic,
)


SUMMARY = [
    {"section": "project-understanding", "bullets": ["A static blog."]},
    {"section": "matched-category", "bullets": ["static-blog-astro"]},
    {"section": "stack", "bullets": ["astro as frontend at ."]},
    {"section": "why-this-fits", "bullets": ["TypeScript-first islands."]},
    {"section": "alternatives", "bullets": ["eleventy: TS preferred."]},
    {"section": "notes", "bullets": ["BL-105."]},
]
LAYERS = [{"stack": "astro", "role": "frontend", "path": ".", "options": {"template": "blog"}}]


# --- compute_bound_cwd ---


def test_compute_bound_cwd_triple(tmp_path: Path):
    bc = compute_bound_cwd(tmp_path)
    assert "realpath" in bc
    assert "st_dev" in bc
    assert "st_ino" in bc
    assert isinstance(bc["st_dev"], int)
    assert isinstance(bc["st_ino"], int)


def test_compute_bound_cwd_missing_path_raises(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(DecisionWriteError) as exc:
        compute_bound_cwd(missing)
    assert exc.value.reason == "bound_cwd_compute_failed"


# --- build_decision_payload + seal ---


def test_build_payload_omits_brainstorm_session_id(tmp_path: Path):
    payload = build_decision_payload(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    # Per HANDSHAKE §1.5 strip-back: brainstorm_session_id MUST NOT be present
    assert "brainstorm_session_id" not in payload


def test_build_payload_required_fields(tmp_path: Path):
    payload = build_decision_payload(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    for key in ("version", "layers", "monorepo", "matched_category_id",
                "rationale_path", "rationale_sha256", "rationale_summary",
                "generated_by", "generated_at", "nonce", "bound_cwd"):
        assert key in payload, f"missing {key}"
    assert payload["version"] == "1.0"
    assert payload["generated_by"] == "/lp-pick-stack"
    assert payload["rationale_path"] == ".launchpad/rationale.md"
    assert payload["monorepo"] is False  # single layer


def test_monorepo_default_when_multi_layer(tmp_path: Path):
    multi_layers = [
        {"stack": "next", "role": "frontend", "path": "apps/web", "options": {}},
        {"stack": "fastapi", "role": "backend", "path": "services/api", "options": {}},
    ]
    payload = build_decision_payload(
        layers=multi_layers,
        matched_category_id="polyglot-next-fastapi",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    assert payload["monorepo"] is True


def test_seal_adds_sha256(tmp_path: Path):
    payload = build_decision_payload(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    sealed = seal_decision_payload(payload)
    assert "sha256" in sealed
    # Verify recompute matches
    payload_no_sha = {k: v for k, v in sealed.items() if k != "sha256"}
    assert sealed["sha256"] == canonical_hash(payload_no_sha)


def test_seal_rejects_double_seal(tmp_path: Path):
    payload = build_decision_payload(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    sealed = seal_decision_payload(payload)
    with pytest.raises(ValueError):
        seal_decision_payload(sealed)


# --- atomic write ---


def test_write_decision_atomic_creates_file(tmp_path: Path):
    payload = build_decision_payload(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    sealed = seal_decision_payload(payload)
    target = write_decision_atomic(sealed, tmp_path)
    assert target.exists()
    assert target.name == DECISION_FILENAME


def test_write_decision_file_mode_0o600(tmp_path: Path):
    target, _ = write_decision_file(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600


def test_write_decision_o_excl_refuses_existing(tmp_path: Path):
    write_decision_file(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    with pytest.raises(DecisionWriteError) as exc:
        write_decision_file(
            layers=LAYERS,
            matched_category_id="static-blog-astro",
            rationale_summary=SUMMARY,
            rationale_sha256=EMPTY_FILE_SHA256,
            cwd=tmp_path,
        )
    assert exc.value.reason == "scaffold_decision_already_exists"


def test_written_file_canonical_json(tmp_path: Path):
    target, sealed = write_decision_file(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    bytes_on_disk = target.read_bytes()
    expected_bytes = json.dumps(
        sealed, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    assert bytes_on_disk == expected_bytes


def test_round_trip_sha256_validates(tmp_path: Path):
    target, _ = write_decision_file(
        layers=LAYERS,
        matched_category_id="static-blog-astro",
        rationale_summary=SUMMARY,
        rationale_sha256=EMPTY_FILE_SHA256,
        cwd=tmp_path,
    )
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    sha = on_disk.pop("sha256")
    assert canonical_hash(on_disk) == sha


# --- rationale.md atomic write ---


def test_write_rationale_atomic_creates_file(tmp_path: Path):
    target, sha = write_rationale_atomic("hello world\n", tmp_path)
    assert target.exists()
    assert target.name == RATIONALE_FILENAME
    assert target.read_text() == "hello world\n"
    # sha256 of "hello world\n"
    import hashlib
    assert sha == hashlib.sha256(b"hello world\n").hexdigest()


def test_write_rationale_o_excl_refuses_existing(tmp_path: Path):
    write_rationale_atomic("first\n", tmp_path)
    with pytest.raises(DecisionWriteError) as exc:
        write_rationale_atomic("second\n", tmp_path)
    assert exc.value.reason == "scaffold_decision_already_exists"


def test_empty_file_sha256_constant():
    import hashlib
    assert EMPTY_FILE_SHA256 == hashlib.sha256(b"").hexdigest()
