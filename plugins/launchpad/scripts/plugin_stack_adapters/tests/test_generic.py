"""generic adapter (typed-fallback, hidden from pick-stack menu) tests.

Phase 4 plan section 2.2 row + section 3.12 v2.2-candidate INFO log.
"""
from __future__ import annotations

import logging
from pathlib import Path

from plugin_stack_adapters.contracts import Adapter
from plugin_stack_adapters.generic import (
    ADAPTER,
    GenericAdapter,
    HIDDEN_FROM_PICK_STACK_MENU,
    log_v22_candidate_routing,
    run,
)


def test_adapter_satisfies_adapter_protocol():
    assert isinstance(ADAPTER, Adapter)


def test_upstream_is_none():
    assert ADAPTER.upstream is None


def test_manifest_schema_version_is_1_0():
    assert ADAPTER.manifest_schema_version == "1.0"


def test_workspace_name_is_extra():
    assert ADAPTER.workspace_name == "extra"


def test_hidden_from_pick_stack_menu_constant_is_true():
    assert HIDDEN_FROM_PICK_STACK_MENU is True


def test_v22_candidate_routing_emits_verbatim_info_log(caplog):
    with caplog.at_level(logging.INFO, logger="plugin_stack_adapters.generic"):
        log_v22_candidate_routing("rails")
    assert any(
        "rails detected; v2.2 ships dedicated adapter; using generic fallback."
        in rec.getMessage()
        for rec in caplog.records
    )


def test_legacy_run_function_returns_generic_adapter_output():
    out = run()
    assert out["stack_id"] == "generic"
    assert out["frontend"] is None
    assert out["app_flow"] is None


def test_scaffold_into_is_noop_for_generic_adapter(tmp_path: Path):
    target = tmp_path / "lp-generic-tmp"
    GenericAdapter().scaffold_into(target)
    assert target.is_dir()
    children = list(target.iterdir())
    assert children == []


def test_composes_with_three_real_adapters_excluding_self_and_ts_monorepo():
    partners = set(ADAPTER.composes_with.keys())
    assert partners == {"nextjs_standalone", "nextjs_fastapi", "astro"}
    assert "generic" not in partners
    assert "ts_monorepo" not in partners
