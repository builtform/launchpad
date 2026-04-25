#!/usr/bin/env python3
"""Config loader tests — realpath-confinement + section-by-section re-parse +
command coercion + defaults.

Run:
  python3 plugins/launchpad/scripts/tests/test_config_loader.py

Exit 0 on pass, 1 on failure.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

# Load the loader module from its hyphenated filename
_spec = importlib.util.spec_from_file_location(
    "plugin_config_loader",
    Path(__file__).resolve().parent.parent / "plugin-config-loader.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

load = _mod.load
ConfigError = _mod.ConfigError


def make_fixture(config_yml: str | None) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-config-test-"))
    if config_yml is not None:
        (d / ".launchpad").mkdir()
        (d / ".launchpad" / "config.yml").write_text(config_yml)
    return d


def cleanup(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)


def test_defaults_when_missing() -> list[str]:
    errors = []
    fixture = make_fixture(None)
    try:
        cfg = load(fixture)
        if cfg["overwrite"] != "prompt":
            errors.append(f"missing config: overwrite={cfg['overwrite']!r}, expected 'prompt'")
        if cfg["paths"]["architecture_dir"] != "docs/architecture":
            errors.append(f"missing config: paths.architecture_dir wrong default")
        if cfg["__errors__"]:
            errors.append(f"missing config: unexpected errors: {cfg['__errors__']}")
    finally:
        cleanup(fixture)
    return errors


def test_realpath_rejects_absolute() -> list[str]:
    errors = []
    fixture = make_fixture("""
paths:
  architecture_dir: "/etc/passwd"
""")
    try:
        cfg = load(fixture)
        if not any("absolute" in e.lower() for e in cfg["__errors__"]):
            errors.append(f"absolute path: expected error mentioning 'absolute', got {cfg['__errors__']}")
        # Should fall back to default, not accept the hostile value
        if cfg["paths"]["architecture_dir"] == "/etc/passwd":
            errors.append("absolute path: loader accepted /etc/passwd")
    finally:
        cleanup(fixture)
    return errors


def test_realpath_rejects_dotdot() -> list[str]:
    errors = []
    fixture = make_fixture("""
paths:
  architecture_dir: "../../../etc"
""")
    try:
        cfg = load(fixture)
        if not any(".." in e for e in cfg["__errors__"]):
            errors.append(f"../ escape: expected error mentioning '..', got {cfg['__errors__']}")
    finally:
        cleanup(fixture)
    return errors


def test_commands_coercion() -> list[str]:
    """commands.* should always be list[str]; scalars get coerced, empty string → []."""
    errors = []
    fixture = make_fixture("""
commands:
  test: "pytest"
  typecheck: ""
  lint: ["ruff check .", "mypy"]
  format:
    - ruff format .
  build: []
""")
    try:
        cfg = load(fixture)
        cmds = cfg["commands"]
        if cmds["test"] != ["pytest"]:
            errors.append(f"scalar coercion: test={cmds['test']!r}, expected ['pytest']")
        if cmds["typecheck"] != []:
            errors.append(f"empty-string coercion: typecheck={cmds['typecheck']!r}, expected []")
        if cmds["lint"] != ["ruff check .", "mypy"]:
            errors.append(f"list passthrough: lint={cmds['lint']!r}")
        if cmds["format"] != ["ruff format ."]:
            errors.append(f"YAML list: format={cmds['format']!r}")
        if cmds["build"] != []:
            errors.append(f"empty list: build={cmds['build']!r}")
    finally:
        cleanup(fixture)
    return errors


def test_section_isolation() -> list[str]:
    """Bad commands section should not prevent paths from being usable."""
    errors = []
    fixture = make_fixture("""
commands:
  test: 42  # type error (not string or list)
paths:
  architecture_dir: "custom/arch"
""")
    try:
        cfg = load(fixture)
        # paths section should still be loaded even though commands errored
        if cfg["paths"]["architecture_dir"] != "custom/arch":
            errors.append(
                f"section isolation: paths.architecture_dir not loaded despite "
                f"commands error (got {cfg['paths']['architecture_dir']!r})"
            )
        # The error should surface in __errors__
        if not cfg["__errors__"]:
            errors.append("section isolation: commands error not surfaced in __errors__")
    finally:
        cleanup(fixture)
    return errors


def test_overwrite_validation() -> list[str]:
    errors = []
    fixture = make_fixture("""
overwrite: yolo
""")
    try:
        cfg = load(fixture)
        if cfg["overwrite"] != "prompt":
            errors.append(f"bad overwrite: fallback should stay 'prompt', got {cfg['overwrite']!r}")
        if not any("overwrite" in e for e in cfg["__errors__"]):
            errors.append(f"bad overwrite: error not surfaced: {cfg['__errors__']}")
    finally:
        cleanup(fixture)
    return errors


def test_audit_committed_opt_in() -> list[str]:
    errors = []
    fixture = make_fixture("""
audit:
  committed: true
""")
    try:
        cfg = load(fixture)
        if cfg["audit"]["committed"] is not True:
            errors.append(f"audit.committed opt-in: got {cfg['audit']!r}")
    finally:
        cleanup(fixture)
    return errors


def main() -> int:
    all_errors = []
    for name, test in [
        ("defaults_when_missing", test_defaults_when_missing),
        ("realpath_rejects_absolute", test_realpath_rejects_absolute),
        ("realpath_rejects_dotdot", test_realpath_rejects_dotdot),
        ("commands_coercion", test_commands_coercion),
        ("section_isolation", test_section_isolation),
        ("overwrite_validation", test_overwrite_validation),
        ("audit_committed_opt_in", test_audit_committed_opt_in),
    ]:
        errs = test()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: config loader tests")
        for e in all_errors:
            print(e)
        return 1

    print("PASS: config loader (7 tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
