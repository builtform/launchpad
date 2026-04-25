#!/usr/bin/env python3
"""Detect which stack adapters apply to a project by inspecting its manifests.

Security constraints:
  - Manifest allowlist (exactly these, no others):
    package.json, pyproject.toml, Cargo.toml, go.mod, Gemfile, composer.json
  - MUST NOT read .env*, .npmrc, secrets.yml, ~/.docker/config.json, or any
    file outside the allowlist. A denylist assertion in tests enforces this.
  - Bounded walk: repo root + 1 level deep only. Hard-excludes noise dirs.
  - Size cap: reject any manifest > 1MB with a clear error.
  - Safe parsers: json.load, yaml.safe_load, tomllib.loads — never yaml.load.

Output: JSON to stdout listing detected stacks + primary framework flavor.
{"stacks": ["ts_monorepo"], "frameworks": ["next.js", "hono"], "polyglot": false}
"""
from __future__ import annotations

import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

# Vendored deps (PyYAML, MarkupSafe, Jinja2). Injected before any YAML use.
_SCRIPT_DIR = Path(__file__).resolve().parent
_VENDOR = _SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

# Strict allowlist — detector opens exactly these filenames and nothing else.
MANIFEST_ALLOWLIST = frozenset([
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
])

# Noise directories that bloat the walk with dep/build output.
EXCLUDED_DIRS = frozenset([
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    ".next",
    "target",
    "build",
    "vendor",
    ".git",
    ".turbo",
    ".cache",
])

# 1MB cap per manifest — anything larger is almost certainly not what we expect.
MAX_MANIFEST_BYTES = 1 * 1024 * 1024


class DetectorError(Exception):
    """Raised when detection fails in a way the caller should surface."""


def _read_workspace_roots(root: Path) -> list[Path]:
    """Read declared workspace roots from pnpm-workspace.yaml or package.json.

    Returns a list of repo-relative directory paths (Path objects, not strings)
    that are the actual workspace package roots — e.g. apps/web, apps/api,
    packages/db. These are TRUSTED roots: the user declared them themselves.

    Glob patterns like 'apps/*' and 'packages/*' are expanded literally; any
    pattern that escapes the repo root (absolute, '..', symlink) is rejected.

    Falls back silently to [] if neither manifest declares workspaces — mirrors
    the bounded-walk default for non-monorepo projects.
    """
    import glob as _glob

    patterns: list[str] = []

    # pnpm-workspace.yaml: top-level `packages:` array of glob strings
    pnpm_ws = root / "pnpm-workspace.yaml"
    if pnpm_ws.is_file() and pnpm_ws.stat().st_size <= MAX_MANIFEST_BYTES:
        try:
            import yaml
            data = yaml.safe_load(pnpm_ws.read_text(encoding="utf-8")) or {}
            raw = data.get("packages") or []
            if isinstance(raw, list):
                patterns.extend(p for p in raw if isinstance(p, str))
        except Exception:
            # Bad YAML — skip silently; the depth-1 walk still covers root + 1.
            pass

    # package.json: top-level `workspaces` array (or `workspaces.packages` array)
    pkg_json = root / "package.json"
    if pkg_json.is_file() and pkg_json.stat().st_size <= MAX_MANIFEST_BYTES:
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            ws = data.get("workspaces")
            if isinstance(ws, list):
                patterns.extend(p for p in ws if isinstance(p, str))
            elif isinstance(ws, dict):
                inner = ws.get("packages")
                if isinstance(inner, list):
                    patterns.extend(p for p in inner if isinstance(p, str))
        except Exception:
            pass

    if not patterns:
        return []

    # Realpath-confined expansion: every match must resolve inside root.
    root_real = root.resolve()
    results: set[Path] = set()
    for pat in patterns:
        # Reject absolute / parent-escape patterns up-front
        if pat.startswith("/") or ".." in Path(pat).parts:
            continue
        # iglob is anchored to cwd; switch to root for the duration
        for match in _glob.iglob(str(root / pat)):
            mp = Path(match)
            if not mp.is_dir():
                continue
            try:
                if mp.resolve().is_relative_to(root_real):
                    results.add(mp)
            except (OSError, ValueError):
                continue

    return sorted(results, key=lambda p: str(p.relative_to(root)))


def find_manifests(root: Path) -> list[Path]:
    """Return all allowlisted manifests at repo root, + 1 level deep, + any
    declared workspace roots from pnpm-workspace.yaml or package.json.

    Never reads a file outside the manifest allowlist or the workspace-config
    allowlist (pnpm-workspace.yaml + package.json's workspaces field). The
    manifest allowlist applies to discovered files (if the filename isn't in
    MANIFEST_ALLOWLIST, we don't even consider it).

    Returns a deterministic, sorted-by-relative-path list so the downstream
    stack-detection and generator rendering produce bit-identical output for
    semantically-equivalent repos (idempotency).
    """
    found: list[Path] = []
    if not root.is_dir():
        raise DetectorError(f"repo root {root} is not a directory")

    # Depth 0: repo root itself
    for name in MANIFEST_ALLOWLIST:
        candidate = root / name
        if candidate.is_file():
            found.append(candidate)

    # Depth 1: immediate subdirs (excluding noise). Sort iterdir() explicitly
    # because filesystem iteration order is not guaranteed stable across mtime
    # changes or re-indexes.
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if child.name in EXCLUDED_DIRS or child.name.startswith("."):
            continue
        for name in MANIFEST_ALLOWLIST:
            candidate = child / name
            if candidate.is_file():
                found.append(candidate)

    # Workspace roots: declared by the user via pnpm-workspace.yaml or
    # package.json's workspaces field. Trusted because the user added them.
    # Realpath-confined to prevent escape via symlink or '..'.
    for ws_dir in _read_workspace_roots(root):
        if ws_dir.name in EXCLUDED_DIRS or ws_dir.name.startswith("."):
            continue
        for name in MANIFEST_ALLOWLIST:
            candidate = ws_dir / name
            if candidate.is_file():
                found.append(candidate)

    # Final deterministic ordering: sort by path relative to root so the
    # order is reproducible regardless of which directory iteration flip
    # any future filesystem might produce. Dedup since workspace roots may
    # overlap with depth-1 children.
    seen: set[Path] = set()
    deduped: list[Path] = []
    for p in sorted(found, key=lambda x: str(x.relative_to(root))):
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def _safe_read(path: Path) -> bytes:
    """Read a manifest safely: enforce size cap, return raw bytes.

    Explicit IOError for any size-cap breach — no silent truncation.
    """
    size = path.stat().st_size
    if size > MAX_MANIFEST_BYTES:
        raise DetectorError(
            f"manifest {path} is {size} bytes (> {MAX_MANIFEST_BYTES} cap); "
            "refusing to read — unusually large manifests are almost never legitimate"
        )
    return path.read_bytes()


def parse_package_json(path: Path) -> dict[str, Any]:
    data = _safe_read(path)
    return json.loads(data)


def parse_pyproject_toml(path: Path) -> dict[str, Any]:
    data = _safe_read(path)
    return tomllib.loads(data.decode("utf-8"))


def parse_cargo_toml(path: Path) -> dict[str, Any]:
    data = _safe_read(path)
    return tomllib.loads(data.decode("utf-8"))


def parse_go_mod(path: Path) -> dict[str, Any]:
    """go.mod isn't TOML/JSON — line-based. Extract module name only."""
    data = _safe_read(path)
    text = data.decode("utf-8")
    module = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("module "):
            module = line.split(None, 1)[1].strip()
            break
    return {"module": module, "raw": text}


def parse_gemfile(path: Path) -> dict[str, Any]:
    data = _safe_read(path)
    return {"raw": data.decode("utf-8", errors="replace")}


def parse_composer_json(path: Path) -> dict[str, Any]:
    data = _safe_read(path)
    return json.loads(data)


PARSERS = {
    "package.json": parse_package_json,
    "pyproject.toml": parse_pyproject_toml,
    "Cargo.toml": parse_cargo_toml,
    "go.mod": parse_go_mod,
    "Gemfile": parse_gemfile,
    "composer.json": parse_composer_json,
}


def detect_from_manifest(path: Path) -> dict[str, Any]:
    """Return {'stack': StackId, 'frameworks': list[str], 'evidence': Path} or {} if unclear."""
    name = path.name
    parser = PARSERS[name]
    content = parser(path)

    if name == "package.json":
        deps = {**content.get("dependencies", {}), **content.get("devDependencies", {})}
        frameworks = []
        if "next" in deps:
            frameworks.append("next.js")
        if "hono" in deps:
            frameworks.append("hono")
        if "react" in deps:
            frameworks.append("react")
        if "express" in deps:
            frameworks.append("express")
        if "@prisma/client" in deps or "prisma" in deps:
            frameworks.append("prisma")
        # Workspaces + turbo => monorepo
        is_monorepo = bool(content.get("workspaces")) or "turbo" in deps
        stack = "ts_monorepo" if is_monorepo or "next" in deps else "ts_monorepo"
        return {"stack": "ts_monorepo", "frameworks": frameworks, "evidence": str(path)}

    if name == "pyproject.toml":
        frameworks = []
        deps_section = (
            content.get("project", {}).get("dependencies", [])
            or content.get("tool", {}).get("poetry", {}).get("dependencies", {})
            or []
        )
        dep_str = " ".join(deps_section) if isinstance(deps_section, list) else " ".join(deps_section.keys())
        if "django" in dep_str.lower():
            frameworks.append("django")
        if "fastapi" in dep_str.lower():
            frameworks.append("fastapi")
        if "flask" in dep_str.lower():
            frameworks.append("flask")
        # Default to python_django adapter if Django present, else generic Python
        stack = "python_django" if "django" in frameworks else "python_django"
        return {"stack": "python_django", "frameworks": frameworks, "evidence": str(path)}

    if name == "go.mod":
        return {"stack": "go_cli", "frameworks": ["go"], "evidence": str(path)}

    if name == "Cargo.toml":
        # v1 has no rust adapter; fall through to generic
        return {"stack": "generic", "frameworks": ["rust"], "evidence": str(path)}

    if name == "Gemfile":
        # v1 has no ruby adapter; fall through to generic
        return {"stack": "generic", "frameworks": ["ruby"], "evidence": str(path)}

    if name == "composer.json":
        # v1 has no PHP adapter; fall through to generic
        return {"stack": "generic", "frameworks": ["php"], "evidence": str(path)}

    return {}


def detect(root: Path) -> dict[str, Any]:
    """Entry point. Returns the detection report for the plugin to consume."""
    manifests = find_manifests(root)
    if not manifests:
        return {
            "stacks": ["generic"],
            "frameworks": [],
            "polyglot": False,
            "manifests": [],
            "zero_manifest": True,
        }

    stacks: list[str] = []
    all_frameworks: list[str] = []
    seen_stacks = set()

    for m in manifests:
        result = detect_from_manifest(m)
        if not result:
            continue
        stack = result["stack"]
        if stack not in seen_stacks:
            stacks.append(stack)
            seen_stacks.add(stack)
        for fw in result["frameworks"]:
            if fw not in all_frameworks:
                all_frameworks.append(fw)

    if not stacks:
        stacks = ["generic"]

    # Sort stacks + frameworks alphabetically for idempotency.
    # Without this, the manifest-iteration-order drift propagates into
    # TECH_STACK.md's "Detected manifests" section, causing the generator
    # to see a diff and rewrite the file even when semantic content is
    # unchanged. Sorting guarantees bit-identical output across runs.
    stacks.sort()
    all_frameworks.sort()

    return {
        "stacks": stacks,
        "frameworks": all_frameworks,
        "polyglot": len(stacks) > 1,
        "manifests": [str(m) for m in manifests],  # manifests already sorted in find_manifests()
        "zero_manifest": False,
    }


def main() -> int:
    root = Path(os.environ.get("LP_REPO_ROOT", os.getcwd())).resolve()
    try:
        report = detect(root)
    except DetectorError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
