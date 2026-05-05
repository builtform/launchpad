"""v2.1 Adapter dispatch helper for /lp-scaffold-stack.

Phase 4 plan section 4 Slice D. The existing
`lp_scaffold_stack/engine.py:run_pipeline` predates the v2.1 Adapter
Protocol and dispatches to the v1 `run() -> AdapterOutput` API; this module
is the v2.1 dispatch surface that compositions and adapter-aware single-
stack scaffolds invoke instead.

Single-adapter mode: invokes `Adapter.scaffold_into(workspace_dir)` followed
by `Adapter.apply_overlay(workspace_dir)`. For adapters with no upstream
(ts_monorepo, generic) the calls are no-ops.

Composition mode: dispatches to `composition.compose(adapters,
composition_root)`. The N=2 cap is enforced upstream by
`composition.validate_pair`; this module surfaces the rejection unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionResult,
    compose,
    validate_pair,
)
from plugin_stack_adapters.contracts import (
    Adapter,
    bridge_to_scaffold_error,
    ScaffoldStepFailedError,
)


_ADAPTER_REGISTRY: dict[str, str] = {
    "ts_monorepo": "plugin_stack_adapters.ts_monorepo",
    "nextjs_standalone": "plugin_stack_adapters.nextjs_standalone",
    "nextjs_fastapi": "plugin_stack_adapters.nextjs_fastapi",
    "astro": "plugin_stack_adapters.astro",
    "generic": "plugin_stack_adapters.generic",
}


def resolve_adapter(stack_id: str) -> Adapter:
    """Look up the v2.1 ADAPTER singleton for a closed-enum stack id."""
    if stack_id not in _ADAPTER_REGISTRY:
        raise ScaffoldStepFailedError(
            reason="unknown_v21_stack_id",
            path=None,
            remediation=(
                f"stack_id {stack_id!r} not in v2.1 active set "
                f"{tuple(_ADAPTER_REGISTRY)!r}; use the generic fallback or "
                f"file a v2.2 adapter request"
            ),
        )
    import importlib

    module = importlib.import_module(_ADAPTER_REGISTRY[stack_id])
    return module.ADAPTER  # type: ignore[no-any-return]


def dispatch_single_adapter(
    adapter: Adapter, workspace_dir: Path
) -> Path:
    """Single-adapter mode: scaffold + overlay into `workspace_dir`."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    try:
        adapter.scaffold_into(workspace_dir)
        adapter.apply_overlay(workspace_dir)
    except Exception as exc:
        raise bridge_to_scaffold_error(exc) from exc
    return workspace_dir


def dispatch_composition(
    adapters: Iterable[Adapter], composition_root: Path
) -> CompositionResult:
    """Composition mode: validate + compose. N=2 cap enforced upstream."""
    selected = list(adapters)
    rejection = validate_pair(selected)
    if rejection is not None:
        raise CompositionAbortError(
            reason=rejection.code.value,
            path=composition_root,
            remediation=rejection.message,
        )
    return compose(selected, composition_root)


def dispatch_by_stack_ids(
    stack_ids: list[str], workspace_dir: Path
) -> CompositionResult | Path:
    """One entrypoint for callers that have stack_ids and want a uniform
    return surface. Single-id: returns the populated workspace_dir.
    Multi-id: returns the CompositionResult.
    """
    if len(stack_ids) == 0:
        raise ScaffoldStepFailedError(
            reason="empty_stack_id_list",
            path=workspace_dir,
            remediation="at least one stack_id is required",
        )
    if len(stack_ids) == 1:
        adapter = resolve_adapter(stack_ids[0])
        return dispatch_single_adapter(adapter, workspace_dir)
    adapters = [resolve_adapter(sid) for sid in stack_ids]
    return dispatch_composition(adapters, workspace_dir)


__all__ = [
    "resolve_adapter",
    "dispatch_single_adapter",
    "dispatch_composition",
    "dispatch_by_stack_ids",
]
