---
name: lp-brainstorm
description: Collaborative brainstorming with codebase research, structured dialogue, and design document capture. NEVER writes code.
---

# /lp-brainstorm

Collaborative brainstorming command. Explores ideas, generates approaches, and captures design documents.

**Arguments:** `$ARGUMENTS` (optional topic)

---

## Phase 0: Assess Clarity

- IF requirement is already clear and specific: skip to Phase 2
- IF vague or exploratory: proceed to Phase 1

## Phase 1: Understand the Idea

1. Load brainstorming skill (process knowledge)
2. IF codebase exists (package.json or similar detected):
   - Dispatch `lp-code-analyzer` + `lp-pattern-finder` in parallel (lightweight repo scan)
   - Research agents MAY read schemas, routes, configs to verify infrastructure claims
   - Prevents stating "table X does not exist" without checking
3. Collaborative dialogue:
   - One question at a time (NEVER batch)
   - Start broad, narrow progressively
   - Cover: Purpose, Users, Constraints, Success Criteria, Edge Cases, Existing Patterns
4. Unverified claims MUST be labeled as assumptions:
   "Assumption: no existing payments table" (not "there is no payments table")
5. NEVER write code — explore and document decisions only

## Phase 2: Explore Approaches

- Present 2-3 concrete approaches
- Each: Name, Description, Pros, Cons, "Best When"
- Lead with recommendation
- Apply YAGNI: simplest approach that meets requirements

## Phase 3: Capture Design Document

1. BEFORE writing: scan for unverified absence claims ("does not exist", "no current", "there is no") — verify or relabel as "Assumption: ..."
2. Scan capture for PII and secrets (email, phone, API keys, tokens, connection strings, internal URLs, real customer data) — replace with anonymized placeholders
3. Topic slug: lowercase, hyphens only, strip special characters, max 50 chars
4. Run `mkdir -p docs/brainstorms/` before writing
5. Write to: `docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md`
6. Template sections:
   - What We're Building
   - Why This Approach
   - Key Decisions
   - Open Questions
   - Next Steps

## Phase 4: Refine + Handoff

1. Load document-review skill
2. Offer refinement pass (max 2 passes, then recommend completion)
3. Handoff options:
   - a) "Review and refine further" (re-enter document-review)
   - b) "Proceed to planning" → "Run /lp-define"
   - c) "Ask more questions" (re-enter Phase 1)
   - d) "Done for now"

---

## Strict Rules

- NEVER write code — brainstorm is about ideas, not implementation
- One question at a time — never dump 5 questions
- Always capture before handoff — no lost brainstorms
- Research agents are optional — skip if no codebase exists
