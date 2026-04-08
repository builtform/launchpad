---
name: harness:kickoff
description: Meta-orchestrator for brainstorming. Delegates to /brainstorm for collaborative idea exploration, then hands off to /harness:define.
---

# /harness:kickoff

Meta-orchestrator for the brainstorming phase. Delegates to `/brainstorm` for the actual brainstorming process.

---

## Step 1: Run /brainstorm

Delegate to `/brainstorm` — the brainstorm command handles:

- Loading the brainstorming skill
- Dispatching research agents when codebase exists
- Collaborative dialogue
- Design document capture to `docs/brainstorms/`
- Post-capture refinement via document-review skill

## Step 2: Transition

"Brainstorm captured. Run `/harness:define` to define your product."
