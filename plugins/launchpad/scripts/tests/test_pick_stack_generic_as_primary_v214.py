"""v2.1.4 BL-331 regression: `generic` selectable as a primary stack via
the /lp-pick-stack manual-override branch.

Pre-fix, `('generic', <role>)` was absent from `VALID_COMBINATIONS`, so
choosing `generic` from the manual-override menu raised
`ManualOverrideError(field='layers[0].stack-role')`. The only path to
`generic` was the v2.2-candidate fallback (passing accept_v22_fallback
against an id like `python_generic`), which surfaced an unrelated WARN
and obscured the actual user intent of "give me a barebones workspace
shell — bring my own framework."

Tests in this module:

  * `test_*_via_manual_override`: pytest end-to-end runs through
    /lp-pick-stack → /lp-scaffold-stack with `(generic, <role>)` and
    asserts the receipt records the generic shell.
  * `test_v22_candidate_fallback_unchanged`: regression — the existing
    `accept_v22_fallback=True` path for v2.2-candidate ids still routes
    through generic and emits `fallback_ids` on the receipt. Picking
    `generic` directly is a SEPARATE path; the candidate fallback path
    must remain identical pre/post-BL-331.
  * `test_valid_combinations_includes_generic`: cheap unit assertion
    that the 5 expected (generic, role) tuples are present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack import (
    VALID_COMBINATIONS,  # noqa: E402
    is_valid_combination,  # noqa: E402
)
from lp_pick_stack.engine import Outcome  # noqa: E402
from lp_pick_stack.engine import run_pipeline as run_pick_stack_pipeline  # noqa: E402
from lp_scaffold_stack.engine import (
    run_pipeline as run_scaffold_stack_pipeline,  # noqa: E402
)
from lp_scaffold_stack.v21_adapter_dispatch import (
    fallback_ids_used,  # noqa: E402
    resolve_adapter,  # noqa: E402
)

VALID_FUNNEL_ANSWERS = {
    "Q1": "web-app",
    "Q2": "yes-needed",
    "Q3": "no",
    "Q4": "mixed-no-strong-preference",
    "Q5": "container",
}


def test_valid_combinations_includes_generic():
    """BL-331: the 5 (generic, role) tuples are part of the manual-override
    catalog."""
    expected = {
        ("generic", "frontend"),
        ("generic", "frontend-main"),
        ("generic", "frontend-dashboard"),
        ("generic", "backend"),
        ("generic", "fullstack"),
    }
    assert expected.issubset(VALID_COMBINATIONS)
    for stack, role in expected:
        assert is_valid_combination(stack, role), (stack, role)


@pytest.mark.parametrize(
    "role",
    ["frontend", "frontend-main", "frontend-dashboard", "backend", "fullstack"],
)
def test_generic_primary_via_manual_override_writes_decision(
    tmp_path: Path, role: str
):
    """BL-331: every (generic, role) tuple flows cleanly through Step 4 ->
    Step 6, writing scaffold-decision.json with matched_category_id =
    'manual-override' and the generic layer recorded verbatim."""
    result = run_pick_stack_pipeline(
        tmp_path,
        VALID_FUNNEL_ANSWERS,
        manual_override=True,
        manual_layer_specs=[{"stack": "generic", "role": role, "path": "."}],
        write_telemetry=False,
    )
    assert result.success, result.message
    assert result.outcome == Outcome.MANUAL_OVERRIDE
    assert result.matched_category_id == "manual-override"

    decision = json.loads(result.decision_path.read_text(encoding="utf-8"))
    assert decision["matched_category_id"] == "manual-override"
    assert decision["layers"] == [
        {"stack": "generic", "role": role, "path": ".", "options": {}}
    ]
    # generic is a STACK_ID_ACTIVE_ENUM member; the v1.1 envelope's
    # flat `stacks` array is derived from layers and passes through
    # unchanged (no _CATALOG_FALLBACK_MAP translation).
    assert "generic" in decision["stacks"]


def test_generic_primary_via_manual_override_then_scaffold_e2e(tmp_path: Path):
    """BL-331: full /lp-pick-stack -> /lp-scaffold-stack happy path with
    `generic` as the primary stack. Asserts scaffold-receipt.json is
    produced and records the generic adapter dispatch."""
    pick_result = run_pick_stack_pipeline(
        tmp_path,
        VALID_FUNNEL_ANSWERS,
        manual_override=True,
        manual_layer_specs=[{"stack": "generic", "role": "frontend", "path": "."}],
        write_telemetry=False,
    )
    assert pick_result.success, pick_result.message

    scaffold_result = run_scaffold_stack_pipeline(
        tmp_path,
        skip_greenfield_gate=False,
        write_telemetry_flag=False,
    )
    assert scaffold_result.success, scaffold_result.message

    receipt_path = tmp_path / ".launchpad" / "scaffold-receipt.json"
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    # BL-331 acceptance: the generic dispatch is NOT a v2.2-candidate
    # fallback. `adapter_dispatch_meta.fallback_ids` MUST be absent or
    # empty when the user picks generic directly — fallback_ids is
    # reserved for v2.2-candidate routing, not user-selected generic.
    meta = receipt.get("adapter_dispatch_meta") or {}
    assert not meta.get("fallback_ids"), (
        f"generic-as-primary must not record fallback_ids; got {meta!r}"
    )


def test_v22_candidate_fallback_unchanged():
    """Regression: v2.2-candidate fallback path (the OTHER way to reach
    the generic adapter) is unchanged by BL-331. resolve_adapter with
    accept_v22_fallback=True for python_generic still returns the
    GenericAdapter, and fallback_ids_used reports the candidate id."""
    adapter = resolve_adapter("python_generic", accept_v22_fallback=True)
    assert adapter.stack_id == "generic"

    ids = fallback_ids_used(["python_generic"], accept_v22_fallback=True)
    assert ids == ["python_generic"]

    # Picking `generic` directly does NOT invoke the candidate fallback,
    # so fallback_ids_used should report empty for it.
    ids_for_generic = fallback_ids_used(["generic"], accept_v22_fallback=True)
    assert ids_for_generic == []


def test_generic_primary_polyglot_with_astro_frontend(tmp_path: Path):
    """BL-331: polyglot scaffold with `generic` (backend) + `astro` (frontend-main)
    composes cleanly. Demonstrates the canonical bring-your-own-backend
    use case (LaunchPad provides Astro frontend; user wires their own
    backend behind the generic shell)."""
    (tmp_path / "apps").mkdir()
    (tmp_path / "services").mkdir()
    result = run_pick_stack_pipeline(
        tmp_path,
        VALID_FUNNEL_ANSWERS,
        manual_override=True,
        manual_layer_specs=[
            {"stack": "astro", "role": "frontend-main", "path": "apps"},
            {"stack": "generic", "role": "backend", "path": "services"},
        ],
        skip_greenfield_gate=True,
        write_telemetry=False,
    )
    assert result.success, result.message
    assert result.outcome == Outcome.MANUAL_OVERRIDE


def test_generic_invalid_role_still_rejected(tmp_path: Path):
    """BL-331 contract: only the 5 documented roles for `generic` are
    accepted. `generic` with `mobile` or `backend-managed` MUST still
    be rejected (no all-roles wildcard)."""
    for bad_role in ["mobile", "backend-managed", "desktop"]:
        sub = tmp_path / f"sub-{bad_role}"
        sub.mkdir()
        result = run_pick_stack_pipeline(
            sub,
            VALID_FUNNEL_ANSWERS,
            manual_override=True,
            manual_layer_specs=[
                {"stack": "generic", "role": bad_role, "path": "."}
            ],
            write_telemetry=False,
        )
        assert not result.success, (
            f"(generic, {bad_role}) must be rejected; got success"
        )
        assert result.reason == "manual_override_invalid", (
            f"unexpected reason for (generic, {bad_role}): {result.reason}"
        )
