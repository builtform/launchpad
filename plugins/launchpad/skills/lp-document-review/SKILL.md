---
name: lp-document-review
description: "Process skill for reviewing and refining brainstorm or plan documents. 6-step assessment with 4 quality criteria and 2-pass recommendation. Loaded by /lp-brainstorm and /lp-harden-plan."
---

# Document Review Skill

## When to Use

Use to refine brainstorm or plan documents before proceeding to the next workflow step.

## 6-Step Review Process

### Step 1: Get the Document

Accept path or read from context.

### Step 2: Assess (5 Questions)

1. Is anything unclear or ambiguous?
2. Is anything unnecessary?
3. Is a decision being avoided?
4. Are there unstated assumptions?
5. Is there scope creep?

### Step 3: Evaluate (4 Criteria)

1. **Clarity** — Can someone unfamiliar execute on this?
2. **Completeness** — Are all necessary details present?
3. **Specificity** — Are requirements concrete enough to implement?
4. **YAGNI** — Is everything here actually needed for the next step?

### Step 4: Identify Critical Improvement

What single change would most improve this document?

### Step 5: Make Changes

- **Auto-fix:** typos, formatting, minor ambiguities. Log a summary of auto-fixes so the user can verify nothing substantive was silently changed.
- **Ask approval:** substantive changes (scope, requirements, approach)

### Step 6: Offer Next Action

- "Refine again" or "Review complete"
- After 2 passes: recommend completion (diminishing returns)

## Simplification Guidance

**SIMPLIFY** when content:

- Serves hypothetical future needs
- Repeats information already stated
- Exceeds what's needed for the next step
- Adds overhead without adding clarity

**DO NOT SIMPLIFY:**

- Constraints and limitations
- Rationale for rejected alternatives
- Unresolved questions
- Integration requirements

## Rules

- Don't rewrite the entire document
- Don't add new sections or requirements
- Don't over-engineer the review
- Don't create separate review files
