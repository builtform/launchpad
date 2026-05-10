"""D15 regression-shield (v2.1.1 Phase 4): cwd_state README carve-out.

Per BL-236 D-verdict D15: clarity rewrite of the single-README greenfield
carve-out at cwd_state.py:73-83. Behavior MUST be preserved (D15 is a
clarity refactor, not a correctness change). This test pins the
README-only-greenfield case + the sized-extra-file edge case so a future
refactor that accidentally inverts the logic fails the gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ on sys.path for sibling-module imports.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import cwd_state as classify_cwd  # noqa: E402


def test_readme_plus_small_extra_classifies_empty(tmp_path):
    """README.md + 1 small (<= 100B) other file → 'empty'."""
    (tmp_path / "README.md").write_text("# Hello\n")  # ~10 B
    (tmp_path / ".editorconfig").write_text("root = true\n")  # ~13 B
    assert classify_cwd(tmp_path) == "empty"


def test_readme_plus_large_extra_classifies_ambiguous(tmp_path):
    """README.md + 1 large (> 100B) other file → 'ambiguous' (PR #41 cycle 7 #3)."""
    (tmp_path / "README.md").write_text("# Hello\n")
    # 200 bytes — exceeds 100B carve-out threshold
    (tmp_path / "stray.txt").write_text("x" * 200)
    assert classify_cwd(tmp_path) == "ambiguous"


def test_large_readme_with_small_extra_classifies_ambiguous(tmp_path):
    """Large README (>= 500B) + 1 small extra → 'ambiguous' (D15 dual-size invariant)."""
    (tmp_path / "README.md").write_text("x" * 600)  # 600 B — exceeds 500B carve-out threshold
    (tmp_path / ".editorconfig").write_text("root = true\n")
    assert classify_cwd(tmp_path) == "ambiguous"


def test_only_readme_classifies_empty(tmp_path):
    """Just README.md (in OK_FILES) → 'empty' regardless of size threshold —
    the carve-out only fires when there's an EXTRA file beyond OK_FILES.
    Plain README is in GREENFIELD_OK_FILES so extras = empty set."""
    (tmp_path / "README.md").write_text("# Hello\n")
    assert classify_cwd(tmp_path) == "empty"


def test_no_readme_with_one_small_extra_classifies_ambiguous(tmp_path):
    """Carve-out requires README presence; without README, single small
    extra classifies as 'ambiguous' (carve-out does NOT fire)."""
    (tmp_path / ".editorconfig").write_text("x")
    assert classify_cwd(tmp_path) == "ambiguous"
