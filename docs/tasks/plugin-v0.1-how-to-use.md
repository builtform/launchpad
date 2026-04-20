# LaunchPad Plugin v0.1.0 — How To Use

> **Temporary reference.** This doc captures everything a user needs to run the LaunchPad plugin at v0.1.0. When v0.2 ships and LaunchPad goes open-source, the content here gets folded into the triple (`README.md`, `docs/guides/HOW_IT_WORKS.md`, `docs/architecture/METHODOLOGY.md`) and this file gets deleted. Until then, consult this doc during v0.1 use.

---

## Install

### Dependency

```bash
brew install jq
```

Required. The merge-prevention hook hard-fails without `jq` on `PATH`.

### Launch Claude Code with the plugin loaded

```bash
claude --plugin-dir "/Users/foadshafighi/dev/My Projects/LaunchPad/plugin"
```

- No init command to run.
- No files are written into your project until you invoke a command that needs state.

---

## Commands

Commands are grouped by readiness. The v0.1 goal was to make 7 core commands brownfield-safe (they self-heal any missing state). The remaining 29 ship unmodified and will get the same treatment in v0.2.

### Brownfield-safe commands (7, self-heal missing state)

| Command                     | What it does                                                                                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `/lp-commit`                | Full commit pipeline: branch guard, tests/typecheck/lint/hooks, conventional commit message, optional PR creation with CI monitoring loop. |
| `/lp-review`                | Dispatches review agents (configurable via `.launchpad/agents.yml`). Findings written to `.harness/todos/`.                                |
| `/lp-ship`                  | Autonomous commit + push + PR. No user approval loop — meant for post-review state.                                                        |
| `/lp-triage`                | Sorts `.harness/todos/` findings into fix / drop / defer.                                                                                  |
| `/lp-resolve-todo-parallel` | Spawns up to 5 parallel resolver agents to fix triaged findings.                                                                           |
| `/lp-defer`                 | Manually add a backlog entry without running review.                                                                                       |
| `/lp-hydrate`               | Session startup context. Loads backlog summary.                                                                                            |

### v0.2-scope commands (29, ship unmodified)

These may require prior state; behavior depends on whether the needed state exists.

**`/lp-harden-plan`** — in practice, works fine. The one blocking state it needs is `.launchpad/agents.yml` (it reads the agent lists from there). That file gets seeded automatically by any Priority A command — so if you've ever run `/lp-commit`, `/lp-review`, `/lp-ship`, `/lp-triage`, `/lp-resolve-todo-parallel`, or `/lp-defer` in this project, `/lp-harden-plan` just works. Other state it reads (`.harness/harness.local.md`, `docs/solutions/`, Context7) is all optional with graceful skip behavior. The only real failure mode is a cold-start brownfield repo where `/lp-harden-plan` is the first-ever plugin command — in that case, run `/lp-commit` once first (even on a trivial change) to seed the config, then re-invoke.

The rest:

- `/lp-inf`
- `/lp-learn`
- `/lp-harness-build`
- `/lp-harness-plan`
- `/lp-harness-define`
- `/lp-harness-kickoff`
- `/lp-pnf`
- `/lp-shape-section`
- `/lp-update-spec`
- `/lp-test-browser`
- `/lp-resolve-pr-comments`
- `/lp-regenerate-backlog`
- `/lp-copy`
- `/lp-copy-review`
- `/lp-feature-video`
- All `/lp-create-*` variants

These are more likely to depend on `.harness/` state or specific project setup. Invoke when ready — native error messages tell you what's missing.

### Utility

| Command       | What it does                                                                      |
| ------------- | --------------------------------------------------------------------------------- |
| `/lp-version` | Prints installed plugin version + surface counts. Safe anywhere, no state needed. |

---

## What gets created in your project

Only when a command that needs state is invoked:

- `.harness/` — runtime state (`todos/`, `observations/`, `review-summary.md`, `design-artifacts/`).
- `.launchpad/agents.yml` — review agent config (seeded from plugin default on first invocation).
- `.launchpad/secret-patterns.txt` — secret-scan patterns (seeded similarly).

The plugin does **NOT** touch:

- `CLAUDE.md`
- `package.json`
- Git hooks
- Anything else

---

## For open-source projects

Add to `.gitignore`:

```
.harness/
.launchpad/
```

The plugin itself leaves no trace when you stop loading it. "Uninstall" =

1. Drop the `--plugin-dir` flag.
2. Optionally `rm -rf .harness .launchpad` in the project.

---

## Updating

```bash
cd "/Users/foadshafighi/dev/My Projects/LaunchPad"
git pull
# restart Claude Code
```

Marketplace-based `claude plugin update` ships in v0.2.

---

## Autonomous execution gotcha

The compound pipeline commands (`/lp-harness-build`, `/lp-inf`, `/lp-learn`) run AI with approval/sandbox flags bypassed. The meta-orchestrator commands set `LP_COMPOUND_AUTONOMOUS=1` automatically — no action needed from you.

This only matters if you shell out to `scripts/compound/build.sh` directly. In that case, set the env var yourself:

```bash
LP_COMPOUND_AUTONOMOUS=1 scripts/compound/build.sh
```

---

## Smoke test

After install, run:

```
/lp-version
```

Expected output:

```
LaunchPad v0.1.0
36 agents / 16 skills / 38 commands
```

---

## TODO for v0.2 announce

Before this repo goes public and v0.2 is submitted to the marketplace, fold this doc's content into:

- `README.md` — install section.
- `docs/guides/HOW_IT_WORKS.md` — commands reference.
- `docs/architecture/METHODOLOGY.md` — why the plugin exists as a second form.

Then delete this file.
