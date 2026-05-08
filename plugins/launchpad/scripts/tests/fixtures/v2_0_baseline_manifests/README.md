# v2.0 baseline manifests (Phase 11 cross-version interop)

Frozen scaffold-decision payloads for the v2.0/v2.1 reader matrix per
Phase 11 plan §3.2 + DA2.

## Files

- `v2_0_scaffold_decision.json` -- sourced from `c563d81` (v2.0.0 ship)
  via `git show c563d81:plugins/launchpad/scripts/tests/fixtures/scaffold_decision_valid_minimal.json`.
  Carries the v2.0 envelope shape: `version: "1.0"`, no `schema_version`,
  no `identity`, no `plugin_version`, no `stacks`.
- `v2_1_scaffold_decision.json` -- synthesized at Phase 11 Slice A via
  `lp_pick_stack.decision_writer.build_decision_payload` shape +
  `decision_integrity.canonical_hash` seal. Carries the v2.1 envelope:
  `version: "1.0"`, `schema_version: "1.1"`, `identity` (all-placeholder),
  `plugin_version: "2.1.0"`, `stacks: ["astro"]`.

## Why frozen in-tree (not loaded via `git show <sha>` at runtime)

Per Phase 11 plan D1 (LOCKED): shell-at-runtime loading is novel and
hurts test reproducibility. Existing fixtures pattern (committed under
`tests/fixtures/`) is the precedent.

## Cross-version reader matrix

The `test_cross_version_interop.py` harness exercises 4 cells using
these fixtures:

| #   | Reader      | Manifest      | Expected                                      |
| --- | ----------- | ------------- | --------------------------------------------- |
| 1   | v2.0 reader | v2.0 manifest | success (legacy 1.0 envelope)                 |
| 2   | v2.0 reader | v2.1 manifest | forward-compat: ignore unknown OR error       |
| 3   | v2.1 reader | v2.0 manifest | backward-compat: success via legacy migration |
| 4   | v2.1 reader | v2.1 manifest | round-trip success                            |

"v2.0 reader" is simulated via the v1.0-envelope detection codepath
(`_is_legacy_1_0_envelope`); subprocess-spawn against `c563d81` is
infeasible in the test runtime per R1.
