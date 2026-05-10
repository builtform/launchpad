# CI/CD Guide

Continuous integration and deployment for "{{PROJECT_NAME}}".

## CI workflows

Three workflows under `.github/workflows/`:

| File               | Purpose                                                                                 | Triggers                         |
| ------------------ | --------------------------------------------------------------------------------------- | -------------------------------- |
| `ci.yml`           | Required-to-merge quality gates: Type Check, Lint, Build, Test, Repo Structure, Install | Pull requests + pushes to `main` |
| `codex-review.yml` | Advisory AI code review (line-level / narrow) via OpenAI Codex                          | Pull requests                    |
| `deploy.yml`       | Deployment workflow (configure for your hosting target)                                 | Configurable                     |

### Required status checks

The branch ruleset on `main` requires these `ci.yml` jobs to pass before any PR can merge:

- `Type Check`
- `Lint`
- `Build`
- `Test`
- `Repo Structure`
- `Install`

The branch ruleset also blocks force pushes and direct deletions of `main`.

## AI code review — two complementary lanes

This repo uses **two AI reviewers in parallel**, each focused on a different lane. Both are **advisory only** (not required for merge), so quota outages or false positives never block legitimate work.

### Lane 1 — Codex (narrow, line-level)

Configured via `.github/workflows/codex-review.yml`. Runs as a GitHub Action invoked on each PR. Sees the diff plus what it can read in its sandbox. Output: a single PR comment summarizing line-level findings.

The Codex job is set with `continue-on-error: true` — quota exhaustion on OpenAI's side surfaces as a CI red mark on the Codex check but does NOT fail the overall PR. Merge can proceed.

### Lane 2 — Greptile (wide, codebase-aware)

Configured via `greptile.json` at repo root. Runs as a GitHub App that pre-indexes the entire repo as a graph (functions, classes, deps) and reviews each PR with whole-codebase context. Output: PR summary comment + inline review comments + (optional) a status check.

Greptile lives outside your GitHub Actions billing — its failures or outages don't touch your CI at all.

#### Configuration (`greptile.json`)

| Field              | Value                                                                                                      | Why                                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `commentTypes`     | `["logic", "syntax", "style"]`                                                                             | Calibration period; narrow to `["logic"]` after observation if syntax/style overlaps with Codex/ESLint |
| `strictness`       | `1`                                                                                                        | Lowest setting; raise only if signal-to-noise is high                                                  |
| `triggerOnUpdates` | `true`                                                                                                     | Re-review on each commit added to a PR                                                                 |
| `triggerOnDrafts`  | `false`                                                                                                    | Skip draft PRs                                                                                         |
| `statusCheck`      | `false`                                                                                                    | Advisory-only initially; can promote to status check after observation                                 |
| `excludeAuthors`   | `["dependabot[bot]"]`                                                                                      | Skip mechanical dep-bump PRs                                                                           |
| `ignorePatterns`   | `node_modules`, `dist`, `.next`, `.turbo`, lockfile, generated `.d.ts`, Prisma migrations, vendored Python | Reduce noise on generated/external code                                                                |

#### Interpreting Greptile findings

Greptile is documented to have **higher recall but higher false-positive rate** than other AI reviewers. Treat its findings as a checklist, not a verdict:

- **Cross-file logical bugs** → high signal, fix
- **Architectural / convention violations** → high signal, fix or push back with reasoning
- **Style / nitpicks** → mostly noise, skim only
- **Syntax suggestions** → cross-check against ESLint output; if both agree, fix; if only Greptile flags, usually noise

### Why two reviewers?

| Concern                                    | Codex catches | Greptile catches |
| ------------------------------------------ | ------------- | ---------------- |
| Typo / off-by-one in the diff              | ✅            | ⚠️               |
| Cross-file refactor leaving callers broken | ❌            | ✅               |
| Convention inconsistency across many files | ❌            | ✅               |
| Architectural drift over time              | ❌            | ✅               |
| Local logic bug in a single function       | ✅            | ✅               |

The lanes overlap on local logic; they don't on cross-file or convention concerns. Running both gives the broadest coverage at zero direct cost (OSS program covers Greptile; Codex Action quota is per-user).

## v2.1.1 local gate inventory

LaunchPad self-host runs the following gates LOCALLY before any push, via `lefthook` + `plugin-build-runner.py` + the new mandatory `/lp-review` dual-pass.

### Pre-commit gates (`lefthook.yml` `pre-commit:` block)

| Gate                      | Priority | Glob                                                     | Exclude                                   | Source                                                                                         | Purpose                                                                             |
| ------------------------- | -------- | -------------------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `prettier-fix`            | 1        | `*.{js,jsx,ts,tsx,json,css,md,yml,yaml,html}`            | —                                         | `pnpm prettier --write {staged_files}`                                                         | Auto-format on staged files                                                         |
| `eslint-fix`              | 2        | `*.{js,jsx,ts,tsx,mjs,cjs}`                              | `next-env\.d\.ts$`                        | `pnpm eslint --fix {staged_files}`                                                             | Auto-fix lint issues on staged files                                                |
| `lint`                    | 10       | `**/*.{js,jsx,ts,tsx,mjs,cjs,py}`                        | —                                         | `python3 plugins/launchpad/scripts/plugin-build-runner.py --stage=lint`                        | Routes through `.launchpad/config.yml` `commands.lint` (per-stack truth)            |
| `typecheck`               | 10       | `**/*.{ts,tsx,py}`                                       | —                                         | `python3 plugins/launchpad/scripts/plugin-build-runner.py --stage=typecheck`                   | Routes through `commands.typecheck`                                                 |
| `test`                    | 10       | `**/*.{ts,tsx,js,jsx,mjs,cjs,py}`                        | —                                         | `python3 plugins/launchpad/scripts/plugin-build-runner.py --stage=test`                        | Routes through `commands.test`                                                      |
| `bandit`                  | 10       | `**/*.py`                                                | `plugins/launchpad/scripts/tests/.*\.py$` | `bandit -ll {staged_files}`                                                                    | Python security scanner (medium-or-higher severity; LOW skipped) — Phase 4          |
| `semgrep-general`         | 10       | `**/*.py`                                                | `plugins/launchpad/scripts/tests/.*\.py$` | `semgrep --config=plugins/launchpad/.semgrep/general.yml {staged_files} --error --metrics=off` | Universal semgrep rules — Phase 4                                                   |
| `structure-check`         | 10       | —                                                        | —                                         | `bash scripts/maintenance/check-repo-structure.sh`                                             | Repo structure invariants                                                           |
| `workflow-action-sha-pin` | 10       | —                                                        | —                                         | `python3 plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py`                           | Enforces SHA pins on GitHub Actions workflows                                       |
| `large-file-guard`        | 10       | `*.{js,jsx,ts,tsx,json,css,md,yml,yaml,html,sh,mjs,cjs}` | —                                         | inline shell                                                                                   | Prevents accidentally-committed large text files (>500KB)                           |
| `trailing-whitespace`     | 10       | `*.{js,jsx,ts,tsx,json,css,md,yml,yaml,html,sh}`         | —                                         | inline shell                                                                                   | Rejects trailing whitespace on staged files                                         |
| `end-of-file-newline`     | 10       | `*.{js,jsx,ts,tsx,json,css,md,yml,yaml,html,sh}`         | —                                         | inline shell                                                                                   | Requires final newline on staged files                                              |
| `ruff-check`              | 11       | `**/*.py`                                                | `plugins/launchpad/scripts/tests/.*\.py$` | `ruff check --config plugins/launchpad/scripts/pyproject.toml {staged_files}`                  | Python lint — serialized post-priority-10 (shares `.ruff_cache/` with format-check) |
| `ruff-format-check`       | 12       | `**/*.py`                                                | `plugins/launchpad/scripts/tests/.*\.py$` | `ruff format --check --config plugins/launchpad/scripts/pyproject.toml {staged_files}`         | Python format check — serialized post-ruff-check                                    |

`plugin-build-runner.py` reads `.launchpad/config.yml` `commands.{lint,typecheck,test}` arrays. Empty arrays skip silently. Non-zero exit fails the stage with a clear error.

### Pre-push gates (`lefthook.yml` `pre-push:` block)

| Gate                         | Priority | Glob      | Source                                                                                                                | Purpose                                                                                                                                                                                                                                |
| ---------------------------- | -------- | --------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backlog-orphan-check`       | (none)   | (none)    | inline shell wrapper around `python3 plugins/launchpad/scripts/plugin-backlog-orphan-check.py --release "$version"`   | Slip-prevention — every BL labeled for current `plugin.json` version must have a status line OR CHANGELOG cross-reference; skips silently when CHANGELOG has no `## [<version>]` block (pre-tag); version extracted from `plugin.json` |
| `pytest`                     | 10       | `**/*.py` | `cd plugins/launchpad/scripts && python -m pytest -x -q`                                                              | Direct pytest invocation (Phase 3 R1-T1-8); short-circuits to exit 0 if `plugins/launchpad/scripts/` absent (downstream consumers)                                                                                                     |
| `pyright`                    | 10       | `**/*.py` | `cd plugins/launchpad/scripts && pyright`                                                                             | Python type check (Phase 4 R1-T1-1: pre-push placement avoids inner-loop friction); strict on 3 security-boundary modules per Phase 4 Hybrid disposition                                                                               |
| `semgrep-launchpad-internal` | 10       | `**/*.py` | `semgrep --config=plugins/launchpad/.semgrep/launchpad-internal.yml plugins/launchpad/scripts/ --error --metrics=off` | Cross-cutting invariants (Phase 4); deeper scan than pre-commit `semgrep-general`                                                                                                                                                      |

### Commit-msg gate (`lefthook.yml` `commit-msg:` block)

| Gate              | Source                                                                 | Purpose                                                                                                           |
| ----------------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `restamp-history` | `python3 plugins/launchpad/scripts/plugin-restamp-history-hook.py {1}` | Subject-line injection defense + restamp-history.jsonl audit append (OPERATIONS §0 strip-back-aware Layer 9 P3-2) |

### Mandatory dual-pass review (`/lp-commit` Step 2.5 + `/lp-ship` Step 4.6)

Both commands run `/lp-review --headless` (specialist with full context) AND `/lp-review --headless --no-context` (blind without context) as TWO SEPARATE Bash invocations. Both passes write to `.harness/todos/`; user triages once via `/lp-triage`. Bypass on hotfix branches via `--skip-review` with TTY-guarded `BYPASS REVIEW` confirmation + audit-trail trailer (Phase 2).

### Manually-invoked validators (NOT lefthook-wired)

| Tool                          | Source            | When                                                                            |
| ----------------------------- | ----------------- | ------------------------------------------------------------------------------- |
| `plugin-v2-handshake-lint.py` | direct invocation | manual / CI-only via `.github/workflows/v2-handshake-lint.yml`; not in lefthook |

See [docs/guides/CODE_REVIEW_LAYERS.md](../guides/CODE_REVIEW_LAYERS.md) for the three-layer architecture rationale.

## Dependency hygiene

Dependabot is configured via `.github/dependabot.yml`:

- npm ecosystem: weekly schedule, max 5 open PRs
- github-actions ecosystem: weekly schedule, max 3 open PRs

Security updates and grouped security PRs are enabled at the repo level (Settings → Security → Dependabot).

For transitive CVE coverage that Dependabot doesn't cover directly:

```bash
pnpm update --recursive
pnpm dedupe
```

Run periodically or when GitHub flags vulnerabilities the open Dependabot PRs don't address.

## Merge protocol

1. Open PR from `feat/*` or `fix/*` or `chore/*` branch to `main`
2. Wait for `ci.yml` required checks to go green
3. Read both Codex and Greptile review comments — address signal, ignore noise
4. Squash-merge (the only enabled merge style)
5. Branch auto-deletes on merge

Tag releases with `vX.Y.Z`, push tag, then `gh release create vX.Y.Z -F docs/releases/vX.Y.Z.md` with hand-authored notes.
