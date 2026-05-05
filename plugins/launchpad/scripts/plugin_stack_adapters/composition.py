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

Sequential render:
  1. Same-FS pre-flight: TMPDIR must be on the same filesystem as
     composition_root. os.replace requires same-FS atomicity.
  2. Per-adapter scaffold_into(tempdir) into composition_root/.tmp/<id>.
  3. Per-adapter apply_overlay(tempdir).
  4. After all adapters complete, atomic os.replace into final
     composition_root/apps/<workspace_name>/ paths.
  5. On any per-adapter failure, rollback: shutil.rmtree all prior
     successful tempdirs + the in-progress one. Errors during cleanup are
     logged with the secrets-warning recommendation per harden P0.
"""
from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from .contracts import (
    Adapter,
    AdapterScaffoldError,
    StackIdActive,
)

LOG = logging.getLogger("plugin_stack_adapters.composition")

N2_CAP = 2
TS_MONOREPO_STACK_ID: StackIdActive = "ts_monorepo"


class CompositionRejectionCode(StrEnum):
    N2_CAP_EXCEEDED = "n2_cap_exceeded"
    TS_MONOREPO_PAIR = "ts_monorepo_pair"
    DUPLICATE_STACKS = "duplicate_stacks"
    UNSUPPORTED_PAIR = "unsupported_pair"


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


def resolve_workspace_allocation(
    adapters: list[Adapter],
) -> tuple[dict[str, Adapter], list[str]]:
    """Build the workspace_dir -> adapter mapping with collision-suffix logic.

    Returns (mapping, info_logs). Info_logs is a list of section 3.12 verbatim
    messages emitted during allocation (currently only the `app -> app-fe`
    collision suffix log).
    """
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


def _ensure_same_fs(composition_root: Path, tmp_root: Path) -> None:
    if composition_root.stat().st_dev != tmp_root.stat().st_dev:
        raise CompositionAbortError(
            reason="cross_filesystem_tmp_dir",
            path=tmp_root,
            remediation=(
                "TMPDIR is on a different filesystem than your project. Set "
                "TMPDIR to a path under the project root and re-run."
            ),
        )


def _rollback(rendered_tempdirs: list[tuple[Adapter, Path]]) -> None:
    """Phase 4 section 3.6 rollback contract; secrets-warning on rmtree fail."""
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


def compose(
    adapters: list[Adapter],
    composition_root: Path,
) -> CompositionResult:
    """Phase 4 composition orchestrator.

    Validates the selection, allocates workspaces, scaffolds + overlays each
    adapter into a tempdir under composition_root/.tmp/, and atomically
    places each rendered tempdir at composition_root/apps/<workspace>.
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
    tmp_root = composition_root / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    _ensure_same_fs(composition_root, tmp_root)

    workspace_map, info_logs = resolve_workspace_allocation(adapters)
    for log_msg in info_logs:
        LOG.info(log_msg)

    # Reverse-map adapter -> assigned workspace_name (primary only). This is
    # what we actually place under apps/. additional_workspaces are handled
    # implicitly by scaffold_into laying down both subtrees inside the
    # tempdir; the placement step only handles the primary workspace dir.
    adapter_to_primary_workspace: dict[Adapter, str] = {}
    for ws_name, adapter in workspace_map.items():
        if adapter not in adapter_to_primary_workspace:
            adapter_to_primary_workspace[adapter] = ws_name

    rendered: list[tuple[Adapter, Path]] = []
    placed: list[Path] = []
    try:
        for adapter in adapters:
            tempdir = tmp_root / f"lp-{adapter.stack_id}-{uuid.uuid4().hex[:8]}"
            try:
                adapter.scaffold_into(tempdir)
                adapter.apply_overlay(tempdir)
            except Exception as exc:
                rendered.append((adapter, tempdir))
                raise CompositionAbortError(
                    reason="adapter_scaffold_failed",
                    path=tempdir,
                    remediation=(
                        f"adapter {adapter.stack_id} failed during scaffold/"
                        f"overlay: {exc}"
                    ),
                ) from exc
            rendered.append((adapter, tempdir))

        for adapter in adapters:
            tempdir = next(td for a, td in rendered if a is adapter)
            workspace_name = adapter_to_primary_workspace[adapter]
            workspace_target = apps_root / workspace_name
            if workspace_target.exists():
                shutil.rmtree(workspace_target)
            import os

            os.replace(str(tempdir), str(workspace_target))
            placed.append(workspace_target)
    except BaseException:
        _rollback([(a, td) for a, td in rendered if td.exists()])
        raise

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
    "compose",
    "resolve_workspace_allocation",
    "validate_pair",
]
