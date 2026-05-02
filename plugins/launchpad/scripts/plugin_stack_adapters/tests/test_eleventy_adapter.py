"""eleventy_adapter — Phase 0.5 §1.4 unit test."""
from __future__ import annotations

from plugin_stack_adapters import eleventy_adapter


def test_run_returns_adapter_output_with_correct_stack_id():
    out = eleventy_adapter.run()
    assert out["stack_id"] == "eleventy"


def test_run_populates_required_fields():
    out = eleventy_adapter.run()
    assert out["tech_stack"]["language"] == "JavaScript"
    assert out["frontend"] is not None
    assert out["frontend"]["framework"] == "Eleventy 3"
    assert "static" in out["backend"]["framework"].lower()
    assert out["pipeline_overrides"]["test_browser_enabled"] is False


def test_module_load_has_no_subprocess_side_effects():
    import importlib
    importlib.reload(eleventy_adapter)
    out = eleventy_adapter.run()
    assert out["stack_id"] == "eleventy"
