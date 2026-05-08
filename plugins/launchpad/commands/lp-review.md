---
name: lp-review
description: Multi-agent code review with confidence scoring, secret scanning, and headless mode for programmatic callers.
---

# /lp-review

Multi-agent parallel code review with confidence-based false-positive suppression.

## Usage

```
/lp-review                              → interactive mode (default)
/lp-review --headless                   → programmatic mode (no interactive output, no report)
/lp-review --no-context                 → bias-stripped mode (skips PR intent, harness context, agent specialty framing)
/lp-review --headless --no-context      → both (used by /lp-commit Step 2.5 in Phase 2)
```

**Standalone usage:** `--no-context` runs in append mode and does NOT clear `.harness/todos/`. To run blind-only review without accumulation, manually `rm -f .harness/todos/*.md` first OR run `/lp-review --headless` first to reset, then `/lp-review --no-context`.

**Arguments:** `$ARGUMENTS` (parse for `--headless` AND `--no-context` flags; both independent and may co-exist; order-independent; duplicate-flag idempotent)

---

## Step 0: Read Configuration

1. Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=lite --command=lp-review --require=.launchpad/agents.yml` — verify-or-refuse: the lite helper checks the required file exists and exits 1 with a pointer to `/lp-define` if not. `/lp-define` is the authoritative seeder; this command never writes `agents.yml`.
2. Load paths via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-config-loader.py` so `paths.architecture_dir` etc. override defaults where relevant.
3. Read `.launchpad/agents.yml` → extract `review_agents`, `review_db_agents`, `review_design_agents`, `review_copy_agents`
4. Validate each agent name: must match `[a-z0-9-]+`. Resolve to a file by scanning `${CLAUDE_PLUGIN_ROOT}/agents/**` for `{name}.md` (built-ins shipped with the plugin; their on-disk filenames already include the `lp-` prefix, e.g. `lp-pattern-finder.md`, and `agents.yml` stores names with the prefix to match) first, then `.claude/agents/**` for `{name}.md` (project-local extensions). Skip with warning if file not found — this handles unimplemented optional agents gracefully.
5. Read `.harness/harness.local.md` → extract review context
6. The lite prereq helper above already refuses with a `/lp-define` pointer when `agents.yml` is missing, so reaching this point means the file exists. No in-command fallback is needed; the legacy "fall back to `lp-pattern-finder` only" path was prose drift that contradicted the helper's verify-or-refuse contract.

## Step 1: Determine Diff Scope

```bash
git diff --name-only origin/main...HEAD
```

- Check for Prisma changes (files matching `packages/db/**`, `prisma/**`, `*.prisma`) → set `db_changes = true/false`

## Step 1.5: Read PR Intent Context (best-effort)

**IF `--no-context` flag is set: skip this entire step. Set `intent_context = empty` and proceed to Step 2.**

- IF a PR exists for current branch: run `gh pr view --json title,body,labels`
  - Extract PR title, body, linked issue number/description
  - Store as `intent_context` for Step 5 confidence scoring
- IF no PR exists: `intent_context = empty` (scoring proceeds without it)
- NEVER fail on this step — purely supplementary context

## Step 2: Pre-dispatch Secret Scan (best-effort)

1. Read patterns from `.launchpad/secret-patterns.txt` (one pattern per line)
2. Get diff: `git diff origin/main...HEAD`
3. Scan only **added lines** (`+` prefix) for matches against each pattern
4. IF matches found: **HALT** and warn user with specific matches
5. Note: best-effort scan. For comprehensive detection, integrate gitleaks/trufflehog.

## Step 3: Dispatch Review Agents (parallel, all model: inherit)

**Pre-filter (v2.1 Phase 6 §3.3 + DA3)**: before dispatch, narrow
`review_agents` through `plugin_agent_scope_filter.filter_agents_by_stacks(
review_agents, stacks)` where `stacks = plugin_config_loader.read_stacks(cwd)`.
The filter drops agents whose `stack_scope` does not match any of the
project's persisted stacks. Step 4 (DB-only conditional), Step 4.5
(design conditional) are NOT filtered. `/lp-review` has no Step 3.5.

**Pass-through fallback** (cycle-4 spec-flow P2-B): if the filter raises
ANY exception, catch broadly, log INFO with the exception type, and emit
the FALLBACK banner to user-visible output:

> ⚠ stack-filter unavailable (\<exception type\>); dispatching full
> roster of N agents

Then dispatch all input agents verbatim.

**Partial-drop banner**: if the filter completes with non-empty
`last_dropped_names()`, emit the PARTIAL-DROP banner:

> ⚠ stack-filter dropped unknown names: \[\<name1\>, \<name2\>\];
> dispatching M of N agents

Then dispatch the M survivors. Both banners go to user-visible command
output, not buried logs.

**v2.1 narrowing reality**: with all 13 review/ agents classified as
`stack:any` per cycle-3 axis-mismatch fix, the filter primarily provides
corpus discipline + the bogus-stack-id validation gate; narrowing on
`stack:<id>` is dead-code in v2.1 (forward-compat for v2.2 framework-axis
wire-through). See plan §1 transparency note.

For each survivor agent in `review_agents`:

- Spawn agent with: diff content + changed file list + files they directly import (1-hop)
- Review context source:
  - DEFAULT: pass review context extracted from `.harness/harness.local.md` (Step 0 step 5)
  - `--no-context` mode: pass empty string for review context
- Agents use Grep/Glob for broader pattern checks — do NOT Read every file in the repo
- For `lp-code-simplicity-reviewer`:
  - DEFAULT: additionally pass "Changed Files: {list}. Suggest changes only to these files. Return observation text for anything outside this list."
  - `--no-context` mode: DROP this constraint — the simplicity reviewer may flag findings outside changed files (no `feature_scope` narrowing)
- Per-agent prompt:
  - DEFAULT: "Review this code diff for issues in your domain. Return findings as structured list with file:line, severity (P1/P2/P3), and description."
  - `--no-context` mode: "Review this code diff for bugs at P0/P1. You have NO project context. The diff and file tree are all you have. Flag bugs you can identify from the code alone." (APPENDED to the agent's base specialty prompt — agent identity persists; context-stripping is partial per master plan D3 honest-naming)

## Step 4: Conditional DB Agent Dispatch (sequential-then-parallel)

IF changed files match `prisma/schema.prisma` OR `prisma/migrations/*`:

**Step 4a:** Dispatch `lp-schema-drift-detector` (SEQUENTIAL — runs first)

- Pass: diff + Prisma files + review context
- Wait for output → `drift_report`

**Step 4b:** Dispatch IN PARALLEL with drift report as context:

- `lp-data-migration-auditor` — receives: diff + Prisma files + review context + `drift_report`
- `lp-data-integrity-auditor` — receives: diff + Prisma files + review context + `drift_report`

The drift report lets downstream agents focus only on legitimate changes, ignoring drifted changes that should be removed.

## Step 4.5: Conditional Design Agents

**Artifact-based dispatch** (decoupled from section registry):

- Check if `.harness/design-artifacts/` contains any `*-approved.png` files
- IF approved design artifacts exist AND `review_design_agents` is not empty:
  - Dispatch all agents from `review_design_agents` in parallel
  - IF Figma artifacts also exist (`.harness/design-artifacts/*-figma.*`): additionally dispatch `lp-design-implementation-reviewer` (marked `# conditional` in agents.yml)
- IF no design artifacts exist: skip design agents entirely
- IF no design artifacts but diff contains UI-relevant files (`.tsx`, `.css`, `.html` in `apps/web/` or `packages/ui/`): emit P2 warning finding

**Copy review dispatch:**

- Read `review_copy_agents` from `.launchpad/agents.yml`
- IF list is non-empty: dispatch all `review_copy_agents` in parallel
- IF list is empty: skip silently (expected in LaunchPad — downstream projects populate)

## Step 5: Confidence Scoring & Synthesis

Runs AFTER all agents return findings, BEFORE writing to `.harness/todos/`.

### Step 5a: Collect raw findings from all agents

### Step 5b: Deduplicate

- Same file:line + same concern → merge into single finding
- Track which agents flagged each finding (for multi-agent boost)

### Step 5c: Confidence Scoring (per finding)

Score each finding 0.00-1.00 using this rubric:

| Tier        | Range     | Meaning                                          |
| ----------- | --------- | ------------------------------------------------ |
| Certain     | 0.90-1.00 | Verified bug, security vulnerability with proof  |
| High        | 0.75-0.89 | Strong evidence, clear code path to failure      |
| Moderate    | 0.60-0.74 | Reasonable concern, would benefit from review    |
| Low         | 0.40-0.59 | Possible issue, limited evidence                 |
| Speculative | 0.20-0.39 | Theoretical concern, no concrete evidence        |
| Noise       | 0.00-0.19 | Generic advice, style preference, not actionable |

**False-positive suppression** — suppress (score < 0.60) findings matching:

1. **Pre-existing issues**: finding describes code unchanged in this diff
2. **Style nitpicks**: formatting, naming preferences with no functional impact
3. **Intentional patterns**: code follows a documented project convention
4. **Handled-elsewhere**: concern is addressed in another file/layer
5. **Code restatement**: finding just describes what the code does, not a problem
6. **Generic advice**: "consider using X" without specific evidence of need

**Boosters:**

- Multi-agent agreement: 2+ agents flag same issue → +0.10
- Security/data concern: finding involves auth, secrets, PII → +0.10
- P1 floor: any finding classified P1 by agent → minimum 0.60 (never auto-suppressed)

**Intent verification** (only when `intent_context` is available):

- IF finding contradicts stated PR intent (e.g., PR says "remove feature X", finding says "feature X is missing") → suppress with note
- IF finding aligns with PR intent → no change

### Step 5d: Filter

- Suppress findings below 0.60 threshold
- Suppressed findings are NOT written to `.harness/todos/`
- Suppressed findings ARE logged in `.harness/review-summary.md` under "## Suppressed Findings ({N})" with score and suppression reason
- This provides audit trail without noise in the todo queue

### Step 5e: Prioritize remaining findings → P1/P2/P3

## Step 6: Write Outputs

**Lifecycle (DEFAULT vs `--no-context`):**

| Artifact                       | DEFAULT mode             | `--no-context` mode                                                            |
| ------------------------------ | ------------------------ | ------------------------------------------------------------------------------ |
| `.harness/todos/` (directory)  | clear-and-write (v2.1.0) | create-if-missing-else-append                                                  |
| `.harness/observations/` (dir) | clear-and-write          | create-if-missing-else-append                                                  |
| `.harness/review-summary.md`   | overwrite (v2.1.0)       | APPEND `## --no-context (blind) findings` section; create-fresh if file absent |

Single-file vs directory artifacts have different "append" semantics — intentional. The summary file uses APPEND-section because a single file with multiple sections is the natural shape; directories use create-if-missing-else-append because each finding is a separate file.

1. Clear `.harness/todos/` directory (remove all existing `.md` files — idempotent on retry)
   - **EXCEPTION (`--no-context` mode):** DO NOT clear. Append mode preserves specialist-pass findings for dual-pass orchestration in Phase 2's `/lp-commit` Step 2.5.
   - **Create-if-missing-else-append semantics:** if `.harness/todos/` does not exist (clean checkout, never run before), `--no-context` mode CREATES the directory and writes new finding files. "Append mode" means "preserve existing files and add new ones," not "skip writes when no prior content exists."
   - **MANDATORY sequential invocation — `/lp-review` CONTRACT:** ALL `/lp-review` callers (Phase 2 `/lp-commit`, future async wrappers, third-party consumers) MUST run specialist pass to completion BEFORE invoking `--no-context` pass. Parallel invocation is undefined behavior — specialist's clear would race with blind's writes, silently dropping blind findings. Phase 1 has NO runtime guard against parallel invocation; enforcement is process-level (Phase 2's `/lp-commit` Step 2.5 spec encodes sequential ordering). v2.2 BL candidate for sentinel-based mutex (mirror `lp_update_identity/sentinel.py` pattern).
   - **Standalone caller contract:** if a caller invokes `--no-context` standalone, prior `.harness/todos/` content from any previous run persists. Manual cleanup is caller's responsibility (see Standalone Usage in Usage block).
   - **Repeated `--no-context` runs:** running blind twice consecutively standalone produces blind-vs-blind filename collisions at identical slugs. Tolerated for Phase 1; Phase 2 callers MUST run blind exactly once per `/lp-commit` invocation (NOT per re-triage loop within a single invocation).
2. For EACH finding above 0.60 threshold, create:

   `.harness/todos/{id}-{description}.md`

   ```yaml
   ---
   status: pending
   priority: P1|P2|P3
   agent_source: <agent-name>     # specialist pass
   confidence: 0.XX
   ---

   ## Problem
   [Description of the issue]

   ## Findings
   - `file.ts:42` - [specific issue at this location]

   ## Proposed Solution
   [How to fix it]
   ```

   **`--no-context` mode:** `agent_source` is suffixed with literal `-blind`:

   ```yaml
   agent_source: <agent-name>-blind # blind / no-context pass
   ```

   **Consumer contract for `-blind` suffix:** all consumers of `agent_source` (current + future v2.1.x/v2.2 consumers) MUST `removesuffix("-blind")` before any agent-name resolution (e.g., `Task(subagent_type=...)`). Failure to strip results in "agent not found" — Task tool fails closed (NOT silent execution), so no security risk, but coordination bug if consumers don't strip. Consumers that present `agent_source` for human triage (e.g., `/lp-triage`'s display) may show the suffix as-is for transparency. Existing consumers verified in v2.1.1 Phase 1 (`/lp-triage`, `/lp-resolve-todo-parallel`, `lp-harness-todo-resolver`) are read-only display or update-in-place; no agent-name dispatch via `agent_source`. Existing `agent_source` writers (`lp-defer.md` writes literal `manual`; `lp-test-browser.md` writes literal `test-browser`) are never `-blind`-suffixed.

   **Edge case — empty/missing `agent_source`:** if a finding lacks `agent_source` (defensive code path), suffix logic produces `unknown-blind` (NOT bare `-blind`). Default mode preserves v2.1.0 behavior on missing `agent_source` (no defensive `unknown` fallback added in Phase 1 — non-regression posture). Symmetric handling is a v2.1.x BL candidate.

3. Write `.harness/review-summary.md`:
   - **DEFAULT mode (specialist pass):** overwrite `.harness/review-summary.md` (v2.1.0 behavior).
   - **`--no-context` mode:** APPEND a `## --no-context (blind) findings` section to the existing file. If the file does not exist (standalone `--no-context`, no prior specialist pass), CREATE it with a single `## --no-context (blind) findings` section.
   - **Section body schema:** the appended `## --no-context (blind) findings` section uses identical body schema to the `## Findings (N)` section below — one bullet per finding with file:line, severity (P1/P2/P3), description, and `agent_source` (with `-blind` suffix). Identical structure prevents downstream parser drift if Phase 2's `/lp-triage` or v2.1.2 corpus reviewer reads by section.

   DEFAULT-mode body (v2.1.0):

   ```markdown
   ## Findings ({N})

   [List of findings above threshold with priority and confidence]

   ## Suppressed Findings ({M})

   [List of suppressed findings with score and suppression reason]

   ## Stats

   - Total raw findings: X
   - Suppressed: Y (Z% suppression rate)
   - Multi-agent agreement: W findings
   ```

4. IF zero findings above threshold: write "Clean review — no actionable findings" to summary

5. Write observation text from `lp-code-simplicity-reviewer` to `.harness/observations/`:
   - For each observation, create `.harness/observations/{id}-{description}.md`
   - YAML frontmatter: `status: observation`, `priority: p3`, `issue_id: "obs-{N}"`, `tags: [simplification]`, `observed_in: "path/to/file"`, `feature_scope: "{changed files list}"`
   - Body: Observation description + "Why Not Actioned: Outside the current feature scope."
   - Agents return observation text — `/lp-review` owns all file writes
   - **DEFAULT mode:** clear-and-write (matches `.harness/todos/` default).
   - **`--no-context` mode:** create-if-missing-else-append (matches `.harness/todos/` `--no-context` lifecycle). `agent_source` field gets `-blind` suffix (e.g., `agent_source: lp-code-simplicity-reviewer-blind`). The `feature_scope` field is OMITTED (or empty string) since the constraint was dropped at dispatch per Step 3.

## Step 7: Report (SKIPPED in --headless mode)

- "{N} findings ({P1} critical, {P2} important, {P3} nice-to-have)"
- "{M} findings suppressed (below 0.60 confidence threshold)"
- IF `--headless`: skip this step entirely. Callers read `.harness/todos/` and `.harness/review-summary.md` directly.

---

## Headless Mode Contract

When invoked with `--headless`, `/lp-review` behaves identically through Steps 0-6 but:

- Suppresses all interactive output (no progress messages, no user prompts)
- Skips Step 7 (Report)
- Returns silently — callers read `.harness/todos/` and `.harness/review-summary.md`
- Used by: `/lp-harden-plan` (Step 3), `/lp-commit` (Step 2.5)
- NOT used by: `/lp-build` (uses normal interactive mode for visibility)
