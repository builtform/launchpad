---
name: lp-probe
description: Test-only agent with namespaced LaunchPad metadata.
tools: Read
x-launchpad:
  schema-version: 1
  component-kind: agent
  capabilities:
    mutation: none
    interaction: none
---

# Claude agent metadata probe

Report `LP_SECTION1_CLAUDE_AGENT_OK` and stop.
