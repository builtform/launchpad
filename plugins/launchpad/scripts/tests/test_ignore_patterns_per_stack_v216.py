"""BL-350 v2.1.6 — stack-aware `.gitignore` / `.gitleaks.toml` / `.greptile.json`.

Before v2.1.6 the three downstream ignore-pattern surfaces shipped
TS-monorepo cruft (`.next/`, `.turbo/`, `pnpm-lock.yaml`) at the
universal kernel level. Every Python / Ruby / Hugo user got those
irrelevant entries — cosmetically misleading and noisy in `git status`.

v2.1.6 moves stack-specific entries out of the kernel templates into
per-stack data in `plugin_stack_adapters._ignore_patterns` and injects
them via sentinel-comment markers at /lp-bootstrap render time.

Test coverage:
- (1) Per-stack rendering: parametrized for each of the three files
  across every stack with non-empty patterns. Render with stacks
  persisted, assert expected entries appear.
- (2) Greenfield no-op for .gitignore and .gitleaks.toml: the sentinels
  remain inert (comment context).
- (3) Greenfield sentinel-strip for .greptile.json: the sentinels are
  CONSUMED on every render (greenfield or otherwise) because they live
  inside a JSON string value.
- (4) Multi-stack dedup: shared patterns across stacks appear once.
- (5) Kernel-regression: the v2.1.5 hardcoded TS entries
  (`pnpm-lock.yaml`, `.next/`, `.turbo/`) are no longer in the kernel
  templates at the universal level.
- (6) Data-shape invariant: allowlist keys are subset of
  STACK_ID_ACTIVE_ENUM.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

_DATA_PATH = _SCRIPT_DIR / "plugin_stack_adapters" / "_ignore_patterns.py"
_spec_d = importlib.util.spec_from_file_location("_ignore_patterns_v216", _DATA_PATH)
assert _spec_d is not None and _spec_d.loader is not None
_data = importlib.util.module_from_spec(_spec_d)
_spec_d.loader.exec_module(_data)
GITIGNORE_PATTERNS_PER_STACK = _data.GITIGNORE_PATTERNS_PER_STACK
GITLEAKS_PATHS_PER_STACK = _data.GITLEAKS_PATHS_PER_STACK
GREPTILE_IGNORE_PATTERNS_PER_STACK = _data.GREPTILE_IGNORE_PATTERNS_PER_STACK

# stack_ignore_patterns uses relative imports — load via package.
from lp_bootstrap.stack_ignore_patterns import (  # noqa: E402
    enrich_gitignore_with_stacks,
    enrich_gitleaks_with_stacks,
    enrich_greptile_with_stacks,
)

_INFRA = _SCRIPT_DIR / "plugin_default_generators" / "infrastructure"
_GITIGNORE_KERNEL = _INFRA / "gitignore.j2"
_GITLEAKS_KERNEL = _INFRA / "gitleaks.toml.j2"
_GREPTILE_KERNEL = _INFRA / "greptile.json.j2"


def _render_kernel(path: Path) -> bytes:
    """Strip Jinja `{% raw/endraw %}` wrappers + minimal `{{ identity.* }}`
    rendering for test purposes. The enricher operates on rendered shell/
    config bytes; tests want a hermetic render that doesn't require the
    full Jinja env."""
    text = path.read_text(encoding="utf-8")
    text = text.replace("{% raw %}", "").replace("{% endraw %}", "")
    # The gitleaks + greptile templates reference `{{ identity.project_name }}`.
    # Replace with a fixture name so the test's downstream JSON/TOML
    # validity check still passes.
    text = text.replace("{{ identity.project_name }}", "test-fixture")
    return text.encode("utf-8")


def _write_config(tmp: Path, stacks: list[str]) -> None:
    cfg = tmp / ".launchpad" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    if stacks:
        lines = "\n".join(f"  - {s}" for s in stacks)
        cfg.write_text(f"stacks:\n{lines}\n", encoding="utf-8")
    else:
        cfg.write_text("stacks: []\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# (5) Kernel-regression: TS entries no longer at the universal level.
# ---------------------------------------------------------------------------


def test_gitignore_kernel_no_longer_hardcodes_ts_entries() -> None:
    text = _GITIGNORE_KERNEL.read_text(encoding="utf-8")
    # `.next/`, `.turbo/`, `node_modules/`, `.pnpm-store/` moved into
    # per-stack entries. None should appear in the kernel template now.
    for forbidden in (".next/", ".turbo/", ".pnpm-store/", "node_modules/"):
        # Allow mention inside comment blocks — the kernel template
        # references the historical entries in its BL-350 explainer
        # comment. Production lines (non-comment) must not contain them.
        production_lines = [
            line
            for line in text.splitlines()
            if line and not line.lstrip().startswith("#")
        ]
        for line in production_lines:
            assert forbidden not in line, (
                f"`.gitignore` kernel still hardcodes `{forbidden}` at the "
                f"universal level. Move into a stack entry in "
                f"_ignore_patterns.py."
            )


def test_gitleaks_kernel_no_longer_hardcodes_ts_entries() -> None:
    text = _GITLEAKS_KERNEL.read_text(encoding="utf-8")
    for forbidden in ("node_modules/", "\\.next/", "\\.turbo/", "pnpm-lock"):
        # Kernel template should only contain these in the comment
        # explainer block, not in the actual `paths = [...]` array.
        # The array body is delimited by `paths = [` and `]`.
        body_start = text.index("paths = [")
        body_end = text.index("]", body_start)
        # Strip the comment lines from the array body.
        array_body = "\n".join(
            line
            for line in text[body_start:body_end].splitlines()
            if not line.lstrip().startswith("#")
        )
        assert forbidden not in array_body, (
            f"`.gitleaks.toml` kernel paths array still hardcodes "
            f"`{forbidden}`. Move into a stack entry."
        )


# ---------------------------------------------------------------------------
# (6) Data-shape invariant.
# ---------------------------------------------------------------------------


def test_ignore_data_keys_are_subset_of_active_enum() -> None:
    from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM

    for name, mapping in (
        ("GITIGNORE_PATTERNS_PER_STACK", GITIGNORE_PATTERNS_PER_STACK),
        ("GITLEAKS_PATHS_PER_STACK", GITLEAKS_PATHS_PER_STACK),
        ("GREPTILE_IGNORE_PATTERNS_PER_STACK", GREPTILE_IGNORE_PATTERNS_PER_STACK),
    ):
        extras = set(mapping) - STACK_ID_ACTIVE_ENUM
        assert not extras, (
            f"{name} contains stack ids not in STACK_ID_ACTIVE_ENUM: {sorted(extras)}"
        )


# ---------------------------------------------------------------------------
# v2.1.6 BL-350 round-3 review fix (Codex P1 #4 + Greptile #1/#2/#3):
# every TS-toolchain stack MUST ignore `node_modules/` because the
# universal kernel no longer ships it. Pre round-3 `astro` shipped only
# `.astro/` and `ts_monorepo` was missing `.next/`. Generated TS repos
# accidentally staged dependency trees / Next build output.
# ---------------------------------------------------------------------------


def test_every_ts_stack_ignores_node_modules() -> None:
    """All TS-toolchain stacks must carry `node_modules/` in their
    .gitignore entry. The universal kernel no longer ships it (BL-350
    move-out), so every Node-based stack must re-add it explicitly."""
    ts_stacks = (
        "astro",
        "ts_monorepo",
        "nextjs_standalone",
        "nextjs_fastapi",
        "nextjs_hono_cloudflare",
        "nextjs_trpc_prisma",
    )
    for stack_id in ts_stacks:
        patterns = GITIGNORE_PATTERNS_PER_STACK[stack_id]
        assert "node_modules/" in patterns, (
            f"`{stack_id}` .gitignore must include `node_modules/` "
            f"(BL-350 kernel-move regression check); got: {patterns}"
        )


def test_ts_monorepo_ignores_next_build_output() -> None:
    """ts_monorepo repos commonly host a Next.js app under apps/web; the
    `.next/` build directory must be ignored. Pre round-3 the universal
    kernel had `.next/`; after BL-350 moved kernel cruft into per-stack
    data, ts_monorepo lost coverage until the round-3 fix restored it."""
    assert ".next/" in GITIGNORE_PATTERNS_PER_STACK["ts_monorepo"]


def test_astro_ignores_full_ts_toolchain_set() -> None:
    """Astro is a JS framework that always uses pnpm/npm/yarn. Pre
    round-3 the entry shipped only `.astro/` — accidentally staging
    `node_modules/`, lockfiles, tsbuildinfo was a real risk on every
    Astro greenfield."""
    astro_patterns = GITIGNORE_PATTERNS_PER_STACK["astro"]
    assert ".astro/" in astro_patterns
    assert "node_modules/" in astro_patterns
    assert "*.tsbuildinfo" in astro_patterns
    # gitleaks parity
    leaks = GITLEAKS_PATHS_PER_STACK["astro"]
    assert r"node_modules/" in leaks
    assert any("pnpm-lock" in p for p in leaks), f"got: {leaks}"
    # greptile parity
    greptile = GREPTILE_IGNORE_PATTERNS_PER_STACK["astro"]
    assert "**/node_modules/**" in greptile


# ---------------------------------------------------------------------------
# (2) Greenfield no-op for gitignore + gitleaks.
# ---------------------------------------------------------------------------


def test_gitignore_greenfield_returns_kernel_bytes_unchanged(tmp_path: Path) -> None:
    kernel = _render_kernel(_GITIGNORE_KERNEL)
    assert enrich_gitignore_with_stacks(kernel, tmp_path) == kernel


def test_gitleaks_greenfield_returns_kernel_bytes_unchanged(tmp_path: Path) -> None:
    kernel = _render_kernel(_GITLEAKS_KERNEL)
    assert enrich_gitleaks_with_stacks(kernel, tmp_path) == kernel


# ---------------------------------------------------------------------------
# (3) Greenfield strips sentinels for greptile.json.
# ---------------------------------------------------------------------------


def test_greptile_greenfield_strips_sentinels(tmp_path: Path) -> None:
    """On greenfield (no stacks), the greptile sentinels MUST be stripped
    from the output because they live inside a JSON string value.
    Leaving them in-place would produce a literal sentinel string in the
    rendered `ignorePatterns` field.
    """
    kernel = _render_kernel(_GREPTILE_KERNEL)
    enriched = enrich_greptile_with_stacks(kernel, tmp_path).decode("utf-8")
    assert "STACK_AWARE_GREPTILE_BEGIN" not in enriched
    assert "STACK_AWARE_GREPTILE_END" not in enriched
    # ignorePatterns becomes an empty string on greenfield.
    assert '"ignorePatterns": ""' in enriched


# ---------------------------------------------------------------------------
# (1) Per-stack rendering.
# ---------------------------------------------------------------------------


_PARAMETRIZE_STACKS = sorted(
    stack_id
    for stack_id in set(GITIGNORE_PATTERNS_PER_STACK)
    | set(GITLEAKS_PATHS_PER_STACK)
    | set(GREPTILE_IGNORE_PATTERNS_PER_STACK)
    if (
        GITIGNORE_PATTERNS_PER_STACK.get(stack_id)
        or GITLEAKS_PATHS_PER_STACK.get(stack_id)
        or GREPTILE_IGNORE_PATTERNS_PER_STACK.get(stack_id)
    )
)


@pytest.mark.parametrize("stack_id", _PARAMETRIZE_STACKS)
def test_gitignore_per_stack_patterns_injected(stack_id: str, tmp_path: Path) -> None:
    _write_config(tmp_path, [stack_id])
    kernel = _render_kernel(_GITIGNORE_KERNEL)
    enriched = enrich_gitignore_with_stacks(kernel, tmp_path).decode("utf-8")
    for pattern in GITIGNORE_PATTERNS_PER_STACK.get(stack_id, ()):
        assert pattern in enriched, (
            f"`{stack_id}` gitignore pattern `{pattern}` missing from rendered output."
        )


@pytest.mark.parametrize("stack_id", _PARAMETRIZE_STACKS)
def test_gitleaks_per_stack_paths_injected(stack_id: str, tmp_path: Path) -> None:
    _write_config(tmp_path, [stack_id])
    kernel = _render_kernel(_GITLEAKS_KERNEL)
    enriched = enrich_gitleaks_with_stacks(kernel, tmp_path).decode("utf-8")
    for pattern in GITLEAKS_PATHS_PER_STACK.get(stack_id, ()):
        # gitleaks patterns are TOML triple-quoted literals. The
        # rendered shape is `'''<pattern>'''`.
        triple = "'''"
        assert f"{triple}{pattern}{triple}" in enriched, (
            f"`{stack_id}` gitleaks pattern `{pattern}` missing from "
            f"rendered TOML allowlist."
        )


@pytest.mark.parametrize("stack_id", _PARAMETRIZE_STACKS)
def test_greptile_per_stack_patterns_injected(stack_id: str, tmp_path: Path) -> None:
    _write_config(tmp_path, [stack_id])
    kernel = _render_kernel(_GREPTILE_KERNEL)
    enriched = enrich_greptile_with_stacks(kernel, tmp_path).decode("utf-8")
    for pattern in GREPTILE_IGNORE_PATTERNS_PER_STACK.get(stack_id, ()):
        assert pattern in enriched, (
            f"`{stack_id}` greptile pattern `{pattern}` missing from "
            f"rendered ignorePatterns."
        )
    # Greenfield-sentinel removal also applies to non-empty renders.
    assert "STACK_AWARE_GREPTILE_BEGIN" not in enriched
    assert "STACK_AWARE_GREPTILE_END" not in enriched


# ---------------------------------------------------------------------------
# (4) Multi-stack dedup.
# ---------------------------------------------------------------------------


def test_multi_stack_gitignore_dedupes(tmp_path: Path) -> None:
    """ts_monorepo and nextjs_fastapi both contribute `node_modules/`.
    Combined render must contain it exactly once."""
    _write_config(tmp_path, ["ts_monorepo", "nextjs_fastapi"])
    kernel = _render_kernel(_GITIGNORE_KERNEL)
    enriched = enrich_gitignore_with_stacks(kernel, tmp_path).decode("utf-8")
    # Count occurrences in the sentinel block only.
    begin = enriched.index("STACK_AWARE_GITIGNORE_BEGIN")
    end = enriched.index("STACK_AWARE_GITIGNORE_END")
    block = enriched[begin:end]
    # node_modules/ should appear exactly once in the injected block.
    assert block.count("node_modules/") == 1, (
        f"Expected node_modules/ once in dedup'd block, got "
        f"{block.count('node_modules/')}"
    )


# ---------------------------------------------------------------------------
# Output validity: rendered .greptile.json must still parse as JSON.
# ---------------------------------------------------------------------------


def test_greptile_output_parses_as_json(tmp_path: Path) -> None:
    import json

    _write_config(tmp_path, ["ts_monorepo"])
    kernel = _render_kernel(_GREPTILE_KERNEL)
    enriched = enrich_greptile_with_stacks(kernel, tmp_path).decode("utf-8")
    parsed = json.loads(enriched)
    assert "ignorePatterns" in parsed
    assert isinstance(parsed["ignorePatterns"], str)
    # The ts_monorepo entry includes **/node_modules/** as a glob.
    assert "node_modules" in parsed["ignorePatterns"]


def test_greptile_greenfield_output_parses_as_json(tmp_path: Path) -> None:
    """Even on greenfield (empty ignorePatterns), the rendered file must
    still parse as valid JSON. Catches the regression where leaving
    sentinels in-place produced a literal sentinel string."""
    import json

    kernel = _render_kernel(_GREPTILE_KERNEL)
    enriched = enrich_greptile_with_stacks(kernel, tmp_path).decode("utf-8")
    parsed = json.loads(enriched)
    assert parsed.get("ignorePatterns") == ""
