---
name: lp-probe
description: Test-only command with namespaced LaunchPad metadata.
x-launchpad:
  schema-version: 1
  component-kind: command
  direct:
    skills:
      - lp-probe-explicit
  capabilities:
    mutation: none
    interaction: none
---

# Claude command metadata probe

Report `LP_SECTION1_CLAUDE_COMMAND_OK` and stop.
