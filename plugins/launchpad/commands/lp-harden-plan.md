---
name: lp-harden-plan
description: Stress-tests implementation plans using multiple review agents. Dispatches code-focused and document-review agents, with optional interactive deepening.
---

# /lp-harden-plan

Stress-tests an implementation plan using specialized review agents — both code-focused (technical gaps) and document-focused (quality/coherence).

## Usage

```
/lp-harden-plan [plan-path] --full          → all agents (section builds)
/lp-harden-plan [plan-path] --lightweight   → core agents (standalone default)
/lp-harden-plan [plan-path] --auto          → Auto-apply (used by /lp-plan)
/lp-harden-plan [plan-path] --interactive   → Present findings one-by-one for accept/reject/discuss
```

**Arguments:** `$ARGUMENTS` (parse for plan path, `--full`/`--lightweight`, `--auto`, `--interactive`)

If no intensity flag provided, default to `--lightweight`.
`--interactive` is default when called from `/lp-plan`.

**Plan path resolution:** if `$ARGUMENTS` names a section (not a file path), resolve to a file via `paths.plans_file_pattern` in `.launchpad/config.yml` (default `docs/tasks/sections/{section_name}-plan.md`). Expand `{section_name}` with the argument.

---

## Step 0: Prerequisite Check (Lite)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=lite --command=lp-harden-plan --require=.launchpad/agents.yml`.

**Ownership rule:** `/lp-harden-plan` ONLY reads `.launchpad/agents.yml` — it never writes and never overwrites. If the file is missing in a cold brownfield, the lite-mode prereq check exits 1 and prints a pointer to `/lp-define`. The shared prereq helper (`plugin-prereq-check.sh --mode=lite`) is fail-fast: it verifies required files exist and refuses if not, rather than creating them with placeholder content.

When `agents.yml` is missing, halt with the prereq error message and ask the user to run `/lp-define` to seed it. Do not invent or write a default `agents.yml` from inside `/lp-harden-plan` — authoritative seeding lives in `/lp-define` and crossing that boundary creates drift between hand-tuned and auto-seeded roster shapes.

---

## Step 1: Read Project Context

- Read `.launchpad/agents.yml` → extract `harden_plan_agents`, `harden_plan_conditional_agents`, `harden_document_agents`
- Read `.harness/harness.local.md` for project context
- Read the plan file at the provided path

## Step 1.5: Idempotency Check

- IF the plan file already contains `## Hardening Notes` → skip with message "Plan already hardened"
- This makes `/lp-harden-plan` safe to re-run

## Step 2: Document Quality Pre-Check

1. Load `document-review` skill
2. Fast-path: if initial scan finds no critical clarity issues (ambiguity, missing scope, contradictions), skip immediately
3. Only run full 5-question assessment when a red flag is detected
4. IF critical clarity issues found:
   - Auto-fix minor issues (log what was changed)
   - Ask approval for substantive issues
   - IF user declines a suggestion: discard silently (not written to observations — advisory only)
   - Re-read plan after fixes
5. This prevents dispatching agents against a plan with fundamental clarity problems

## Step 2.5: Learnings Scan (parallel with Step 2.7)

- Scan `docs/solutions/` for past learnings relevant to this plan
- Match by: tags, category, module in YAML frontmatter
- Skip files with malformed or missing frontmatter
- IF `docs/solutions/` empty or missing: skip silently
- Dispatch `lp-learnings-researcher` agent to search by frontmatter metadata
- IF matches found: pass at most 5 most-recent matches (key insight only, not full document)
- This ensures past mistakes and discoveries inform plan review

## Step 2.7: Context7 Technology Enrichment (parallel with Step 2.5)

- Parse plan for technology references (frameworks, libraries, APIs)
- Query Context7 MCP for current documentation — ALL queries run IN PARALLEL
- Focus on: breaking changes, deprecated APIs, version-specific gotchas
- Collect insights → pass to agents as supplementary context
- IF Context7 MCP unavailable: skip silently (graceful degradation)
- Per-query timeout: 10s. Total step timeout: 30s.
- IMPORTANT: Queries MUST contain only library names + version numbers. NEVER include plan content or business logic in queries.

## Step 3: Dispatch Code-Focused Agents (all model: inherit)

Read agent names from `.launchpad/agents.yml`:

### Always dispatched (both `--full` and `--lightweight`):

Read `harden_plan_agents` from `agents.yml`. Dispatch all listed agents in parallel with plan + project context + learnings + Context7 enrichment.

### Conditional (`--full` only):

Read `harden_plan_conditional_agents` from `agents.yml`. Dispatch all listed agents in parallel.

**Agent resolution:** Scan `${CLAUDE_PLUGIN_ROOT}/agents/**` for `{name}.md` (built-ins shipped with the plugin; their on-disk filenames already include the `lp-` prefix and `agents.yml` stores names with the prefix to match) first, then `.claude/agents/**` for `{name}.md` (project-local extensions). First match wins. If agent file not found, skip silently with a note.

## Step 3.5: Dispatch Document-Review Agents

- Read `harden_document_agents` from `.launchpad/agents.yml`
- IF not empty: dispatch all document-review agents in parallel with plan + project context
- `lp-design-lens-reviewer`: ONLY dispatched when section has UI components (skip when `"design:skipped"`)
- Runs AFTER Step 3 code-focused agents complete, so document reviewers can reference code-focused findings

## Step 3.7: Interactive Deepening

IF `--interactive` (default when called from `/lp-plan`):

1. Collect all findings from Step 3 + Step 3.5
2. Present each agent's findings one-by-one, grouped by agent
3. For each set: "Accept / Reject / Discuss?"
   - **Accept:** integrate into Hardening Notes
   - **Reject:** discard (not written anywhere — advisory only)
   - **Discuss:** open dialogue, then re-present for accept/reject
4. This gives the human control over what goes into the plan

IF `--auto`: skip interactive deepening, auto-merge all findings

## Step 4: Synthesize Findings

- Collect all accepted findings (from interactive deepening) or all findings (from --auto)
- Deduplicate overlapping concerns
- Prioritize: P1 (must fix before build), P2 (should fix), P3 (nice to have)

## Step 5: Apply

### IF `--auto` (used by `/lp-plan`):

- Append `## Hardening Notes` section to the plan file automatically
- Include all findings organized by priority
- No user prompt

### IF standalone (no `--auto`):

- Present findings summary to user
- Ask: "Apply these hardening notes to the plan? (yes/no)"
- IF yes: append `## Hardening Notes` section
- IF no: exit with "Hardening notes not applied"
