# SKILL.md Annotated Template

<!-- HOW TO USE THIS TEMPLATE:
     Copy the template section below into a new SKILL.md file.
     Replace all {{placeholders}} with actual content.
     Delete all ANNOTATION comment blocks when done.
     Keep the final file under 500 lines. -->

> **Loaded when:** creating a new skill from scratch or reviewing an existing SKILL.md for structural compliance.

---

## Constraints

Before writing a SKILL.md, internalize these hard limits:

| Constraint                            | Threshold                         | Why                                                                                |
| ------------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------- |
| Max file length                       | 500 lines                         | Anthropic guidance — longer skills degrade Claude's attention                      |
| Target length for orchestrator skills | Under 400 lines                   | Deep knowledge lives in reference files, not in SKILL.md                           |
| Role of SKILL.md                      | ROUTER, not textbook              | It dispatches to reference files; it does not teach domain knowledge inline        |
| Frontmatter `name`                    | Kebab-case, max 64 characters     | Machine-parseable identifier; no spaces, no special chars                          |
| Frontmatter `description`             | Third-person, max 1024 characters | Must include trigger phrases at the end: `Triggers on: phrase1, phrase2, phrase3.` |
| Naming convention                     | Gerund preferred                  | e.g., `processing-pdfs`, `analyzing-spreadsheets`, `creating-skills`               |

### Frontmatter Rules

- `name` is the skill's machine ID. Use kebab-case, no more than 64 characters. Match the directory name.
- `description` is written in third person ("Generates a PRD...", not "Generate a PRD..."). It tells Claude WHEN to activate this skill. End with `Triggers on:` followed by 3-6 natural-language phrases a user would say.
- The description is a triggering mechanism, not documentation. Every word must earn its place.

---

## Template

Copy everything below this line into your new `SKILL.md` file.

---

```markdown
---
name: { { skill-name } }
description: "{{What it does in third person. When to use it. Triggers on: phrase1, phrase2, phrase3.}}"
---

# {{Skill Title}}

<!-- ANNOTATION: Place the most critical constraint FIRST. Recency bias means
     Claude pays sharpest attention to what it processed first and last.
     Make this a single bold line — unmissable. -->

**{{CRITICAL CONSTRAINT — e.g., "NEVER do X" or "ALWAYS do Y before anything else"}}**

---

## Trigger

This skill activates when: {{positive trigger conditions}}

**Examples:**

- "{{Example invocation 1}}"
- "{{Example invocation 2}}"
- "{{Example invocation 3}}"

## What This Skill Does NOT Handle

<!-- ANNOTATION: Negative boundaries are equally important as positive triggers.
     Without them, the skill activates on false positives. List 2-4 exclusions.
     Each exclusion must include a reason — naked bullet points get ignored. -->

- {{Explicit exclusion 1 — with reason why this is out of scope}}
- {{Explicit exclusion 2 — with reason why this belongs to a different skill or workflow}}

---

## The Job

<!-- ANNOTATION: 3-7 numbered steps. Each step MUST produce a visible output
     or concrete decision. "Understand the requirements" is NOT a step —
     Claude does this automatically. Start with the first non-obvious action.
     Use imperative verbs: "Generate", "Read", "Emit", "Validate". -->

1. {{Step producing visible output or artifact}}
2. {{Step producing visible output or artifact}}
3. {{Step producing visible output or artifact}}

---

## {{Primary Workflow Section}}

<!-- ANNOTATION: This is where domain-specific methodology lives.
     Use imperatives: "Do X" not "You might want to consider X."
     Reference files are loaded here with explicit triggers.
     Keep this section action-oriented — if it exceeds ~80 lines,
     move the detail into a reference file. -->

{{Instructions — specific, actionable, no hedge language}}

**Read [references/{{file}}.md](mdc:references/{{file}}.md) before proceeding to {{next section}}.**

<!-- ANNOTATION: The mdc: protocol loads a reference file into context.
     Only load reference files at the point where their content is needed,
     never at the top of the skill. This conserves context window. -->

---

## {{Additional Workflow Section}}

<!-- ANNOTATION: Add as many workflow sections as the skill requires.
     Each section should map to a distinct phase of the job.
     Name sections after what they DO, not what they ARE:
     "Generate Output" not "Output Section".
     Delete this section if The Job is simple enough to need only one. -->

{{Instructions for this phase}}

---

## Verification

<!-- ANNOTATION: This is the verification gate. It runs BEFORE delivering output.
     Every criterion must be pass/fail testable by Claude itself.
     "Output is good" is NOT a criterion. "Output contains no TODO placeholders" IS.
     Include 4-7 criteria. Always include the hedge-language check and
     the structural-difference check as the last two items. -->

Before delivering output:

- [ ] {{Concrete pass/fail criterion with specific threshold or check}}
- [ ] {{Concrete pass/fail criterion}}
- [ ] {{Concrete pass/fail criterion}}
- [ ] No hedge language in output ("try to," "consider," "you might want to")
- [ ] Output differs structurally from what Claude would produce without this skill

---

**{{CRITICAL CONSTRAINT — repeated at END for recency bias}}**

<!-- ANNOTATION: Repeat the same critical constraint from the top of the file.
     This exploits the primacy-recency effect: Claude attends most to
     the first and last things it reads. Bookending the constraint
     ensures it survives long context windows. -->
```

---

## Section-by-Section Rationale

| Section                      | Purpose                                      | Common Mistake                                                   |
| ---------------------------- | -------------------------------------------- | ---------------------------------------------------------------- |
| Frontmatter                  | Machine-parseable metadata + trigger phrases | Writing `name` with spaces or exceeding 64 chars                 |
| Critical Constraint (top)    | Primacy bias — first thing Claude reads      | Burying constraints in the middle of the file                    |
| Trigger                      | Positive activation conditions               | Listing too many triggers (causes false positives)               |
| Does NOT Handle              | Negative boundaries                          | Omitting this section entirely (causes scope creep)              |
| The Job                      | Ordered steps with visible outputs           | Including "understand X" as a step (Claude does this implicitly) |
| Workflow Sections            | Domain-specific methodology                  | Inlining 200+ lines instead of using reference files             |
| Verification                 | Pass/fail gate before output                 | Using subjective criteria ("looks good", "is clean")             |
| Critical Constraint (bottom) | Recency bias — last thing Claude reads       | Forgetting to repeat the constraint at the end                   |
