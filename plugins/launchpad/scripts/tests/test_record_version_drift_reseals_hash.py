"""v2.1 Codex PR #50 cycle 6 F9: `_record_version_drift` reseals sha256.

Cycle 5's `_record_version_drift` mutated the sealed scaffold-decision
payload by appending `version_drift_log[]` and wrote it back via
`atomic_write_replace` WITHOUT recomputing the `sha256` envelope. The
decision_validator later recomputes the hash and rejects mismatches,
so `/lp-bootstrap --accept-plugin-version-drift` produced a hash-invalid
file that broke subsequent `/lp-scaffold-stack` / `/lp-bootstrap` runs.

Cycle 6 routes the mutation through `re_seal_decision_atomic()`. This
test asserts:
  1. `version_drift_log` field is appended correctly
  2. `sha256` matches `seal_decision_payload(payload-minus-sha256)`
  3. `generated_at` is byte-identical pre/post (DA9 invariant)
  4. File mode is 0o600 post-write (T0-2 / DA-F9.1 contract pin)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_bootstrap import LAUNCHPAD_DIR_NAME
from lp_bootstrap.engine import _record_version_drift
from lp_pick_stack.decision_writer import seal_decision_payload


def _seed_sealed_decision(cwd: Path, plugin_version: str = "1.0.0") -> dict:
    """Seed a sealed scaffold-decision.json in cwd/.launchpad/."""
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


def test_record_version_drift_writes_valid_hash(tmp_path: Path) -> None:
    """Hash chain valid after drift-log append; mode 0o600."""
    sealed_pre = _seed_sealed_decision(tmp_path, plugin_version="1.0.0")
    pre_generated_at = sealed_pre["generated_at"]

    _record_version_drift(
        tmp_path, dict(sealed_pre), from_version="1.0.0", to_version="2.0.0",
    )

    decision_path = tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"
    written = json.loads(decision_path.read_text(encoding="utf-8"))

    # 1. version_drift_log appended
    assert written.get("version_drift_log"), "drift log missing"
    assert len(written["version_drift_log"]) == 1
    entry = written["version_drift_log"][0]
    assert entry["from_version"] == "1.0.0"
    assert entry["to_version"] == "2.0.0"
    assert entry["via"] == "bootstrap"

    # 2. sha256 envelope matches re-seal of payload-minus-sha256
    on_disk_sha = written.pop("sha256")
    assert on_disk_sha is not None, "sha256 missing post-mutation (F9 regression)"
    resealed = seal_decision_payload(written)
    assert resealed["sha256"] == on_disk_sha, (
        "hash chain invalid (F9 regression): on-disk sha256 != "
        "seal_decision_payload(payload-minus-sha256)"
    )

    # 3. generated_at byte-identical (DA9 invariant)
    assert written["generated_at"] == pre_generated_at

    # 4. mode 0o600 (DA-F9.1 contract pin; T0-2 intentional tightening)
    assert (os.stat(decision_path).st_mode & 0o777) == 0o600
