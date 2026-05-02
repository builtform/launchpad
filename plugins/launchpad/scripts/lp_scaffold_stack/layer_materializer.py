"""Layer materialization (Phase 3 §4.1 Step 3).

Per scaffolders.yml entries:

- `type: orchestrate` layers run the scaffolder's `command` + `headless_flags`
  via `safe_run.safe_run()` from the layer's resolved `path`.
- `type: curate` layers (eleventy, fastapi) load the knowledge-anchor pattern
  doc via `knowledge_anchor_loader.read_and_verify` (sha256 pinned) and
  perform the in-process file scaffolding.

Both branches return a `MaterializationResult` carrying `files_created`
(relative paths from cwd). On failure: raises `LayerMaterializationError`
with `reason` field — the engine catches this and emits the partial-cleanup
record via `cleanup_recorder.write_scaffold_failed`.

Orchestrate-mode injection harness (test hook): callers may pass
`run_invoker=...` to override `safe_run.safe_run` (used by gate #11 to inject
a known failure on a specific layer index).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

# Sibling-script imports.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from knowledge_anchor_loader import read_and_verify  # noqa: E402
from safe_run import UnsafeArgvError, safe_run  # noqa: E402

# Default: the LaunchPad repo root (3 levels up from this file:
# scripts/lp_scaffold_stack/ → scripts/ → launchpad/ → plugins/ → repo).
DEFAULT_PLUGINS_ROOT = Path(__file__).resolve().parents[3]


class LayerMaterializationError(RuntimeError):
    """Raised when a single layer fails to materialize. Carries `reason`."""

    def __init__(self, message: str, reason: str, *, files_created: Sequence[str] = ()):
        super().__init__(message)
        self.reason = reason
        self.files_created = list(files_created)


@dataclass
class MaterializationResult:
    """Per-layer materialization outcome."""

    stack: str
    path: str
    scaffolder_used: str  # "orchestrate" | "curate"
    files_created: list[str] = field(default_factory=list)


# Type alias for the safe_run injection harness.
RunInvoker = Callable[[Sequence[str], Path], subprocess.CompletedProcess[bytes]]


def _walk_files_under(root: Path, *, since_set: set[Path]) -> list[Path]:
    """Return Path entries under `root` that are NOT in `since_set` (the
    pre-materialization snapshot of existing files)."""
    out: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            p = Path(dirpath) / name
            if p not in since_set:
                out.append(p)
    return out


def _snapshot_files(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    snap: set[Path] = set()
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            snap.add(Path(dirpath) / name)
    return snap


def _resolve_layer_target(layer_path: str, cwd: Path) -> Path:
    """Resolve a layer's relative `path` to an absolute Path under cwd, creating
    parent directories as needed. Per HANDSHAKE §6 the path was already
    validated; this is the materialization-time mkdir + return."""
    if layer_path == ".":
        target = cwd
    else:
        target = cwd / layer_path
    target.mkdir(parents=True, exist_ok=True)
    return target


def _build_orchestrate_argv(
    scaffolder: Mapping[str, Any],
    layer: Mapping[str, Any],
) -> list[str]:
    """Build argv from scaffolder's `command` + `destination_argv` +
    `headless_flags` + per-layer `options`.

    The command may be a multi-token string (e.g., `npm create astro@latest`);
    we split on whitespace. `destination_argv` (per-stack tokens like `["."]`)
    is appended next so positional destination args land in the right slot for
    CLIs that require them (create-next-app, rails new, hugo new site, etc.).
    Headless flags appended verbatim. Options keys that look like CLI flags
    (`--key=value`) appended after.

    Every argv element is validated against `safe_run`'s allowlist via
    `safe_run`'s internal `_validate_argv` — which we re-trigger by passing
    the argv directly. This is the only orchestration path that constructs
    argv from scaffolders.yml; the regex enforced here matches the safe_run
    allowlist, so a malicious scaffolders.yml entry would be rejected at the
    safe_run boundary.
    """
    cmd = str(scaffolder.get("command", "")).strip()
    if not cmd:
        raise LayerMaterializationError(
            f"orchestrate scaffolder for stack={layer.get('stack')!r} has empty command",
            reason="scaffolder_command_missing",
        )
    argv = cmd.split()
    destination_argv = scaffolder.get("destination_argv") or []
    for token in destination_argv:
        argv.append(str(token))
    flags = scaffolder.get("headless_flags") or []
    for flag in flags:
        argv.append(str(flag))
    options = layer.get("options") or {}
    for k, v in options.items():
        if isinstance(v, bool):
            if v:
                argv.append(f"--{k}")
        else:
            argv.append(f"--{k}={v}")
    return argv


def _materialize_orchestrate(
    layer: Mapping[str, Any],
    scaffolder: Mapping[str, Any],
    cwd: Path,
    *,
    run_invoker: RunInvoker | None = None,
) -> MaterializationResult:
    """Run the scaffolder's headless command via `safe_run` from layer.path.

    Captures `files_created` as the diff between pre-snapshot and post-state
    of the layer-target directory.
    """
    layer_target = _resolve_layer_target(str(layer["path"]), cwd)
    pre_snap = _snapshot_files(layer_target)

    argv = _build_orchestrate_argv(scaffolder, layer)
    invoker = run_invoker if run_invoker is not None else safe_run
    try:
        invoker(argv, layer_target)
    except UnsafeArgvError as exc:
        raise LayerMaterializationError(
            f"argv allowlist rejected scaffolder argv: {exc}",
            reason="layer_materialization_failed",
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise LayerMaterializationError(
            f"scaffolder exited non-zero: {exc.returncode}; stderr={exc.stderr!r}",
            reason="layer_materialization_failed",
        ) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LayerMaterializationError(
            f"scaffolder process error: {exc}",
            reason="layer_materialization_failed",
        ) from exc

    post = _walk_files_under(layer_target, since_set=pre_snap)
    rel_files = sorted(str(p.relative_to(cwd)) for p in post)
    return MaterializationResult(
        stack=str(layer["stack"]),
        path=str(layer["path"]),
        scaffolder_used="orchestrate",
        files_created=rel_files,
    )


def _materialize_curate(
    layer: Mapping[str, Any],
    scaffolder: Mapping[str, Any],
    cwd: Path,
    *,
    plugins_root: Path,
) -> MaterializationResult:
    """Curate-mode: load the knowledge-anchor doc (sha256-pinned) and create
    a minimal placeholder file at the layer target.

    At v2.0 Phase 3 the curate-mode template materialization is intentionally
    minimal: a `README.scaffold.md` placeholder file is dropped in the layer
    target with the loaded knowledge-anchor content (verified bytes). The
    full curate-mode templating (eleventy / fastapi project trees) is
    orchestrated by the user reading the placeholder + Claude in the
    `/lp-define` Phase 0.5 adapters; this Phase 3 step is the chain-of-custody
    handoff (verified bytes from the plugin tree → user's project tree).
    """
    layer_target = _resolve_layer_target(str(layer["path"]), cwd)
    pre_snap = _snapshot_files(layer_target)

    anchor_rel = scaffolder.get("knowledge_anchor")
    expected_sha = scaffolder.get("knowledge_anchor_sha256")
    if not isinstance(anchor_rel, str) or not isinstance(expected_sha, str):
        raise LayerMaterializationError(
            f"curate scaffolder for stack={layer.get('stack')!r} missing "
            "knowledge_anchor / knowledge_anchor_sha256",
            reason="layer_materialization_failed",
        )
    anchor_path = plugins_root / anchor_rel
    try:
        buf = read_and_verify(anchor_path, expected_sha, plugins_root)
    except (ValueError, OSError) as exc:
        raise LayerMaterializationError(
            f"knowledge-anchor read/verify failed for {anchor_rel}: {exc}",
            reason="layer_materialization_failed",
        ) from exc

    placeholder = layer_target / "README.scaffold.md"
    placeholder.write_bytes(buf)

    post = _walk_files_under(layer_target, since_set=pre_snap)
    rel_files = sorted(str(p.relative_to(cwd)) for p in post)
    return MaterializationResult(
        stack=str(layer["stack"]),
        path=str(layer["path"]),
        scaffolder_used="curate",
        files_created=rel_files,
    )


def materialize_layer(
    layer: Mapping[str, Any],
    scaffolder: Mapping[str, Any],
    cwd: Path,
    *,
    plugins_root: Path | None = None,
    run_invoker: RunInvoker | None = None,
) -> MaterializationResult:
    """Dispatch on `scaffolder.type` ('orchestrate' | 'curate').

    `plugins_root` defaults to the LaunchPad repo root (the parent of
    `plugins/launchpad/`).

    Raises LayerMaterializationError on any failure (callers catch and emit
    `scaffold-failed-<ts>.json` via cleanup_recorder).
    """
    plugins_root = plugins_root if plugins_root is not None else DEFAULT_PLUGINS_ROOT
    sc_type = scaffolder.get("type")
    if sc_type == "orchestrate":
        return _materialize_orchestrate(layer, scaffolder, cwd, run_invoker=run_invoker)
    if sc_type == "curate":
        return _materialize_curate(layer, scaffolder, cwd, plugins_root=plugins_root)
    raise LayerMaterializationError(
        f"unknown scaffolder type {sc_type!r} for stack={layer.get('stack')!r}",
        reason="layer_materialization_failed",
    )


__all__ = [
    "DEFAULT_PLUGINS_ROOT",
    "LayerMaterializationError",
    "MaterializationResult",
    "RunInvoker",
    "materialize_layer",
]
