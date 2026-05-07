"""Smoke import test for the lp_scaffold_stack package (Phase 3 S1)."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_package_imports():
    import lp_scaffold_stack

    assert isinstance(lp_scaffold_stack.EXPECTED_DECISION_VERSION, frozenset)
    assert "1.0" in lp_scaffold_stack.EXPECTED_DECISION_VERSION
    assert lp_scaffold_stack.WRITTEN_RECEIPT_VERSION == "1.0"
    # PR #41 cycle 8 #2 closure (Codex P1): the constant was hardcoded
    # to 8 but the v2.1 /lp-define orchestrator (lp_define_runner.py;
    # superseded plugin-doc-generator in Phase 8.5) emits only 4
    # docs/architecture/* outputs (PRD, TECH_STACK, BACKEND_STRUCTURE,
    # APP_FLOW). Receipt and panel now reflect reality.
    assert lp_scaffold_stack.TIER1_ARCHITECTURE_DOCS_RENDERED == 4


def test_submodule_imports():
    """v2.1.0 completion plan §3.6: `layer_materializer` deleted; the
    v2.1 adapter dispatch surface now lives in `v21_adapter_dispatch` +
    `dispatch_enumeration`."""
    from lp_scaffold_stack import (
        cleanup_recorder,
        cross_cutting_wirer,
        decision_validator,
        dispatch_enumeration,
        engine,
        marker_consumer,
        nonce_ledger,
        receipt_writer,
        rejection_logger,
        v21_adapter_dispatch,
    )

    assert callable(decision_validator.validate_decision)
    assert callable(nonce_ledger.append_nonce)
    assert callable(marker_consumer.consume_marker)
    assert callable(v21_adapter_dispatch.dispatch_by_stack_ids)
    assert callable(dispatch_enumeration.enumerate_files)
    assert callable(cross_cutting_wirer.wire_cross_cutting)
    assert callable(receipt_writer.write_receipt)
    assert callable(rejection_logger.write_rejection)
    assert callable(cleanup_recorder.write_scaffold_failed)
    assert callable(engine.run_pipeline)
