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
