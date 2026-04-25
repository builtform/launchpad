#!/usr/bin/env python3
"""Stack detector tests — allowlist enforcement + size cap + polyglot detection.

Creates ephemeral fixture repos under /tmp with mktemp-style isolation and
verifies the detector behaves per spec.

Run:
  python3 plugins/launchpad/scripts/tests/test_detector.py

Exit 0 on pass, 1 on failure.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Import the detector module directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "stack_detector",
    Path(__file__).resolve().parent.parent / "plugin-stack-detector.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

detect = _mod.detect
find_manifests = _mod.find_manifests
MANIFEST_ALLOWLIST = _mod.MANIFEST_ALLOWLIST
MAX_MANIFEST_BYTES = _mod.MAX_MANIFEST_BYTES
DetectorError = _mod.DetectorError


def make_fixture(files: dict[str, str]) -> Path:
    """Create a temp dir populated with the given files. Caller must clean up."""
    d = Path(tempfile.mkdtemp(prefix="lp-detector-test-"))
    for path, content in files.items():
        full = d / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return d


def cleanup(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)


def test_ts_monorepo() -> list[str]:
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({
            "name": "ts-mono",
            "workspaces": ["apps/*", "packages/*"],
            "dependencies": {"next": "15.0.0", "hono": "4.0.0", "@prisma/client": "5.0.0"},
        }),
    })
    try:
        report = detect(fixture)
        if "ts_monorepo" not in report["stacks"]:
            errors.append(f"ts_monorepo fixture: expected ts_monorepo, got {report['stacks']}")
        if "next.js" not in report["frameworks"] or "hono" not in report["frameworks"]:
            errors.append(f"ts_monorepo fixture: expected next.js + hono in frameworks, got {report['frameworks']}")
        if report["polyglot"]:
            errors.append("ts_monorepo fixture: polyglot=True, expected False")
    finally:
        cleanup(fixture)
    return errors


def test_polyglot() -> list[str]:
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"name": "poly", "dependencies": {"next": "15.0.0"}}),
        "pyproject.toml": '[project]\nname = "poly"\ndependencies = ["django"]\n',
    })
    try:
        report = detect(fixture)
        if "ts_monorepo" not in report["stacks"]:
            errors.append(f"polyglot: missing ts_monorepo: {report['stacks']}")
        if "python_django" not in report["stacks"]:
            errors.append(f"polyglot: missing python_django: {report['stacks']}")
        if not report["polyglot"]:
            errors.append("polyglot: polyglot=False, expected True")
    finally:
        cleanup(fixture)
    return errors


def test_zero_manifest() -> list[str]:
    errors = []
    fixture = make_fixture({"README.md": "docs-only repo"})
    try:
        report = detect(fixture)
        if not report["zero_manifest"]:
            errors.append(f"zero-manifest: zero_manifest=False, expected True")
        if report["stacks"] != ["generic"]:
            errors.append(f"zero-manifest: expected ['generic'], got {report['stacks']}")
    finally:
        cleanup(fixture)
    return errors


def test_manifest_size_cap() -> list[str]:
    errors = []
    # Build a manifest just over the cap.
    huge = '{"name": "huge", "x": "' + ("A" * (MAX_MANIFEST_BYTES + 100)) + '"}'
    fixture = make_fixture({"package.json": huge})
    try:
        try:
            detect(fixture)
            errors.append("size cap: detector accepted >1MB manifest, expected DetectorError")
        except DetectorError as e:
            if "cap" not in str(e).lower():
                errors.append(f"size cap: error did not mention cap: {e}")
    finally:
        cleanup(fixture)
    return errors


def test_allowlist_denies_env() -> list[str]:
    """The detector's allowlist must NOT open .env* files.

    We verify this by (a) creating a fixture with ONLY a .env and ensuring
    the detector reports zero_manifest (didn't find .env), and (b) inspecting
    MANIFEST_ALLOWLIST to confirm .env isn't in it.
    """
    errors = []
    # Sanity-check the allowlist itself
    forbidden = [".env", ".env.local", ".npmrc", "secrets.yml", "credentials.json"]
    for f in forbidden:
        if f in MANIFEST_ALLOWLIST:
            errors.append(f"allowlist regression: {f!r} is in MANIFEST_ALLOWLIST (must NOT be)")

    # Behavioral test: repo with only .env.local should fall through to generic
    fixture = make_fixture({
        ".env.local": "DATABASE_URL=postgres://user:pass@localhost/db",
        ".env": "SECRET=abc123",
    })
    try:
        report = detect(fixture)
        if not report["zero_manifest"]:
            errors.append(
                f".env-only fixture: detector found manifests, expected zero_manifest. "
                f"Report: {report}"
            )
    finally:
        cleanup(fixture)
    return errors


def test_excluded_dirs() -> list[str]:
    """Detector must not walk into node_modules, .venv, etc."""
    errors = []
    fixture = make_fixture({
        "node_modules/some-dep/package.json": '{"name": "a-dep"}',
        ".venv/lib/package.json": '{"name": "another"}',
        # Real manifest at root
        "package.json": '{"name": "real-root", "dependencies": {"express": "4"}}',
    })
    try:
        manifests = find_manifests(fixture)
        manifest_paths = {str(m.relative_to(fixture)) for m in manifests}
        if "package.json" not in manifest_paths:
            errors.append(f"excluded_dirs: missing root manifest: {manifest_paths}")
        if any("node_modules" in p for p in manifest_paths):
            errors.append(f"excluded_dirs: detector walked into node_modules: {manifest_paths}")
        if any(".venv" in p for p in manifest_paths):
            errors.append(f"excluded_dirs: detector walked into .venv: {manifest_paths}")
    finally:
        cleanup(fixture)
    return errors


def test_deterministic_order() -> list[str]:
    """Stacks + manifests must be sorted alphabetically so the generator
    produces bit-identical TECH_STACK.md across runs on semantically-equivalent
    repos. Without this, the file churns on every run even when nothing
    semantic changed."""
    errors = []
    # Polyglot fixture — order should be alphabetical: python_django before ts_monorepo
    fixture = make_fixture({
        "package.json": '{"dependencies": {"next": "15"}}',
        "pyproject.toml": '[project]\nname="x"\ndependencies=["django"]\n',
    })
    try:
        result = detect(fixture)
        stacks = result.get("stacks", [])
        if stacks != sorted(stacks):
            errors.append(f"stacks not sorted: {stacks}")
        if stacks and stacks != ["python_django", "ts_monorepo"]:
            errors.append(f"expected [python_django, ts_monorepo], got {stacks}")

        manifests = result.get("manifests", [])
        # Manifest basenames (paths are absolute) should come out in sorted order
        basenames = [m.rsplit("/", 1)[-1] for m in manifests]
        if basenames != sorted(basenames):
            errors.append(f"manifests not sorted: {basenames}")

        # Run detect twice in a row with no file changes — must be identical
        result2 = detect(fixture)
        if result.get("stacks") != result2.get("stacks"):
            errors.append(f"non-idempotent stacks: {result['stacks']} vs {result2['stacks']}")
        if result.get("manifests") != result2.get("manifests"):
            errors.append(f"non-idempotent manifests: {result['manifests']} vs {result2['manifests']}")
    finally:
        cleanup(fixture)
    return errors


def main() -> int:
    all_errors = []
    for name, test in [
        ("ts_monorepo", test_ts_monorepo),
        ("polyglot", test_polyglot),
        ("zero_manifest", test_zero_manifest),
        ("size_cap", test_manifest_size_cap),
        ("allowlist_denies_env", test_allowlist_denies_env),
        ("excluded_dirs", test_excluded_dirs),
        ("deterministic_order", test_deterministic_order),
    ]:
        errs = test()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: stack detector tests")
        for e in all_errors:
            print(e)
        return 1

    print("PASS: stack detector (7 tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
