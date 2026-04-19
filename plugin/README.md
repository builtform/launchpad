# LaunchPad Plugin

> **This directory is a build artifact.** Do not edit files here directly. Edit the corresponding source under `.claude/` at the LaunchPad repo root and run `pnpm build:plugin`. The pre-commit hook enforces this.

A Claude Code plugin exposing LaunchPad's 36 agents, 16 skills, and 38 commands to any project — greenfield or brownfield. Commands are prefixed with `lp-` (e.g., `/lp-commit`, `/lp-review`, `/lp-ship`) to avoid collisions with project-local commands.

---

## What this plugin installs

| Component     | Count | Example                                                                  |
| ------------- | ----- | ------------------------------------------------------------------------ |
| Agents        | 36    | `lp-security-auditor`, `lp-pattern-finder`, `lp-kieran-foad-ts-reviewer` |
| Skills        | 16    | `/lp-commit`, `/lp-frontend-design`, `/lp-instructions` (new)            |
| Commands      | 38    | `/lp-commit`, `/lp-review`, `/lp-ship`, `/lp-version` (new)              |
| Hooks         | 3     | SessionStart, PreToolUse(Bash), PostToolUse(Skill)                       |
| Shell scripts | 11    | Runtime helpers under `plugin/bin/`                                      |

---

## Install (v0.1 — local `--plugin-dir`)

**Prerequisite:** `jq` must be on your PATH. `brew install jq` on macOS.

```bash
# In any project where you want LaunchPad available:
cd /your/brownfield/project
claude --plugin-dir /path/to/LaunchPad/plugin
```

That's it. No init step. No scaffolding. Priority A commands self-heal missing state (`.harness/`, `.launchpad/agents.yml`) on first use.

### Alternative: project-level setting

Add to your project's `.claude/settings.local.json` so you don't need the `--plugin-dir` flag every session:

```json
{ "plugins": { "dir": "/path/to/LaunchPad/plugin" } }
```

### Updates

`--plugin-dir` installs do not auto-update. To pull latest:

```bash
cd /path/to/LaunchPad
git pull
# Restart your Claude session in the consuming project.
```

v0.2 will submit to the Anthropic marketplace (`claude plugin install launchpad`), which enables `claude plugin update`.

---

## What runs on session start (SessionStart hook)

`plugin/bin/hydrate.sh` fires on every session start and `/clear`. It:

1. Emits a compact "LaunchPad active" card with core conventions
2. Prints `docs/tasks/BACKLOG.md` (first 200 lines) if present; silent if absent
3. Does NOT run structure-drift detection (template-only concern; excluded from plugin)

---

## What runs on every Bash call (PreToolUse hook)

`plugin/bin/block-merges.sh` fires before every `Bash` tool invocation. It exits 2 (blocks) if the command matches any of:

- `gh pr merge`
- `git merge main` / `git merge master` (not `origin/main`)
- `git push --force` / `git push -f`
- `git push origin main` / `origin master`
- `gh pr review --approve`

Otherwise exits 0 (allows). Performance: ~15 ms per call on macOS (hardened from the earlier 30–80 ms version).

Empty stdin is allowed (relaxed from earlier fail-closed behavior). `jq` is a hard dependency — without it, the hook exits 2 with an install hint.

## What runs after every Skill call (PostToolUse hook)

`plugin/bin/track-skill-usage.sh` fires after every `Skill` tool invocation. It records the last-used date for the invoked skill in `docs/skills-catalog/skills-usage.json`. ~30 ms per call (jq-based; was ~60–150 ms with python3).

---

## Per-project hook opt-out

If any hook conflicts with your project's existing conventions, add to your project's `.claude/settings.local.json`:

```json
{ "disabledPluginHooks": { "launchpad": ["PreToolUse"] } }
```

(Exact schema TBD with Anthropic's plugin-hook opt-out contract. If the above key is not honored, the fallback is to remove the specific hook entry from `plugin/hooks/hooks.json` in your local clone — note that `git pull` will restore it.)

---

## v0.1 command scope

### Brownfield-safe (7 Priority A commands — self-heal missing state)

These work out-of-the-box in a brand-new `git init` repo with no prior setup:

- `/lp-commit` — stage, quality gates, commit, optional PR
- `/lp-review` — multi-agent code review with confidence scoring
- `/lp-ship` — quality gates + PR + CI monitoring (never merges)
- `/lp-triage` — interactive triage of review findings
- `/lp-resolve-todo-parallel` — parallel resolver agents
- `/lp-defer` — add a task to the backlog
- `/lp-hydrate` — print the project backlog

Plus:

- `/lp-instructions` — skill that carries core conventions (root cause, no secrets, Definition of Done, git prefixes)
- `/lp-version` — print plugin version + surface counts

### v0.2 scope (ship unmodified in v0.1 — may fail on missing state)

The remaining 29 commands (`/lp-pnf`, `/lp-harden-plan`, `/lp-define-product`, `/lp-shape-section`, `/lp-harness-build`, `/lp-harness-plan`, `/lp-learn`, etc.) are present in the plugin but have not yet been hardened for brownfield. They may fail with their current error messages if the required state (`docs/architecture/PRD.md`, section specs, etc.) is missing. Degradation for these commands lands in v0.2.

---

## Differentiation vs alternatives

vs Compound Engineering (`/ce-*` plugin):

- LaunchPad's opinionated 4-phase methodology (`harness:kickoff` → `harness:define` → `harness:plan` → `harness:build`) with an explicit design-before-planning discipline and a status contract (shaped → designed → planned → hardened → approved → reviewed)
- Compound-learning loop tied to `docs/solutions/` — captured lessons reshape future reviews
- Section-based planning model (registry in `docs/architecture/PRD.md`, one spec per section)
- Runtime state model (`.harness/`) with todos, observations, review history
- Merge-prevention hook enforcing "no direct to main"

vs homegrown agent setups:

- 36 agents across research / review / document-review / resolve / design / skills namespaces, curated rather than accumulated
- Integrated quality gates (typecheck, test, lint) wired into `/lp-commit` and `/lp-ship`
- Same agents run in LaunchPad itself — well-exercised on real projects

---

## Reporting issues

LaunchPad is at `https://github.com/foadshafighi/LaunchPad`. For v0.1 specifically, file issues against the `feat/plugin-extraction` branch until the plugin stabilizes.
