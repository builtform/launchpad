"""v2.1 Codex PR #50 cycle 6 T2-8 / DA-F9.3: unsealed-decision refuses-loud.

If `_record_version_drift` is invoked against a missing or malformed
scaffold-decision.json, it must raise
`BootstrapEngineError(VERSION_DRIFT_RESEAL_FAILED)` with actionable
remediation (rather than the unstructured exceptions that
`re_seal_decision_atomic` would otherwise propagate).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_bootstrap import BootstrapErrorCode, LAUNCHPAD_DIR_NAME
from lp_bootstrap.engine import BootstrapEngineError, _record_version_drift


def test_missing_decision_file_raises_structured_error(tmp_path: Path) -> None:
    """No `.launchpad/scaffold-decision.json` -> VERSION_DRIFT_RESEAL_FAILED."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()

    with pytest.raises(BootstrapEngineError) as excinfo:
        _record_version_drift(
            tmp_path, {"identity": {}},
            from_version="1.0.0", to_version="2.0.0",
        )
    assert excinfo.value.reason == (
        BootstrapErrorCode.VERSION_DRIFT_RESEAL_FAILED
    )
    assert "could not reseal" in str(excinfo.value)
    assert "/lp-bootstrap --refresh" in excinfo.value.remediation


def test_malformed_decision_file_raises_structured_error(tmp_path: Path) -> None:
    """Hand-edited / malformed JSON -> VERSION_DRIFT_RESEAL_FAILED."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    (tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json").write_text(
        "{not valid json", encoding="utf-8",
    )

    with pytest.raises(BootstrapEngineError) as excinfo:
        _record_version_drift(
            tmp_path, {"identity": {}},
            from_version="1.0.0", to_version="2.0.0",
        )
    assert excinfo.value.reason == (
        BootstrapErrorCode.VERSION_DRIFT_RESEAL_FAILED
    )


def test_non_object_decision_raises_structured_error(tmp_path: Path) -> None:
    """Top-level non-object payload -> VERSION_DRIFT_RESEAL_FAILED."""
    (tmp_path / LAUNCHPAD_DIR_NAME).mkdir()
    (tmp_path / LAUNCHPAD_DIR_NAME / "scaffold-decision.json").write_text(
        '["not", "an", "object"]', encoding="utf-8",
    )

    with pytest.raises(BootstrapEngineError) as excinfo:
        _record_version_drift(
            tmp_path, {"identity": {}},
            from_version="1.0.0", to_version="2.0.0",
        )
    assert excinfo.value.reason == (
        BootstrapErrorCode.VERSION_DRIFT_RESEAL_FAILED
    )
