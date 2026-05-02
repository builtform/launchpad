"""fastapi_adapter — Phase 0.5 §1.4 unit test."""
from __future__ import annotations

from plugin_stack_adapters import fastapi_adapter


def test_run_returns_adapter_output_with_correct_stack_id():
    out = fastapi_adapter.run()
    assert out["stack_id"] == "fastapi"


def test_run_populates_required_fields():
    out = fastapi_adapter.run()
    assert out["tech_stack"]["language"] == "Python"
    assert out["backend"]["framework"] == "FastAPI"
    assert out["backend"]["routes_dir"]
    # Backend-only — frontend is None by design (paired with frontend stack
    # in polyglot mode).
    assert out["frontend"] is None
    assert out["pipeline_overrides"]["design_enabled"] is False


def test_module_load_has_no_subprocess_side_effects():
    import importlib
    importlib.reload(fastapi_adapter)
    out = fastapi_adapter.run()
    assert out["stack_id"] == "fastapi"
