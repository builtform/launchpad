"""Regression tests for the backlog-orphan-check slip-prevention gate.

The gate exists because BL-236 (lefthook Python coverage) was labeled
v2.1 in BACKLOG.md but never implemented or deferred. These tests pin
the contract that surfaced the slip on 2026-05-07: a BL labeled for the
release MUST have either a `**Status**:` close marker OR a CHANGELOG
reference, otherwise the script exits 1 with a per-orphan report.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "plugin-backlog-orphan-check.py"
)


def _write(tmp_path: Path, backlog: str, changelog: str) -> tuple[Path, Path]:
    bl = tmp_path / "BACKLOG.md"
    cl = tmp_path / "CHANGELOG.md"
    bl.write_text(textwrap.dedent(backlog).lstrip(), encoding="utf-8")
    cl.write_text(textwrap.dedent(changelog).lstrip(), encoding="utf-8")
    return bl, cl


def _run(release: str, bl: Path, cl: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            release,
            "--backlog",
            str(bl),
            "--changelog",
            str(cl),
        ],
        capture_output=True,
        text=True,
    )


def test_pass_when_status_marker_present(tmp_path: Path) -> None:
    bl, cl = _write(
        tmp_path,
        """
        # BACKLOG
        #### BL-100 - v2.1: shipped feature
        **Status (2026-05-07)**: SHIPPED in v2.1.0.
        Body text.
        """,
        """
        # Changelog
        ## [2.1.0]
        ### Added
        - Something unrelated
        """,
    )
    r = _run("2.1.0", bl, cl)
    assert r.returncode == 0, r.stderr
    assert "PASS" in r.stdout


def test_pass_when_changelog_references_bl(tmp_path: Path) -> None:
    bl, cl = _write(
        tmp_path,
        """
        # BACKLOG
        #### BL-200 - v2.1: shipped feature
        Body text.
        """,
        """
        # Changelog
        ## [2.1.0]
        ### Added
        - Sealed identity contract (BL-200)
        """,
    )
    r = _run("2.1.0", bl, cl)
    assert r.returncode == 0, r.stderr
    assert "PASS" in r.stdout


def test_fails_when_orphan_present(tmp_path: Path) -> None:
    bl, cl = _write(
        tmp_path,
        """
        # BACKLOG
        #### BL-236 - v2.1: lefthook Python coverage
        Body without status line.
        """,
        """
        # Changelog
        ## [2.1.0]
        ### Added
        - Something completely unrelated
        """,
    )
    r = _run("2.1.0", bl, cl)
    assert r.returncode == 1
    assert "BL-236" in r.stderr
    assert "FAIL" in r.stderr


def test_v_minor_label_matches_minor_zero_release(tmp_path: Path) -> None:
    bl, cl = _write(
        tmp_path,
        """
        # BACKLOG
        #### BL-300 - v2.1: orphan
        Body.
        """,
        "# Changelog\n",
    )
    r = _run("2.1.0", bl, cl)
    assert r.returncode == 1
    assert "BL-300" in r.stderr


def test_explicit_patch_label_does_not_match_dot_zero(tmp_path: Path) -> None:
    bl, cl = _write(
        tmp_path,
        """
        # BACKLOG
        #### BL-400 - v2.1.1: deferred to patch lane
        Body.
        """,
        "# Changelog\n",
    )
    r = _run("2.1.0", bl, cl)
    assert r.returncode == 0, r.stderr


def test_re_targeted_status_value_counts_as_closed(tmp_path: Path) -> None:
    bl, cl = _write(
        tmp_path,
        """
        # BACKLOG
        #### BL-500 - v2.1: re-targeted
        **Status (2026-05-07)**: RE-TARGETED v2.1 -> v2.1.1.
        Body.
        """,
        "# Changelog\n",
    )
    r = _run("2.1.0", bl, cl)
    assert r.returncode == 0, r.stderr


def test_multi_version_label_is_parsed(tmp_path: Path) -> None:
    bl, cl = _write(
        tmp_path,
        """
        # BACKLOG
        #### BL-600 - v2.0.1 / v2.0.2: cycle-12 closures
        **Status**: SHIPPED.
        Body.
        """,
        "# Changelog\n",
    )
    assert _run("2.1.0", bl, cl).returncode == 0
    assert _run("2.0.1", bl, cl).returncode == 0
    assert _run("2.0.2", bl, cl).returncode == 0
