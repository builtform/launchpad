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

# Default: the LaunchPad repo root. This file is at
# plugins/launchpad/scripts/lp_scaffold_stack/layer_materializer.py, so
# parents[0..4] are lp_scaffold_stack / scripts / launchpad / plugins / repo.
# parents[3] would be `plugins/` (knowledge anchors land at
# `plugins/launchpad/scaffolders/*.md` — joining with `plugins/` produces
# `plugins/plugins/launchpad/...`, broken). parents[4] = repo root, which
# is the correct base for plugin-shipped relative anchor paths
# (PR #41 cycle 4 #1 closure).
DEFAULT_PLUGINS_ROOT = Path(__file__).resolve().parents[4]

# Default scaffolder wall-clock budget. Most modern CLIs (create-next-app,
# rails new, etc.) finish in under 2 minutes on a healthy network; the
# 5-minute ceiling catches infinite hangs (notably `mixed-prompts` flavors
# like supabase that can stall on stdin if a flag drifts) without false-
# tripping on slow networks. Per-scaffolder overrides are deferred to v2.1
# (would require a `headless_timeout_seconds` field on scaffolders.yml).
DEFAULT_SCAFFOLDER_TIMEOUT_SEC = 300.0


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
    # Per PR #41 cycle-12 #2 closure (v2.0.1 BL-244 #2): option keys can carry
    # an explicit CLI flag-name override via the scaffolder's `option_flags`
    # mapping. Without the mapping, the flag falls back to `--{key}`. This
    # closes the silent-failure path where snake_case option keys (like
    # `src_dir`) emitted invalid kebab-case-expecting flags (`create-next-app`
    # uses `--src-dir`). The override mapping is per-scaffolder so each CLI's
    # spelling convention can be encoded once in scaffolders.yml.
    option_flags = scaffolder.get("option_flags") or {}
    options = layer.get("options") or {}
    for k, v in options.items():
        flag = str(option_flags.get(k, f"--{k}"))
        if isinstance(v, bool):
            if v:
                argv.append(flag)
        else:
            argv.append(f"{flag}={v}")
    return argv


def _invoke_scaffolder(
    argv: list[str],
    target: Path,
    invoker: RunInvoker,
) -> None:
    """Run the scaffolder argv at `target` via `invoker`. Translates
    subprocess exceptions into LayerMaterializationError with the
    canonical reason."""
    try:
        invoker(argv, target, timeout=DEFAULT_SCAFFOLDER_TIMEOUT_SEC)
    except UnsafeArgvError as exc:
        raise LayerMaterializationError(
            f"argv allowlist rejected scaffolder argv: {exc}",
            reason="layer_materialization_failed",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise LayerMaterializationError(
            f"scaffolder timed out after {DEFAULT_SCAFFOLDER_TIMEOUT_SEC}s "
            f"(likely interactive prompt or infinite hang): argv[0]={argv[0]!r}",
            reason="layer_materialization_failed",
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise LayerMaterializationError(
            f"scaffolder exited non-zero: {exc.returncode}; stderr={exc.stderr!r}",
            reason="layer_materialization_failed",
        ) from exc
    except OSError as exc:
        raise LayerMaterializationError(
            f"scaffolder process error: {exc}",
            reason="layer_materialization_failed",
        ) from exc


def _merge_temp_into_cwd(tmp: Path, cwd: Path) -> None:
    """Two-pass merge of `tmp` contents into `cwd`.

    Pass 1: walk `tmp` and refuse if ANY entry collides with an existing
    path in cwd (including `.launchpad/` files). The refusal happens BEFORE
    any move, so partial-state cwd is impossible from a collision.

    Pass 2: shutil.move every top-level entry from `tmp` into `cwd`.
    `tempfile.TemporaryDirectory(dir=cwd.parent)` is created same-filesystem
    so individual moves are atomic POSIX renames; on a cross-filesystem
    fallback (cwd.parent unwritable) shutil.move degrades to copy+delete,
    which is non-atomic but the temp dir's auto-cleanup still preserves
    the scaffolder output for forensic recovery if a partial move occurs.
    """
    # Pass 1: collision check — recursive walk of tmp.
    collisions: list[str] = []
    for entry in sorted(tmp.rglob("*")):
        rel = entry.relative_to(tmp)
        dest = cwd / rel
        if dest.exists():
            collisions.append(str(rel))
    if collisions:
        raise LayerMaterializationError(
            f"scaffolder output collides with {len(collisions)} pre-existing "
            f"path(s) in cwd: {collisions[:5]}{'...' if len(collisions) > 5 else ''}. "
            f"Most commonly this means the cwd already contains scaffolder "
            f"output (re-run after `/lp-pick-stack` reset) OR .launchpad/ "
            f"files were unexpectedly written by the scaffolder.",
            reason="layer_materialization_failed",
        )

    # Pass 2: move top-level entries.
    import shutil
    for entry in tmp.iterdir():
        shutil.move(str(entry), str(cwd / entry.name))


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

    Per v2.0.1 BL-239 closure (PR #41 cycle-5 #1): when `layer.path == "."`,
    the scaffolder runs in a clean temp dir and its output is then merged
    into cwd. This avoids scaffolder refusal on cwd's pre-existing
    `.launchpad/` contents (e.g., `create-next-app .` refuses on non-empty
    dirs). The collision check before merging guarantees that a scaffolder
    that legitimately ran in an empty temp dir cannot clobber any existing
    cwd file.
    """
    layer_path = str(layer["path"])
    is_dot_path = layer_path.rstrip("/") == "." or layer_path == ""

    invoker = run_invoker if run_invoker is not None else safe_run
    argv = _build_orchestrate_argv(scaffolder, layer)

    if is_dot_path:
        # Temp-dir-merge path: run scaffolder in a clean temp dir, then
        # collision-check + move into cwd. Snapshot cwd BEFORE the run so
        # files_created can be computed via post-merge diff.
        pre_snap = _snapshot_files(cwd)
        # Prefer cwd.parent as the temp parent so move is same-filesystem
        # atomic; fall back to OS default if cwd.parent is unwritable
        # (rare: requires user invoking from a read-only parent).
        import tempfile
        tmp_parent: Path | None = cwd.parent
        try:
            tmp_parent.mkdir(parents=True, exist_ok=True)
            (tmp_parent / ".lp-write-test").touch()
            (tmp_parent / ".lp-write-test").unlink()
        except OSError:
            tmp_parent = None  # fall back to OS default tmp

        with tempfile.TemporaryDirectory(prefix="lp-scaffold-", dir=tmp_parent) as tmp_str:
            tmp = Path(tmp_str)
            _invoke_scaffolder(argv, tmp, invoker)
            _merge_temp_into_cwd(tmp, cwd)

        post = _walk_files_under(cwd, since_set=pre_snap)
        rel_files = sorted(str(p.relative_to(cwd)) for p in post)
        return MaterializationResult(
            stack=str(layer["stack"]),
            path=layer_path,
            scaffolder_used="orchestrate",
            files_created=rel_files,
        )

    # Non-"." path: run scaffolder directly in the layer target (existing
    # behavior — no merge dance needed because the layer target is empty).
    layer_target = _resolve_layer_target(layer_path, cwd)
    pre_snap = _snapshot_files(layer_target)
    _invoke_scaffolder(argv, layer_target, invoker)
    post = _walk_files_under(layer_target, since_set=pre_snap)
    rel_files = sorted(str(p.relative_to(cwd)) for p in post)
    return MaterializationResult(
        stack=str(layer["stack"]),
        path=layer_path,
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
    # PR #41 cycle 8 #4 closure (Codex P2): atomic create-only write
    # matching the rest of the pipeline (decision_writer, receipt_writer,
    # cross_cutting_wirer). Previously `write_bytes()` would silently
    # overwrite an existing file — clobbering a user-edited recovery
    # artifact or a small pre-existing placeholder in an otherwise
    # greenfield directory. O_NOFOLLOW also refuses symlink writes.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        fd = os.open(str(placeholder), flags, 0o600)
    except FileExistsError as exc:
        raise LayerMaterializationError(
            f"curate-mode placeholder already exists: {placeholder.relative_to(cwd)}; "
            f"resolve the collision and re-run /lp-scaffold-stack",
            reason="layer_materialization_failed",
        ) from exc
    try:
        os.write(fd, buf)
        os.fsync(fd)
    finally:
        os.close(fd)

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
