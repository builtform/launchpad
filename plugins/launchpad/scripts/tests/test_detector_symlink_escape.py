#!/usr/bin/env python3
"""Regression test: stack detector refuses to follow symlinks.

The detector's manifest allowlist confines reads to a small set of filenames
(package.json, pyproject.toml, etc.) under the repo root. Earlier the walk
used `is_file()`, which silently followed symlinks. A repo containing
`some-dir -> /outside` or `package.json -> ../secret.json` could trick the
detector into reading files outside the repo despite the stated
realpath-confinement contract.

This test:
  1. Creates a temp repo with a package.json symlinked to a file OUTSIDE
     the repo. Asserts the detector does NOT report that package.json in
     its manifests list, and does NOT read its contents.
  2. Creates a temp repo with a directory symlinked to one outside the
     repo, where the symlinked dir contains a package.json. Asserts the
     detector skips the symlinked dir.
  3. Creates a control repo with a normal (non-symlinked) package.json
     to confirm the safe-candidate filter does not over-block legitimate
     manifests.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

_DET_PATH = SCRIPT_DIR / "plugin-stack-detector.py"
_spec = importlib.util.spec_from_file_location("stack_detector", _DET_PATH)
_det = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_det)  # type: ignore[union-attr]
detect = _det.detect


def test_symlinked_manifest_file_skipped() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lp-symlink-") as outside_str, \
         tempfile.TemporaryDirectory(prefix="lp-repo-") as repo_str:
        outside = Path(outside_str).resolve()
        repo = Path(repo_str).resolve()
        # File outside the repo with secret-looking content
        outside_pkg = outside / "secret.json"
        outside_pkg.write_text(json.dumps({
            "name": "outside",
            "dependencies": {"next": "15"},
        }), encoding="utf-8")
        # Symlink inside the repo pointing at the outside file
        try:
            (repo / "package.json").symlink_to(outside_pkg)
        except OSError:
            # Filesystem refuses symlink (rare on CI sandboxes); skip the test.
            return errors

        report = detect(repo)
        manifests = report.get("manifests", []) or []
        # The symlinked manifest must NOT be reported.
        if any("package.json" in m for m in manifests):
            errors.append(
                f"detector reported a symlinked package.json that points "
                f"outside the repo: manifests={manifests}"
            )
        # Frameworks inferred from the outside file must NOT be present.
        if "next.js" in (report.get("frameworks") or []):
            errors.append(
                "detector picked up frameworks from a symlinked-out manifest"
            )
    return errors


def test_symlinked_directory_skipped() -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lp-symdir-") as outside_str, \
         tempfile.TemporaryDirectory(prefix="lp-repo-") as repo_str:
        outside = Path(outside_str).resolve()
        repo = Path(repo_str).resolve()
        outside_dir = outside / "rogue"
        outside_dir.mkdir()
        (outside_dir / "package.json").write_text(json.dumps({
            "name": "rogue",
            "dependencies": {"hono": "4"},
        }), encoding="utf-8")
        try:
            (repo / "rogue").symlink_to(outside_dir, target_is_directory=True)
        except OSError:
            return errors

        report = detect(repo)
        manifests = report.get("manifests", []) or []
        for m in manifests:
            real = Path(m).resolve()
            if not real.is_relative_to(repo):
                errors.append(
                    f"detector reported a manifest whose real path escapes "
                    f"the repo: {m} -> {real}"
                )
    return errors


def test_normal_manifest_still_seen() -> list[str]:
    """Control: a normal (non-symlinked) package.json must still be seen."""
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lp-control-") as repo_str:
        repo = Path(repo_str).resolve()
        (repo / "package.json").write_text(json.dumps({
            "name": "ok",
            "workspaces": ["apps/*"],
            "dependencies": {"next": "15"},
        }), encoding="utf-8")
        report = detect(repo)
        manifests = report.get("manifests", []) or []
        if not any(m.endswith("package.json") for m in manifests):
            errors.append(
                f"control: normal package.json not reported (over-blocking?): "
                f"manifests={manifests}"
            )
    return errors


def main() -> int:
    tests = [
        ("symlinked_manifest_file_skipped", test_symlinked_manifest_file_skipped),
        ("symlinked_directory_skipped", test_symlinked_directory_skipped),
        ("normal_manifest_still_seen", test_normal_manifest_still_seen),
    ]
    all_errors: list[str] = []
    for name, t in tests:
        errs = t()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: stack detector symlink escape")
        for e in all_errors:
            print(e)
        return 1

    print(f"PASS: stack detector symlink escape ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
