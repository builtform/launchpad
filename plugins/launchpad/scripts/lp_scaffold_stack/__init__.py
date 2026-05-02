"""lp_scaffold_stack package — owner of /lp-scaffold-stack consumer-side primitives.

This package implements Phase 3 of the v2.0 pipeline: validates the
`scaffold-decision.json` produced by `/lp-pick-stack`, materializes layers via
`scaffolders.yml`, manages the nonce ledger, writes `scaffold-receipt.json`
for `/lp-define`, and emits forensic artifacts on rejection or partial-failure.

Per HANDSHAKE §1.5 strip-back:

- Rule 12 (`brainstorm_session_id`) is BL-235 deferred — DO NOT validate.
- Marker consumption is simple `os.rename` (no JSON envelope, no sha256, no
  bound_cwd, no `.first-run-marker.lock`) per BL-235.
- `recovery_commands` runtime enforcement is BL-231 deferred — Phase 3 EMITS
  the structured array as forward-compat hint; Phase 3 does NOT enforce
  closed-enum / denylist / idempotency / sha256-self-hash / .recovery.lock /
  at-most-one-rerun rules at runtime. Write-time destructive-path denylist
  DOES apply (refuses to WRITE entries with forbidden paths, but doesn't
  enforce on read).
- Forensic surfaces (scaffold-rejection-<ts>.jsonl, scaffold-failed-<ts>.json)
  are written INLINE without `forensic_writer.py` indirection (BL-223).

Constants exported: WRITTEN_RECEIPT_VERSION (writer-side single source);
EXPECTED_DECISION_VERSION (read-side strict-equality frozenset).
"""
from __future__ import annotations

# Decision-file version constant accepted by /lp-scaffold-stack consumers.
# Bumped from "0.x-test" to "1.0" in the coordinated v2.0.0 ship commit per
# HANDSHAKE §10. Strict-equality per HANDSHAKE §10 forward-compat policy
# DEFERRED to v2.2 (BL-211).
EXPECTED_DECISION_VERSION = frozenset({"1.0"})

# Receipt-file version constant the consumer writes. Coordinated bump with
# the decision version at v2.0.0 ship per HANDSHAKE §10.
WRITTEN_RECEIPT_VERSION = "1.0"

# Count of `docs/architecture/*` outputs the doc generator emits — single
# source for the Tier 1 reveal panel. Per PR #41 cycle 8 #2 closure: this
# was hardcoded as 8 in the original BL-217 placeholder, but the generator
# emits only 4 docs/architecture/* outputs (PRD, TECH_STACK,
# BACKEND_STRUCTURE, APP_FLOW). The receipt and panel now reflect reality.
# Counted by hand here to avoid an import cycle from the generator side
# (generator imports adapters which would need this constant).
TIER1_ARCHITECTURE_DOCS_RENDERED = 4


__all__ = [
    "EXPECTED_DECISION_VERSION",
    "TIER1_ARCHITECTURE_DOCS_RENDERED",
    "WRITTEN_RECEIPT_VERSION",
]
