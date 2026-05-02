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
    assert lp_scaffold_stack.TIER1_ARCHITECTURE_DOCS_RENDERED == 8


def test_submodule_imports():
    from lp_scaffold_stack import (
        cleanup_recorder,
        cross_cutting_wirer,
        decision_validator,
        engine,
        layer_materializer,
        marker_consumer,
        nonce_ledger,
        receipt_writer,
        rejection_logger,
    )

    assert callable(decision_validator.validate_decision)
    assert callable(nonce_ledger.append_nonce)
    assert callable(marker_consumer.consume_marker)
    assert callable(layer_materializer.materialize_layer)
    assert callable(cross_cutting_wirer.wire_cross_cutting)
    assert callable(receipt_writer.write_receipt)
    assert callable(rejection_logger.write_rejection)
    assert callable(cleanup_recorder.write_scaffold_failed)
    assert callable(engine.run_pipeline)
