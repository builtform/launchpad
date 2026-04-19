# LaunchPad Plugin Changelog

## v0.1.0 — 2026-04-19

Initial release. Extracts LaunchPad methodology into a Claude Code plugin for brownfield (and any non-LaunchPad) projects.

### Added

- **36 agents** under `plugin/agents/lp-*.md` (research, review, document-review, resolve, design, skills namespaces)
- **16 skills** under `plugin/skills/lp-*/` including:
  - `lp-instructions` (new) — portable subset of CLAUDE.md with core principles, Definition of Done, git conventions
  - 15 skills ported from LaunchPad source
- **38 commands** under `plugin/commands/lp-*.md` including:
  - `lp-version` (new) — trivial introspection; prints plugin version + surface counts
  - 37 commands from LaunchPad source (pull-launchpad dropped — template-only)
- **3 hooks** (`plugin/hooks/hooks.json`):
  - SessionStart → `hydrate.sh` (simplified; no drift detection in plugin mode)
  - PreToolUse(Bash) → `block-merges.sh` (hardened; <15 ms/call)
  - PostToolUse(Skill) → `track-skill-usage.sh` (jq-based; <30 ms/call)
- **Build pipeline** (`scripts/build-plugin.sh` + companion Python/shell scripts): deterministic, atomic, signed with SHA256SUMS
- **Pre-commit hook** auto-rebuilds `plugin/` on source change; rejects direct `plugin/` edits

### Graceful degradation (Priority A commands)

7 commands self-heal missing state for brownfield use:

- `/lp-commit` — Pattern A (mkdir .harness/todos) + Pattern B (seed agents.yml)
- `/lp-review` — Pattern A + B + C (optional harness.local.md)
- `/lp-ship` — Pattern B + optional review-summary.md
- `/lp-triage` — Pattern A + D (halt if no findings)
- `/lp-resolve-todo-parallel` — Pattern A + D
- `/lp-defer` — Pattern A (mkdir observations)
- `/lp-hydrate` — already Pattern C (skip missing backlog)

### Known limitations

- 29 remaining commands ship unmodified; may fail on missing state. Degradation lands in v0.2.
- `create-agent` / `create-skill` / `update-skill` / `port-skill` don't yet have a target-resolution contract.
- `--plugin-dir` installs don't auto-update; `git pull` required. Marketplace submission in v0.2.
- Ambient-convention enforcement is weaker than CLAUDE.md injection (which we deliberately don't do). `lp-instructions` skill + SessionStart card is the primary mechanism.

### Security

- See `plugin/SECURITY.md` for hook blast radius, dependencies, secret-scan posture, and integrity verification.

### Verified

- Deterministic build (same source input → byte-identical plugin output)
- Path-with-spaces install tested from `/Users/foadshafighi/dev/My Projects/LaunchPad/plugin`
- Self-locating shim handles absent `$CLAUDE_PLUGIN_ROOT`
- Brownfield simulation (empty `git init` repo): Priority A flows self-heal correctly
