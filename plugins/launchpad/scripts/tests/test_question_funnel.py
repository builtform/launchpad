"""Tests for lp_pick_stack.question_funnel (Phase 2 §4.1 Step 2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.question_funnel import (
    AnswerValidationError,
    MAX_DESCRIBE_CHARS,
    QUESTION_ENUMS,
    validate_answers,
)


VALID = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}


def test_validate_returns_dict_copy():
    out = validate_answers(VALID)
    assert out == VALID
    # mutating output does not mutate input
    out["Q1"] = "mobile-app"
    assert VALID["Q1"] == "static-site-or-blog"


def test_all_5_questions_have_enums():
    assert set(QUESTION_ENUMS.keys()) == {"Q1", "Q2", "Q3", "Q4", "Q5"}
    for q, enum in QUESTION_ENUMS.items():
        assert isinstance(enum, frozenset)
        assert len(enum) >= 3


def test_missing_question_raises():
    bad = {k: v for k, v in VALID.items() if k != "Q3"}
    with pytest.raises(AnswerValidationError) as exc:
        validate_answers(bad)
    assert "Q3" in str(exc.value)


def test_unknown_enum_value_raises():
    bad = dict(VALID, Q1="quantum-computer")
    with pytest.raises(AnswerValidationError) as exc:
        validate_answers(bad)
    assert "quantum-computer" in str(exc.value)


def test_non_str_value_raises():
    bad = dict(VALID, Q3=123)
    with pytest.raises(AnswerValidationError):
        validate_answers(bad)


def test_describe_required_when_q1_is_something_else():
    bad = dict(VALID, Q1="something-else-describe")
    with pytest.raises(AnswerValidationError) as exc:
        validate_answers(bad)
    assert "describe" in str(exc.value).lower()


def test_describe_optional_for_enum_q1():
    out = validate_answers(VALID)
    assert "describe" not in out


def test_describe_accepted_when_present():
    out = validate_answers(dict(VALID, describe="A static blog with TS islands"))
    assert out["describe"] == "A static blog with TS islands"


def test_describe_rejects_null_byte():
    bad = dict(VALID, describe="hello\x00world")
    with pytest.raises(AnswerValidationError) as exc:
        validate_answers(bad)
    assert "null byte" in str(exc.value)


def test_describe_rejects_overlong():
    too_long = "a" * (MAX_DESCRIBE_CHARS + 1)
    bad = dict(VALID, describe=too_long)
    with pytest.raises(AnswerValidationError) as exc:
        validate_answers(bad)
    assert "describe length" in str(exc.value)


def test_non_mapping_raises():
    with pytest.raises(AnswerValidationError):
        validate_answers("not a mapping")  # type: ignore[arg-type]


def test_q1_something_else_describe_with_describe_succeeds():
    out = validate_answers({**VALID, "Q1": "something-else-describe", "describe": "custom shape"})
    assert out["Q1"] == "something-else-describe"
    assert out["describe"] == "custom shape"


def test_field_name_attribute_on_error():
    bad = dict(VALID, Q1="bogus")
    with pytest.raises(AnswerValidationError) as exc:
        validate_answers(bad)
    assert exc.value.field_name == "Q1"
