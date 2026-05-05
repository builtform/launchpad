"""Tests for v2.0.1 BL-239 (PR #41 cycle-5 #1 closure):
orchestrate-mode scaffolders with `layer.path == "."` now run in a clean
temp dir and merge their output into cwd, instead of running directly in
cwd (where `.launchpad/scaffold-decision.json` + `rationale.md` would
cause refusal from CLIs like `create-next-app .` that demand empty dirs).

The temp-dir-merge approach:
  1. Run scaffolder in `tempfile.TemporaryDirectory(dir=cwd.parent)`
  2. Walk temp tree → collision-check against cwd (refuse if ANY collision)
  3. shutil.move each top-level entry from temp → cwd

The collision check is the safety net: even if a buggy scaffolder writes
to `.launchpad/`, the merge refuses before clobbering anything.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.layer_materializer import (
    LayerMaterializationError,
    _materialize_orchestrate,
)


def _fake_invoker_writes(files: dict[str, str]):
    """Build a RunInvoker that, when called, writes `files` into the cwd
    arg (the scaffolder's working directory).

    `files` keys are paths relative to cwd; values are file contents.
    Directories are auto-created. Returns a callable matching the
    RunInvoker signature: (argv, cwd_path, *, timeout) → CompletedProcess.
    """
    import subprocess

    def invoke(argv, cwd_path, *, timeout=None):
        target = Path(cwd_path)
        for rel, content in files.items():
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
        # Return a successful completed-process object (real safe_run does this).
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout=b"", stderr=b"")

    return invoke


def _fake_invoker_failure():
    """Build a RunInvoker that raises CalledProcessError (non-zero exit)."""
    import subprocess

    def invoke(argv, cwd_path, *, timeout=None):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=argv, stderr=b"scaffolder failed"
        )
    return invoke


# --- happy path: path: "." with .launchpad/ pre-existing ---

def test_dot_path_scaffold_with_launchpad_present(tmp_path: Path):
    """The canonical scenario: `.launchpad/scaffold-decision.json` and
    `rationale.md` exist at cwd; scaffolder runs cleanly via temp-dir-merge
    and produces a `package.json` etc."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    # Pre-existing .launchpad/ that would refuse a `create-next-app .` invocation.
    (cwd / ".launchpad").mkdir()
    (cwd / ".launchpad" / "scaffold-decision.json").write_text("{}", encoding="utf-8")
    (cwd / "rationale.md").write_text("# rationale\n", encoding="utf-8")

    layer = {"stack": "next", "path": ".", "options": {}}
    scaffolder = {
        "command": "echo",  # any allowlisted command — we override the invoker
        "destination_argv": ["."],
        "headless_flags": [],
    }
    invoker = _fake_invoker_writes({
        "package.json": "{}\n",
        "src/app/page.tsx": "export default function Page() {}\n",
    })
    result = _materialize_orchestrate(layer, scaffolder, cwd, run_invoker=invoker)

    assert result.scaffolder_used == "orchestrate"
    assert (cwd / "package.json").exists()
    assert (cwd / "src" / "app" / "page.tsx").exists()
    # .launchpad/ untouched
    assert (cwd / ".launchpad" / "scaffold-decision.json").read_text() == "{}"
    assert (cwd / "rationale.md").read_text() == "# rationale\n"
    # files_created lists the new files (relative to cwd)
    assert "package.json" in result.files_created


def test_dot_path_collision_with_existing_file_refused(tmp_path: Path):
    """If the scaffolder would write a file that already exists in cwd,
    refuse with layer_materialization_failed BEFORE moving anything."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    # Pre-existing file that scaffolder will try to write
    (cwd / "package.json").write_text('{"existing": true}\n', encoding="utf-8")

    layer = {"stack": "next", "path": ".", "options": {}}
    scaffolder = {"command": "echo", "destination_argv": ["."], "headless_flags": []}
    invoker = _fake_invoker_writes({
        "package.json": '{"new": true}\n',
        "src/index.ts": "",
    })

    with pytest.raises(LayerMaterializationError) as ex:
        _materialize_orchestrate(layer, scaffolder, cwd, run_invoker=invoker)
    assert ex.value.reason == "layer_materialization_failed"
    assert "collide" in str(ex.value).lower()

    # Pre-existing file untouched (no partial merge)
    assert (cwd / "package.json").read_text() == '{"existing": true}\n'
    # New scaffolder file NOT moved
    assert not (cwd / "src" / "index.ts").exists()


def test_dot_path_collision_with_launchpad_dir_refused(tmp_path: Path):
    """If the scaffolder writes to `.launchpad/` (e.g., a buggy/malicious
    scaffolder), the collision check refuses — `.launchpad/` files are
    LaunchPad's chain-of-custody artifacts and must never be clobbered."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / ".launchpad").mkdir()
    (cwd / ".launchpad" / "scaffold-decision.json").write_text("{}", encoding="utf-8")

    layer = {"stack": "next", "path": ".", "options": {}}
    scaffolder = {"command": "echo", "destination_argv": ["."], "headless_flags": []}
    invoker = _fake_invoker_writes({
        ".launchpad/scaffold-decision.json": '{"hostile": true}\n',
        "package.json": "{}\n",
    })

    with pytest.raises(LayerMaterializationError) as ex:
        _materialize_orchestrate(layer, scaffolder, cwd, run_invoker=invoker)
    assert ex.value.reason == "layer_materialization_failed"
    # Original .launchpad file untouched
    assert (cwd / ".launchpad" / "scaffold-decision.json").read_text() == "{}"
    # No partial merge (package.json not moved either)
    assert not (cwd / "package.json").exists()


def test_dot_path_scaffolder_failure_cleanup(tmp_path: Path):
    """If the scaffolder itself fails (non-zero exit), the temp dir is
    cleaned up and cwd is untouched."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / ".launchpad").mkdir()
    (cwd / ".launchpad" / "scaffold-decision.json").write_text("{}", encoding="utf-8")

    layer = {"stack": "next", "path": ".", "options": {}}
    scaffolder = {"command": "echo", "destination_argv": ["."], "headless_flags": []}
    invoker = _fake_invoker_failure()

    with pytest.raises(LayerMaterializationError) as ex:
        _materialize_orchestrate(layer, scaffolder, cwd, run_invoker=invoker)
    assert ex.value.reason == "layer_materialization_failed"

    # cwd untouched after scaffolder failure
    assert list(cwd.iterdir()) == [cwd / ".launchpad"]
    assert (cwd / ".launchpad" / "scaffold-decision.json").read_text() == "{}"

    # No `lp-scaffold-*` temp dirs left in cwd.parent
    leftover_temps = [
        p for p in cwd.parent.iterdir()
        if p.name.startswith("lp-scaffold-")
    ]
    assert leftover_temps == [], (
        f"temp-dir cleanup failed; leftover: {leftover_temps}"
    )


# --- non-"." paths still use direct-run (regression guard) ---

def test_non_dot_path_runs_directly_no_temp_merge(tmp_path: Path):
    """Layer with `path: "apps/web"` runs scaffolder directly in `apps/web`
    (existing behavior); no temp-dir-merge."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / "apps" / "web").mkdir(parents=True)

    layer = {"stack": "next", "path": "apps/web", "options": {}}
    scaffolder = {"command": "echo", "destination_argv": ["."], "headless_flags": []}
    invoker = _fake_invoker_writes({
        "package.json": "{}\n",
    })
    result = _materialize_orchestrate(layer, scaffolder, cwd, run_invoker=invoker)

    assert result.path == "apps/web"
    assert (cwd / "apps" / "web" / "package.json").exists()
    # The fake invoker wrote into apps/web (the layer target), not cwd
    assert not (cwd / "package.json").exists()


# --- regression: empty path treated as "." ---

def test_empty_path_treated_as_dot(tmp_path: Path):
    """`layer.path == ""` is normalized to "." semantics — also goes through
    temp-dir-merge."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    (cwd / ".launchpad").mkdir()

    layer = {"stack": "next", "path": "", "options": {}}
    scaffolder = {"command": "echo", "destination_argv": ["."], "headless_flags": []}
    invoker = _fake_invoker_writes({"package.json": "{}\n"})

    result = _materialize_orchestrate(layer, scaffolder, cwd, run_invoker=invoker)
    assert (cwd / "package.json").exists()
    assert result.scaffolder_used == "orchestrate"
