"""D11 regression-shield (v2.1.1 Phase 4): nonce_ledger longest-prefix-match
tiebreak.

Per BL-236 D-verdict D11: when /proc/self/mountinfo contains two mount-point
entries with EQUAL-length prefixes that both match the target path, the
longest-prefix-match must use strict `>` (first-seen wins), NOT `>=` (later-
seen wins, which is filesystem-ordering-dependent and non-deterministic).

This test pins the new tiebreak behavior. Without the D11 fix the test
would fail because `>=` causes the LATER duplicate to overwrite `best_fs`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

# scripts/ on sys.path for sibling-module imports.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.nonce_ledger import _detect_filesystem_type  # noqa: E402


def test_mountpoint_equal_length_prefix_tiebreak_first_seen_wins(tmp_path):
    """Two equal-length prefix matches: first-seen MUST win (D11)."""
    # Synthetic mountinfo: two entries with the SAME mount-point depth,
    # both prefix-matching `/data/x`. Without D11 fix, `ext4` (LATER) would
    # overwrite `xfs` (EARLIER) due to `>=` tiebreak. With D11 fix
    # (strict `>`), `xfs` (FIRST) wins.
    mountinfo_content = (
        "1 2 0:1 / /data rw,relatime - xfs /dev/sda1 rw\n"
        "3 4 0:2 / /data rw,relatime - ext4 /dev/sdb1 rw\n"
    )
    target = tmp_path / "x"
    target.touch()

    # Force the function to think we are on Linux + read our synthetic
    # mountinfo. Also clear the per-process cache so the call is fresh.
    import lp_scaffold_stack.nonce_ledger as nm

    nm._FS_TYPE_CACHE.clear()
    fake_mountinfo = mock.mock_open(read_data=mountinfo_content)

    with (
        mock.patch.object(sys, "platform", "linux"),
        mock.patch("os.path.realpath", return_value="/data/x"),
        mock.patch("builtins.open", fake_mountinfo),
    ):
        result = _detect_filesystem_type(target)

    # D11 fix: strict `>` tiebreak → first-seen (xfs) wins.
    # Pre-fix `>=` would have produced "ext4" (later overwrites).
    assert result == "xfs", (
        f"D11 regression: expected 'xfs' (first-seen wins under strict-`>` "
        f"tiebreak); got {result!r}. If 'ext4', the `>=` regression has "
        f"reappeared at lp_scaffold_stack/nonce_ledger.py:_detect_filesystem_type."
    )
