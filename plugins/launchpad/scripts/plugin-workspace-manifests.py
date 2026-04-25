#!/usr/bin/env python3
"""List workspace package.json paths declared by pnpm-workspace.yaml or
package.json's `workspaces` field.

Used by plugin-prereq-check.sh to invalidate the Step 0 cache when ANY
workspace manifest changes, including non-default layouts (libs/*,
services/*, etc.) that don't fall under the apps/* or packages/*
fallback paths.

Standalone helper rather than calling plugin-stack-detector.py because
this runs on EVERY prereq invocation (every L2 command's Step 0) and
spawning the full detector for cache-key purposes would defeat the
cache. This script only reads workspace configs — it does not parse
manifest content, run framework detection, or import yaml.

Output: one absolute path per line, deterministic alphabetical order.
Empty output when no workspace config / no matching manifests.

Usage:
  LP_REPO_ROOT=/path/to/repo plugin-workspace-manifests.py
"""
from __future__ import annotations

import glob as _glob
import json
import os
import sys
from pathlib import Path


def _read_pnpm_workspace_packages(pw: Path) -> list[str]:
    """Mini YAML reader scoped to pnpm-workspace.yaml's `packages:` list.
    Avoids importing yaml so this script runs even when vendored yaml is
    unavailable. Handles both block-list and inline-array forms.
    """
    if not pw.is_file():
        return []
    out: list[str] = []
    in_packages = False
    for raw in pw.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("packages:"):
            in_packages = True
            inline = line.split(":", 1)[1].strip()
            if inline.startswith("[") and inline.endswith("]"):
                inner = inline[1:-1]
                for tok in inner.split(","):
                    tok = tok.strip().strip("'").strip('"')
                    if tok:
                        out.append(tok)
                in_packages = False
            continue
        if in_packages:
            stripped = line.lstrip()
            if stripped.startswith("- "):
                tok = stripped[2:].strip().strip("'").strip('"')
                if tok:
                    out.append(tok)
            elif line and not line.startswith((" ", "\t")):
                in_packages = False
    return out


def _read_package_json_workspaces(pj: Path) -> list[str]:
    if not pj.is_file():
        return []
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return []
    ws = data.get("workspaces")
    if isinstance(ws, list):
        return [p for p in ws if isinstance(p, str)]
    if isinstance(ws, dict):
        inner = ws.get("packages")
        if isinstance(inner, list):
            return [p for p in inner if isinstance(p, str)]
    return []


def main() -> int:
    root = Path(os.environ.get("LP_REPO_ROOT", os.getcwd())).resolve()
    patterns: list[str] = []
    patterns.extend(_read_pnpm_workspace_packages(root / "pnpm-workspace.yaml"))
    patterns.extend(_read_package_json_workspaces(root / "package.json"))

    if not patterns:
        return 0

    found: set[Path] = set()
    for pat in patterns:
        if pat.startswith("/") or ".." in Path(pat).parts:
            continue
        for d in _glob.iglob(str(root / pat)):
            dp = Path(d)
            if not dp.is_dir():
                continue
            try:
                real = dp.resolve(strict=True)
                if not real.is_relative_to(root):
                    continue
            except (OSError, ValueError):
                continue
            cand = dp / "package.json"
            if cand.is_file():
                found.add(cand)

    for p in sorted(found, key=lambda x: str(x)):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
