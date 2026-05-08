"""Phase 6 Slice B -- agent scope filter perf budget.

In-process budget per §3.2: <50ms warm hit (lru_cache <1ms), <200ms cold
load (36 plugin files * ~5ms). Subprocess budget deferred to v2.2 BL.

`cache_clear()` is called via autouse fixture per §3.2 cache lifecycle to
isolate cold-load measurements between tests.
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
_FILTER_PATH = _SCRIPTS / "plugin-agent-scope-filter.py"


def _fresh_filter_module():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    sys.modules.pop("plugin_agent_scope_filter", None)
    spec = importlib.util.spec_from_file_location(
        "plugin_agent_scope_filter", _FILTER_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(autouse=True)
def _autouse_cache_clear():
    """§3.2 cache lifecycle: every perf test starts with a cleared lru_cache."""
    mod = _fresh_filter_module()
    mod._load_agent_index.cache_clear()
    yield
    mod._load_agent_index.cache_clear()


def test_cold_load_under_200ms():
    """Cold load (cache cleared) must come in under 200ms in-process."""
    mod = _fresh_filter_module()
    mod._load_agent_index.cache_clear()
    start = time.perf_counter()
    mod._load_agent_index()
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 200, f"cold load took {elapsed_ms:.1f}ms (>200ms budget)"


def test_warm_hit_under_50ms():
    """Warm hits (cache populated) must come in under 50ms each."""
    mod = _fresh_filter_module()
    mod._load_agent_index()  # warm the cache
    start = time.perf_counter()
    for _ in range(100):
        mod._load_agent_index()
    elapsed_ms = (time.perf_counter() - start) * 1000
    avg_ms = elapsed_ms / 100
    assert avg_ms < 50, f"warm avg {avg_ms:.3f}ms exceeds 50ms budget"


def test_thousand_iter_filter_under_5s():
    """1000-iteration benchmark of filter call must complete under 5s.
    Detects pathological non-cached re-compile or per-call disk reads."""
    mod = _fresh_filter_module()
    mod._load_agent_index()  # warm the cache
    start = time.perf_counter()
    for _ in range(1000):
        mod.filter_agents_by_stacks(
            ["lp-file-locator", "lp-security-auditor"], stacks=["ts_monorepo"]
        )
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"1000-iter filter took {elapsed:.2f}s (>5s budget)"
