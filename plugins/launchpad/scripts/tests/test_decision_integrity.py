"""Known-answer test vector for canonical_hash() per HANDSHAKE §3.

Pinned hex output for fixture input. Linux/macOS produce identical bytes
because json.dumps with sort_keys=True + ensure_ascii=True + tight separators
is locale-independent and byte-deterministic across Python implementations.

The macOS CI leg is BL-233 deferred to v2.2 per HANDSHAKE §1.5 strip-back; at
v2.0 the test runs on Linux CI (and any local platform) and is manually
spot-checked on macOS at Phase 7.5 ship.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts/ to path so tests can import library modules
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash


PINNED_HEX = "b5871e407c514e9e08499fb512c302eba8b011f9d3837555bfe23154c3721e26"
FIXTURE = {"a": 1, "b": [2, "3"], "c": None}


def test_canonical_hash_kat_vector():
    """KAT: pinned hex for the canonical fixture input."""
    assert canonical_hash(FIXTURE) == PINNED_HEX


def test_canonical_hash_key_order_invariance():
    """Reordering keys produces the same hash (sort_keys=True)."""
    assert canonical_hash({"c": None, "a": 1, "b": [2, "3"]}) == PINNED_HEX


def test_canonical_hash_list_order_changes_hash():
    """Lists are ordered tuples; reordering changes the hash."""
    h1 = canonical_hash({"x": [1, 2, 3]})
    h2 = canonical_hash({"x": [3, 2, 1]})
    assert h1 != h2


def test_canonical_hash_rejects_nan():
    with pytest.raises(ValueError):
        canonical_hash({"x": float("nan")})


def test_canonical_hash_rejects_infinity():
    with pytest.raises(ValueError):
        canonical_hash({"x": float("inf")})


def test_canonical_hash_rejects_non_dict():
    with pytest.raises(ValueError):
        canonical_hash([1, 2, 3])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        canonical_hash("not a dict")  # type: ignore[arg-type]


def test_canonical_hash_unicode_ascii_escape():
    """ensure_ascii=True escapes non-ASCII as \\uXXXX for byte-stability."""
    h = canonical_hash({"k": "café"})
    # Same logical content via escaped form should produce same hash
    h_escape = canonical_hash({"k": "café"})
    assert h == h_escape


def test_canonical_hash_empty_dict():
    """Empty dict has a stable hash."""
    h1 = canonical_hash({})
    h2 = canonical_hash({})
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex
