"""Composition wrapper: 2-adapter sequential render with rollback.

Phase 4 plan section 3.4 (pair table from data) + section 3.5 (per-adapter
unwrap_strategy dispatch) + section 3.6 (sequential render + rollback +
same-FS enforcement) + section 3.12 (verbatim user-facing messages).

Pair table semantics:
  - 5 active stack ids -> C(5,2) = 10 distinct unordered pairs.
  - 4 of those 10 collapse via the `ts_monorepo + *` catch-all rejection
    (ts_monorepo has empty composes_with so the pair-table is data-driven
    from each adapter's `composes_with` declaration).
  - 6 substantive cross-pairs remain (every non-ts_monorepo pair).
  - 2 duplicate-rejection rules sit OUTSIDE C(5,2): astro + astro and
    generic + generic.

Workspace allocation:
  - nextjs_standalone -> app
  - nextjs_fastapi    -> app (+ api as additional workspace)
  - astro             -> content
  - generic           -> extra
  - The only collision in v2.1 is nextjs_standalone + nextjs_fastapi
    (both claim "app"); collision suffix renames the FIRST to "app-fe"
    with the section 3.12 verbatim INFO log.

Sequential render (Codex PR #50 P1-B harden):
  1. Same-FS pre-flight: TMPDIR must be on the same filesystem as
     composition_root. os.replace requires same-FS atomicity.
  2. Per-adapter scaffold_into(tempdir) into composition_root/.lp-tmp/<id>.
  3. Per-adapter apply_overlay(tempdir).
  4. After all adapters complete, per-workspace `os.replace` lifts
     `tempdir/<source_relpath>` to `composition_root/apps/<workspace_name>/`
     using `Adapter.workspace_source_map_composition`. Empty map preserves
     legacy whole-tempdir → apps/<primary> behavior. `package_workspace_paths`
     entries lift to `composition_root/<path>` siblings.
  5. On any per-adapter failure: rollback rmtrees both rendered tempdirs
     AND already-placed `apps/<workspace>/` + `composition_root/<package>/`
     paths in reverse order. Errors during cleanup are logged with the
     secrets-warning recommendation per harden P0.
"""
from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import shutil
import stat
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from .contracts import (
    Adapter,
    AdapterScaffoldError,
    StackIdActive,
    _validate_package_workspace_paths,
    _validate_workspace_source_map,
)

LOG = logging.getLogger("plugin_stack_adapters.composition")

N2_CAP = 2
TS_MONOREPO_STACK_ID: StackIdActive = "ts_monorepo"

# Per Codex PR #50 P1-B harden P1-ζ: tempdir parent renamed from `.tmp/`
# (collides with Next.js build dirs) to `.lp-tmp/`. Both single-adapter
# wrapping and composition mode use this directory.
TMP_PARENT_DIRNAME = ".lp-tmp"


class CompositionRejectionCode(StrEnum):
    N2_CAP_EXCEEDED = "n2_cap_exceeded"
    TS_MONOREPO_PAIR = "ts_monorepo_pair"
    DUPLICATE_STACKS = "duplicate_stacks"
    UNSUPPORTED_PAIR = "unsupported_pair"
    # Per Codex PR #50 P1-B harden P2-δ + P2-θ.
    WORKSPACE_SOURCE_MAP_MISMATCH = "workspace_source_map_mismatch"
    PACKAGE_WORKSPACE_PATH_COLLISION = "package_workspace_path_collision"
    # Per Codex PR #50 P1-B harden P1-α + P1-β + P3-ν.
    PATH_TRAVERSAL_IN_WORKSPACE_MAP = "path_traversal_in_workspace_map"
    SYMLINK_IN_SCAFFOLD_TREE = "symlink_in_scaffold_tree"
    RESIDUAL_TAMPERED_TEMPDIR = "residual_tampered_tempdir"
    # v2.1 Codex PR #50 post-review P0: stale .pre-composition-<sha8> backup
    # from a prior crashed run is present at the target's sibling slot.
    # Refuse with clear remediation (run /lp-bootstrap --recover).
    STALE_PRE_COMPOSITION_BACKUP = "stale_pre_composition_backup"


# Phase 4 section 3.12 verbatim catalog.
_REJECT_N2 = (
    "LaunchPad v2.1 supports up to 2 stacks per project. To request "
    "3-stack composition, open an issue with label v2.2-composition."
)
_REJECT_TS_MONOREPO = (
    "ts_monorepo is itself a monorepo; it cannot be combined with another "
    "stack. Pick one of: ts_monorepo (alone) OR nextjs_standalone/"
    "nextjs_fastapi/astro/generic with a second stack."
)
_REJECT_DUPLICATE = (
    "Duplicate stacks are not allowed. Pick two different stacks."
)
_COLLISION_INFO = (
    "Renamed first 'app' workspace to 'app-fe' due to composition "
    "collision; second adapter retains 'app'."
)


class CompositionAbortError(RuntimeError):
    """Phase 3 inheritance section 3.11.5(b): structured triple."""

    def __init__(self, *, reason: str, path: Path | None, remediation: str) -> None:
        super().__init__(remediation)
        self.reason = reason
        self.path = path
        self.remediation = remediation


@dataclass(frozen=True)
class CompositionRejection:
    code: CompositionRejectionCode
    message: str


@dataclass(frozen=True)
class _PlacementEntry:
    """Per-workspace placement directive built from adapter declarations.

    `declared_key` is the key in `adapter.workspace_source_map_composition`
    (or `""` for legacy whole-tempdir adapters); `dest_workspace_name` is
    the post-rename name under `apps/`. Per harden P3-β, the rename only
    affects the destination; source-side relpath stays adapter-declared.
    """

    adapter: Adapter
    declared_key: str
    dest_workspace_name: str
    source_relpath: str  # "" for legacy whole-tempdir adapters


@dataclass
class CompositionResult:
    composition_root: Path
    workspaces: dict[str, Adapter]
    placed_paths: list[Path] = field(default_factory=list)
    info_log_messages: list[str] = field(default_factory=list)


def _stack_ids(adapters: Iterable[Adapter]) -> tuple[StackIdActive, ...]:
    return tuple(a.stack_id for a in adapters)


def validate_pair(
    adapters: list[Adapter],
) -> CompositionRejection | None:
    """Validate a 1- or 2-adapter selection. Returns None when valid.

    Single-adapter compositions are allowed (`/lp-scaffold-stack` calls
    `compose([adapter], root)` for the no-composition path).
    """
    if len(adapters) > N2_CAP:
        return CompositionRejection(
            code=CompositionRejectionCode.N2_CAP_EXCEEDED,
            message=_REJECT_N2,
        )
    if len(adapters) == 0:
        return CompositionRejection(
            code=CompositionRejectionCode.UNSUPPORTED_PAIR,
            message="At least one stack is required.",
        )
    ids = _stack_ids(adapters)
    if TS_MONOREPO_STACK_ID in ids and len(ids) == 2:
        return CompositionRejection(
            code=CompositionRejectionCode.TS_MONOREPO_PAIR,
            message=_REJECT_TS_MONOREPO,
        )
    if len(ids) == 2 and ids[0] == ids[1]:
        return CompositionRejection(
            code=CompositionRejectionCode.DUPLICATE_STACKS,
            message=_REJECT_DUPLICATE,
        )
    if len(ids) == 2:
        primary, secondary = adapters
        if secondary.stack_id not in primary.composes_with:
            return CompositionRejection(
                code=CompositionRejectionCode.UNSUPPORTED_PAIR,
                message=(
                    f"{primary.stack_id} cannot compose with "
                    f"{secondary.stack_id}; check the adapter's composes_with "
                    f"declaration"
                ),
            )
        if primary.stack_id not in secondary.composes_with:
            return CompositionRejection(
                code=CompositionRejectionCode.UNSUPPORTED_PAIR,
                message=(
                    f"{secondary.stack_id} cannot compose with "
                    f"{primary.stack_id}; check the adapter's composes_with "
                    f"declaration"
                ),
            )
    return None


def _validate_workspace_source_map_consistency(adapter: Adapter) -> None:
    """Per Codex PR #50 P1-B harden P2-δ: workspace_source_map_composition
    keys must match {primary} ∪ additional_workspaces of the same adapter.

    Empty map is allowed (legacy whole-tempdir adapters: ts_monorepo,
    astro, generic). Non-empty map must contain ALL declared workspaces
    (primary + additional_workspaces) AND must NOT contain extra keys.
    """
    map_keys = set(adapter.workspace_source_map_composition.keys())
    if not map_keys:
        # Legacy whole-tempdir adapter; additional_workspaces must be empty
        # because there is no source path to lift extras from.
        extras = tuple(getattr(adapter, "additional_workspaces", ()))
        if extras:
            raise CompositionAbortError(
                reason=(
                    CompositionRejectionCode
                    .WORKSPACE_SOURCE_MAP_MISMATCH.value
                ),
                path=None,
                remediation=(
                    f"adapter {adapter.stack_id} declares "
                    f"additional_workspaces={extras!r} but "
                    f"workspace_source_map_composition is empty; declare "
                    f"per-workspace source relpaths to lift them"
                ),
            )
        return

    primary = adapter.workspace_name
    additional = tuple(getattr(adapter, "additional_workspaces", ()))
    declared: set[str] = set(additional)
    if primary is not None:
        declared.add(primary)

    extra_keys = map_keys - declared
    if extra_keys:
        raise CompositionAbortError(
            reason=(
                CompositionRejectionCode
                .WORKSPACE_SOURCE_MAP_MISMATCH.value
            ),
            path=None,
            remediation=(
                f"adapter {adapter.stack_id} workspace_source_map_composition "
                f"declares {sorted(extra_keys)!r} but those keys are not in "
                f"{{primary={primary!r}}} ∪ additional_workspaces="
                f"{additional!r}"
            ),
        )

    missing_keys = declared - map_keys
    if missing_keys:
        raise CompositionAbortError(
            reason=(
                CompositionRejectionCode
                .WORKSPACE_SOURCE_MAP_MISMATCH.value
            ),
            path=None,
            remediation=(
                f"adapter {adapter.stack_id} declares "
                f"primary={primary!r} + additional_workspaces={additional!r} "
                f"but workspace_source_map_composition is missing keys "
                f"{sorted(missing_keys)!r}"
            ),
        )


def resolve_workspace_allocation(
    adapters: list[Adapter],
) -> tuple[dict[str, Adapter], list[str]]:
    """Build the workspace_dir -> adapter mapping with collision-suffix logic.

    Returns (mapping, info_logs). Info_logs is a list of section 3.12 verbatim
    messages emitted during allocation (currently only the `app -> app-fe`
    collision suffix log).

    Per Codex PR #50 P1-B harden P2-δ: validates each adapter's
    workspace_source_map_composition is consistent with its declared
    primary + additional_workspaces. Mismatches raise CompositionAbortError.
    """
    for adapter in adapters:
        _validate_workspace_source_map_consistency(adapter)

    mapping: dict[str, Adapter] = {}
    info_logs: list[str] = []
    seen_app_workspace = False
    for adapter in adapters:
        primary = adapter.workspace_name
        if primary is None:
            continue
        target_name = primary
        if primary == "app":
            if seen_app_workspace:
                # second adapter to claim 'app': it retains 'app'; the FIRST
                # is renamed -fe in a post-pass.
                target_name = "app"
            else:
                seen_app_workspace = True
                target_name = "app"
        mapping[target_name] = adapter

        # additional_workspaces (e.g. nextjs_fastapi 'api'): include them so
        # the composition-mode integration smoke can verify multi-workspace
        # adapters lay down all expected directories.
        for extra in getattr(adapter, "additional_workspaces", ()):
            if extra not in mapping:
                mapping[extra] = adapter

    # Resolve the `app + app` collision: if BOTH primary workspace_names are
    # 'app', rename the FIRST occurrence to 'app-fe' per section 3.4 +
    # section 3.12 INFO log.
    primary_app_claimers = [
        a for a in adapters if a.workspace_name == "app"
    ]
    if len(primary_app_claimers) == 2:
        first_adapter = primary_app_claimers[0]
        # rebuild mapping respecting the collision rename
        rebuilt: dict[str, Adapter] = {}
        for adapter in adapters:
            if adapter is first_adapter:
                rebuilt["app-fe"] = adapter
            elif adapter.workspace_name and adapter.workspace_name not in rebuilt:
                rebuilt[adapter.workspace_name] = adapter
            for extra in getattr(adapter, "additional_workspaces", ()):
                if extra not in rebuilt:
                    rebuilt[extra] = adapter
        mapping = rebuilt
        info_logs.append(_COLLISION_INFO)

    return mapping, info_logs


def _build_placement_plan(
    adapters: list[Adapter], mapping: dict[str, Adapter]
) -> list[_PlacementEntry]:
    """Build the (adapter, declared_key, dest_workspace_name, source_relpath)
    placement plan from the resolved workspace mapping.

    Per Codex PR #50 P1-B harden P3-β: when `resolve_workspace_allocation`
    renames the first `app`-claimer to `app-fe`, the source-side relpath
    stays adapter-declared (looked up by the original `workspace_name`)
    while the destination key reflects the rename.
    """
    plan: list[_PlacementEntry] = []
    # Reverse-lookup adapter-instance to dest names. dict is order-preserving
    # so the order matches resolve_workspace_allocation's iteration.
    adapter_to_dest_names: dict[int, list[str]] = {}
    for dest_name, adapter in mapping.items():
        adapter_to_dest_names.setdefault(id(adapter), []).append(dest_name)

    for adapter in adapters:
        dest_names = adapter_to_dest_names.get(id(adapter), [])
        if not dest_names:
            continue  # ts_monorepo (workspace_name=None) gets no placement

        ws_map = adapter.workspace_source_map_composition
        if not ws_map:
            # Legacy whole-tempdir adapter (astro / generic). Single dest_name
            # only; map source_relpath="" meaning "tempdir IS the workspace".
            assert len(dest_names) == 1, (
                f"adapter {adapter.stack_id} with empty "
                f"workspace_source_map_composition cannot have multiple "
                f"destinations {dest_names!r}"
            )
            plan.append(
                _PlacementEntry(
                    adapter=adapter,
                    declared_key=dest_names[0],
                    dest_workspace_name=dest_names[0],
                    source_relpath="",
                )
            )
            continue

        # Non-empty map: iterate the adapter's declared keys and resolve
        # each to its (possibly renamed) destination.
        primary = adapter.workspace_name
        for declared_key, source_relpath in ws_map.items():
            # Determine dest_workspace_name: if rename happened, the primary
            # was renamed to "app-fe" while additional_workspaces kept their
            # names. Match dest_names by elimination.
            if declared_key == primary and "app-fe" in dest_names:
                dest_workspace_name = "app-fe"
            elif declared_key in dest_names:
                dest_workspace_name = declared_key
            else:
                # Declared key absent from mapping (e.g. primary renamed but
                # additional_workspaces still in dest_names without primary
                # entry): fall back to renamed primary if exactly one
                # un-claimed dest_name remains.
                claimed = {
                    e.dest_workspace_name
                    for e in plan
                    if e.adapter is adapter
                }
                remaining = [d for d in dest_names if d not in claimed]
                if declared_key == primary and len(remaining) == 1:
                    dest_workspace_name = remaining[0]
                else:
                    raise CompositionAbortError(
                        reason=(
                            CompositionRejectionCode
                            .WORKSPACE_SOURCE_MAP_MISMATCH.value
                        ),
                        path=None,
                        remediation=(
                            f"adapter {adapter.stack_id} declares "
                            f"workspace_source_map_composition key "
                            f"{declared_key!r} but no destination "
                            f"in mapping {mapping!r} matches"
                        ),
                    )
            plan.append(
                _PlacementEntry(
                    adapter=adapter,
                    declared_key=declared_key,
                    dest_workspace_name=dest_workspace_name,
                    source_relpath=source_relpath,
                )
            )
    return plan


def _ensure_same_fs(composition_root: Path, tmp_root: Path) -> None:
    """Per harden P1-ζ: cross-FS guard. os.replace requires same-FS
    atomicity. Reject early so rollback cleanup doesn't compound the
    failure mode.
    """
    if composition_root.stat().st_dev != tmp_root.stat().st_dev:
        raise CompositionAbortError(
            reason="cross_filesystem_tmp_dir",
            path=tmp_root,
            remediation=(
                "TMPDIR is on a different filesystem than your project. Set "
                "TMPDIR to a path under the project root and re-run."
            ),
        )


def _reject_symlinks_in_subtree(src: Path) -> None:
    """Per Codex PR #50 P1-B harden P1-β: reject symlinks at the placement
    boundary. Walks the source subtree without following symlinks; any
    symlink (file OR dir) raises CompositionAbortError. Prevents an
    attacker-controlled scaffold tree from `os.replace`-ing a symlink to
    `/etc` into the project tree.
    """
    if src.is_symlink():
        raise CompositionAbortError(
            reason=CompositionRejectionCode.SYMLINK_IN_SCAFFOLD_TREE.value,
            path=src,
            remediation=(
                f"scaffold tree contains symlink at {src}; v2.1 forbids "
                f"symlinks in adapter-rendered output (defense against "
                f"attacker-controlled path traversal)"
            ),
        )
    if not src.is_dir():
        # is_symlink() on a missing path is False; so a stat check covers
        # the "src never existed" case in caller.
        return
    for dirpath, dirnames, filenames in os.walk(
        str(src), followlinks=False
    ):
        for name in (*dirnames, *filenames):
            child = Path(dirpath) / name
            try:
                child_stat = os.lstat(str(child))
            except OSError:
                continue
            if stat.S_ISLNK(child_stat.st_mode):
                raise CompositionAbortError(
                    reason=(
                        CompositionRejectionCode
                        .SYMLINK_IN_SCAFFOLD_TREE.value
                    ),
                    path=child,
                    remediation=(
                        f"scaffold tree contains symlink at {child}; "
                        f"v2.1 forbids symlinks in adapter-rendered "
                        f"output (defense against attacker-controlled "
                        f"path traversal)"
                    ),
                )


def _assert_within(
    candidate: Path, root: Path, *, field_name: str
) -> Path:
    """Per Codex PR #50 P1-B harden P1-α: containment check before every
    `os.replace`. `Path.is_relative_to` rejects path traversal even if the
    adapter import-time validator was bypassed.

    Mirrors the verbatim "attacker-controlled path traversal" comment pin
    from `plugin_default_generators/_renderer_base.py:75-79`.
    """
    resolved_candidate = candidate.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    if not resolved_candidate.is_relative_to(resolved_root):
        raise CompositionAbortError(
            reason=(
                CompositionRejectionCode
                .PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
            ),
            path=candidate,
            remediation=(
                f"{field_name} resolves to {resolved_candidate} which "
                f"escapes {resolved_root} (attacker-controlled path "
                f"traversal forbidden)"
            ),
        )
    return resolved_candidate


def _pre_composition_backup_path(target: Path, composition_root: Path) -> Path:
    """v2.1 Codex PR #50 post-review P0: deterministic backup-path naming.

    Returns `<parent>/<basename>.pre-composition-<sha8>` where sha8 is
    sha256 of the target's relpath under composition_root. Determinism
    means a stale backup from a prior crashed run is detectable by
    name (the user can either rename it back or run /lp-bootstrap
    --recover after confirming nothing else uses it).
    """
    rel = target.relative_to(composition_root).as_posix()
    sha8 = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:8]
    return target.with_name(f"{target.name}.pre-composition-{sha8}")


def _backup_existing_target(
    target: Path,
    composition_root: Path,
) -> Path | None:
    """v2.1 Codex PR #50 post-review P0: replace rmtree-then-place with
    rename-aside-then-place.

    If `target` exists, atomic-rename it to its deterministic backup
    sibling and return the backup path. If `target` is absent, return
    None (no backup needed). If the backup path already exists (stale
    from a prior crash), refuse with `STALE_PRE_COMPOSITION_BACKUP` so
    the operator decides whether to keep the prior backup or move it
    aside before re-running.

    Atomic rename preserves the user's pre-existing tree byte-for-byte
    (no copy cost; same-FS rename guaranteed since composition_root +
    backup-sibling share the same parent device).
    """
    if not target.exists():
        return None
    backup = _pre_composition_backup_path(target, composition_root)
    if backup.exists():
        raise CompositionAbortError(
            reason=CompositionRejectionCode.STALE_PRE_COMPOSITION_BACKUP.value,
            path=backup,
            remediation=(
                f"a stale composition backup is present at {backup} from a "
                f"prior crashed /lp-pick-stack or /lp-scaffold-stack run. "
                f"Run /lp-bootstrap --recover to clear stale state, OR "
                f"manually rename {backup} aside if you want to keep it for "
                f"forensic review before re-running. composition refuses to "
                f"clobber an unverified backup."
            ),
        )
    os.rename(str(target), str(backup))
    return backup


def _rollback(
    rendered_tempdirs: list[tuple[Adapter, Path]],
    placed_paths: list[Path],
    backups: "list[tuple[Path, Path]] | None" = None,
) -> None:
    """Per Codex PR #50 P1-B harden P1-γ: rollback rmtrees BOTH rendered
    tempdirs AND already-placed `apps/<workspace>/` + composition_root
    package paths in REVERSE order. Errors during cleanup preserve the
    secrets-warning log line VERBATIM from the legacy rollback path.

    v2.1 Codex PR #50 post-review P0: also restore pre-existing target
    trees from `.pre-composition-<sha8>` backups. Reverse-order:
      1. Remove placed paths (newly written content).
      2. Atomic-rename each backup back to its original target path,
         restoring the user's pre-existing tree byte-for-byte.
      3. Remove rendered tempdirs.

    Backup restore happens AFTER placed-path removal so the rename slot
    is clear when restore fires.
    """
    # Reverse-order rmtree of placed paths first (more visible to the
    # operator post-failure).
    for placed in reversed(placed_paths):
        try:
            if placed.is_dir():
                shutil.rmtree(placed, ignore_errors=False)
            elif placed.exists():
                placed.unlink()
        except OSError as cleanup_err:
            LOG.error(
                "rollback rmtree failed for %s; manual cleanup required (may "
                "contain secrets-shaped files like .env.example): %s",
                placed,
                cleanup_err,
            )
    # v2.1 Codex PR #50 post-review P0: restore backups in reverse
    # order so dependent paths (e.g., apps/web restored before
    # apps/admin) are slotted back consistently.
    if backups:
        for original, backup in reversed(backups):
            if not backup.exists():
                continue
            try:
                # If the placed-path removal above failed and the
                # original is still on disk, we cannot restore without
                # clobbering — leave the backup in place and surface a
                # loud log so the operator handles it manually.
                if original.exists():
                    LOG.error(
                        "rollback could not restore %s from backup %s: "
                        "original path still exists post-rollback. Manual "
                        "intervention required: rm -rf %s && mv %s %s",
                        original, backup, original, backup, original,
                    )
                    continue
                os.rename(str(backup), str(original))
            except OSError as restore_err:
                LOG.error(
                    "rollback restore failed for %s -> %s; manual cleanup "
                    "required (backup at %s contains user's pre-composition "
                    "tree; mv it back manually): %s",
                    backup, original, backup, restore_err,
                )
    for adapter, tempdir in rendered_tempdirs:
        try:
            shutil.rmtree(tempdir, ignore_errors=False)
        except OSError as cleanup_err:
            LOG.error(
                "rollback rmtree failed for %s; manual cleanup required (may "
                "contain secrets-shaped files like .env.example): %s",
                tempdir,
                cleanup_err,
            )


def _check_no_residual_moved_subtree(
    tempdir: Path,
    moved_relpaths: Iterable[str],
) -> None:
    """Per Codex PR #50 P1-B harden P3-ν: if any of the previously-moved
    subtree paths is still present under tempdir after the move loop
    completes, that signals tampering (a fetcher re-emerged moved
    content). Refuse cleanup (fail-closed) with structured error citing
    the offending paths.
    """
    offenders: list[Path] = []
    for relpath in moved_relpaths:
        if not relpath:
            continue
        candidate = tempdir / relpath
        if candidate.exists():
            offenders.append(candidate)
    if offenders:
        raise CompositionAbortError(
            reason=(
                CompositionRejectionCode
                .RESIDUAL_TAMPERED_TEMPDIR.value
            ),
            path=tempdir,
            remediation=(
                f"tempdir {tempdir} contains residual paths previously "
                f"moved out: {[str(p) for p in offenders]!r}; refusing "
                f"cleanup to surface tampered-tempdir slip-through"
            ),
        )


# --- v2.1 Codex PR #50 cycle 6 F8: atomic backup relocation -------------
#
# Cycle 5's success-path used `shutil.rmtree(backup_path)` to clean up
# `.pre-composition-<sha8>/` siblings AFTER composition succeeded. That
# was a destructive write that PERMANENTLY DELETED user content on
# brownfield runs. Cycle 6 replaces deletion with atomic relocation to
# `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>/` so the user's
# pre-existing content is forensically recoverable.
#
# Naming scheme + dir creation reuse `make_backup_dir()` from
# `lp_bootstrap.policy`; the helper allocates the path empty, we rmdir
# it, stage in a sibling `<basename>.staging/`, then atomic-rename
# staging -> final on success (single os.rename = atomic commit boundary).


def _validate_backup_relpath(relpath: Path) -> None:
    """Per DA-F8.4: traversal-safe relpath check.

    Reject `..`, empty parts, null bytes, embedded path separators, and
    absolute paths. Defense-in-depth against adapter-manifest-supplied
    path injection.
    """
    if relpath.is_absolute():
        raise CompositionAbortError(
            reason=(
                CompositionRejectionCode
                .PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
            ),
            path=relpath,
            remediation=(
                f"backup relpath {relpath!r} is absolute; v2.1 requires "
                f"relative paths under composition_root for backup "
                f"relocation"
            ),
        )
    for part in relpath.parts:
        if part in ("", ".."):
            raise CompositionAbortError(
                reason=(
                    CompositionRejectionCode
                    .PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
                ),
                path=relpath,
                remediation=(
                    f"backup relpath {relpath!r} contains forbidden "
                    f"component {part!r}; v2.1 forbids path-traversal "
                    f"in adapter-supplied paths (defense against "
                    f"attacker-controlled path traversal)"
                ),
            )
        if "\x00" in part or "/" in part or "\\" in part:
            raise CompositionAbortError(
                reason=(
                    CompositionRejectionCode
                    .PATH_TRAVERSAL_IN_WORKSPACE_MAP.value
                ),
                path=relpath,
                remediation=(
                    f"backup relpath {relpath!r} contains null byte or "
                    f"path-separator artifact in component {part!r}"
                ),
            )


def _count_tree(path: Path) -> tuple[int, int]:
    """Return (file_count, total_bytes) under `path`.

    Used to populate the per-target backup manifest (DA-F8.5). Best-effort:
    OSErrors during stat are skipped so a partially-readable backup tree
    doesn't fail the manifest write.

    Cycle 6 hardening: uses `os.lstat` + `stat.S_ISREG` so symlinks within
    a user-controlled backup tree do NOT contribute to the byte count
    (defense-in-depth — without this, a symlink to `/dev/zero` planted in
    a prior backup could distort the disk-space WARN threshold).
    """
    file_count = 0
    total_bytes = 0
    for dirpath, _dirnames, filenames in os.walk(str(path), followlinks=False):
        for name in filenames:
            child = Path(dirpath) / name
            try:
                st = os.lstat(str(child))
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                # Skip symlinks, devices, fifos — only regular files count.
                continue
            file_count += 1
            total_bytes += st.st_size
    return file_count, total_bytes


def _read_plugin_version_for_manifest(composition_root: Path) -> str:
    """Best-effort read of plugin_version from scaffold-decision.json.

    Returns "unknown" if the decision file is missing or malformed.
    Manifest write must not fail because of decision-file unavailability.
    """
    decision_path = (
        composition_root / ".launchpad" / "scaffold-decision.json"
    )
    try:
        text = decision_path.read_text(encoding="utf-8")
        payload = json.loads(text)
        if isinstance(payload, dict):
            version = payload.get("plugin_version")
            if isinstance(version, str) and version:
                return version
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return "unknown"


def _relocate_backups_to_launchpad(
    backups: list[tuple[Path, Path]],
    composition_root: Path,
) -> Path | None:
    """Atomically relocate `.pre-composition-<sha8>/` backups to
    `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>/` on composition success.

    DA-F8.1: reuses `make_backup_dir()` naming scheme (rmdirs the eagerly-
    created dir to free the path for atomic-rename commit).
    DA-F8.2: uses `os.replace` (atomic same-FS); EXDEV refuses-loud.
    DA-F8.3: stage-then-commit pattern. Phase A relocates per-target into
    `<basename>.staging/`; Phase B is a single `os.rename` that commits the
    entire staged tree atomically. On Phase A failure, every already-staged
    item is rolled back to its workspace `.pre-composition-<sha8>/` slot.
    DA-F8.5: writes `_manifest.json` listing per-target metadata.

    Returns the final `<ts>-<PID>-<rand4>/` directory (or None if `backups`
    is empty — greenfield placement). Mode 0o700 on the staging dir per
    T2-5; preserved across the atomic rename to the final dir.
    """
    if not backups:
        return None

    # Deferred import to keep `composition` module light at import time.
    from lp_bootstrap.policy import make_backup_dir

    # DA-F8.1 naming via shared helper. The helper creates the dir empty
    # (`mkdir(parents=True, exist_ok=False)`); rmdir it so the path is
    # free for the atomic-rename commit below. The `<ts>-<PID>-<rand4>`
    # naming is collision-resistant and same-process, so the rmdir-then-
    # rename window cannot be observed by another concurrent caller.
    final_dir = make_backup_dir(composition_root)
    final_dir.rmdir()
    staging_dir = final_dir.parent / (final_dir.name + ".staging")
    staging_dir.mkdir()
    # T2-5: explicit chmod after mkdir; some umask values defeat mkdir mode.
    os.chmod(staging_dir, 0o700)

    # Phase A: stage all backups. Track for rollback on partial failure.
    staged: list[tuple[Path, Path, Path]] = []  # (workspace_backup, staged_dest, original_target)
    try:
        for target, workspace_backup in backups:
            relpath = target.relative_to(composition_root)
            _validate_backup_relpath(relpath)
            dest = staging_dir / relpath
            dest.parent.mkdir(parents=True, exist_ok=True)
            _assert_within(
                dest,
                staging_dir,
                field_name=(
                    f"backup-relocation dest for relpath "
                    f"{relpath.as_posix()!r}"
                ),
            )
            try:
                os.replace(str(workspace_backup), str(dest))
            except OSError as exc:
                if exc.errno == errno.EXDEV:
                    raise CompositionAbortError(
                        reason="cross_filesystem_backup_relocation",
                        path=workspace_backup,
                        remediation=(
                            f".launchpad/backups/ must be on the same "
                            f"filesystem as composition_root="
                            f"{composition_root!r}; got EXDEV relocating "
                            f"{workspace_backup} -> {dest}. If you "
                            f"bind-mounted .launchpad/, undo the mount "
                            f"and re-run /lp-scaffold-stack."
                        ),
                    ) from exc
                raise
            staged.append((workspace_backup, dest, target))
    except BaseException:
        # Rollback Phase A: return staged items to their workspace
        # `.pre-composition-<sha8>/` slots. On rollback failure, log
        # loud — user gets stale-backup error on next composition run.
        for workspace_backup, staged_dest, _target in reversed(staged):
            try:
                os.replace(str(staged_dest), str(workspace_backup))
            except OSError as restore_err:
                LOG.error(
                    "Phase A backup-relocation rollback failed: %s -> %s; "
                    "manual cleanup required (the next composition run "
                    "will refuse with STALE_PRE_COMPOSITION_BACKUP "
                    "and surface the leak): %s",
                    staged_dest,
                    workspace_backup,
                    restore_err,
                )
        try:
            shutil.rmtree(staging_dir, ignore_errors=False)
        except OSError as cleanup_err:
            LOG.error(
                "staging cleanup failed at %s; manual rm -rf required: %s",
                staging_dir,
                cleanup_err,
            )
        raise

    # Build manifest while paths are still under staging_dir.
    manifest_targets: list[dict[str, object]] = []
    for _workspace_backup, staged_dest, target in staged:
        relpath_posix = target.relative_to(composition_root).as_posix()
        file_count, size_bytes = _count_tree(staged_dest)
        manifest_targets.append({
            "original_path": relpath_posix,
            "size_bytes": size_bytes,
            "file_count": file_count,
        })
    composition_run_id = hashlib.sha256(
        "|".join(sorted(
            str(t["original_path"]) for t in manifest_targets
        )).encode("utf-8")
    ).hexdigest()[:8]
    manifest = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "composition_run_id": composition_run_id,
        "targets": manifest_targets,
        "plugin_version": _read_plugin_version_for_manifest(composition_root),
        "caller": "/lp-scaffold-stack",
    }
    (staging_dir / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Phase B: atomic single-rename commit. After this succeeds, the entire
    # staged tree (including manifest) becomes visible at `final_dir` in one
    # syscall. If this rename fails, workspace state is already consumed
    # (Phase A succeeded) — we surface the failure with structured error +
    # loud stderr notice so the operator knows where to recover from
    # (rather than discovering an orphan `.staging/` dir via `du -sh`).
    try:
        os.rename(str(staging_dir), str(final_dir))
    except OSError as exc:
        sys.stderr.write(
            f"error: composition succeeded but backup commit failed at "
            f"{final_dir}; staged content preserved at {staging_dir}/. "
            f"Manual recovery: mv {staging_dir} {final_dir}\n"
        )
        raise CompositionAbortError(
            reason="backup_relocation_commit_failed",
            path=staging_dir,
            remediation=(
                f"composition succeeded but backup-relocation commit "
                f"(os.rename {staging_dir} -> {final_dir}) failed: {exc}. "
                f"Workspace state is already consumed (the new scaffold IS "
                f"at the original target locations). Pre-existing user "
                f"content is preserved at {staging_dir}/; recover via "
                f"`mv {staging_dir} {final_dir}` before re-running "
                f"/lp-scaffold-stack."
            ),
        ) from exc
    return final_dir


def _emit_backup_relocation_notice(final_dir: Path) -> None:
    """DA-F8.8: stderr surface backup location post-success.

    Without this, user discovers `.launchpad/backups/` only via `du -sh`
    audit — hostile UX.

    Cycle 6 hardening: parity with `_rollback`'s "may contain
    secrets-shaped files" warning so operators tarballing backups for
    forensic review know NOT to commit / share without a sweep.
    """
    sys.stderr.write(
        f"note: previous workspace content preserved at {final_dir}/ "
        f"(recovery: cp -r {final_dir}/<relpath>/ <original-target>/). "
        f"May contain secrets-shaped files like .env or .env.example; "
        f"do NOT commit or share without auditing.\n"
    )


def _warn_if_backups_dir_large(composition_root: Path) -> None:
    """DA-F8.9: stderr WARN when `.launchpad/backups/` exceeds 50 entries
    or 1 GB. Pointer to manual cleanup; v2.1.1 BL-287 lands an automated
    `/lp-cleanup-backups [--older-than=N-days]` retention command.
    """
    backups_root = composition_root / ".launchpad" / "backups"
    if not backups_root.is_dir():
        return
    try:
        entries = [e for e in backups_root.iterdir() if e.is_dir()]
    except OSError:
        return
    total_bytes = 0
    for entry in entries:
        _, sz = _count_tree(entry)
        total_bytes += sz
    one_gb = 1024 ** 3
    if len(entries) > 50 or total_bytes > one_gb:
        sys.stderr.write(
            f"warn: .launchpad/backups/ contains {len(entries)} backup "
            f"entries totalling {total_bytes // (1024 * 1024)} MB. "
            f"Consider manual cleanup: rm -rf .launchpad/backups/<older-entries>\n"
        )


def compose(
    adapters: list[Adapter],
    composition_root: Path,
) -> CompositionResult:
    """Phase 4 composition orchestrator.

    Validates the selection, allocates workspaces, scaffolds + overlays each
    adapter into a tempdir under composition_root/.lp-tmp/, and atomically
    places each rendered tempdir's per-workspace subtree at
    composition_root/apps/<workspace_name>/. `package_workspace_paths` lift
    upstream-nested `packages/` to top-level siblings.

    Per Codex PR #50 P1-B: composition placement now honors
    `Adapter.workspace_source_map_composition` so `nextjs_standalone`
    (`{"app": "apps/app"}` + `package_workspace_paths=("packages",)`) and
    `nextjs_fastapi` (`{"app": "app", "api": "api"}`) produce
    structurally-correct Turborepo layouts.
    """
    rejection = validate_pair(adapters)
    if rejection is not None:
        raise CompositionAbortError(
            reason=rejection.code.value,
            path=composition_root,
            remediation=rejection.message,
        )

    composition_root.mkdir(parents=True, exist_ok=True)
    apps_root = composition_root / "apps"
    apps_root.mkdir(parents=True, exist_ok=True)
    tmp_root = composition_root / TMP_PARENT_DIRNAME
    tmp_root.mkdir(parents=True, exist_ok=True)
    _ensure_same_fs(composition_root, tmp_root)

    workspace_map, info_logs = resolve_workspace_allocation(adapters)
    for log_msg in info_logs:
        LOG.info(log_msg)

    # Per Codex PR #50 P1-B harden P2-θ: detect collisions between adapters
    # declaring overlapping `package_workspace_paths` BEFORE rendering any
    # tempdir.
    seen_packages: dict[str, Adapter] = {}
    for adapter in adapters:
        for pkg_path in adapter.package_workspace_paths:
            if pkg_path in seen_packages:
                raise CompositionAbortError(
                    reason=(
                        CompositionRejectionCode
                        .PACKAGE_WORKSPACE_PATH_COLLISION.value
                    ),
                    path=composition_root,
                    remediation=(
                        f"adapters {seen_packages[pkg_path].stack_id} and "
                        f"{adapter.stack_id} both declare "
                        f"package_workspace_paths containing {pkg_path!r}; "
                        f"v2.1 forbids overlap"
                    ),
                )
            seen_packages[pkg_path] = adapter

    placement_plan = _build_placement_plan(adapters, workspace_map)

    # Per Codex PR #50 P1-B harden P3-γ: dict instead of list[tuple] keyed
    # on adapter identity to eliminate the legacy O(n²) `next()` scan.
    rendered: dict[int, tuple[Adapter, Path]] = {}
    placed: list[Path] = []
    # v2.1 Codex PR #50 post-review P0: backup-before-clobber tracking.
    # Each entry is `(original_target_path, backup_path)`; rollback
    # restores by atomic-renaming backup -> original.
    backups: list[tuple[Path, Path]] = []
    try:
        for adapter in adapters:
            tempdir = tmp_root / f"lp-{adapter.stack_id}-{uuid.uuid4().hex[:8]}"
            try:
                adapter.scaffold_into(tempdir)
                adapter.apply_overlay(tempdir)
            except Exception as exc:
                rendered[id(adapter)] = (adapter, tempdir)
                raise CompositionAbortError(
                    reason="adapter_scaffold_failed",
                    path=tempdir,
                    remediation=(
                        f"adapter {adapter.stack_id} failed during scaffold/"
                        f"overlay: {exc}"
                    ),
                ) from exc
            rendered[id(adapter)] = (adapter, tempdir)

        # Per-workspace placement loop using per-adapter
        # workspace_source_map_composition. Empty map preserves the legacy
        # whole-tempdir → apps/<dest> behavior.
        for entry in placement_plan:
            _, tempdir = rendered[id(entry.adapter)]
            if entry.source_relpath:
                src_raw = tempdir / entry.source_relpath
            else:
                src_raw = tempdir
            # Containment check against the rendering tempdir (P1-α).
            src = _assert_within(
                src_raw,
                tempdir,
                field_name=(
                    f"workspace_source_map_composition[{entry.declared_key!r}]"
                    f" of {entry.adapter.stack_id}"
                ),
            )
            if not src.exists():
                raise CompositionAbortError(
                    reason=(
                        CompositionRejectionCode
                        .WORKSPACE_SOURCE_MAP_MISMATCH.value
                    ),
                    path=src,
                    remediation=(
                        f"adapter {entry.adapter.stack_id} declared source "
                        f"relpath {entry.source_relpath!r} but the rendered "
                        f"tempdir does not contain that path"
                    ),
                )
            # Symlink rejection (P1-β) on the source subtree.
            _reject_symlinks_in_subtree(src)
            workspace_target_raw = apps_root / entry.dest_workspace_name
            workspace_target = _assert_within(
                workspace_target_raw,
                composition_root,
                field_name=(
                    f"apps/{entry.dest_workspace_name}"
                ),
            )
            # v2.1 Codex PR #50 post-review P0: replace rmtree-then-place
            # with backup-rename-then-place. Atomic rename preserves the
            # user's pre-existing tree byte-for-byte; rollback can
            # restore it if placement fails. Refuse if a stale backup
            # already exists (prior crashed run).
            backup = _backup_existing_target(workspace_target, composition_root)
            if backup is not None:
                backups.append((workspace_target, backup))
            os.replace(str(src), str(workspace_target))
            placed.append(workspace_target)

        # Per-package lift: top-level siblings under composition_root.
        for adapter in adapters:
            _, tempdir = rendered[id(adapter)]
            for pkg_relpath in adapter.package_workspace_paths:
                src_raw = tempdir / pkg_relpath
                src = _assert_within(
                    src_raw,
                    tempdir,
                    field_name=(
                        f"package_workspace_paths[{pkg_relpath!r}] of "
                        f"{adapter.stack_id}"
                    ),
                )
                if not src.exists():
                    # Adapter declared a `packages/` sibling but the upstream
                    # didn't ship one in this rendering. Skip silently rather
                    # than fail; not all sub-templates have the same layout.
                    continue
                _reject_symlinks_in_subtree(src)
                dst_raw = composition_root / pkg_relpath
                dst = _assert_within(
                    dst_raw,
                    composition_root,
                    field_name=f"package path {pkg_relpath!r}",
                )
                # v2.1 Codex PR #50 post-review P0: backup-rename-then-place
                # for package paths too (same data-loss risk as workspace
                # paths above).
                backup = _backup_existing_target(dst, composition_root)
                if backup is not None:
                    backups.append((dst, backup))
                os.replace(str(src), str(dst))
                placed.append(dst)

        # Per harden P2-ε + P3-ν: cleanup the now-stripped tempdirs after
        # all moves. Fail-closed if any moved subtree path re-emerges in
        # the residual (signals tampering).
        for adapter in adapters:
            _, tempdir = rendered[id(adapter)]
            moved_relpaths: list[str] = []
            for entry in placement_plan:
                if entry.adapter is adapter and entry.source_relpath:
                    moved_relpaths.append(entry.source_relpath)
            moved_relpaths.extend(adapter.package_workspace_paths)
            _check_no_residual_moved_subtree(tempdir, moved_relpaths)
            if tempdir.exists():
                shutil.rmtree(tempdir, ignore_errors=False)

        # If nothing else lives under tmp_root, drop it too (keeps
        # composition_root tidy when the gitignore has not yet been seeded).
        if tmp_root.exists() and not any(tmp_root.iterdir()):
            tmp_root.rmdir()
    except BaseException:
        _rollback(
            [(a, td) for (a, td) in rendered.values() if td.exists()],
            placed,
            backups=backups,
        )
        raise

    # v2.1 Codex PR #50 cycle 6 F8: replace destructive `shutil.rmtree`
    # cleanup (which permanently deleted user code on brownfield runs)
    # with atomic relocation to `.launchpad/backups/<ts>-<PID>-<rand4>/`.
    # The relocation preserves the user's pre-existing tree forensically
    # AND lifts it OUT of workspace globs (`apps/*`, `packages/*`) so the
    # next composition run cannot trigger `STALE_PRE_COMPOSITION_BACKUP`.
    final_backup_dir = _relocate_backups_to_launchpad(
        backups, composition_root
    )
    if final_backup_dir is not None:
        _emit_backup_relocation_notice(final_backup_dir)
        _warn_if_backups_dir_large(composition_root)

    return CompositionResult(
        composition_root=composition_root,
        workspaces=workspace_map,
        placed_paths=placed,
        info_log_messages=info_logs,
    )


__all__ = [
    "CompositionAbortError",
    "CompositionRejection",
    "CompositionRejectionCode",
    "CompositionResult",
    "N2_CAP",
    "TMP_PARENT_DIRNAME",
    "compose",
    "resolve_workspace_allocation",
    "validate_pair",
    "_ensure_same_fs",
    "_reject_symlinks_in_subtree",
    "_assert_within",
]
