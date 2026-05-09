# Changelog

All notable changes to LaunchPad are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Tracked in [ROADMAP.md](ROADMAP.md). v2.2 lands the 15 operational/security infrastructure surfaces deferred from v2.0 plus the 10 deferred stacks. See `docs/tasks/BACKLOG.md` (BL-251 through BL-254) for v2.2-deferred items captured during v2.1 ship.

## [2.1.1]

Mandatory `/lp-review` dual-pass wiring + `--no-context` blind-review flag + Layer 3 static-analysis gate (ruff + bandit + semgrep + pyright). Universal `lefthook.yml` routes test/typecheck/lint through `plugin-build-runner.py` for stack-aware dispatch. **Validation:** v2.1.1's mandatory review gates were validated by passing this very release through them — Phase 5's commit was the first production exercise of the full Layer 1+2+3 stack.

### For LaunchPad users (downstream behavior changes)

- `/lp-review --no-context` flag (bias-stripped blind pass; Phase 1)
- **Mandatory dual-pass review in `/lp-commit` Step 2.5 + `/lp-ship` Step 4.6** — was previously optional yes/no prompt; honors `--skip-review` on hotfix branches with TTY-guarded `BYPASS REVIEW` confirmation + audit-trail trailer (Phase 2). **Behavior change.**
- `/lp-ship` 3-round autonomous fix loop with 90-min timeout (Phase 2)
- Universal `lefthook.yml` (self-host only at v2.1.1) routes test/typecheck/lint through `plugin-build-runner.py` — stack-aware per `.launchpad/config.yml` `commands.*` arrays (Phase 3 D1+D2). **Downstream lefthook propagation tracked as BL-316, scheduled for v2.1.2.**
- New guide: [`docs/guides/CODE_REVIEW_LAYERS.md`](docs/guides/CODE_REVIEW_LAYERS.md) — three-layer architecture rationale + override patterns
- `CLAUDE.md` Definition of Done extended with conditional Python gates (apply only when changes touch `*.py`)

### For LaunchPad contributors (self-host hardening)

- `pytest` direct pre-push lefthook entry (Phase 3 R1-T1-8)
- `plugin-v2-handshake-lint.py` `_is_v2_module()` path-prefix matcher (Phase 3 BL-237 closure)
- Layer 3 static-analysis stack on plugin scripts (ruff + bandit + semgrep + pyright + pytest)
- **3 active cross-cutting invariant semgrep rules + 1 BL-deferred** in `plugins/launchpad/.semgrep/launchpad-internal.yml` (Phase 4) — sentinel-precedes-materialize rule deferred to BL-303 per >2 fail-to-validate iterations
- 8 universal semgrep rules in `plugins/launchpad/.semgrep/general.yml` (Phase 4) — path-traversal rule narrowed post-iteration from `Path() / X` to `open(... + USER_INPUT)`
- pip-compile-locked `requirements.txt` with `--require-hashes` (Phase 4) — Path A authorization; +1228 LOC transitive lock
- `Makefile` with `lock-deps` target for regenerating `requirements.txt` (Phase 4 — Path A authorization)
- Pyright strict mode on 3 security-boundary modules (`decision_validator.py`, `nonce_ledger.py`, `decision_integrity.py`) with documented `# type: ignore` ladders for residual `Any`-leakage (Phase 4 Hybrid disposition); `decision_validator.py` extended directive disables 4 Any-leakage rules
- 8 pyright per-rule severity downgrades in `pyproject.toml` (`reportArgumentType`, `reportOptionalMemberAccess`, etc.) — admits pre-existing v2.0 surface as warnings; gate exits 0
- Vendored version-pin files: `_vendor/{BANDIT,PYRIGHT,RUFF,SEMGREP}_VERSION` (Phase 4)
- 4 `# nosec` annotations with BL/HANDSHAKE/plan cross-reference triple (B602 ×2 + B506 + B608)
- 2 NEW regression-shield tests at `plugins/launchpad/scripts/tests/`: `test_nonce_ledger_mountpoint_tiebreak.py` (D11), `test_cwd_state_single_readme_carveout.py` (D15). D3 cascade-recovery enforced via the pre-existing `test_brownfield_manifests_single_source.py` (which Phase 4 preserved by restoring the `from cwd_state import BROWNFIELD_MANIFESTS` re-export in `plugin-stack-detector.py` per Commit 1 ride-along).
- 6 new step entries in `.github/workflows/v2-handshake-lint.yml` (4 logical tools per Phase 4 R1-T1-12)
- 7 D-verdict FIX items absorbed (D3 + D9 + D10 + D11 + D12 + D13 + D15)
- `nonce_ledger.UUID_HEX_RE` promoted to public alias (Phase 4 amend P1 SoT consolidation)

### Closed BL items

- **BL-236** (Lefthook Python coverage expansion): SHIPPED via Phase 3 + Phase 4 — see PR #<PR-TBD>
- **BL-237** (V2_MODULES scope tightening): SHIPPED via Phase 3 — see PR #<PR-TBD>
- **BL-245** (Stack-aware lefthook generation): SHIPPED via universal lefthook + build-runner indirection (master plan D1); see PR #<PR-TBD>

### Deferred to v2.1.3 / v2.2

- BL-291..297 + 22 v2.1.1→v2.2 retags + 8 v2.1.1→v2.1.3 retags (per BACKLOG.md)
- BL-298 (pyright strict on engine modules) — v2.1.3
- BL-299 (nodeenv binary outside pip hash coverage) — v2.1.3
- BL-300 (`--strict-dispatch` flag on `/lp-review` — closes Phase 3 Hard Rule 6 violation class) — v2.1.3
- BL-301 (semgrep synthetic-violation fixtures — Phase 4 deferred; Phase 5 Slice F surfaced) — v2.1.3
- BL-303 (`lp-engine-sentinel-must-precede-materialize` semgrep rule — Phase 4 BL-deferred per >2 fail-to-validate iterations) — v2.1.3
- BL-304 (secret-patterns.txt over-match on `\bdownstream\s+project` — false-positive in Jinja-template comment surface) — v2.1.3
- BL-305 (portable timeout wrapper for macOS lefthook entries — `timeout` binary absent on macOS; wrappers removed) — v2.1.3
- BL-306 (semgrep allowlist-vs-handshake-lint parallelism — R2-T1-14 placeholder from Phase 4) — v2.1.3
- BL-307 (9 simplicity-reviewer cleanup-style P1s deferred from Phase 4 /lp-review — out of v2.1.1 scope per Phase 4 sibling triage) — v2.1.3 / v2.2
- Tag-signing automation (BL-258, v2.2) — v2.1.1 tag is unsigned per existing posture (see SECURITY.md)

## [2.1.0]

`/lp-scaffold-stack` now actually scaffolds via specialized v2.1 adapters — the v2.1 Adapter Protocol's `dispatch_by_stack_ids` is wired in production for the 5 active stacks (`ts_monorepo`, `nextjs_standalone`, `nextjs_fastapi`, `astro`, `generic`). The 5 v2.2-candidate stacks (`python_django`, `python_generic`, `nextjs_hono_cloudflare`, `nextjs_trpc_prisma`, `rails`) require explicit opt-in via `--accept-v22-fallback`; v2.2 ships dedicated support. Schema 1.0 decisions are now hard-rejected at validate time — v2.0 reached zero in-the-wild adoption before v2.1 ship; the rejection message names the regeneration recipe verbatim.

Full release notes in [docs/releases/v2.1.0.md](docs/releases/v2.1.0.md).

### Added (v2.1.0 ship)

- `dispatch_by_stack_ids` wired in `/lp-scaffold-stack`'s production pipeline; legacy `materialize_layer` orchestrate/curate path deleted (`layer_materializer.py` removed)
- `--accept-v22-fallback` kwarg surface on `run_pipeline` for v2.2-candidate stack-ids; receipt records `adapter_dispatch_meta.fallback_ids` when used
- `dispatch_enumeration.py` module: post-dispatch workspace walker with symlink rejection, cwd-containment check, `.git*` + credential-dotdir exclusion, 50k-file cap
- Receipt schema gains `LayerReceiptEntry` TypedDict (replaces deleted `MaterializationResult` dataclass) + `adapter_dispatch_meta` allowlisted sibling
- Decision schema_1.1 envelope gains `_META_KEY_REGEX` + `_ALLOWED_DECISION_META_KEYS` allowlist; new `*_meta` keys require schema_version bump

### Bug fixes (v2.1.0 ship)

- `atomic_io._write_all` POSIX short-write loop at all 3 atomic-write call sites (was `os.write` once; could silently truncate)
- Case E "y" all-files-missing schema corruption fix: signal moves from `_meta` smuggled into `kernel_render_state` (corrupted per-file uniform shape) to a top-level `kernel_render_state_meta` sibling
- Workflow SHA-pinning at all 8 sites (root + `.j2` templates) with new lefthook grep gate enforcing the pin
- Downstream `.j2` workflows gain `permissions: { contents: read }` and `persist-credentials: false` on `actions/checkout`
- `--seed-brownfield` reframed as `--dry-run`-only at v2.1.0; non-dry-run create path lands at v2.1.1 BL-271
- `lp-scaffold-stack.md` doc drift reconciled to the new v2.1 dispatch surface

### Added

- Sealed identity contract: 7-field identity block (`pii_opt_in`, `project_name`, `email`, `copyright_holder`, `repo_url`, `license`, `license_other_body`) sealed under `schema_version: "1.1"` envelope at `/lp-pick-stack` time
- `/lp-bootstrap` command: bootstraps the harness configuration from plugin-bundled defaults with sentinel-protected execution
- `/lp-update-identity` command: edits sealed identity values atomically with byte-identical preservation of `generated_at` across re-seal; 5-case re-entry detection (A through E) with transparent legacy v1.0 envelope migration
- Composition wrapper at `plugin_stack_adapters/composition.py`: pair-table-from-data resolution at runtime, per-stack tempdir isolation, N=2 cap on multi-stack scaffolds
- 7 stack-agnostic kernel templates (LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, README.md, SECURITY.md, AGENTS.md, CLAUDE.md) with full canonical license bodies for MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, ISC, MPL-2.0
- Stack-aware review dispatch: 36 review agents gain `stack_scope` frontmatter (16 `core_pipeline`, 13 `stack:any`, 6 `design_quality`, 1 `skill_quality`); `/lp-review` and `/lp-harden-plan` filter agents per detected stack
- `StackIdV22Candidate` forward-compat enum: 5 v2.2-candidate stack ids (`python_django`, `python_generic`, `nextjs_hono_cloudflare`, `nextjs_trpc_prisma`, `rails`) routed to `generic` with verbatim INFO log
- `lp_define_runner.py` render-batch flow: `render_batch` + `scan_batch` + `write_batch` gates every kernel and adapter render through a full-batch secret scanner; any finding refuses the entire batch atomically
- `secret_allowlist.py` with three suppression mechanisms (Jinja-comment, file-path-glob, regex) plus `BUNDLED_DEFAULT_PATTERNS` fallback when `.launchpad/secret-patterns.txt` is absent
- `docs/guides/SECRET_SCANNER_TUNING.md`: tuning guide for the secret-scanner gate

### Changed

- v2.0 scaffold artifacts auto-migrate to `schema_version: "1.1"` on first contact with the v2.1 plugin via in-memory-first transparent migration
- Bidirectional sentinel cross-detect across `/lp-bootstrap`, `/lp-update-identity`, `/lp-scaffold-stack` so two concurrent operations cannot corrupt each other's state
- ALLOWLIST-based handshake-lint over `atomic_write_replace` callers via AST + import-binding resolution; alias-rename bypasses caught at lint time
- CODEOWNERS extended with 8 v2.1 schema-source entries; modifications to schema constants require same-commit append-only audit-log entries

### Deferred

- v2.2: composition wrapper test stress harness (3 tests under `test_composition_wrapper.py` family); template cache concurrency hardening; brainstorm Python runner extraction; `pip-audit` and `osv-scanner` promotion from advisory to required gates; 4 manifest tampering scenarios (NullByteInjection, UnicodeNormalizationAttack, ZIP-bomb, ConcurrentModification); GPG-signed tags
- See `docs/tasks/BACKLOG.md` BL-251 through BL-254

## [2.0.0] — 2026-05-01

Major release. Greenfield project scaffolding pipeline ships: `/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define`. Chain-of-custody-bound (SHA-256 envelopes + UUID4 nonces + bound_cwd triple), brownfield-aware (refuses to scaffold over existing projects), 10-stack catalog. Brownfield path unchanged from v1.x.

Full release notes in [docs/releases/v2.0.0.md](docs/releases/v2.0.0.md).

### Added

- Four-command greenfield pipeline (brainstorm → pick-stack → scaffold-stack → define) with structured `rationale_summary` defense-in-depth so consumers never read raw rationale.md
- 10-stack catalog: `astro`, `next`, `eleventy`, `hugo`, `hono`, `fastapi`, `django`, `rails`, `supabase`, `expo`
- 6 new `/lp-define` adapters: `astro`, `fastapi`, `rails`, `hugo`, `eleventy`, `expo`
- 18-category routing catalog with 5 ambiguity clusters (`category-patterns.yml`)
- Forensic primitives: `decision_integrity.canonical_hash`, `path_validator`, `cwd_state`, `safe_run`, NFKC-aware sanitizer, 1MB-rollover nonce ledger, `bound_cwd` triple, `pid_identity` cross-platform
- 11 OPERATIONS §6 acceptance gates + 8 joint-pipeline integration tests + 100-iteration nonce concurrency race loop + adversarial corpus (10 mutations, 100% reason-match coverage)
- `.github/workflows/v2-handshake-lint.yml` (PR-triggered) + `.github/workflows/v2-release.yml` (tag-triggered single-shot 4-check verify-v2-ship battery)
- Python-wired `lefthook` commit-msg hook with subject-line injection-defense (`\n` / `\r\n` / lone `\r` rejection)

### Deferred

- v2.1: METHODOLOGY/HOW_IT_WORKS/governance documentation refresh
- v2.2: 15 operational/security infrastructure surfaces (BL-215 + BL-220–BL-235) plus 10 deferred stacks (sveltekit, elysia, phoenix-liveview, convex, flutter, tauri, cloudflare-workers, nestjs, laravel, vite)

## [1.1.0] — 2026-04-27

Minor release. Adds an enforcement-style skill that mandates fresh verification evidence before any agent claims work is done. No breaking changes; install path unchanged.

### Added

- **`lp-verification-before-completion` skill.** Enforces evidence-before-claims for completion assertions. Maps each kind of completion claim ("tests pass", "build green", "PR ready", "Definition of Done met") to the verification command that proves it (test/typecheck/lint/build) and refuses the claim until the command's exit code and output are attached. Auto-triggers on completion-claim phrasing across commands. Closes the most common agentic failure mode where work is declared done without running the checks. The TS-stack pnpm examples in the skill prose are illustrative; for other stacks, commands resolve to `.launchpad/config.yml`'s `commands.test`/`commands.typecheck`/`commands.lint`/`commands.build` arrays via `plugin-build-runner.py`. Adapted from [obra/superpowers](https://github.com/obra/superpowers) (MIT). See `plugins/launchpad/skills/lp-verification-before-completion/SKILL.md`.

### Documentation

- `docs/skills-catalog/skills-index.md` — new entry for `lp-verification-before-completion` plus full Detailed Description; closes a pre-existing gap by adding the missing entry for `lp-step-zero`; numbering 1–17 contiguous across all sections; header count reconciled with `README.md` and the on-disk skills directory at 17
- `docs/skills-catalog/README.md` — harness-skills count and alphabetical list updated (16 → 17)
- `docs/releases/v1.1.0.md` — hand-authored release notes (required by the LaunchPad-only release-notes-check gate)

### Internal

- All 15 plugin test suites pass; frontmatter integrity check now reports 17 skills (was 16)
- Full `ci.yml` required-checks suite green (Type Check, Lint, Build, Test, Repo Structure, Install)
- Greptile + Codex dual-reviewer cycle ran clean

## [1.0.1] — 2026-04-26

Patch release: dependency hygiene and a second AI code reviewer for every PR. No production code changes — the plugin behavior at install is identical to v1.0.0.

### Security

- **23 of 26 flagged CVEs cleared** via direct dep bumps + `pnpm update --recursive && pnpm dedupe`
  - High-severity fixes: `hono` → 4.12.15 (arbitrary file access via serveStatic), `@hono/node-server` → 1.19.14 (auth bypass via encoded slashes), `next` → 15.5.15 (Server Components DoS), `picomatch` (ReDoS), `defu` (proto pollution), `effect` (concurrency context contamination), `flatted` (proto pollution)
  - Medium-severity fixes: cleared 12+ medium CVEs across `hono`, `next`, `picomatch`, `brace-expansion`, `postcss`, `vite`, and others
- **3 residual CVEs** in deeply-transitive copies (esbuild 0.21.5, postcss 8.4.31, vite 5.4.21) pinned by other dependencies; addressable via `pnpm.overrides` if upstream Dependabot keeps flagging them
- **GitHub Actions runners upgraded** to current major versions (commit-pinned): `actions/checkout` v6.0.2, `actions/setup-node` v6.4.0, `actions/cache` v5.0.5

### Added

- **Greptile as a second AI code reviewer** alongside Codex on every PR. Codex covers the narrow / line-level lane (per-PR diff context); Greptile covers the wide / codebase-aware lane (pre-indexed graph of the whole repo). Both advisory only; merge gating remains the existing required `ci.yml` jobs. Configured via `greptile.json` at repo root.
- **Template support for downstream projects** — `greptile.template.json` + `init-project.sh` swap-chain wiring so projects scaffolded from the LaunchPad template inherit the dual-reviewer pattern automatically.
- New CI workflow `.github/workflows/release-notes-check.yml` (LaunchPad-only) — enforces that every release PR and tag push includes a hand-authored `docs/releases/v<VERSION>.md` file.
- New maintainer-only doc `docs/maintainers/RELEASE_PROCESS.md` (LaunchPad-only) — explicit step-by-step release checklist.

### Changed

- `/lp-commit`, `/lp-ship`, and `/lp-build` PR-monitoring loops now include Gate B3 for Greptile alongside Gate B2 for Codex
- Gate numbering aligned across `/lp-commit` and `/lp-ship` (B1 = human review, B2 = Codex, B3 = Greptile)
- `/lp-ship` autonomous auto-fix criteria for Greptile findings now use concrete signals (P0/P1 severity + cross-file evidence)

### Documentation

- New `docs/architecture/CI_CD.md` — full dual-reviewer reference, Dependabot hygiene, merge protocol
- `docs/guides/HOW_IT_WORKS.md` — tech-stack table updated; new "Setting up Greptile" subsection
- `SECURITY.md` — new hardening recommendation describing the dual-reviewer pattern
- `docs/architecture/REPOSITORY_STRUCTURE.md` + `scripts/maintenance/check-repo-structure.sh` — root-file whitelist now allows `greptile.json` and `greptile.template.json`

Full details in [docs/releases/v1.0.1.md](docs/releases/v1.0.1.md).

## [1.0.0] — 2026-04-24

First public release. LaunchPad is now installable as a Claude Code plugin from the BuiltForm marketplace and runs end-to-end in any brownfield repository — no template clone required.

### Added

- **Plugin packaging.** Repository ships `.claude-plugin/marketplace.json` (marketplace name: `builtform`) and `plugins/launchpad/.claude-plugin/plugin.json` (plugin name: `launchpad`). Installable via `/plugin install launchpad@builtform`.
- **38 slash commands** organized as four meta-orchestrators (`/lp-kickoff`, `/lp-define`, `/lp-plan`, `/lp-build`) plus L2 commands for review, ship, commit, harden, learn, and triage workflows.
- **36 sub-agents** in 6 namespaces: `research/`, `review/`, `resolve/`, `design/`, `skills/`, and `document-review/`. Code reviewers are stack-aware — TypeScript reviewer dispatches when TS detected, Python reviewer when Python detected.
- **16 skills** covering design workflows, document review, commit discipline, brainstorming, planning, and skill authoring.
- **Stack detector** with allowlist-only manifest reading. Reads `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json` only — never touches `.env*`, `.npmrc`, `secrets.yml`. Bounded walk depth, hard-excludes vendored directories, 1 MB per-manifest size cap. Output is alphabetically sorted for deterministic re-runs.
- **Stack adapters** for `ts_monorepo`, `python_django`, `go_cli`, `generic`, plus a `polyglot` composer that merges multi-stack outputs deterministically (TS > Python > Go > generic precedence).
- **Doc generator.** Jinja2-rendered (autoescape on) templates for `PRD.md`, `TECH_STACK.md`, `BACKEND_STRUCTURE.md`, `APP_FLOW.md`, `SECTION_REGISTRY.md`, `config.yml`, and `agents.yml`. Pre-write secret scanner refuses on AWS, GitHub, Stripe, Anthropic, OpenAI, Slack, and DB-credential patterns. Realpath-confined writes.
- **Vendored pure-Python runtime.** Jinja2 + MarkupSafe + PyYAML bundled inside the plugin. Zero `pip install` at plugin-install time; runs on any Python 3.10+.
- **Config-driven L2 commands.** `/lp-commit`, `/lp-ship`, `/lp-review`, `/lp-test-browser`, `/lp-harden-plan` read shell invocations from `.launchpad/config.yml`. Same command works in TypeScript monorepos, Python backends, Go CLIs, or polyglot repos.
- **Audit log.** `.launchpad/audit.log` (gitignored by default) records every autonomous command with ISO-8601 timestamp, git user, commit SHA, content-hash of canonical commands, and invoking command name. Hash survives rebase/amend/squash. Opt in to commit via `audit.committed: true`.
- **Autonomous-execution gates.** `/lp-build` requires `.launchpad/autonomous-ack.md` to exist as a tracked file, and refuses to run if the section spec and acknowledgment file land in the same commit. The `LP_CONFIG_REVIEWED` environment variable must match the canonical commands hash (full 64-char or 16-char prefix accepted).
- **Multi-agent review with confidence scoring.** `/lp-review` dispatches code, database, design, and copy reviewers in parallel. Findings carry confidence scores (0.00–1.00); only those at or above 0.60 reach actionable todos. Multi-agent agreement adds +0.10; security-flagged findings add +0.10; P1-severity has a 0.60 floor.
- **Multi-layer merge prevention.** Commands refuse to run `gh pr merge` or `git merge main`; a `PreToolUse` hook intercepts them at the tool level; GitHub branch protection backs the rule server-side.
- **Pre-dispatch secret scan.** `/lp-review` scans every added line against `.launchpad/secret-patterns.txt` before any review agent is dispatched. Hits block review.
- **`--dry-run` preview.** `/lp-inf --dry-run` reports which section, plan file, and branch the build would use without running the loop.
- **Compound learning.** `/lp-learn` writes structured solution docs to `docs/solutions/` after each `/lp-build` cycle, indexed by category and tags for semantic retrieval by `learnings-researcher` agent on subsequent builds.

### Documentation

- [README.md](README.md) — install paths, first 15 minutes, what's inside, security summary, links
- [HOW_IT_WORKS.md](docs/guides/HOW_IT_WORKS.md) — operator's manual covering every phase
- [METHODOLOGY.md](docs/guides/METHODOLOGY.md) — six-layer architecture, design principles, agent fleet
- [SECURITY.md](SECURITY.md) — threat model, what the harness controls / does not control, recommended companion (`dcg`), reporting channel
- [ROADMAP.md](ROADMAP.md) — v1.0.x patch line, v1.1 scope, what's not in v1.1, branch model
- [CONTRIBUTING.md](CONTRIBUTING.md) — getting started, PR guidelines, architecture decisions
- [AGENTS.md](AGENTS.md) — cross-tool bridge for Codex / Cursor / Aider / Windsurf / Gemini users
- [docs/guides/MEMPALACE_INTEGRATION.md](docs/guides/MEMPALACE_INTEGRATION.md) — optional pairing with MemPalace for verbatim session-memory recall

### Known limitations

Carried forward into v1.1:

- Python framework detection treats any `pyproject.toml` as `python_django`. FastAPI / Flask projects need manual edit to `.launchpad/config.yml` until the framework-distinction adapter ships.
- Polyglot design-field precedence defaults to `skipped` for TS+Python combinations. Workaround: hand-edit `pipeline.define.design`, `pipeline.plan.design_review`, `pipeline.build.test_browser` in `.launchpad/config.yml`.
- Bare `pytest` invocation assumes no env manager. Detection of `poetry.lock` / `uv.lock` is queued.
- Runner exit code `2` overlaps `pytest`'s collection-error exit. Remap to the reserved 64–78 range is queued.
- `/lp-pnf` and `/lp-brainstorm` Phase 1 are dialogue-heavy; no `--stub` / `--yes-to-all` non-interactive mode yet.
- `/lp-shape-section --from-todo <id>` import adapter for projects with existing TODO files is queued.

Full v1.1 scope in [ROADMAP.md](ROADMAP.md).

[Unreleased]: https://github.com/builtform/launchpad/compare/v2.1.1...HEAD
[2.1.1]: https://github.com/builtform/launchpad/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/builtform/launchpad/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/builtform/launchpad/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/builtform/launchpad/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/builtform/launchpad/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/builtform/launchpad/releases/tag/v1.0.0
