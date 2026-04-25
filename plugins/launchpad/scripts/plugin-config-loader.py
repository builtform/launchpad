#!/usr/bin/env python3
"""Load and validate `.launchpad/config.yml` once per process.

Contract:
  - Parse YAML into a single merged config object (pipeline / commands / paths)
  - Realpath-confinement on all `paths.*` values — reject absolute paths,
    `..` segments, and paths that resolve outside the repo root
  - Section-by-section re-parse on error: a malformed `commands:` does NOT
    prevent `/lp-kickoff` (which only reads `paths:`) from running. Unused
    sections log a warning; required sections fail hard.
  - `commands.*` is always-array; any `""` or scalar is coerced to a list
  - Caller queries the parsed object; never re-reads the file.

Usage (CLI):
    plugin-config-loader.py [--repo-root PATH] [--section pipeline|commands|paths|all]

Exit code 0 on success; 1 on unrecoverable parse/validation error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


# --- YAML parsing: minimal, no external dep ---
# PyYAML would be ideal but we don't want to add it to the vendor bundle just
# for config loading. Use a tiny hand-rolled parser that handles the shapes
# config.yml actually uses (flat dict, nested dict, lists, scalars).
# If config.yml grows more complex shapes, swap to yaml.safe_load. For now,
# tomllib can't help (TOML), and json is too rigid.
#
# Decision: use PyYAML from the _vendor dir if available, else bootstrap.


# Bootstrap the vendor dir onto sys.path before any YAML import.
_VENDOR = Path(__file__).resolve().parent / "plugin_stack_adapters" / "_vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))


def _load_yaml_safe(text: str) -> Any:
    """Load YAML using vendored PyYAML (falls back to system if vendor missing)."""
    try:
        import yaml  # type: ignore
    except ImportError:
        raise ConfigError(
            "PyYAML not available; vendor it into scripts/plugin-stack-adapters/_vendor/ "
            "or install system-wide."
        )
    return yaml.safe_load(text)


class ConfigError(Exception):
    """Raised for config-loading failures the caller should surface to the user."""


# --- Path confinement ---

def _confine_path(raw: str, repo_root: Path, key: str) -> str:
    """Validate a single `paths.*` value is inside the repo root.

    Rejects:
      - absolute paths (anything starting with '/')
      - paths containing '..' segments
      - paths that resolve outside repo_root after realpath expansion
    """
    if not isinstance(raw, str):
        raise ConfigError(f"paths.{key}: expected string, got {type(raw).__name__}")
    if raw.startswith("/"):
        raise ConfigError(f"paths.{key}={raw!r}: absolute paths are not allowed")
    if ".." in Path(raw).parts:
        raise ConfigError(f"paths.{key}={raw!r}: '..' segments are not allowed")

    # Resolve and verify containment
    resolved = (repo_root / raw).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        raise ConfigError(
            f"paths.{key}={raw!r} resolves to {resolved}, outside repo root {repo_root}"
        )
    return raw


# --- Command coercion ---

def _coerce_commands(commands: dict[str, Any]) -> dict[str, list[str]]:
    """Normalize every commands.* value to a list[str].

    Scalars become single-element lists; empty strings become empty lists
    (skip marker); missing keys become empty lists.
    """
    out: dict[str, list[str]] = {}
    for key in ("test", "typecheck", "lint", "format", "build"):
        val = commands.get(key, [])
        if isinstance(val, str):
            val = [val] if val else []
        elif isinstance(val, list):
            # Every item must be a string. Previously str(v) coerced YAML
            # scalars like true/123 or mappings into command strings —
            # silently turning typos into executed bogus commands. Refuse
            # non-strings with a clear ConfigError instead.
            cleaned: list[str] = []
            for i, v in enumerate(val):
                if v is None or (isinstance(v, str) and v == ""):
                    continue
                if not isinstance(v, str):
                    raise ConfigError(
                        f"commands.{key}[{i}]: expected string, got "
                        f"{type(v).__name__} (value={v!r}). Quote the "
                        "value in YAML if it should be passed literally."
                    )
                cleaned.append(v)
            val = cleaned
        else:
            raise ConfigError(f"commands.{key}: expected list or string, got {type(val).__name__}")
        out[key] = val
    return out


# --- Section-by-section loader ---

def load(repo_root: Path | None = None, path: Path | None = None) -> dict[str, Any]:
    """Load and validate .launchpad/config.yml.

    Returns a dict with keys: pipeline, commands, paths, overwrite, audit.
    Each section is validated independently — a failure in one section
    surfaces a warning but does not prevent other sections from being returned
    (the caller can check for '__errors__' key to detect partial loads).
    """
    repo_root = (repo_root or Path.cwd()).resolve()
    path = path or (repo_root / ".launchpad" / "config.yml")

    result: dict[str, Any] = {
        "pipeline": {},
        "commands": {"test": [], "typecheck": [], "lint": [], "format": [], "build": []},
        "paths": {
            "architecture_dir": "docs/architecture",
            "tasks_dir": "docs/tasks",
            "sections_dir": "docs/tasks/sections",
            "plans_file_pattern": "docs/tasks/sections/{section_name}-plan.md",
            "reports_dir": "docs/reports",
            "solutions_dir": "docs/solutions",
            "brainstorms_dir": "docs/brainstorms",
            "harness_dir": ".harness",
            "launchpad_dir": ".launchpad",
        },
        "overwrite": "prompt",
        "audit": {"committed": False},
        "__errors__": [],
    }

    if not path.is_file():
        # Missing config is not an error — downstream code uses defaults.
        return result

    text = path.read_text(encoding="utf-8")
    try:
        raw = _load_yaml_safe(text) or {}
    except Exception as e:
        raise ConfigError(f"{path}: YAML parse error: {e}")

    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top-level must be a mapping, got {type(raw).__name__}")

    # --- pipeline section ---
    if "pipeline" in raw:
        if isinstance(raw["pipeline"], dict):
            result["pipeline"] = raw["pipeline"]
        else:
            result["__errors__"].append("pipeline: expected mapping")

    # --- commands section ---
    if "commands" in raw:
        if isinstance(raw["commands"], dict):
            try:
                result["commands"] = _coerce_commands(raw["commands"])
            except ConfigError as e:
                result["__errors__"].append(str(e))
        else:
            result["__errors__"].append("commands: expected mapping")

    # --- paths section (critical: realpath-confinement) ---
    if "paths" in raw:
        if isinstance(raw["paths"], dict):
            for key, val in raw["paths"].items():
                try:
                    confined = _confine_path(val, repo_root, key)
                    result["paths"][key] = confined
                except ConfigError as e:
                    result["__errors__"].append(str(e))
        else:
            result["__errors__"].append("paths: expected mapping")

    # --- overwrite ---
    if "overwrite" in raw:
        val = raw["overwrite"]
        if val in ("skip", "prompt", "force"):
            result["overwrite"] = val
        else:
            result["__errors__"].append(f"overwrite={val!r}: expected skip|prompt|force")

    # --- audit ---
    if "audit" in raw and isinstance(raw["audit"], dict):
        result["audit"]["committed"] = bool(raw["audit"].get("committed", False))

    return result


# --- CLI entry ---

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    ap.add_argument("--section", choices=["pipeline", "commands", "paths", "overwrite", "audit", "all"], default="all")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if any section had errors")
    args = ap.parse_args()

    try:
        cfg = load(Path(args.repo_root))
    except ConfigError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1

    errors = cfg.pop("__errors__")
    if errors:
        for err in errors:
            print(f"WARN: {err}", file=sys.stderr)
        if args.strict:
            return 1

    if args.section == "all":
        print(json.dumps(cfg, indent=2))
    else:
        print(json.dumps(cfg[args.section], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
