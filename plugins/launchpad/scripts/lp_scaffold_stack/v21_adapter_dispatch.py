"""v2.1 Adapter dispatch helper for /lp-scaffold-stack.

Phase 4 plan section 4 Slice D + Codex PR #50 P1-B harden Slice C.
The existing `lp_scaffold_stack/engine.py:run_pipeline` predates the v2.1
Adapter Protocol and dispatches to the v1 `run() -> AdapterOutput` API;
this module is the v2.1 dispatch surface that compositions and
adapter-aware single-stack scaffolds invoke instead.

Single-adapter mode:
  - When `Adapter.workspace_source_map_single` is empty (ts_monorepo,
    nextjs_standalone, astro, generic), invokes
    `Adapter.scaffold_into(workspace_dir)` followed by
    `Adapter.apply_overlay(workspace_dir)`. Preserves the existing
    fork-as-project-root semantics for nextjs_standalone.
  - When the map is non-empty (nextjs_fastapi: `{"app": "app",
    "api": "api"}`), routes through `dispatch_single_adapter_into_apps`
    which renders into a `<workspace>/.lp-tmp/` tempdir then `os.replace`
    each declared subtree to `<workspace>/apps/<workspace_name>/`.

Composition mode: dispatches to `composition.compose(adapters,
composition_root)`. The N=2 cap is enforced upstream by
`composition.validate_pair`; this module surfaces the rejection unchanged.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Iterable

from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM
from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionRejectionCode,
    CompositionResult,
    TMP_PARENT_DIRNAME,
    _assert_within,
    _ensure_same_fs,
    _reject_symlinks_in_subtree,
    compose,
    validate_pair,
)
from plugin_stack_adapters.contracts import (
    Adapter,
    bridge_to_scaffold_error,
    ScaffoldStepFailedError,
)


_ADAPTER_REGISTRY: dict[str, str] = {
    "ts_monorepo": "plugin_stack_adapters.ts_monorepo",
    "nextjs_standalone": "plugin_stack_adapters.nextjs_standalone",
    "nextjs_fastapi": "plugin_stack_adapters.nextjs_fastapi",
    "astro": "plugin_stack_adapters.astro",
    "generic": "plugin_stack_adapters.generic",
}

# v2.1.0 completion plan §3.1 D1a: v2.2-candidate stack-ids partition,
# derived from `STACK_ID_ACTIVE_ENUM - frozenset(_ADAPTER_REGISTRY)` so
# the partition invariant is structural (any future addition to
# STACK_ID_ACTIVE_ENUM auto-classifies as candidate-or-active by registry
# membership; drift becomes impossible). Replaces the cycle-0 drift-gate
# test approach with a one-line invariant.
_V22_CANDIDATE_IDS: frozenset[str] = (
    STACK_ID_ACTIVE_ENUM - frozenset(_ADAPTER_REGISTRY)
)


def resolve_adapter(
    stack_id: str,
    *,
    accept_v22_fallback: bool = False,
) -> Adapter:
    """Look up the v2.1 ADAPTER singleton for a closed-enum stack id.

    For v2.2-candidate ids without an active Adapter Protocol
    implementation: hard-fail unless `accept_v22_fallback=True`. With the
    flag, route via the `generic` adapter and emit stderr WARN; the
    caller persists `adapter_dispatch_meta.fallback_ids` to the receipt.

    Per 2026-05-08-v2.1.0-completion-plan.md §2.1.1: silent generic
    fallback is a confused-deputy hazard (user picks `nextjs_hono_*`,
    artifact is a blank shell, divergence invisible until workspace
    open). Flag-gated opt-in keeps the catalog-alias pattern available
    for power users while preserving discoverability.
    """
    import importlib

    if stack_id in _ADAPTER_REGISTRY:
        return importlib.import_module(_ADAPTER_REGISTRY[stack_id]).ADAPTER  # type: ignore[no-any-return]

    if stack_id in _V22_CANDIDATE_IDS:
        if not accept_v22_fallback:
            raise ScaffoldStepFailedError(
                reason="v22_candidate_unsupported",
                path=None,
                remediation=(
                    f"stack_id {stack_id!r} ships specialized support in "
                    f"v2.2; pass --accept-v22-fallback to scaffold via the "
                    f"generic adapter at v2.1.0 (a minimal, framework-"
                    f"agnostic workspace shell — framework-specific "
                    f"scaffolding ships in v2.2)"
                ),
            )
        import sys
        print(
            f"[v2.1 dispatch] stack_id {stack_id!r} routed via generic "
            f"adapter — no specialized v2.1 adapter; v2.2 ships dedicated "
            f"support; --accept-v22-fallback acknowledged",
            file=sys.stderr,
        )
        return importlib.import_module(_ADAPTER_REGISTRY["generic"]).ADAPTER  # type: ignore[no-any-return]

    raise ScaffoldStepFailedError(
        reason="unknown_v21_stack_id",
        path=None,
        remediation=(
            f"stack_id {stack_id!r} not in STACK_ID_ACTIVE_ENUM "
            f"{tuple(_ADAPTER_REGISTRY) + tuple(sorted(_V22_CANDIDATE_IDS))!r}"
        ),
    )


def _dispatch_single_adapter_into_apps(
    adapter: Adapter, project_root: Path
) -> Path:
    """Single-adapter mode for adapters declaring a non-empty
    `workspace_source_map_single`.

    Per Codex PR #50 P1-B harden D3 + P1-ε + P1-ζ:
      1. Refuse-loud if `<project_root>/apps/<workspace_name>/` already
         contains user content (re-run idempotency).
      2. Scaffold into a tempdir under `<project_root>/.lp-tmp/`.
      3. For each declared `(workspace_name, source_relpath)`: validate
         path containment, reject symlinks, then `os.replace
         tempdir/<source_relpath> → project_root/apps/<workspace_name>/`.
      4. Lift `package_workspace_paths` to top-level siblings.
      5. Cleanup the residual tempdir; fail-closed if a moved subtree
         re-emerged.

    Per harden P1-ζ: the tempdir parent is `.lp-tmp/` (NOT `.tmp/`) to
    avoid collision with Next.js build directories. Generated
    `.gitignore` includes `.lp-tmp/` (item-driven; not in this module).
    """
    project_root.mkdir(parents=True, exist_ok=True)
    apps_root = project_root / "apps"
    apps_root.mkdir(parents=True, exist_ok=True)

    # Per harden P1-ε re-run idempotency: refuse-loud if any declared
    # destination already contains user content. composition_root is
    # whole-project-replace by contract; single-adapter dispatch is NOT,
    # so we cannot blindly rmtree-then-replace.
    for workspace_name in adapter.workspace_source_map_single:
        target = apps_root / workspace_name
        if target.exists() and any(target.iterdir()):
            raise ScaffoldStepFailedError(
                reason="workspace_target_already_populated",
                path=target,
                remediation=(
                    f"{target} already contains user content; "
                    f"delete apps/{workspace_name}/ or use --force "
                    f"to re-scaffold"
                ),
            )
    for pkg_relpath in adapter.package_workspace_paths:
        target = project_root / pkg_relpath
        if target.exists() and any(target.iterdir()):
            raise ScaffoldStepFailedError(
                reason="workspace_target_already_populated",
                path=target,
                remediation=(
                    f"{target} already contains user content; "
                    f"delete {pkg_relpath}/ or use --force to re-scaffold"
                ),
            )

    tmp_root = project_root / TMP_PARENT_DIRNAME
    tmp_root.mkdir(parents=True, exist_ok=True)
    # Per harden P1-ζ: cross-FS guard on the single-adapter tempdir mirrors
    # the composition-mode check.
    _ensure_same_fs(project_root, tmp_root)

    tempdir = tmp_root / f"lp-{adapter.stack_id}-{uuid.uuid4().hex[:8]}"
    placed: list[Path] = []
    try:
        adapter.scaffold_into(tempdir)
        adapter.apply_overlay(tempdir)

        for workspace_name, source_relpath in (
            adapter.workspace_source_map_single.items()
        ):
            src_raw = tempdir / source_relpath
            src = _assert_within(
                src_raw,
                tempdir,
                field_name=(
                    f"workspace_source_map_single[{workspace_name!r}] of "
                    f"{adapter.stack_id}"
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
                        f"adapter {adapter.stack_id} declared source "
                        f"relpath {source_relpath!r} but the rendered "
                        f"tempdir does not contain that path"
                    ),
                )
            _reject_symlinks_in_subtree(src)
            workspace_target_raw = apps_root / workspace_name
            workspace_target = _assert_within(
                workspace_target_raw,
                project_root,
                field_name=f"apps/{workspace_name}",
            )
            # Idempotency pre-check above already verified the target is
            # empty/missing; safe to rmdir an empty placeholder if one
            # exists from the apps_root.mkdir above.
            if workspace_target.exists() and not any(
                workspace_target.iterdir()
            ):
                workspace_target.rmdir()
            os.replace(str(src), str(workspace_target))
            placed.append(workspace_target)

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
                continue
            _reject_symlinks_in_subtree(src)
            dst_raw = project_root / pkg_relpath
            dst = _assert_within(
                dst_raw,
                project_root,
                field_name=f"package path {pkg_relpath!r}",
            )
            if dst.exists() and not any(dst.iterdir()):
                dst.rmdir()
            os.replace(str(src), str(dst))
            placed.append(dst)

        # Per harden P3-ν: surface tampered-tempdir slip-through.
        for workspace_name, source_relpath in (
            adapter.workspace_source_map_single.items()
        ):
            if (tempdir / source_relpath).exists():
                raise CompositionAbortError(
                    reason=(
                        CompositionRejectionCode
                        .RESIDUAL_TAMPERED_TEMPDIR.value
                    ),
                    path=tempdir,
                    remediation=(
                        f"tempdir {tempdir} still contains "
                        f"{source_relpath!r} after move; refusing cleanup "
                        f"to surface tampered-tempdir slip-through"
                    ),
                )
        for pkg_relpath in adapter.package_workspace_paths:
            if (tempdir / pkg_relpath).exists():
                raise CompositionAbortError(
                    reason=(
                        CompositionRejectionCode
                        .RESIDUAL_TAMPERED_TEMPDIR.value
                    ),
                    path=tempdir,
                    remediation=(
                        f"tempdir {tempdir} still contains "
                        f"{pkg_relpath!r} after move; refusing cleanup "
                        f"to surface tampered-tempdir slip-through"
                    ),
                )

        if tempdir.exists():
            shutil.rmtree(tempdir, ignore_errors=False)
        if tmp_root.exists() and not any(tmp_root.iterdir()):
            tmp_root.rmdir()
    except BaseException:
        # Per harden P1-γ: rollback in REVERSE order. Failure to clean up
        # a placed dir logs the secrets-warning recommendation via the
        # composition._rollback path; here we inline a simpler rollback
        # since dispatch is single-adapter-only.
        for path in reversed(placed):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=False)
                elif path.exists():
                    path.unlink()
            except OSError:
                # Same secrets-warning posture as composition._rollback.
                pass
        if tempdir.exists():
            try:
                shutil.rmtree(tempdir, ignore_errors=False)
            except OSError:
                pass
        raise

    return project_root


def dispatch_single_adapter(
    adapter: Adapter, workspace_dir: Path
) -> Path:
    """Single-adapter mode dispatch.

    Per Codex PR #50 P1-B harden D3:
      - Empty `workspace_source_map_single`: legacy behavior — call
        `scaffold_into(workspace_dir)` directly. Covers ts_monorepo +
        astro + generic + nextjs_standalone (single-mode preserves
        fork-as-project-root for next-forge).
      - Non-empty: route through `_dispatch_single_adapter_into_apps`.
    """
    workspace_dir.mkdir(parents=True, exist_ok=True)
    if not adapter.workspace_source_map_single:
        try:
            adapter.scaffold_into(workspace_dir)
            adapter.apply_overlay(workspace_dir)
        except Exception as exc:
            raise bridge_to_scaffold_error(exc) from exc
        return workspace_dir
    try:
        return _dispatch_single_adapter_into_apps(adapter, workspace_dir)
    except CompositionAbortError:
        raise
    except Exception as exc:
        raise bridge_to_scaffold_error(exc) from exc


def dispatch_composition(
    adapters: Iterable[Adapter], composition_root: Path
) -> CompositionResult:
    """Composition mode: validate + compose. N=2 cap enforced upstream."""
    selected = list(adapters)
    rejection = validate_pair(selected)
    if rejection is not None:
        raise CompositionAbortError(
            reason=rejection.code.value,
            path=composition_root,
            remediation=rejection.message,
        )
    return compose(selected, composition_root)


def dispatch_by_stack_ids(
    stack_ids: list[str],
    workspace_dir: Path,
    *,
    accept_v22_fallback: bool = False,
) -> CompositionResult | Path:
    """One entrypoint for callers that have stack_ids and want a uniform
    return surface. Single-id: returns the populated workspace_dir.
    Multi-id: returns the CompositionResult.

    `accept_v22_fallback` (kwarg-only per cycle-3 of the v2.1.0
    completion plan §2.1.1): when True, v2.2-candidate stack ids route
    via the `generic` adapter instead of hard-failing. The caller is
    responsible for persisting the fallback list to
    `adapter_dispatch_meta.fallback_ids` on the scaffold receipt.
    """
    if len(stack_ids) == 0:
        raise ScaffoldStepFailedError(
            reason="empty_stack_id_list",
            path=workspace_dir,
            remediation="at least one stack_id is required",
        )
    if len(stack_ids) == 1:
        adapter = resolve_adapter(
            stack_ids[0], accept_v22_fallback=accept_v22_fallback
        )
        return dispatch_single_adapter(adapter, workspace_dir)
    adapters = [
        resolve_adapter(sid, accept_v22_fallback=accept_v22_fallback)
        for sid in stack_ids
    ]
    return dispatch_composition(adapters, workspace_dir)


def fallback_ids_used(
    stack_ids: list[str], *, accept_v22_fallback: bool
) -> list[str]:
    """Return the post-validation intersection of `stack_ids` with the
    v2.2-candidate set, only when the fallback flag is in effect.

    Per 2026-05-08-v2.1.0-completion-plan.md §3.5: the engine persists
    this list as `adapter_dispatch_meta.fallback_ids` on the scaffold
    receipt. Bounded by the N=2 composition cap and STACK_ID_ACTIVE_ENUM
    membership; v2.2 readers MUST treat the field as historical record
    (validate against v2.1.0's union, not v2.2's then-current enum).
    """
    if not accept_v22_fallback:
        return []
    return [sid for sid in stack_ids if sid in _V22_CANDIDATE_IDS]


__all__ = [
    "_V22_CANDIDATE_IDS",
    "resolve_adapter",
    "dispatch_single_adapter",
    "dispatch_composition",
    "dispatch_by_stack_ids",
    "fallback_ids_used",
]
