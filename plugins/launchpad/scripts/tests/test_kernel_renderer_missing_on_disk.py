"""v2.1.0 kernel_renderer drift fix (Codex P1 #2 fold).

Pins §4.6 of
`docs/plans/launchpad_plans/2026-05-08-v2.1.0-atomic-io-symlink-and-kernel-drift-fix-plan.md`:

  * `compute_current_on_disk_state` drops `user_has_drift` entirely.
    Missing files seal `missing_on_disk: True` + placeholder
    `rendered_content_sha256 == source_template_sha256`. Present files
    seal `missing_on_disk: False` + on-disk SHA (which differs from
    the template SHA because of Jinja interpolation -- the very domain
    mismatch the always-wrong `user_has_drift` was comparing).
  * `refresh()` branches on `missing_on_disk`:
      - missing_on_disk: True + target missing -> render fresh
      - missing_on_disk: True + target present -> skip with WARN
      - missing_on_disk: False + on-disk SHA matches -> render
      - missing_on_disk: False + on-disk SHA differs -> skip (user edit)
  * Legacy v2.1-alpha seal with `user_has_drift: True` AND
    `rendered_content_sha256 == source_template_sha256`: refresh sees
    the SHA mismatch (alpha seal stored template_sha; on-disk is the
    post-Jinja rendered SHA), classifies as user-edit, and SKIPS.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _identity():
    return {
        "pii_opt_in": True,
        "project_name": "demo",
        "email": "demo@example.com",
        "copyright_holder": "Demo Owner",
        "repo_url": "https://github.com/demo/demo",
        "license": "MIT",
        "license_other_body": "",
    }


# ---------------------------------------------------------------------------
# §4.6 #1 -- compute_current_on_disk_state: missing files seal placeholder
# ---------------------------------------------------------------------------
def test_compute_current_on_disk_state_missing_files_seal_placeholder(tmp_path):
    from plugin_default_generators.kernel_renderer import KernelRenderer
    state = KernelRenderer().compute_current_on_disk_state(tmp_path)
    assert len(state) == 7
    for entry in state:
        assert entry["missing_on_disk"] is True
        # Placeholder seal: rendered_content_sha256 == source_template_sha256.
        assert entry["rendered_content_sha256"] == entry["source_template_sha256"]
        # user_has_drift dropped entirely.
        assert "user_has_drift" not in entry


# ---------------------------------------------------------------------------
# §4.6 #2 -- compute_current_on_disk_state: present files seal rendered
# ---------------------------------------------------------------------------
def test_compute_current_on_disk_state_present_files_seal_rendered(tmp_path):
    """Present files seal the on-disk SHA (post-Jinja-interpolation),
    which differs from the template-source SHA (pre-interpolation) for
    every kernel file -- the very domain mismatch the prior
    `user_has_drift` flag was always-wrongly flagging."""
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    renderer.render_all(tmp_path, _identity())

    state = renderer.compute_current_on_disk_state(tmp_path)
    for entry in state:
        assert entry["missing_on_disk"] is False
        # The interpolated render SHA differs from the raw template SHA
        # for every kernel file (all 7 interpolate identity fields).
        assert entry["rendered_content_sha256"] != entry["source_template_sha256"]
        assert "user_has_drift" not in entry


# ---------------------------------------------------------------------------
# §4.6 #3 -- refresh: missing_on_disk True + target missing -> render fresh
# ---------------------------------------------------------------------------
def test_refresh_missing_on_disk_overwrites_when_still_missing(tmp_path):
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    template_sha = renderer._template_sha256("LICENSE.j2")
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": template_sha,  # placeholder
        "source_template_sha256": template_sha,
        "missing_on_disk": True,
    }]

    license_path = tmp_path / "LICENSE"
    assert not license_path.exists()

    result = renderer.refresh(
        tmp_path,
        _identity(),
        prior_kernel_render_state=prior_state,
    )

    rendered_paths = {p for p, _sha in result.rendered}
    assert license_path in rendered_paths
    assert license_path.is_file()


# ---------------------------------------------------------------------------
# §4.6 #4 -- refresh: missing_on_disk True + target present -> skip
# ---------------------------------------------------------------------------
def test_refresh_missing_on_disk_skips_when_file_present(tmp_path):
    """cycle-1 SF-P1-3: stale-placeholder race. Between Case E seal and
    this refresh, an intermediate render path wrote the file. The
    placeholder SHA is no longer trustworthy; conservative skip."""
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    # Pre-stage the file (simulating the intermediate render race).
    renderer.render_all(tmp_path, _identity())
    license_path = tmp_path / "LICENSE"
    assert license_path.is_file()

    template_sha = renderer._template_sha256("LICENSE.j2")
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": template_sha,
        "source_template_sha256": template_sha,
        "missing_on_disk": True,
    }]

    result = renderer.refresh(
        tmp_path,
        _identity(),
        prior_kernel_render_state=prior_state,
    )

    assert license_path in result.skipped_user_edits
    # Recovery breadcrumb names /lp-bootstrap --refresh.
    assert any(
        "/lp-bootstrap --refresh" in info for info in result.template_drift_infos
    )


# ---------------------------------------------------------------------------
# §4.6 #5 -- refresh: missing_on_disk False + SHA mismatch -> skip
# ---------------------------------------------------------------------------
def test_refresh_rendered_user_edit_skips(tmp_path):
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    renderer.render_all(tmp_path, _identity())

    license_path = tmp_path / "LICENSE"
    edited = b"user-edited LICENSE\n"
    license_path.write_bytes(edited)

    template_sha = renderer._template_sha256("LICENSE.j2")
    sentinel_prior_clean = "f" * 64  # known-different from the user-edit SHA
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": sentinel_prior_clean,
        "source_template_sha256": template_sha,
        "missing_on_disk": False,
    }]

    result = renderer.refresh(
        tmp_path,
        _identity(),
        prior_kernel_render_state=prior_state,
    )

    assert license_path in result.skipped_user_edits
    assert license_path.read_bytes() == edited


# ---------------------------------------------------------------------------
# §4.6 #6 -- legacy v2.1-alpha seal: skip clean files (acceptable regression)
# ---------------------------------------------------------------------------
def test_refresh_legacy_alpha_state_with_broken_seal_skips_clean_files(tmp_path):
    """cycle-1 SEC-F8: v2.1-alpha sealed with `user_has_drift: True` AND
    `rendered_content_sha256 == source_template_sha256` (the broken
    seal). New refresh ignores `user_has_drift`, sees `missing_on_disk:
    False` + SHA mismatch (alpha placeholder vs actual rendered SHA),
    classifies as user-edit, SKIPS. User re-scaffolds to fix.
    """
    from plugin_default_generators.kernel_renderer import KernelRenderer

    renderer = KernelRenderer()
    renderer.render_all(tmp_path, _identity())  # writes clean rendered LICENSE
    license_path = tmp_path / "LICENSE"

    template_sha = renderer._template_sha256("LICENSE.j2")
    # Alpha seal: rendered_content_sha256 = template_sha (broken),
    # missing_on_disk: False, user_has_drift: True (legacy noise).
    prior_state = [{
        "path": "LICENSE",
        "rendered_content_sha256": template_sha,
        "source_template_sha256": template_sha,
        "missing_on_disk": False,
        "user_has_drift": True,  # legacy field; new refresh ignores it
    }]

    result = renderer.refresh(
        tmp_path,
        _identity(),
        prior_kernel_render_state=prior_state,
    )

    # On-disk SHA (post-Jinja) != template_sha (alpha placeholder).
    # SHA mismatch -> skip (user-edit branch).
    assert license_path in result.skipped_user_edits
    # File preserved on disk (not overwritten).
    assert license_path.is_file()
