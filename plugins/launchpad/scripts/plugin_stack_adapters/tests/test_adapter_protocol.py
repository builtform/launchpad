"""Adapter Protocol conformance + per-module error bridging.

Phase 4 plan §3.3 + §3.11.5(b). Tests cover:
  - `Adapter` is `runtime_checkable`.
  - `bridge_to_scaffold_error` preserves the structured triple.
  - duck-typed dicts are NOT recognized as Adapter instances.
  - `StackIdActive` Literal contains the 5 expected v2.1 ids.

Per-adapter Protocol conformance for nextjs_standalone / nextjs_fastapi /
astro / generic is asserted in their respective test files (Slice C); this
file covers the cross-cutting Protocol contract that lands in Slice A.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, get_args, runtime_checkable

import pytest

from plugin_stack_adapters.contracts import (
    Adapter,
    AdapterScaffoldError,
    ScaffoldStepFailedError,
    StackIdActive,
    bridge_to_scaffold_error,
)
from plugin_stack_adapters.ts_monorepo import ADAPTER as TS_ADAPTER


def test_adapter_protocol_is_runtime_checkable():
    @runtime_checkable
    class _Probe(Protocol):
        pass

    isinstance(object(), _Probe)
    isinstance(TS_ADAPTER, Adapter)


def test_ts_monorepo_satisfies_adapter_protocol():
    assert isinstance(TS_ADAPTER, Adapter)


def test_stack_id_active_contains_five_v21_ids():
    args = set(get_args(StackIdActive))
    assert args == {
        "ts_monorepo",
        "nextjs_standalone",
        "nextjs_fastapi",
        "astro",
        "generic",
    }


def test_duck_typed_dict_is_not_adapter():
    fake = {
        "stack_id": "ts_monorepo",
        "upstream": None,
        "manifest_schema_version": "1.0",
        "workspace_name": None,
        "unwrap_strategy": "none",
        "composes_with": {},
    }
    assert not isinstance(fake, Adapter)


def test_per_module_error_bridges_to_scaffold_step_preserves_triple():
    err = AdapterScaffoldError(
        reason="upstream_clone_failed",
        path=Path("/tmp/lp-nextjs_standalone-abc12345"),
        remediation="Re-run /lp-scaffold-stack with network connectivity.",
    )
    bridged = bridge_to_scaffold_error(err)
    assert isinstance(bridged, ScaffoldStepFailedError)
    assert bridged.reason == "upstream_clone_failed"
    assert bridged.path == Path("/tmp/lp-nextjs_standalone-abc12345")
    assert bridged.remediation == "Re-run /lp-scaffold-stack with network connectivity."


def test_bridge_handles_unstructured_exception_gracefully():
    err = ValueError("some unexpected error")
    bridged = bridge_to_scaffold_error(err)
    assert isinstance(bridged, ScaffoldStepFailedError)
    assert bridged.reason == "ValueError"
    assert bridged.path is None
    assert "some unexpected error" in bridged.remediation


def test_adapter_scaffold_error_carries_attributes():
    err = AdapterScaffoldError(
        reason="r", path=None, remediation="m"
    )
    assert err.reason == "r"
    assert err.path is None
    assert err.remediation == "m"


def test_scaffold_step_failed_error_is_runtime_error_subclass():
    assert issubclass(ScaffoldStepFailedError, RuntimeError)
    assert issubclass(AdapterScaffoldError, RuntimeError)
