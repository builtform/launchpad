---
name: lp-review
description: Multi-agent code review with confidence scoring, secret scanning, and headless mode for programmatic callers.
---
# /lp-review

Multi-agent parallel code review with confidence-based false-positive suppression.

## Usage

```
/lp-review                    → interactive mode (default)
/lp-review --headless         → programmatic mode (no interactive output, no report)
```

**Arguments:** `$ARGUMENTS` (parse for `--headless` flag)

---

## Step 0: Read Configuration

1. Read `.launchpad/agents.yml` → extract `review_agents`, `review_db_agents`, `review_design_agents`, `review_copy_agents`
2. Validate each agent name: must match `[a-z0-9-]+`, must resolve to a file in `.claude/agents/` (scan all subdirectories). Skip with warning if file not found — this handles `[Phase N]` agents gracefully.
3. Read `.harness/harness.local.md` → extract review context
4. If `agents.yml` missing: fall back to `lp-pattern-finder` only, warn user

## Step 1: Determine Diff Scope

```bash
git diff --name-only origin/main...HEAD
```

- Check for Prisma changes (files matching `packages/db/**`, `prisma/**`, `*.prisma`) → set `db_changes = true/false`

## Step 1.5: Read PR Intent Context (best-effort)

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

For each agent in `review_agents`:

- Spawn agent with: diff content + changed file list + files they directly import (1-hop) + review context from `.harness/harness.local.md`
- Agents use Grep/Glob for broader pattern checks — do NOT Read every file in the repo
- For `lp-code-simplicity-reviewer`: additionally pass "Changed Files: {list}. Suggest changes only to these files. Return observation text for anything outside this list."
- Prompt: "Review this code diff for issues in your domain. Return findings as structured list with file:line, severity (P1/P2/P3), and description."

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

1. Clear `.harness/todos/` directory (remove all existing `.md` files — idempotent on retry)
2. For EACH finding above 0.60 threshold, create:

   `.harness/todos/{id}-{description}.md`

   ```yaml
   ---
   status: pending
   priority: P1|P2|P3
   agent_source: <agent-name>
   confidence: 0.XX
   ---

   ## Problem
   [Description of the issue]

   ## Findings
   - `file.ts:42` - [specific issue at this location]

   ## Proposed Solution
   [How to fix it]
   ```

3. Write `.harness/review-summary.md`:

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
- Used by: `/lp-harden-plan` [Phase 3], `/lp-commit` Step 2.5 [Phase 7]
- NOT used by: `/lp-harness-build` (uses normal interactive mode for visibility)
