"""Phase 4 v2.1 minimal `stack:` -> `stacks: [...]` lift tests (Slice D).

Phase 4 plan section 3.12 verbatim WARN message + section 4 Slice D
"MINIMAL `stack:` -> `stacks: [...]` lift in config.yml reader (read-time
auto-promote scalar to single-element array; warn-on-write per section
3.12)."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_LOADER_PATH = (
    REPO_ROOT
    / "plugins"
    / "launchpad"
    / "scripts"
    / "plugin-config-loader.py"
)


def _import_loader():
    spec = importlib.util.spec_from_file_location(
        "lp_config_loader_under_test", CONFIG_LOADER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_stack_scalar_auto_promotes_to_stacks_list():
    loader = _import_loader()
    config = {"stack": "nextjs_standalone"}
    promoted, warnings = loader.auto_promote_stack_to_stacks(config)
    assert promoted["stacks"] == ["nextjs_standalone"]
    assert promoted["stack"] == "nextjs_standalone"  # legacy preserved
    assert len(warnings) == 1
    assert "auto-promoted" in warnings[0]
    assert "nextjs_standalone" in warnings[0]


def test_existing_stacks_list_does_not_re_warn():
    loader = _import_loader()
    config = {"stacks": ["nextjs_standalone", "astro"]}
    promoted, warnings = loader.auto_promote_stack_to_stacks(config)
    assert promoted["stacks"] == ["nextjs_standalone", "astro"]
    assert warnings == []


def test_no_stack_or_stacks_is_no_op():
    loader = _import_loader()
    config = {"version": "1.1"}
    promoted, warnings = loader.auto_promote_stack_to_stacks(config)
    assert "stacks" not in promoted
    assert warnings == []


def test_lift_idempotent_when_both_present():
    loader = _import_loader()
    config = {
        "stack": "astro",
        "stacks": ["nextjs_standalone"],
    }
    promoted, warnings = loader.auto_promote_stack_to_stacks(config)
    # stacks already populated -> do not re-overwrite from legacy stack.
    assert promoted["stacks"] == ["nextjs_standalone"]
    assert warnings == []


def test_warn_message_matches_phase_4_section_3_12_verbatim():
    loader = _import_loader()
    config = {"stack": "generic"}
    _, warnings = loader.auto_promote_stack_to_stacks(config)
    assert (
        warnings[0]
        == "config.yml uses legacy 'stack:' scalar; auto-promoted to "
           "'stacks: [generic]'. Update config.yml to silence this warning."
    )


def test_non_dict_input_returns_unchanged():
    loader = _import_loader()
    promoted, warnings = loader.auto_promote_stack_to_stacks(
        []  # type: ignore[arg-type]
    )
    assert promoted == []
    assert warnings == []
