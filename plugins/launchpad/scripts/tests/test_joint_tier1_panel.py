"""Phase 7 §4.5 — Tier 1 panel verification (gate #8).

Per OPERATIONS §6 acceptance gate #8. The Tier 1 governance panel is the
post-scaffold reveal that surfaces concrete numbers from
`scaffold-receipt.json.tier1_governance_summary` to the user.

Three variants per handoff §4.5:

  - **Greenfield**: receipt has the 4 standard fields with concrete numbers.
    (Phase 3's `receipt_writer.build_receipt_payload()` populates 4 fields:
    `whitelisted_paths`, `lefthook_hooks`, `slash_commands_wired`,
    `architecture_docs_rendered`. The "5 enumerated items" prescription in
    handoff §4.5 / OPERATIONS §5 was the pre-strip-back spec; Phase 3 ships
    4. See Phase 7 finding observation if the discrepancy needs revisiting.)

  - **Brownfield**: pipeline is rejected at Step 0; no receipt exists, so
    the panel surface IS the scaffold-rejection log under
    `.harness/observations/`. We assert the rejection log carries enough
    forensic context for a brownfield Tier 1 panel to render from it.

  - **Telemetry-disabled**: with `LP_TELEMETRY=off` (via `.launchpad/config.yml`
    `telemetry: off`), the receipt's panel summary is UNCHANGED — telemetry
    opt-out gates the `v2-pipeline-*.jsonl` analytics writes, NOT the
    receipt's tier1_governance_summary. (The "(disabled)" placeholder per
    OPERATIONS §5 is a UI-render concern; the receipt is the data source.)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _phase5_decision_builder import (  # noqa: E402
    STACK_COMBOS,
    build_decision,
    write_decision_to_cwd,
    write_first_run_marker,
    write_matching_rationale_md,
)
from scaffold_smoke_runner import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
    PLUGIN_SCAFFOLD_STACK,
    _read_latest_rejection,
)
from test_joint_pipeline_smoke import _stub_scaffolders_yml  # noqa: E402


def _make_tempdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-joint-tier1-"))
    os.chmod(d, 0o700)
    return d


def _build_clean_setup(cwd: Path) -> Path:
    """Build a valid greenfield setup (decision + rationale + marker + stub
    scaffolders.yml) and return the stub catalog path."""
    spec = STACK_COMBOS["A"]
    decision = build_decision(
        spec["stack_combo"], cwd,
        monorepo=spec["monorepo"],
        matched_category_id=spec["matched_category_id"],
    )
    write_decision_to_cwd(decision, cwd)
    write_matching_rationale_md(decision, cwd)
    write_first_run_marker(cwd)
    return _stub_scaffolders_yml(cwd / ".launchpad" / "stub-scaffolders.yml")


def _invoke_cli(cwd: Path, scaffolders_yml: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, str(PLUGIN_SCAFFOLD_STACK),
            "--cwd", str(cwd),
            "--scaffolders-yml", str(scaffolders_yml),
            "--category-patterns-yml", str(DEFAULT_CATEGORY_PATTERNS_YML),
            "--plugins-root", str(DEFAULT_PLUGINS_ROOT),
            # NOTE: telemetry flag is per-test; greenfield/brownfield variants
            # leave telemetry enabled (default), telemetry-disabled variant
            # writes config.yml `telemetry: off` BEFORE invocation.
        ],
        capture_output=True, timeout=60, check=False,
    )


def test_tier1_panel_greenfield():
    """Greenfield variant: receipt's tier1_governance_summary has the 4
    Phase 3 fields populated."""
    cwd = _make_tempdir()
    try:
        stub = _build_clean_setup(cwd)
        rv = _invoke_cli(cwd, stub)
        assert rv.returncode == 0, (
            f"pipeline failed: stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )
        receipt = json.loads(
            (cwd / ".launchpad" / "scaffold-receipt.json").read_text(
                encoding="utf-8",
            ),
        )
        panel = receipt.get("tier1_governance_summary")
        assert isinstance(panel, dict), (
            f"tier1_governance_summary missing or wrong shape: {panel!r}"
        )
        # Phase 3's receipt_writer.build_receipt_payload populates these 4:
        for required in (
            "whitelisted_paths", "lefthook_hooks",
            "slash_commands_wired", "architecture_docs_rendered",
        ):
            assert required in panel, (
                f"tier1_governance_summary missing field {required!r}: {panel!r}"
            )
        # Concrete numbers populated.
        assert isinstance(panel["whitelisted_paths"], int)
        assert isinstance(panel["lefthook_hooks"], list)
        assert len(panel["lefthook_hooks"]) == 4, (
            f"lefthook_hooks expected 4 entries, got "
            f"{len(panel['lefthook_hooks'])}: {panel['lefthook_hooks']!r}"
        )
        assert set(panel["lefthook_hooks"]) == {
            "secret-scan", "structure-drift", "typecheck", "lint",
        }
        assert isinstance(panel["slash_commands_wired"], int)
        assert panel["architecture_docs_rendered"] == 8, (
            f"architecture_docs_rendered expected 8 (TIER1_ARCHITECTURE_"
            f"DOCS_RENDERED constant); got {panel['architecture_docs_rendered']!r}"
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_tier1_panel_brownfield():
    """Brownfield variant: pipeline rejected at Step 0; no receipt; the
    Tier 1 panel surface IS the scaffold-rejection log."""
    cwd = _make_tempdir()
    try:
        # Pre-populate brownfield indicator BEFORE the setup.
        (cwd / "package.json").write_text(
            '{"name":"existing-project"}', encoding="utf-8",
        )
        # Build a valid decision in a sibling tmpdir, move .launchpad into the
        # brownfield cwd. (Per joint_pipeline_smoke pattern.)
        prep = _make_tempdir()
        try:
            stub_path_in_prep = _build_clean_setup(prep)
            # Move .launchpad into the brownfield cwd.
            shutil.move(
                str(prep / ".launchpad"),
                str(cwd / ".launchpad"),
            )
            stub_path = cwd / ".launchpad" / stub_path_in_prep.name
        finally:
            shutil.rmtree(prep, ignore_errors=True)

        rv = _invoke_cli(cwd, stub_path)
        assert rv.returncode != 0, "pipeline accepted brownfield (expected reject)"
        rejection = _read_latest_rejection(cwd)
        assert rejection is not None, (
            "no scaffold-rejection-*.jsonl written; brownfield Tier 1 panel "
            "has no data source"
        )
        # Forensic context for brownfield panel: reason + timestamp + pid.
        assert rejection.get("reason") == "cwd_state_brownfield"
        assert rejection.get("timestamp")
        assert rejection.get("pid")
        # No receipt should exist (no greenfield panel).
        assert not (cwd / ".launchpad" / "scaffold-receipt.json").exists()
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_tier1_panel_telemetry_disabled():
    """Telemetry-disabled variant: receipt panel is UNCHANGED with telemetry
    off (telemetry opt-out gates analytics, not the receipt schema)."""
    cwd = _make_tempdir()
    try:
        stub = _build_clean_setup(cwd)
        # Write `.launchpad/config.yml` with telemetry: off BEFORE invocation.
        (cwd / ".launchpad" / "config.yml").write_text(
            "telemetry: off\n", encoding="utf-8",
        )
        rv = _invoke_cli(cwd, stub)
        assert rv.returncode == 0, (
            f"pipeline failed: stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )
        receipt = json.loads(
            (cwd / ".launchpad" / "scaffold-receipt.json").read_text(
                encoding="utf-8",
            ),
        )
        panel = receipt["tier1_governance_summary"]
        # Same 4 fields as greenfield variant.
        assert "whitelisted_paths" in panel
        assert "lefthook_hooks" in panel
        assert "slash_commands_wired" in panel
        assert panel["architecture_docs_rendered"] == 8

        # Telemetry analytics file should NOT exist.
        obs = cwd / ".harness" / "observations"
        v2_pipeline_files = list(obs.glob("v2-pipeline-*.jsonl")) if obs.exists() else []
        assert not v2_pipeline_files, (
            f"telemetry: off but v2-pipeline-*.jsonl was written: "
            f"{v2_pipeline_files!r}"
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
