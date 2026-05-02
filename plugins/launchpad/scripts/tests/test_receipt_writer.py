"""Tests for lp_scaffold_stack.receipt_writer (Phase 3 S7)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash
from lp_scaffold_stack.receipt_writer import (
    RECEIPT_FILENAME,
    ReceiptWriteError,
    build_receipt_payload,
    seal_receipt_payload,
    write_receipt,
)


def _fixture_layer():
    return {
        "stack": "astro",
        "path": ".",
        "scaffolder_used": "orchestrate",
        "files_created": ["package.json", "src/pages/index.astro"],
    }


def test_build_payload_shape():
    payload = build_receipt_payload(
        decision_sha256="a" * 64,
        decision_nonce="b" * 32,
        layers_materialized=[_fixture_layer()],
        cross_cutting_files=["lefthook.yml"],
        toolchains_detected=["node"],
        secret_scan_passed=True,
    )
    assert payload["version"] == "1.0"
    assert payload["decision_sha256"] == "a" * 64
    assert payload["decision_nonce"] == "b" * 32
    assert payload["secret_scan_passed"] is True
    assert payload["tier1_governance_summary"]["architecture_docs_rendered"] == 8
    assert "secret-scan" in payload["tier1_governance_summary"]["lefthook_hooks"]


def test_seal_computes_canonical_hash():
    payload = build_receipt_payload(
        decision_sha256="a" * 64, decision_nonce="b" * 32,
        layers_materialized=[_fixture_layer()],
        cross_cutting_files=["lefthook.yml"], toolchains_detected=["node"],
        secret_scan_passed=True,
    )
    sealed = seal_receipt_payload(payload)
    expected = canonical_hash({k: v for k, v in sealed.items() if k != "sha256"})
    assert sealed["sha256"] == expected


def test_seal_rejects_pre_sealed():
    payload = build_receipt_payload(
        decision_sha256="a" * 64, decision_nonce="b" * 32,
        layers_materialized=[_fixture_layer()],
        cross_cutting_files=["lefthook.yml"], toolchains_detected=["node"],
        secret_scan_passed=True,
    )
    payload["sha256"] = "pre-sealed"
    with pytest.raises(ValueError):
        seal_receipt_payload(payload)


def test_atomic_write_then_read_back(tmp_path: Path):
    target, sealed = write_receipt(
        decision_sha256="a" * 64, decision_nonce="b" * 32,
        layers_materialized=[_fixture_layer()],
        cross_cutting_files=["lefthook.yml"], toolchains_detected=["node"],
        secret_scan_passed=True, cwd=tmp_path,
    )
    assert target.name == RECEIPT_FILENAME
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert on_disk == sealed
    # Self-hash matches.
    expected = canonical_hash({k: v for k, v in on_disk.items() if k != "sha256"})
    assert on_disk["sha256"] == expected


def test_collision_refuses(tmp_path: Path):
    target, _ = write_receipt(
        decision_sha256="a" * 64, decision_nonce="b" * 32,
        layers_materialized=[_fixture_layer()],
        cross_cutting_files=["lefthook.yml"], toolchains_detected=["node"],
        secret_scan_passed=True, cwd=tmp_path,
    )
    assert target.exists()
    with pytest.raises(ReceiptWriteError) as exc:
        write_receipt(
            decision_sha256="a" * 64, decision_nonce="b" * 32,
            layers_materialized=[_fixture_layer()],
            cross_cutting_files=["lefthook.yml"], toolchains_detected=["node"],
            secret_scan_passed=True, cwd=tmp_path,
        )
    assert exc.value.reason == "scaffold_receipt_already_exists"


def test_file_mode_0o600(tmp_path: Path):
    target, _ = write_receipt(
        decision_sha256="a" * 64, decision_nonce="b" * 32,
        layers_materialized=[_fixture_layer()],
        cross_cutting_files=["lefthook.yml"], toolchains_detected=["node"],
        secret_scan_passed=True, cwd=tmp_path,
    )
    import stat
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600
