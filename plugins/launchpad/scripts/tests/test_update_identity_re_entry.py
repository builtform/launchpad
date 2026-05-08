"""Phase 11 v3.1 -- /lp-update-identity 5-case re-entry consolidated +
case-pair transitions (DA6).

Phase 10 ships per-case tests in `test_update_identity_engine.py` for
A/B/C/D/E. Phase 11 consolidates these into a single parameterized
matrix and adds case-pair transition coverage that the per-case tests
do not exercise.

Plan section 5: +5 (parameterized cases) + 4 (case-pair transitions) = 9.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.decision_writer import (  # noqa: E402
    default_unset_identity,
    write_decision_file,
)
from lp_update_identity import (  # noqa: E402
    IdentityUpdateStatus,
)
from lp_update_identity.engine import (  # noqa: E402
    _detect_re_entry_case,
    _is_legacy_1_0_envelope,
    _migrate_legacy_envelope_in_memory,
    run_update_identity,
)


def _mit_identity() -> dict[str, Any]:
    return {
        "pii_opt_in": True,
        "project_name": "demo-project",
        "email": "owner@example.com",
        "copyright_holder": "Demo Owner",
        "repo_url": "https://github.com/example/demo",
        "license": "MIT",
        "license_other_body": "",
    }


def _layers() -> list[dict[str, Any]]:
    return [{"stack": "next", "role": "fullstack", "path": ".", "options": {}}]


def _seed_full_scaffold(tmp_path: Path, identity: Mapping[str, Any] | None = None) -> Path:
    """Seed scaffold-decision.json + render kernel files + seal kernel_render_state."""
    (tmp_path / ".launchpad").mkdir(exist_ok=True)
    write_decision_file(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=[
            {"category_id": "next-fullstack", "rank": 1, "score": 100, "reasons": []},
        ],
        rationale_sha256="0" * 64,
        cwd=tmp_path,
        identity=identity if identity is not None else _mit_identity(),
    )
    from plugin_default_generators.kernel_renderer import KernelRenderer
    from lp_pick_stack.decision_writer import re_seal_decision_atomic
    _rendered, kernel_render_state = KernelRenderer().render_all(
        tmp_path, identity if identity is not None else _mit_identity(),
    )

    def _set_state(payload):
        payload["kernel_render_state"] = kernel_render_state

    re_seal_decision_atomic(tmp_path, update_fn=_set_state)
    return tmp_path


# ---------------------------------------------------------------------------
# Parameterized 5-case detection matrix (DA6 consolidation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_id, payload_factory, seed_brownfield, expected",
    [
        # Case A: missing scaffold-decision payload + no brownfield flag.
        ("A", lambda: None, False, "A"),
        # Case B: legacy v1.0 envelope (schema_version absent) -- no identity.
        ("B", lambda: {"version": "1.0"}, False, "B"),
        # Case C: 1.1 envelope + identity + render-state present (UPDATED).
        ("C", lambda: {
            "schema_version": "1.1",
            "identity": _mit_identity(),
            "kernel_render_state": [{"path": "LICENSE"}],
        }, False, "UPDATED"),
        # Case D: missing payload + brownfield seed flag.
        ("D", lambda: None, True, "D"),
        # Case E: 1.1 envelope + identity but NO kernel_render_state.
        ("E", lambda: {
            "schema_version": "1.1",
            "identity": _mit_identity(),
        }, False, "E"),
    ],
)
def test_re_entry_case_matrix(
    case_id: str,
    payload_factory,
    seed_brownfield: bool,
    expected: str,
) -> None:
    """DA6 consolidated 5-case parameterized matrix. Per-case tests in
    `test_update_identity_engine.py` remain authoritative for individual
    case correctness; this test guards against case-detection drift
    across the matrix."""
    payload = payload_factory()
    case = _detect_re_entry_case(payload, seed_brownfield=seed_brownfield)
    assert case == expected, (
        f"case {case_id} detection drift: expected {expected!r}, got {case!r}"
    )


# ---------------------------------------------------------------------------
# Case-pair transitions (4 tests; DA6 surplus coverage)
# ---------------------------------------------------------------------------


def test_transition_A_to_B_legacy_envelope_appears_after_seed(tmp_path: Path) -> None:
    """A -> B: Initially no scaffold-decision (Case A). After a v2.0-era
    /lp-pick-stack seeds a legacy v1.0 envelope, re-detection routes
    through Case B."""
    case_initial = _detect_re_entry_case(None, seed_brownfield=False)
    assert case_initial == "A"

    # Simulate v2.0-era seed: legacy 1.0 envelope without identity block.
    legacy_payload = {"version": "1.0", "layers": _layers()}
    case_after_seed = _detect_re_entry_case(legacy_payload, seed_brownfield=False)
    assert case_after_seed == "B"
    assert _is_legacy_1_0_envelope(legacy_payload) is True


def test_transition_B_to_UPDATED_after_legacy_migration() -> None:
    """B -> UPDATED: legacy v1.0 envelope migrates in-memory to v1.1 with
    seeded identity; once kernel_render_state is also sealed (post-render),
    the case becomes UPDATED."""
    legacy_payload = {"version": "1.0", "layers": _layers()}
    case_b = _detect_re_entry_case(legacy_payload, seed_brownfield=False)
    assert case_b == "B"

    info, freshly_seeded = _migrate_legacy_envelope_in_memory(legacy_payload)
    assert info
    assert freshly_seeded is True
    assert legacy_payload["schema_version"] == "1.1"
    assert legacy_payload["identity"] == default_unset_identity()

    # Post-migration, before kernel_render_state seal, payload is in Case E.
    case_post_migrate = _detect_re_entry_case(legacy_payload, seed_brownfield=False)
    assert case_post_migrate == "E"

    # After kernel_render_state seal, payload reaches UPDATED.
    legacy_payload["kernel_render_state"] = [{"path": "LICENSE"}]
    case_updated = _detect_re_entry_case(legacy_payload, seed_brownfield=False)
    assert case_updated == "UPDATED"


def test_transition_E_to_UPDATED_after_kernel_render_state_seal() -> None:
    """E -> UPDATED: schema_version=1.1 + identity present but no
    kernel_render_state -> Case E. Sealing the state block transitions
    the payload to UPDATED."""
    payload = {
        "schema_version": "1.1",
        "identity": _mit_identity(),
    }
    assert _detect_re_entry_case(payload, seed_brownfield=False) == "E"

    payload["kernel_render_state"] = [{"path": "LICENSE"}, {"path": "README.md"}]
    assert _detect_re_entry_case(payload, seed_brownfield=False) == "UPDATED"


def test_transition_UPDATED_to_UPDATED_no_op_re_run(tmp_path: Path) -> None:
    """UPDATED -> UPDATED: re-running /lp-update-identity with the same
    identity is a NO_OP (zero fields changed). Verifies idempotency."""
    _seed_full_scaffold(tmp_path)
    decision_path = tmp_path / ".launchpad" / "scaffold-decision.json"
    payload_before = json.loads(decision_path.read_text(encoding="utf-8"))
    assert _detect_re_entry_case(payload_before, seed_brownfield=False) == "UPDATED"

    # Re-run with the SAME identity -- should be a NO_OP.
    result = run_update_identity(tmp_path, _mit_identity(), quiet=True)
    assert result.error_code is None, (
        f"unexpected error in idempotent re-run: code={result.error_code} "
        f"msg={result.error_message}"
    )
    assert result.status == IdentityUpdateStatus.NO_OP, (
        f"expected NO_OP on identical re-run, got {result.status!r}"
    )
    assert result.fields_changed == [], (
        f"expected zero fields changed; got {result.fields_changed!r}"
    )

    # Case still UPDATED post no-op.
    payload_after = json.loads(decision_path.read_text(encoding="utf-8"))
    assert _detect_re_entry_case(payload_after, seed_brownfield=False) == "UPDATED"
