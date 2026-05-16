"""BL-347 v2.1.6 — stack-aware ALLOWED_DIRS / ALLOWED_CONFIGS injection.

Before v2.1.6 the rendered `scripts/maintenance/check-repo-structure.sh`
hard-coded LaunchPad-monorepo allowlist entries (`apps/`, `packages/`,
`pnpm-workspace.yaml`, etc.). Every greenfield single-app project hit a
P0 first-commit blocker: legitimate framework files at root —
`astro.config.mjs`, `next.config.ts`, `public/`, `src/`, `manage.py`,
`Gemfile` — got flagged as "unauthorized files" by the structure-check
pre-commit hook.

v2.1.6 fix:
- Kernel template ships a stack-agnostic baseline allowlist (universal
  directories + universal config files).
- Sentinel comments inside the `ALLOWED_DIRS=(...)` and
  `ALLOWED_CONFIGS=(...)` arrays mark the injection points.
- `lp_bootstrap/stack_structure_check.py` reads the persisted `stacks:`
  list from `.launchpad/config.yml`, looks up per-stack additions in
  `plugin_stack_adapters/_structure_allowlists.py`, and splices them
  between the sentinels.

Test coverage:
- (1) Per-stack rendering: parametrized across every entry in
  STACK_ID_ACTIVE_ENUM. Render the structure-check script with that
  stack persisted, assert all expected directories + configs are
  present in the rendered bash arrays.
- (2) Greenfield (no stacks persisted): rendering returns kernel bytes
  unchanged.
- (3) Multi-stack project (e.g., ts_monorepo + python_django): both
  stacks' additions appear, deduplicated.
- (4) Unknown stack id: enricher returns kernel bytes unchanged
  (defensive — never block bootstrap on a future stack id).
- (5) Sentinel-shape invariant: the kernel template contains both
  `STACK_AWARE_DIRS_BEGIN/END` and `STACK_AWARE_CONFIGS_BEGIN/END`
  sentinel pairs. The structure-check renderer expects these — a
  template edit that breaks them is a test failure.
- (6) Data-shape invariant: every key in `STACK_ALLOWED_DIRS` /
  `STACK_ALLOWED_CONFIGS` is in `STACK_ID_ACTIVE_ENUM`. Drift between
  the active enum and the allowlist data → test failure.
- (7) Kernel-allowlist regression: the kernel template no longer
  contains the hardcoded `apps/` / `packages/` entries that v2.1.5
  shipped at root level (those moved into the `ts_monorepo` stack
  entry).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# Load modules by file path to mirror BL-356's approach (the
# plugin_stack_adapters package import chain pulls in vendor deps the
# test suite doesn't need).
_ALLOWLISTS_PATH = _SCRIPT_DIR / "plugin_stack_adapters" / "_structure_allowlists.py"
_spec_a = importlib.util.spec_from_file_location("_structure_allowlists", _ALLOWLISTS_PATH)
assert _spec_a is not None and _spec_a.loader is not None
_allow = importlib.util.module_from_spec(_spec_a)
_spec_a.loader.exec_module(_allow)
STACK_ALLOWED_DIRS = _allow.STACK_ALLOWED_DIRS
STACK_ALLOWED_CONFIGS = _allow.STACK_ALLOWED_CONFIGS

# stack_structure_check uses relative imports — load via package path.
from lp_bootstrap.stack_structure_check import enrich_structure_check_with_stacks  # noqa: E402

_KERNEL_TEMPLATE = (
    _SCRIPT_DIR
    / "plugin_default_generators"
    / "infrastructure"
    / "scripts"
    / "maintenance"
    / "check-repo-structure.sh.j2"
)


def _render_kernel_bytes() -> bytes:
    """Return the kernel template bytes with the `{% raw %}` / `{% endraw %}`
    wrappers stripped. The enricher operates on rendered shell output
    (post-Jinja), not on the template source. Stripping the wrappers
    yields the same bytes a real bootstrap render would emit.
    """
    text = _KERNEL_TEMPLATE.read_text(encoding="utf-8")
    text = text.replace("{% raw %}", "").replace("{% endraw %}", "")
    return text.encode("utf-8")


def _write_config_with_stacks(tmp: Path, stacks: list[str]) -> None:
    """Write a minimal `.launchpad/config.yml` containing only `stacks:`.

    The enricher reads via `plugin-config-loader.read_stacks`, which
    parses the top-level YAML stacks key. Other config sections are not
    required for this enricher's behaviour.
    """
    cfg = tmp / ".launchpad" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    if stacks:
        lines = "\n".join(f"  - {s}" for s in stacks)
        cfg.write_text(f"stacks:\n{lines}\n", encoding="utf-8")
    else:
        cfg.write_text("stacks: []\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# (5) Sentinel-shape invariant.
# ---------------------------------------------------------------------------


def test_kernel_template_contains_sentinel_markers() -> None:
    """Kernel template must contain both sentinel pairs. A template edit
    that removes them silently degrades the structure check to
    kernel-allowlist-only (because the regex no longer matches and the
    splice returns unchanged bytes). This test catches the regression.
    """
    text = _KERNEL_TEMPLATE.read_text(encoding="utf-8")
    assert "STACK_AWARE_DIRS_BEGIN" in text
    assert "STACK_AWARE_DIRS_END" in text
    assert "STACK_AWARE_CONFIGS_BEGIN" in text
    assert "STACK_AWARE_CONFIGS_END" in text


# ---------------------------------------------------------------------------
# (7) Kernel-allowlist regression.
# ---------------------------------------------------------------------------


def test_kernel_template_no_longer_hardcodes_monorepo_dirs() -> None:
    """`apps/` and `packages/` MUST NOT appear in the kernel ALLOWED_DIRS
    block any longer — they're now contributed by the `ts_monorepo`
    stack entry. This regression test catches a future refactor that
    accidentally restores the hardcoded values.
    """
    rendered = _render_kernel_bytes().decode("utf-8")
    # Limit the search to the ALLOWED_DIRS=( ... ) block so we don't
    # match incidental occurrences elsewhere (e.g., comments referencing
    # the historical shape, or a directory entry like 'apps' inside an
    # allowed-name list elsewhere in the script).
    start = rendered.index("ALLOWED_DIRS=(")
    end = rendered.index(")", start)
    block = rendered[start:end]
    # Up to (but not including) the sentinels — the stack-aware section
    # is empty in kernel render bytes, so anything between them is
    # legitimate sentinel scaffolding, not a hardcoded value.
    kernel_section = block.split("STACK_AWARE_DIRS_BEGIN")[0]
    assert '"apps"' not in kernel_section, (
        '`apps/` must no longer appear in the kernel ALLOWED_DIRS block. '
        "Stack-aware injection delegates this entry to the `ts_monorepo` "
        "stack so non-monorepo projects don't inherit it."
    )
    assert '"packages"' not in kernel_section, (
        '`packages/` must no longer appear in the kernel ALLOWED_DIRS block.'
    )


# ---------------------------------------------------------------------------
# (6) Data-shape invariant.
# ---------------------------------------------------------------------------


def test_allowlist_keys_are_subset_of_active_enum() -> None:
    """Every stack id in the allowlist dicts MUST be in
    `STACK_ID_ACTIVE_ENUM` (or a v2.2 candidate that the active enum
    explicitly accepts). Drift between the two surfaces produces silent
    no-ops at render time. This test catches the drift early.
    """
    from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM

    extra_dirs = set(STACK_ALLOWED_DIRS) - STACK_ID_ACTIVE_ENUM
    extra_configs = set(STACK_ALLOWED_CONFIGS) - STACK_ID_ACTIVE_ENUM
    assert not extra_dirs, (
        f"STACK_ALLOWED_DIRS contains stack ids not in STACK_ID_ACTIVE_ENUM: "
        f"{sorted(extra_dirs)}. Either add them to the active enum or "
        f"remove from the allowlist dict."
    )
    assert not extra_configs, (
        f"STACK_ALLOWED_CONFIGS contains stack ids not in STACK_ID_ACTIVE_ENUM: "
        f"{sorted(extra_configs)}."
    )


# ---------------------------------------------------------------------------
# (2) Greenfield: no stacks → unchanged kernel bytes.
# ---------------------------------------------------------------------------


def test_greenfield_returns_kernel_bytes_unchanged(tmp_path: Path) -> None:
    """A project with no `.launchpad/config.yml` (greenfield bootstrap)
    must receive the kernel allowlist unchanged. Pre-config state is a
    legitimate intermediate during bootstrap; the enricher must not
    raise or otherwise alter behaviour.
    """
    kernel = _render_kernel_bytes()
    result = enrich_structure_check_with_stacks(kernel, tmp_path)
    assert result == kernel


def test_empty_stacks_list_returns_kernel_bytes_unchanged(tmp_path: Path) -> None:
    """`stacks: []` in config.yml (post-/lp-define on a stackless project)
    also returns unchanged kernel bytes."""
    _write_config_with_stacks(tmp_path, [])
    kernel = _render_kernel_bytes()
    result = enrich_structure_check_with_stacks(kernel, tmp_path)
    assert result == kernel


# ---------------------------------------------------------------------------
# (4) Unknown stack id: defensive no-op.
# ---------------------------------------------------------------------------


def test_unknown_stack_id_returns_kernel_bytes_unchanged(tmp_path: Path) -> None:
    """An unknown stack id (e.g., a v2.3 candidate that landed in
    config.yml ahead of the matching allowlist entry) MUST NOT raise
    or otherwise corrupt the rendered script. The enricher passes
    through with empty additions.
    """
    _write_config_with_stacks(tmp_path, ["a_future_stack_id_that_does_not_exist"])
    kernel = _render_kernel_bytes()
    result = enrich_structure_check_with_stacks(kernel, tmp_path)
    assert result == kernel


# ---------------------------------------------------------------------------
# (1) Per-stack rendering: parametrized across every key with non-empty
# additions.
# ---------------------------------------------------------------------------


# Build the parametrize list: every stack id that contributes at least
# one directory or config entry. Skipping ts_monorepo's empty configs
# entry (configs=() is still a legitimate test target via dirs).
_PARAMETRIZE_STACKS = sorted(
    stack_id
    for stack_id in set(STACK_ALLOWED_DIRS) | set(STACK_ALLOWED_CONFIGS)
    if STACK_ALLOWED_DIRS.get(stack_id) or STACK_ALLOWED_CONFIGS.get(stack_id)
)


def test_python_django_allowlist_includes_config_directory() -> None:
    """v2.1.6 BL-347 round-2 review fix (Codex P2 #4): default
    `django-admin startproject` layouts produce a `config/` directory
    (or `<project_name>/`) at root. Pre round-2 the allowlist only
    permitted `apps/`, so fresh Django projects hit the structure-check
    on first commit. The fix adds `config/` (the most common Django
    convention since cookiecutter-django popularised it)."""
    assert "config" in STACK_ALLOWED_DIRS["python_django"], (
        "python_django STACK_ALLOWED_DIRS must include `config` so "
        "default Django project layouts pass the structure check on "
        "first commit. Custom project module names are still a v2.1.7 "
        "BL (warning-based Python structure check)."
    )
    # Sanity: the original `apps/` entry survives.
    assert "apps" in STACK_ALLOWED_DIRS["python_django"]


@pytest.mark.parametrize("stack_id", _PARAMETRIZE_STACKS)
def test_per_stack_additions_injected(stack_id: str, tmp_path: Path) -> None:
    """For each stack, render the script with only that stack persisted
    and assert every expected directory + config appears in the rendered
    bash arrays.

    Verifies the sentinel splice mechanism, the lookup-by-stack-id
    dispatch, and the bash-array formatting. Per-stack data correctness
    is verified separately via the allowlist dict (which is its own SoT
    and reviewable).
    """
    _write_config_with_stacks(tmp_path, [stack_id])
    kernel = _render_kernel_bytes()
    enriched = enrich_structure_check_with_stacks(kernel, tmp_path).decode("utf-8")

    for expected_dir in STACK_ALLOWED_DIRS.get(stack_id, ()):
        assert f'"{expected_dir}"' in enriched, (
            f"`{stack_id}` should inject directory entry `{expected_dir}` "
            f"into ALLOWED_DIRS but it's missing from the rendered output."
        )
    for expected_cfg in STACK_ALLOWED_CONFIGS.get(stack_id, ()):
        assert f'"{expected_cfg}"' in enriched, (
            f"`{stack_id}` should inject config entry `{expected_cfg}` "
            f"into ALLOWED_CONFIGS but it's missing from the rendered output."
        )


# ---------------------------------------------------------------------------
# (3) Multi-stack project: both contributions appear, deduplicated.
# ---------------------------------------------------------------------------


def test_multi_stack_project_unions_and_dedupes(tmp_path: Path) -> None:
    """A project with multiple persisted stacks (the LaunchPad
    self-hosting case: `[python_generic, ts_monorepo]`) gets the union
    of both stacks' allowlist entries with duplicates removed.
    """
    _write_config_with_stacks(tmp_path, ["python_generic", "ts_monorepo"])
    kernel = _render_kernel_bytes()
    enriched = enrich_structure_check_with_stacks(kernel, tmp_path).decode("utf-8")

    # ts_monorepo contributes apps + packages
    assert '"apps"' in enriched
    assert '"packages"' in enriched
    # python_generic contributes src + app
    assert '"src"' in enriched
    assert '"app"' in enriched
    # And the python_generic config entries
    assert '"pyproject.toml"' in enriched
    assert '"requirements.txt"' in enriched

    # Dedup check: count "src" occurrences in the dirs sentinel block.
    # If both stacks contributed `src`, it must still appear exactly once.
    dirs_start = enriched.index("STACK_AWARE_DIRS_BEGIN")
    dirs_end = enriched.index("STACK_AWARE_DIRS_END")
    dirs_block = enriched[dirs_start:dirs_end]
    assert dirs_block.count('"src"') == 1, (
        "stack additions must be deduplicated; `src` should appear "
        "exactly once in the dirs sentinel block."
    )


# ---------------------------------------------------------------------------
# Hardening: bash array shape is preserved.
# ---------------------------------------------------------------------------


def test_enriched_output_still_parses_as_bash_array_syntax(tmp_path: Path) -> None:
    """Sanity check: the splice operation MUST preserve the surrounding
    `ALLOWED_DIRS=(\n  ...\n)` / `ALLOWED_CONFIGS=(\n  ...\n)` syntax.
    A malformed splice would emit invalid bash that the check script
    can't load.
    """
    _write_config_with_stacks(tmp_path, ["astro"])
    kernel = _render_kernel_bytes()
    enriched = enrich_structure_check_with_stacks(kernel, tmp_path).decode("utf-8")

    # The arrays must each open with `=(\n` and close with `\n)`.
    assert "ALLOWED_DIRS=(\n" in enriched
    assert "ALLOWED_CONFIGS=(\n" in enriched

    # Every injected line should have leading 2-space indent + a quoted entry.
    dirs_start = enriched.index("STACK_AWARE_DIRS_BEGIN")
    dirs_end = enriched.index("STACK_AWARE_DIRS_END")
    for line in enriched[dirs_start:dirs_end].splitlines()[1:]:  # skip sentinel line
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        assert line.startswith('  "') and line.endswith('"'), (
            f"injected line {line!r} must be `  \"<value>\"` shape"
        )
