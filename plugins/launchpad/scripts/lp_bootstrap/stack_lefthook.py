"""Stack-aware lefthook.yml enrichment (BL-316 production wiring).

Renders stack-specific lefthook fragments and additively merges them into
the kernel-rendered lefthook.yml bytes BEFORE the engine's policy
dispatch fires. Closes the production-wiring gap between BL-316's
shared partial (`plugin_stack_adapters/_partials/_python_gates.j2.fragment`)
and the consumer-emitted `lefthook.yml`.

Architecture (Slice 4c.4):

  1. engine.py renders kernel `lefthook.yml.j2` -> `kernel_bytes`.
  2. `enrich_lefthook_with_stacks(kernel_bytes, cwd)` reads
     `.launchpad/config.yml` via the existing `plugin-config-loader.read_stacks`.
  3. For each persisted stack, renders
     `plugin_stack_adapters/<stack>/templates/lefthook.j2.fragment` via
     `make_stack_aware_jinja_env` (the env used by the previously
     test-only `lefthook.yml.j2.outer`).
  4. `merge_keys_additive(user=enriched, plugin=stack_dict)` per stack.
     Earlier-declared stacks + kernel commands win on duplicate command
     names (first-declared-wins, matching the outer template's docstring).
  5. Returns serialized YAML bytes; engine.py uses these for SHA
     computation, fast-path comparison, and the existing user-side
     `apply_merge_keys` step (which merges with any pre-existing consumer
     `lefthook.yml`).

Greenfield (no `.launchpad/config.yml` or empty stacks list): returns
`kernel_bytes` unchanged for byte-identical behavior with v2.1.1 and
prior. No idempotency hazard.

Defense-in-depth: every parse / render / import failure path returns the
input bytes (or skips that stack) rather than raising into the bootstrap
render loop. The bootstrap engine treats lefthook.yml as load-bearing
infrastructure; a stack-fragment defect MUST NOT break `/lp-bootstrap`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml

from .policy import merge_keys_additive

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
_STACK_FRAGMENTS_ROOT = _SCRIPTS_ROOT / "plugin_stack_adapters"
_CONFIG_LOADER_PATH = _SCRIPTS_ROOT / "plugin-config-loader.py"


def _read_stacks(cwd: Path) -> list[str]:
    """Lazy-load `plugin-config-loader.read_stacks` (hyphenated filename
    requires importlib.util.spec_from_file_location)."""
    if not _CONFIG_LOADER_PATH.is_file():
        return []
    spec = importlib.util.spec_from_file_location(
        "plugin_config_loader_stack_lefthook",
        _CONFIG_LOADER_PATH,
    )
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


def _stack_fragment_path(stack_id: str) -> Path:
    return _STACK_FRAGMENTS_ROOT / stack_id / "templates" / "lefthook.j2.fragment"


def _render_stack_fragment(stack_id: str) -> bytes | None:
    """Render `<stack>/templates/lefthook.j2.fragment` via the stack-aware
    Jinja env (which resolves `_partials/` includes + the `require_tool`
    macro). Returns None when the stack has no fragment or rendering fails.
    """
    if not _stack_fragment_path(stack_id).is_file():
        return None
    if str(_SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_ROOT))
    try:
        from plugin_default_generators._renderer_base import (
            make_stack_aware_jinja_env,
        )
    except Exception:
        return None
    env = make_stack_aware_jinja_env()
    try:
        template = env.get_template(f"{stack_id}/templates/lefthook.j2.fragment")
        rendered = template.render()
    except Exception:
        return None
    return rendered.encode("utf-8")


def enrich_lefthook_with_stacks(kernel_bytes: bytes, cwd: Path) -> bytes:
    """Merge persisted stack lefthook fragments into `kernel_bytes`.

    Returns `kernel_bytes` unchanged when:
      * `.launchpad/config.yml` is absent or has no `stacks:`
      * the kernel YAML is malformed (defense; never block bootstrap)
      * no stack contributes a parseable fragment

    Emits the merged result via `yaml.safe_dump(default_flow_style=False,
    sort_keys=False)` to preserve declaration order so consumers see
    kernel hooks first, stack hooks appended.
    """
    stacks = _read_stacks(cwd)
    if not stacks:
        return kernel_bytes

    try:
        kernel_dict = yaml.safe_load(kernel_bytes)
    except yaml.YAMLError:
        return kernel_bytes
    if not isinstance(kernel_dict, dict):
        return kernel_bytes

    enriched: dict[str, Any] = kernel_dict
    any_merge_applied = False
    for stack_id in stacks:
        fragment_bytes = _render_stack_fragment(stack_id)
        if fragment_bytes is None:
            continue
        try:
            stack_dict = yaml.safe_load(fragment_bytes)
        except yaml.YAMLError:
            continue
        if not isinstance(stack_dict, dict):
            continue
        enriched, _warnings = merge_keys_additive(user=enriched, plugin=stack_dict)
        any_merge_applied = True

    if not any_merge_applied:
        return kernel_bytes

    return _safe_dump_lefthook_yaml(enriched).encode("utf-8")


def _str_block_representer(dumper: Any, data: str) -> Any:
    """Force PyYAML to emit multi-line strings as `|` block scalars instead
    of quoted strings with embedded `\\n` escapes. lefthook's `run:` blocks
    are functionally identical in either form, but block-scalar output is
    far more readable for human review of the generated `lefthook.yml`
    and matches the kernel template's style.
    """
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _safe_dump_lefthook_yaml(payload: dict[str, Any]) -> str:
    """yaml.safe_dump with the block-scalar representer applied to a
    private SafeDumper subclass (does not mutate the global PyYAML state)."""

    class _LefthookSafeDumper(yaml.SafeDumper):
        pass

    _LefthookSafeDumper.add_representer(str, _str_block_representer)
    return yaml.dump(
        payload,
        Dumper=_LefthookSafeDumper,
        default_flow_style=False,
        sort_keys=False,
        # PyYAML defaults to width=80 which forces quoted-string fallback
        # on any block-scalar line longer than 80 chars (lefthook gate
        # preambles routinely exceed this). Large width keeps `|` style
        # so the rendered lefthook.yml matches the kernel template's
        # human-readable shape.
        width=10000,
        allow_unicode=True,
    )


__all__ = ["enrich_lefthook_with_stacks"]
