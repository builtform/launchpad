---
name: lp-step-zero
description: Shared Step 0 prerequisite-and-capability-check pattern for LaunchPad harness and L2 commands. Called by slash-commands BEFORE their main logic runs. Provides two modes — Full (harness-level, detect/classify/present/scaffold) and Lite (L2, create-if-missing for required state files). Enforces the "Lite ⊆ Full" contract mechanically via a single shared helper.
---

# lp-step-zero

Shared prerequisite-and-capability check used by every LaunchPad harness
command and L2 command that depends on canonical state. Prevents drift
between command-specific Step 0 implementations by routing everything
through a single shell helper (`${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh`).

---

## When to use

- **Harness commands** (`/lp-kickoff`, `/lp-define`, `/lp-plan`, `/lp-build`):
  call in **full mode** before running command logic.
- **L2 commands** (`/lp-commit`, `/lp-review`, `/lp-ship`, `/lp-harden-plan`,
  etc.): call in **lite mode** with an explicit `--require` list.
- **Never inline** the Step 0 logic in a command's prose. The whole point of
  this skill is to keep the check in one place.

## Full mode (harness)

Runs the detect → classify → present → scaffold protocol. Harness commands
invoke it like this near the top of their prose:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=full --command=lp-kickoff
```

If the check returns non-zero, the harness command presents the interactive
menu from the core-pattern section of the v1 plan (`[a] scaffold / [b] run
prior / [c] override paths / [d] exit`).

## Lite mode (L2)

Only checks that explicit required files exist. No detection, no interactive
menu, no scaffolding. If a required file is missing, the caller sees a
clear "run `/lp-define` to seed" message and exit code 1.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh \
  --mode=lite \
  --command=lp-commit \
  --require=.launchpad/config.yml,.launchpad/agents.yml
```

## Contract: Lite is strictly a subset of Full

If Lite grows its own detection logic, it becomes a parallel implementation —
exactly the failure mode this skill was designed to prevent. L2 commands MUST
NOT implement their own prereq logic; anything richer than create-if-missing
lives in Full mode and is called from a harness command.

## Performance

Acceptance budget: p95 < 200ms on a warm cache, < 500ms cold. Session
cache (keyed on mtime of `config.yml` + top-level manifests) lives at
`$LP_CACHE_DIR` (default `/tmp/lp-prereq-cache-$USER/`).

## Prior art

This skill generalizes the Step 0 self-heal pattern already in production
across seven L2 commands on main: `lp-commit.md`, `lp-review.md`,
`lp-ship.md`, `lp-resolve-todo-parallel.md`, `lp-triage.md`,
`lp-test-browser.md`, `lp-pnf.md`. Migrated commands call this shared
helper instead of duplicating inline checks.

## Exit codes

| Code | Meaning                                                           |
| ---- | ----------------------------------------------------------------- |
| 0    | Prerequisites satisfied; command may proceed                      |
| 1    | Missing prerequisite; caller must handle (prompt or abort)        |
| 2    | Fatal error (bad invocation, corrupt config) — command must abort |
