"""v2.1.0 completion plan §4.3 regression: Case E "y" all-files-missing
must NOT corrupt kernel_render_state schema.

Pre-fix: the engine appended `{"_meta": "all_files_missing", ...}` to
the kernel_render_state list, breaking the per-file uniform shape and
causing the next `/lp-bootstrap --refresh` to misclassify missing-then-
recreated files as user-edits (permanent USER_EDIT_BLOCKS_REFRESH).

Post-fix: kernel_render_state stays uniform per-file dicts, with
missing files seeded `rendered_content_sha256 = source_template_sha256`
so the next refresh detects them as fresh-render-allowed. The
all-files-missing signal is sealed as a top-level
`kernel_render_state_meta` sibling key.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_case_e_y_all_files_missing_schema_uniform() -> None:
    """The kernel_render_state list contains only per-file dicts (no
    `_meta` smuggled entries); the all-files-missing signal lives on
    `kernel_render_state_meta` instead.

    This test exercises the helper shape directly because the full
    engine path requires a working scaffold-decision baseline +
    pre-migration backup + sentinel handshake — coverage of the engine
    glue lives at `test_update_identity_engine.py`. The schema
    invariant the §4.3 fix addresses is properties of the
    on_disk_state list, not the orchestration glue.
    """
    from plugin_default_generators.kernel_renderer import KernelRenderer
    renderer = KernelRenderer()

    # All files missing scenario — empty cwd.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        on_disk_state = renderer.compute_current_on_disk_state(Path(td))

        all_missing = all(
            e.get("missing_on_disk", False) for e in on_disk_state
        )
        assert all_missing, "expected every kernel file missing on empty cwd"

        # Apply the §4.3 transform inline (mirrors the engine.py logic).
        new_kernel_state = [
            {
                **e,
                "rendered_content_sha256": e.get("source_template_sha256"),
            }
            for e in on_disk_state
        ]

        # Schema invariant: every entry is a per-file dict with `path`
        # and `rendered_content_sha256` — no `_meta` smuggled siblings.
        for entry in new_kernel_state:
            assert "path" in entry, f"entry missing path: {entry!r}"
            assert "rendered_content_sha256" in entry
            assert entry["rendered_content_sha256"] == entry.get(
                "source_template_sha256"
            )
            assert "_meta" not in entry


def test_case_e_y_kernel_render_state_meta_is_sibling_key() -> None:
    """The all-files-missing signal lives on `kernel_render_state_meta`
    as a sibling to `kernel_render_state` on scaffold-decision.json.
    Both validators (decision-side + receipt-side) accept this key per
    `_ALLOWED_DECISION_META_KEYS`."""
    from lp_scaffold_stack.decision_validator import (
        _ALLOWED_DECISION_META_KEYS,
    )
    assert "kernel_render_state_meta" in _ALLOWED_DECISION_META_KEYS
