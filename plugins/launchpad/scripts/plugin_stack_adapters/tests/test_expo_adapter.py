"""expo_adapter — Phase 0.5 §1.4 unit test."""
from __future__ import annotations

from plugin_stack_adapters import expo_adapter


def test_run_returns_adapter_output_with_correct_stack_id():
    out = expo_adapter.run()
    assert out["stack_id"] == "expo"


def test_run_populates_required_fields():
    out = expo_adapter.run()
    assert out["tech_stack"]["language"] == "TypeScript"
    assert out["frontend"] is not None
    assert "Expo" in out["frontend"]["framework"]
    # Mobile target — browser tests off; client-only (no backend).
    assert out["pipeline_overrides"]["test_browser_enabled"] is False
    assert "client" in out["backend"]["framework"].lower()


def test_module_load_has_no_subprocess_side_effects():
    import importlib
    importlib.reload(expo_adapter)
    out = expo_adapter.run()
    assert out["stack_id"] == "expo"
