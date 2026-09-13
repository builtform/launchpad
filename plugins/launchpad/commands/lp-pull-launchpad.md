---
description: Decommissioned in v2.1
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

This command was removed in v2.1. Use `claude /plugin update launchpad` to sync from marketplace; pin to v2.0.x with `git checkout v2.0.x` for legacy behavior. See `CHANGELOG.md` (v2.1.0) and `docs/maintainers/decommission-history.md`.
