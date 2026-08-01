"""Regression: `/lp-bootstrap --recover` is sentinel-clear-only, BY DESIGN.

Recover mode had zero test coverage before this file (a repo-wide grep for
`mode="recover"` matched nothing in source or tests), which is how a
doc/implementation divergence survived: `lp-bootstrap.md` described recover as
also unlinking a "provably stale" manifest to close a plugin-version downgrade
window, and nothing contradicted it.

That documented step was withdrawn rather than implemented (BL-376), because
the rationale was wrong twice over:

  * `_check_plugin_version_pin` reads `plugin.json` and
    `scaffold-decision.json` only -- never the manifest -- so retaining a
    stale manifest cannot bypass the version pin.
  * A missing manifest leaves `manifest_rendered_sha` None, which `policy.py`
    treats as "target absent" and OVERWRITES unconditionally. Unlinking would
    destroy the user-edit protection it claimed to strengthen, and the plain
    bootstrap path writes no backup first.

`test_recover_preserves_existing_manifest` is the load-bearing one: it pins
the deliberate non-unlink so the withdrawn behavior cannot be reintroduced
without deleting an explicit test that says why.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap import (  # noqa: E402
    LAUNCHPAD_DIR_NAME,
    MANIFEST_FILENAME,
    BootstrapErrorCode,
    BootstrapStatus,
)
from lp_bootstrap.engine import run_bootstrap  # noqa: E402
from lp_bootstrap.sentinel import write_sentinel  # noqa: E402

DEAD_PID = 999_999  # extremely unlikely to be alive


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


def _write_dead_sentinel(cwd: Path) -> None:
    (cwd / LAUNCHPAD_DIR_NAME).mkdir(exist_ok=True)
    write_sentinel(
        cwd,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=[],
        command_pid=DEAD_PID,
    )


def test_recover_with_stale_sentinel_reports_recovered_status(tmp_path):
    _write_dead_sentinel(tmp_path)
    result = run_bootstrap(tmp_path, mode="recover", identity=_identity())

    assert result.outcome == "success"
    assert result.status is BootstrapStatus.RECOVERED_SENTINEL_CLEAR_ONLY
    assert not (tmp_path / LAUNCHPAD_DIR_NAME / ".bootstrap-in-progress").exists()
    assert result.files_written == 0


def test_recover_with_no_sentinel_reports_no_status(tmp_path):
    """`status` discriminates "cleared something" from a no-op clear."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    result = run_bootstrap(tmp_path, mode="recover", identity=_identity())

    assert result.outcome == "success"
    assert result.status is None


def test_recover_preserves_existing_manifest(tmp_path):
    """Recover must NOT unlink the manifest. See module docstring / BL-376."""
    run_bootstrap(tmp_path, mode="greenfield", identity=_identity())
    manifest = tmp_path / LAUNCHPAD_DIR_NAME / MANIFEST_FILENAME
    assert manifest.is_file(), "greenfield bootstrap should write a manifest"
    before = manifest.read_bytes()

    _write_dead_sentinel(tmp_path)
    result = run_bootstrap(tmp_path, mode="recover", identity=_identity())

    assert result.outcome == "success"
    assert manifest.is_file(), "recover must not unlink the manifest"
    assert manifest.read_bytes() == before, "recover must not rewrite the manifest"


def test_recover_does_not_bypass_a_live_sentinel(tmp_path):
    """A live-PID sentinel still blocks; recover is not a force-unlock."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    write_sentinel(
        tmp_path,
        mode="greenfield",
        pre_edit_manifest_sha256=None,
        target_paths=[],
        command_pid=os.getpid(),
    )
    result = run_bootstrap(tmp_path, mode="recover", identity=_identity())

    assert result.outcome != "success"
    assert any(e.code == BootstrapErrorCode.SENTINEL_BLOCKING for e in result.errors)


def test_withdrawn_stale_sentinel_status_member_stays_deleted(tmp_path):
    """`STALE_SENTINEL_DETECTED` was dead code describing absent predicates.

    The sentinel carries no hostname field and no age check exists, so the
    member (and `STALE_SENTINEL_THRESHOLD_HOURS`) described behavior that was
    never implemented. Pin the deletion so it is not reintroduced by symmetry.
    """
    assert not hasattr(BootstrapStatus, "STALE_SENTINEL_DETECTED")
    import lp_bootstrap

    assert not hasattr(lp_bootstrap, "STALE_SENTINEL_THRESHOLD_HOURS")
