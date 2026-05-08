"""ts_monorepo v2.1 refactor: Adapter Protocol conformance + composition rule.

Phase 4 plan §2.1 + §3.3: ts_monorepo declares `upstream=None`,
`composes_with={}` (cannot compose), `unwrap_strategy="none"`. The legacy
`run() -> AdapterOutput` API is preserved for the polyglot composer.
"""
from __future__ import annotations

from pathlib import Path

from plugin_stack_adapters.contracts import Adapter
from plugin_stack_adapters.ts_monorepo import ADAPTER, TsMonorepoAdapter, run


def test_adapter_singleton_is_adapter_instance():
    assert isinstance(ADAPTER, Adapter)


def test_adapter_class_is_adapter_instance():
    assert isinstance(TsMonorepoAdapter(), Adapter)


def test_stack_id_is_ts_monorepo():
    assert ADAPTER.stack_id == "ts_monorepo"


def test_upstream_is_none():
    assert ADAPTER.upstream is None


def test_composes_with_is_empty():
    assert ADAPTER.composes_with == {}


def test_unwrap_strategy_is_none():
    assert ADAPTER.unwrap_strategy == "none"


def test_workspace_name_is_none():
    assert ADAPTER.workspace_name is None


def test_manifest_schema_version_is_1_0():
    assert ADAPTER.manifest_schema_version == "1.0"


def test_scaffold_into_is_noop(tmp_path: Path):
    assert ADAPTER.scaffold_into(tmp_path) is None
    assert ADAPTER.apply_overlay(tmp_path) is None


def test_legacy_run_function_still_returns_adapter_output():
    out = run()
    assert out["stack_id"] == "ts_monorepo"
    assert out["tech_stack"]["language"] == "TypeScript"
    assert "test" in out["commands"]
