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


def test_active_enum_contains_exactly_six_v21_stack_ids():
    # Phase 6 v2.1: `rails` added as detector groundwork (no Rails-specific
    # reviewer in v2.1; framework-axis + Rails reviewers arrive in v2.2 BL).
    assert STACK_ID_ACTIVE_ENUM == frozenset({
        "ts_monorepo",
        "nextjs_standalone",
        "nextjs_fastapi",
        "astro",
        "generic",
        "rails",
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
