---
name: fixture-reviewer
description: Reviews the fixture's project-specific marker.
stack_scope: stack:any
tools: Read, Grep, Glob
model: inherit
---

# Fixture reviewer

Review only the changed files supplied in the task. If the added diff contains `FIXTURE_PROJECT_REVIEWER_FINDING`, return one P2 finding for its exact file and line, describing it as an unresolved fixture marker. If the marker is absent, return no finding. Do not modify files.
