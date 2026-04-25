# Quality Gates — Recursive Evaluation Loop

This reference defines the evaluation protocol for validating skill quality. Run this loop after generating skill files. Do not ship a skill that has not passed all three evaluation passes.

---

## The Recursive Self-Improvement Loop

```
GENERATE skill files
    |
EVALUATE (3 passes: first-principles, baseline detection, Anthropic checklist)
    |
ALL PASS? --yes--> Ship
    | no
DIAGNOSE specific failures (explain WHY each failure occurred, not just that it failed)
    |
IMPROVE (rewrite targeting diagnosed weaknesses specifically)
    |
RE-EVALUATE (max 3 cycles)
    |
STILL FAILING? --> Present remaining issues to user
```

### Loop Rules

- Each cycle runs all three passes from scratch. Partial re-evaluation is not allowed.
- Diagnosis must explain WHY, not just WHAT. "Criterion 6 failed" is insufficient. "Criterion 6 failed because line 47 uses 'consider implementing' — replace with 'implement'" is required.
- Improvements must target diagnosed weaknesses specifically. Do not perform shotgun rewrites.
- After 3 cycles, remaining issues require human judgment. Present them with full context. Do not loop forever.
- The evaluator is a read-only documentarian. It reports findings. It does not make decisions or override the user.

---

## Pass 1 — First-Principles

Ask three questions. If any answer is "no," the skill fails this pass.

### 1. Does every component earn its place?

Walk through each file in the skill. For every file, state its purpose in one sentence. If you cannot, or if the purpose overlaps with another file, it has not earned its place.

### 2. Could you achieve the same result with fewer parts?

Identify the minimum set of files required to produce the skill's intended behavior. If the current file count exceeds that minimum, justify each extra file with a concrete capability it adds that no other file provides.

### 3. Is every reference file independently justified?

A reference file is justified when removing it would degrade the skill's output quality for its target task. If a reference file contains information that SKILL.md could inline without exceeding the 500-line limit, inline it and delete the reference file.

### First-Principles Evaluation Output

```
- [PASS/FAIL] Each component earns its place
- [PASS/FAIL] Cannot achieve same result with fewer parts
- [PASS/FAIL] Every reference file independently justified
- Evidence: [specific reasoning for each judgment]
```

---

## Pass 2 — Baseline Detection

This pass determines whether the skill produces output that differs meaningfully from what Claude generates without any skill loaded. A skill that merely reformats default behavior is not a skill — it is decoration.

### Detection Questions

**1. Does this look like what a default LLM would produce with no skill loaded?**

Take the skill's target task. Imagine prompting Claude with just the task description and no skill. Compare the expected output structure, depth, and reasoning steps. If they match, the skill fails.

**2. Does the thinking architecture encode a different reasoning process, or just format the same reasoning differently?**

Examine the skill's decision trees, phase structures, and conditional logic. A different format (numbered steps instead of paragraphs) with identical reasoning is not differentiation. A different reasoning sequence (evaluate before generating, constrain before expanding) is differentiation.

**3. Would removing the skill produce meaningfully worse output for the target task?**

Define "meaningfully worse" as: missing a specific output component, skipping a required validation step, or producing a qualitatively different (inferior) structure. Vague quality differences do not count.

### Baseline Red Flags

Check for these specific patterns that indicate a skill is baseline-equivalent:

- **Generic advice disguised as domain methodology.** Example: "Understand the requirements before implementing" repackaged as "Phase 1: Requirements Analysis."
- **Buzzword-heavy but action-light sections.** Sections that use domain terminology without encoding domain-specific decision logic.
- **"Steps" that reformat common sense.** Instructions that any competent developer would follow without the skill telling them to.

### Baseline Detection Evaluation Output

```
- [PASS/FAIL] Output differs structurally from default LLM behavior
- [PASS/FAIL] Thinking architecture encodes different reasoning process
- [PASS/FAIL] Removing skill produces meaningfully worse output
- Evidence: [specific examples of differentiation or lack thereof]
```

---

## Pass 3 — Anthropic Checklist

Ten criteria with binary pass/fail thresholds. No partial credit.

| #   | Criterion                | Pass Condition                                                                                                                 |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Frontmatter validity     | `name` is kebab-case, 64 chars max, no reserved words. `description` is third-person, 1024 chars max, includes trigger phrases |
| 2   | Body length              | SKILL.md is under 500 lines                                                                                                    |
| 3   | Reference depth          | One level from SKILL.md. No nested chains (reference files must NOT reference other reference files)                           |
| 4   | Progressive disclosure   | Explicit loading triggers ("Read X before Phase Y"), not vague ("check X if needed")                                           |
| 5   | Baseline differentiation | Output is structurally different from no-skill Claude. At least one reasoning step that Claude would not produce on its own    |
| 6   | No hedge language        | Zero instances of: "try to," "consider," "you might want to," "it may be helpful," "perhaps," "could potentially"              |
| 7   | Concrete examples        | At least 2 input/output examples somewhere in skill files                                                                      |
| 8   | Trigger precision        | Positive triggers AND negative boundaries (what the skill does NOT handle)                                                     |
| 9   | Verification gate        | Built-in quality check, checklist, or self-evaluation step                                                                     |
| 10  | Workflow completeness    | Every conditional path has a resolution. No "if X then TBD"                                                                    |

### Criterion Details

**1. Frontmatter validity.**
Validate the `name` field against kebab-case regex: `^[a-z][a-z0-9-]{0,63}$`. Scan `description` for at least one trigger phrase that tells Claude when to activate the skill.

**2. Body length.**
Count lines in SKILL.md. If the count exceeds 500, move content to reference files using progressive disclosure triggers.

**3. Reference depth.**
Grep every reference file for patterns that load other reference files (`Read `, `see `, `refer to `). Any match is a failure. Reference files are leaf nodes.

**4. Progressive disclosure.**
Search SKILL.md for every reference file mention. Each mention must include a conditional loading trigger that specifies WHEN to load it. Acceptable: "Read QUALITY-GATES.md before running evaluation." Unacceptable: "See QUALITY-GATES.md for details."

**5. Baseline differentiation.**
This criterion overlaps with Pass 2. If Pass 2 failed, this criterion automatically fails. If Pass 2 passed, confirm at least one reasoning step in the skill that Claude does not perform by default.

**6. No hedge language.**
Scan all skill files for the exact phrases: "try to," "consider," "you might want to," "it may be helpful," "perhaps," "could potentially." Any occurrence is a failure. Replace with direct imperatives.

**7. Concrete examples.**
Count input/output example pairs across all skill files. An example pair consists of a labeled input and its corresponding labeled output. Inline code snippets without input/output framing do not count.

**8. Trigger precision.**
Verify the skill defines both: (a) positive triggers — what tasks activate it, and (b) negative boundaries — what tasks it explicitly does not handle. Missing either is a failure.

**9. Verification gate.**
Confirm the skill includes at least one self-evaluation mechanism: a checklist the user runs against output, a validation step in the workflow, or a quality criteria table. The gate must be actionable, not aspirational.

**10. Workflow completeness.**
Trace every conditional branch in the skill ("if X," "when Y," "for Z cases"). Each branch must terminate in a concrete action or explicit delegation. Branches that end in "TBD," "handle as needed," or equivalent are failures.

### Anthropic Checklist Evaluation Output

```
- [PASS/FAIL] 1. Frontmatter validity
- [PASS/FAIL] 2. Body length (<500 lines)
- [PASS/FAIL] 3. Reference depth (single level)
- [PASS/FAIL] 4. Progressive disclosure
- [PASS/FAIL] 5. Baseline differentiation
- [PASS/FAIL] 6. No hedge language
- [PASS/FAIL] 7. Concrete examples (>=2)
- [PASS/FAIL] 8. Trigger precision
- [PASS/FAIL] 9. Verification gate
- [PASS/FAIL] 10. Workflow completeness
```

---

## Evaluation Report Format

Assemble the outputs from all three passes into a single report.

```
## Skill Evaluation Report: [skill-name]

### Pass 1: First-Principles
- [PASS/FAIL] Each component earns its place
- [PASS/FAIL] Cannot achieve same result with fewer parts
- [PASS/FAIL] Every reference file independently justified
- Evidence: [specific reasoning]

### Pass 2: Baseline Detection
- [PASS/FAIL] Output differs structurally from default LLM behavior
- [PASS/FAIL] Thinking architecture encodes different reasoning process
- [PASS/FAIL] Removing skill produces meaningfully worse output
- Evidence: [specific examples of differentiation or lack thereof]

### Pass 3: Anthropic Checklist
- [PASS/FAIL] 1. Frontmatter validity
- [PASS/FAIL] 2. Body length (<500 lines)
- [PASS/FAIL] 3. Reference depth (single level)
- [PASS/FAIL] 4. Progressive disclosure
- [PASS/FAIL] 5. Baseline differentiation
- [PASS/FAIL] 6. No hedge language
- [PASS/FAIL] 7. Concrete examples (>=2)
- [PASS/FAIL] 8. Trigger precision
- [PASS/FAIL] 9. Verification gate
- [PASS/FAIL] 10. Workflow completeness

### Failures (if any)
1. [Criterion]: [What failed] -> [Why it failed] -> [Specific fix instruction]

### Overall: PASS / FAIL (N/16 criteria met)
```

The total is 16 criteria: 3 from Pass 1, 3 from Pass 2, 10 from Pass 3. Criterion 5 in Pass 3 and the Pass 2 results are linked but counted separately — a skill can pass Pass 2 overall while failing the specific Anthropic threshold, or vice versa.

---

## Adversarial Pressure (Full Complexity Skills Only)

After Pass 3, apply these adversarial personas to stress-test the skill. This step is optional for Focused and Standard complexity skills. It is required for Full complexity skills.

### The Lazy User

Invoke the skill with minimal input — just the task name, no context, no preferences. Evaluate:

- Does the skill produce useful output, or does it stall waiting for information it should infer or prompt for?
- Are required inputs explicitly marked as required, with clear error messages when missing?

### The Edge Case User

Provide unusual or boundary inputs: empty strings, extremely long inputs, inputs in the wrong domain, inputs that match negative triggers. Evaluate:

- Does the skill handle edge cases gracefully, or does it produce broken output?
- Are negative boundaries enforced, or does the skill attempt to handle tasks outside its scope?

### The Impatient User

Skip all optional steps. Run only the mandatory workflow path. Evaluate:

- Does the core workflow still function end-to-end?
- Are optional steps clearly marked as optional, or does skipping them break downstream steps?

### Adversarial Pressure Output

```
### Adversarial Pressure
- Lazy User: [PASS/FAIL] — [evidence]
- Edge Case User: [PASS/FAIL] — [evidence]
- Impatient User: [PASS/FAIL] — [evidence]
```

---

## Failure Diagnosis Format

When a criterion fails, the diagnosis must follow this structure:

```
**Criterion [N]: [Name]**
- What failed: [Observable symptom]
- Why it failed: [Root cause in the skill files, with file name and line reference]
- Fix: [Exact change to make — not "improve this" but "replace line 47 'consider implementing X' with 'implement X'"]
```

Do not batch failures into vague summaries. Each failure gets its own diagnosis block. Each diagnosis names the file, the line, and the replacement text.

---

## Improvement Cycle Constraints

- **Cycle 1:** Address all diagnosed failures. Re-run all three passes.
- **Cycle 2:** Address remaining failures. If the same criterion fails twice, escalate: explain what was attempted and why it did not resolve the issue.
- **Cycle 3 (final):** Address remaining failures. If any criterion still fails, compile a report of unresolved issues with full context and present to the user for judgment.

Do not enter Cycle 2 if Cycle 1 resolved everything. Do not enter Cycle 3 if Cycle 2 resolved everything. Each cycle is expensive — run the minimum number required.
