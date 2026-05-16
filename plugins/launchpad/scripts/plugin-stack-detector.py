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
from pathlib import Path
from typing import Any

# Vendored deps (PyYAML, MarkupSafe, Jinja2). Injected before any YAML use.
_SCRIPT_DIR = Path(__file__).resolve().parent
_VENDOR = _SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

# TOML parsing: tomllib is stdlib only on Python 3.11+. The plugin commands
# invoke bare `python3`, which on macOS or older Linux distributions can be
# 3.9/3.10. Fall back to `tomli` (the upstream package tomllib was forked
# from, API-compatible) when stdlib tomllib is missing. If neither is
# available, raise a clear actionable error at the point where toml parsing
# is actually attempted, not at module import time — projects without any
# pyproject.toml or Cargo.toml never need toml parsing and should still run.
try:
    import tomllib  # type: ignore[import-not-found]

    _TOML_IMPORT_ERROR: str | None = None
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]

        _TOML_IMPORT_ERROR = None
    except ImportError:
        tomllib = None  # type: ignore[assignment]
        _TOML_IMPORT_ERROR = (
            "TOML parsing requires Python 3.11+ (stdlib tomllib) or the "
            "`tomli` package (pip install tomli). Detected Python "
            f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]} "
            "with neither available. Projects with no pyproject.toml / "
            "Cargo.toml are unaffected; install tomli or upgrade Python "
            "to detect those manifests."
        )

# Strict allowlist — detector opens exactly these filenames and nothing else.
MANIFEST_ALLOWLIST = frozenset(
    [
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "Gemfile",
        "composer.json",
    ]
)

# v2.0 single-source enforcement (HANDSHAKE §8): the broader brownfield-
# detection set is owned by `cwd_state.py` and shared across v1 + v2 surfaces.
# This module IMPORTS it (does NOT redefine it). The stack-detector itself
# uses the narrower MANIFEST_ALLOWLIST above for its own bounded-walk
# parsing logic; the imported constant is exposed for the single-source
# CI lint assertion + identity check (test_brownfield_manifests_single_source.py).
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from cwd_state import (  # noqa: E402, F401  (single-source enforcement)
    BROWNFIELD_MANIFESTS,
)

# Noise directories that bloat the walk with dep/build output.
EXCLUDED_DIRS = frozenset(
    [
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
    ]
)

# 1MB cap per manifest — anything larger is almost certainly not what we expect.
MAX_MANIFEST_BYTES = 1 * 1024 * 1024

# Phase 6 v2.1 Rails detection: matches `gem "rails"` or `gem 'rails'` lines
# in a Gemfile. Module-level compile (cycle-3 perf P1-2 mirror).
import re as _re  # noqa: E402  (re-imported here under module-local alias by design)

_GEMFILE_RAILS_REGEX = _re.compile(r"""(?m)^\s*gem\s+["']rails["']""")


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

    root_real = root.resolve()

    def _safe_candidate(candidate: Path) -> Path | None:
        """Refuse the candidate if any of:
        - it is a symlink (file or via parent dir)
        - its real path resolves outside root_real
        - it is not actually a regular file
        Returns the candidate Path on success, None on rejection. The
        previous walk simply called `is_file()`, which silently followed
        symlinks; a hostile repo containing `package.json -> ../secret.json`
        or a symlinked workspace dir could read files outside the repo via
        the manifest allowlist.
        """
        try:
            if candidate.is_symlink():
                return None
            if not candidate.is_file():
                return None
            real = candidate.resolve(strict=True)
            if not real.is_relative_to(root_real):
                return None
            return candidate
        except (OSError, ValueError):
            return None

    # Depth 0: repo root itself
    for name in MANIFEST_ALLOWLIST:
        sc = _safe_candidate(root / name)
        if sc is not None:
            found.append(sc)

    # Depth 1: immediate subdirs (excluding noise). Sort iterdir() explicitly
    # because filesystem iteration order is not guaranteed stable across mtime
    # changes or re-indexes. Skip symlinked directories — they can point
    # outside the repo, which would let manifests there be read despite
    # the allowlist.
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if child.is_symlink():
            continue
        if not child.is_dir():
            continue
        if child.name in EXCLUDED_DIRS or child.name.startswith("."):
            continue
        for name in MANIFEST_ALLOWLIST:
            sc = _safe_candidate(child / name)
            if sc is not None:
                found.append(sc)

    # Workspace roots: declared by the user via pnpm-workspace.yaml or
    # package.json's workspaces field. Trusted because the user added them.
    # Same symlink/realpath checks apply — a workspace pattern like
    # `apps/*` could glob a symlinked directory the user did not intend
    # to expose.
    for ws_dir in _read_workspace_roots(root):
        if ws_dir.is_symlink():
            continue
        if ws_dir.name in EXCLUDED_DIRS or ws_dir.name.startswith("."):
            continue
        for name in MANIFEST_ALLOWLIST:
            sc = _safe_candidate(ws_dir / name)
            if sc is not None:
                found.append(sc)

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
    if tomllib is None:
        raise DetectorError(_TOML_IMPORT_ERROR or "tomllib unavailable")
    data = _safe_read(path)
    return tomllib.loads(data.decode("utf-8"))


def parse_cargo_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:
        raise DetectorError(_TOML_IMPORT_ERROR or "tomllib unavailable")
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
        # v2.1.6 BL-345: extend the detector to recognise additional v2.1
        # active stacks that previously fell through to `generic`. Each
        # entry adds one framework token used by downstream stack-id
        # mapping; the actual stack-id assignment below picks the most
        # specific match.
        if "astro" in deps:
            frameworks.append("astro")
        if "@11ty/eleventy" in deps:
            frameworks.append("eleventy")
        if "expo" in deps:
            frameworks.append("expo")
        if "@supabase/supabase-js" in deps or "@supabase/auth-helpers-nextjs" in deps:
            frameworks.append("supabase")
        # Map to ts_monorepo ONLY when the project IS a monorepo AND has
        # the framework profile the adapter is shaped for: pnpm + Turborepo
        # + apps/web (Next), apps/api (Hono), packages/db (Prisma). Three
        # gates, all must hold:
        #
        #   (1) Monorepo signal — workspaces declared OR turbo dependency.
        #       A single-app project gets generic regardless of frameworks.
        #
        #   (2) TypeScript signal — `typescript` dependency OR a
        #       tsconfig.json at the manifest's directory. A pure-JS
        #       monorepo, or a Python/Go workspace that happens to have a
        #       package.json, gets generic — not TS-shaped commands.
        #
        #   (3) Relevant framework signal — at least one of Next.js, Hono,
        #       or Prisma. A monorepo of unrelated TS libraries (eslint
        #       configs, build tools, design tokens) gets generic so the
        #       doc generator does not seed Next/Hono/Prisma prose for a
        #       project that uses none of them.
        #
        # Any failed gate falls back to generic. Detected frameworks are
        # still surfaced in the report so the doc generator can mention
        # them; only the *stack template* changes.
        is_monorepo = bool(content.get("workspaces")) or "turbo" in deps
        has_typescript = (
            "typescript" in deps or (path.parent / "tsconfig.json").is_file()
        )
        has_relevant_framework = any(
            fw in frameworks for fw in ("next.js", "hono", "prisma")
        )
        # v2.1.6 BL-345: stack-id mapping for non-monorepo single-stack
        # projects. Specificity order: astro > next > eleventy > expo >
        # ts_monorepo > generic. The first matching framework picks the
        # stack id; downstream adapters handle composition when multiple
        # frameworks coexist.
        if "astro" in frameworks:
            stack = "astro"
        elif is_monorepo and has_typescript and has_relevant_framework:
            stack = "ts_monorepo"
        elif "next.js" in frameworks and not is_monorepo:
            stack = "nextjs_standalone"
        elif "eleventy" in frameworks:
            stack = "generic"  # v2.2 candidate; ships under generic for v2.1
        elif "expo" in frameworks:
            stack = "generic"  # v2.2 candidate
        else:
            stack = "generic"
        return {"stack": stack, "frameworks": frameworks, "evidence": str(path)}

    if name == "pyproject.toml":
        frameworks = []
        deps_section = (
            content.get("project", {}).get("dependencies", [])
            or content.get("tool", {}).get("poetry", {}).get("dependencies", {})
            or []
        )
        dep_str = (
            " ".join(deps_section)
            if isinstance(deps_section, list)
            else " ".join(deps_section.keys())
        )
        if "django" in dep_str.lower():
            frameworks.append("django")
        if "fastapi" in dep_str.lower():
            frameworks.append("fastapi")
        if "flask" in dep_str.lower():
            frameworks.append("flask")
        # v2.1.6 BL-345: any Python project (FastAPI, Flask, plain-Python)
        # now maps to `python_generic` instead of falling through to
        # `generic`. The doc generator gains Python-specific scaffolding
        # (pytest, ruff, pyright commands) without seeding Django-specific
        # commands inappropriately. Django still maps to `python_django`
        # for its specific scaffolding needs (manage.py migrate, etc.).
        if "django" in frameworks:
            stack = "python_django"
        elif frameworks:  # any Python framework detected
            stack = "python_generic"
        else:
            # No framework detected — still mark as python_generic so
            # the Python stack family (pytest / ruff / pyright commands)
            # applies. The pre-v2.1.6 fall-through to `generic` produced
            # broken pnpm-based bootstrap output for every plain-Python
            # project; python_generic is strictly safer.
            stack = "python_generic"
        return {"stack": stack, "frameworks": frameworks, "evidence": str(path)}

    if name == "go.mod":
        return {"stack": "go_cli", "frameworks": ["go"], "evidence": str(path)}

    if name == "Cargo.toml":
        # v1 has no rust adapter; fall through to generic
        return {"stack": "generic", "frameworks": ["rust"], "evidence": str(path)}

    if name == "Gemfile":
        # Phase 6 v2.1: detect Rails when `gem "rails"` is present. Without
        # rails (Sinatra etc.) → fallthrough to generic so Phase 6 ships
        # detection groundwork only; Rails-specific reviewer + framework-axis
        # wire-through arrive in v2.2 BL.
        raw = content.get("raw", "")
        if isinstance(raw, str) and _GEMFILE_RAILS_REGEX.search(raw):
            return {"stack": "rails", "frameworks": ["rails"], "evidence": str(path)}
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

    # Two-pass: first record (manifest_name, stack) for each manifest; then
    # aggregate stacks at the language level so a TS monorepo's many
    # sub-package.json files do not split into ts_monorepo + spurious
    # generic. A real polyglot (TS + Python, TS + Go, etc.) keeps both
    # because the spurious "generic" contribution only ever comes from the
    # SAME language family that already produced the strong stack signal.
    per_manifest: list[tuple[str, str]] = []  # (manifest filename, stack)
    all_frameworks: list[str] = []
    for m in manifests:
        result = detect_from_manifest(m)
        if not result:
            continue
        per_manifest.append((m.name, result["stack"]))
        for fw in result["frameworks"]:
            if fw not in all_frameworks:
                all_frameworks.append(fw)

    package_json_stacks = {s for n, s in per_manifest if n == "package.json"}
    pyproject_stacks = {s for n, s in per_manifest if n == "pyproject.toml"}

    # Collapse same-language splits: if package.json produced ts_monorepo
    # anywhere, every other package.json's "generic" contribution is just a
    # sub-package of that monorepo, not a separate stack. Same for
    # python_django vs generic from pyproject.toml.
    #
    # v2.1.6 round-4 review fix (Codex P1 #1): BL-345 extended the
    # per-manifest classifier to emit `nextjs_standalone` for single-app
    # Next.js (no workspaces) and `python_generic` for non-Django Python.
    # That makes a TURBOREPO's `apps/web/package.json` return
    # `nextjs_standalone` because workspaces live in ROOT's package.json,
    # not the sub-manifest. Pre round-4 the suppress logic only collapsed
    # the LEGACY `generic` sub-package contribution; the new BL-345
    # variants leaked through, marking a single Turborepo as polyglot
    # `[nextjs_standalone, ts_monorepo]`. The fix extends the collapse
    # rule to cover both legacy `generic` and the BL-345 single-app
    # variants — every package.json sub-contribution is suppressed when
    # the root manifest has already produced `ts_monorepo`. The
    # ancestor-walk alternative is architecturally cleaner but more
    # invasive; the suppress-list extension matches the existing pattern
    # and ships in v2.1.6's deferred-cleanup space.
    suppress: set[tuple[str, str]] = set()
    _TS_SUB_PACKAGE_STACKS = ("generic", "nextjs_standalone", "astro")
    _PY_SUB_PACKAGE_STACKS = ("generic", "python_generic")
    if "ts_monorepo" in package_json_stacks:
        for sub in _TS_SUB_PACKAGE_STACKS:
            if sub in package_json_stacks:
                suppress.add(("package.json", sub))
    if "python_django" in pyproject_stacks:
        for sub in _PY_SUB_PACKAGE_STACKS:
            if sub in pyproject_stacks:
                suppress.add(("pyproject.toml", sub))

    seen_stacks: set[str] = set()
    stacks: list[str] = []
    for n, s in per_manifest:
        if (n, s) in suppress:
            continue
        if s not in seen_stacks:
            stacks.append(s)
            seen_stacks.add(s)

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
        "manifests": [
            str(m) for m in manifests
        ],  # manifests already sorted in find_manifests()
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
