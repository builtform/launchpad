---
name: harness:kickoff
description: Meta-orchestrator for brainstorming. Loads brainstorming skill, facilitates open-ended dialogue, captures to docs/brainstorms/.
---

# /harness:kickoff

Meta-orchestrator for the brainstorming phase. Opens creative exploration before defining product scope.

---

## Step 1: Load Brainstorming Skill

Load the brainstorming skill to guide open-ended dialogue. If the skill is not available, proceed with general brainstorming guidance.

## Step 2: Open-Ended Dialogue

Facilitate open-ended exploration with the user:

- What problem are they solving?
- Who is the target user?
- What does success look like?
- What constraints exist (time, budget, tech)?
- What alternatives have they considered?

## Step 3: Capture Output

Save the brainstorm to `docs/brainstorms/YYYY-MM-DD-[topic].md` with:

- Key ideas discussed
- Decisions made
- Open questions
- Next steps

## Step 4: Transition

"Run `/harness:define` to define your product."
