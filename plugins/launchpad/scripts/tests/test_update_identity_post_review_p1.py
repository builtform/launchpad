"""v2.1 Codex PR #50 post-review-2 regression tests.

P1 #1 — Case D `--seed-brownfield` non-dry-run path returns a
        structured `BROWNFIELD_SEED_NOT_IMPLEMENTED` error rather than
        crashing with an unstructured FileNotFoundError.

P1 #2 — `KernelRenderer.refresh()` honors `user_has_drift` from the
        prior kernel_render_state. When the flag is True (sealed by
        Case E "y" path), the file is skipped regardless of the
        on-disk SHA — preventing the previously-discovered data-loss
        regression where `current_disk_sha == prior_rendered_sha`
        (because both are the user's edit SHA) caused the file to be
        silently overwritten on the next refresh.

P1 #2 — `user_has_drift` is preserved across skipped refreshes so the
        consent boundary stays live until the user explicitly resolves
        the drift.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_update_identity import IdentityUpdateErrorCode  # noqa: E402
from lp_update_identity.engine import run_update_identity  # noqa: E402


def _identity_mit() -> dict:
    return {
        "pii_opt_in": True,
        "project_name": "demo-project",
        "email": "owner@example.com",
        "copyright_holder": "Demo Owner",
        "repo_url": "https://github.com/example/demo",
        "license": "MIT",
        "license_other_body": "",
    }


# ---------------------------------------------------------------------------
# P1 #1: Case D --seed-brownfield non-dry-run fails closed
# ---------------------------------------------------------------------------


def test_case_d_seed_brownfield_non_dry_run_fails_closed(tmp_path):
    """v2.1 Codex PR #50 post-review-2 P1 #1: non-dry-run Case D returns
    `BROWNFIELD_SEED_NOT_IMPLEMENTED` rather than crashing with
    FileNotFoundError on `re_seal_decision_atomic`."""
    (tmp_path / ".launchpad").mkdir()
    # No scaffold-decision.json — Case D path.
    result = run_update_identity(
        tmp_path,
        _identity_mit(),
        seed_brownfield=True,
        allow_email_mismatch=True,  # bypass git config check
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert result.error_code == IdentityUpdateErrorCode.BROWNFIELD_SEED_NOT_IMPLEMENTED
    assert "not implemented" in result.error_message.lower()
    assert "BL-271" in result.remediation or "v2.1.1" in result.remediation
    # No scaffold-decision.json was written.
    assert not (tmp_path / ".launchpad" / "scaffold-decision.json").exists()


def test_case_d_seed_brownfield_dry_run_still_works(tmp_path):
    """Dry-run path still validates preconditions without crashing."""
    (tmp_path / ".launchpad").mkdir()
    result = run_update_identity(
        tmp_path,
        _identity_mit(),
        seed_brownfield=True,
        allow_email_mismatch=True,
        dry_run=True,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    # Dry-run returns SEEDED_FIRST_TIME info status (not error).
    assert result.error_code is None
    assert result.status is not None


# ---------------------------------------------------------------------------
# P1 #2: refresh() honors user_has_drift
# ---------------------------------------------------------------------------


def test_refresh_skips_files_marked_user_has_drift(tmp_path):
    """v2.1 Codex PR #50 post-review-2 P1 #2: refresh() must skip files
    whose prior state has `user_has_drift: True`, regardless of
    on-disk-sha vs prior-rendered-sha equality."""
    from plugin_default_generators.kernel_renderer import KernelRenderer

    # Seed kernel files via render_all so the templates land on disk.
    renderer = KernelRenderer()
    renderer.render_all(tmp_path, _identity_mit())

    # User edits LICENSE (the drift simulation).
    license_path = tmp_path / "LICENSE"
    edited_content = b"USER EDITED CONTENT - MUST PRESERVE\n"
    license_path.write_bytes(edited_content)

    # Build prior_state in the shape Case E "y" would seal: the user's
    # edited SHA is recorded as `rendered_content_sha256` AND the
    # `user_has_drift` flag is True. Without the flag, refresh() would
    # see `current_disk_sha == prior_rendered_sha` (both the user's edit
    # SHA) and falsely classify the file as "safe to overwrite".
    import hashlib
    user_edit_sha = hashlib.sha256(edited_content).hexdigest()
    template_sha = renderer._template_sha256("LICENSE.j2")
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": user_edit_sha,
        "source_template_sha256": template_sha,
        "user_has_drift": True,
    }]

    # New identity with a different copyright_holder so the rendered
    # template content WOULD differ from the user's edit if refresh
    # didn't refuse.
    new_identity = dict(_identity_mit())
    new_identity["copyright_holder"] = "New Owner"

    result = renderer.refresh(
        tmp_path,
        new_identity,
        prior_kernel_render_state=prior_state,
    )

    # P1 #2 regression assertion: LICENSE was skipped (user_has_drift honored).
    assert license_path in result.skipped_user_edits
    # User's edit preserved byte-for-byte.
    assert license_path.read_bytes() == edited_content


def test_refresh_preserves_user_has_drift_across_skipped(tmp_path):
    """v2.1 Codex PR #50 post-review-2 P1 #2: when refresh() skips a
    file due to user_has_drift, the new kernel_render_state preserves
    the flag so the consent boundary stays live across refreshes."""
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    renderer.render_all(tmp_path, _identity_mit())

    license_path = tmp_path / "LICENSE"
    license_path.write_bytes(b"user edit\n")

    import hashlib
    edit_sha = hashlib.sha256(b"user edit\n").hexdigest()
    template_sha = renderer._template_sha256("LICENSE.j2")
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": edit_sha,
        "source_template_sha256": template_sha,
        "user_has_drift": True,
    }]

    result = renderer.refresh(
        tmp_path,
        _identity_mit(),
        prior_kernel_render_state=prior_state,
    )

    # Find LICENSE in the new state.
    license_state = next(
        (e for e in result.kernel_render_state if e.get("path") == "LICENSE"),
        None,
    )
    assert license_state is not None
    # The flag is preserved.
    assert license_state.get("user_has_drift") is True


def test_refresh_without_drift_flag_falls_through_to_sha_compare(tmp_path):
    """Backward compat: prior state entries without `user_has_drift`
    fall through to the existing SHA-comparison path."""
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    renderer.render_all(tmp_path, _identity_mit())

    license_path = tmp_path / "LICENSE"
    rendered_sha_before_refresh = __import__("hashlib").sha256(
        license_path.read_bytes()
    ).hexdigest()
    template_sha = renderer._template_sha256("LICENSE.j2")

    # Prior state with NO user_has_drift flag (matches pre-fix v2.1.0
    # state shape).
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": rendered_sha_before_refresh,
        "source_template_sha256": template_sha,
    }]

    new_identity = dict(_identity_mit())
    new_identity["copyright_holder"] = "Different Owner"

    result = renderer.refresh(
        tmp_path,
        new_identity,
        prior_kernel_render_state=prior_state,
    )

    # SHA matches (no user edits) -> file gets re-rendered, NOT skipped.
    assert license_path not in result.skipped_user_edits
    rendered_paths = [p for p, _sha in result.rendered]
    assert license_path in rendered_paths
