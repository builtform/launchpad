"""Phase 4 v2.1 (Slice F) closed-enum gate tests.

Phase 4 plan section 3.11: any non-enum stack_id MUST raise
StackIdInvalidError BEFORE renderer entry. The closed-enum guarantee is
what prevents a hostile or stale stack_id from triggering a path traversal
in the stack-aware fragment loader.
"""
from __future__ import annotations

import pytest

from plugin_default_generators._renderer_base import (
    STACK_ID_ACTIVE_ENUM,
    StackIdInvalidError,
    validate_stack_id,
)


def test_active_enum_contains_exactly_eleven_v21_stack_ids():
    # Phase 7 v2.1 (DA5): reconciled to V3 §8.1 union of StackIdActive (5) and
    # StackIdV22Candidate (5). Renderer accepts the union; adapter dispatch
    # routes candidate ids without an active Adapter Protocol implementation
    # via `generic`. Companion partition guard lives in
    # tests/test_stack_coupling_refactors.py.
    #
    # v2.1.6 BL-345 review fix (Codex P1 #2 + Greptile #2): `go_cli`
    # widened from 10 → 11. The detector has been emitting `go_cli` since
    # v2.0 with a real `go_cli.py` adapter module-level `run()`, but it
    # was missing from the active enum; the v2.1.6 stack-aware data
    # modules (_package_managers / _structure_allowlists /
    # _ignore_patterns) gained Go entries, and listing the id in the
    # active enum lets the data-shape invariant tests cover it without
    # special-casing.
    assert STACK_ID_ACTIVE_ENUM == frozenset({
        "ts_monorepo",
        "nextjs_standalone",
        "nextjs_fastapi",
        "astro",
        "generic",
        "python_django",
        "python_generic",
        "nextjs_hono_cloudflare",
        "nextjs_trpc_prisma",
        "rails",
        "go_cli",
    })


def test_validate_stack_id_accepts_each_active_member():
    for sid in STACK_ID_ACTIVE_ENUM:
        assert validate_stack_id(sid) == sid


# Phase 6 v2.1: rails-rejection assertion REMOVED; rails is now an active
# enum member. Rejection is reframed as a phoenix canary in
# test_stack_id_closed_enum_rails_acceptance.py.


def test_validate_stack_id_rejects_path_traversal_attempt():
    # The closed-enum gate is a security boundary: a hostile stack_id
    # carrying ".." should never reach the fragment loader.
    with pytest.raises(StackIdInvalidError):
        validate_stack_id("../../../etc/passwd")


def test_validate_stack_id_rejects_empty_string():
    with pytest.raises(StackIdInvalidError):
        validate_stack_id("")
