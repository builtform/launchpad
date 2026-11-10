"""Shared stack-source and formatting helpers for the bootstrap enrichers.

A non-empty configured stacks list wins; otherwise the sealed decision
supplies the stack list before config exists. The shared resolver normalizes
catalog shortnames and keeps only active ids used by the enrichment tables.

Stack readers return an empty list on failure; the decision reader returns
an empty object. Enrichers retain their safe fallback to the input bytes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_LOADER_PATH = _SCRIPTS_ROOT / "plugin-config-loader.py"


def read_stacks_safe(cwd: Path, *, module_spec_name: str) -> list[str]:
    """Lazy-load `plugin-config-loader.read_stacks` and return the
    persisted `stacks:` list from `.launchpad/config.yml` under `cwd`.

    Returns `[]` on every failure path — missing loader file, spec load
    failure, exec failure, missing `read_stacks` attribute,
    non-list result. Each caller supplies a unique
    `module_spec_name` so concurrent enricher loads don't collide on
    `sys.modules` keys.

    The hyphenated filename (`plugin-config-loader.py`) prevents the
    standard `import plugin_config_loader` form; spec_from_file_location
    is the canonical workaround.
    """
    if not _CONFIG_LOADER_PATH.is_file():
        return []
    spec = importlib.util.spec_from_file_location(module_spec_name, _CONFIG_LOADER_PATH)
    if spec is None or spec.loader is None:
        return []
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return []
    try:
        result = mod.read_stacks(cwd)
    except Exception:
        return []
    if not isinstance(result, list):
        return []
    return [str(s) for s in result]


def read_decision_payload_safe(cwd: Path, *, module_spec_name: str) -> dict:
    """Return the canonical decision reader's payload, or an empty object.

    The payload only selects table entries here; signature verification
    remains with the decision consumers. All loader and reader failures,
    including ConfigError, return the safe default.
    """
    try:
        if not _CONFIG_LOADER_PATH.is_file():
            return {}
        spec = importlib.util.spec_from_file_location(
            module_spec_name, _CONFIG_LOADER_PATH
        )
        if spec is None or spec.loader is None:
            return {}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        payload = mod.read_scaffold_decision(cwd).payload
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def read_enricher_stacks(cwd: Path, *, module_spec_name: str) -> list[str]:
    """Read configured stacks or decision stacks, normalize and filter them.

    A non-empty config list takes precedence. The fallback decision list
    must contain only strings. Unknown normalized ids are omitted, and any
    read, import or normalization failure returns an empty list.
    """
    try:
        ids = read_stacks_safe(cwd, module_spec_name=module_spec_name)
        if not ids:
            payload = read_decision_payload_safe(cwd, module_spec_name=module_spec_name)
            ids = payload.get("stacks")
            if not isinstance(ids, list) or not all(isinstance(s, str) for s in ids):
                return []
        from lp_pick_stack.decision_writer import derive_stacks
        from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM

        normalized = derive_stacks([{"stack": stack_id} for stack_id in ids])
        return [stack_id for stack_id in normalized if stack_id in STACK_ID_ACTIVE_ENUM]
    except Exception:
        return []


def dedupe_preserving_order(items: list[str]) -> list[str]:
    """Return `items` with duplicates removed, preserving first-occurrence
    order.

    Two stacks in the same project may legitimately contribute the same
    entry to a per-stack accumulation (e.g., `nextjs_fastapi` lists `src`
    and `nextjs_standalone` also lists `src` if a user enables both).
    The rendered output MUST NOT have duplicate entries because the shell
    array membership check treats them as a single match anyway, but a
    clean output is friendlier on review.

    Operates on string lists only — the enrichers all accumulate per-stack
    string tuples (directory names, config-file names, ignore patterns).
    """
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


__all__ = [
    "dedupe_preserving_order",
    "read_decision_payload_safe",
    "read_enricher_stacks",
    "read_stacks_safe",
]
