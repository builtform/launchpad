"""Phase 10 v2.1 -- /lp-update-identity engine tests.

~22 tests:
  Round-trip (6): each-field round-trip + composite multi-field
  Re-entry (5): cases A/B/C/D/E
  Preconditions (6): each of the 6 checks at §3.4
  Brownfield seed (3): with-flag-success + without-flag-refused +
    --allow-email-mismatch override
  Diff-summary (1): truncation + multi-line collapse
  PII WARN regression (1): verbatim two-line string
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

import pytest

# Sibling-script imports.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_update_identity import (
    IdentityUpdateErrorCode,
    IdentityUpdateStatus,
)
from lp_update_identity.engine import (
    UpdateIdentityResult,
    _PreconditionAbort,
    _compute_identity_diff,
    _detect_re_entry_case,
    _format_diff_summary,
    _print_pii_warn,
    _truncate_for_diff,
    _validate_preconditions,
    run_update_identity,
)
from lp_pick_stack.decision_writer import (
    default_unset_identity,
    write_decision_file,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _layers():
    return [{"stack": "next", "role": "fullstack", "path": ".", "options": {}}]


def _summary():
    return [
        {"category_id": "next-fullstack", "rank": 1, "score": 100, "reasons": []},
    ]


def _mit_identity() -> dict:
    return {
        "pii_opt_in": True,
        "project_name": "demo-project",
        "email": "owner@example.com",
        "copyright_holder": "Demo Owner",
        "repo_url": "https://github.com/example/demo",
        "license": "MIT",
        "license_other_body": "",
    }


def _seed_full_scaffold(tmp_path: Path, identity: Mapping[str, Any] | None = None) -> Path:
    """Seed scaffold-decision.json with optional identity, then run KernelRenderer
    to populate kernel_render_state via the side-effect.
    """
    (tmp_path / ".launchpad").mkdir(exist_ok=True)
    write_decision_file(
        layers=_layers(),
        matched_category_id="next-fullstack",
        rationale_summary=_summary(),
        rationale_sha256="0" * 64,
        cwd=tmp_path,
        identity=identity if identity is not None else _mit_identity(),
    )
    # Run kernel render once so kernel_render_state populates.
    from plugin_default_generators.kernel_renderer import KernelRenderer
    KernelRenderer().render_all(tmp_path, identity if identity is not None else _mit_identity())
    return tmp_path


# ---------------------------------------------------------------------------
# Re-entry case detection (5 tests covering DA5)
# ---------------------------------------------------------------------------


def test_re_entry_case_A_missing_decision():
    case = _detect_re_entry_case(None, seed_brownfield=False)
    assert case == "A"


def test_re_entry_case_B_legacy_1_0_envelope():
    payload = {"version": "1.0", "schema_version": "1.0"}  # no identity block
    case = _detect_re_entry_case(payload, seed_brownfield=False)
    assert case == "B"


def test_re_entry_case_C_no_field_change_returns_UPDATED_then_caller_no_ops():
    """Case C is detected at the engine level via diff = []; the case-letter
    detector returns UPDATED for the (1.1 + identity + state-block) shape."""
    payload = {
        "schema_version": "1.1",
        "identity": _mit_identity(),
        "kernel_render_state": [{"path": "LICENSE"}],
    }
    case = _detect_re_entry_case(payload, seed_brownfield=False)
    assert case == "UPDATED"


def test_re_entry_case_D_brownfield_seed_with_flag():
    case = _detect_re_entry_case(None, seed_brownfield=True)
    assert case == "D"


def test_re_entry_case_E_no_kernel_render_state_block():
    payload = {
        "schema_version": "1.1",
        "identity": _mit_identity(),
        # No kernel_render_state field at all.
    }
    case = _detect_re_entry_case(payload, seed_brownfield=False)
    assert case == "E"


# ---------------------------------------------------------------------------
# Preconditions (6 tests covering DA4)
# ---------------------------------------------------------------------------


def test_preconditions_scaffold_decision_missing_aborts(tmp_path: Path):
    (tmp_path / ".launchpad").mkdir()
    with pytest.raises(_PreconditionAbort) as exc:
        _validate_preconditions(tmp_path, seed_brownfield=False)
    assert exc.value.code == IdentityUpdateErrorCode.SCAFFOLD_DECISION_MISSING


def test_preconditions_seed_brownfield_skips_scaffold_check(tmp_path: Path):
    (tmp_path / ".launchpad").mkdir()
    payload, infos = _validate_preconditions(tmp_path, seed_brownfield=True)
    assert payload is None
    assert any("brownfield" in i for i in infos)


def test_preconditions_malformed_scaffold_decision_aborts(tmp_path: Path):
    (tmp_path / ".launchpad").mkdir()
    (tmp_path / ".launchpad" / "scaffold-decision.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(_PreconditionAbort) as exc:
        _validate_preconditions(tmp_path, seed_brownfield=False)
    assert exc.value.code == IdentityUpdateErrorCode.SCAFFOLD_DECISION_MISSING


def test_preconditions_dead_pid_sentinel_recovers(tmp_path: Path):
    _seed_full_scaffold(tmp_path)
    from lp_update_identity.sentinel import write_sentinel
    write_sentinel(
        tmp_path,
        pre_edit_decision_sha256=None,
        target_paths=[],
        backup_path="/tmp/bk",
        command_pid=2**31 - 1,  # guaranteed dead
    )
    payload, infos = _validate_preconditions(tmp_path, seed_brownfield=False)
    assert payload is not None
    assert any("recovered stale identity-update sentinel" in i for i in infos)


def test_preconditions_live_bootstrap_sentinel_aborts(tmp_path: Path):
    """Check 4: /lp-bootstrap concurrent-run via sentinel + live PID."""
    _seed_full_scaffold(tmp_path)
    from lp_bootstrap.sentinel import write_sentinel as bs_write
    bs_write(
        tmp_path,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=[],
        command_pid=os.getpid(),
    )
    with pytest.raises(_PreconditionAbort) as exc:
        _validate_preconditions(tmp_path, seed_brownfield=False)
    assert exc.value.code == IdentityUpdateErrorCode.BOOTSTRAP_IN_PROGRESS


def test_preconditions_unwritable_launchpad_aborts(tmp_path: Path):
    _seed_full_scaffold(tmp_path)
    launchpad_dir = tmp_path / ".launchpad"
    # Save mode for restore (the directory must be writable for tmp_path cleanup).
    original_mode = launchpad_dir.stat().st_mode
    try:
        os.chmod(launchpad_dir, 0o500)  # read+execute only
        # On macOS, root processes bypass; skip if running as root.
        if os.access(str(launchpad_dir), os.W_OK):
            pytest.skip("test environment grants write despite chmod 0o500")
        with pytest.raises(_PreconditionAbort) as exc:
            _validate_preconditions(tmp_path, seed_brownfield=False)
        assert exc.value.code == IdentityUpdateErrorCode.PERMISSION_DENIED
    finally:
        os.chmod(launchpad_dir, original_mode)


# ---------------------------------------------------------------------------
# Round-trip (6 tests)
# ---------------------------------------------------------------------------


def test_round_trip_project_name_change_updates_LICENSE_etc(tmp_path: Path):
    _seed_full_scaffold(tmp_path)
    new_identity = dict(_mit_identity())
    new_identity["project_name"] = "renamed-project"
    out = io.StringIO()
    result = run_update_identity(
        tmp_path, new_identity, stdout=out, stderr=io.StringIO(),
    )
    assert result.status == IdentityUpdateStatus.UPDATED
    assert result.fields_changed == ["project_name"]
    # All 7 kernel files should re-render (none user-edited).
    assert len(result.rendered) == 7
    assert result.skipped_user_edits == []
    # README.md should now contain the new name.
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "renamed-project" in readme


def test_round_trip_email_change(tmp_path: Path):
    _seed_full_scaffold(tmp_path)
    new = dict(_mit_identity())
    new["email"] = "new@example.com"
    result = run_update_identity(tmp_path, new, stdout=io.StringIO(), stderr=io.StringIO())
    assert result.fields_changed == ["email"]
    assert "new@example.com" in (tmp_path / "CONTRIBUTING.md").read_text("utf-8")


def test_round_trip_license_change_preserves_other_fields(tmp_path: Path):
    _seed_full_scaffold(tmp_path)
    new = dict(_mit_identity())
    new["license"] = "Apache-2.0"
    result = run_update_identity(tmp_path, new, stdout=io.StringIO(), stderr=io.StringIO())
    assert "license" in result.fields_changed
    assert (tmp_path / "LICENSE").exists()


def test_round_trip_no_change_returns_no_op(tmp_path: Path):
    _seed_full_scaffold(tmp_path)
    result = run_update_identity(
        tmp_path, _mit_identity(), stdout=io.StringIO(), stderr=io.StringIO(),
    )
    assert result.status == IdentityUpdateStatus.NO_OP
    assert result.fields_changed == []


def test_round_trip_preserves_generated_at(tmp_path: Path):
    """DA9: identity update MUST NOT mutate generated_at."""
    _seed_full_scaffold(tmp_path)
    pre = json.loads((tmp_path / ".launchpad" / "scaffold-decision.json").read_text("utf-8"))
    pre_generated = pre["generated_at"]
    new = dict(_mit_identity())
    new["project_name"] = "new-name"
    run_update_identity(tmp_path, new, stdout=io.StringIO(), stderr=io.StringIO())
    post = json.loads((tmp_path / ".launchpad" / "scaffold-decision.json").read_text("utf-8"))
    assert post["generated_at"] == pre_generated


def test_round_trip_user_edited_kernel_file_skipped_with_remediation(tmp_path: Path):
    """Phase 10 §3.7: per-file user-edit refusal continues for other files."""
    _seed_full_scaffold(tmp_path)
    # User edits LICENSE post-render.
    license_path = tmp_path / "LICENSE"
    license_path.write_text("USER-EDITED LICENSE TEXT", encoding="utf-8")
    new = dict(_mit_identity())
    new["project_name"] = "renamed-x"
    result = run_update_identity(
        tmp_path, new, stdout=io.StringIO(), stderr=io.StringIO(),
    )
    assert license_path in result.skipped_user_edits
    assert all(p != license_path for p in result.rendered)
    # Other files DID re-render.
    assert (tmp_path / "README.md").read_text("utf-8").find("renamed-x") >= 0


# ---------------------------------------------------------------------------
# Brownfield seed (3 tests)
# ---------------------------------------------------------------------------


def test_brownfield_seed_without_flag_refused(tmp_path: Path):
    (tmp_path / ".launchpad").mkdir()
    result = run_update_identity(
        tmp_path, _mit_identity(), seed_brownfield=False,
        stdout=io.StringIO(), stderr=io.StringIO(),
    )
    assert result.error_code == IdentityUpdateErrorCode.SCAFFOLD_DECISION_MISSING


def test_brownfield_seed_with_flag_email_mismatch_blocks(tmp_path: Path):
    (tmp_path / ".launchpad").mkdir()
    with patch(
        "lp_update_identity.engine._read_git_config_email",
        return_value="different@example.com",
    ):
        result = run_update_identity(
            tmp_path, _mit_identity(), seed_brownfield=True,
            stdout=io.StringIO(), stderr=io.StringIO(),
        )
    assert result.error_code == IdentityUpdateErrorCode.GIT_CONFIG_EMAIL_MISMATCH


def test_brownfield_allow_email_mismatch_override_proceeds(tmp_path: Path):
    """--allow-email-mismatch downgrades BLOCK to WARN; proceeds.

    Uses dry_run=True so the test isolates the email-check + WARN path
    from the Case D seed-from-scratch write flow (which requires a layers
    stub outside this test's fixture scope; tested upstream via the
    /lp-pick-stack engine + the Case D write integration test in v2.2 BL).
    """
    (tmp_path / ".launchpad").mkdir()
    err_stream = io.StringIO()
    with patch(
        "lp_update_identity.engine._read_git_config_email",
        return_value="",  # empty -> mismatch
    ):
        result = run_update_identity(
            tmp_path, _mit_identity(),
            seed_brownfield=True, allow_email_mismatch=True,
            dry_run=True,
            stdout=io.StringIO(), stderr=err_stream,
        )
    assert result.error_code != IdentityUpdateErrorCode.GIT_CONFIG_EMAIL_MISMATCH
    assert "git config user.email mismatch" in err_stream.getvalue()


# ---------------------------------------------------------------------------
# Diff helpers (2 tests)
# ---------------------------------------------------------------------------


def test_compute_identity_diff_returns_changed_field_names_only():
    old = _mit_identity()
    new = dict(old)
    new["project_name"] = "y"
    new["email"] = "z@example.com"
    diff = _compute_identity_diff(old, new)
    assert set(diff) == {"project_name", "email"}


def test_truncate_for_diff_caps_at_80_chars_and_collapses_newlines():
    long = "x" * 100
    truncated = _truncate_for_diff(long)
    assert len(truncated) == 78  # 77 chars + ellipsis
    assert truncated.endswith("…")

    multi = "line1\nline2"
    assert _truncate_for_diff(multi) == "line1\\nline2"


# ---------------------------------------------------------------------------
# PII WARN regression (1 test, locked verbatim per DA6)
# ---------------------------------------------------------------------------


def test_pii_warn_locked_verbatim_two_line_string():
    """DA6: regression test pinning the verbatim WARN string. v2.2 BL
    plan-author must update this test if the string changes."""
    class _FakeTTY(io.StringIO):
        def isatty(self):
            return True

    out = _FakeTTY()
    _print_pii_warn(quiet=False, stream=out)
    text = out.getvalue()
    assert (
        "WARN: prior identity values persist in git history "
        "(LICENSE, CONTRIBUTING.md, ...)." in text
    )
    assert "See docs/guides/IDENTITY_AND_PII.md for removal options." in text


def test_pii_warn_quiet_flag_suppresses():
    out = io.StringIO()
    _print_pii_warn(quiet=True, stream=out)
    assert out.getvalue() == ""
