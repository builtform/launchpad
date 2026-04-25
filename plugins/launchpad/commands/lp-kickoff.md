---
name: lp-kickoff
description: Meta-orchestrator for brainstorming. Runs Step 0 prereq check, delegates to /lp-brainstorm for collaborative idea exploration, then hands off to /lp-define.
---

# /lp-kickoff

Meta-orchestrator for the brainstorming phase. The entry point — no upstream dependency. Works in empty brownfield repos from cold start.

---

## Step 0: Prerequisite & Capability Check

Before running the brainstorm workflow, establish the minimum state this command needs and surface any pre-existing LaunchPad config that requires user acknowledgment.

### 0.1 — Detect config and paths

Read `.launchpad/config.yml` if it exists. Extract `paths.brainstorms_dir` (default: `docs/brainstorms`).

- **IF `.launchpad/config.yml` does NOT exist** — this is a cold start in a fresh repo. Proceed with LaunchPad defaults. Do NOT scaffold `config.yml` here — that's `/lp-define`'s job.
- **IF `.launchpad/config.yml` exists** — a prior LaunchPad install is already here. Before writing anything, print the detected paths and ask the user to confirm:

  > "Detected existing `.launchpad/config.yml`. Brainstorms will go to `<paths.brainstorms_dir>`. Proceed? [Y/n]"

  If the user declines, exit cleanly — let them edit config first.

### 0.2 — Auto-create brainstorms_dir

Silently run `mkdir -p <paths.brainstorms_dir>` (resolved path from 0.1). No prompt — it's just a directory. The prereq-check helper's rollback tracker logs this creation in case the user later exits mid-Step-0 via `[d]`.

### 0.3 — Validate write path

The resolved `paths.brainstorms_dir` must be inside the repo root (the config loader already enforces realpath-confinement, but if this command was invoked with a manually-overridden env var, re-verify here).

---

## Step 1: Run /lp-brainstorm

Delegate to `/lp-brainstorm` — the brainstorm command handles:

- Loading the brainstorming skill
- Dispatching research agents when codebase exists
- Collaborative dialogue
- Design document capture to the configured brainstorms directory
- Post-capture refinement via document-review skill

## Step 2: Transition

"Brainstorm captured to `<paths.brainstorms_dir>`. Run `/lp-define` to scaffold canonical architecture docs based on your detected stack."

---

## Acceptance behavior

- **Cold start, empty brownfield**: works with zero prior config, creates `docs/brainstorms/`, proceeds directly.
- **Existing LaunchPad repo**: detects existing `config.yml`, confirms path before write, honors custom `paths.brainstorms_dir`.
- **Alongside other tools using `docs/`**: non-destructive — only creates the specific brainstorms subdirectory, never deletes or reorganizes other `docs/` content.
- **Never blocks with "must run X first"** — `/lp-kickoff` has no upstream dependency in the harness pipeline.
