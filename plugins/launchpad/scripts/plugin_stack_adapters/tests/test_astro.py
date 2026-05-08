"""astro adapter (3 sub-templates: docs / blog / marketing) tests.

Phase 4 plan section 2.2 row + section 3.1 + section 3.12. Replaces the
legacy `test_astro_adapter.py` (deleted in this slice). Covers:
  - 3 sub-templates emit distinct SHAs from pin_registry (docs and the
    Astro examples come from different repos; blog and marketing share a
    repo + sha but distinct sub_template_id).
  - user-prompt + hint-defaults, non-interactive default = `marketing`.
  - composition mode silent + INFO log.
  - "no opt-out" -> generic INFO log.
  - git_clone_depth_1 (verified by way of using the template_cache fetcher
    contract; no `npm_create` invocation anywhere in the module).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import pytest

from plugin_stack_adapters.astro import (
    ADAPTER,
    AstroAdapter,
    _DEFAULT_SUB_TEMPLATE,
    _SUB_PATHS,
    _SUB_TEMPLATES,
    run,
    select_sub_template_or_decline,
)
from plugin_stack_adapters.contracts import Adapter
from plugin_stack_adapters.pin_registry import get_pin

pytestmark = pytest.mark.slow


def _starlight_synthetic_tree() -> dict[str, bytes]:
    return {
        "package.json": b'{"name": "starlight"}\n',
        "astro.config.mjs": b'import starlight from "@astrojs/starlight";\n',
        "src/content/docs/index.md": b"# Docs\n",
    }


def _astro_examples_synthetic_tree() -> dict[str, bytes]:
    return {
        "package.json": b'{"name": "astro-monorepo"}\n',
        "examples/blog/package.json": b'{"name": "blog-example"}\n',
        "examples/blog/src/pages/index.astro": b"---\n---\nblog\n",
        "examples/portfolio/package.json": b'{"name": "portfolio-example"}\n',
        "examples/portfolio/src/pages/index.astro": b"---\n---\nportfolio\n",
    }


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


@pytest.fixture
def starlight_fetcher() -> Callable[[Path], None]:
    files = _starlight_synthetic_tree()

    def fetcher(target: Path) -> None:
        for rel, body in files.items():
            p = target / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)

    return fetcher


@pytest.fixture
def astro_examples_fetcher() -> Callable[[Path], None]:
    files = _astro_examples_synthetic_tree()

    def fetcher(target: Path) -> None:
        for rel, body in files.items():
            p = target / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)

    return fetcher


def test_adapter_satisfies_adapter_protocol():
    assert isinstance(ADAPTER, Adapter)


def test_default_singleton_uses_marketing():
    assert ADAPTER.sub_template_id == _DEFAULT_SUB_TEMPLATE
    assert ADAPTER.sub_template_id == "marketing"


def test_three_sub_templates_resolve_to_distinct_pins():
    docs = get_pin("astro", "docs")
    blog = get_pin("astro", "blog")
    marketing = get_pin("astro", "marketing")
    assert docs["repo_url"] != blog["repo_url"]
    assert docs["sha"] != blog["sha"]
    assert blog["repo_url"] == marketing["repo_url"]
    assert blog["sha"] == marketing["sha"]


def test_select_sub_template_non_interactive_defaults_to_marketing():
    assert (
        select_sub_template_or_decline(
            user_choice=None, interactive=False, composition_mode=False
        )
        == "marketing"
    )


def test_select_sub_template_composition_mode_silent_default_with_info_log(caplog):
    with caplog.at_level(logging.INFO, logger="plugin_stack_adapters.astro"):
        result = select_sub_template_or_decline(
            user_choice=None, interactive=False, composition_mode=True
        )
    assert result == "marketing"
    assert any(
        "composition mode" in rec.message and "marketing" in rec.message
        for rec in caplog.records
    )


def test_select_sub_template_decline_routes_to_generic_with_info_log(caplog):
    with caplog.at_level(logging.INFO, logger="plugin_stack_adapters.astro"):
        result = select_sub_template_or_decline(
            user_choice="generic-fallback",
            interactive=True,
            composition_mode=False,
        )
    assert result is None
    assert any(
        "declined Astro sub-templates" in rec.message
        for rec in caplog.records
    )


def test_select_sub_template_uses_docs_hint():
    assert (
        select_sub_template_or_decline(
            user_choice=None,
            interactive=True,
            composition_mode=False,
            hints={"docs": True},
        )
        == "docs"
    )


def test_select_sub_template_accepts_explicit_blog_choice():
    assert (
        select_sub_template_or_decline(
            user_choice="blog",
            interactive=True,
            composition_mode=False,
        )
        == "blog"
    )


def test_invalid_sub_template_raises_at_construction():
    with pytest.raises(Exception):  # AdapterScaffoldError
        AstroAdapter(sub_template_id="invalid")  # type: ignore[arg-type]


def test_scaffold_into_starlight_materializes_repo_root(
    tmp_path: Path, cache_root_tmp: Path, starlight_fetcher
):
    adapter = AstroAdapter(sub_template_id="docs", fetcher=starlight_fetcher)
    target = tmp_path / "lp-astro-docs-tmp"
    adapter.scaffold_into(target)
    assert (target / "package.json").is_file()
    assert (target / "astro.config.mjs").is_file()


def test_scaffold_into_blog_extracts_examples_blog_subtree(
    tmp_path: Path, cache_root_tmp: Path, astro_examples_fetcher
):
    adapter = AstroAdapter(sub_template_id="blog", fetcher=astro_examples_fetcher)
    target = tmp_path / "lp-astro-blog-tmp"
    adapter.scaffold_into(target)
    assert (target / "package.json").is_file()
    assert (target / "src" / "pages" / "index.astro").is_file()
    text = (target / "src" / "pages" / "index.astro").read_text(encoding="utf-8")
    assert "blog" in text


def test_scaffold_into_marketing_extracts_examples_portfolio_subtree(
    tmp_path: Path, cache_root_tmp: Path, astro_examples_fetcher
):
    adapter = AstroAdapter(
        sub_template_id="marketing", fetcher=astro_examples_fetcher
    )
    target = tmp_path / "lp-astro-marketing-tmp"
    adapter.scaffold_into(target)
    assert (target / "package.json").is_file()
    text = (target / "src" / "pages" / "index.astro").read_text(encoding="utf-8")
    assert "portfolio" in text


def test_module_does_not_invoke_npm_create():
    import plugin_stack_adapters.astro as astro_module

    source = Path(astro_module.__file__).read_text(encoding="utf-8")
    assert "npm create" not in source
    assert "npm_create" not in source.replace("(NOT `npm_create`)", "")


def test_legacy_run_function_preserved_for_polyglot_composer():
    out = run()
    assert out["stack_id"] == "astro"
    assert "Astro 5" in out["tech_stack"]["frameworks"]
    assert out["frontend"] is not None


def test_sub_paths_map_to_three_sub_templates():
    assert set(_SUB_PATHS.keys()) == set(_SUB_TEMPLATES)
    assert _SUB_PATHS["docs"] == ""
    assert "examples/blog" in _SUB_PATHS["blog"]
    assert "examples/portfolio" in _SUB_PATHS["marketing"]
