"""BL-333 v2.1.5: `/lp-define` consumes `.launchpad/brainstorm-summary.md`
content into the canonical docs (PRD / APP_FLOW / BACKEND_STRUCTURE)
instead of producing empty placeholders.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from lp_define_runner import (  # noqa: E402
    _build_jinja_context,
    _slug_section_name,
    read_brainstorm_summary,
)
from plugin_stack_adapters import generic  # noqa: E402


_BRAINSTORM_FIXTURE = """---
name: test-brainstorm
date: 2026-05-15
---

# Brainstorm summary

## Overview

The product is a deliberate test brainstorm body — it must appear in the
rendered PRD.md Overview section so users see brainstorm investment pay off.

## Users

Solo founders shipping their first SaaS who need scaffolding plus speed.

## Success Criteria

A founder can scaffold and ship a first version within a weekend.

## Non-goals

Replacing a full design system or a custom workflow engine.

## Constraints

Must work offline-first; must respect privacy choices.

## Navigation

Single-page entry → onboarding flow → main dashboard. No deep nesting.

## Routes

`GET /` lists active features; `POST /sections` shapes a new section.
"""


def test_slug_section_name_basic() -> None:
    assert _slug_section_name("Overview") == "overview"
    assert _slug_section_name("Success Criteria") == "success_criteria"
    assert _slug_section_name("Non-goals") == "non-goals"
    assert _slug_section_name("Goals & Metrics!") == "goals_metrics"


def test_read_brainstorm_summary_returns_empty_when_missing(tmp_path: Path) -> None:
    result = read_brainstorm_summary(tmp_path)
    assert result == {}


def test_read_brainstorm_summary_parses_sections(tmp_path: Path) -> None:
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(_BRAINSTORM_FIXTURE)
    result = read_brainstorm_summary(tmp_path)
    assert "overview" in result
    assert "users" in result
    assert "success_criteria" in result
    assert "non_goals" in result
    assert "constraints" in result
    assert "navigation" in result
    assert "routes" in result
    # Body content survives unchanged
    assert "deliberate test brainstorm body" in result["overview"]
    assert "Solo founders" in result["users"]
    assert "weekend" in result["success_criteria"]


def test_read_brainstorm_summary_applies_aliases(tmp_path: Path) -> None:
    """A brainstorm header `## Problem` should land at `overview`; `## Personas`
    should land at `users`."""
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text("""
## Problem

The problem statement body.

## Personas

The personas body.
""")
    result = read_brainstorm_summary(tmp_path)
    assert result.get("overview") == "The problem statement body."
    assert result.get("users") == "The personas body."


def test_jinja_context_includes_brainstorm(tmp_path: Path) -> None:
    """`_build_jinja_context` injects `brainstorm` as a dict-like key."""
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(_BRAINSTORM_FIXTURE)
    adapter_out = generic.run()
    ctx = _build_jinja_context(adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path)
    assert "brainstorm" in ctx
    assert "overview" in ctx["brainstorm"]
    assert "deliberate test brainstorm body" in ctx["brainstorm"]["overview"]


def test_prd_renders_brainstorm_content(tmp_path: Path) -> None:
    """End-to-end: `.launchpad/brainstorm-summary.md` present → PRD.md
    renders brainstorm sections inline with a `filled from brainstorm`
    comment block."""
    from plugin_default_generators._renderer_base import RendererBase
    from collections.abc import Iterator, Mapping
    from typing import Any

    # Define a tiny renderer that renders just the PRD template, no batch.
    class _PrdOnly(RendererBase):
        TEMPLATE_SUBDIR = "."

        def render_targets(self, context: Mapping[str, Any]) -> Iterator[tuple[Path, str]]:
            ctx: dict[str, Any] = context["jinja_context"]
            tmpl = self.env.get_template("PRD.md.j2")
            yield tmp_path / "PRD.md", tmpl.render(**ctx)

    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(_BRAINSTORM_FIXTURE)
    adapter_out = generic.run()
    ctx = _build_jinja_context(adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path)

    renderer = _PrdOnly()
    batch = renderer.render_batch([{"jinja_context": ctx}])
    target = next(iter(batch))
    rendered = batch[target].decode("utf-8")

    assert "TestProduct" in rendered
    # The brainstorm-marked comment appears for each populated section.
    assert "v2.1.5 BL-333: filled from .launchpad/brainstorm-summary.md" in rendered
    # The brainstorm body content is present (NOT placeholder text).
    assert "deliberate test brainstorm body" in rendered
    assert "Solo founders" in rendered
    assert "weekend" in rendered
    # The placeholder italic text is gone for populated sections.
    assert "Describe the product's purpose" not in rendered
    assert "Who uses this?" not in rendered


def test_prd_falls_back_to_placeholder_when_no_brainstorm(tmp_path: Path) -> None:
    """When `.launchpad/brainstorm-summary.md` is absent, PRD.md renders
    the original placeholder italic text (no brainstorm injection)."""
    from plugin_default_generators._renderer_base import RendererBase
    from collections.abc import Iterator, Mapping
    from typing import Any

    class _PrdOnly(RendererBase):
        TEMPLATE_SUBDIR = "."

        def render_targets(self, context: Mapping[str, Any]) -> Iterator[tuple[Path, str]]:
            ctx: dict[str, Any] = context["jinja_context"]
            tmpl = self.env.get_template("PRD.md.j2")
            yield tmp_path / "PRD.md", tmpl.render(**ctx)

    # NO brainstorm-summary.md present
    adapter_out = generic.run()
    ctx = _build_jinja_context(adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path)

    renderer = _PrdOnly()
    batch = renderer.render_batch([{"jinja_context": ctx}])
    target = next(iter(batch))
    rendered = batch[target].decode("utf-8")

    # Placeholder italic text returns
    assert "Describe the product's purpose" in rendered
    assert "Who uses this?" in rendered
    # No brainstorm-marked comment
    assert "BL-333" not in rendered
