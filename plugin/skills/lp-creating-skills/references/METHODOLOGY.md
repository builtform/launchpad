# Meta-Skill Forge: 7-Phase Methodology

Reference document for the creating-skills meta-skill. Describes the full methodology for building Claude Code skills inside the Launchpad framework, adapted for Launchpad's two-wave sub-agent architecture.

Load this file when Phase 2 (Targeted Extraction) begins or when any phase references the methodology pipeline.

---

## Overview

The Meta-Skill Forge transforms domain expertise into structured Claude Code skills through seven sequential phases. Each phase produces a visible artifact. No phase is optional -- Phase 4 determines depth, but every phase executes.

| Phase | Name                  | Output                                  | Sub-Agents  |
| ----- | --------------------- | --------------------------------------- | ----------- |
| 1     | Context Ingestion     | Research brief + file inventory         | 3-6 (waves) |
| 2     | Targeted Extraction   | Validated extraction answers (4 rounds) | 0           |
| 3     | Contrarian Analysis   | Challenge frame + engineering responses | 0           |
| 4     | Architecture Decision | Complexity tier + file plan             | 0           |
| 5     | Write the Skill       | SKILL.md + reference files              | 0-1         |
| 6     | Quality Validation    | Evaluation report + fixes               | 1           |
| 7     | Ship It               | Registered skill + usage guide          | 0           |

---

## Phase 1: Context Ingestion

Build a complete understanding of the skill's domain before asking the user any questions. Follows the two-wave sub-agent pattern from `pnf.md`.

### Wave 1: Discovery (parallel, inherit, no Read tool)

| Agent            | Task                                                                | Tools      |
| ---------------- | ------------------------------------------------------------------- | ---------- |
| `lp-pattern-finder` | Find existing skills, commands, and workflow patterns in `.claude/` | Glob, Grep |
| `lp-docs-locator`   | Find relevant docs across `docs/`, `CLAUDE.md`, `AGENTS.md`         | Glob, Grep |
| `lp-file-locator`   | Find implementation files related to the skill's target domain      | Glob, Grep |

**Wait for ALL Wave 1 agents before spawning Wave 2.**

### Wave 2: Analysis (parallel, inherit, targeted by Wave 1)

| Agent            | Task                                                          | Tools               |
| ---------------- | ------------------------------------------------------------- | ------------------- |
| `lp-code-analyzer`  | Read and understand patterns at paths from Wave 1             | Read, Glob, Grep    |
| `lp-docs-analyzer`  | Extract decisions, constraints, conventions from located docs | Read, Glob, Grep    |
| `lp-web-researcher` | Gather current docs for unfamiliar libraries or techniques    | WebSearch, WebFetch |

**Wait for ALL Wave 2 agents before proceeding.**

### Source Material Handling

When the user provides context files ("based on this report," "adapt from this document"):

- **Document <= 10 pages:** Read fully into context. No sub-agent required.
- **Document > 10 pages:** Spawn `source-material-researcher` (Opus, read-only). Reads in chunks of 20 pages per pass. Produces: (a) General context brief (~2-3 pages) summarizing core concepts, terminology, and structure. (b) Round-specific draft answers for Phase 2's four extraction rounds, keyed to source sections with page references.

---

## Phase 2: Targeted Extraction (Collaborative Review)

Extract the precise domain knowledge required to build the skill through structured user interaction.

### Two Modes

**Mode A (Source-Material-Informed):** Activated when Phase 1 studied a source document. Present draft answers alongside each question. User validates, augments, overrides, or defers each answer.

**Mode B (Open-Ended):** Activated when no source material exists. User is the domain expert. Direct questions only.

### Four Extraction Rounds

| Round | Name            | Core Questions                                                                                           |
| ----- | --------------- | -------------------------------------------------------------------------------------------------------- |
| 1     | Scope           | What does this skill do? What does it NOT do? Who uses it and when?                                      |
| 2     | Differentiation | What makes this different from manual execution? What does the skill know that a generic agent does not? |
| 3     | Structure       | What phases/steps? What inputs and outputs at each step? What decision points?                           |
| 4     | Breaking Points | What goes wrong? What edge cases? What does failure look like, and how must recovery work?               |

**Mode A format:** Present draft answer with source page references, then questions targeting gaps. User actions: Validate / Augment / Override / Defer.

**Mode B format:** 2-3 direct questions per round. User says "skip" for any they want inferred from context.

### Adaptive Stopping

If the user accepts Rounds 1-2 without modification or defers both: compress Rounds 3 and 4 into a single combined round with only the highest-priority questions. Note the compression in the extraction summary.

---

## Phase 3: Contrarian Analysis

Prevent the skill from becoming a generic, predictable checklist.

1. Load `CONTRARIAN-FRAME.md` from creating-skills references
2. Write out: the generic version of the skill (what a lazy build looks like), 2-3 predictable patterns, and 2-3 assumptions to challenge with engineering responses for each:

| #   | Assumption            | Challenge               | Engineering Response      |
| --- | --------------------- | ----------------------- | ------------------------- |
| 1   | [Unstated assumption] | [Why it might be wrong] | [How to design around it] |

3. Present the full analysis to the user
4. Incorporate user response into Phase 4

---

## Phase 4: Architecture Decision (+ Adaptive Complexity)

Choose structural complexity based on Phases 1-3. **This decision happens here, NOT upfront.** Never pre-commit to a tier before extraction and contrarian analysis complete.

### Three Tiers

| Tier     | Structure                                      | Phases Run                                | Extraction Rounds |
| -------- | ---------------------------------------------- | ----------------------------------------- | ----------------- |
| Simple   | Single SKILL.md, <300 lines                    | 1, 2 (2 rounds), 4, 5 + lightweight check | 2                 |
| Moderate | SKILL.md + 1-3 reference files                 | All 7                                     | 2                 |
| Full     | SKILL.md + workflow + concept + template files | All 7                                     | 4                 |

**Simple** when: <3 phases, no external knowledge needed, single instruction set, no sub-agents during execution.

**Moderate** when: 3-6 phases, reference material improves quality, common structure across use cases, 1-2 sub-agents during execution.

**Full** when: 7+ phases or branching workflows, extensive reference/template needs, distinct execution paths, multiple sub-agents, skill creates artifacts.

Present to user: recommended tier, rationale (2-3 sentences), proposed file plan with paths and purposes, phase adjustments. Wait for approval.

---

## Phase 5: Write the Skill

Produce the actual skill files following Launchpad conventions.

### Prerequisites

Load `SKILL-TEMPLATE.md` and `REFERENCE-TEMPLATE.md` before writing.

### Six Writing Rules

1. **SKILL.md is a ROUTER, not a textbook.** Dispatch to reference files for deep content. Never more than 2-3 sentences of explanation per phase.
2. **Reference files are independently loadable.** Each starts with a one-line load trigger. No reference file depends on another being loaded simultaneously.
3. **Critical constraints at START and END.** Place the most important rules in the first 5 and last 5 lines of every file.
4. **No hedge language.** Use "always," "never," "must." Never "try to," "consider," "you might want to."
5. **Every phase yields visible output.** No phase completes silently -- every one produces a markdown block, file, table, or user-facing message.
6. **Imperatives throughout.** Command form: "Spawn three agents," "Present the analysis." Never passive voice for instructions.

### Fidelity Check (Source-Material Skills Only)

When the skill was built from a source document, spawn `fidelity-check` (Sonnet, read-only) before Phase 6. It spot-checks 3-5 critical claims per reference file against the original source.

| Status    | Meaning                     | Action                       |
| --------- | --------------------------- | ---------------------------- |
| VERIFIED  | Matches source exactly      | None                         |
| ADAPTED   | Reasonable interpretation   | None                         |
| DRIFTED   | Shifted meaning from source | Fix before Phase 6           |
| UNSOURCED | No basis in source material | Fix or remove before Phase 6 |

All DRIFTED and UNSOURCED claims must be resolved before proceeding.

---

## Phase 6: Quality Validation

Evaluate the skill against Launchpad's quality standards.

1. Load `QUALITY-GATES.md` from creating-skills references
2. Spawn `lp-skill-evaluator` (Sonnet, read-only) to evaluate against all quality gates
3. Execute the recursive improvement loop (max 3 cycles):

```
Generate --> Evaluate --> Diagnose --> Improve
```

**Cycle 1:** Evaluate initial output. All gates pass --> Phase 7.
**Cycle 2:** Fix Cycle 1 issues, re-evaluate. All gates pass --> Phase 7.
**Cycle 3 (final):** Fix remaining issues, re-evaluate. If gates still fail, document failures in shipping notes and proceed to Phase 7 with explicit warnings.

Never exceed 3 cycles. Each cycle produces an evaluation report: gate-by-gate pass/fail table, overall status, root cause diagnosis, and prescribed fix.

---

## Phase 7: Ship It

### 7a: Registration

1. **CLAUDE.md** -- Add entry to Available Skills table: skill name, trigger phrases, one-line description
2. **AGENTS.md** -- Add skill to agents config: skill path, description, trigger conditions

### 7b: Presentation

Present to user: file tree with one-line purpose per file, architecture rationale (referencing Phase 4 decision), evaluation findings (what passed, what was fixed, known limitations), exact CLAUDE.md and AGENTS.md changes, usage guide (invocation, inputs, outputs).

---

## Context Signals (Error Handling)

Every phase must handle degraded conditions. Never silently skip a phase.

| Signal                                  | Response                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------- |
| Wave 1 finds nothing                    | Proceed with user context + web research. Note the gap.                   |
| User rejects contrarian frame           | Revised frame. If rejected twice, ask user for their angle.               |
| Evaluator conflicts with user expertise | User always wins. Document the override.                                  |
| Topic too simple                        | Phase 4 routes to Simple. Document why.                                   |
| No context files AND no codebase        | Note honestly in architecture rationale. Build from user expertise alone. |
| Source document > 10 pages              | Phase 1 distillation protocol. Never skip distillation.                   |
| Fidelity check finds DRIFTED/UNSOURCED  | Fix all flagged claims before Phase 6. Never ship drifted content.        |
| Quality gate fails after 3 cycles       | Document failures. Ship with warnings. Never silently pass.               |
| User defers all extraction rounds       | Compress to 2 rounds. Infer from context. Flag all inferences.            |

---

## Phase Dependencies

Phases execute sequentially. No phase starts before its predecessor completes. The adaptive stopping rule in Phase 2 compresses rounds but never skips the phase.

```
Phase 1 --> Phase 2 --> Phase 3 --> Phase 4 --> Phase 5 --> Phase 6 --> Phase 7
```

Phase 4 retroactively determines depth of Phases 5-7 but never skips them. A Simple-tier skill still runs Phase 6 (lightweight evaluator pass) and Phase 7 (registration).

---

## Sub-Agent Summary

| Agent                        | Phase | Model   | Mode      | Spawned When                |
| ---------------------------- | ----- | ------- | --------- | --------------------------- |
| `lp-pattern-finder`             | 1     | inherit | Read-only | Always (Wave 1)             |
| `lp-docs-locator`               | 1     | Sonnet  | Read-only | Always (Wave 1)             |
| `lp-file-locator`               | 1     | inherit | Read-only | Always (Wave 1)             |
| `lp-code-analyzer`              | 1     | inherit | Read-only | Always (Wave 2)             |
| `lp-docs-analyzer`              | 1     | Sonnet  | Read-only | Always (Wave 2)             |
| `lp-web-researcher`             | 1     | inherit | Read-only | Unfamiliar tech involved    |
| `source-material-researcher` | 1     | Opus    | Read-only | Source document > 10 pages  |
| `fidelity-check`             | 5     | Sonnet  | Read-only | Skill built from source doc |
| `lp-skill-evaluator`            | 6     | Sonnet  | Read-only | Always                      |

**Wave 1 agents:** Never use the Read tool. Glob and Grep only. Fast and cheap.
**Wave 2 agents:** Use Read on targeted paths from Wave 1. Expensive -- precision matters.
**Opus agents:** Reserved for deep synthesis (source material distillation only).
