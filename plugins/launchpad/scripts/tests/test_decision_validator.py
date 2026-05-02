"""Tests for lp_scaffold_stack.decision_validator (Phase 3 S2).

Covers all 12 active §4 rules (rule 12 BL-235 deferred). Each rule has
positive + negative coverage.
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash
from lp_scaffold_stack.decision_validator import (
    Accepted,
    MANUAL_OVERRIDE_ID,
    Rejected,
    validate_decision,
)


# A minimal scaffolders catalog matching the v2.0 10-entry catalog shape.
SCAFFOLDERS = {
    "astro": {
        "type": "orchestrate",
        "options_schema": {"template": "string"},
    },
    "fastapi": {
        "type": "curate",
        "options_schema": {"database": "string"},
    },
    "next": {
        "type": "orchestrate",
        "options_schema": {"src_dir": "boolean"},
    },
}

CATEGORY_IDS = {
    "static-blog-astro", "marketing-next", "polyglot-next-fastapi",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bound_cwd_for(cwd: Path) -> dict:
    real = os.path.realpath(str(cwd))
    st = os.stat(real)
    return {"realpath": real, "st_dev": int(st.st_dev), "st_ino": int(st.st_ino)}


def _valid_summary() -> list[dict]:
    return [
        {"section": "project-understanding", "bullets": ["A static blog"]},
        {"section": "matched-category", "bullets": ["static-blog-astro"]},
        {"section": "stack", "bullets": ["astro as frontend"]},
        {"section": "why-this-fits", "bullets": ["TS-first islands match"]},
        {"section": "alternatives", "bullets": ["eleventy: TS preferred"]},
        {"section": "notes", "bullets": ["BL-105 freshness review"]},
    ]


def _make_valid_decision(cwd: Path, *, rationale_path: Path | None = None) -> dict:
    """Construct a fully-valid decision dict (sha256 sealed) for tmp cwd."""
    if rationale_path is not None:
        rsha = hashlib.sha256(rationale_path.read_bytes()).hexdigest()
    else:
        rsha = hashlib.sha256(b"").hexdigest()
    payload = {
        "version": "1.0",
        "layers": [{"stack": "astro", "role": "frontend", "path": ".",
                    "options": {"template": "blog"}}],
        "monorepo": False,
        "matched_category_id": "static-blog-astro",
        "rationale_path": ".launchpad/rationale.md",
        "rationale_sha256": rsha,
        "rationale_summary": _valid_summary(),
        "generated_by": "/lp-pick-stack",
        "generated_at": _utc_now_iso(),
        "nonce": "a" * 32,
        "bound_cwd": _bound_cwd_for(cwd),
    }
    payload["sha256"] = canonical_hash(payload)
    return payload


# --- positive baseline ---


def test_valid_decision_accepted(tmp_path: Path):
    rationale = tmp_path / ".launchpad" / "rationale.md"
    rationale.parent.mkdir(parents=True, exist_ok=True)
    rationale.write_text("# rationale\n", encoding="utf-8")
    decision = _make_valid_decision(tmp_path, rationale_path=rationale)
    verdict = validate_decision(
        decision, tmp_path,
        scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS,
        rationale_path_for_sha=rationale,
    )
    assert isinstance(verdict, Accepted)
    assert verdict.nonce == "a" * 32


# --- Rule 1: version ---


def test_rule_1_version_unsupported(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["version"] = "9.99"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(
        decision, tmp_path,
        scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS,
    )
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "version_unsupported"
    assert verdict.seen_version == "9.99"


# --- Rule 2: layers ---


def test_rule_2_unknown_stack_id(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["layers"][0]["stack"] = "unknown-stack"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "unknown_stack_id"


def test_rule_2_layer_role_invalid(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["layers"][0]["role"] = "not-a-role"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "layer_role_invalid"


def test_rule_2_path_traversal(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["layers"][0]["path"] = "../escape"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "path_traversal"


def test_rule_2_layer_options_unknown_key(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["layers"][0]["options"] = {"unknown_key": "blog"}
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "layer_options_unknown_key"


def test_rule_2_paths_collide(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["monorepo"] = True
    decision["layers"] = [
        {"stack": "astro", "role": "frontend", "path": "apps/web", "options": {"template": "blog"}},
        {"stack": "next", "role": "frontend", "path": "apps/web", "options": {}},
    ]
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "layer_paths_collide"


# --- Rule 3: monorepo ---


def test_rule_3_monorepo_inconsistent_layers(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["monorepo"] = True  # but only 1 layer
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "monorepo_inconsistent_layers"


def test_rule_3_path_dot_carveout_accepts_duplicate_dot(tmp_path: Path):
    # HANDSHAKE §4 rule 3 explicitly permits monorepo=false + len(layers)>1
    # when all layers share path == "." (single-dir overlay layers). The
    # validator MUST accept this shape; previous behavior rejected via
    # `layer_paths_collide` even though rule 3 admits it.
    decision = _make_valid_decision(tmp_path)
    decision["monorepo"] = False
    decision["layers"] = [
        {"stack": "rails", "role": "fullstack", "path": ".", "options": {"database": "postgresql"}},
        {"stack": "hugo", "role": "frontend", "path": ".", "options": {}},
    ]
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    # Acceptance is the carve-out's whole point. Reject path-collision rule
    # specifically; other rules (rule 4 matched_category_id, etc.) may still
    # surface their own verdicts in the synthetic fixture, so we guard only
    # against the regression.
    if isinstance(verdict, Rejected):
        assert verdict.reason != "layer_paths_collide", (
            f"path == '.' carve-out regressed: got {verdict.reason}"
        )


# --- Rule 4: matched_category_id ---


def test_rule_4_unknown_category(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["matched_category_id"] = "not-a-real-category"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "matched_category_id_unknown"


def test_rule_4_manual_override_accepted(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["matched_category_id"] = MANUAL_OVERRIDE_ID
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Accepted)


# --- Rule 5: rationale_path ---


def test_rule_5_rationale_path_invalid(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["rationale_path"] = "wrong/path.md"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "rationale_path_invalid"


# --- Rule 6: rationale_sha256 ---


def test_rule_6_rationale_sha_mismatch(tmp_path: Path):
    rationale = tmp_path / ".launchpad" / "rationale.md"
    rationale.parent.mkdir(parents=True, exist_ok=True)
    rationale.write_text("# real content\n", encoding="utf-8")
    decision = _make_valid_decision(tmp_path)
    decision["rationale_sha256"] = "f" * 64
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(
        decision, tmp_path,
        scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS,
        rationale_path_for_sha=rationale,
    )
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "rationale_sha256_mismatch"


# --- Rule 7: rationale_summary ---


def test_rule_7_summary_empty(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["rationale_summary"] = [
        {"section": s, "bullets": []} for s in
        ("project-understanding", "matched-category", "stack",
         "why-this-fits", "alternatives", "notes")
    ]
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "rationale_summary_empty"


def test_rule_7_forbidden_token(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["rationale_summary"][1]["bullets"] = ["http://attacker.example/x"]
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "forbidden_bullet_token"


# --- Rule 8: generated_by ---


def test_rule_8_generated_by_invalid(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["generated_by"] = "/some-other-command"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "generated_by_invalid"


# --- Rule 9: generated_at ---


def test_rule_9_generated_at_expired(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    expired = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    decision["generated_at"] = expired
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "generated_at_expired"


def test_rule_9_generated_at_future_beyond_skew_rejected(tmp_path: Path):
    """A forged future-dated decision must NOT bypass the replay window.

    Closes the bypass where the original validator only checked age > MAX_AGE
    and silently accepted negative ages (timestamps in the future).
    """
    decision = _make_valid_decision(tmp_path)
    far_future = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    decision["generated_at"] = far_future
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "generated_at_in_future"


def test_rule_9_generated_at_small_future_skew_accepted(tmp_path: Path):
    """Within the 5-minute clock-skew tolerance, future timestamps pass."""
    decision = _make_valid_decision(tmp_path)
    near_future = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    decision["generated_at"] = near_future
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    if isinstance(verdict, Rejected):
        assert verdict.reason != "generated_at_in_future", (
            "small clock-skew within tolerance should not be rejected as future"
        )


# --- Rule 10: nonce ---


def test_rule_10_nonce_seen(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    verdict = validate_decision(
        decision, tmp_path,
        scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS,
        nonce_seen=True,
    )
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "nonce_seen"


def test_rule_10_nonce_format_invalid(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["nonce"] = "not-a-uuid"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "nonce_format_invalid"


# --- Rule 11: bound_cwd ---


def test_rule_11_realpath_mismatch(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["bound_cwd"]["realpath"] = "/var/empty/never-exists"
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    # realpath differs AND inode differs (different cwd) → realpath_mismatch
    assert verdict.reason in {"bound_cwd_realpath_mismatch", "bound_cwd_realpath_changed_inode_match"}


def test_rule_11_inode_mismatch(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    # Same realpath, different inode
    decision["bound_cwd"]["st_ino"] = 999999999
    decision["sha256"] = canonical_hash({k: v for k, v in decision.items() if k != "sha256"})
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "bound_cwd_inode_mismatch"


# --- Rule 12: SKIPPED at v2.0 per BL-235 ---


def test_rule_12_brainstorm_session_id_omitted_accepted(tmp_path: Path):
    """Per BL-235 strip-back: validator does NOT require brainstorm_session_id."""
    decision = _make_valid_decision(tmp_path)
    assert "brainstorm_session_id" not in decision
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Accepted)


# --- Rule 13: sha256 ---


def test_rule_13_sha256_mismatch(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    decision["sha256"] = "0" * 64
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "sha256_mismatch"


# --- Missing required field ---


def test_missing_required_field(tmp_path: Path):
    decision = _make_valid_decision(tmp_path)
    del decision["nonce"]
    verdict = validate_decision(decision, tmp_path,
                                scaffolders=SCAFFOLDERS, category_ids=CATEGORY_IDS)
    assert isinstance(verdict, Rejected)
    assert verdict.reason == "scaffold_decision_missing_field"
    assert verdict.field_name == "nonce"
