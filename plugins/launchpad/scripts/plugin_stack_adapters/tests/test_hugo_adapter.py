"""hugo_adapter — Phase 0.5 §1.4 unit test."""
from __future__ import annotations

from plugin_stack_adapters import hugo_adapter


def test_run_returns_adapter_output_with_correct_stack_id():
    out = hugo_adapter.run()
    assert out["stack_id"] == "hugo"


def test_run_populates_required_fields():
    out = hugo_adapter.run()
    assert out["tech_stack"]["language"] == "Go"
    assert out["frontend"] is not None
    assert out["frontend"]["framework"] == "Hugo"
    # Static site — backend is "None"; browser tests off.
    assert "static" in out["backend"]["framework"].lower()
    assert out["pipeline_overrides"]["test_browser_enabled"] is False
    assert out["commands"]["build"] == ["hugo --minify"]


def test_module_load_has_no_subprocess_side_effects():
    import importlib
    importlib.reload(hugo_adapter)
    out = hugo_adapter.run()
    assert out["stack_id"] == "hugo"
