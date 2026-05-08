"""v2.1.1 Phase 3 BL-237 closure: verify V2_MODULES → path-prefix matcher
covers all v2.0 modules + Phase 3 in-scope expansions, and that
LINT_RAW_SUBPROCESS_ALLOWLIST entries are full paths (not basenames)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# R1-T1-1: parents[4] = repo root from plugins/launchpad/scripts/tests/<file>.py
# (parents[0]=tests, parents[1]=scripts, parents[2]=launchpad, parents[3]=plugins, parents[4]=repo root)
REPO_ROOT = Path(__file__).resolve().parents[4]
LINT_SCRIPT = REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin-v2-handshake-lint.py"


def _load_lint_module():
    # R1-T2-3: defensive None-checks on spec + loader (modern importlib pattern;
    # also satisfies pyright/mypy strict-mode lint Phase 4 will add).
    spec = importlib.util.spec_from_file_location("v2_lint", LINT_SCRIPT)
    assert spec is not None and spec.loader is not None, (
        f"could not load lint module from {LINT_SCRIPT}"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v2_lint"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


def test_path_matcher_includes_existing_v2_modules(lint):
    legacy_v2_basenames = [
        "decision_integrity.py", "knowledge_anchor_loader.py",
        "path_validator.py", "cwd_state.py", "safe_run.py",
        "telemetry_writer.py", "pid_identity.py",
        "plugin-v2-handshake-lint.py", "plugin-scaffold-receipt-loader.py",
        "plugin-freshness-check.py", "plugin-scaffold-stack.py",
    ]
    for basename in legacy_v2_basenames:
        path = f"plugins/launchpad/scripts/{basename}"
        assert lint._is_v2_module(path), f"{basename} regressed under new matcher"


def test_path_matcher_excludes_vendor_and_nested_vendor(lint):
    assert not lint._is_v2_module("plugins/launchpad/scripts/_vendor/foo.py")
    assert not lint._is_v2_module(
        "plugins/launchpad/scripts/plugin_stack_adapters/_vendor/bar.py"
    )


def test_path_matcher_excludes_tests(lint):
    assert not lint._is_v2_module("plugins/launchpad/scripts/tests/test_foo.py")


def test_path_matcher_excludes_jinja_templates(lint):
    assert not lint._is_v2_module(
        "plugins/launchpad/scripts/plugin_default_generators/foo.py.j2"
    )


def test_raw_subprocess_allowlist_uses_full_paths_not_basenames(lint):
    """engine.py has 4 occurrences in scope; basename allowlist would
    silently exempt all four. Verify allowlist entries are full paths
    (R1-T3-3: dropped redundant `/` assertion — startswith implies it)."""
    for entry in lint.LINT_RAW_SUBPROCESS_ALLOWLIST:
        assert entry.startswith("plugins/launchpad/scripts/"), (
            f"allowlist entry {entry!r} is not a full path"
        )


def test_shell_true_allowlist_uses_full_paths_not_basenames(lint):
    """R1-T2-12: parallel coverage for LINT_SHELL_TRUE_ALLOWLIST.
    Same engine.py collision-class hazard applies."""
    for entry in lint.LINT_SHELL_TRUE_ALLOWLIST:
        assert entry.startswith("plugins/launchpad/scripts/"), (
            f"shell-true allowlist entry {entry!r} is not a full path"
        )
