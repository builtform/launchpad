"""Regression tests for v2.0.1 BL-244 #2 (PR #41 cycle-12 #2 closure):
scaffolder option keys can carry an explicit CLI flag-name override via
the scaffolder's `option_flags` mapping. Without override, the flag falls
back to `--{key}` (the previous default behavior).

The fix targets the silent-failure path where snake_case option keys
(like Next's `src_dir`) emitted invalid kebab-case-expecting flags
(`create-next-app` uses `--src-dir`). The override mapping lets each
CLI's spelling convention be encoded once in scaffolders.yml without
forcing snake_case→kebab-case across all option keys.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.layer_materializer import _build_orchestrate_argv


def test_option_flags_override_kebab_case():
    """`option_flags: {src_dir: --src-dir}` produces `--src-dir` not `--src_dir`."""
    scaffolder = {
        "command": "npx create-next-app@latest",
        "destination_argv": ["."],
        "headless_flags": ["--yes", "--typescript"],
        "option_flags": {"src_dir": "--src-dir"},
    }
    layer = {"options": {"src_dir": True}}
    argv = _build_orchestrate_argv(scaffolder, layer)
    assert "--src-dir" in argv, f"expected --src-dir in argv, got {argv!r}"
    assert "--src_dir" not in argv, (
        f"snake_case --src_dir leaked despite option_flags override; "
        f"argv={argv!r}"
    )


def test_option_flags_override_with_value():
    """Override applies to non-bool values too (string options)."""
    scaffolder = {
        "command": "tool",
        "destination_argv": [],
        "headless_flags": [],
        "option_flags": {"db_engine": "--db-engine"},
    }
    layer = {"options": {"db_engine": "postgres"}}
    argv = _build_orchestrate_argv(scaffolder, layer)
    assert "--db-engine=postgres" in argv, (
        f"expected --db-engine=postgres in argv, got {argv!r}"
    )


def test_option_without_override_falls_back_to_default():
    """Options without an explicit override use the legacy `--{key}` shape."""
    scaffolder = {
        "command": "tool",
        "destination_argv": [],
        "headless_flags": [],
        # NO option_flags key present
    }
    layer = {"options": {"flag": True, "value": "x"}}
    argv = _build_orchestrate_argv(scaffolder, layer)
    assert "--flag" in argv
    assert "--value=x" in argv


def test_option_flags_partial_override():
    """Mapping covers SOME keys; unmapped keys fall back to `--{key}`."""
    scaffolder = {
        "command": "tool",
        "destination_argv": [],
        "headless_flags": [],
        "option_flags": {"src_dir": "--src-dir"},  # only this one mapped
    }
    layer = {"options": {"src_dir": True, "other_opt": True}}
    argv = _build_orchestrate_argv(scaffolder, layer)
    assert "--src-dir" in argv
    assert "--other_opt" in argv  # falls back to default


def test_bool_false_omits_flag():
    """Bool option set to False does NOT emit the flag (matches pre-fix behavior)."""
    scaffolder = {
        "command": "tool",
        "destination_argv": [],
        "headless_flags": [],
        "option_flags": {"src_dir": "--src-dir"},
    }
    layer = {"options": {"src_dir": False}}
    argv = _build_orchestrate_argv(scaffolder, layer)
    assert "--src-dir" not in argv
    assert "--src_dir" not in argv


def test_next_scaffolder_yaml_shape():
    """Verify the actual scaffolders.yml entry for `next` has option_flags wired
    AND has dropped `app_router` from options_schema (since --app forces it
    via headless_flags)."""
    import yaml

    scaffolders_path = _SCRIPTS.parent / "scaffolders.yml"
    with open(scaffolders_path, "r", encoding="utf-8") as f:
        catalog = yaml.safe_load(f)
    next_entry = catalog["stacks"]["next"]

    # option_flags maps src_dir → --src-dir
    assert next_entry.get("option_flags", {}).get("src_dir") == "--src-dir"

    # app_router is NOT in options_schema (already forced via --app)
    options_schema = next_entry.get("options_schema", {})
    assert "app_router" not in options_schema, (
        f"app_router should be dropped from options_schema since --app is "
        f"already in headless_flags; got {options_schema!r}"
    )

    # --app IS in headless_flags (the actual App Router enabler)
    assert "--app" in next_entry["headless_flags"]
