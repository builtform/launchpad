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
    ctx = _build_jinja_context(
        adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path
    )
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

        def render_targets(
            self, context: Mapping[str, Any]
        ) -> Iterator[tuple[Path, str]]:
            ctx: dict[str, Any] = context["jinja_context"]
            tmpl = self.env.get_template("PRD.md.j2")
            yield tmp_path / "PRD.md", tmpl.render(**ctx)

    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(_BRAINSTORM_FIXTURE)
    adapter_out = generic.run()
    ctx = _build_jinja_context(
        adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path
    )

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

        def render_targets(
            self, context: Mapping[str, Any]
        ) -> Iterator[tuple[Path, str]]:
            ctx: dict[str, Any] = context["jinja_context"]
            tmpl = self.env.get_template("PRD.md.j2")
            yield tmp_path / "PRD.md", tmpl.render(**ctx)

    # NO brainstorm-summary.md present
    adapter_out = generic.run()
    ctx = _build_jinja_context(
        adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path
    )

    renderer = _PrdOnly()
    batch = renderer.render_batch([{"jinja_context": ctx}])
    target = next(iter(batch))
    rendered = batch[target].decode("utf-8")

    # Placeholder italic text returns
    assert "Describe the product's purpose" in rendered
    assert "Who uses this?" in rendered
    # No brainstorm-marked comment
    assert "BL-333" not in rendered


# ---------------------------------------------------------------------------
# v2.1.5 PR #68 round-3 review fixes (A2 + B4)
# ---------------------------------------------------------------------------


def test_partial_brainstorm_does_not_crash(tmp_path: Path) -> None:
    """A2 regression (Codex P1): a brainstorm-summary.md containing ONLY
    `## Problem` (aliased to `overview`) without `## Users`, `## Success
    Criteria`, etc. must NOT raise `jinja2.UndefinedError` at render time.

    Prior shape used `{% if brainstorm and brainstorm.users %}` which
    evaluated `brainstorm.users` under StrictUndefined → crash. The
    hardened shape uses `brainstorm.get("users")` which never raises."""
    from collections.abc import Iterator, Mapping
    from typing import Any

    from plugin_default_generators._renderer_base import RendererBase

    class _PrdRenderer(RendererBase):
        TEMPLATE_SUBDIR = "."

        def render_targets(
            self, context: Mapping[str, Any]
        ) -> Iterator[tuple[Path, str]]:
            ctx: dict[str, Any] = context["jinja_context"]
            tmpl = self.env.get_template("PRD.md.j2")
            yield tmp_path / "PRD.md", tmpl.render(**ctx)

    # Brainstorm with ONLY `## Problem` (→ `overview` via alias). No
    # `## Users`, no `## Success Criteria`, no `## Non-Goals`,
    # no `## Constraints`. Under StrictUndefined this was the crash shape.
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(
        "## Problem\n\nOnly-the-overview body.\n", encoding="utf-8"
    )

    adapter_out = generic.run()
    ctx = _build_jinja_context(
        adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path
    )
    renderer = _PrdRenderer()
    # Must not raise.
    batch = renderer.render_batch([{"jinja_context": ctx}])
    rendered = batch[next(iter(batch))].decode("utf-8")
    assert "Only-the-overview body." in rendered
    # The non-populated sections fall back to placeholder text.
    assert "Who uses this?" in rendered


def test_brainstorm_html_is_markdown_escaped(tmp_path: Path) -> None:
    """B4 regression (security-auditor P2): a hostile brainstorm-summary.md
    that injects `<script>` / `javascript:` must render escaped, not raw.

    The `| markdown_safe` filter (applied via the `brainstorm_section`
    macro) escapes CommonMark active chars including `<` and `>`."""
    from collections.abc import Iterator, Mapping
    from typing import Any

    from plugin_default_generators._renderer_base import RendererBase

    class _PrdRenderer(RendererBase):
        TEMPLATE_SUBDIR = "."

        def render_targets(
            self, context: Mapping[str, Any]
        ) -> Iterator[tuple[Path, str]]:
            ctx: dict[str, Any] = context["jinja_context"]
            tmpl = self.env.get_template("PRD.md.j2")
            yield tmp_path / "PRD.md", tmpl.render(**ctx)

    hostile = "## Problem\n\n<script>alert(1)</script>\n[link](javascript:alert(1))\n"
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(
        hostile, encoding="utf-8"
    )
    adapter_out = generic.run()
    ctx = _build_jinja_context(
        adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path
    )
    renderer = _PrdRenderer()
    batch = renderer.render_batch([{"jinja_context": ctx}])
    rendered = batch[next(iter(batch))].decode("utf-8")

    # `<script>` must NOT appear as a raw HTML tag. With markdown_safe
    # applied, `<` and `>` are backslash-escaped.
    assert "<script>" not in rendered
    assert "\\<script\\>" in rendered or r"\<script\>" in rendered
    # The `[link](...)` markdown shape must also be defused (parens
    # escaped) so it does not render as an active link.
    assert "[link](javascript" not in rendered


# ---------------------------------------------------------------------------
# v2.1.5 PR #68 round-3 review fixes (A8 + B7)
# ---------------------------------------------------------------------------


def _render_doc(
    tmp_path: Path,
    template_name: str,
    output_relpath: str,
    *,
    ctx_overrides: dict | None = None,
) -> str:
    """Helper: render a single doc template against the brainstorm fixture
    and return decoded UTF-8 content. Used by A8 APP_FLOW + BACKEND_STRUCTURE
    coverage tests.

    `ctx_overrides` lets a test inject ctx keys (e.g., `app_flow`) that the
    generic adapter doesn't synthesize on its own."""
    from collections.abc import Iterator, Mapping
    from typing import Any

    from plugin_default_generators._renderer_base import RendererBase

    class _OneDoc(RendererBase):
        TEMPLATE_SUBDIR = "."

        def render_targets(
            self, context: Mapping[str, Any]
        ) -> Iterator[tuple[Path, str]]:
            ctx: dict[str, Any] = context["jinja_context"]
            tmpl = self.env.get_template(template_name)
            yield tmp_path / output_relpath, tmpl.render(**ctx)

    adapter_out = generic.run()
    ctx = _build_jinja_context(
        adapter_out, {"stacks": ["generic"]}, "TestProduct", tmp_path
    )
    if ctx_overrides:
        ctx.update(ctx_overrides)
    renderer = _OneDoc()
    batch = renderer.render_batch([{"jinja_context": ctx}])
    return batch[next(iter(batch))].decode("utf-8")


# Minimal truthy `app_flow` block so the `{% if app_flow %}` branch of
# APP_FLOW.md.j2 fires (otherwise the template short-circuits to a
# backend-only placeholder and the brainstorm sections never render).
_APP_FLOW_STUB = {
    "entry_routes": ["/"],
    "primary_journeys": ["primary-journey"],
    "auth_flow": "",
}


def test_app_flow_renders_brainstorm_content(tmp_path: Path) -> None:
    """A8 regression (testing-reviewer P1): APP_FLOW.md.j2 received
    brainstorm-injection blocks in BL-333 but had ZERO render tests.
    Mirror the PRD coverage with navigation + error_states sections."""
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(
        _BRAINSTORM_FIXTURE, encoding="utf-8"
    )
    rendered = _render_doc(
        tmp_path,
        "APP_FLOW.md.j2",
        "APP_FLOW.md",
        ctx_overrides={"app_flow": _APP_FLOW_STUB},
    )

    # Marker comment appears for the populated brainstorm section
    # (`navigation` from the fixture).
    assert "v2.1.5 BL-333: filled from" in rendered
    # Brainstorm content from the fixture is present.
    assert "onboarding flow" in rendered  # from `## Navigation`
    # APP_FLOW-specific scaffolding is preserved (it wraps brainstorm
    # injection inside the `{% if app_flow %}` block).
    assert "Navigation structure" in rendered


def test_app_flow_falls_back_to_placeholder_when_no_brainstorm(
    tmp_path: Path,
) -> None:
    """No brainstorm-summary.md → APP_FLOW.md placeholder italics return
    for the brainstorm-eligible sections within the `{% if app_flow %}`
    branch."""
    # NO brainstorm-summary.md present.
    rendered = _render_doc(
        tmp_path,
        "APP_FLOW.md.j2",
        "APP_FLOW.md",
        ctx_overrides={"app_flow": _APP_FLOW_STUB},
    )
    assert "Describe how users move between" in rendered
    assert "BL-333" not in rendered


def test_backend_structure_renders_brainstorm_content(tmp_path: Path) -> None:
    """A8 regression: BACKEND_STRUCTURE.md.j2 received brainstorm-injection
    blocks for routes + error_handling + observability but had zero
    render-tests. Cover the routes + (implicit error_handling/observability)
    pathways.

    v2.1.6 BL-349 update: the generic adapter now sets static_capable=True,
    which routes through the new "static site — no backend" framing that
    omits the Routes section entirely. Override the backend dict here to
    `static_capable=False` so the route-injection path is exercised.
    """
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(
        _BRAINSTORM_FIXTURE, encoding="utf-8"
    )
    rendered = _render_doc(
        tmp_path,
        "BACKEND_STRUCTURE.md.j2",
        "BACKEND_STRUCTURE.md",
        ctx_overrides={
            "backend": {
                "framework": "TestBackend",
                "api_style": "REST",
                "routes_dir": "src/routes/",
                "models_dir": "src/models/",
                "auth_pattern": "session",
                "static_capable": False,
            }
        },
    )

    # `## Routes` from fixture → brainstorm.routes section in BACKEND_STRUCTURE.
    assert "v2.1.5 BL-333: filled from" in rendered
    assert "/sections" in rendered  # from `## Routes` fixture content
    # No `error_handling` / `observability` in fixture → placeholder italics.
    assert "Document the error-response contract" in rendered
    assert "Logging destination, metrics provider" in rendered


def test_backend_structure_falls_back_to_placeholder_when_no_brainstorm(
    tmp_path: Path,
) -> None:
    """No brainstorm-summary.md → BACKEND_STRUCTURE.md placeholder
    text for all 3 brainstorm-eligible sections.

    v2.1.6 BL-349 update: override backend.static_capable=False so the
    Routes / Data models / Authentication sections render (otherwise
    the static-site framing replaces them entirely).
    """
    rendered = _render_doc(
        tmp_path,
        "BACKEND_STRUCTURE.md.j2",
        "BACKEND_STRUCTURE.md",
        ctx_overrides={
            "backend": {
                "framework": "TestBackend",
                "api_style": "REST",
                "routes_dir": "src/routes/",
                "models_dir": "src/models/",
                "auth_pattern": "session",
                "static_capable": False,
            }
        },
    )
    # Each brainstorm-eligible section falls back to placeholder.
    assert "Document the error-response contract" in rendered
    assert "Logging destination, metrics provider" in rendered
    # No marker comments.
    assert "BL-333" not in rendered


def test_backend_structure_static_site_framing_when_static_capable_true(
    tmp_path: Path,
) -> None:
    """BL-349 v2.1.6: when backend.static_capable=True, BACKEND_STRUCTURE.md
    emits "Static site — no backend" framing and omits the Routes / Data
    models / Authentication sections.

    Verifies the renderer actually consumes the static_capable field that
    BL-349 added to the BackendInfo contract — closes the testing-reviewer
    P1-B finding from the v2.1.6 /lp-review pass.
    """
    rendered = _render_doc(
        tmp_path,
        "BACKEND_STRUCTURE.md.j2",
        "BACKEND_STRUCTURE.md",
        ctx_overrides={
            "backend": {
                "framework": "Astro static",
                "api_style": "",
                "routes_dir": "src/pages/",
                "models_dir": None,
                "auth_pattern": None,
                "static_capable": True,
            }
        },
    )
    assert "Static site — no backend" in rendered, (
        "BACKEND_STRUCTURE.md must render the static-site framing when "
        "backend.static_capable is True (BL-349)."
    )
    # Server-side sections must be omitted.
    assert "## Routes" not in rendered, (
        "Routes section should be omitted under static_capable=True."
    )
    assert "## Data models" not in rendered
    assert "## Authentication" not in rendered


def test_canonical_overview_wins_over_aliased_problem(tmp_path: Path) -> None:
    """B7 regression (testing-reviewer + ts-reviewer): the Codex round-2
    alias-precedence flip had no regression test. Locks in the contract:
    `## Overview` body ALWAYS wins over `## Problem` (aliased → overview)
    regardless of document order.

    The fixture below puts `## Vision` (aliased → overview) FIRST and
    `## Overview` (canonical) SECOND. Pass-2 of `read_brainstorm_summary`
    must overwrite the alias entry with the canonical body."""
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(
        "## Vision\n\nVISION-via-alias body.\n\n"
        "## Overview\n\nCANONICAL-overview body.\n",
        encoding="utf-8",
    )
    result = read_brainstorm_summary(tmp_path)
    assert result.get("overview") == "CANONICAL-overview body.", (
        "B7 regression: when both `## Vision` (alias) and `## Overview` "
        "(canonical) are present, canonical must win regardless of order."
    )


def test_canonical_users_wins_over_aliased_personas(tmp_path: Path) -> None:
    """B7 regression: same contract for `## Personas` (alias → users) +
    `## Users` (canonical). Order: canonical first, alias second; alias
    must NOT overwrite."""
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(
        "## Users\n\nCANONICAL-users body.\n\n"
        "## Personas\n\nPERSONAS-via-alias body.\n",
        encoding="utf-8",
    )
    result = read_brainstorm_summary(tmp_path)
    assert result.get("users") == "CANONICAL-users body.", (
        "B7 regression: `## Users` (canonical) appearing before "
        "`## Personas` (alias) must still win at pass-2 overwrite."
    )


def test_data_models_alias_dropped_v215(tmp_path: Path) -> None:
    """C9 regression: `## Models` no longer aliases to `data_models` (the
    alias was dead — no template consumed `brainstorm.data_models`). The
    section now lands verbatim as `models` per pass-3 fallthrough.
    v2.1.6 can re-add the alias when BACKEND_STRUCTURE.md.j2 gains a
    `data_models` brainstorm section."""
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "brainstorm-summary.md").write_text(
        "## Models\n\nUser, Order, Invoice.\n",
        encoding="utf-8",
    )
    result = read_brainstorm_summary(tmp_path)
    # No `data_models` key — the alias is gone.
    assert "data_models" not in result
    # Verbatim slug from pass-3 fallthrough.
    assert result.get("models") == "User, Order, Invoice."
