"""Per-stack allowlist data for `scripts/maintenance/check-repo-structure.sh`.

Closes BL-347 (v2.1.6): the rendered `check-repo-structure.sh` previously
shipped a single hardcoded `ALLOWED_DIRS` / `ALLOWED_CONFIGS` allowlist
modeled on LaunchPad's own monorepo shape (`apps/`, `packages/`,
`pnpm-workspace.yaml`, etc.). On every greenfield single-app project
(Astro / Next / Hugo / etc.) the first commit hit a P0 ship-blocker:
legitimate framework files at repo root — `public/`, `src/`,
`astro.config.mjs`, `next.config.ts`, `manage.py`, `Gemfile` — got
flagged as "unauthorized files" and the structure-check pre-commit hook
refused to let the user commit.

This module declares one entry per active v2.1 stack and feeds it to
`lp_bootstrap/stack_structure_check.py`, which injects the stack-specific
additions between sentinel comments in the rendered script. The same
data also feeds `REPOSITORY_STRUCTURE.md` rendering when BL-336 lands.

Single source of truth. Per-adapter methods (BL-346 default_commands pattern)
intentionally NOT used here — the data is pure values, not behaviour, and
duplicating it across 11 adapter classes would invite per-stack drift.

Conventions for entries:
- Names are matched verbatim by the structure-check script's
  `[[ " ${ALLOWED_DIRS[@]} " =~ " ${item} " ]]` check. Use the casing
  that appears on disk (e.g., `"Gemfile"` not `"gemfile"`).
- Multiple config-file extensions for the same logical file (Astro's
  `.js` / `.mjs` / `.ts` config variants) are listed individually — the
  shell allowlist is a set check, so listing all variants is the cheapest
  correct representation.
- Stack ids match what `plugin-stack-detector.py` returns and what
  `.launchpad/config.yml`'s `stacks:` array persists. Adding a new stack
  here requires adding it to that closed enum.
- `generic` and any stack without a clear convention contribute an empty
  list. The user customizes for novel shapes after first commit — but the
  baseline (hardcoded TS-monorepo shape) is gone, so an unrecognized
  stack no longer blocks every legitimate root-level file.

BL-346 cross-reference: `default_commands()` will eventually move to a
per-adapter method on each stack class. This module's data is simpler
(pure value lists, no per-stack behaviour) and stays here. The two
shapes are intentionally separate.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Per-stack additions to ALLOWED_DIRS.
# ---------------------------------------------------------------------------
#
# Entries are EXTENSIONS to the kernel allowlist (which retains the
# universal entries like `docs/`, `.github/`, `.launchpad/`, `node_modules/`,
# `.git/`). The kernel allowlist no longer ships the monorepo-only
# `apps/` and `packages/` entries — those move into the `ts_monorepo`
# stack entry below.
# Stack ids match `_renderer_base.STACK_ID_ACTIVE_ENUM` — the 10 stacks
# v2.1 actually emits and dispatches. v2.2 candidate stacks (eleventy,
# hugo, hono, supabase, expo, etc.) will gain entries when their adapters
# land per BL-212; until then, unknown-stack lookup returns `()` (kernel
# allowlist only) which is strictly safer than rejecting their root files.
STACK_ALLOWED_DIRS: Final[dict[str, tuple[str, ...]]] = {
    "astro": ("public", "src"),
    # ts_monorepo carries the historical LaunchPad shape. Pre-v2.1.6 this
    # was the implicit default; the BL-347 fix makes it explicit so
    # non-monorepo stacks no longer inherit `apps/` + `packages/` and
    # then trip the "non-whitelisted directory at root" check on every
    # legitimate framework directory.
    "ts_monorepo": ("apps", "packages"),
    "nextjs_standalone": ("app", "src", "public", "pages"),
    "nextjs_fastapi": ("app", "src", "public", "pages", "api"),
    "nextjs_hono_cloudflare": ("app", "src", "public", "pages"),
    "nextjs_trpc_prisma": ("app", "src", "public", "pages", "prisma"),
    # Python stacks vary in project-name directory shape — `<project_name>/`
    # is the conventional Django location. The structure check allows
    # `apps/` as a generic Python application directory; users with a
    # `<project_name>/` directory at root append it to their local copy
    # after first commit.
    "python_django": ("apps",),
    "python_generic": ("src", "app"),
    "rails": ("app", "config", "db", "lib", "public", "test", "spec", "vendor"),
    # v2.1.6 BL-345 review fix (Codex P1 #2 + Greptile #2): `go_cli`
    # was emitted by the detector but missing from this allowlist; Go
    # projects hit a P0 first-commit blocker on `cmd/`, `internal/`,
    # `pkg/`, `vendor/` directories. Stack-typical Go layout per the
    # Go standard project layout convention.
    "go_cli": ("cmd", "internal", "pkg", "vendor", "api", "configs", "scripts"),
    # Generic / unrecognized stacks contribute nothing — user customizes.
    "generic": (),
}


# ---------------------------------------------------------------------------
# Per-stack additions to ALLOWED_CONFIGS.
# ---------------------------------------------------------------------------
#
# Same kernel-extension semantics as STACK_ALLOWED_DIRS. The kernel
# retains universal entries (`.gitignore`, `package.json`, `tsconfig.json`,
# etc.); per-stack additions cover framework-specific config files.
STACK_ALLOWED_CONFIGS: Final[dict[str, tuple[str, ...]]] = {
    "astro": ("astro.config.mjs", "astro.config.ts", "astro.config.js"),
    "ts_monorepo": (),  # kernel allowlist already covers the monorepo shape
    "nextjs_standalone": (
        "next.config.js",
        "next.config.ts",
        "next.config.mjs",
        "next-env.d.ts",
    ),
    "nextjs_fastapi": (
        "next.config.js",
        "next.config.ts",
        "next.config.mjs",
        "next-env.d.ts",
        # FastAPI side
        "pyproject.toml",
        "requirements.txt",
    ),
    "nextjs_hono_cloudflare": (
        "next.config.js",
        "next.config.ts",
        "next.config.mjs",
        "next-env.d.ts",
        "wrangler.toml",
        "wrangler.jsonc",
    ),
    "nextjs_trpc_prisma": (
        "next.config.js",
        "next.config.ts",
        "next.config.mjs",
        "next-env.d.ts",
    ),
    "python_django": ("manage.py", "requirements.txt", "pyproject.toml"),
    "python_generic": ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"),
    "rails": ("Gemfile", "Rakefile", "config.ru"),
    # v2.1.6 BL-345 review fix: Go projects need go.mod / go.sum at root.
    "go_cli": ("go.mod", "go.sum", "Makefile"),
    "generic": (),
}


def stack_allowed_dirs(stack_id: str) -> tuple[str, ...]:
    """Return the ALLOWED_DIRS additions for `stack_id`, or `()` if unknown.

    Unknown stacks return an empty tuple rather than raising — the
    structure-check renderer fail-closes by emitting the kernel allowlist
    only, which is strictly safer than raising into bootstrap.
    """
    return STACK_ALLOWED_DIRS.get(stack_id, ())


def stack_allowed_configs(stack_id: str) -> tuple[str, ...]:
    """Return the ALLOWED_CONFIGS additions for `stack_id`, or `()` if unknown."""
    return STACK_ALLOWED_CONFIGS.get(stack_id, ())


__all__ = [
    "STACK_ALLOWED_CONFIGS",
    "STACK_ALLOWED_DIRS",
    "stack_allowed_configs",
    "stack_allowed_dirs",
]
