"""v2.1 Codex PR #50 P1.D (D4) regression: --dry-run sentinel-lifecycle smoke.

Tests:
  * dry_run=True acquires + clears sentinel
  * dry_run=True writes NO manifest
  * dry_run=True returns BootstrapResult.outcome == "success"
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _identity():
    return {
        "pii_opt_in": True,
        "project_name": "smoke",
        "email": "a@b.c",
        "copyright_holder": "X",
        "repo_url": "https://github.com/x/y",
        "license": "MIT",
    }


def test_dry_run_clean_tmpdir(tmp_path):
    from lp_bootstrap.engine import run_bootstrap
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity(), dry_run=True)
    assert result.outcome == "success"
    assert result.files_processed == 0
    assert result.files_written == 0
    assert not (tmp_path / ".launchpad" / "bootstrap-manifest.json").exists()
    assert not (tmp_path / ".launchpad" / ".bootstrap-in-progress").exists()


def test_dry_run_returns_no_errors(tmp_path):
    from lp_bootstrap.engine import run_bootstrap
    result = run_bootstrap(tmp_path, mode="greenfield", identity=_identity(), dry_run=True)
    assert result.errors == ()
