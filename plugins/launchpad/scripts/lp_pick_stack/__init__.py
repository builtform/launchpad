"""lp_pick_stack package — owner of pick-stack-side primitives.

Inlines the manual-override `VALID_COMBINATIONS` frozenset of `(stack, role)`
tuples per HANDSHAKE §12 + pick-stack plan §3.4. NOT a separate YAML or .py
file: at 7 rules the file overhead doesn't earn its keep. Promote to a
separate module when the matrix exceeds ~30 rules; promote to YAML when the
rules need data-file editing without a Python diff.

The 7 tuples below cover the v2.0 10-stack catalog's primary single-stack
default-role combinations. Multi-stack combinations (frontend + backend
polyglot, frontend-main + frontend-dashboard, backend-managed + frontend)
compose two valid singletons and are validated by the pick-stack command's
layer-set-validation logic, which lives later in the pipeline and is
gated by the matrix's cross-layer rules (single-role-per-layer, fullstack-
precludes-split, mobile-standalone, polyglot-allowed, multi-frontend-allowed,
backend-managed-pairing, path-uniqueness).

Constants exported: WRITTEN_DECISION_VERSION (writer-side §10 single source).
"""
from __future__ import annotations

# Decision-file version constant (§10 lifecycle bump list). Bumped from
# "0.x-test" to "1.0" in the coordinated v2.0.0 ship commit per HANDSHAKE
# §10. v2.1+ revisions follow the §10 forward-compat policy (BL-211).
WRITTEN_DECISION_VERSION = "1.0"

# 7 (stack, role) tuples — manual-override catalog. Each tuple represents a
# stack + its primary default role per the v2.0 10-stack catalog
# (HANDSHAKE §11). next/rails/django/supabase/eleventy/hugo combinations
# beyond their default role compose via the multi-stack rules in the manual-
# override matrix (pick-stack plan §3.4).
VALID_COMBINATIONS = frozenset({
    ("astro", "frontend"),
    ("next", "fullstack"),
    ("hono", "backend"),
    ("fastapi", "backend"),
    ("django", "fullstack"),
    ("rails", "fullstack"),
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
