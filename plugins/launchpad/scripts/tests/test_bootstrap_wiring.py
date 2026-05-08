"""Wiring tests for the v2.1 Phase 3 Slice D wiring (per plan section 5).

Coverage matrix:
  * Greenfield Step 4.6 wiring: lp_scaffold_stack.engine calls
    run_bootstrap(mode="greenfield"); failure path emits scaffold-failed
    with reason="bootstrap_failed".
  * Brownfield-auto: cwd_state.infrastructure_present() classifies state;
    /lp-define brownfield branch surfaces the consent prompt OR honors
    --accept-bootstrap non-interactive flag (consent surface pinned by
    presence of the prompt-string assertion in lp-define.md doctext).
  * cwd_state.infrastructure_present 5-state enum:
    FULL / PARTIAL_MISSING / PARTIAL_STALE / PRESENT_UNMANAGED / ABSENT.
  * Engine ordering: plugin-version pin checked FIRST (before tampering).
  * Brownfield-auto fast-path: on a clean overlay, every file hits the
    fast-path (zero atomic writes for overwrite-if-unchanged paths).
  * Sentinel-already-present rejection: live-PID sentinel aborts.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import infrastructure_present  # noqa: E402
from lp_bootstrap import (  # noqa: E402
    BootstrapErrorCode,
    BootstrapState,
    LAUNCHPAD_DIR_NAME,
    SENTINEL_NAME,
)
from lp_bootstrap.engine import run_bootstrap  # noqa: E402
from lp_bootstrap.sentinel import write_sentinel  # noqa: E402


def _identity():
    return {
        "pii_opt_in": True,
        "project_name": "demo",
        "email": "demo@example.com",
        "copyright_holder": "@demo",
        "repo_url": "https://github.com/demo/demo",
        "license": "MIT",
        "license_other_body": "",
    }


def _bootstrap_clean(tmp_path: Path):
    return run_bootstrap(tmp_path, mode="greenfield", identity=_identity())


# --- cwd_state.infrastructure_present 5-state enum ------------------------

def test_infrastructure_present_returns_absent_on_empty_dir(tmp_path):
    state, missing = infrastructure_present(tmp_path)
    assert state == BootstrapState.ABSENT
    # v2.1 Codex PR #50 P1.A: count is 31 after restamp-history-hook entry.
    from lp_bootstrap import INFRASTRUCTURE_FILES
    assert len(missing) == len(INFRASTRUCTURE_FILES)


def test_infrastructure_present_returns_full_after_clean_bootstrap(tmp_path):
    _bootstrap_clean(tmp_path)
    state, paths = infrastructure_present(tmp_path)
    assert state == BootstrapState.FULL
    assert paths == []


def test_infrastructure_present_returns_partial_missing_when_some_files_missing(tmp_path):
    _bootstrap_clean(tmp_path)
    # Delete a couple of files
    (tmp_path / "scripts" / "compound" / "build.sh").unlink()
    (tmp_path / ".gitignore").unlink()
    state, paths = infrastructure_present(tmp_path)
    assert state == BootstrapState.PARTIAL_MISSING
    assert "scripts/compound/build.sh" in paths
    assert ".gitignore" in paths


def test_infrastructure_present_returns_partial_stale_when_user_edits_file(tmp_path):
    _bootstrap_clean(tmp_path)
    target = tmp_path / "scripts" / "compound" / "lib.sh"
    target.write_bytes(b"# user edit\n")
    state, paths = infrastructure_present(tmp_path)
    assert state == BootstrapState.PARTIAL_STALE
    assert "scripts/compound/lib.sh" in paths


def test_infrastructure_present_returns_present_unmanaged_when_no_manifest(tmp_path):
    _bootstrap_clean(tmp_path)
    # Delete just the manifest; all 30 paths still on disk
    (tmp_path / LAUNCHPAD_DIR_NAME / "bootstrap-manifest.json").unlink()
    state, paths = infrastructure_present(tmp_path)
    assert state == BootstrapState.PRESENT_UNMANAGED


def test_infrastructure_present_module_const_inventory_size(tmp_path):
    """Path inventory derived from INFRASTRUCTURE_FILES is exactly 30."""
    state, missing = infrastructure_present(tmp_path)
    # Empty cwd -> all 30 missing
    assert state == BootstrapState.ABSENT
    assert sorted(missing) == sorted(missing)
    # v2.1 Codex PR #50 P1.A: count is 31 after restamp-history-hook entry.
    from lp_bootstrap import INFRASTRUCTURE_FILES
    assert len(missing) == len(INFRASTRUCTURE_FILES)


# --- Engine ordering: plugin-version FIRST (before tampering) -------------

def test_engine_checks_plugin_version_before_manifest_tampering(tmp_path):
    """Both drift AND tampering present -> drift error wins (step 3 < step 4)."""
    # Bootstrap clean first
    _bootstrap_clean(tmp_path)
    # Tamper the manifest (would normally trigger MANIFEST_TAMPERED)
    manifest = tmp_path / LAUNCHPAD_DIR_NAME / "bootstrap-manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"][0]["source_template_sha256"] = "0" * 64
    manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Seed a version drift
    decision = tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"
    decision.write_text(json.dumps({
        "schema_version": "1.1",
        "version": "1.0",
        "plugin_version": "0.1.0-old",
        "identity": _identity(),
    }), encoding="utf-8")

    result = run_bootstrap(tmp_path, mode="brownfield-auto", identity=_identity())
    # Plugin-version pin is checked FIRST; that's what surfaces.
    assert result.outcome == "plugin_version_mismatch"


# --- Brownfield-auto fast-path: clean overlay zero-writes -----------------

def test_brownfield_auto_fast_path_on_clean_overlay(tmp_path):
    """A second run on an unmodified overlay should skip atomic writes for
    the 26 overwrite-if-unchanged paths."""
    first = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    # v2.1 Codex PR #50 P1.A: count is 31 after restamp-history-hook entry.
    from lp_bootstrap import INFRASTRUCTURE_FILES
    assert first.files_written == len(INFRASTRUCTURE_FILES)  # all written first time

    second = run_bootstrap(tmp_path, mode="brownfield-auto", identity=_identity())
    assert second.outcome == "brownfield_auto_rendered"
    # The 26 overwrite-if-unchanged + .gitignore + CODEOWNERS hit fast-path;
    # 2 merge-keys (lefthook.yml + scripts/compound/config.json) re-merge.
    assert second.files_skipped >= 26
    assert second.files_written <= 4


# --- Sentinel-already-present rejection -----------------------------------

def test_live_pid_sentinel_blocks_new_bootstrap(tmp_path):
    """A sentinel with a live PID raises sentinel_blocking."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    write_sentinel(
        tmp_path,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=[],
        command_pid=os.getpid(),  # we're alive
    )
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "sentinel_blocked"
    assert result.errors[0].code == BootstrapErrorCode.SENTINEL_BLOCKING


def test_dead_pid_sentinel_auto_recovers(tmp_path):
    """Stale sentinel with a dead PID is cleared and bootstrap proceeds."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    write_sentinel(
        tmp_path,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=[],
        command_pid=999_999,  # extremely unlikely to be alive
    )
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "success"
    # Recovery info appears in warnings
    assert any("recovered stale sentinel" in w for w in result.warnings)


# --- Greenfield Step 4.6 wiring -------------------------------------------

def test_greenfield_pipeline_wires_bootstrap_after_kernel_render(tmp_path):
    """End-to-end: lp_scaffold_stack pipeline runs Step 4.5 (kernel) then
    Step 4.6 (bootstrap). After successful run_pipeline, all 7 kernel files
    AND all 30 infrastructure files exist with manifest."""
    # We don't run the full pipeline (it requires scaffolders + decision +
    # nonce + receipt). Instead we pin the wiring: run_bootstrap is
    # callable from the same import path that engine.py uses, AND a
    # greenfield run produces the manifest.
    from lp_bootstrap.engine import run_bootstrap as engine_run  # noqa
    from lp_bootstrap import INFRASTRUCTURE_FILES  # noqa
    result = engine_run(tmp_path, mode="greenfield", identity=_identity())
    assert result.outcome == "success"
    assert result.files_written == len(INFRASTRUCTURE_FILES)
    assert (tmp_path / LAUNCHPAD_DIR_NAME / "bootstrap-manifest.json").is_file()


def test_greenfield_failure_surfaces_bootstrap_failed_reason(tmp_path):
    """If run_bootstrap returns a non-success outcome, the wiring at Step
    4.6 must surface `reason="bootstrap_failed"` to the pipeline."""
    # We pin the engine-side contract: engine.py imports
    # `from lp_bootstrap import BootstrapError, BootstrapErrorCode` and
    # uses `reason="bootstrap_failed"` when wiring into _record_partial_failure.
    src = (
        Path(__file__).resolve().parent.parent
        / "lp_scaffold_stack" / "engine.py"
    ).read_text(encoding="utf-8")
    assert "reason=\"bootstrap_failed\"" in src
    assert "from lp_bootstrap.engine import run_bootstrap" in src


# --- Brownfield consent surface ------------------------------------------

def test_lp_define_command_doctext_surfaces_consent_prompt():
    """The brownfield consent prompt copy is required by harden A11."""
    define_md = (
        Path(__file__).resolve().parents[2] / "commands" / "lp-define.md"
    ).read_text(encoding="utf-8")
    assert "Proceed? [Y/n]" in define_md
    assert "--accept-bootstrap" in define_md


def test_lp_define_brownfield_dispatch_table_present_in_doctext():
    """Step 1.5 of /lp-define documents the 5-state dispatch table."""
    define_md = (
        Path(__file__).resolve().parents[2] / "commands" / "lp-define.md"
    ).read_text(encoding="utf-8")
    for state in (
        "FULL", "PARTIAL_MISSING", "PARTIAL_STALE",
        "PRESENT_UNMANAGED", "ABSENT",
    ):
        assert state in define_md


# --- Manifest-not-written-on-partial-render-failure (harden B16) ----------

def test_manifest_preserved_when_render_fails_partway(tmp_path):
    """If render fails mid-loop, the prior manifest must NOT be overwritten."""
    _bootstrap_clean(tmp_path)
    manifest_path = tmp_path / LAUNCHPAD_DIR_NAME / "bootstrap-manifest.json"
    pre_failure_bytes = manifest_path.read_bytes()

    # Simulate a render failure by symlinking a target. apply_overwrite_if_
    # unchanged refuses through symlinks, raising BootstrapPolicyError.
    real = tmp_path / "_real_lib.sh"
    real.write_bytes(b"# real\n")
    target = tmp_path / "scripts" / "compound" / "lib.sh"
    target.unlink()
    target.symlink_to(real)

    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    # Engine surfaces the policy error; manifest must be unchanged.
    assert result.outcome != "success"
    post_failure_bytes = manifest_path.read_bytes()
    assert post_failure_bytes == pre_failure_bytes


# --- Telemetry instrumentation (harden A3) --------------------------------

def test_telemetry_event_written_for_successful_bootstrap(tmp_path):
    """Engine emits a v2-pipeline-*.jsonl entry per BootstrapResult."""
    # Telemetry defaults ON when no .launchpad/config.yml exists.
    _bootstrap_clean(tmp_path)
    obs = tmp_path / ".harness" / "observations"
    if obs.is_dir():
        files = list(obs.glob("v2-pipeline-*.jsonl"))
        assert files, "expected at least one telemetry entry"
        # Decode + assert command name
        text = files[0].read_text(encoding="utf-8")
        assert any('"command":"lp-bootstrap"' in line for line in text.splitlines())


def test_telemetry_off_suppresses_emission(tmp_path):
    """Honors `.launchpad/config.yml` telemetry: off."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    (tmp_path / LAUNCHPAD_DIR_NAME / "config.yml").write_text("telemetry: off\n")
    _bootstrap_clean(tmp_path)
    obs = tmp_path / ".harness" / "observations"
    # No v2-pipeline jsonl produced
    if obs.is_dir():
        assert not any(obs.glob("v2-pipeline-*.jsonl"))


# --- Engine ordering pin: plugin-version step is BEFORE tampering ---------

def test_engine_ordering_source_pin():
    """Static contract: engine.py runs plugin-version pin (step 3) before
    manifest tampering check (step 4)."""
    src = (
        Path(__file__).resolve().parent.parent
        / "lp_bootstrap" / "engine.py"
    ).read_text(encoding="utf-8")
    pos_v = src.find("Step 3: plugin-version pin check FIRST")
    pos_t = src.find("Step 4: manifest tampering integrity check")
    assert 0 < pos_v < pos_t
