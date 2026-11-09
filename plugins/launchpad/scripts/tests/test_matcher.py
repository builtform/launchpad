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
    confident_pick,
    match_categories,
    resolve_in_cluster,
    shortlist_categories,
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


def test_null_description_scores_as_empty(catalog: dict):
    answers = {"Q1": "api-only", "Q4": "python", "describe": None}
    assert [(c.id, c.score) for c in match_categories(answers, catalog)] == [
        ("api-only-django-drf", 2), ("api-only-fastapi", 2),
    ]
    assert shortlist_categories(answers, catalog) == shortlist_categories(
        dict(answers, describe=""), catalog
    )


_DESCRIPTION = (
    "A private, single-user web app that keeps a long-range personal plan and derives today's single priority "
    "with a scheduler. PostgreSQL, an in-app LLM agent, a token-protected YAML import and export API, "
    "passkey sign-in, and an installable PWA with web push."
)
_INFORMED_DESCRIPTION = (
    "A private, single-user web app built as a TypeScript end-to-end monorepo: a long-running Node API server "
    "with PostgreSQL, a scheduler, passkey sign-in, a token-protected YAML import and export API, an in-app "
    "LLM agent, and an installable PWA with web push."
)
_BASE_ANSWERS = {"Q1": "web-app", "Q3": "feature-not-core"}
_CASE_A = dict(_BASE_ANSWERS, Q2="not-sure-decide-for-me", Q4="none-AI-driven-dev", Q5="no-strong-preference", describe=_DESCRIPTION)
_CASE_C = dict(_BASE_ANSWERS, Q2="yes-needed", Q4="none-AI-driven-dev", Q5="node-server", describe=_DESCRIPTION)
_CASE_D = dict(_CASE_C, Q4="typescript-javascript")
_EXPECTED_A = [
    ("saas-django-postgres", 2, ("Q2", "Q4"), 0, 0),
    ("multi-frontend-astro-next", 1, (), 0, 1),
    ("polyglot-next-hono", 1, ("Q2", "Q4"), 0, 1),
    ("realtime-django-channels", 1, ("Q4",), 0, 1),
    ("saas-next-supabase", 1, ("Q2", "Q4"), 0, 1),
]
_CASES = [
    pytest.param(_CASE_A, _EXPECTED_A, None, id="A"),
    pytest.param({k: v for k, v in _CASE_A.items() if k != "describe"}, _EXPECTED_A, None, id="B"),
    pytest.param(_CASE_C, [
        ("saas-django-postgres", 3, ("Q4",), 0, 0),
        ("polyglot-next-hono", 2, ("Q4",), 0, 1),
        ("saas-next-supabase", 2, ("Q4",), 0, 1),
        ("multi-frontend-astro-next", 1, (), 0, 1),
        ("realtime-django-channels", 1, ("Q4",), 0, 1),
    ], None, id="C"),
    pytest.param(_CASE_D, [
        ("polyglot-next-hono", 3, (), 0, 1),
        ("saas-next-supabase", 3, (), 0, 1),
        ("multi-frontend-astro-next", 1, (), 0, 1),
    ], None, id="D"),
    pytest.param(dict(_CASE_D, describe=_INFORMED_DESCRIPTION), [
        ("polyglot-next-hono", 4, (), 2, 1),
        ("saas-next-supabase", 3, (), 0, 1),
        ("multi-frontend-astro-next", 1, (), 0, 1),
    ], "polyglot-next-hono", id="E"),
    pytest.param(dict(_CASE_D, describe=_INFORMED_DESCRIPTION + " Passkey authentication."), [
        ("polyglot-next-hono", 4, (), 2, 1),
        ("saas-next-supabase", 4, (), 1, 1),
        ("multi-frontend-astro-next", 1, (), 0, 1),
    ], None, id="F"),
    pytest.param({"Q1": "api-only", "Q4": "mixed-no-strong-preference", "describe": "edge API"}, [
        ("api-only-hono", 3, (), 1, 1),
        ("api-only-django-drf", 1, ("Q4",), 0, 1),
        ("api-only-fastapi", 1, ("Q4",), 0, 1),
        ("api-only-rails", 1, ("Q4",), 0, 0),
    ], "api-only-hono", id="G"),
]


@pytest.mark.parametrize(("answers", "expected", "chosen_id"), _CASES)
def test_shortlist_cases(catalog: dict, answers: dict, expected: list, chosen_id: str | None):
    candidates = shortlist_categories(answers, catalog)
    assert [(c.id, c.score, c.matched_by_wildcard) for c in candidates] == [
        (cat_id, score, wildcards) for cat_id, score, wildcards, _, _ in expected
    ]
    for candidate, (_, _, _, hits, atoms) in zip(candidates, expected, strict=True):
        assert (len(candidate.describe_hits) > 0) == (hits > 0)
        assert candidate.describe_atoms == atoms
    if answers.get("describe", "").startswith(_INFORMED_DESCRIPTION):
        assert candidates[0].describe_hits == ("typescript end-to-end", "monorepo")


@pytest.mark.parametrize(("answers", "expected", "chosen_id"), _CASES)
def test_confident_pick_cases(catalog: dict, answers: dict, expected: list, chosen_id: str | None):
    picked = confident_pick(shortlist_categories(answers, catalog))
    assert (picked.id if picked else None) == chosen_id
