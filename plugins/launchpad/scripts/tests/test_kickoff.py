#!/usr/bin/env python3
"""Behavioral contract tests for /lp-kickoff.

Since slash commands are prose the LLM follows, we can't literally "run"
lp-kickoff without Claude Code in the loop. But we can test every invariant
the command DEPENDS on, so if any of those invariants drift the command
breaks in a detectable way.

Acceptance invariants:
  - Cold start: no config.yml present → config loader returns default
    paths.brainstorms_dir == 'docs/brainstorms'. No error.
  - Existing config: custom paths.brainstorms_dir is honored, not silently
    replaced with the default.
  - Never blocks upstream: prereq-check in full mode succeeds in a cold
    brownfield (no config.yml, no PRD, no agents.yml).
  - Non-destructive: creating paths.brainstorms_dir doesn't touch sibling
    paths under docs/.

Run:
  python3 plugins/launchpad/scripts/tests/test_kickoff.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_SCRIPTS.parent.parent.parent

# Load config loader as a module
_spec = importlib.util.spec_from_file_location(
    "plugin_config_loader", PLUGIN_SCRIPTS / "plugin-config-loader.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
load = _mod.load

PREREQ_SH = str(PLUGIN_SCRIPTS / "plugin-prereq-check.sh")


def make_fixture(config_yml: str | None = None, extra_files: dict[str, str] | None = None) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase2-"))
    if config_yml is not None:
        (d / ".launchpad").mkdir(exist_ok=True)
        (d / ".launchpad" / "config.yml").write_text(config_yml)
    for rel, content in (extra_files or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def cleanup(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)


def test_cold_start_default_path() -> list[str]:
    """Invariant: with no config.yml, paths.brainstorms_dir defaults cleanly."""
    errors = []
    fixture = make_fixture(None)
    try:
        cfg = load(fixture)
        if cfg["paths"]["brainstorms_dir"] != "docs/brainstorms":
            errors.append(
                f"cold start: expected brainstorms_dir='docs/brainstorms', "
                f"got {cfg['paths']['brainstorms_dir']!r}"
            )
        if cfg["__errors__"]:
            errors.append(f"cold start: unexpected errors: {cfg['__errors__']}")
    finally:
        cleanup(fixture)
    return errors


def test_custom_brainstorms_dir_honored() -> list[str]:
    """Invariant: an existing config.yml with a custom brainstorms_dir is used."""
    errors = []
    fixture = make_fixture("""
paths:
  brainstorms_dir: "docs/ideas"
""")
    try:
        cfg = load(fixture)
        if cfg["paths"]["brainstorms_dir"] != "docs/ideas":
            errors.append(
                f"custom path: expected 'docs/ideas', got {cfg['paths']['brainstorms_dir']!r}"
            )
    finally:
        cleanup(fixture)
    return errors


def test_prereq_full_mode_cold_start() -> list[str]:
    """Invariant: prereq-check in full mode succeeds in an empty brownfield.

    /lp-kickoff must NEVER block with 'you must run X first' in a fresh repo.
    """
    errors = []
    fixture = make_fixture(None)
    try:
        # Isolate cache dir so a prior run doesn't poison the result
        cache = Path(tempfile.mkdtemp(prefix="lp-prereq-cache-"))
        env = dict(os.environ)
        env["LP_CACHE_DIR"] = str(cache)
        env["LP_REPO_ROOT"] = str(fixture)
        result = subprocess.run(
            [PREREQ_SH, "--mode=full", "--command=lp-kickoff", f"--repo-root={fixture}"],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            errors.append(
                f"cold start full-mode: exited {result.returncode}. "
                f"stderr: {result.stderr[:400]}"
            )
        cleanup(cache)
    finally:
        cleanup(fixture)
    return errors


def test_realpath_confinement_on_brainstorms() -> list[str]:
    """Invariant: a hostile brainstorms_dir = '../../etc' is rejected by the loader.

    /lp-kickoff then creates the DEFAULT directory (not the hostile one).
    """
    errors = []
    fixture = make_fixture("""
paths:
  brainstorms_dir: "../../../etc/evil"
""")
    try:
        cfg = load(fixture)
        if ".." in cfg["paths"]["brainstorms_dir"]:
            errors.append(
                f"hostile brainstorms_dir not rejected: {cfg['paths']['brainstorms_dir']!r}"
            )
        if not any("brainstorms_dir" in e for e in cfg["__errors__"]):
            errors.append(
                f"hostile brainstorms_dir: expected error, got {cfg['__errors__']}"
            )
        # Default should still be intact
        if cfg["paths"]["brainstorms_dir"] != "docs/brainstorms":
            errors.append(
                f"fallback to default after rejection failed: {cfg['paths']['brainstorms_dir']!r}"
            )
    finally:
        cleanup(fixture)
    return errors


def test_nondestructive_sibling_paths() -> list[str]:
    """Invariant: scaffolding brainstorms_dir doesn't touch sibling docs/ subdirs.

    We simulate mkdir -p and verify existing content is untouched.
    """
    errors = []
    fixture = make_fixture(
        None,
        extra_files={
            "docs/architecture/EXISTING.md": "do not touch",
            "docs/notes/mine.md": "also do not touch",
        },
    )
    try:
        # Simulate what lp-kickoff Step 0.2 does: mkdir -p docs/brainstorms
        (fixture / "docs" / "brainstorms").mkdir(parents=True, exist_ok=True)

        # Sibling content must still exist and be unchanged
        for rel, expected in [
            ("docs/architecture/EXISTING.md", "do not touch"),
            ("docs/notes/mine.md", "also do not touch"),
        ]:
            p = fixture / rel
            if not p.exists():
                errors.append(f"sibling {rel} was deleted")
            elif p.read_text() != expected:
                errors.append(f"sibling {rel} content changed")

        # brainstorms_dir must exist
        if not (fixture / "docs" / "brainstorms").is_dir():
            errors.append("docs/brainstorms was not created")
    finally:
        cleanup(fixture)
    return errors


def test_kickoff_command_frontmatter() -> list[str]:
    """Invariant: the lp-kickoff command file is well-formed and references Step 0."""
    errors = []
    kickoff = REPO_ROOT / "plugins" / "launchpad" / "commands" / "lp-kickoff.md"
    if not kickoff.is_file():
        errors.append(f"{kickoff} missing")
        return errors
    content = kickoff.read_text()
    if "name: lp-kickoff" not in content:
        errors.append("lp-kickoff.md missing 'name: lp-kickoff' frontmatter")
    if "Step 0" not in content:
        errors.append("lp-kickoff.md is missing Step 0 section (contract)")
    if "paths.brainstorms_dir" not in content:
        errors.append("lp-kickoff.md does not reference paths.brainstorms_dir")
    if "/lp-define" not in content:
        errors.append("lp-kickoff.md does not suggest /lp-define on completion")
    return errors


def main() -> int:
    tests = [
        ("cold_start_default_path", test_cold_start_default_path),
        ("custom_brainstorms_dir_honored", test_custom_brainstorms_dir_honored),
        ("prereq_full_mode_cold_start", test_prereq_full_mode_cold_start),
        ("realpath_confinement_on_brainstorms", test_realpath_confinement_on_brainstorms),
        ("nondestructive_sibling_paths", test_nondestructive_sibling_paths),
        ("kickoff_command_frontmatter", test_kickoff_command_frontmatter),
    ]
    all_errors = []
    for name, test in tests:
        errs = test()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: kickoff acceptance")
        for e in all_errors:
            print(e)
        return 1

    print(f"PASS: kickoff acceptance ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
