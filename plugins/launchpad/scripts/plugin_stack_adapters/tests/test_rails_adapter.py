"""rails_adapter — Phase 0.5 §1.4 unit test."""
from __future__ import annotations

from plugin_stack_adapters import rails_adapter


def test_run_returns_adapter_output_with_correct_stack_id():
    out = rails_adapter.run()
    assert out["stack_id"] == "rails"


def test_run_populates_required_fields():
    out = rails_adapter.run()
    assert out["tech_stack"]["language"] == "Ruby"
    assert out["backend"]["framework"] == "Rails 8"
    # Rails fullstack: ships its own view layer (Hotwire).
    assert out["frontend"] is not None
    assert "Hotwire" in out["frontend"]["framework"]
    assert out["app_flow"] is not None


def test_module_load_has_no_subprocess_side_effects():
    import importlib
    importlib.reload(rails_adapter)
    out = rails_adapter.run()
    assert out["stack_id"] == "rails"
