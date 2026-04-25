---
name: lp-creating-skills
description: "Creates new Claude Code skills using the 7-phase Meta-Skill Forge methodology. Produces quality-validated skills with progressive disclosure, evaluation loops, and contrarian analysis. Use when creating a new skill, teaching Claude a new workflow, building a custom agent capability, or automating a repeatable task. Triggers on: create skill, new skill, build skill, teach Claude, make a skill for."
---

# Meta-Skill Forge

NEVER produce a skill that looks like what Claude would generate with no skill loaded. Every skill must demonstrate structural differentiation from baseline output.

---

## Trigger

Activates when:

- Creating a new skill
- Teaching Claude a new workflow
- Building a custom agent capability
- Automating a repeatable task

Example invocations:

- `/lp-create-skill frontend development`
- `/lp-create-skill "API testing" based on docs/articles/api-guide.md`
- `"build a skill for database migrations"`
- `"teach Claude how to do code reviews"`

---

## What This Skill Does NOT Handle

| Request                         | Use Instead                                     |
| ------------------------------- | ----------------------------------------------- |
| Quick one-off prompts           | Direct prompting -- no skill needed             |
| Modifying an existing skill     | `/lp-update-skill`                              |
| Creating cognitive profiles     | `.claude/profiles/PROFILE-TEMPLATE.md` directly |
| Evaluating a skill in isolation | `skill-evaluator` sub-agent directly            |

---

## The Job

| Step | Phase       | Visible Output                                          |
| ---- | ----------- | ------------------------------------------------------- |
| 1    | Parse input | Skill topic + optional context files identified         |
| 2    | Research    | Research brief from two-wave sub-agents                 |
| 3    | Extract     | Validated answers from 4 collaborative rounds           |
| 4    | Analyze     | Contrarian frame with engineering-away plan             |
| 5    | Decide      | Architecture complexity tier (Simple / Moderate / Full) |
| 6    | Write       | SKILL.md + reference files + eval scenarios             |
| 7    | Validate    | Evaluation report (PASS / FAIL with diagnostics)        |
| 8    | Ship        | Registered skill + usage guide presented to user        |

Every step produces a visible artifact. No step is skipped.

---

## Phase 1: Context Ingestion

Read [references/METHODOLOGY.md](mdc:references/METHODOLOGY.md) for the full two-wave sub-agent protocol before proceeding.

### Wave 1: Discovery (parallel, inherit)

Spawn three sub-agents simultaneously:

1. **pattern-finder** -- Find existing skills, commands, and agent patterns in the codebase. Report file paths, structural conventions, and naming patterns.
2. **docs-locator** -- Find all documentation related to the skill topic. Include architecture docs, guides, learnings, and prior decisions.
3. **file-locator** -- Find all implementation files related to the skill topic. Include configs, scripts, and test files.

### Wave 2: Analysis (parallel, inherit)

After Wave 1 completes, spawn three more:

1. **code-analyzer** -- Analyze Wave 1 findings for patterns, anti-patterns, and conventions to follow.
2. **docs-analyzer** -- Extract decisions, constraints, rejected approaches, and promoted patterns from documentation.
3. **web-researcher** -- Search the web for best practices, common pitfalls, and expert approaches to the skill topic.

### Source Material Handling

If the user provided source files ("based on ..."):

1. Detect document size
2. If >10 pages: apply the distillation protocol from METHODOLOGY.md (chunked extraction with progressive summarization)
3. If <=10 pages: ingest directly into the extraction rounds

**Output:** Research brief summarizing findings across all sub-agents.

---

## Phase 2: Targeted Extraction

Read [references/METHODOLOGY.md](mdc:references/METHODOLOGY.md) for Mode A vs Mode B extraction protocols before proceeding.

### Mode Detection

Auto-detect based on Phase 1 inputs:

- **Mode A (source-material-informed):** User provided files, articles, or documentation. Extraction grounds questions in source material.
- **Mode B (open-ended expert extraction):** No source material. Extraction draws from codebase patterns, web research, and user expertise.

### 4 Collaborative Rounds

Each round is a focused conversation with the user:

| Round | Focus           | Question Type                                                     |
| ----- | --------------- | ----------------------------------------------------------------- |
| 1     | Scope           | What does this skill do and NOT do? What triggers it?             |
| 2     | Differentiation | What makes this approach different from a generic prompt?         |
| 3     | Structure       | What phases, reference files, and outputs does the skill produce? |
| 4     | Breaking Points | Where does the skill fail? What edge cases exist?                 |

Present 3-5 MCQ questions per round. User responds with shorthand (e.g., "1A, 2C, 3B").

### Adaptive Stopping

If the user defers on a round (e.g., "skip this" or "just decide"), answer the remaining questions using research findings from Phase 1. Skip remaining rounds only if the user explicitly requests it.

**Output:** Validated extraction answers for all 4 rounds.

---

## Phase 3: Contrarian Analysis

Read [references/CONTRARIAN-FRAME.md](mdc:references/CONTRARIAN-FRAME.md) before proceeding.

### Execute the Baseline Detection Process

1. **Write the generic version.** Ask: "If Claude received just the topic name and no skill, what would it produce?" Write 3-5 bullet points covering predictable structure, vocabulary, and assumptions.

2. **Name every predictable pattern.** List the default sections, ordering, hedge phrases, and assumptions that a skillless Claude would produce.

3. **Challenge 2-3 assumptions.** Identify the strongest assumptions in the generic version. For each one, articulate why it fails for this specific use case.

4. **Write the engineering-away plan.** For each predictable pattern, state the specific structural or behavioral difference the skill will enforce.

### User Confirmation

Present the contrarian frame to the user. Two possible outcomes:

- **Accepted:** Proceed to Phase 4 with the engineering-away plan as a constraint.
- **Rejected (first time):** Revise the frame based on user feedback.
- **Rejected (second time):** Ask the user directly: "What is your differentiation angle?" Use their answer as the constraint.

**Output:** Confirmed contrarian frame with engineering-away plan.

---

## Phase 4: Architecture Decision

Choose complexity based on discoveries from Phases 1-3:

### Simple

- Single SKILL.md under 300 lines
- No reference files
- Fast path: executes Phases 1, 2, 4, 5, 6 (lightweight evaluator), 7 (registration) — only Phase 3 is skipped
- Use when: the skill's entire knowledge fits in one file without crowding

### Moderate

- SKILL.md + 1-3 reference files
- All 7 phases execute, but only 2 extraction rounds (Scope + Structure)
- Use when: the skill has distinct sub-concerns that benefit from separation

### Full

- SKILL.md + multiple reference files + eval directory
- All 7 phases execute with all 4 extraction rounds
- Use when: the skill orchestrates a multi-phase process with deep domain knowledge

### Decision Protocol

Present the recommendation to the user with this format:

```
Architecture: [Simple / Moderate / Full]
Rationale: [1-2 sentences explaining why]
File plan:
  .claude/skills/<name>/SKILL.md
  .claude/skills/<name>/references/FILE-1.md  (if Moderate/Full)
  .claude/skills/<name>/references/FILE-2.md  (if Full)
  .claude/skills/<name>/evals/                (if Full)
```

Get user confirmation before proceeding.

**Output:** Confirmed architecture tier + file plan.

---

## Phase 5: Write the Skill

Read [references/SKILL-TEMPLATE.md](mdc:references/SKILL-TEMPLATE.md) and [references/REFERENCE-TEMPLATE.md](mdc:references/REFERENCE-TEMPLATE.md) before proceeding.

### Writing Rules

1. **Router, not textbook.** SKILL.md routes to reference files. Deep knowledge lives in references. Keep SKILL.md under the target line count for its tier.
2. **Independently loadable references.** Each reference file works without any other reference file loaded. No cross-reference chains.
3. **Constraints at START and END.** The critical constraint appears at the top and bottom of SKILL.md.
4. **No hedge language.** Remove "consider", "you might want to", "it's generally a good idea". Use imperatives: "Run", "Check", "Emit", "Reject".
5. **Visible output per phase.** Every phase in the skill produces a named artifact the user can inspect.
6. **Explicit loading triggers.** Each reference file loading is a specific instruction: "Read [file](path) before proceeding to [next step]."

### File Creation

Save files to `.claude/skills/<skill-name>/`:

- `SKILL.md` -- the orchestrator
- `references/*.md` -- one file per concern (if Moderate/Full)

### Fidelity Check (Source-Material Skills Only)

If the skill was built from user-provided source material (Mode A), spawn a **fidelity-check** sub-agent (Sonnet, read-only):

- Compare skill claims against source material
- Flag any invented procedures not in the source
- Flag any source material omitted from the skill
- Report discrepancies for user review

**Output:** Saved skill files + fidelity report (if applicable).

---

## Phase 6: Quality Validation

Read [references/QUALITY-GATES.md](mdc:references/QUALITY-GATES.md) before proceeding.

### Recursive Evaluation Loop

Spawn a `skill-evaluator` sub-agent (Sonnet, read-only access to skill files).

The loop:

```
GENERATE skill files
    |
EVALUATE (3 passes: first-principles, baseline detection, Anthropic checklist)
    |
ALL PASS? --yes--> Proceed to Phase 7
    | no
DIAGNOSE specific failures (explain WHY, not just WHAT)
    |
IMPROVE (rewrite targeting diagnosed weaknesses)
    |
RE-EVALUATE (max 3 cycles)
```

### After 3 Cycles

If the skill still has failing gates after 3 improvement cycles:

1. List remaining failures with diagnostics
2. Present to user with the question: "These issues remain. Ship as-is, or provide guidance?"
3. Act on user's decision

**Output:** Evaluation report (PASS or FAIL with remaining issues).

---

## Phase 7: Ship It

### Generate Evaluation Scenarios

Read [references/EVAL-TEMPLATE.md](mdc:references/EVAL-TEMPLATE.md) before proceeding.

Create at least 3 eval scenarios:

1. **Happy path** -- Standard invocation with typical inputs
2. **Edge case** -- Minimal, ambiguous, or tricky input
3. **Negative boundary** -- Input that looks related but is out of scope

Each scenario includes a baseline comparison (what Claude does WITHOUT the skill).

Save to `.claude/skills/<skill-name>/evals/`.

### Register the Skill

Update these files:

1. **CLAUDE.md** -- Add skill to the Progressive Disclosure table and Available Sub-Agents section
2. **AGENTS.md** -- Add skill entry with name, description, and trigger phrases
3. **`docs/skills-catalog/skills-usage.json`** -- Add `"<skill-name>": "YYYY-MM-DD"` to the `skills` object (use today's date). Create the file with initial structure if it doesn't exist: `{"last_audit_date": "YYYY-MM-DD", "skills": {}}`
4. **`docs/skills-catalog/skills-index.md`** -- Add the skill to the correct group in both the Quick Reference table and Detailed Descriptions section. Canonical groups (in order): Design & UI, Frontend Engineering, Backend Engineering, Data & Database, Testing & QA, DevOps & Infrastructure, Security & Auth, API & Integrations, Billing & Payments, Build Pipeline, Quality & Workflow, Documentation, Meta (Skill Management), Other. Assign the next sequential number. Place the skill in the best-fit group. Use "Other" only if no canonical group fits. Add a row to the group's Quick Reference table and a full description entry under the group's Detailed Descriptions heading.

### Present to User

Deliver a structured summary:

```
## Skill Created: <name>

### File Tree
.claude/skills/<name>/
  SKILL.md (XXX lines)
  references/
    FILE-1.md
    FILE-2.md
  evals/
    eval-scenarios.md

### Architecture
[Simple / Moderate / Full] -- [1 sentence rationale]

### Evaluation Findings
[PASS / FAIL] -- [summary of results]

### CLAUDE.md Changes
- Added to workflow commands table: [entry]
- Added to Available Sub-Agents: [entry]

### Usage
Invoke with: /lp-create-skill <topic>
Or say: "create a skill for <topic>"
```

Ask: "Commit these files, or adjust something first?"

---

## Verification Gate

Before delivering the skill to the user, confirm every item:

- [ ] Skill files saved to `.claude/skills/<skill-name>/`
- [ ] SKILL.md under 500 lines
- [ ] All reference files independently loadable
- [ ] No hedge language in any skill file
- [ ] Evaluation report shows PASS
- [ ] CLAUDE.md updated with skill entry
- [ ] AGENTS.md updated with skill entry
- [ ] `docs/skills-catalog/skills-usage.json` updated with new skill
- [ ] `docs/skills-catalog/skills-index.md` updated with new skill entry
- [ ] At least 3 eval scenarios created
- [ ] Output differs structurally from what Claude would produce without this skill

If any item fails, return to the relevant phase and fix before delivering.

---

NEVER produce a skill that looks like what Claude would generate with no skill loaded. Every skill must demonstrate structural differentiation from baseline output.
