---
name: resolve_todo_parallel
description: Resolves review findings in .harness/todos/ by spawning parallel harness-todo-resolver agents (max 5 concurrent).
---

# /resolve_todo_parallel

Resolves pending review findings from `.harness/todos/` using parallel resolver agents.

---

## Step 1: Read Pending Todos

- Scan `.harness/todos/` for `.md` files
- Parse YAML frontmatter: filter for `status: pending`
- IF none found: report "0 findings to resolve" → exit

## Step 2: Group by File Overlap

- Parse `file:line` references from each todo body
- Group todos that reference overlapping files → these must run **sequentially** within the group
- Non-overlapping groups can run in parallel

## Step 3: Spawn Resolver Agents

- Spawn `harness-todo-resolver` agents (max 5 concurrent)
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
- This mirrors Phase 4's pr-comment-resolver Step 4 pattern

## Step 5: Stage and Commit

- Stage ONLY the files reported as changed by resolver agents (explicit `git add` per file, **no `git add -A`**)
- Commit with message: `fix: resolve review findings`
- This commit is **DURABLE** — safe from session crashes
- `/ship` will add its own commit on top (two-commit strategy)
- If the repo uses squash-merge, both fold into one on main

## Step 6: Update Todo Status

- For each successfully resolved todo: update YAML frontmatter `status: pending` → `status: complete`

## Step 7: Report

- "{N} resolved, {M} files changed"
- List any todos that could not be resolved (with reason)
