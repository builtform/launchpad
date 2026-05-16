"""Stack-aware rewrite of `lefthook.yml` and `.github/workflows/ci.yml`
package-manager commands (BL-346, BL-352, v2.1.6).

Before v2.1.6, `/lp-bootstrap` rendered both files with hardcoded
`pnpm/action-setup`, `pnpm install --frozen-lockfile`, `pnpm typecheck`,
`pnpm test`, etc. For Python / Ruby / Hugo / Go users those commands
fail at hook-exec time and at the CI setup step. v2.1.6 shifts the
canonical command sources into `plugin_stack_adapters._package_managers`
and rewrites the rendered files at the bootstrap render boundary.

Two enrichers, one per file:

  enrich_ci_yml_pkg_setup(kernel_bytes, cwd)
    Operates on `.github/workflows/ci.yml`. **Rewrites only the
    `run:` body lines** (test / typecheck / lint / build / install)
    with the family-appropriate command strings — see the
    `_PNPM_HOOK_REWRITES` map below for the exact set. The
    `pnpm/action-setup` + `actions/setup-node` setup-action steps
    themselves are LEFT IN PLACE; replacing the setup block per
    family (`actions/setup-python` etc.) requires a structural
    workflow rewrite that's deferred to v2.1.7 (see
    `docs/releases/v2.1.6.md` "Scope NOT in v2.1.6"). Non-TS users
    will see CI fail at the pnpm setup step on first run with a
    clear error; the recommended workaround is to swap the setup
    steps manually following the v2.1.7 documentation.

  enrich_lefthook_yml_pkg_commands(kernel_bytes, cwd)
    Operates on `lefthook.yml`. Rewrites the `pnpm typecheck`, `pnpm
    test`, `pnpm install --frozen-lockfile` etc. hook bodies with
    family-appropriate equivalents (see `_PNPM_HOOK_REWRITES`). For
    non-TS primary stacks, the entire `prettier-fix:` and
    `eslint-fix:` hook blocks are STRIPPED (their globs match
    `json/css/md/yml/yaml/html` which non-TS projects DO have, so
    pre-fix they fired at the `pnpm` invocation and failed).

Architecture mirrors BL-347's `stack_structure_check`: greenfield
returns kernel bytes unchanged for TS-stack identity preservation. The
v2.1.5 baseline expects the kernel template to produce TS-style output
by default; the enricher only rewrites when the primary detected stack
family is non-TS.

Defense-in-depth: every parse / lookup / regex failure path returns
input bytes unchanged. A misconfigured stack id can never break the
bootstrap render — worst case is the v2.1.5 baseline (TS-style hooks).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from ._enricher_common import read_stacks_safe

_SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
_PKG_MGRS_PATH = _SCRIPTS_ROOT / "plugin_stack_adapters" / "_package_managers.py"


def _load_pkg_data():  # type: ignore[no-untyped-def]
    """Return the `_package_managers` module (carrying
    `primary_family_for_stacks` + `lefthook_hooks_for_family`) on success.

    Returns None on import failure (caller defaults to no-op enrichment).
    """
    if not _PKG_MGRS_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        "pkg_managers_stack_pkg",
        _PKG_MGRS_PATH,
    )
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def _primary_family(cwd: Path) -> str:
    """Return the primary stack family for the project at `cwd`.

    Defaults to `"ts"` for greenfield (no config), unknown stack ids,
    or any data-load failure. The `"ts"` family is byte-identical to
    the v2.1.5 kernel templates, so the default is also the
    no-op-enrichment path.
    """
    stacks = read_stacks_safe(cwd, module_spec_name="plugin_config_loader_stack_pkg")
    data = _load_pkg_data()
    if data is None:
        return "ts"
    try:
        return data.primary_family_for_stacks(stacks)
    except Exception:
        return "ts"


# ---------------------------------------------------------------------------
# lefthook.yml: replace `pnpm <cmd>` hook bodies for non-TS families.
# ---------------------------------------------------------------------------
#
# Hook bodies in `lefthook.yml.j2` reference pnpm verbatim. The
# enricher operates on the rendered bytes (post-Jinja). Each kernel
# hook line `      run: pnpm <verb> [args]` is matched and rewritten
# per the family's lefthook_hooks_for_family() mapping. Only hooks
# whose `run:` body matches a known pnpm command get rewritten —
# non-pnpm hooks (structure-check, large-file-guard, etc.) pass through.

_PNPM_HOOK_REWRITES: dict[str, str] = {
    "pnpm typecheck": "typecheck_command",
    "pnpm test": "test_command",
    "pnpm lint": "lint_command",
    "pnpm format": "format_command",
    "pnpm build": "build_command",
    "pnpm install --frozen-lockfile": "install_command",
}


# v2.1.6 BL-346 review fix (Codex P1 #3): the `prettier-fix` and
# `eslint-fix` auto-fixer hooks in `lefthook.yml.j2` match
# `{staged_files}` against globs that include `json`, `css`, `md`,
# `yml`, `yaml`, `html`. On Python / Ruby / Hugo / Go projects those
# globs DO match real staged files (e.g., `.github/workflows/*.yml`,
# `README.md`, `pyproject.toml`'s sibling `*.yml` configs). Pre-v2.1.6
# the inert-hook claim was wrong; the hooks fired and failed at the
# `pnpm` invocation because pnpm wasn't installed. The fix is to
# strip both hook blocks from the rendered lefthook.yml for non-TS
# primary stacks.
#
# Hook-block regex: matches `    <name>:` (4-space-indented YAML key
# at the lefthook command level) through to the next blank line OR
# the next command sibling. Anchored to the start of a YAML line so
# inline references in comments don't match.
_PRETTIER_FIX_HOOK_RE = re.compile(
    r"\n    prettier-fix:\n(?:      [^\n]*\n)+",
)
_ESLINT_FIX_HOOK_RE = re.compile(
    r"\n    eslint-fix:\n(?:      [^\n]*\n)+",
)


def enrich_lefthook_yml_pkg_commands(kernel_bytes: bytes, cwd: Path) -> bytes:
    """Rewrite `pnpm <cmd>` hook bodies in lefthook.yml for non-TS
    primary stacks.

    For TS-family projects (or any stack data load failure), returns
    kernel bytes unchanged — the kernel template already emits the
    TS-appropriate pnpm commands.

    Targeted replacements (per `_PNPM_HOOK_REWRITES`):
      * `pnpm typecheck`     -> family's typecheck_command
      * `pnpm test`          -> family's test_command
      * `pnpm lint`          -> family's lint_command
      * `pnpm format`        -> family's format_command
      * `pnpm build`         -> family's build_command
      * `pnpm install --frozen-lockfile` -> family's install_command

    v2.1.6 BL-346 review fix (Codex P1 #3): for non-TS primary stacks
    the entire `prettier-fix` and `eslint-fix` hook blocks are STRIPPED
    from the rendered output. Pre-fix these hooks claimed to be inert
    on non-TS projects but their globs include `json` / `css` / `md` /
    `yml` / `yaml` / `html` — Python / Ruby / Hugo / Go projects DO
    have such files (README, GitHub workflow YAMLs, etc.) and the
    hooks fired at the `pnpm` invocation. The fix removes the hook
    blocks entirely; non-TS projects relying on Prettier/ESLint for
    their JS/TS sub-directories can re-add them via the consumer-side
    `lefthook.yml` user customization.
    """
    family = _primary_family(cwd)
    if family == "ts":
        return kernel_bytes

    data = _load_pkg_data()
    if data is None:
        return kernel_bytes
    try:
        hooks = data.lefthook_hooks_for_family(family)
    except Exception:
        return kernel_bytes

    decoded = kernel_bytes.decode("utf-8", errors="strict")

    # First: strip the prettier-fix / eslint-fix hook blocks for non-TS
    # families. These hooks fail at runtime on non-TS projects because
    # their globs match docs/yaml/css files that the project DOES have.
    decoded = _PRETTIER_FIX_HOOK_RE.sub("\n", decoded)
    decoded = _ESLINT_FIX_HOOK_RE.sub("\n", decoded)

    rewritten = decoded
    for pnpm_str, hook_key in _PNPM_HOOK_REWRITES.items():
        replacement = hooks.get(hook_key, "")
        if not replacement:
            # Empty replacement => the family doesn't have an
            # equivalent (e.g., Hugo has no test_command). Comment
            # the hook out by replacing with a `:` no-op shell builtin
            # so the YAML key still parses but execution is a no-op.
            replacement = ":"
        # Use word-boundary safe replace: match the pnpm string only
        # when it's the entire `run:` body line (avoids matching
        # inside comments or longer commands).
        pattern = re.compile(
            r"(\brun:\s*)" + re.escape(pnpm_str) + r"(\s*$)",
            re.MULTILINE,
        )
        rewritten = pattern.sub(rf"\g<1>{replacement}\g<2>", rewritten)
    return rewritten.encode("utf-8")


# ---------------------------------------------------------------------------
# ci.yml: replace the pnpm/setup-node setup block for non-TS families.
# ---------------------------------------------------------------------------


def enrich_ci_yml_pkg_setup(kernel_bytes: bytes, cwd: Path) -> bytes:
    """Rewrite `pnpm/action-setup` + `actions/setup-node` + the
    pnpm install/test/lint/typecheck/build `run:` lines for non-TS
    primary stacks.

    For TS-family projects (or any stack data load failure), returns
    kernel bytes unchanged — kernel template is TS-appropriate.

    The function ONLY rewrites the `run:` body lines via the same
    `_PNPM_HOOK_REWRITES` map used by the lefthook enricher. The
    setup-action steps themselves (`pnpm/action-setup@<sha>` +
    `actions/setup-node@<sha>`) are LEFT IN PLACE for non-TS
    projects — removing them requires structural workflow rewrite
    outside BL-352's scope. Non-TS users will see CI fail on the
    pnpm setup step until they manually swap the setup actions per
    `docs/guides/HOW_IT_WORKS.md` BL-352 documentation. This is a
    documented limitation, not a defect — the alternative (best-effort
    automatic action swap) would silently produce invalid workflows
    on any setup-action sha rotation.

    For Python / Ruby / Hugo / Go users, the actionable next step
    after `/lp-bootstrap` is the manual workflow edit; the rendered
    `.github/workflows/ci.yml` includes a comment header at the top
    referencing this guidance.
    """
    family = _primary_family(cwd)
    if family == "ts":
        return kernel_bytes

    data = _load_pkg_data()
    if data is None:
        return kernel_bytes
    try:
        hooks = data.lefthook_hooks_for_family(family)
    except Exception:
        return kernel_bytes

    decoded = kernel_bytes.decode("utf-8", errors="strict")
    rewritten = decoded
    for pnpm_str, hook_key in _PNPM_HOOK_REWRITES.items():
        replacement = hooks.get(hook_key, "")
        if not replacement:
            replacement = "echo 'skipped (no equivalent for this stack)'"
        # CI workflow uses `run: <cmd>` with potentially trailing
        # comments. Match the same `run:` body pattern as the lefthook
        # enricher.
        pattern = re.compile(
            r"(\brun:\s*)" + re.escape(pnpm_str) + r"(\s*$)",
            re.MULTILINE,
        )
        rewritten = pattern.sub(rf"\g<1>{replacement}\g<2>", rewritten)
    return rewritten.encode("utf-8")


__all__ = [
    "enrich_ci_yml_pkg_setup",
    "enrich_lefthook_yml_pkg_commands",
]
