"""Per-stack package-manager + tooling metadata (BL-346, BL-352, v2.1.6).

Before v2.1.6, `lp_bootstrap` rendered `lefthook.yml` and
`.github/workflows/ci.yml` with hardcoded `pnpm/action-setup`,
`pnpm install`, `pnpm typecheck`, `pnpm eslint --fix`, etc. For
Python / Ruby / Hugo / Go users those commands fail catastrophically:
pnpm isn't installed, the npm scripts don't exist, the CI workflow
aborts at setup.

This module declares per-stack tooling so the lefthook + ci.yml
enrichers can rewrite the hardcoded TS-monorepo defaults into
stack-appropriate equivalents:

  * `STACK_PACKAGE_MANAGER` — which package manager each stack uses
    (`pnpm`, `pip`, `bundler`, `hugo`, `go`, or `none`).
  * `STACK_CI_SETUP_ACTIONS` — the GitHub Actions setup steps each
    package manager needs (`pnpm/action-setup`, `actions/setup-python`,
    `ruby/setup-ruby`, etc.) plus the lockfile / version-file each
    references.
  * `STACK_LEFTHOOK_COMMANDS` — the lefthook hook bodies each stack
    family wants (test / typecheck / lint / format). For TS stacks
    the body matches the v2.1.5 kernel defaults verbatim — meaning
    TS-stack bootstrap renders are byte-identical to the pre-BL-346
    output. The enrichers only rewrite when the primary stack is
    non-TS.

Stack ids match `_renderer_base.STACK_ID_ACTIVE_ENUM`. Unknown stacks
default to the TS family (the kernel default) — strictly safer than
producing broken non-TS output for an unmodelled stack.
"""

from __future__ import annotations

from typing import Final, TypedDict


class CISetupAction(TypedDict):
    """One CI setup step rendered into `.github/workflows/ci.yml`."""

    uses: str  # GitHub Action ref with sha-pin (e.g. `pnpm/action-setup@...`)
    with_: dict[str, str]  # `with:` block key/value pairs


class StackLefthookHooks(TypedDict):
    """The four primary lefthook pre-commit / pre-push commands a
    stack contributes. `prettier_glob` / `eslint_glob` are TS-only;
    non-TS stacks set them to None.
    """

    test_command: str
    typecheck_command: str
    lint_command: str
    format_command: str
    install_command: str
    build_command: str


# Stack family categories. Each stack id maps to one family; the family
# determines which setup actions + lefthook commands apply.
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


# Per-family CI setup-action steps. Each family declares the actions
# that must run BEFORE `pnpm install` / `pip install` / `bundle install`.
# Empty tuple for `none` (the user customizes).
STACK_CI_SETUP_ACTIONS: Final[dict[str, tuple[CISetupAction, ...]]] = {
    "ts": (
        # Hardcoded to match the v2.1.5 kernel template byte-for-byte
        # so TS-stack bootstrap renders pass identity.
        {
            "uses": "pnpm/action-setup@0c17529a66aca453f9227af23103ed11469b1e47",
            "with_": {"version": "{{ default_pnpm_version }}"},
        },
        {
            "uses": "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020",
            "with_": {"node-version-file": ".nvmrc", "cache": "pnpm"},
        },
    ),
    "ts_python": (
        {
            "uses": "pnpm/action-setup@0c17529a66aca453f9227af23103ed11469b1e47",
            "with_": {"version": "{{ default_pnpm_version }}"},
        },
        {
            "uses": "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020",
            "with_": {"node-version-file": ".nvmrc", "cache": "pnpm"},
        },
        {
            "uses": "actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b",
            "with_": {"python-version": "3.11", "cache": "pip"},
        },
    ),
    "python": (
        {
            "uses": "actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2b",
            "with_": {"python-version": "3.11", "cache": "pip"},
        },
    ),
    "ruby": (
        {
            "uses": "ruby/setup-ruby@v1",
            "with_": {"bundler-cache": "true"},
        },
    ),
    "hugo": (
        {
            "uses": "actions/setup-go@v5",
            "with_": {"go-version-file": "go.mod"},
        },
        {
            "uses": "peaceiris/actions-hugo@v3",
            "with_": {"hugo-version": "latest"},
        },
    ),
    "go": (
        {
            "uses": "actions/setup-go@v5",
            "with_": {"go-version-file": "go.mod"},
        },
    ),
}


# Per-family lefthook hook bodies. The TS family matches v2.1.5
# kernel hooks byte-for-byte; non-TS families substitute the
# stack-appropriate commands.
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
        # first then dispatches Python via the shared partial. lefthook
        # treats command bodies as bash; the install/typecheck/lint
        # commands here are the TS half. Python gates live in the
        # `_python_gates.j2.fragment` partial that nextjs_fastapi includes.
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
    "hugo": {
        "install_command": "",  # Hugo binary self-contained
        "test_command": "",  # static sites have no test gate by default
        "typecheck_command": "",
        "lint_command": "",
        "format_command": "",
        "build_command": "hugo --gc --minify",
    },
    "go": {
        "install_command": "go mod download",
        "test_command": "go test ./...",
        "typecheck_command": "go vet ./...",
        "lint_command": "golangci-lint run",
        "format_command": "gofmt -w .",
        "build_command": "go build ./...",
    },
}


def stack_family(stack_id: str) -> str:
    """Return the family for a stack id, defaulting to `ts` (the kernel
    template default) for unknown stacks. Returning the kernel default
    means an unmodelled stack ships byte-identical to v2.1.5 — safer
    than emitting broken non-TS commands for it.
    """
    return STACK_FAMILY.get(stack_id, "ts")


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
    return stack_family(stacks[0])


def setup_actions_for_family(family: str) -> tuple[CISetupAction, ...]:
    """Return the CI setup-action tuple for a family. Unknown family
    -> empty tuple (no setup steps, user customizes)."""
    return STACK_CI_SETUP_ACTIONS.get(family, ())


def lefthook_hooks_for_family(family: str) -> StackLefthookHooks:
    """Return the lefthook hook command bodies for a family. Unknown
    family -> TS defaults (safe fallback matching kernel)."""
    return STACK_LEFTHOOK_HOOKS.get(family, STACK_LEFTHOOK_HOOKS["ts"])


__all__ = [
    "CISetupAction",
    "STACK_CI_SETUP_ACTIONS",
    "STACK_FAMILY",
    "STACK_LEFTHOOK_HOOKS",
    "StackLefthookHooks",
    "lefthook_hooks_for_family",
    "primary_family_for_stacks",
    "setup_actions_for_family",
    "stack_family",
]
