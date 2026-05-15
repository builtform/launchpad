"""Per-stack package-manager + tooling metadata (BL-346, BL-352, v2.1.6).

Before v2.1.6, `lp_bootstrap` rendered `lefthook.yml` and
`.github/workflows/ci.yml` with hardcoded `pnpm/action-setup`,
`pnpm install`, `pnpm typecheck`, `pnpm eslint --fix`, etc. For
Python / Ruby / Hugo / Go users those commands fail catastrophically:
pnpm isn't installed, the npm scripts don't exist, the CI workflow
aborts at setup.

This module declares per-stack-family lefthook hook bodies so the
lefthook + ci.yml enrichers in `lp_bootstrap/stack_pkg_manager.py`
can rewrite the hardcoded TS-monorepo defaults into stack-appropriate
equivalents.

Stack ids match `_renderer_base.STACK_ID_ACTIVE_ENUM`. Unknown stacks
default to the TS family (the kernel default) — strictly safer than
producing broken non-TS output for an unmodelled stack. The TS-family
entry matches the v2.1.5 kernel template byte-for-byte so TS-stack
bootstrap renders pass identity.

CI setup-action data (`pnpm/action-setup` vs `actions/setup-python` vs
`ruby/setup-ruby` etc.) is documented as deferred to v2.1.7 — see the
`enrich_ci_yml_pkg_setup` docstring in `stack_pkg_manager.py`. The
v2.1.6 scope is `run:` body rewrites only; setup-step swaps require a
structural workflow rewrite outside this BL.
"""

from __future__ import annotations

from typing import Final, TypedDict


class StackLefthookHooks(TypedDict):
    """The lefthook hook bodies a stack-family contributes. Keys map to
    the entries in `_PNPM_HOOK_REWRITES` in `stack_pkg_manager.py`; new
    keys here require a matching entry there.
    """

    test_command: str
    typecheck_command: str
    lint_command: str
    format_command: str
    install_command: str
    build_command: str


# Stack family categories. Each stack id maps to one family; the family
# determines which lefthook commands apply.
STACK_FAMILY: Final[dict[str, str]] = {
    "astro": "ts",
    "ts_monorepo": "ts",
    "nextjs_standalone": "ts",
    "nextjs_fastapi": "ts_python",
    "nextjs_hono_cloudflare": "ts",
    "nextjs_trpc_prisma": "ts",
    "python_django": "python",
    "python_generic": "python",
    "rails": "ruby",
    "generic": "ts",  # fail-safe default; matches v2.1.5 kernel behaviour
}


# Per-family lefthook hook bodies. The TS family matches v2.1.5 kernel
# hooks byte-for-byte; non-TS families substitute the stack-appropriate
# commands. Only families that an active stack id maps to are included
# here — adding a new family requires also adding a `STACK_FAMILY` entry
# pointing at it.
STACK_LEFTHOOK_HOOKS: Final[dict[str, StackLefthookHooks]] = {
    "ts": {
        "install_command": "pnpm install --frozen-lockfile",
        "test_command": "pnpm test",
        "typecheck_command": "pnpm typecheck",
        "lint_command": "pnpm lint",
        "format_command": "pnpm format",
        "build_command": "pnpm build",
    },
    "ts_python": {
        # ts_python composites both runtimes; pre-commit runs the TS gates
        # first then dispatches Python via the shared partial. The
        # install/typecheck/lint commands here are the TS half; Python
        # gates live in the `_python_gates.j2.fragment` partial that
        # nextjs_fastapi includes.
        "install_command": "pnpm install --frozen-lockfile && pip install -r requirements.txt",
        "test_command": "pnpm test && pytest",
        "typecheck_command": "pnpm typecheck && pyright .",
        "lint_command": "pnpm lint && ruff check .",
        "format_command": "pnpm format && ruff format .",
        "build_command": "pnpm build",
    },
    "python": {
        "install_command": "pip install -r requirements.txt",
        "test_command": "pytest",
        "typecheck_command": "pyright .",
        "lint_command": "ruff check .",
        "format_command": "ruff format .",
        "build_command": "python -m build",
    },
    "ruby": {
        "install_command": "bundle install",
        "test_command": "bundle exec rspec",
        "typecheck_command": "bundle exec sorbet tc",
        "lint_command": "bundle exec rubocop",
        "format_command": "bundle exec rubocop -a",
        "build_command": "bundle exec rails assets:precompile",
    },
}


def primary_family_for_stacks(stacks: list[str]) -> str:
    """Pick the primary family for a multi-stack project.

    Selection rule:
      * If exactly one family is represented, use it.
      * If multiple, prefer the FIRST stack's family (matches v2.1.5
        `stacks:` ordering convention — the first entry is primary).
      * Empty list -> `ts` (kernel default).
    """
    if not stacks:
        return "ts"
    return STACK_FAMILY.get(stacks[0], "ts")


def lefthook_hooks_for_family(family: str) -> StackLefthookHooks:
    """Return the lefthook hook command bodies for a family. Unknown
    family -> TS defaults (safe fallback matching kernel)."""
    return STACK_LEFTHOOK_HOOKS.get(family, STACK_LEFTHOOK_HOOKS["ts"])


__all__ = [
    "STACK_FAMILY",
    "STACK_LEFTHOOK_HOOKS",
    "StackLefthookHooks",
    "lefthook_hooks_for_family",
    "primary_family_for_stacks",
]
