---
name: lp-resolve-todo-parallel
description: Resolves review findings in .harness/todos/ by spawning parallel harness-todo-resolver agents (max 5 concurrent).
---

---

## Step 0: Prerequisite Check (Lite)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=lite --command=lp-resolve-todo-parallel --require=.launchpad/agents.yml`.

Verify-or-refuse only — the lite helper checks the required files exist and exits 1 with a pointer to `/lp-define` if not; it does NOT create missing files or run the full detect/classify/present/scaffold protocol (that's harness-level). Honors `config.yml` `paths.harness_dir` when scanning `.harness/todos/`.

## Step 0.5: Autonomous-mode acknowledgment (BL-356)

`/lp-resolve-todo-parallel` spawns parallel resolver agents that write fix implementations across multiple todos autonomously. Even when invoked directly (without going through `/lp-build`), the same authorization signal applies — `.launchpad/autonomous-ack.md` MUST exist.

Call `assert_autonomous_ack(repo_root)` from `${CLAUDE_PLUGIN_ROOT}/scripts/plugin_stack_adapters/autonomous_guard.py`. If it raises `AutonomousAckMissingError`, surface `str(exc)` verbatim to the user and exit. The canonical refuse-message (composed from `AUTONOMOUS_ACK_DESCRIPTION` + `AUTONOMOUS_ACK_TEMPLATE`) embeds a short description of what `.launchpad/autonomous-ack.md` is plus the copy-pasteable starter template beginning with `# Autonomous Execution Acknowledgment` so the user can author the file without leaving the terminal.

BL-356 invariant: gate logic lives in exactly one module. Do NOT re-author the refuse-text in this command file, and do NOT inline a markdown-only absence check — the shared helper is the single source of truth.

---

# /lp-resolve-todo-parallel

Resolves pending review findings from `.harness/todos/` using parallel resolver agents.

---

## Step 1: Read Pending Todos

- Scan `.harness/todos/` for `.md` files
- Parse YAML frontmatter: filter for `status: pending` OR `status: ready`
- IF none found: report "0 findings to resolve" → exit

## Step 2: Group by File Overlap

- Use frontmatter `file:` for the primary file reference when present (added in v2.1.1 Slice H.4; authoritative — overrides body refs). For pre-Slice-H.4 todos lacking the field, fall back to parsing `file:line` references from the todo body. Body refs remain useful for secondary file mentions even when frontmatter `file:` is present.
- Group todos that reference overlapping files → these must run **sequentially** within the group
- Non-overlapping groups can run in parallel

## Step 3: Spawn Resolver Agents

- Spawn `lp-harness-todo-resolver` agents (max 5 concurrent)
- Each agent receives:
  - The full todo file content
  - The working directory context
- Sequential within overlapping-file groups, parallel across groups

## Step 4: Collect Results

- Gather changed file lists from each resolver agent
- Gather resolution reports

## Step 4.5: Scope Validation

For each resolver agent's results:

- Verify modified files are within scope (files referenced in the todo + 1-hop imports)
- IF out-of-scope changes detected: revert those specific changes before committing
- This mirrors the `lp-pr-comment-resolver` Step 4 pattern

## Step 5: Stage and Commit

- Stage ONLY the files reported as changed by resolver agents (explicit `git add` per file, **no `git add -A`**)
- Commit with message: `fix: resolve review findings`
- This commit is **DURABLE** — safe from session crashes
- `/lp-ship` will add its own commit on top (two-commit strategy)
- If the repo uses squash-merge, both fold into one on main

## Step 6: Update Todo Status

- For each successfully resolved todo: update YAML frontmatter `status: pending` → `status: complete`

## Step 7: Report

- "{N} resolved, {M} files changed"
- List any todos that could not be resolved (with reason)
