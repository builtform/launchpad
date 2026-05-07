"""v2.1 Codex PR #50 Greptile #5 (D5) regression: catalog-shortname fallback.

Tests:
  * Composition-first ordering (next + fastapi → nextjs_fastapi)
  * Composition-first for next + hono → nextjs_hono_cloudflare
  * Singleton fallback for `django` → `python_generic`
  * Singleton fallback for `next` → `nextjs_standalone`
  * Singleton fallback for `supabase` → `generic`
  * Already-canonical ids pass through unchanged
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_pick_stack.decision_writer import derive_stacks  # noqa: E402


def test_composition_first_next_fastapi():
    layers = [
        {"stack": "next", "role": "frontend", "path": "apps/web"},
        {"stack": "fastapi", "role": "backend", "path": "apps/api"},
    ]
    assert derive_stacks(layers) == ["nextjs_fastapi"]


def test_composition_first_next_hono():
    layers = [
        {"stack": "next", "role": "frontend", "path": "apps/web"},
        {"stack": "hono", "role": "backend", "path": "apps/api"},
    ]
    assert derive_stacks(layers) == ["nextjs_hono_cloudflare"]


def test_singleton_fallback_django_to_python_generic():
    layers = [{"stack": "django", "role": "fullstack", "path": "."}]
    assert derive_stacks(layers) == ["python_generic"]


def test_singleton_fallback_next_to_nextjs_standalone():
    layers = [{"stack": "next", "role": "fullstack", "path": "."}]
    assert derive_stacks(layers) == ["nextjs_standalone"]


def test_singleton_fallback_supabase_to_generic():
    layers = [{"stack": "supabase", "role": "backend-managed", "path": "."}]
    assert derive_stacks(layers) == ["generic"]


def test_canonical_id_passes_through():
    layers = [{"stack": "astro", "role": "frontend", "path": "."}]
    assert derive_stacks(layers) == ["astro"]


def test_multi_element_post_fallback():
    # next + django (not a composition) → both fall back independently.
    layers = [
        {"stack": "next", "role": "frontend", "path": "apps/web"},
        {"stack": "django", "role": "backend", "path": "apps/api"},
    ]
    out = derive_stacks(layers)
    assert "nextjs_standalone" in out
    assert "python_generic" in out
