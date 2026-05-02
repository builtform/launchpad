"""Tests for VALID_COMBINATIONS frozenset (HANDSHAKE §12 + pick-stack plan §3.4).

Per the pick-stack plan: ≥10 positive (allowed) + ≥10 negative (rejected)
known-answer fixtures. Removal of any negative test requires CODEOWNERS
approval (the negative cases encode the default-deny semantics).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack import (
    VALID_COMBINATIONS,
    WRITTEN_DECISION_VERSION,
    is_valid_combination,
)


# --- structural ---

def test_valid_combinations_is_frozenset():
    assert isinstance(VALID_COMBINATIONS, frozenset)


def test_valid_combinations_count_is_thirteen():
    """HANDSHAKE §12: 13 tuples (10 stacks at canonical role + 3 dual-role
    variations for next/django/rails); promote to YAML > ~30."""
    assert len(VALID_COMBINATIONS) == 13


def test_each_entry_is_string_tuple():
    for entry in VALID_COMBINATIONS:
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        stack, role = entry
        assert isinstance(stack, str)
        assert isinstance(role, str)


def test_decision_version_pinned_at_v2():
    """v2.0.0 ship pinned the decision-file version constant at "1.0" per
    HANDSHAKE §10 coordinated bump (was "0.x-test" during pre-ship dev)."""
    assert WRITTEN_DECISION_VERSION == "1.0"


# --- positive cases (allowed) ---

@pytest.mark.parametrize("stack,role", [
    ("astro", "frontend"),
    ("eleventy", "frontend"),
    ("hugo", "frontend"),
    ("next", "frontend"),
    ("next", "fullstack"),
    ("hono", "backend"),
    ("fastapi", "backend"),
    ("supabase", "backend-managed"),
    ("django", "backend"),
    ("django", "fullstack"),
    ("rails", "backend"),
    ("rails", "fullstack"),
    ("expo", "mobile"),
])
def test_allowed_combinations(stack: str, role: str):
    assert is_valid_combination(stack, role)
    assert (stack, role) in VALID_COMBINATIONS


def test_positive_count_meets_lower_bound():
    """Pick-stack plan: ≥10 positive cases. The 13 distinct allowed tuples
    exceed the lower bound; we exercise each."""
    cases = [
        ("astro", "frontend"),
        ("eleventy", "frontend"),
        ("hugo", "frontend"),
        ("next", "frontend"),
        ("next", "fullstack"),
        ("hono", "backend"),
        ("fastapi", "backend"),
        ("supabase", "backend-managed"),
        ("django", "backend"),
        ("django", "fullstack"),
        ("rails", "backend"),
        ("rails", "fullstack"),
        ("expo", "mobile"),
    ]
    assert len(cases) >= 10
    for stack, role in cases:
        assert is_valid_combination(stack, role)


# --- negative cases (rejected) ---

@pytest.mark.parametrize("stack,role", [
    # Wrong role for a single-purpose stack
    ("astro", "backend"),
    ("hono", "frontend"),
    ("fastapi", "fullstack"),
    ("expo", "frontend"),
    # Unknown stack
    ("svelte", "frontend"),
    ("phoenix-liveview", "fullstack"),  # deferred to v2.1 per BL-212
    ("convex", "backend-managed"),       # deferred to v2.1 per BL-212
    # Unknown role
    ("astro", "desktop"),
    ("next", "iot"),
    # Case mismatch (frozenset is case-sensitive)
    ("Astro", "frontend"),
    ("next", "Fullstack"),
    # Empty / nonsense
    ("", "frontend"),
    ("astro", ""),
])
def test_rejected_combinations(stack: str, role: str):
    """Default-deny: any combination not in VALID_COMBINATIONS is rejected."""
    assert not is_valid_combination(stack, role)


def test_negative_count_meets_lower_bound():
    """Pick-stack plan: ≥10 negative cases. Removal requires CODEOWNERS."""
    rejected = [
        ("astro", "backend"),
        ("hono", "frontend"),
        ("fastapi", "fullstack"),
        ("expo", "frontend"),
        ("svelte", "frontend"),
        ("phoenix-liveview", "fullstack"),
        ("convex", "backend-managed"),
        ("astro", "desktop"),
        ("next", "iot"),
        ("Astro", "frontend"),
        ("next", "Fullstack"),
        ("", "frontend"),
        ("astro", ""),
    ]
    assert len(rejected) >= 10
    for stack, role in rejected:
        assert not is_valid_combination(stack, role)
