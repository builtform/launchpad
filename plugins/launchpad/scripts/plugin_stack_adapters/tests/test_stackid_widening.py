"""StackId widening — Phase 0.5 §1.4 acceptance test.

Asserts the v2.0 10-entry catalog (HANDSHAKE §11) is reflected in the
`StackId` Literal. Fails closed if any catalog member is missing OR if a
stale entry from outside the catalog appears.
"""
from __future__ import annotations

from typing import get_args

from plugin_stack_adapters.contracts import StackId


# v2.0 10-stack catalog per HANDSHAKE §11. Order does not matter (Literal
# argument set is a tuple but membership is what callers care about); but
# we assert exact set-equality to fail-closed on stale or missing IDs.
EXPECTED_V20_STACKS = frozenset({
    "ts_monorepo", "python_django", "go_cli", "generic",  # v1.x carry-over
    "astro", "fastapi", "rails", "hugo", "eleventy", "expo",  # v2.0 widening
})


def test_stackid_literal_member_count():
    args = get_args(StackId)
    assert len(args) == 10, f"expected 10 StackId members, got {len(args)}: {args}"


def test_stackid_contains_all_v20_catalog_entries():
    args = set(get_args(StackId))
    missing = EXPECTED_V20_STACKS - args
    extra = args - EXPECTED_V20_STACKS
    assert not missing, f"missing v2.0 catalog stacks: {sorted(missing)}"
    assert not extra, f"unexpected stacks in StackId: {sorted(extra)}"


def test_each_new_v20_stack_present():
    """Per Phase 0.5 acceptance: each new ID appears in StackId.__args__."""
    args = set(get_args(StackId))
    for new_id in ("astro", "fastapi", "rails", "hugo", "eleventy", "expo"):
        assert new_id in args, f"v2.0 widening missing stack: {new_id}"
