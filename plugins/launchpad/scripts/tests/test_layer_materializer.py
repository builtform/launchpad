"""Tests for lp_scaffold_stack.layer_materializer (Phase 3 S5).

Coverage: orchestrate dispatch via injected run_invoker (no real subprocess);
curate dispatch using a temp scaffolders dir + matching anchor doc; failure
propagation as LayerMaterializationError.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.layer_materializer import (
    LayerMaterializationError,
    materialize_layer,
)


def _fake_run_success(out_files: list[str]):
    """Return a run_invoker that creates the listed files in cwd then returns."""
    def _invoker(argv, cwd):
        for f in out_files:
            target = cwd / f
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")
        return subprocess.CompletedProcess(args=list(argv), returncode=0,
                                           stdout=b"", stderr=b"")
    return _invoker


def _fake_run_failure(argv, cwd):
    raise subprocess.CalledProcessError(returncode=1, cmd=list(argv),
                                        output=b"", stderr=b"sim-fail")


def test_orchestrate_creates_files(tmp_path: Path):
    layer = {"stack": "astro", "role": "frontend", "path": ".", "options": {"template": "blog"}}
    scaffolder = {
        "type": "orchestrate",
        "command": "npm create astro@latest",
        "headless_flags": ["--", "--yes"],
        "options_schema": {"template": "string"},
    }
    invoker = _fake_run_success(["package.json", "src/pages/index.astro"])
    result = materialize_layer(layer, scaffolder, tmp_path, run_invoker=invoker)
    assert result.scaffolder_used == "orchestrate"
    assert result.stack == "astro"
    assert "package.json" in result.files_created
    assert "src/pages/index.astro" in result.files_created


def test_orchestrate_failure_propagates(tmp_path: Path):
    layer = {"stack": "astro", "role": "frontend", "path": ".", "options": {}}
    scaffolder = {
        "type": "orchestrate",
        "command": "npm create astro@latest",
        "headless_flags": [],
        "options_schema": {},
    }
    with pytest.raises(LayerMaterializationError) as exc:
        materialize_layer(layer, scaffolder, tmp_path, run_invoker=_fake_run_failure)
    assert exc.value.reason == "layer_materialization_failed"


def test_curate_loads_anchor_and_drops_placeholder(tmp_path: Path):
    """Synthesize a plugins-root layout with a matching anchor doc."""
    plugins_root = tmp_path / "plugins-root"
    plugins_root.mkdir()
    anchor_dir = plugins_root / "plugins" / "launchpad" / "scaffolders"
    anchor_dir.mkdir(parents=True)
    anchor = anchor_dir / "fastapi-pattern.md"
    body = b"# fastapi pattern\n"
    anchor.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()

    cwd = tmp_path / "project"
    cwd.mkdir()
    layer = {"stack": "fastapi", "role": "backend", "path": ".", "options": {}}
    scaffolder = {
        "type": "curate",
        "knowledge_anchor": "plugins/launchpad/scaffolders/fastapi-pattern.md",
        "knowledge_anchor_sha256": sha,
        "options_schema": {"database": "string"},
    }
    result = materialize_layer(layer, scaffolder, cwd, plugins_root=plugins_root)
    assert result.scaffolder_used == "curate"
    placeholder = cwd / "README.scaffold.md"
    assert placeholder.exists()
    assert placeholder.read_bytes() == body
    assert "README.scaffold.md" in result.files_created


def test_curate_anchor_sha_mismatch_raises(tmp_path: Path):
    plugins_root = tmp_path / "plugins-root"
    plugins_root.mkdir()
    anchor_dir = plugins_root / "plugins" / "launchpad" / "scaffolders"
    anchor_dir.mkdir(parents=True)
    anchor = anchor_dir / "fastapi-pattern.md"
    anchor.write_bytes(b"not the expected content")
    cwd = tmp_path / "project"
    cwd.mkdir()
    layer = {"stack": "fastapi", "role": "backend", "path": ".", "options": {}}
    scaffolder = {
        "type": "curate",
        "knowledge_anchor": "plugins/launchpad/scaffolders/fastapi-pattern.md",
        "knowledge_anchor_sha256": "0" * 64,
        "options_schema": {"database": "string"},
    }
    with pytest.raises(LayerMaterializationError) as exc:
        materialize_layer(layer, scaffolder, cwd, plugins_root=plugins_root)
    assert exc.value.reason == "layer_materialization_failed"


def test_unknown_scaffolder_type_raises(tmp_path: Path):
    layer = {"stack": "astro", "role": "frontend", "path": ".", "options": {}}
    scaffolder = {"type": "magic", "options_schema": {}}
    with pytest.raises(LayerMaterializationError):
        materialize_layer(layer, scaffolder, tmp_path)
