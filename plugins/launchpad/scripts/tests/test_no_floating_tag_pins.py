"""No-floating-tag-pins lint test.

Phase 4 plan §3.2 + §2.2 Slice A row: every pin in `pin_registry.py` must be
a 40-char hex commit SHA (not a floating tag like `main`, `HEAD`, `v6.0.2`,
or `latest`); audit log at `docs/maintainers/upstream-pin-rotations.md` must
contain dual-resolution evidence and an entry per pin.
"""
from __future__ import annotations

import re
from pathlib import Path

from plugin_stack_adapters.pin_registry import _PINS, _SHA_RE

REPO_ROOT = Path(__file__).resolve().parents[4]
AUDIT_LOG = REPO_ROOT / "docs" / "maintainers" / "upstream-pin-rotations.md"
PIN_REGISTRY = (
    REPO_ROOT
    / "plugins"
    / "launchpad"
    / "scripts"
    / "plugin_stack_adapters"
    / "pin_registry.py"
)

_FLOATING_PATTERNS = (
    r"^main$",
    r"^master$",
    r"^HEAD$",
    r"^latest$",
    r"^v\d",
    r"^[\d.]+$",
)


def test_every_pin_sha_matches_40char_hex_regex():
    for key, pin in _PINS.items():
        assert _SHA_RE.match(pin["sha"]), f"{key} sha {pin['sha']!r} fails regex"


def test_no_pin_uses_a_floating_tag_string():
    for key, pin in _PINS.items():
        for pat in _FLOATING_PATTERNS:
            assert not re.match(pat, pin["sha"]), (
                f"{key} pin sha {pin['sha']!r} matches floating-tag pattern {pat}"
            )


def test_audit_log_exists_at_expected_path():
    assert AUDIT_LOG.exists(), f"audit log missing at {AUDIT_LOG}"


def test_audit_log_records_dual_resolution_evidence():
    content = AUDIT_LOG.read_text(encoding="utf-8")
    assert "dual-resolved" in content, (
        "audit log must contain 'dual-resolved' evidence per Phase 4 §3.2"
    )
    assert "git ls-remote" in content


def test_audit_log_contains_an_entry_per_registered_pin_sha():
    content = AUDIT_LOG.read_text(encoding="utf-8")
    for key, pin in _PINS.items():
        assert pin["sha"] in content, (
            f"audit log missing entry for {key} sha {pin['sha']}"
        )


def test_pin_registry_file_has_no_floating_tag_string_constants():
    content = PIN_REGISTRY.read_text(encoding="utf-8")
    for forbidden in (
        '"sha": "main"',
        '"sha": "HEAD"',
        '"sha": "latest"',
    ):
        assert forbidden not in content, (
            f"pin_registry contains forbidden floating tag: {forbidden}"
        )
