"""D3 regression-shield (v2.1.1 Phase 4): rationale_renderer default
fallback bullet length pin.

Per BL-236 D-verdict D3: the `alternatives` and `notes` default fallback
bullets at lp_pick_stack/rationale_renderer.py are just above the 30-char
minimum required by HANDSHAKE §4 rule 7 (ambiguity-cluster validator).
Future shortening would silently break the validator's "≥1 non-empty
bullet ≥30 chars" rule. This test pins the invariant.
"""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ on sys.path for sibling-module imports.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack import rationale_renderer  # noqa: E402
from lp_pick_stack.matcher import MatchCandidate  # noqa: E402

MIN_BULLET_CHARS = 30


def _make_match():
    return MatchCandidate(
        id="cat",
        name="Test",
        score=1,
        canonical_stack=({"stack": "ts_monorepo", "role": "primary", "path": "."},),
        explanation="Test category",
        cluster=None,
    )


def test_render_rationale_default_alternatives_bullet_meets_min_length():
    """Default `alternatives` fallback bullet ≥ 30 chars (D3 invariant)."""
    md = rationale_renderer.render_rationale(
        _make_match(),
        answers={"Q1": "ts-monorepo"},
        project_understanding=("X",),
        why_this_fits=("Y",),
        alternatives=(),  # empty → triggers default fallback
        notes=("Z",),
    )
    lines = md.splitlines()
    alt_idx = lines.index("## alternatives")
    bullet_line = next(
        line for line in lines[alt_idx + 1 :] if line.startswith("- ")
    )
    assert len(bullet_line) >= MIN_BULLET_CHARS, (
        f"D3 regression: default 'alternatives' fallback bullet shrunk to "
        f"{len(bullet_line)} chars (< {MIN_BULLET_CHARS}). HANDSHAKE §4 rule 7 "
        f"ambiguity-cluster validator requires ≥30-char non-empty bullets."
    )


def test_render_rationale_default_notes_bullet_meets_min_length():
    """Default `notes` fallback bullet ≥ 30 chars (D3 invariant)."""
    md = rationale_renderer.render_rationale(
        _make_match(),
        answers={"Q1": "ts-monorepo"},
        project_understanding=("X",),
        why_this_fits=("Y",),
        alternatives=("A",),
        notes=(),
    )
    lines = md.splitlines()
    notes_idx = lines.index("## notes")
    bullet_line = next(
        line for line in lines[notes_idx + 1 :] if line.startswith("- ")
    )
    assert len(bullet_line) >= MIN_BULLET_CHARS, (
        f"D3 regression: default 'notes' fallback bullet shrunk to "
        f"{len(bullet_line)} chars (< {MIN_BULLET_CHARS})."
    )
