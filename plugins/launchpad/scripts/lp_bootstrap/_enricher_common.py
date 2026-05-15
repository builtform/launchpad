"""Shared helpers for the v2.1.6 stack-aware enrichers.

Closes BL-356 review findings F4 (`_read_stacks` triplicated across the
three new enricher modules) and F5 (`_dedupe_preserving_order` duplicated
between `stack_structure_check` and `stack_ignore_patterns`).

The four enricher modules — `stack_lefthook` (pre-existing),
`stack_structure_check`, `stack_ignore_patterns`, `stack_pkg_manager` —
each had a private `_read_stacks(cwd)` helper that lazy-imported
`plugin-config-loader.py` via `importlib.util.spec_from_file_location`.
The implementations were byte-identical except for the unique `sys.modules`
spec-name string. This module centralises the shape; each enricher passes
its own unique spec name to avoid `sys.modules` collisions across imports.

Defense-in-depth invariant: every exported helper returns a safe default
(`[]` for stacks, `[]` for dedupe input) on any failure path. Enrichers
that build on these helpers preserve the "input bytes returned unchanged
on any failure" contract documented in each enricher's module docstring.
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


__all__ = ["dedupe_preserving_order", "read_stacks_safe"]
