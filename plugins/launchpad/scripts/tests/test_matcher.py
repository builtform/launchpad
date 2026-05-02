"""Tests for lp_pick_stack.matcher (Phase 2 §4.1 Step 3)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.matcher import (
    MANUAL_OVERRIDE_ID,
    MatchCandidate,
    match_categories,
    resolve_in_cluster,
)


_CATALOG_PATH = (
    _SCRIPTS / "lp_pick_stack" / "data" / "category-patterns.yml"
)


@pytest.fixture(scope="module")
def catalog() -> dict:
    return yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))


# --- structural ---


def test_catalog_loads(catalog: dict):
    assert "categories" in catalog
    assert "ambiguity_clusters" in catalog
    assert isinstance(catalog["categories"], list)


# --- single-category match ---


def test_static_blog_astro_matches(catalog: dict):
    answers = {
        "Q1": "static-site-or-blog",
        "Q2": "static-content-only",
        "Q3": "no",
        "Q4": "typescript-javascript",
        "Q5": "managed-platform",
        "describe": "A blog with TypeScript-first islands for interactive bits",
    }
    results = match_categories(answers, catalog)
    assert results, "expected at least one match"
    assert results[0].id == "static-blog-astro"


def test_django_saas_matches(catalog: dict):
    answers = {
        "Q1": "web-app",
        "Q2": "yes-needed",
        "Q3": "no",
        "Q4": "python",
        "Q5": "container",
        "describe": "Python team building a SaaS",
    }
    results = match_categories(answers, catalog)
    assert results
    assert any(c.id == "saas-django-postgres" for c in results)


def test_mobile_expo_matches(catalog: dict):
    answers = {
        "Q1": "mobile-app",
        "Q2": "yes-needed",
        "Q3": "no",
        "Q4": "typescript-javascript",
        "Q5": "managed-platform",
    }
    results = match_categories(answers, catalog)
    assert results
    assert results[0].id == "mobile-app-expo"


# --- ambiguity cluster ---


def test_static_blog_trio_ambiguity(catalog: dict):
    answers = {
        "Q1": "static-site-or-blog",
        "Q2": "static-content-only",
        "Q3": "no",
        "Q4": "typescript-javascript",
        "Q5": "managed-platform",
        "describe": "Blog using both TypeScript and Hugo",
    }
    results = match_categories(answers, catalog)
    assert len(results) >= 2
    clusters = {c.cluster for c in results}
    assert clusters == {"static-blog-trio"}


def test_resolve_in_cluster_picks_chosen():
    cands = [
        MatchCandidate("a", "A", 3, (), "", "x"),
        MatchCandidate("b", "B", 3, (), "", "x"),
    ]
    chosen = resolve_in_cluster(cands, "b")
    assert chosen.id == "b"


def test_resolve_in_cluster_rejects_unknown():
    cands = [MatchCandidate("a", "A", 3, (), "", "x")]
    with pytest.raises(ValueError):
        resolve_in_cluster(cands, "z")


# --- no-match ---


def test_zero_match_returns_empty(catalog: dict):
    # Use a Q1 that no category matches AND no describe text
    answers = {
        "Q1": "desktop-app",
        "Q2": "yes-needed",
        "Q3": "no",
        "Q4": "elixir",
        "Q5": "container",
    }
    results = match_categories(answers, catalog)
    assert results == []


# --- manual-override exclusion ---


def test_manual_override_excluded_from_normal_matching(catalog: dict):
    # No matter what answers, manual-override should never be returned
    answers = {
        "Q1": "web-app",
        "Q2": "yes-needed",
        "Q3": "no",
        "Q4": "python",
        "Q5": "container",
    }
    results = match_categories(answers, catalog)
    assert all(c.id != MANUAL_OVERRIDE_ID for c in results)


# --- predicate atom evaluation ---


def test_q_in_predicate(catalog: dict):
    answers = {
        "Q1": "api-only",
        "Q2": "yes-needed",
        "Q3": "no",
        "Q4": "mixed-no-strong-preference",
        "Q5": "edge-runtime",
        "describe": "Edge-deployable serverless API",
    }
    results = match_categories(answers, catalog)
    assert any(c.id == "api-only-hono" for c in results)


def test_describe_contains_predicate_case_insensitive(catalog: dict):
    answers = {
        "Q1": "api-only",
        "Q2": "yes-needed",
        "Q3": "no",
        "Q4": "python",
        "Q5": "container",
        "describe": "AsYNc Python ML API",
    }
    results = match_categories(answers, catalog)
    assert any(c.id == "api-only-fastapi" for c in results)


def test_invalid_predicate_atom_does_not_match(catalog: dict):
    # Empty answers: no predicate should fire
    results = match_categories({}, catalog)
    assert results == []
