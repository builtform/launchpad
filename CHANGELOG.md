# Changelog

All notable changes to LaunchPad are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Tracked in [ROADMAP.md](ROADMAP.md). Future minor releases will continue with the Codex CLI overlay generator and polyglot stack-detection refinements.

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

[Unreleased]: https://github.com/builtform/launchpad/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/builtform/launchpad/releases/tag/v1.0.0
