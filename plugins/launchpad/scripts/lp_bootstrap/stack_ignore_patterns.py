"""Stack-aware enrichment of `.gitignore` / `.gitleaks.toml` / `.greptile.json` (BL-350).

Companion to `stack_structure_check.py` (BL-347). The three ignore-pattern
surfaces — `.gitignore` lines, `.gitleaks.toml` allowlist paths, and
`.greptile.json` ignorePatterns — each previously shipped a kernel
template with TS-monorepo cruft baked in (`.next/`, `.turbo/`,
`pnpm-lock.yaml`). v2.1.6 BL-350 moves those entries into per-stack
data in `plugin_stack_adapters._ignore_patterns` and injects them at
bootstrap-render time based on the persisted `stacks:` list.

Three template surfaces, three sentinel pairs:

  * `.gitignore` — sentinels `STACK_AWARE_GITIGNORE_BEGIN/END` (markdown
    comment style: `# ...`). Each per-stack pattern emitted as one line
    matching .gitignore syntax.
  * `.gitleaks.toml` — sentinels `STACK_AWARE_GITLEAKS_BEGIN/END` inside
    the `paths = [ ... ]` array, TOML comment style (`# ...`). Each
    per-stack pattern wrapped in `'''...'''` triple-quoted literal.
  * `.greptile.json` — sentinels `STACK_AWARE_GREPTILE_BEGIN/END` inside
    the JSON `"ignorePatterns": "..."` string value. Patterns joined
    with literal `\\n` (Greptile's documented multi-pattern convention).

Defense-in-depth mirrors `stack_structure_check`: every failure path
returns input bytes unchanged. The resulting templates are valid in
their respective formats even with empty sentinel blocks — `.gitignore`
with only universal patterns, `.gitleaks.toml` with universal-only
allowlist, `.greptile.json` with empty ignorePatterns.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from ._enricher_common import dedupe_preserving_order, read_stacks_safe

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
_IGNORE_PATTERNS_PATH = _SCRIPTS_ROOT / "plugin_stack_adapters" / "_ignore_patterns.py"


# `.gitignore` sentinel: bare `# ...` comment lines.
_GITIGNORE_RE = re.compile(
    r"(# STACK_AWARE_GITIGNORE_BEGIN[^\n]*\n)[\s\S]*?(# STACK_AWARE_GITIGNORE_END[^\n]*\n)",
)
# `.gitleaks.toml` sentinel: TOML-array context, leading whitespace
# preserved (4-space indent matches the existing `paths = [` formatting).
_GITLEAKS_RE = re.compile(
    r"(    # STACK_AWARE_GITLEAKS_BEGIN[^\n]*\n)[\s\S]*?(    # STACK_AWARE_GITLEAKS_END[^\n]*\n)",
)
# `.greptile.json` sentinel: JSON-string context — sentinels surrounded
# by literal `\\n` backslash-n sequences (the actual two characters in
# the JSON source, which the parser turns into a newline in the
# resulting string value).
_GREPTILE_RE = re.compile(
    r"(STACK_AWARE_GREPTILE_BEGIN)\\n[\s\S]*?(STACK_AWARE_GREPTILE_END)",
)


def _load_ignore_data() -> tuple[
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
]:
    """Lazy-load the per-stack ignore-pattern dicts. Returns three
    `({}, {}, {})` on import failure (defense)."""
    if not _IGNORE_PATTERNS_PATH.is_file():
        return {}, {}, {}
    spec = importlib.util.spec_from_file_location(
        "ignore_patterns_stack_ignore",
        _IGNORE_PATTERNS_PATH,
    )
    if spec is None or spec.loader is None:
        return {}, {}, {}
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return {}, {}, {}
    gitignore = getattr(mod, "GITIGNORE_PATTERNS_PER_STACK", {})
    gitleaks = getattr(mod, "GITLEAKS_PATHS_PER_STACK", {})
    greptile = getattr(mod, "GREPTILE_IGNORE_PATTERNS_PER_STACK", {})
    if not all(isinstance(d, dict) for d in (gitignore, gitleaks, greptile)):
        return {}, {}, {}
    return gitignore, gitleaks, greptile


def _accumulate(stacks: list[str], data: dict[str, tuple[str, ...]]) -> list[str]:
    out: list[str] = []
    for stack_id in stacks:
        out.extend(data.get(stack_id, ()))
    return dedupe_preserving_order(out)


def _splice(
    body: bytes,
    pattern: re.Pattern[str],
    formatted_block: str,
) -> bytes:
    """Splice `formatted_block` between the sentinel markers. Returns
    `body` unchanged when the sentinels are absent."""
    decoded = body.decode("utf-8", errors="strict")
    match = pattern.search(decoded)
    if match is None:
        return body
    begin = match.group(1)
    end = match.group(2)
    replacement = f"{begin}{formatted_block}{end}"
    new_decoded = decoded[: match.start()] + replacement + decoded[match.end() :]
    return new_decoded.encode("utf-8")


def _format_gitignore_lines(patterns: list[str]) -> str:
    """One pattern per line, no leading indent (matches .gitignore syntax)."""
    if not patterns:
        return ""
    return "\n".join(patterns) + "\n"


def _format_gitleaks_lines(patterns: list[str]) -> str:
    """Each pattern wrapped in TOML triple-quoted literal, 4-space indent
    matching the existing `paths = [` array body formatting."""
    if not patterns:
        return ""
    # TOML triple-quoted literal: '''<body>''',  — single trailing comma.
    triple = "'''"
    lines = [f"    {triple}{pattern}{triple}," for pattern in patterns]
    return "\n".join(lines) + "\n"


def _format_greptile_inline(patterns: list[str]) -> str:
    """Greptile takes one `\\n`-joined string in JSON. Output is the
    patterns joined by literal `\\n` two-char escape (the JSON parser
    converts those to newlines in the resulting string value). No
    leading or trailing `\\n` — the caller substitutes the entire
    sentinel block including the separator, so the splice produces
    `"ignorePatterns": "<pattern1>\\n<pattern2>"` with no spurious
    leading newline."""
    if not patterns:
        return ""
    return "\\n".join(patterns)


def enrich_gitignore_with_stacks(kernel_bytes: bytes, cwd: Path) -> bytes:
    """Enrich `.gitignore` with per-stack patterns.

    On greenfield (no stacks), returns kernel bytes unchanged — the
    sentinel comments remain in `.gitignore` and are inert (gitignore
    treats them as comments).
    """
    stacks = read_stacks_safe(cwd, module_spec_name="plugin_config_loader_stack_ignore")
    if not stacks:
        return kernel_bytes
    gitignore, _, _ = _load_ignore_data()
    if not gitignore:
        return kernel_bytes
    patterns = _accumulate(stacks, gitignore)
    if not patterns:
        return kernel_bytes
    return _splice(kernel_bytes, _GITIGNORE_RE, _format_gitignore_lines(patterns))


def enrich_gitleaks_with_stacks(kernel_bytes: bytes, cwd: Path) -> bytes:
    """Enrich `.gitleaks.toml` allowlist with per-stack regex paths.

    On greenfield (no stacks), returns kernel bytes unchanged — the
    sentinel comments remain inside the TOML array and are inert.
    """
    stacks = read_stacks_safe(cwd, module_spec_name="plugin_config_loader_stack_ignore")
    if not stacks:
        return kernel_bytes
    _, gitleaks, _ = _load_ignore_data()
    if not gitleaks:
        return kernel_bytes
    patterns = _accumulate(stacks, gitleaks)
    if not patterns:
        return kernel_bytes
    return _splice(kernel_bytes, _GITLEAKS_RE, _format_gitleaks_lines(patterns))


def enrich_greptile_with_stacks(kernel_bytes: bytes, cwd: Path) -> bytes:
    """Enrich `.greptile.json` ignorePatterns with per-stack glob patterns.

    UNLIKE the gitignore / gitleaks enrichers, this one ALWAYS rewrites
    the sentinel block — even on greenfield with empty patterns — because
    the sentinel markers live inside a JSON string value. Leaving them
    in-place would produce a literal
    `STACK_AWARE_GREPTILE_BEGIN\\nSTACK_AWARE_GREPTILE_END` string in the
    rendered `ignorePatterns` field, which Greptile would interpret as a
    literal file pattern. On greenfield, the sentinels are stripped and
    `ignorePatterns` becomes an empty string — empty pattern list,
    Greptile reviews everything, no spurious literal pattern.

    The sentinels are CONSUMED (not preserved) in the rewrite — they
    only exist as template anchors, not in the rendered output.
    """
    _, _, greptile = _load_ignore_data()
    stacks = read_stacks_safe(cwd, module_spec_name="plugin_config_loader_stack_ignore")
    patterns = _accumulate(stacks, greptile) if (stacks and greptile) else []
    formatted = _format_greptile_inline(patterns) if patterns else ""

    decoded = kernel_bytes.decode("utf-8", errors="strict")
    match = _GREPTILE_RE.search(decoded)
    if match is None:
        return kernel_bytes
    new_decoded = decoded[: match.start()] + formatted + decoded[match.end() :]
    return new_decoded.encode("utf-8")


__all__ = [
    "enrich_gitignore_with_stacks",
    "enrich_gitleaks_with_stacks",
    "enrich_greptile_with_stacks",
]
