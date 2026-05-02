"""Tests for lp_scaffold_stack.cross_cutting_wirer (Phase 3 S6)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.cross_cutting_wirer import (
    CrossCuttingError,
    LEFTHOOK_HOOKS,
    wire_cross_cutting,
)


def test_single_layer_emits_only_lefthook(tmp_path: Path):
    layers = [{"stack": "astro", "role": "frontend", "path": "."}]
    result = wire_cross_cutting(tmp_path, layers, materialized_files=[])
    assert "lefthook.yml" in result.cross_cutting_files
    assert "pnpm-workspace.yaml" not in result.cross_cutting_files
    assert "turbo.json" not in result.cross_cutting_files
    assert result.toolchains_detected == ["node"]


def test_monorepo_layout_emits_workspace_files(tmp_path: Path):
    layers = [
        {"stack": "next", "role": "frontend", "path": "apps/web"},
        {"stack": "fastapi", "role": "backend", "path": "services/api"},
    ]
    result = wire_cross_cutting(tmp_path, layers, materialized_files=[])
    assert "lefthook.yml" in result.cross_cutting_files
    assert "pnpm-workspace.yaml" in result.cross_cutting_files
    assert "turbo.json" in result.cross_cutting_files
    assert "node" in result.toolchains_detected
    assert "python" in result.toolchains_detected


def test_collision_raises(tmp_path: Path):
    """If a cross-cutting target file already exists, the wirer raises."""
    (tmp_path / "lefthook.yml").write_text("pre-existing", encoding="utf-8")
    layers = [{"stack": "astro", "role": "frontend", "path": "."}]
    with pytest.raises(CrossCuttingError) as exc:
        wire_cross_cutting(tmp_path, layers, materialized_files=[])
    assert exc.value.reason == "cross_cutting_wiring_collision"


def test_secret_scan_clean(tmp_path: Path):
    layers = [{"stack": "astro", "role": "frontend", "path": "."}]
    safe_file = tmp_path / "package.json"
    safe_file.write_text('{"name": "demo"}\n', encoding="utf-8")
    result = wire_cross_cutting(tmp_path, layers, materialized_files=["package.json"])
    assert result.secret_scan_passed is True
    assert result.secret_scan_findings == []


def test_secret_scan_finds_aws_key(tmp_path: Path):
    layers = [{"stack": "astro", "role": "frontend", "path": "."}]
    leak = tmp_path / ".env.example"
    leak.write_text("AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    result = wire_cross_cutting(tmp_path, layers, materialized_files=[".env.example"])
    assert result.secret_scan_passed is False
    assert any(".env.example" in f for f in result.secret_scan_findings)


def test_lefthook_includes_all_4_hooks_for_node(tmp_path: Path):
    layers = [{"stack": "astro", "role": "frontend", "path": "."}]
    wire_cross_cutting(tmp_path, layers, materialized_files=[])
    body = (tmp_path / "lefthook.yml").read_text(encoding="utf-8")
    for hook in LEFTHOOK_HOOKS:
        assert hook in body


def test_lefthook_python_branch(tmp_path: Path):
    layers = [{"stack": "fastapi", "role": "backend", "path": "."}]
    wire_cross_cutting(tmp_path, layers, materialized_files=[])
    body = (tmp_path / "lefthook.yml").read_text(encoding="utf-8")
    assert "mypy" in body or "ruff" in body
