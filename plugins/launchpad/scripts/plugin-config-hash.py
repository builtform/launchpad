#!/usr/bin/env python3
"""Compute the canonical content hash of config.yml's `commands:` section.

v2.0 backport: JSON canonicalization (HANDSHAKE §3 backport) + 5-branch
LP_CONFIG_REVIEWED migration UX with `hmac.compare_digest` + single-signal
`_is_ci_environment()` env-var-only at v2.0 (multi-signal `_has_ci_filesystem_signal`
is BL-224 deferred per §1.5 strip-back).

The legacy YAML migration helper `_legacy_yaml_canonical_hash` is INLINED in
this module per HANDSHAKE §12 (was a separate `lp-migrate-config-hash.py` in
Layer 2 spec; collapsed here for SRP coherence). Removed at v2.1.0 per BL-210.

Outputs: sha256 hex digest to stdout. Exit codes:
  0 — hash printed; LP_CONFIG_REVIEWED resolution: ACCEPTED
  1 — config.yml is missing/unparseable
  2 — LP_CONFIG_REVIEWED resolution: REPROMPT or REPROMPT_AUTO_REVIEW_OUTSIDE_CI
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import warnings
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR = SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

import yaml  # noqa: E402  (vendored)


# Resolution outcomes for LP_CONFIG_REVIEWED.
ACCEPTED = "ACCEPTED"
REPROMPT = "REPROMPT"
REPROMPT_FIRST_TIME = "REPROMPT_FIRST_TIME"
REPROMPT_AUTO_REVIEW_OUTSIDE_CI = "REPROMPT_AUTO_REVIEW_OUTSIDE_CI"


# CI vendor env vars — single-signal at v2.0 per §1.5 strip-back. Multi-signal
# (`_has_ci_filesystem_signal()`) is BL-224 deferred to v2.2.
_CI_VENDOR_ENV_VARS = (
    "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI",
    "BUILDKITE", "JENKINS_HOME", "TRAVIS",
)


def commands_section(config_path: Path) -> dict:
    """Load + extract the `commands:` mapping from config.yml. Used by both
    canonicalization variants (new JSON, legacy YAML)."""
    text = config_path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text) or {}
    commands = doc.get("commands", {}) or {}
    if not isinstance(commands, dict):
        raise ValueError(
            f"commands section must be a mapping, got {type(commands).__name__}"
        )
    return commands


def canonical_hash(payload: dict) -> str:
    """JSON canonicalization per HANDSHAKE §3.

    Defined here AND in `decision_integrity.py` — both must produce the same
    bytes; the v2 module is the canonical owner, this is the v1 backport.
    Unit test in tests/test_config_hash_backport.py asserts cross-module
    equality on a shared fixture.
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"canonical_hash requires a dict payload, got {type(payload).__name__}"
        )
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _legacy_yaml_canonical_hash(payload: dict) -> str:
    """Legacy v1.x YAML canonicalization. Kept for one minor cycle (v2.0.x)
    under DeprecationWarning; removed at v2.1.0 per BL-210.

    The keep-then-remove pattern is load-bearing for the v2.0.0-yanked
    rollback story: a downstream rolling back to v1.1.0 needs its old YAML
    hash to still validate.
    """
    warnings.warn(
        "plugin-config-hash._legacy_yaml_canonical_hash is deprecated; "
        "v2.1.0 removes it (BL-210). Re-export LP_CONFIG_REVIEWED to the "
        "new JSON-based hash to dismiss this notice.",
        DeprecationWarning,
        stacklevel=2,
    )
    canonical = yaml.safe_dump(payload, sort_keys=True, default_flow_style=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_ci_environment() -> bool:
    """Single-signal env-var detection at v2.0 (per §1.5 strip-back).

    Threat-model concession: a hostile rcfile / dependency postinstall can
    pivot via env vars alone — load-bearing defenses remain CODEOWNERS gate
    (OPERATIONS §2) + non-blocking soft-warn UX. Multi-signal detection
    (filesystem markers + parent-process check) is BL-224 deferred to v2.2.
    """
    if os.environ.get("CI") != "true":
        return False
    return any(os.environ.get(v) for v in _CI_VENDOR_ENV_VARS)


def resolve_review_state(config_path: Path) -> tuple[str, str]:
    """Apply the 5-branch LP_CONFIG_REVIEWED migration UX truth table per
    HANDSHAKE §3.

    Returns (outcome, new_hash) — caller decides what to print/return.
    Outcomes: ACCEPTED, REPROMPT, REPROMPT_FIRST_TIME,
    REPROMPT_AUTO_REVIEW_OUTSIDE_CI.
    """
    commands = commands_section(config_path)
    new_hash = canonical_hash(commands)
    reviewed = os.environ.get("LP_CONFIG_REVIEWED")
    auto_review = os.environ.get("LP_CONFIG_AUTO_REVIEW") == "1"

    # Cell E: env var unset entirely.
    if reviewed is None:
        if auto_review and _is_ci_environment():
            return ACCEPTED, new_hash
        if auto_review and not _is_ci_environment():
            return REPROMPT_AUTO_REVIEW_OUTSIDE_CI, new_hash
        return REPROMPT_FIRST_TIME, new_hash

    # Cells A + C: current scheme matches (silent ACCEPTED).
    if hmac.compare_digest(reviewed, new_hash):
        return ACCEPTED, new_hash

    # Cell B: legacy YAML match (soft-warn; non-blocking).
    try:
        legacy_hash = _legacy_yaml_canonical_hash(commands)
    except Exception:
        legacy_hash = ""
    if legacy_hash and hmac.compare_digest(reviewed, legacy_hash):
        print(
            "LaunchPad v2.0 changed how config-review hashes are computed (v1.x\n"
            "used YAML; v2.0 uses JSON for cross-platform reliability). Your\n"
            "existing LP_CONFIG_REVIEWED hash is still honored — but to dismiss\n"
            "this notice:\n"
            f"\n  export LP_CONFIG_REVIEWED={new_hash}\n\n"
            "The legacy hash continues to work through v2.0.x; v2.1.0 will\n"
            "require the new hash. To roll back to v1.1.0 instead:\n"
            "  unset LP_CONFIG_REVIEWED && claude /plugin install launchpad@v1.1.0",
            file=sys.stderr,
        )
        return ACCEPTED, new_hash

    # Cell D: neither matches — config genuinely changed since last review.
    return REPROMPT, new_hash


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    ap.add_argument(
        "--resolve-review-state", action="store_true",
        help="Apply 5-branch LP_CONFIG_REVIEWED truth table; emit outcome.",
    )
    args = ap.parse_args()

    cfg = Path(args.repo_root) / ".launchpad" / "config.yml"
    if not cfg.is_file():
        print("", end="")  # empty output means "no commands section" by convention
        print(f"WARN: {cfg} does not exist; nothing to hash", file=sys.stderr)
        return 1

    try:
        if args.resolve_review_state:
            outcome, new_hash = resolve_review_state(cfg)
            print(json.dumps({"outcome": outcome, "hash": new_hash}))
            if outcome in (REPROMPT, REPROMPT_AUTO_REVIEW_OUTSIDE_CI):
                return 2
            return 0
        else:
            print(canonical_hash(commands_section(cfg)))
            return 0
    except (yaml.YAMLError, ValueError) as e:
        print(f"error hashing commands section: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
