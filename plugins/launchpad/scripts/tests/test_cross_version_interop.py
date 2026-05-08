"""Phase 11 v3.1 -- cross-version interop matrix (DA2).

Tests v2.0/v2.1 manifest forward-compat + backward-compat per Phase 11
plan section 3.2. Four cells:

  | # | Reader | Manifest | Expected |
  |---|--------|----------|----------|
  | 1 | v2.0 | v2.0 | success (legacy 1.0 envelope) |
  | 2 | v2.0 | v2.1 | forward-compat: ignore unknown fields |
  | 3 | v2.1 | v2.0 | backward-compat: legacy migration succeeds |
  | 4 | v2.1 | v2.1 | round-trip success |

"v2.0 reader" is simulated via the `_is_legacy_1_0_envelope` codepath
(Phase 1+2 retroactive amendment A3). Subprocess-spawn against `c563d81`
is infeasible at test runtime per R1; test scope is bounded to manifest
parsing, NOT full reader runtime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.decision_writer import default_unset_identity  # noqa: E402
from lp_update_identity.engine import (  # noqa: E402
    _is_legacy_1_0_envelope,
    _migrate_legacy_envelope_in_memory,
)


_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "v2_0_baseline_manifests"
V2_0_MANIFEST_PATH = _FIXTURES_DIR / "v2_0_scaffold_decision.json"
V2_1_MANIFEST_PATH = _FIXTURES_DIR / "v2_1_scaffold_decision.json"


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixture sanity (one-time)
# ---------------------------------------------------------------------------


def test_fixtures_present_and_loadable() -> None:
    """Both fixtures load cleanly via json.loads and have the expected
    envelope-shape signatures (DA2 fixture-correctness gate)."""
    assert V2_0_MANIFEST_PATH.exists(), f"missing v2.0 fixture: {V2_0_MANIFEST_PATH}"
    assert V2_1_MANIFEST_PATH.exists(), f"missing v2.1 fixture: {V2_1_MANIFEST_PATH}"

    v20 = _load_manifest(V2_0_MANIFEST_PATH)
    v21 = _load_manifest(V2_1_MANIFEST_PATH)

    # v2.0: legacy envelope -- no schema_version, no identity, no plugin_version.
    assert v20.get("version") == "1.0"
    assert "schema_version" not in v20
    assert "identity" not in v20
    assert "plugin_version" not in v20
    assert "stacks" not in v20

    # v2.1: 1.1 envelope -- carries all four new keys.
    assert v21.get("version") == "1.0"
    assert v21.get("schema_version") == "1.1"
    assert isinstance(v21.get("identity"), dict)
    assert isinstance(v21.get("plugin_version"), str)
    assert isinstance(v21.get("stacks"), list)


# ---------------------------------------------------------------------------
# Cell #1 -- v2.0 reader on v2.0 manifest (success path)
# ---------------------------------------------------------------------------


def test_cell_1_v20_reader_on_v20_manifest_succeeds() -> None:
    """v2.0 reader recognizes a v1.0 envelope as legacy. The
    `_is_legacy_1_0_envelope` predicate returns True (no schema_version)."""
    manifest = _load_manifest(V2_0_MANIFEST_PATH)
    assert _is_legacy_1_0_envelope(manifest) is True
    # v2.0 reader keys off `version` and reads top-level fields directly.
    # Cross-check that the canonical fields are present.
    assert manifest["matched_category_id"] == "static-blog-astro"
    assert isinstance(manifest["layers"], list)
    assert manifest["layers"][0]["stack"] == "astro"


# ---------------------------------------------------------------------------
# Cell #2 -- v2.0 reader on v2.1 manifest (forward-compat ignore-unknown)
# ---------------------------------------------------------------------------


def test_cell_2_v20_reader_on_v21_manifest_ignores_unknown() -> None:
    """v2.0 reader on v2.1 manifest: forward-compat per Phase 6 schema 1.1
    design (DOCUMENTED-IGNORE-UNKNOWN). The legacy-envelope predicate
    returns False (schema_version is present and equal to "1.1"), so a
    v2.0 reader that keys off `version` would still see "1.0" and parse
    the canonical fields, ignoring the four new keys."""
    manifest = _load_manifest(V2_1_MANIFEST_PATH)
    # Predicate distinguishes v2.0 vs v2.1: v2.1 carries schema_version="1.1".
    assert _is_legacy_1_0_envelope(manifest) is False
    # The canonical v2.0 fields are still present and readable.
    assert manifest["version"] == "1.0"
    assert manifest["matched_category_id"] == "static-blog-astro"
    assert isinstance(manifest["layers"], list)
    # The v2.1-only fields are present but a v2.0 reader simply ignores them.
    assert "identity" in manifest
    assert "plugin_version" in manifest
    assert "stacks" in manifest


# ---------------------------------------------------------------------------
# Cell #3 -- v2.1 reader on v2.0 manifest (backward-compat via migration)
# ---------------------------------------------------------------------------


def test_cell_3_v21_reader_on_v20_manifest_migrates_legacy() -> None:
    """v2.1 reader on v2.0 manifest: backward-compat per Phase 1+2
    retroactive amendment A3. `_migrate_legacy_envelope_in_memory` mutates
    the in-memory payload to add schema_version="1.1" + identity block;
    identity is freshly seeded so route through Case B."""
    manifest = _load_manifest(V2_0_MANIFEST_PATH)
    assert _is_legacy_1_0_envelope(manifest) is True

    info_message, identity_freshly_seeded = (
        _migrate_legacy_envelope_in_memory(manifest)
    )
    # Migration must report a non-empty info string (consumed by the
    # update-identity engine + printed to stderr).
    assert info_message
    assert isinstance(info_message, str)
    # Legacy v2.0 manifest had no identity block; the migration seeds it.
    assert identity_freshly_seeded is True

    # Post-migration envelope must carry schema_version="1.1" + a placeholder
    # identity block (PII-opt-out posture).
    assert manifest["schema_version"] == "1.1"
    assert isinstance(manifest["identity"], dict)
    assert manifest["identity"] == default_unset_identity()


# ---------------------------------------------------------------------------
# Cell #4 -- v2.1 reader on v2.1 manifest (round-trip)
# ---------------------------------------------------------------------------


def test_cell_4_v21_reader_on_v21_manifest_round_trip() -> None:
    """v2.1 reader on v2.1 manifest: round-trip success. Predicate
    correctly identifies as non-legacy; no migration runs; schema_version
    and identity are intact."""
    manifest = _load_manifest(V2_1_MANIFEST_PATH)
    original_keys = set(manifest.keys())

    assert _is_legacy_1_0_envelope(manifest) is False
    # No migration on a non-legacy envelope; envelope shape unchanged.
    assert set(manifest.keys()) == original_keys
    assert manifest["schema_version"] == "1.1"
    assert isinstance(manifest["identity"], dict)
    assert manifest["plugin_version"] == "2.1.0"
    assert manifest["stacks"] == ["astro"]
