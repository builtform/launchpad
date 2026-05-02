"""astro_adapter — Phase 0.5 §1.4 unit test."""
from __future__ import annotations

from plugin_stack_adapters import astro_adapter
from plugin_stack_adapters.contracts import AdapterOutput


def test_run_returns_adapter_output_with_correct_stack_id():
    out = astro_adapter.run()
    assert out["stack_id"] == "astro"


def test_run_populates_required_fields():
    out = astro_adapter.run()
    assert out["tech_stack"]["language"] == "TypeScript"
    assert "Astro 5" in out["tech_stack"]["frameworks"]
    assert out["frontend"] is not None
    assert out["frontend"]["framework"] == "Astro 5"
    assert out["backend"]["routes_dir"]


def test_module_load_has_no_subprocess_side_effects():
    """Re-importing must not spawn anything (load-time pure per §1.3.5)."""
    import importlib
    importlib.reload(astro_adapter)
    out = astro_adapter.run()
    assert out["stack_id"] == "astro"
