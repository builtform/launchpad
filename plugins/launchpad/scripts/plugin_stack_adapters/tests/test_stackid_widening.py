"""StackId widening — Phase 0.5 §1.4 acceptance test.

Asserts the v2.0 10-entry catalog (HANDSHAKE §11) is reflected in the
`StackId` Literal. Fails closed if any catalog member is missing OR if a
stale entry from outside the catalog appears.

Cycle-3 expansion: 4 catalog-alias members (`next`, `django`, `hono`,
`supabase`) were added to StackId so receipt-driven `/lp-define` dispatch
never silently falls back to `generic` for a real catalog stack ID. This
test now expects 14 members total (4 v1.x + 6 new adapters + 4 aliases).
"""
from __future__ import annotations

from typing import get_args

from plugin_stack_adapters.contracts import StackId


# v2.0 14-stack StackId membership (HANDSHAKE §11 catalog + adapter aliases).
# Order does not matter (Literal argument set is a tuple but membership is
# what callers care about); we assert exact set-equality to fail-closed on
# stale or missing IDs.
EXPECTED_V20_STACKS = frozenset({
    # v1.x carry-over adapters
    "ts_monorepo", "python_django", "go_cli", "generic",
    # v2.0 stack-specific adapters (Phase 0.5 §1.4 widening)
    "astro", "fastapi", "rails", "hugo", "eleventy", "expo",
    # v2.0 catalog aliases (PR #41 cycle 3 #2 — receipt-dispatch coverage
    # for next/django/hono/supabase, which previously fell back to generic)
    "next", "django", "hono", "supabase",
})


def test_stackid_literal_member_count():
    args = get_args(StackId)
    assert len(args) == 14, f"expected 14 StackId members, got {len(args)}: {args}"


def test_stackid_contains_all_v20_catalog_entries():
    args = set(get_args(StackId))
    missing = EXPECTED_V20_STACKS - args
    extra = args - EXPECTED_V20_STACKS
    assert not missing, f"missing v2.0 catalog stacks: {sorted(missing)}"
    assert not extra, f"unexpected stacks in StackId: {sorted(extra)}"


def test_each_new_v20_stack_present():
    """Per Phase 0.5 acceptance: each new ID appears in StackId.__args__."""
    args = set(get_args(StackId))
    for new_id in (
        "astro", "fastapi", "rails", "hugo", "eleventy", "expo",
        "next", "django", "hono", "supabase",
    ):
        assert new_id in args, f"v2.0 widening missing stack: {new_id}"
