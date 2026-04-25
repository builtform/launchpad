# Contributing to LaunchPad

Thanks for your interest in contributing. This document covers how to get a working development environment, how to send a useful pull request, and the architectural conventions that keep the project coherent over time.

> Not to be confused with [`CONTRIBUTING.template.md`](CONTRIBUTING.template.md), which is the template that LaunchPad's project scaffolder writes into newly initialized downstream projects. This file is for contributing to LaunchPad itself.

## Getting started

```bash
git clone https://github.com/builtform/launchpad
cd launchpad
pnpm install
```

`pnpm install` also installs Lefthook git hooks. The first commit you make in the repo will trigger them.

If you want the plugin loaded into your local Claude Code while you work on it, use the local-path install:

```
/plugin marketplace add /absolute/path/to/your/launchpad-clone
/plugin install launchpad@builtform
```

Restart Claude Code. Your `/lp-*` commands now run from your working tree — re-install or restart Claude Code after edits to pick them up.

## Running tests

```bash
pnpm test         # vitest across all workspaces
pnpm typecheck    # TypeScript type check (no emit)
pnpm lint         # ESLint
```

The plugin's Python test suites live under `plugins/launchpad/scripts/tests/`. Run them with:

```bash
cd plugins/launchpad/scripts
python3 -m pytest
```

All test suites must stay green before a PR is mergeable. CI runs them automatically.

## Project structure

```
launchpad/
├── .claude-plugin/         # marketplace.json (catalog entry for the BuiltForm marketplace)
├── plugins/launchpad/      # the plugin itself
│   ├── .claude-plugin/     # plugin.json (manifest)
│   ├── commands/           # /lp-* slash commands (markdown + YAML frontmatter)
│   ├── agents/             # 36 sub-agents in 6 namespaces
│   ├── skills/             # 16 reusable skills
│   └── scripts/            # runtime: stack detector, doc generator, audit log, etc.
├── apps/                   # template-path: Next.js + Hono monorepo (greenfield scaffold)
├── packages/               # template-path: shared workspace packages
├── docs/                   # architecture docs, guides, releases
├── scripts/setup/          # init-project.sh — the template-path scaffold wizard
└── .github/                # CI, issue templates, dependabot, CODEOWNERS
```

Two products ship from this repo:

- The **plugin** (`/plugin install launchpad@builtform`) — works in any brownfield repo
- The **template** (`git clone … && ./scripts/setup/init-project.sh`) — bootstraps a fresh monorepo with the plugin pre-installed

Most contributions touch only `plugins/launchpad/`. Template changes (under `apps/`, `packages/`, `scripts/setup/`) are reviewed for whether they degrade the plugin path.

## Pull request guidelines

1. **Branch from `main`.** Use a conventional-commit prefix in the branch name: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `docs/<topic>`, `refactor/<topic>`, `test/<topic>`, `perf/<topic>`, `style/<topic>`, `ci/<topic>`.
2. **Write a focused PR.** One concern per PR. If you discover unrelated improvements while working, file them as separate issues or PRs.
3. **Use the PR template.** The default template asks for Summary / Changes / Test plan / Callouts for reviewers. The Test plan section uses checkboxes — checked items are commands you ran; unchecked items are what the reviewer should verify.
4. **Run quality gates locally before pushing.** `pnpm test`, `pnpm typecheck`, `pnpm lint`. Pre-commit hooks block commits with style violations; do not bypass with `--no-verify`.
5. **Link to issues.** Use `Closes #N` syntax in the PR body so the issue closes automatically on merge.
6. **Direct merges to `main` are blocked.** All changes — including the maintainer's — go through PR review and CI.

### Commit messages

LaunchPad follows a conventional-commit pattern:

```
type(scope): short imperative description

Optional longer body explaining root cause, file paths, test results,
or anything that would be useful to a future reader of git log.
```

- **Types**: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`, `security`, `release`
- **Scope** (optional): the affected area — `commands`, `agents`, `skills`, `scripts`, `plugin`, `init`, `docs`, etc.
- **Subject**: imperative mood, lowercase after the colon, no trailing period, ~60 characters
- **Body** (optional but encouraged for non-trivial changes): file:line references, bullet-pointed change manifests, test-result counts, issue numbers inline (`fixes #123`)
- **AI attribution**: do NOT add `Co-Authored-By: Claude` or any AI co-authorship trailer. The plugin's commit format intentionally omits it. Human authorship attribution stays standard (`git commit --author=...` if needed).

The `/lp-commit` slash command (when contributing from inside Claude Code) generates messages following this pattern automatically.

## Code style

- **TypeScript**: ESLint + Prettier handle style. Do not manually fix style; run `pnpm format`.
- **Python (plugin scripts)**: ruff for linting and formatting. Vendored runtime in `plugins/launchpad/scripts/_vendor/` is not linted (ruff `# noqa` at file level).
- **Markdown**: prettier formats markdown too. Tables get aligned automatically.

## Good first issues

Issues labeled `good first issue` are scoped for new contributors — usually small, well-described, and isolated from the rest of the codebase. If you'd like an issue labeled, ask in the corresponding GitHub issue and the maintainer can add the label after a quick scope review.

## Architecture decisions

These conventions exist for a reason. Read [METHODOLOGY.md](docs/guides/METHODOLOGY.md) for the long-form rationale; the short form is here.

### Status contract

Every feature section moves through an explicit status sequence:

```
defined → shaped → designed → planned → hardened → approved → reviewed → built
```

Each meta-orchestrator (`/lp-define`, `/lp-plan`, `/lp-build`) checks the section's current status before proceeding and updates it on completion. This is what lets you resume work in the middle of a feature without re-running upstream phases.

PRs that touch the status logic must keep this sequence intact and document any addition.

### Fresh-context loops

`/lp-build` runs in fresh-context iterations. Each loop step starts a new sub-agent with a clean context window, reading only the section spec, the plan, and the current diff. State that needs to persist across iterations writes to `.harness/`, not to chat history. PRs that introduce hidden context dependencies between iterations will be asked to refactor.

### Confidence scoring

Multi-agent review findings are scored 0.00 to 1.00 with a 0.60 threshold. Findings below threshold are suppressed with an audit trail. Boosters: multi-agent agreement (+0.10), security flag (+0.10), P1-severity floor (0.60). PRs that change scoring need a justification and a test that exercises the new behavior.

### Multi-layer merge prevention

Three layers prevent unsafe merges, and the project assumes all three are active:

1. Commands refuse to run `gh pr merge` and `git merge main`
2. A `PreToolUse` hook intercepts those commands at the tool level (file: `.claude/hooks/block-merges.sh`)
3. GitHub branch protection backs the rule server-side

PRs that weaken any of these layers — including bypassing the hook — will be rejected. The `--no-verify` flag is never acceptable; if a hook is broken, fix the hook.

### Plugin-first, template-second

When the plugin path and the template path diverge, the plugin path wins. The template is a convenience for greenfield monorepos; the plugin must work in every brownfield. PRs that improve template ergonomics at the cost of plugin compatibility are not merged.

## Reporting security issues

Do not file security issues publicly. See [SECURITY.md](SECURITY.md) for the GitHub Private Vulnerability Reporting flow.

## Community

- **Issues** — bug reports, feature requests, and install-flow problems. Use the dedicated `plugin install issue` template for installation failures; it asks for the right diagnostic fields up front.
- **Discussions** — open-ended questions, "is this how I should…" shape questions, and showing off what you've built with LaunchPad. Use Discussions instead of Issues for non-actionable conversation.

## License

By contributing, you agree that your contributions are licensed under the MIT License. See [LICENSE](LICENSE).
