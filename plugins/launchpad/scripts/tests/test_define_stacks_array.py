"""Phase 6 v2.1 Slice D -- /lp-define top-level `stacks:` array via
`lp_bootstrap.policy.write_config_yaml_atomic` + `--redetect-stack` flag
semantics.

Tests cover:
  1. /lp-define renders top-level `stacks: [...]` array (NOT under pipeline).
  2. v2.0 lift via `auto_promote_stack_to_stacks` reuse + caller-side
     warnings discard (read_stacks helper).
  3. `--redetect-stack` bare flag aborts non-zero on id-mismatch (exit 65).
  4. `--redetect-stack --force` overwrites without prompt.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
RUNNER = str(PLUGIN_SCRIPTS / "lp_define_runner.py")
LOADER_PATH = PLUGIN_SCRIPTS / "plugin-config-loader.py"

# Load config loader for read_stacks programmatic access.
_spec = importlib.util.spec_from_file_location(
    "plugin_config_loader_phase6", LOADER_PATH
)
_loader_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_loader_mod)  # type: ignore[union-attr]
read_stacks = _loader_mod.read_stacks
auto_promote_stack_to_stacks = _loader_mod.auto_promote_stack_to_stacks


@pytest.fixture
def repo() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase6-define-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, RUNNER, f"--repo-root={repo}",
         "--no-trust-banner", *args],
        capture_output=True,
        text=True,
    )


def test_lp_define_writes_top_level_stacks_array(repo: Path):
    """Slice D §3.6: config.yml carries `stacks: [...]` at TOP LEVEL
    (not under pipeline) so v2.1 callers can read it without dotted paths."""
    (repo / "package.json").write_text(json.dumps({
        "name": "ts-mono",
        "workspaces": ["apps/*"],
        "dependencies": {"next": "15.0.0", "hono": "4.0.0"},
        "devDependencies": {"typescript": "5.0.0"},
    }), encoding="utf-8")
    proc = _run(repo, "--force")
    assert proc.returncode == 0, proc.stderr

    config_path = repo / ".launchpad" / "config.yml"
    assert config_path.is_file()
    text = config_path.read_text(encoding="utf-8")
    # `stacks:` line must be at top-level (not indented under pipeline).
    stacks_line = next(
        (ln for ln in text.splitlines() if ln.startswith("stacks:")),
        None,
    )
    assert stacks_line is not None, f"no top-level stacks: line in {text}"
    assert "[ts_monorepo]" in stacks_line or "ts_monorepo" in stacks_line


def test_read_stacks_layers_over_auto_promote_and_discards_warnings(repo: Path):
    """Slice D §3.6: `read_stacks` calls `auto_promote_stack_to_stacks`
    and discards the returned warnings list (NO helper modification)."""
    (repo / ".launchpad").mkdir()
    (repo / ".launchpad" / "config.yml").write_text(
        # legacy v2.0 shape: scalar `stack:`, no `stacks:` array
        "stack: ts_monorepo\npipeline:\n  brainstorm: enabled\n",
        encoding="utf-8",
    )
    out = read_stacks(repo)
    assert out == ["ts_monorepo"]
    # Direct check that auto_promote signature is byte-equivalent (no
    # suppress_warn kwarg added).
    import inspect
    sig = inspect.signature(auto_promote_stack_to_stacks)
    assert list(sig.parameters.keys()) == ["config"]


def test_redetect_stack_bare_aborts_with_exit_65_on_mismatch(repo: Path):
    """DA6 + cycle-4 spec-flow P2-A: bare `--redetect-stack` on id-mismatch
    exits 65 (EX_DATAERR) with stderr message — does NOT overwrite."""
    # Seed a fixture with persisted stack=astro but a Gemfile that detects
    # to stack=rails. Mismatch must trigger the exit-65 abort.
    (repo / ".launchpad").mkdir()
    (repo / ".launchpad" / "config.yml").write_text(
        "stacks: [astro]\npipeline:\n  brainstorm: enabled\n",
        encoding="utf-8",
    )
    (repo / "Gemfile").write_text(
        'source "https://rubygems.org"\ngem "rails", "~> 7.1"\n',
        encoding="utf-8",
    )
    proc = _run(repo, "--redetect-stack")
    assert proc.returncode == 65, (
        f"expected exit 65 on id-mismatch; got {proc.returncode}. "
        f"stderr={proc.stderr[:300]}"
    )
    assert "differs from persisted" in proc.stderr
    assert "--force" in proc.stderr
    # Persisted stacks unchanged on the abort path.
    persisted = read_stacks(repo)
    assert persisted == ["astro"]


def test_redetect_stack_force_overwrites_atomically(repo: Path):
    """DA6: `--redetect-stack --force` rewrites the `stacks:` line via
    `lp_bootstrap.policy.write_config_yaml_atomic` and exits 0."""
    (repo / ".launchpad").mkdir()
    (repo / ".launchpad" / "config.yml").write_text(
        "stacks: [astro]\npipeline:\n  brainstorm: enabled\n",
        encoding="utf-8",
    )
    (repo / "Gemfile").write_text(
        'source "https://rubygems.org"\ngem "rails"\n',
        encoding="utf-8",
    )
    proc = _run(repo, "--redetect-stack", "--force")
    assert proc.returncode == 0, proc.stderr
    persisted = read_stacks(repo)
    assert persisted == ["rails"]
    # Pipeline section preserved (not clobbered by overwrite).
    text = (repo / ".launchpad" / "config.yml").read_text(encoding="utf-8")
    assert "pipeline:" in text
    assert "brainstorm: enabled" in text
