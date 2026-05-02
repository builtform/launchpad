# Roadmap

This document is the public-facing summary of where LaunchPad is going. It is updated each release. For day-to-day operator guidance see [HOW_IT_WORKS.md](docs/guides/HOW_IT_WORKS.md); for architectural rationale see [METHODOLOGY.md](docs/guides/METHODOLOGY.md).

## v1.0.x — stability patches

The first weeks after `v1.0.0` are reserved for patch-level fixes surfaced by real-world installation across diverse brownfields. No new features land on the patch line — only:

- Install-flow regressions
- Stack-detection misfires on previously untested stacks
- Doc corrections
- Cross-platform bugs (macOS / Linux / Windows under WSL)

If you hit a v1.0.0 issue, please open an issue from the `plugin install issue` template — install flow is our most likely failure surface and the dedicated template makes triage faster.

## v1.1.0 — Codex overlay

The headline feature of v1.1 is a **Codex overlay generator**: a build script that produces a parallel set of Codex CLI plugin artifacts from the canonical Claude Code plugin source. Goal: a single `LaunchPad` source tree that ships natively to both Claude Code (via the BuiltForm marketplace) and Codex CLI.

What this unlocks for Codex users:

- Native parallel sub-agent dispatch (currently degrades to single-generalist review in non-Claude CLIs)
- Skill format support (Codex's TOML-based skills)
- 1-command install via Codex's plugin system
- Version parity with the Claude Code plugin from the same git tag

The cross-tool bridge ([AGENTS.md](AGENTS.md)) continues to work for Cursor, Aider, Windsurf, Jules, and other CLIs that follow the AGENTS.md convention.

Other v1.1 items:

- Single-app TypeScript adapter (`ts_app` / `ts_service`) so plain Next.js / Hono projects without workspaces or Turborepo get sensible non-monorepo defaults instead of falling through to `generic`. Today the detector deliberately routes them to `generic` to avoid seeding hardcoded `apps/web/`, `apps/api/`, `packages/db/`, pnpm-only commands into single-app repos.
- Polyglot stack-detection refinements (Python framework distinction beyond Django, env-manager detection for poetry/uv)
- Non-interactive mode for dialogue-heavy commands (`/lp-pnf`, `/lp-brainstorm`)
- Brownfield TODO-import adapter (`/lp-shape-section --from-todo <id>`)
- Runner exit-code remap to the reserved 64–78 range
- Test-coverage gaps surfaced during v1.0 stabilization

## What is NOT in v1.1

Explicit non-goals so the scope stays honest:

- **Gemini CLI overlay.** Gemini users continue on the [AGENTS.md](AGENTS.md) bridge pattern with manual `context.fileName` configuration. Gemini support is on the long-term roadmap; no version assigned. Re-evaluated based on demand.
- **Auto-bundled memory backend.** LaunchPad does not ship its own session-memory store. Users who want verbatim session recall pair LaunchPad with [MemPalace](https://github.com/MemPalace/mempalace) — see [docs/guides/MEMPALACE_INTEGRATION.md](docs/guides/MEMPALACE_INTEGRATION.md).
- **Cross-CLI plugin marketplace federation.** Each CLI continues to ship from its own marketplace. The overlay generator produces artifacts; it does not publish them automatically.
- **`lp-` filename-prefix removal.** The plugin already namespaces commands at the CLI level; the additional `lp-` filename prefix is cosmetic redundancy. Removal is queued indefinitely as it touches ~100 files for no functional gain.

## v2.0 — Released

v2.0 introduces a 4-step user pipeline for greenfield project scaffolding: `/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define`. The brownfield path (existing-repo `/lp-brainstorm` → `/lp-define`) continues to work unchanged.

Full release notes: [docs/releases/v2.0.0.md](docs/releases/v2.0.0.md).

### v2.0 catalog (10 stacks)

| Stack      | Pillar                       | Status  |
| ---------- | ---------------------------- | ------- |
| `astro`    | Frontend Content/Performance | ✅ v2.0 |
| `next`     | Frontend App                 | ✅ v2.0 |
| `eleventy` | Frontend Content             | ✅ v2.0 |
| `hugo`     | Frontend Content (Go)        | ✅ v2.0 |
| `hono`     | Backend Edge-native TS       | ✅ v2.0 |
| `fastapi`  | Backend Python               | ✅ v2.0 |
| `django`   | Backend Python               | ✅ v2.0 |
| `rails`    | Backend MVC (Ruby)           | ✅ v2.0 |
| `supabase` | Backend Managed              | ✅ v2.0 |
| `expo`     | Frontend Mobile (RN)         | ✅ v2.0 |

The 10-stack scope is curated so every recommendation `/lp-pick-stack` makes points to a stack with a working `/lp-define` adapter rendering stack-specific architecture docs.

### v2.0 integrity primitives

- **JSON canonicalization + `canonical_hash()`** — byte-deterministic SHA-256 across implementations
- **`scaffold-decision.json` schema** with `bound_cwd` triple (realpath + st_dev + st_ino), nonce ledger replay protection, 4-hour replay window
- **`scaffold-receipt.json`** with chain-of-custody back to pick-stack
- **Path validator + greenfield/brownfield detector** as single sources of truth across commands
- **Rationale summary extractor** with prompt-injection defenses (NFKC normalization, forbidden-bullet patterns)
- **`safe_run()` subprocess helper** with strict env allowlist + LC_CTYPE override

## v2.1

v2.1 is documentation-only: refreshed `METHODOLOGY.md` + `HOW_IT_WORKS.md` + governance updates that reflect the v2.0 pipeline as a first-class workflow. No new stacks, no new commands.

## v2.2

v2.2 lands the operational/security infrastructure deferred from v2.0 per the v2.0 strip-back, plus the 10 deferred stacks queued behind v2.0's curated catalog.

### Operational/security infrastructure

- `forensic_writer.py` SRP-split module with `security-events.jsonl` chain-hashing
- Multi-signal CI detection (filesystem markers + parent-process check)
- PyYAML AST `pull_request_target` shape check (replaces grep-based v2.0 check)
- Tag protection rule + content verification + nightly watchdog
- Recall procedure (`vX.Y.Z-recalled` rename) + 24h post-tag observation window
- Authored runbooks: `rollback-runbook.md` + `branch-protection-token.md`
- Consolidated `v2-nightly-checks.yml` workflow
- `recovery_commands` runtime enforcement contract
- Exponential-backoff polling for `verify-v2-ship`
- KAT cross-platform parity (macOS CI leg)
- `.first-run-marker` integrity binding (JSON envelope + sha256 + bound_cwd)

### Deferred stacks

The following stacks are queued for v2.2 alongside the infrastructure work — user demand and ecosystem signal drive prioritization within the list.

| Stack                | Pillar                    |
| -------------------- | ------------------------- |
| `cloudflare-workers` | Backend Edge-native       |
| `tauri`              | Cross-platform desktop    |
| `nestjs`             | Enterprise TS backend     |
| `laravel`            | PHP MVC framework         |
| `vite`               | Generic SPA scaffolder    |
| `sveltekit`          | Frontend App              |
| `elysia`             | Backend Edge-native TS    |
| `phoenix-liveview`   | Backend Realtime (Elixir) |
| `convex`             | Backend Managed           |
| `flutter`            | Frontend Mobile (Dart)    |

Want a deferred stack moved up the v2.2 priority list? Open an issue at the LaunchPad GitHub repo with the title `[v2.2] Stack request: <name>` and a one-paragraph use case.

## Branch model

LaunchPad uses a simple branch model:

- **`main`** — the only long-lived branch. End-user plugin installs read from `main` (default branch). All releases tag `main`.
- **Feature branches** — short-lived, named with conventional-commit prefixes: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `docs/<topic>`, `refactor/<topic>`, `test/<topic>`, `style/<topic>`, `perf/<topic>`, `ci/<topic>`. Branched from `main`, merged back via PR.

Direct merges to `main` are blocked. All changes — including from the maintainer — go through pull requests and pass CI before landing.

A more elaborate Gitflow (with a separate `develop` integration branch and release branches) is not used at this time. If maintainer count grows past one, the model will be revisited.

## How to influence this roadmap

- **Open an issue** from the `feature_request` template with concrete use-cases.
- **Open a discussion** for shape questions before writing a feature request.
- **Send a PR** — PRs that align with a roadmap item or close a known limitation are reviewed quickly. PRs that expand scope beyond the roadmap may be asked to land as a separate maintained fork until the surface area stabilizes.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution flow.
