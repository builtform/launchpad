---
name: lp-hydrate
description: "Read and present the project backlog from BACKLOG.md as a session briefing"
---
# Hydrate — Session Briefing

Read `docs/tasks/BACKLOG.md` and present its contents to the user.

If BACKLOG.md does not exist, inform the user: "No backlog found. Run a workflow (/lp-harness-build, /lp-commit, or /lp-triage) to generate it."

This command is also triggered automatically at session start via the SessionStart hook. Use it manually to re-read the backlog mid-session.
