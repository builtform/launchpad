#!/usr/bin/env python3
"""Compute the canonical content hash of config.yml's `commands:` section.

An exact canonicalization is mandated so different reviewers on different
machines compute the same hash for the same logical content:

    sha256(yaml.safe_dump(commands, sort_keys=True, default_flow_style=False))

This hash is used for:
  - The hash-change prompt ("commands block changed since your last ack —
    review and confirm?")
  - The CI override env var LP_CONFIG_REVIEWED (must match this hash)
  - Audit log entries (commands_sha=<this>) — survives rebase/amend/squash
    because it's a content hash, not a commit SHA.

Usage:
  plugin-config-hash.py [--repo-root PATH]

Outputs: the sha256 hex digest to stdout, nothing else. Exit 0 on success,
1 if config.yml is missing or unparseable.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR = SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

import yaml  # noqa: E402  (vendored)


def commands_hash(config_path: Path) -> str:
    """Return the canonical sha256 hex digest of config.yml's commands section.

    If commands is missing, hash the empty dict (a consistent value).
    """
    text = config_path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text) or {}
    commands = doc.get("commands", {}) or {}
    if not isinstance(commands, dict):
        raise ValueError(f"commands section must be a mapping, got {type(commands).__name__}")
    canonical = yaml.safe_dump(commands, sort_keys=True, default_flow_style=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    args = ap.parse_args()

    cfg = Path(args.repo_root) / ".launchpad" / "config.yml"
    if not cfg.is_file():
        print("", end="")  # empty output means "no commands section" by convention
        print(f"WARN: {cfg} does not exist; nothing to hash", file=sys.stderr)
        return 1
    try:
        print(commands_hash(cfg))
        return 0
    except (yaml.YAMLError, ValueError) as e:
        print(f"error hashing commands section: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
