---
name: lp-harness-kickoff
description: Meta-orchestrator for brainstorming. Delegates to /lp-brainstorm for collaborative idea exploration, then hands off to /lp-harness-define.
---
# /lp-harness-kickoff

Meta-orchestrator for the brainstorming phase. Delegates to `/lp-brainstorm` for the actual brainstorming process.

---

## Step 1: Run /lp-brainstorm

Delegate to `/lp-brainstorm` — the brainstorm command handles:

- Loading the brainstorming skill
- Dispatching research agents when codebase exists
- Collaborative dialogue
- Design document capture to `docs/brainstorms/`
- Post-capture refinement via document-review skill

## Step 2: Transition

"Brainstorm captured. Run `/lp-harness-define` to define your product."
