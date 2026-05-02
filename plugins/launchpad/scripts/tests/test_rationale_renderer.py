"""Tests for lp_pick_stack.rationale_renderer (Phase 2 §4.1 Step 5)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.matcher import MatchCandidate
from lp_pick_stack.rationale_renderer import render_rationale
from lp_pick_stack.rationale_summary_extractor import (
    SECTION_ORDER,
    extract_summary,
)


def _basic_candidate() -> MatchCandidate:
    return MatchCandidate(
        id="static-blog-astro",
        name="Static blog (Astro)",
        score=3,
        canonical_stack=({"stack": "astro", "role": "frontend", "path": "."},),
        explanation="Markdown-driven blog with TypeScript-first islands.",
        cluster="static-blog-trio",
    )


VALID_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}


def test_renders_all_six_sections():
    body = render_rationale(_basic_candidate(), VALID_ANSWERS)
    for slug in SECTION_ORDER:
        assert f"## {slug}" in body


def test_rendered_body_round_trips_through_extractor(tmp_path: Path):
    body = render_rationale(_basic_candidate(), VALID_ANSWERS)
    out = tmp_path / "rationale.md"
    out.write_text(body, encoding="utf-8")
    summary = extract_summary(out)
    # All 6 sections present with at least one bullet
    assert len(summary) == 6
    assert all(isinstance(s["bullets"], list) for s in summary)
    # At least one section has ≥1 non-empty bullet (HANDSHAKE §4 rule 7)
    assert any(s["bullets"] for s in summary)


def test_frontmatter_includes_matched_category_id():
    body = render_rationale(_basic_candidate(), VALID_ANSWERS)
    assert "matched_category_id: static-blog-astro" in body


def test_caller_supplied_bullets_render():
    body = render_rationale(
        _basic_candidate(),
        VALID_ANSWERS,
        project_understanding=["A static blog for personal writing."],
        why_this_fits=["Astro chosen because team prefers TS islands."],
        alternatives=["static-blog-eleventy: rejected because TS preferred."],
    )
    assert "A static blog for personal writing." in body
    assert "Astro chosen because team prefers TS islands." in body


def test_forbidden_token_filtered():
    body = render_rationale(
        _basic_candidate(),
        VALID_ANSWERS,
        project_understanding=["Visit https://evil.example.com for details"],
    )
    assert "https://" not in body


def test_html_tag_filtered():
    body = render_rationale(
        _basic_candidate(),
        VALID_ANSWERS,
        project_understanding=["Inject <script>alert(1)</script> here"],
    )
    assert "<script>" not in body


def test_overlong_bullet_truncated():
    long_text = "a" * 500
    body = render_rationale(
        _basic_candidate(),
        VALID_ANSWERS,
        project_understanding=[long_text],
    )
    # Body should not contain the full overlong text
    assert long_text not in body


def test_explicit_canonical_stack_override():
    body = render_rationale(
        _basic_candidate(),
        VALID_ANSWERS,
        canonical_stack=[
            {"stack": "next", "role": "frontend", "path": "apps/web"},
            {"stack": "fastapi", "role": "backend", "path": "services/api"},
        ],
    )
    assert "next as frontend at apps/web" in body
    assert "fastapi as backend at services/api" in body


def test_manual_override_id_renders():
    body = render_rationale(
        _basic_candidate(),
        VALID_ANSWERS,
        matched_category_id="manual-override",
        matched_name="Manual override",
    )
    assert "matched_category_id: manual-override" in body


def test_default_bullet_when_section_input_empty():
    body = render_rationale(_basic_candidate(), VALID_ANSWERS)
    # project-understanding gets a default bullet derived from Q1
    assert "static-site-or-blog" in body


def test_nfkc_normalization_strips_confusables():
    body = render_rationale(
        _basic_candidate(),
        VALID_ANSWERS,
        notes=["fullwidth ＜tag＞ in body"],
    )
    # The fullwidth confusable normalizes to <tag> via NFKC, then forbidden_token
    # filter drops it (because `<` matches the FORBIDDEN_BULLET_RE)
    assert "＜tag＞" not in body
    assert "<tag>" not in body
