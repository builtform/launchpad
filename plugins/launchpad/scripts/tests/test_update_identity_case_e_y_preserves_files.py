"""v2.1 Codex PR #50 Greptile #6 (D6) regression: Case E "y" preserves files.

Tests (v2.1.0 Codex P1 #2 fold updates):
  * compute_current_on_disk_state returns expected keys (no user_has_drift)
  * Missing files seal `missing_on_disk: True` AND placeholder
    `rendered_content_sha256 == source_template_sha256`
  * Idempotent (read-only, side-effect-free).
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def test_compute_current_on_disk_state_returns_expected_keys(tmp_path):
    from plugin_default_generators.kernel_renderer import KernelRenderer
    state = KernelRenderer().compute_current_on_disk_state(tmp_path)
    assert isinstance(state, list)
    assert len(state) == 7  # 7 kernel files
    for entry in state:
        assert "path" in entry
        assert "rendered_content_sha256" in entry
        assert "source_template_sha256" in entry
        assert "missing_on_disk" in entry
        # v2.1.0 Codex P1 #2 fold: user_has_drift dropped entirely.
        assert "user_has_drift" not in entry


def test_compute_current_on_disk_state_marks_missing_files(tmp_path):
    from plugin_default_generators.kernel_renderer import KernelRenderer
    state = KernelRenderer().compute_current_on_disk_state(tmp_path)
    for entry in state:
        assert entry["missing_on_disk"] is True
        # v2.1.0 Codex P1 #2 fold: missing files now seal the template SHA
        # as a placeholder (was `None`); the disambiguating signal is
        # `missing_on_disk`. This keeps schema consumers happy by always
        # having a 64-hex SHA in the field.
        assert entry["rendered_content_sha256"] == entry["source_template_sha256"]


def test_compute_current_on_disk_state_idempotent(tmp_path):
    """Read-only, side-effect-free, returns a fresh list on each call."""
    from plugin_default_generators.kernel_renderer import KernelRenderer
    r = KernelRenderer()
    a = r.compute_current_on_disk_state(tmp_path)
    b = r.compute_current_on_disk_state(tmp_path)
    assert a == b
    assert a is not b  # fresh list each time
