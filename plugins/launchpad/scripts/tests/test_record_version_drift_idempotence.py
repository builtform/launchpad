"""v2.1 Codex PR #50 cycle 6 T1-7: `_record_version_drift` is idempotent.

Two consecutive drift-accepts (e.g., 1.0.0 -> 2.0.0, then 2.0.0 -> 2.1.0)
must:
  1. Append both entries to `version_drift_log` (not replace)
  2. Preserve `generated_at` byte-identical across both invocations
  3. Hash chain valid after each
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_bootstrap import LAUNCHPAD_DIR_NAME
from lp_bootstrap.engine import _record_version_drift
from lp_pick_stack.decision_writer import seal_decision_payload


def _seed_sealed_decision(cwd: Path, plugin_version: str) -> dict:
    (cwd / LAUNCHPAD_DIR_NAME).mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.1",
        "version": "1.0",
        "plugin_version": plugin_version,
        "generated_at": "2026-05-07T12:00:00Z",
        "identity": {
            "pii_opt_in": False,
            "project_name": "<project-name>",
            "email": "<email>",
            "copyright_holder": "<copyright-holder>",
            "repo_url": "<repo-url>",
            "license": "Other",
            "license_other_body": "",
        },
    }
    sealed = seal_decision_payload(payload)
    decision_path = cwd / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"
    decision_path.write_text(
        json.dumps(sealed, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return sealed


def test_repeated_drift_accept_appends_entries(tmp_path: Path) -> None:
    sealed_pre = _seed_sealed_decision(tmp_path, plugin_version="1.0.0")
    pre_generated_at = sealed_pre["generated_at"]

    decision_path = tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"

    # First drift: 1.0.0 -> 2.0.0
    payload1 = json.loads(decision_path.read_text(encoding="utf-8"))
    _record_version_drift(
        tmp_path, payload1, from_version="1.0.0", to_version="2.0.0",
    )

    # Second drift: 2.0.0 -> 2.1.0 (re-read from disk to simulate fresh invoke)
    payload2 = json.loads(decision_path.read_text(encoding="utf-8"))
    _record_version_drift(
        tmp_path, payload2, from_version="2.0.0", to_version="2.1.0",
    )

    written = json.loads(decision_path.read_text(encoding="utf-8"))
    log = written["version_drift_log"]
    assert len(log) == 2, (
        f"expected 2 drift entries (append, not replace), got {len(log)}"
    )
    assert log[0]["from_version"] == "1.0.0"
    assert log[0]["to_version"] == "2.0.0"
    assert log[1]["from_version"] == "2.0.0"
    assert log[1]["to_version"] == "2.1.0"

    # generated_at byte-identical across both reseals
    assert written["generated_at"] == pre_generated_at

    # Hash chain valid after the second reseal
    on_disk_sha = written.pop("sha256")
    resealed = seal_decision_payload(written)
    assert resealed["sha256"] == on_disk_sha
