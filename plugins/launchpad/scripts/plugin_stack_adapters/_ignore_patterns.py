"""Per-stack ignore-pattern data for the three downstream ignore surfaces.

Closes BL-350 (v2.1.6): the v2.1.5 `.gitignore` / `.gitleaks.toml` /
`.greptile.json` kernel templates hardcoded TS-monorepo cruft
(`.next/`, `.turbo/`, `pnpm-lock.yaml`) at the universal level. Every
Python / Ruby / Hugo / Go user got those entries — cosmetically misleading
("this template wasn't built for me") and noisy in `git status` once
node_modules/ inevitably appears via a tooling install.

v2.1.6 moves stack-specific entries out of the kernel templates into
per-stack entries here. The kernel templates keep only universal entries
(build outputs, OS files, `.env*`, Python cache that every Python tool
emits regardless of framework) plus a sentinel comment block where
per-stack additions get spliced at /lp-bootstrap render time.

Architecture parallels `_structure_allowlists.py` (BL-347 data store).
The three lp_bootstrap enrichers (`stack_structure_check`,
`stack_ignore_patterns`) share the same shape: read stacks: from
config.yml -> look up per-stack data -> splice between sentinels.

Three surfaces:

  GITIGNORE_PATTERNS_PER_STACK
    Lines appended to `.gitignore` between the kernel template's
    `# STACK_AWARE_BEGIN` / `# STACK_AWARE_END` sentinel comments. Each
    entry is one ignore pattern (e.g., `".next/"`).

  GITLEAKS_PATHS_PER_STACK
    Entries appended to `.gitleaks.toml`'s `[allowlist].paths` array.
    Each entry is a TOML triple-quoted regex literal body (not the
    triple quotes themselves; the enricher wraps).

  GREPTILE_IGNORE_PATTERNS_PER_STACK
    Glob patterns appended to `.greptile.json`'s `ignorePatterns`
    string. Entries are joined with `\\n` per Greptile's
    documented convention.

Unknown stacks return `()` from the lookup helpers — fail-closed defense
mirrors BL-347.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# .gitignore additions per stack.
# ---------------------------------------------------------------------------

GITIGNORE_PATTERNS_PER_STACK: Final[dict[str, tuple[str, ...]]] = {
    "astro": (".astro/",),
    "ts_monorepo": (
        "node_modules/",
        ".turbo/",
        ".pnpm-store/",
        "*.tsbuildinfo",
    ),
    "nextjs_standalone": (
        "node_modules/",
        ".next/",
        "out/",
        ".pnpm-store/",
        "*.tsbuildinfo",
    ),
    "nextjs_fastapi": (
        "node_modules/",
        ".next/",
        "out/",
        ".pnpm-store/",
        "*.tsbuildinfo",
        # Python side
        ".venv/",
        ".pytest_cache/",
        ".ruff_cache/",
    ),
    "nextjs_hono_cloudflare": (
        "node_modules/",
        ".next/",
        ".wrangler/",
        "*.tsbuildinfo",
    ),
    "nextjs_trpc_prisma": (
        "node_modules/",
        ".next/",
        "out/",
        "*.tsbuildinfo",
        # Prisma generated client lives in node_modules/, but local
        # migrate-against-sqlite dev convention is to also ignore the
        # dev sqlite file. Optional; users can remove for production-DB
        # workflows.
        "prisma/dev.db*",
    ),
    "python_django": (
        ".venv/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".mypy_cache/",
        "db.sqlite3",
        "db.sqlite3-journal",
        "media/",
        "staticfiles/",
    ),
    "python_generic": (
        ".venv/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".mypy_cache/",
    ),
    "rails": (
        "tmp/",
        "log/",
        "db/*.sqlite3",
        ".bundle/",
        "vendor/bundle/",
    ),
    # v2.1.6 BL-345 review fix (Codex P1 #2 + Greptile #2): Go projects
    # need their build/test artifacts ignored. Conventional Go binary
    # output goes alongside the source (no fixed `dist/`); the build is
    # invoked with `-o bin/<name>` in many projects so `bin/` is the
    # de-facto build dir.
    "go_cli": (
        "bin/",
        "vendor/",
        "*.test",
        "*.out",
        "coverage.txt",
    ),
    "generic": (),
}


# ---------------------------------------------------------------------------
# .gitleaks.toml allowlist additions per stack.
# ---------------------------------------------------------------------------
#
# Format: TOML regex body — the enricher wraps each in triple-quotes
# matching the existing `paths = ['''...''']` shape. Backslashes are
# emitted as-is (TOML triple-quoted literal strings do not interpret
# escapes — they are raw).

GITLEAKS_PATHS_PER_STACK: Final[dict[str, tuple[str, ...]]] = {
    "astro": (r"\.astro/",),
    "ts_monorepo": (
        r"node_modules/",
        r"\.next/",
        r"\.turbo/",
        r"pnpm-lock\.yaml",
        r"package-lock\.json",
        r"yarn\.lock",
    ),
    "nextjs_standalone": (
        r"node_modules/",
        r"\.next/",
        r"pnpm-lock\.yaml",
        r"package-lock\.json",
        r"yarn\.lock",
        r"out/",
    ),
    "nextjs_fastapi": (
        r"node_modules/",
        r"\.next/",
        r"pnpm-lock\.yaml",
        r"\.venv/",
        r"__pycache__/",
        r"poetry\.lock",
    ),
    "nextjs_hono_cloudflare": (
        r"node_modules/",
        r"\.next/",
        r"\.wrangler/",
        r"pnpm-lock\.yaml",
    ),
    "nextjs_trpc_prisma": (
        r"node_modules/",
        r"\.next/",
        r"pnpm-lock\.yaml",
    ),
    "python_django": (
        r"\.venv/",
        r"__pycache__/",
        r"\.pytest_cache/",
        r"poetry\.lock",
        r"uv\.lock",
        r"Pipfile\.lock",
    ),
    "python_generic": (
        r"\.venv/",
        r"__pycache__/",
        r"\.pytest_cache/",
        r"poetry\.lock",
        r"uv\.lock",
        r"Pipfile\.lock",
    ),
    "rails": (
        r"tmp/",
        r"log/",
        r"\.bundle/",
        r"vendor/bundle/",
        r"Gemfile\.lock",
    ),
    # v2.1.6 BL-345 review fix: Go projects.
    "go_cli": (
        r"vendor/",
        r"bin/",
        r"go\.sum",
    ),
    "generic": (),
}


# ---------------------------------------------------------------------------
# .greptile.json ignorePatterns additions per stack.
# ---------------------------------------------------------------------------
#
# Greptile takes one `\n`-joined string. Patterns are glob-style.

GREPTILE_IGNORE_PATTERNS_PER_STACK: Final[dict[str, tuple[str, ...]]] = {
    "astro": ("**/.astro/**",),
    "ts_monorepo": (
        "**/node_modules/**",
        "**/.next/**",
        "**/.turbo/**",
        "**/dist/**",
        "pnpm-lock.yaml",
        "**/*.d.ts",
    ),
    "nextjs_standalone": (
        "**/node_modules/**",
        "**/.next/**",
        "**/out/**",
        "pnpm-lock.yaml",
        "**/*.d.ts",
    ),
    "nextjs_fastapi": (
        "**/node_modules/**",
        "**/.next/**",
        "**/__pycache__/**",
        "**/.venv/**",
        "pnpm-lock.yaml",
        "**/*.d.ts",
    ),
    "nextjs_hono_cloudflare": (
        "**/node_modules/**",
        "**/.next/**",
        "**/.wrangler/**",
        "pnpm-lock.yaml",
    ),
    "nextjs_trpc_prisma": (
        "**/node_modules/**",
        "**/.next/**",
        "**/out/**",
        "pnpm-lock.yaml",
    ),
    "python_django": (
        "**/__pycache__/**",
        "**/.venv/**",
        "**/.pytest_cache/**",
        "**/migrations/**",
    ),
    "python_generic": (
        "**/__pycache__/**",
        "**/.venv/**",
        "**/.pytest_cache/**",
    ),
    "rails": (
        "**/tmp/**",
        "**/log/**",
        "**/vendor/bundle/**",
    ),
    # v2.1.6 BL-345 review fix: Go projects.
    "go_cli": (
        "**/vendor/**",
        "**/bin/**",
    ),
    "generic": (),
}


def gitignore_patterns(stack_id: str) -> tuple[str, ...]:
    """Return `.gitignore` additions for `stack_id`, or `()` if unknown."""
    return GITIGNORE_PATTERNS_PER_STACK.get(stack_id, ())


def gitleaks_paths(stack_id: str) -> tuple[str, ...]:
    """Return `.gitleaks.toml` allowlist additions for `stack_id`."""
    return GITLEAKS_PATHS_PER_STACK.get(stack_id, ())


def greptile_ignore_patterns(stack_id: str) -> tuple[str, ...]:
    """Return `.greptile.json` ignorePatterns additions for `stack_id`."""
    return GREPTILE_IGNORE_PATTERNS_PER_STACK.get(stack_id, ())


__all__ = [
    "GITIGNORE_PATTERNS_PER_STACK",
    "GITLEAKS_PATHS_PER_STACK",
    "GREPTILE_IGNORE_PATTERNS_PER_STACK",
    "gitignore_patterns",
    "gitleaks_paths",
    "greptile_ignore_patterns",
]
