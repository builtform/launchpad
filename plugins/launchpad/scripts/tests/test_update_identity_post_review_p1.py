"""v2.1 Codex PR #50 post-review-2 regression tests.

P1 #1 — Case D `--seed-brownfield` non-dry-run path returns a
        structured `BROWNFIELD_SEED_NOT_IMPLEMENTED` error rather than
        crashing with an unstructured FileNotFoundError.

v2.1.0 Codex P1 #2 fold (replaces prior `user_has_drift` tests): the
prior `user_has_drift` boolean was always-true on clean rendered files
(it compared the on-disk post-Jinja-interpolation SHA against the raw
template source SHA — different domains), so refresh() permanently
skipped every file. The fix drops `user_has_drift` and branches on
`missing_on_disk` instead. These tests pin the new contract:

  * Files where the prior seal said `missing_on_disk: False` AND on-disk
    SHA matches the prior `rendered_content_sha256` get re-rendered.
  * Files where the prior seal said `missing_on_disk: False` AND on-disk
    SHA differs from prior get skipped (user-edit detection).
  * Files where the prior seal said `missing_on_disk: True` AND target
    is now present (intermediate render race) get skipped with WARN.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

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
# P1 #2 (v2.1.0 fold): refresh() branches on missing_on_disk
# ---------------------------------------------------------------------------


def test_refresh_skips_user_edited_files_via_sha_compare(tmp_path):
    """v2.1.0 Codex P1 #2 fold: a present file whose on-disk SHA differs
    from the prior `rendered_content_sha256` gets skipped (user-edit
    detection). `missing_on_disk: False` + SHA mismatch ⇒ skip.
    """
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    renderer.render_all(tmp_path, _identity_mit())

    license_path = tmp_path / "LICENSE"
    edited_content = b"USER EDITED CONTENT - MUST PRESERVE\n"
    license_path.write_bytes(edited_content)

    # Prior state recorded the *clean* rendered SHA (the legitimate seal
    # produced by render_all). The user has since edited; refresh's
    # SHA-compare detects the divergence and skips.
    import hashlib
    template_sha = renderer._template_sha256("LICENSE.j2")
    # We don't know the clean rendered SHA without re-rendering; so seal a
    # known-different placeholder and assert the SHA mismatch path.
    sentinel_clean_sha = "0" * 64
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": sentinel_clean_sha,
        "source_template_sha256": template_sha,
        "missing_on_disk": False,
    }]

    new_identity = dict(_identity_mit())
    new_identity["copyright_holder"] = "New Owner"

    result = renderer.refresh(
        tmp_path,
        new_identity,
        prior_kernel_render_state=prior_state,
    )

    assert license_path in result.skipped_user_edits
    assert license_path.read_bytes() == edited_content


def test_refresh_missing_on_disk_true_with_present_file_skips_with_warn(tmp_path):
    """v2.1.0 Codex P1 #2 fold (cycle-1 SF-P1-3 stale-placeholder race):
    when prior seal said `missing_on_disk: True` but the target is now
    present (intermediate render race wrote it between Case E seal and
    this refresh), the file is skipped with a template_drift_infos
    breadcrumb naming the recovery command.
    """
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    # Pre-seed LICENSE on disk (simulating the intermediate render race).
    renderer.render_all(tmp_path, _identity_mit())
    license_path = tmp_path / "LICENSE"
    assert license_path.is_file()

    template_sha = renderer._template_sha256("LICENSE.j2")
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": template_sha,  # placeholder seal
        "source_template_sha256": template_sha,
        "missing_on_disk": True,
    }]

    result = renderer.refresh(
        tmp_path,
        _identity_mit(),
        prior_kernel_render_state=prior_state,
    )

    assert license_path in result.skipped_user_edits
    # Breadcrumb names the recovery command.
    assert any(
        "/lp-bootstrap --refresh" in info for info in result.template_drift_infos
    ), f"missing recovery breadcrumb in {result.template_drift_infos!r}"


def test_refresh_clean_files_with_missing_on_disk_false_get_rendered(tmp_path):
    """v2.1.0 Codex P1 #2 fold: the originally-broken case. Clean files
    sealed via render_all (`missing_on_disk: False`, on-disk SHA matches
    prior) MUST be re-rendered on identity update. Pre-fix, the
    always-true `user_has_drift` flag blocked this path entirely.
    """
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    _rendered, kernel_state = renderer.render_all(tmp_path, _identity_mit())
    # All seals carry missing_on_disk: False with the actual rendered SHA.
    assert all(e.get("missing_on_disk") is False for e in kernel_state)

    new_identity = dict(_identity_mit())
    new_identity["copyright_holder"] = "Different Owner"

    result = renderer.refresh(
        tmp_path,
        new_identity,
        prior_kernel_render_state=kernel_state,
    )

    # All 7 kernel files re-rendered (not skipped). This was the pre-fix
    # failure mode: every clean file got skipped because user_has_drift
    # was always True for post-Jinja-interpolation files.
    rendered_paths = {p for p, _sha in result.rendered}
    assert (tmp_path / "LICENSE") in rendered_paths
    assert result.skipped_user_edits == []
