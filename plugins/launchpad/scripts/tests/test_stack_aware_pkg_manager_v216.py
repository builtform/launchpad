"""BL-346 + BL-352 v2.1.6 — stack-aware package-manager commands in
`lefthook.yml` and `.github/workflows/ci.yml`.

Before v2.1.6 both files hardcoded `pnpm/action-setup` + `pnpm install`
+ `pnpm typecheck/test/lint/build`. Python / Ruby / Hugo / Go users hit
catastrophic failures (pnpm not installed; scripts don't exist).

v2.1.6 adds two enrichers (BL-346 lefthook + BL-352 ci.yml) that
rewrite `run: pnpm <cmd>` body lines into family-appropriate
equivalents based on the persisted `stacks:` array.

Test coverage:
- (1) Data shape: STACK_FAMILY maps every active stack to a known
  family; STACK_LEFTHOOK_HOOKS covers every family.
- (2) Greenfield (no config): both enrichers return kernel bytes
  unchanged (TS-stack identity preserved).
- (3) TS-stack project: both enrichers return kernel bytes unchanged
  (kernel already TS-correct).
- (4) Python-primary project: lefthook + ci.yml `run: pnpm test`
  lines rewritten to `run: pytest`, `pnpm typecheck` -> `pyright .`,
  etc.
- (5) Ruby-primary project: rewritten to `bundle exec` equivalents.
- (6) primary_family_for_stacks: picks first stack's family in
  multi-stack scenarios.
- (7) Unknown stack id: enricher returns kernel bytes unchanged
  (defaults to `ts` family => no-op).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

_DATA_PATH = _SCRIPT_DIR / "plugin_stack_adapters" / "_package_managers.py"
_spec = importlib.util.spec_from_file_location("_package_managers_v216", _DATA_PATH)
assert _spec is not None and _spec.loader is not None
_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_data)
STACK_FAMILY = _data.STACK_FAMILY
STACK_LEFTHOOK_HOOKS = _data.STACK_LEFTHOOK_HOOKS
primary_family_for_stacks = _data.primary_family_for_stacks
lefthook_hooks_for_family = _data.lefthook_hooks_for_family

from lp_bootstrap.stack_pkg_manager import (  # noqa: E402
    enrich_ci_yml_pkg_setup,
    enrich_lefthook_yml_pkg_commands,
)

# Kernel fixtures matching the relevant slices of lefthook.yml.j2 and
# ci.yml.j2. Real templates have additional content; the enrichers only
# care about the `run: pnpm <cmd>` body lines.
_LEFTHOOK_KERNEL = b"""
pre-commit:
  commands:
    typecheck:
      run: pnpm typecheck
      priority: 10
"""

_CI_KERNEL = b"""
jobs:
  build:
    steps:
      - uses: pnpm/action-setup@sha
      - name: Install
        run: pnpm install --frozen-lockfile
      - name: Type Check
        run: pnpm typecheck
      - name: Lint
        run: pnpm lint
      - name: Test
        run: pnpm test
      - name: Build
        run: pnpm build
"""


def _write_config(tmp: Path, stacks: list[str]) -> None:
    cfg = tmp / ".launchpad" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"  - {s}" for s in stacks)
    cfg.write_text(f"stacks:\n{lines}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# (1) Data shape invariants.
# ---------------------------------------------------------------------------


def test_stack_family_covers_active_enum() -> None:
    """Every stack id in STACK_ID_ACTIVE_ENUM must map to a known family."""
    from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM

    missing = STACK_ID_ACTIVE_ENUM - set(STACK_FAMILY)
    assert not missing, (
        f"STACK_FAMILY missing entries for active stacks: {sorted(missing)}. "
        f"Add a family mapping for every active stack."
    )


def test_every_family_has_lefthook_hooks() -> None:
    """Every family that STACK_FAMILY references must exist in
    STACK_LEFTHOOK_HOOKS."""
    families = set(STACK_FAMILY.values())
    missing = families - set(STACK_LEFTHOOK_HOOKS)
    assert not missing, (
        f"STACK_LEFTHOOK_HOOKS missing entries for families: {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# (2) + (3) Greenfield + TS-stack no-op.
# ---------------------------------------------------------------------------


def test_lefthook_greenfield_no_op(tmp_path: Path) -> None:
    assert (
        enrich_lefthook_yml_pkg_commands(_LEFTHOOK_KERNEL, tmp_path) == _LEFTHOOK_KERNEL
    )


def test_ci_greenfield_no_op(tmp_path: Path) -> None:
    assert enrich_ci_yml_pkg_setup(_CI_KERNEL, tmp_path) == _CI_KERNEL


def test_lefthook_ts_stack_no_op(tmp_path: Path) -> None:
    _write_config(tmp_path, ["ts_monorepo"])
    assert (
        enrich_lefthook_yml_pkg_commands(_LEFTHOOK_KERNEL, tmp_path) == _LEFTHOOK_KERNEL
    )


def test_ci_ts_stack_no_op(tmp_path: Path) -> None:
    _write_config(tmp_path, ["ts_monorepo"])
    assert enrich_ci_yml_pkg_setup(_CI_KERNEL, tmp_path) == _CI_KERNEL


# ---------------------------------------------------------------------------
# (4) Python-primary project rewrites.
# ---------------------------------------------------------------------------


def test_lefthook_python_stack_rewrites_typecheck(tmp_path: Path) -> None:
    """On a Python-primary project, `pnpm typecheck` becomes `pyright .`."""
    _write_config(tmp_path, ["python_django"])
    rewritten = enrich_lefthook_yml_pkg_commands(_LEFTHOOK_KERNEL, tmp_path).decode(
        "utf-8"
    )
    assert "run: pyright ." in rewritten, (
        f"Expected `pyright .` rewrite for python_django; got: {rewritten}"
    )
    # The original `pnpm typecheck` body must be gone (only `run: pyright .`
    # exists).
    assert "run: pnpm typecheck" not in rewritten


def test_ci_python_stack_rewrites_run_lines(tmp_path: Path) -> None:
    """On a Python-primary project, ci.yml `run: pnpm test` becomes
    `run: pytest`, `run: pnpm install --frozen-lockfile` becomes
    `run: pip install -r requirements.txt`, etc."""
    _write_config(tmp_path, ["python_generic"])
    rewritten = enrich_ci_yml_pkg_setup(_CI_KERNEL, tmp_path).decode("utf-8")
    assert "run: pytest" in rewritten
    assert "run: pyright ." in rewritten
    assert "run: ruff check ." in rewritten
    assert "run: pip install -r requirements.txt" in rewritten
    assert "run: pnpm test" not in rewritten
    assert "run: pnpm typecheck" not in rewritten


# ---------------------------------------------------------------------------
# (5) Ruby-primary project rewrites.
# ---------------------------------------------------------------------------


def test_ci_ruby_stack_rewrites_run_lines(tmp_path: Path) -> None:
    """On a Rails project, ci.yml gets `bundle exec rspec` etc."""
    _write_config(tmp_path, ["rails"])
    rewritten = enrich_ci_yml_pkg_setup(_CI_KERNEL, tmp_path).decode("utf-8")
    assert "run: bundle exec rspec" in rewritten
    assert "run: bundle exec sorbet tc" in rewritten
    assert "run: bundle exec rubocop" in rewritten


# ---------------------------------------------------------------------------
# (6) primary_family_for_stacks: first-stack wins.
# ---------------------------------------------------------------------------


def test_primary_family_picks_first_stack() -> None:
    """Multi-stack project uses the first stack's family as primary."""
    assert primary_family_for_stacks(["python_django", "ts_monorepo"]) == "python"
    assert primary_family_for_stacks(["ts_monorepo", "python_django"]) == "ts"
    assert primary_family_for_stacks(["rails"]) == "ruby"
    assert primary_family_for_stacks([]) == "ts"


# ---------------------------------------------------------------------------
# (7) Unknown stack defaults to ts (no-op enrichment).
# ---------------------------------------------------------------------------


def test_unknown_stack_id_does_not_rewrite(tmp_path: Path) -> None:
    """An unknown stack id falls through to family=`ts`; both enrichers
    return kernel bytes unchanged."""
    _write_config(tmp_path, ["a_future_stack_id"])
    assert (
        enrich_lefthook_yml_pkg_commands(_LEFTHOOK_KERNEL, tmp_path) == _LEFTHOOK_KERNEL
    )
    assert enrich_ci_yml_pkg_setup(_CI_KERNEL, tmp_path) == _CI_KERNEL


# ---------------------------------------------------------------------------
# Hooks data sanity: every family's lefthook hooks contains the expected keys.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", sorted(STACK_LEFTHOOK_HOOKS.keys()))
def test_lefthook_hooks_complete_per_family(family: str) -> None:
    hooks = lefthook_hooks_for_family(family)
    for key in (
        "test_command",
        "typecheck_command",
        "lint_command",
        "format_command",
        "install_command",
        "build_command",
    ):
        assert key in hooks, (
            f"family {family} lefthook_hooks_for_family() missing `{key}`"
        )


# ---------------------------------------------------------------------------
# v2.1.6 BL-346 Codex P1 #3 round-1 review fix: non-TS lefthook output must
# strip the `prettier-fix` and `eslint-fix` hook blocks. Their `{staged_files}`
# globs match `json/css/md/yml/yaml/html` — files Python / Ruby / Hugo / Go
# projects DO have (README.md, GitHub workflow YAMLs, pyproject sibling
# configs) — so pre-fix the hooks fired at the `pnpm` invocation and failed.
# ---------------------------------------------------------------------------


_LEFTHOOK_KERNEL_WITH_AUTOFIX_HOOKS = b"""
pre-commit:
  commands:
    typecheck:
      run: pnpm typecheck
      priority: 10
    prettier-fix:
      tags: format
      glob: "*.{ts,tsx,js,json,css,md,yml,yaml,html}"
      run: pnpm prettier --write {staged_files}
      stage_fixed: true
    eslint-fix:
      tags: lint
      glob: "*.{ts,tsx,js}"
      run: pnpm eslint --fix {staged_files}
      stage_fixed: true
    structure-check:
      tags: structure
      run: ./scripts/maintenance/check-repo-structure.sh
"""


def test_lefthook_python_stack_strips_prettier_fix_and_eslint_fix_hook_blocks(
    tmp_path: Path,
) -> None:
    """On a Python-primary project, the entire `prettier-fix:` and
    `eslint-fix:` hook command blocks must be removed from the rendered
    lefthook.yml. Their `{staged_files}` globs match `json/md/yml/yaml`
    which Python projects DO have — pre-v2.1.6 these hooks fired at the
    pnpm invocation and failed."""
    _write_config(tmp_path, ["python_django"])
    rewritten = enrich_lefthook_yml_pkg_commands(
        _LEFTHOOK_KERNEL_WITH_AUTOFIX_HOOKS, tmp_path
    ).decode("utf-8")
    assert "prettier-fix:" not in rewritten, (
        "Python-primary lefthook.yml must NOT contain the `prettier-fix:` "
        f"hook block; got:\n{rewritten}"
    )
    assert "eslint-fix:" not in rewritten, (
        "Python-primary lefthook.yml must NOT contain the `eslint-fix:` "
        f"hook block; got:\n{rewritten}"
    )
    assert "pnpm prettier" not in rewritten, (
        "Python-primary lefthook.yml must NOT reference pnpm prettier; "
        f"got:\n{rewritten}"
    )
    assert "pnpm eslint" not in rewritten, (
        "Python-primary lefthook.yml must NOT reference pnpm eslint; "
        f"got:\n{rewritten}"
    )
    # The non-pnpm hook (structure-check) must survive untouched.
    assert "structure-check:" in rewritten


def test_lefthook_ts_stack_preserves_prettier_fix_and_eslint_fix_hook_blocks(
    tmp_path: Path,
) -> None:
    """On a TS-primary project, the kernel template's `prettier-fix:`
    and `eslint-fix:` hook blocks must pass through unchanged — the
    enricher only strips them for non-TS families."""
    _write_config(tmp_path, ["ts_monorepo"])
    rewritten = enrich_lefthook_yml_pkg_commands(
        _LEFTHOOK_KERNEL_WITH_AUTOFIX_HOOKS, tmp_path
    )
    assert rewritten == _LEFTHOOK_KERNEL_WITH_AUTOFIX_HOOKS, (
        "TS-primary lefthook.yml must be byte-identical to kernel (no-op "
        "enrichment); the prettier-fix + eslint-fix stripping is non-TS only."
    )


def test_lefthook_rails_stack_strips_prettier_fix_and_eslint_fix_hook_blocks(
    tmp_path: Path,
) -> None:
    """Ruby/Rails parity: Rails projects must also get the hook blocks
    stripped — same `json/md/yml/yaml` glob issue as Python."""
    _write_config(tmp_path, ["rails"])
    rewritten = enrich_lefthook_yml_pkg_commands(
        _LEFTHOOK_KERNEL_WITH_AUTOFIX_HOOKS, tmp_path
    ).decode("utf-8")
    assert "prettier-fix:" not in rewritten
    assert "eslint-fix:" not in rewritten
    assert "structure-check:" in rewritten
