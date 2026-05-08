"""Verify plugin-workflow-sha-pin-check.py catches all non-SHA refs.

Phase 5 (cycle 5 F6 P2): the checker must reject `@v1`, `@main`,
`@master`, `@release`, semver tags, and any non-40-char-hex ref.
Valid 40-char SHA pins must pass.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_checker():
    """Import the SHA-pin checker module."""
    spec = importlib.util.spec_from_file_location(
        "plugin_workflow_sha_pin_check",
        _SCRIPTS_DIR / "plugin-workflow-sha-pin-check.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = _load_checker()


class TestExtractRef:
    def test_standard_action(self) -> None:
        assert checker._extract_ref("actions/checkout@abc123") == "abc123"

    def test_local_action_returns_none(self) -> None:
        assert checker._extract_ref("./my-action") is None

    def test_docker_action_returns_none(self) -> None:
        assert checker._extract_ref("docker://alpine:3.18") is None

    def test_no_at_sign_returns_none(self) -> None:
        assert checker._extract_ref("actions/checkout") is None


class TestScanFile:
    def _write_workflow(self, tmp_path: Path, content: str) -> Path:
        wf = tmp_path / "test.yml"
        wf.write_text(content)
        return wf

    def test_valid_sha_pin_passes(self, tmp_path: Path) -> None:
        wf = self._write_workflow(tmp_path, (
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      - uses: actions/checkout@"
            "a5ac7e51b41094c92402da3b24376905380afc29 # v4\n"
        ))
        assert checker.scan_file(wf) == []

    def test_tag_v1_rejected(self, tmp_path: Path) -> None:
        wf = self._write_workflow(tmp_path, (
            "    - uses: actions/checkout@v1\n"
        ))
        violations = checker.scan_file(wf)
        assert len(violations) == 1
        assert violations[0][2] == "v1"

    def test_tag_v2_semver_rejected(self, tmp_path: Path) -> None:
        wf = self._write_workflow(tmp_path, (
            "    - uses: actions/setup-node@v2.0.2\n"
        ))
        violations = checker.scan_file(wf)
        assert len(violations) == 1

    def test_branch_main_rejected(self, tmp_path: Path) -> None:
        wf = self._write_workflow(tmp_path, (
            "    - uses: owner/repo@main\n"
        ))
        violations = checker.scan_file(wf)
        assert len(violations) == 1
        assert violations[0][2] == "main"

    def test_branch_master_rejected(self, tmp_path: Path) -> None:
        wf = self._write_workflow(tmp_path, (
            "    - uses: owner/repo@master\n"
        ))
        violations = checker.scan_file(wf)
        assert len(violations) == 1

    def test_branch_release_rejected(self, tmp_path: Path) -> None:
        wf = self._write_workflow(tmp_path, (
            "    - uses: owner/repo@release\n"
        ))
        violations = checker.scan_file(wf)
        assert len(violations) == 1

    def test_short_sha_rejected(self, tmp_path: Path) -> None:
        wf = self._write_workflow(tmp_path, (
            "    - uses: owner/repo@abc123\n"
        ))
        violations = checker.scan_file(wf)
        assert len(violations) == 1
