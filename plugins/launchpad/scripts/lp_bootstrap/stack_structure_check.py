"""Stack-aware enrichment of `scripts/maintenance/check-repo-structure.sh` (BL-347).

The kernel template ships with universal ALLOWED_DIRS / ALLOWED_CONFIGS
entries plus sentinel-comment placeholders for per-stack additions. This
module reads the persisted `stacks:` array from `.launchpad/config.yml`,
looks up each stack's allowlist data in
`plugin_stack_adapters._structure_allowlists`, and rewrites the rendered
shell-script bytes to inject those additions between the sentinels.

Architecture mirrors `stack_lefthook.enrich_lefthook_with_stacks`:

  1. engine.py renders the kernel `check-repo-structure.sh.j2` -> kernel
     bytes.
  2. `enrich_structure_check_with_stacks(kernel_bytes, cwd)` reads
     `.launchpad/config.yml` for persisted stacks via the existing
     `plugin-config-loader.read_stacks` loader.
  3. For each stack, look up `stack_allowed_dirs(stack_id)` and
     `stack_allowed_configs(stack_id)`.
  4. Splice the union of those entries between the sentinel-comment
     markers in the rendered bytes.
  5. Return the rewritten bytes. The engine's SHA computation,
     manifest stamping, and policy dispatch see the enriched output.

Greenfield (no `.launchpad/config.yml` or empty stacks list): returns
kernel bytes unchanged for byte-identical behavior with v2.1.5.

Defense-in-depth: every parse / lookup / splice failure path returns the
input bytes rather than raising. The kernel `check-repo-structure.sh`
remains valid bash even with empty sentinel blocks — the worst case on
enricher failure is "kernel-only allowlist, user customizes after first
commit" rather than "no allowlist at all".
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from ._enricher_common import dedupe_preserving_order, read_stacks_safe

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
_ALLOWLISTS_PATH = _SCRIPTS_ROOT / "plugin_stack_adapters" / "_structure_allowlists.py"


# Sentinel-block regex compiled once. The capturing group spans the
# entire sentinel block including the open/close markers so the splice
# operation can preserve those markers verbatim. The `[\s\S]*?` non-greedy
# match handles arbitrary content between sentinels (empty in the kernel,
# populated in the enriched output, possibly stale-but-recoverable on
# re-render).
_DIRS_RE = re.compile(
    r"(  # STACK_AWARE_DIRS_BEGIN[^\n]*\n)[\s\S]*?(  # STACK_AWARE_DIRS_END[^\n]*\n)",
)
_CONFIGS_RE = re.compile(
    r"(  # STACK_AWARE_CONFIGS_BEGIN[^\n]*\n)[\s\S]*?(  # STACK_AWARE_CONFIGS_END[^\n]*\n)",
)


def _load_allowlists() -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """Lazy-load the per-stack allowlist data. Returns
    `(STACK_ALLOWED_DIRS, STACK_ALLOWED_CONFIGS)` or `({}, {})` on import
    failure. Defense: a malformed allowlist file MUST NOT block bootstrap.
    """
    if not _ALLOWLISTS_PATH.is_file():
        return {}, {}
    spec = importlib.util.spec_from_file_location(
        "structure_allowlists_stack_structure",
        _ALLOWLISTS_PATH,
    )
    if spec is None or spec.loader is None:
        return {}, {}
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return {}, {}
    dirs = getattr(mod, "STACK_ALLOWED_DIRS", {})
    configs = getattr(mod, "STACK_ALLOWED_CONFIGS", {})
    if not isinstance(dirs, dict) or not isinstance(configs, dict):
        return {}, {}
    return dirs, configs


def _format_array_entries(values: list[str]) -> str:
    """Format a list of entries as bash array members, one per line,
    indented to match the surrounding `ALLOWED_*=(...)` block.

    Deduplication and ordering are caller responsibilities — this helper
    is mechanical text formatting only.
    """
    if not values:
        return ""
    lines = [f'  "{value}"' for value in values]
    return "\n".join(lines) + "\n"


def _splice_sentinel(
    body: bytes,
    pattern: re.Pattern[str],
    additions: str,
) -> bytes:
    """Replace the content between sentinel markers with `additions`.

    Returns `body` unchanged when the sentinel block is absent (defense
    against a downstream user manually editing the kernel template).
    """
    decoded = body.decode("utf-8", errors="strict")
    match = pattern.search(decoded)
    if match is None:
        return body
    begin_marker = match.group(1)
    end_marker = match.group(2)
    replacement = f"{begin_marker}{additions}{end_marker}"
    new_decoded = decoded[: match.start()] + replacement + decoded[match.end() :]
    return new_decoded.encode("utf-8")


def enrich_structure_check_with_stacks(kernel_bytes: bytes, cwd: Path) -> bytes:
    """Splice per-stack ALLOWED_DIRS / ALLOWED_CONFIGS entries into the
    kernel `check-repo-structure.sh` bytes between the sentinel-comment
    markers.

    Returns `kernel_bytes` unchanged when:
      * `.launchpad/config.yml` is absent or has no `stacks:`
      * the allowlist data module fails to import
      * the sentinel markers are missing from the kernel template
      * no stack contributes any entries

    Greenfield projects (no stacks persisted) ship the kernel-only
    allowlist — strictly safer than the pre-v2.1.6 monorepo-hardcoded
    allowlist for any non-monorepo shape.
    """
    stacks = read_stacks_safe(
        cwd, module_spec_name="plugin_config_loader_stack_structure"
    )
    if not stacks:
        return kernel_bytes

    stack_dirs, stack_configs = _load_allowlists()
    if not stack_dirs and not stack_configs:
        return kernel_bytes

    dirs_accum: list[str] = []
    configs_accum: list[str] = []
    for stack_id in stacks:
        dirs_accum.extend(stack_dirs.get(stack_id, ()))
        configs_accum.extend(stack_configs.get(stack_id, ()))

    dirs_accum = dedupe_preserving_order(dirs_accum)
    configs_accum = dedupe_preserving_order(configs_accum)

    if not dirs_accum and not configs_accum:
        return kernel_bytes

    enriched = kernel_bytes
    if dirs_accum:
        enriched = _splice_sentinel(
            enriched, _DIRS_RE, _format_array_entries(dirs_accum)
        )
    if configs_accum:
        enriched = _splice_sentinel(
            enriched, _CONFIGS_RE, _format_array_entries(configs_accum)
        )

    return enriched


__all__ = ["enrich_structure_check_with_stacks"]
