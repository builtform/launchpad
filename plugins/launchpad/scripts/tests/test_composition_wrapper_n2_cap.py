"""Composition wrapper N=2 cap tests.

Phase 4 plan section 3.12 verbatim catalog: 3+-adapter selections rejected
with the verbatim message + the structured CompositionRejectionCode.
"""
from __future__ import annotations

import pytest

from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionRejectionCode,
    N2_CAP,
    compose,
    validate_pair,
)
from plugin_stack_adapters.astro import AstroAdapter
from plugin_stack_adapters.generic import GenericAdapter
from plugin_stack_adapters.nextjs_standalone import NextjsStandaloneAdapter


def test_n2_cap_constant_is_two():
    assert N2_CAP == 2


def test_validate_pair_rejects_three_adapter_selection():
    rejection = validate_pair(
        [NextjsStandaloneAdapter(), AstroAdapter(), GenericAdapter()]
    )
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.N2_CAP_EXCEEDED


def test_validate_pair_rejects_three_with_verbatim_message():
    rejection = validate_pair(
        [NextjsStandaloneAdapter(), AstroAdapter(), GenericAdapter()]
    )
    assert rejection is not None
    assert (
        rejection.message
        == "LaunchPad v2.1 supports up to 2 stacks per project. To request "
           "3-stack composition, open an issue with label v2.2-composition."
    )


def test_validate_pair_accepts_one_or_two_adapters():
    assert validate_pair([NextjsStandaloneAdapter()]) is None
    assert (
        validate_pair([NextjsStandaloneAdapter(), AstroAdapter()]) is None
    )


def test_compose_raises_composition_abort_error_on_three_adapter_selection(
    tmp_path
):
    with pytest.raises(CompositionAbortError) as exc:
        compose(
            [NextjsStandaloneAdapter(), AstroAdapter(), GenericAdapter()],
            tmp_path / "project",
        )
    assert exc.value.reason == CompositionRejectionCode.N2_CAP_EXCEEDED.value
    assert "3-stack composition" in exc.value.remediation


def test_validate_pair_rejects_zero_adapter_selection():
    rejection = validate_pair([])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.UNSUPPORTED_PAIR
