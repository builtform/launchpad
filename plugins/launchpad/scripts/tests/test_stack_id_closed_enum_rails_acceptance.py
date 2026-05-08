"""Phase 6 v2.1 -- rails IS in STACK_ID_ACTIVE_ENUM (companion to
test_stack_id_closed_enum.py whose rails-REJECTION assertion was deleted).

Phoenix is the new canary for v2.2 composite stacks (per V3 §8.4): NOT
shipped in v2.1, MUST raise StackIdInvalidError until then.
"""
from __future__ import annotations

import pytest

from plugin_default_generators._renderer_base import (
    STACK_ID_ACTIVE_ENUM,
    StackIdInvalidError,
    validate_stack_id,
)


def test_rails_is_active_enum_member():
    assert "rails" in STACK_ID_ACTIVE_ENUM
    assert validate_stack_id("rails") == "rails"


def test_phoenix_remains_rejected_as_v22_canary():
    # phoenix is a planned v2.2 composite stack; until v2.2 ships, it MUST
    # raise StackIdInvalidError (closed-enum gate).
    with pytest.raises(StackIdInvalidError) as exc:
        validate_stack_id("phoenix")
    assert "phoenix" in str(exc.value)
