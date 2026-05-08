"""Phase 7 v2.1 -- Tier-1 stack-coupling refactor tests.

Eight tests covering DA1-DA6 commitments (DA7 N/A by design; DA8 gated by
CODEOWNERS + invariant test #4):

  1. StackIdActive Literal exact membership (5 ids -- DA1)
  2. StackIdV22Candidate Literal exact membership (5 ids -- DA2)
  3. StackIdActive ∩ StackIdV22Candidate disjoint
  4. STACK_ID_ACTIVE_ENUM partition invariant (DA5 -- union equality +
     active/candidate disjoint subsets)
  5. Path-traversal stack_id rejected + verbatim threat-model comment pin
     (Security S1 + S2)
  6. Legacy adapter modules (hugo/eleventy/expo/fastapi) still importable
     (DA6 non-regression guard -- Spec-flow P2-A)
  7. StackIdLegacy NOT importable from contracts (DA4 deferral guard --
     Spec-flow P2-B)
  8. StackId v2.0 14-id catalog preserved (DA3 guard -- Spec-flow P2-C)
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import get_args

import pytest

from plugin_default_generators._renderer_base import (
    STACK_ID_ACTIVE_ENUM,
    StackIdInvalidError,
    validate_stack_id,
)
from plugin_stack_adapters.contracts import (
    StackId,
    StackIdActive,
    StackIdV22Candidate,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
RENDERER_BASE = (
    REPO_ROOT
    / "plugins"
    / "launchpad"
    / "scripts"
    / "plugin_default_generators"
    / "_renderer_base.py"
)


def test_stackid_active_exact_membership():
    """DA1: StackIdActive Literal carries exactly the 5 v2.1 active ids."""
    assert set(get_args(StackIdActive)) == {
        "ts_monorepo",
        "nextjs_standalone",
        "nextjs_fastapi",
        "astro",
        "generic",
    }


def test_stackid_v22_candidate_exact_membership():
    """DA2: StackIdV22Candidate Literal carries exactly the 5 V3 §8.1 ids."""
    assert set(get_args(StackIdV22Candidate)) == {
        "python_django",
        "python_generic",
        "nextjs_hono_cloudflare",
        "nextjs_trpc_prisma",
        "rails",
    }


def test_stackid_active_v22_candidate_disjoint():
    """V3 §8.1 design: active and candidate are disjoint subsets of the
    reconciled enum."""
    active = set(get_args(StackIdActive))
    candidate = set(get_args(StackIdV22Candidate))
    assert active & candidate == set(), (
        f"StackIdActive ∩ StackIdV22Candidate must be empty; overlap: "
        f"{active & candidate}"
    )


def test_stack_id_active_enum_partition_invariant():
    """DA5: STACK_ID_ACTIVE_ENUM == StackIdActive | StackIdV22Candidate AND
    StackIdActive & StackIdV22Candidate == ∅ (partition).

    Combined invariant catches BOTH drift (deletion / silent widening) AND
    silent active↔candidate reclassification (Adversarial #3)."""
    active = frozenset(get_args(StackIdActive))
    candidate = frozenset(get_args(StackIdV22Candidate))
    assert STACK_ID_ACTIVE_ENUM == active | candidate, (
        f"STACK_ID_ACTIVE_ENUM drift: enum={STACK_ID_ACTIVE_ENUM} vs "
        f"active|candidate={active | candidate}"
    )
    assert active & candidate == frozenset(), (
        f"Partition disjointness violated: overlap={active & candidate}"
    )


def test_path_traversal_stack_id_rejected():
    """Security S1: path-traversal-shaped stack_id rejected by closed-enum
    gate. Security S2: verbatim threat-model comment preserved at
    `_renderer_base.py:75-79`.

    Dot count matches `test_stack_id_closed_enum.py:46` precedent."""
    with pytest.raises(StackIdInvalidError):
        validate_stack_id("../../../etc/passwd")
    text = RENDERER_BASE.read_text(encoding="utf-8")
    assert "attacker-controlled path traversal" in text, (
        "Phase 7 plan Security S2 invariant violated: the verbatim "
        "'attacker-controlled path traversal' threat-model sentence at "
        "_renderer_base.py:75-79 must be preserved."
    )


def test_legacy_adapter_modules_still_importable():
    """DA6 non-regression: hugo/eleventy/expo/fastapi adapter modules ship
    working AdapterOutput modules; deletion is deferred to v2.2 BL."""
    for name in ("hugo_adapter", "eleventy_adapter", "expo_adapter", "fastapi_adapter"):
        mod = importlib.import_module(f"plugin_stack_adapters.{name}")
        assert mod is not None, f"plugin_stack_adapters.{name} failed import"


def test_stackidlegacy_not_importable():
    """DA4 deferral: StackIdLegacy is v2.2 BL surface; v2.1 must NOT export
    it. v2.2 BL plan-author flips this test (delete + add new
    `test_stackidlegacy_exact_membership`) when introducing the alias."""
    from plugin_stack_adapters import contracts as _contracts

    assert not hasattr(_contracts, "StackIdLegacy"), (
        "DA4 deferral guard violated: StackIdLegacy must not exist on "
        "plugin_stack_adapters.contracts in v2.1; defer to v2.2 BL bundle."
    )


def test_stackid_14id_catalog_preserved():
    """DA3 guard: v2.0 14-id detection catalog preserved against accidental
    narrowing. V3 §8.1 narrowing to active|candidate deferred to v2.2 BL
    per §3.0 D1."""
    assert len(get_args(StackId)) == 14
