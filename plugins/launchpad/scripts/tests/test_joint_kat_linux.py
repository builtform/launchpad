"""Phase 7 §4.7 — Linux KAT pair (Divergence + Cross-platform).

Per Phase 7.5 retained-at-v2.0 list. Two known-answer tests verify SHA-256
canonicalization stability + cross-platform path validator behavior.

  - **KAT-1 (Divergence)**: feed a fixed scaffold-decision-shaped dict
    through `decision_integrity.canonical_hash()`; assert the output equals
    a hardcoded sha256 hex string. Tests JSON canonicalization stability
    across Python versions + ensures `canonical_hash` never silently drifts.

  - **KAT-2 (Cross-platform)**: feed a fixed relative path through
    `path_validator.validate_relative_path()` + run `cwd_state.cwd_state()`
    against a fixed greenfield-shaped tmp directory; assert exact-string
    output matches the expected enum.

Per handoff §4.7: macOS leg is `xfail-not-implemented` (BL-233 deferred);
Linux leg PASSes uniformly. KAT-1 is platform-independent (pure Python)
so both legs run; KAT-2 has a `pytest.mark.skipif(sys.platform != 'linux')`
guard for the path-validator behavioral leg.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import cwd_state  # noqa: E402
from decision_integrity import canonical_hash  # noqa: E402
from path_validator import (  # noqa: E402
    PathValidationError,
    validate_relative_path,
)


# Fixed KAT-1 input — a minimal scaffold-decision-shaped dict. Any change to
# this dict OR to canonical_hash's serialization OR to JSON canonicalization
# (sort_keys / separators / ensure_ascii) WILL change the expected hash.
KAT_1_INPUT = {
    "version": "1.0",
    "matched_category_id": "static-blog-astro",
    "monorepo": False,
    "layers": [{
        "stack": "astro", "role": "frontend", "path": ".",
        "options": {"template": "blog"},
    }],
    "rationale_path": ".launchpad/rationale.md",
    "rationale_sha256": "a" * 64,
    "rationale_summary": [
        {"section": "project-understanding", "bullets": ["kat"]},
    ],
    "generated_by": "/lp-pick-stack",
    "generated_at": "2026-05-03T00:00:00Z",
    "nonce": "0" * 32,
    "bound_cwd": {"realpath": "/tmp/kat", "st_dev": 1, "st_ino": 2},
}

# Computed via canonical_hash(KAT_1_INPUT) on Python 3.13.5 / darwin / x86_64.
# Pure-Python pipeline; cross-platform-stable as long as JSON canonicalization
# is stable. If this changes, EITHER the input dict or the canonicalization
# protocol drifted — investigate before updating the constant.
KAT_1_EXPECTED_SHA256 = (
    "68b515a4a72078f7634efb87c8082826917f98cab0942bb431bd9172ee57f599"
)


def test_kat_1_canonical_hash_divergence():
    """KAT-1: `canonical_hash` over the fixed input matches the pinned hex.

    Cross-platform stable (pure Python). If this test fails, EITHER the input
    schema changed OR `canonical_hash`'s JSON canonicalization changed —
    both are contract-breaking and require coordinated handling.
    """
    actual = canonical_hash(KAT_1_INPUT)
    assert actual == KAT_1_EXPECTED_SHA256, (
        f"KAT-1 hash drift: expected {KAT_1_EXPECTED_SHA256!r}, got {actual!r}; "
        f"input={KAT_1_INPUT!r}"
    )


def test_kat_2_cross_platform_path_validator_string_shape():
    """KAT-2 (string-shape leg): `validate_relative_path` rejects a known-
    bad input with a stable error message.

    Tests the pure-string layer (no filesystem) — runs on all platforms.
    """
    cwd = Path(tempfile.mkdtemp(prefix="lp-joint-kat-"))
    try:
        # Absolute path: rejected with "absolute path forbidden".
        with pytest.raises(PathValidationError) as exc:
            validate_relative_path("/etc/passwd", cwd)
        assert "absolute path forbidden" in str(exc.value), (
            f"unexpected error message: {exc.value!r}"
        )

        # Parent traversal: rejected with "parent traversal forbidden".
        with pytest.raises(PathValidationError) as exc:
            validate_relative_path("../escape", cwd)
        assert "parent traversal forbidden" in str(exc.value), (
            f"unexpected error message: {exc.value!r}"
        )

        # Null byte: rejected with "null byte in path".
        with pytest.raises(PathValidationError) as exc:
            validate_relative_path("ok\x00bad", cwd)
        assert "null byte in path" in str(exc.value)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="KAT-2 filesystem leg is Linux-only at v2.0 (BL-233); macOS spot-"
           "check deferred to Phase 7.5 manual run per handoff §4.7",
)
def test_kat_2_cross_platform_cwd_state_filesystem_leg_linux():
    """KAT-2 (filesystem leg): `cwd_state` returns 'empty' for a freshly-
    created tmpdir on Linux.

    macOS leg is skipped per handoff §4.7 BL-233 deferral; Phase 7.5 will
    spot-check macOS manually before ship.
    """
    cwd = Path(tempfile.mkdtemp(prefix="lp-joint-kat-linux-"))
    try:
        os.chmod(cwd, 0o700)
        assert cwd_state(cwd) == "empty", (
            f"empty tmpdir misclassified as {cwd_state(cwd)!r} on Linux"
        )

        # Add `.gitignore` (allowed) — should still be empty.
        (cwd / ".gitignore").write_text("dist/\n", encoding="utf-8")
        assert cwd_state(cwd) == "empty"

        # Add a brownfield manifest: brownfield.
        (cwd / "package.json").write_text('{}', encoding="utf-8")
        assert cwd_state(cwd) == "brownfield", (
            f"package.json should trigger brownfield, got {cwd_state(cwd)!r}"
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
