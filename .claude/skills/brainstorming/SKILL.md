---
name: brainstorming
description: "Process skill for structured brainstorming sessions. Guides collaborative idea exploration through progressive questioning, approach comparison, and design document capture. Loaded by /brainstorm and /harness:kickoff."
---

# Brainstorming Skill

## When to Brainstorm vs Skip

- **Clear:** explicit acceptance criteria, specific tech requirements → skip brainstorming, go straight to planning
- **Unclear:** "make it better", "improve performance", no success criteria → brainstorm first

## Question Techniques

- One at a time (NEVER batch 5 questions)
- Prefer multiple choice over open-ended when possible
- Start broad ("what problem?"), narrow progressively ("which users specifically?")
- Validate assumptions explicitly ("you mentioned X — does that mean Y?")
- Ask about success criteria early ("how will we know this worked?")

### Key Topics to Cover

| Topic             | Purpose              | Example Question                                        |
| ----------------- | -------------------- | ------------------------------------------------------- |
| Purpose           | Why build this?      | "What problem does this solve for users?"               |
| Users             | Who benefits?        | "Who are the primary users? How do they discover this?" |
| Constraints       | What limits exist?   | "Any budget, timeline, or tech constraints?"            |
| Success           | How to measure?      | "What measurable outcome means this succeeded?"         |
| Edge Cases        | What could go wrong? | "What happens when X fails or is unavailable?"          |
| Existing Patterns | What exists already? | "Are there similar features we can model after?"        |

## Approach Exploration

- 2-3 approaches, each with: Name, Description, Pros, Cons, "Best When"
- Lead with recommendation and explain why
- Apply YAGNI: simplest approach that meets requirements wins

## Design Document Template

Output to: `docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md`

Sections:

1. **What We're Building** — Problem statement, target users, success criteria
2. **Why This Approach** — Chosen approach and rationale
3. **Key Decisions** — Decisions made during brainstorm with rationale
4. **Open Questions** — Unresolved items that need further investigation
5. **Next Steps** — Concrete next actions

## YAGNI Principles

- Don't design for hypothetical scale
- Don't add config when one value works
- Don't abstract before 3 instances
- Don't build features nobody asked for
- Don't over-specify implementation details

## Anti-Patterns

| Anti-Pattern                | Better Approach                  |
| --------------------------- | -------------------------------- |
| Asking 5 questions at once  | Ask one at a time                |
| Jumping to solution         | Understand the problem first     |
| Ignoring constraints        | Ask about budget, timeline, team |
| Skipping success criteria   | Define "done" before starting    |
| Over-engineering brainstorm | It's a brainstorm, not a spec    |
| Not capturing decisions     | Write it down before moving on   |

## Integration

- Brainstorm = WHAT (problem space)
- Plan = HOW (solution space)
- When brainstorm output exists, `/define-product` uses it as context
- Research agents (`code-analyzer`, `pattern-finder`) replace CE's `repo-research-analyst`
- Canonical handoff: `/harness:define`
