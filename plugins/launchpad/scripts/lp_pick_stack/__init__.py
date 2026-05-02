"""lp_pick_stack package — owner of pick-stack-side primitives.

Inlines the manual-override `VALID_COMBINATIONS` frozenset of `(stack, role)`
tuples per HANDSHAKE §12 + pick-stack plan §3.4. NOT a separate YAML or .py
file: at 13 rules the file overhead doesn't earn its keep. Promote to a
separate module when the matrix exceeds ~30 rules; promote to YAML when the
rules need data-file editing without a Python diff.

The 13 tuples below cover all 10 stacks from the v2.0 catalog (HANDSHAKE §11)
at their canonical default role, plus dual-role variations for next/django/
rails (which ship both fullstack and backend-only personas). Multi-stack
combinations (frontend + backend polyglot, frontend-main + frontend-dashboard,
backend-managed + frontend) compose two valid singletons and are validated
by the pick-stack command's layer-set-validation logic, which lives later in
the pipeline and is gated by the matrix's cross-layer rules (single-role-
per-layer, fullstack-precludes-split, mobile-standalone, polyglot-allowed,
multi-frontend-allowed, backend-managed-pairing, path-uniqueness).

Constants exported: WRITTEN_DECISION_VERSION (writer-side §10 single source).
"""
from __future__ import annotations

# Decision-file version constant (§10 lifecycle bump list). Bumped from
# "0.x-test" to "1.0" in the coordinated v2.0.0 ship commit per HANDSHAKE
# §10. v2.1+ revisions follow the §10 forward-compat policy (BL-211).
WRITTEN_DECISION_VERSION = "1.0"

# 13 (stack, role) tuples — manual-override catalog. Covers all 10 stacks
# from the v2.0 catalog (HANDSHAKE §11) at their canonical default role,
# plus dual-role variations for stacks that ship both fullstack and
# backend-only personas (next, django, rails). Single-purpose stacks
# (astro, eleventy, hugo, hono, fastapi, supabase, expo) are pinned to
# their one valid role; cross-role tuples remain default-deny.
VALID_COMBINATIONS = frozenset({
    # Frontend (single-purpose) — base role
    ("astro", "frontend"),
    ("eleventy", "frontend"),
    ("hugo", "frontend"),
    # Multi-frontend variants — used by the multi-frontend category
    # (frontend-main + frontend-dashboard pairing). manual_override_resolver
    # already accepts these roles in ALLOWED_ROLES; tuples below close the
    # cross-check so users can manually re-create the multi-frontend shape
    # (PR #41 cycle 5 #4 + Greptile cycle-4 P1 closure).
    ("astro", "frontend-main"), ("astro", "frontend-dashboard"),
    ("eleventy", "frontend-main"), ("eleventy", "frontend-dashboard"),
    ("hugo", "frontend-main"), ("hugo", "frontend-dashboard"),
    ("next", "frontend-main"), ("next", "frontend-dashboard"),
    # Frontend or fullstack (next is the only TS framework with both modes)
    ("next", "frontend"),
    ("next", "fullstack"),
    # Backend (single-purpose)
    ("hono", "backend"),
    ("fastapi", "backend"),
    ("supabase", "backend-managed"),
    # Backend or fullstack (server-rendered frameworks with API-only mode)
    ("django", "backend"),
    ("django", "fullstack"),
    ("rails", "backend"),
    ("rails", "fullstack"),
    # Mobile (single-purpose)
    ("expo", "mobile"),
})


def is_valid_combination(stack: str, role: str) -> bool:
    """Return True if (stack, role) is in the manual-override catalog.

    Pure-CPU; no I/O. Multi-layer combination validation (polyglot,
    multi-frontend, backend-managed pairing) is the pick-stack command's
    job — this helper is the per-tuple base check that those rules
    compose on top of.
    """
    return (stack, role) in VALID_COMBINATIONS


__all__ = [
    "VALID_COMBINATIONS",
    "WRITTEN_DECISION_VERSION",
    "is_valid_combination",
]
