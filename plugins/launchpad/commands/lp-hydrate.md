---
name: lp-hydrate
description: "Read and present the project backlog from BACKLOG.md as a session briefing"
x-launchpad:
  schema-version: 1
  component-kind: command
  capabilities:
    required:
      - canonical_resource_read
      - explicit_invocation_provenance
      - installed_root_binding
      - interaction_mode_attestation
      - repository_read
      - structured_arguments
    mutation: none
    interaction: optional
    external-data-egress: false
    tool-profile: read_only
    fallback: inspect_only
---

# Hydrate — Session Briefing

Read `docs/tasks/BACKLOG.md` and present its contents to the user.

If BACKLOG.md does not exist, inform the user: "No backlog found. Run a workflow (/lp-build, /lp-commit, or /lp-triage) to generate it."

This command is also triggered automatically at session start via the SessionStart hook. Use it manually to re-read the backlog mid-session.
