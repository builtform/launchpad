"""Top-level `/lp-bootstrap` orchestration (v2.1 Phase 3 Slice C).

Public surface:
    run_bootstrap(cwd, *, mode, refresh_paths=None,
                  accept_plugin_version_drift=False) -> BootstrapResult

Engine ordering (locked in plan section 4 Slice C step 1, harden A7):

  1. Acquire flock on dedicated `.launchpad/.bootstrap.lock` (NOT the
     manifest itself, NOT the parent directory).
  2. Inspect sentinel; PID-liveness via `os.kill(pid, 0)`; recover-if-stale
     (INFO `stale_sentinel_recovered`) OR refuse with `sentinel_blocking`.
  3. Plugin-version pin check FIRST. Surfaces drift before tampering check
     fires misleadingly. Honor `accept_plugin_version_drift` per section 3.4
     (records drift in scaffold-decision `version_drift_log[]`,
     auto-triggers `--refresh-all`).
  4. Manifest-tampering integrity check on plugin-shipped templates. Uses
     module-load-cached `_SOURCE_TEMPLATE_SHAS` (no per-invocation file reads).
  5. Write sentinel.
  6. Render loop with fast-path (harden A16): for each target, compute
     rendered_sha + on_disk_sha + manifest_entry_sha. If
     `on_disk_sha == manifest_entry_sha == rendered_sha`, skip atomic
     write entirely. Brownfield-auto on a clean overlay drops 30 fsyncs to 0.
  7. Atomic-write via `atomic_io.atomic_write_replace`; chmod AFTER replace
     per harden B8 (post-replace chmod is defense-in-depth on top of the
     atomic-write helper's tempfile-mode fchmod).
  8. Write manifest atomically (LAST in loop); only on full-run success
     per harden B16.
  9. Clear sentinel.
  10. Release flock.
  11. Emit telemetry per harden A3.
  12. Return `BootstrapResult`.

Renderer singleton (harden B4): `_RENDERER = InfrastructureRenderer()` at
module top so the Jinja env is constructed once per Python process; saves
~5-15ms per brownfield-auto call.

Direct script invocation is supported via `python3 -m lp_bootstrap.engine`
(see `__main__` guard below) and serializes on the flock; manual `rm` of
the sentinel is for confirmed-dead processes only.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from datetime import (  # noqa: E402  (placed after sys.path mutation for sibling import resolution)
    UTC,
)

from atomic_io import advisory_flock  # noqa: E402
from plugin_default_generators._renderer_base import (  # noqa: E402
    sha256_bytes,
    sha256_file,
)
from plugin_default_generators.infrastructure_renderer import (  # noqa: E402
    InfrastructureRenderer,
    InfrastructureRenderError,
)
from telemetry_writer import write_telemetry_entry  # noqa: E402

from lp_bootstrap import (  # noqa: E402
    INFRASTRUCTURE_FILES,
    INFRASTRUCTURE_TARGETS,
    LAUNCHPAD_DIR_NAME,
    LOCK_NAME,
    BootstrapError,
    BootstrapErrorCode,
    BootstrapPolicy,
)
from lp_bootstrap.manifest_writer import (  # noqa: E402
    BootstrapManifest,
    BootstrapManifestEntry,
    BootstrapManifestError,
    build_manifest,
    source_template_shas,
    verify_source_template_shas,
    write_manifest,
)
from lp_bootstrap.policy import (  # noqa: E402
    BootstrapPolicyError,
    PolicyAction,
    apply_append_only,
    apply_merge_keys,
    apply_overwrite_if_unchanged,
    ensure_backups_in_gitignore,
    make_backup_dir,
    record_warnings,
    write_backup_then_overwrite,
)
from lp_bootstrap.sentinel import (  # noqa: E402
    SentinelSnapshot,
    clear_sentinel,
    is_pid_alive,
    read_sentinel,
    write_sentinel,
)

# --- Per-module typed exception ------------------------------------------


class BootstrapEngineError(RuntimeError):
    """Engine orchestration failure raised by this module."""

    def __init__(
        self,
        message: str,
        *,
        reason: BootstrapErrorCode,
        path: Path | None = None,
        remediation: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path
        self.remediation = remediation


# --- BootstrapResult ------------------------------------------------------

BootstrapMode = Literal[
    "greenfield", "brownfield-auto", "refresh", "refresh-all", "recover"
]

BootstrapOutcome = Literal[
    "success",
    "sentinel_blocked",
    "manifest_tampered",
    "manifest_corrupt",
    "plugin_version_mismatch",
    "policy_collision",
    "brownfield_auto_rendered",
    "render_failed",
]


@dataclass(frozen=True)
class BootstrapResult:
    """Engine result surface; consumed by the slash command + telemetry."""

    outcome: BootstrapOutcome
    mode: BootstrapMode
    files_processed: int
    files_written: int
    files_skipped: int
    files_kept_user_edits: int
    errors: tuple[BootstrapError, ...]
    warnings: tuple[str, ...]
    manifest_path: Path | None
    backup_dir: Path | None
    plugin_version: str | None


# --- Renderer singleton (harden B4) --------------------------------------

_RENDERER: InfrastructureRenderer = InfrastructureRenderer()


# --- Plugin manifest path (read_running_plugin_version source of truth) --
#
# Phase 1+2 retroactive amendment (bonus dead-code removal): the prior
# inlined `_read_running_plugin_version` + `_PLUGIN_JSON` constants were
# byte-for-byte duplicates of `lp_pick_stack.decision_writer`'s exported
# `read_running_plugin_version`. Consolidated to a single source of truth
# via deferred import inside the helper to keep engine import-time light.


def _read_running_plugin_version() -> str:
    """Delegate to `lp_pick_stack.decision_writer.read_running_plugin_version`.

    Deferred import keeps the heavy identity-validation surface out of
    engine import time. On manifest-not-found, the underlying reader
    raises FileNotFoundError; we translate to a structured engine error
    so callers see the existing remediation message.
    """
    from lp_pick_stack.decision_writer import (
        read_running_plugin_version as _shared,
    )

    try:
        return _shared()
    except FileNotFoundError as exc:
        raise BootstrapEngineError(
            f"plugin manifest not found: {exc}",
            reason=BootstrapErrorCode.LAUNCHPAD_DIR_MISSING,
            remediation="reinstall the LaunchPad plugin",
        ) from exc


# --- Phase 1 reader bridge -----------------------------------------------
#
# `plugin-config-loader.py` is the canonical reader for both
# `scaffold-decision.json` and `bootstrap-manifest.json`. The hyphenated
# filename forces an explicit spec_from_file_location; we keep the loaded
# module cached so the import cost is paid once per Python process.

_PLUGIN_CONFIG_LOADER: Any = None


def _plugin_config_loader() -> Any:
    """Return the lazily-loaded plugin-config-loader module."""
    global _PLUGIN_CONFIG_LOADER
    if _PLUGIN_CONFIG_LOADER is not None:
        return _PLUGIN_CONFIG_LOADER
    loader_path = _SCRIPTS_DIR / "plugin-config-loader.py"
    spec = importlib.util.spec_from_file_location("plugin_config_loader", loader_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _PLUGIN_CONFIG_LOADER = mod
    return mod


# --- Identity sourcing ---------------------------------------------------


def _resolve_identity(cwd: Path) -> Mapping[str, Any]:
    """Resolve identity for rendering from `.launchpad/scaffold-decision.json`.

    Falls back to placeholder identity when scaffold-decision is absent or
    schema 1.0 (legacy v2.0 envelope without identity). Greenfield callers
    (Step 4.6 wiring) inject identity directly via `mode="greenfield"` so
    this helper is the brownfield/refresh path.
    """
    cfg = _plugin_config_loader()
    result = cfg.read_scaffold_decision(cwd)
    if not result.present:
        return _placeholder_identity()
    payload = result.payload
    identity = payload.get("identity")
    if not isinstance(identity, dict):
        return _placeholder_identity()
    return identity


def _placeholder_identity() -> dict[str, Any]:
    """Build a placeholder identity matching the v2.1 PII opt-out posture.

    Mirrors `lp_pick_stack.decision_writer.default_unset_identity`. Pulled
    inline so the engine does not import the heavy decision_writer module
    (which validates identity on every import).
    """
    return {
        "pii_opt_in": False,
        "project_name": "<project-name>",
        "email": "<email>",
        "copyright_holder": "<copyright-holder>",
        "repo_url": "<repo-url>",
        "license": "Other",
        "license_other_body": "",
    }


# --- Plugin-version pin check (V3 section 11.1; engine step 3) ----------


def _check_plugin_version_pin(
    cwd: Path,
    *,
    accept_drift: bool,
) -> tuple[str, list[str]]:
    """Verify the running plugin version matches what scaffold-decision recorded.

    Returns `(running_version, warnings)`. Raises
    `BootstrapEngineError(PLUGIN_VERSION_MISMATCH)` on drift unless
    `accept_drift=True`, in which case a warning is collected and the
    drift is recorded in scaffold-decision.json `version_drift_log[]` per
    section 3.4.
    """
    running = _read_running_plugin_version()

    cfg = _plugin_config_loader()
    decision = cfg.read_scaffold_decision(cwd)
    if not decision.present or decision.schema_version in (None, "1.0"):
        # Legacy or absent decision -> nothing to drift against.
        return running, []
    recorded = decision.payload.get("plugin_version")
    if not isinstance(recorded, str) or recorded == running:
        return running, []

    if not accept_drift:
        raise BootstrapEngineError(
            f"plugin version drift: scaffold-decision recorded {recorded!r}, "
            f"running plugin is {running!r}",
            reason=BootstrapErrorCode.PLUGIN_VERSION_MISMATCH,
            remediation=(
                "re-run with --accept-plugin-version-drift to accept the "
                "drift (auto-triggers --refresh-all and records the drift "
                "in scaffold-decision.json `version_drift_log[]`)."
            ),
        )

    # accept_drift=True: record the drift inline on scaffold-decision.json.
    _record_version_drift(cwd, decision.payload, recorded, running)
    return running, [
        f"plugin version drift accepted: {recorded!r} -> {running!r}; "
        f"--refresh-all auto-triggered to align manifest shas"
    ]


def _record_version_drift(
    cwd: Path,
    decision_payload: dict[str, Any],
    from_version: str,
    to_version: str,
) -> None:
    """Append a `version_drift_log[]` entry and reseal scaffold-decision.json.

    v2.1 Codex PR #50 Greptile #7 (D7): canonical 5-key shape via the
    shared `compute_identity_fields_changed` helper. Bootstrap version-
    pin drift always emits `fields_changed=["plugin_version"]` (only
    plugin_version drifted; identity fields unchanged).

    Sealed identity preserved (the original `plugin_version` field stays
    pointing at the originally-recorded version; future readers see the
    drift in the audit trail rather than via overwrite).

    LOAD-BEARING INVARIANT (DA-F9.2): this function MUST be called under
    `advisory_flock(lock_path)` from `_check_plugin_version_pin`. Calling
    it outside the locked region creates a read-mutate-write race where
    concurrent `--accept-plugin-version-drift` invocations can lose log
    entries. The flock is acquired at engine.py:669; do NOT refactor this
    call out of the locked region.

    v2.1 Codex PR #50 cycle 6 F9: routes the mutation through
    `re_seal_decision_atomic()` so the on-disk `sha256` envelope is
    recomputed after the drift-log append. Cycle 5's direct
    `atomic_write_replace` left the hash stale, breaking subsequent
    decision validation. File mode tightens 0o644 -> 0o600 via the
    helper's contract (DA-F9.1, intentional posture-tightening).
    """
    from datetime import datetime

    from lp_bootstrap.version_drift import (
        Fingerprint,
        Names,
        compute_identity_fields_changed,
    )

    accepted_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Bootstrap drift always touches `plugin_version` only; route through
    # the shared helper so writer-side serialization (Names ->
    # fields_changed; Fingerprint -> fields_changed_fingerprint) matches
    # the identity-update writer exactly. `pii_opt_in` is read from the
    # in-memory payload (the flock invariant above prevents skew between
    # this read and the disk re-read inside `re_seal_decision_atomic`).
    pii_opt_in = bool(
        ((decision_payload.get("identity") or {}) or {}).get("pii_opt_in")
    )
    changed = compute_identity_fields_changed(
        {"plugin_version": str(from_version)},
        {"plugin_version": str(to_version)},
        pii_opt_in=pii_opt_in,
    )
    entry: dict[str, Any] = {
        "from_version": from_version,
        "to_version": to_version,
        "via": "bootstrap",
        "accepted_at": accepted_at,
    }
    if isinstance(changed, Names):
        entry["fields_changed"] = list(changed.names)
    elif isinstance(changed, Fingerprint):
        entry["fields_changed_fingerprint"] = changed.digest

    def _apply_drift_log(payload: dict[str, Any]) -> None:
        log = payload.get("version_drift_log") or []
        log.append(entry)
        payload["version_drift_log"] = log

    from lp_pick_stack.decision_writer import re_seal_decision_atomic

    try:
        re_seal_decision_atomic(cwd, update_fn=_apply_drift_log)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # OSError covers FileNotFoundError (missing decision file) AND the
        # write-side surface of `atomic_write_replace` (disk full / EACCES /
        # EROFS / EXDEV / FileExistsError on sentinel collision). Catching
        # the broader class ensures every reseal-side failure surfaces with
        # the structured VERSION_DRIFT_RESEAL_FAILED code rather than
        # leaking a raw OSError past the engine boundary.
        raise BootstrapEngineError(
            f"--accept-plugin-version-drift could not reseal "
            f"scaffold-decision.json: {exc}",
            reason=BootstrapErrorCode.VERSION_DRIFT_RESEAL_FAILED,
            remediation=(
                "Verify .launchpad/scaffold-decision.json exists and is "
                "not hand-edited; check available disk space and "
                "filesystem permissions; run /lp-bootstrap --refresh to "
                "regenerate the sealed envelope before retrying "
                "--accept-plugin-version-drift."
            ),
        ) from exc


# --- Sentinel preflight (engine step 2) -----------------------------------


def _sentinel_preflight(cwd: Path) -> tuple[SentinelSnapshot | None, list[str]]:
    """Inspect sentinel; recover-if-stale OR refuse.

    Returns `(snapshot_or_None, info_messages)`. Raises
    `BootstrapEngineError(SENTINEL_BLOCKING)` when a live PID owns the
    `/lp-bootstrap` sentinel; raises `BootstrapEngineError(
    IDENTITY_UPDATE_IN_PROGRESS)` when a live PID owns the
    `/lp-update-identity` sentinel (Phase 10 DA3 bidirectional parity per
    security F2 + frontend-races F1).
    """
    # Phase 10 DA3: bidirectional cross-detect of identity-update sentinel
    # BEFORE the bootstrap-own sentinel check. If a live /lp-update-identity
    # is running, /lp-bootstrap must refuse so the two commands cannot
    # interleave their atomic-replace windows on scaffold-decision.json.
    #
    # Phase 11 hardening A1: same-PID guard. /lp-scaffold-stack acquires
    # its own sentinel and then invokes run_bootstrap from the SAME
    # process; that legitimate in-process re-entry must not self-block.
    # If `command_pid == os.getpid()`, the sentinel belongs to the same
    # execution context (not a concurrent peer), so skip the refusal.
    own_pid = os.getpid()
    try:
        from lp_update_identity.sentinel import (
            is_pid_alive as _id_is_pid_alive,
        )
        from lp_update_identity.sentinel import (
            read_sentinel as _id_read_sentinel,
        )
    except ImportError:  # pragma: no cover - lp_update_identity ships in v2.1
        _id_read_sentinel = None  # type: ignore[assignment]
    if _id_read_sentinel is not None:
        id_snap = _id_read_sentinel(cwd)
        if (
            id_snap is not None
            and id_snap.command_pid != own_pid
            and _id_is_pid_alive(id_snap.command_pid)
        ):
            raise BootstrapEngineError(
                f"/lp-update-identity is running (sentinel pid={id_snap.command_pid})",
                reason=BootstrapErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
                remediation=(
                    f"wait for pid {id_snap.command_pid} to finish before "
                    f"re-running /lp-bootstrap; the two commands cannot "
                    f"interleave"
                ),
            )

    # Phase 10 cycle-2 F9 + cycle-3 P2-2: bidirectional cross-detect of
    # scaffold-stack sentinel. /lp-bootstrap refuses while
    # /lp-scaffold-stack is in its kernel-render + scaffold-decision
    # re-seal window so the two commands cannot race the atomic-replace.
    # Same-PID guard mirrors the identity-update branch above.
    try:
        from lp_scaffold_stack.sentinel import (
            is_pid_alive as _ss_is_pid_alive,
        )
        from lp_scaffold_stack.sentinel import (
            read_sentinel as _ss_read_sentinel,
        )
    except ImportError:  # pragma: no cover
        _ss_read_sentinel = None  # type: ignore[assignment]
    if _ss_read_sentinel is not None:
        ss_snap = _ss_read_sentinel(cwd)
        if (
            ss_snap is not None
            and ss_snap.command_pid != own_pid
            and _ss_is_pid_alive(ss_snap.command_pid)
        ):
            raise BootstrapEngineError(
                f"/lp-scaffold-stack is running (sentinel pid={ss_snap.command_pid})",
                reason=BootstrapErrorCode.SENTINEL_BLOCKING,
                remediation=(
                    f"wait for pid {ss_snap.command_pid} to finish before "
                    f"re-running /lp-bootstrap"
                ),
            )

    snap = read_sentinel(cwd)
    if snap is None:
        return None, []

    if is_pid_alive(snap.command_pid):
        raise BootstrapEngineError(
            f"another /lp-bootstrap is running (sentinel pid={snap.command_pid})",
            reason=BootstrapErrorCode.SENTINEL_BLOCKING,
            remediation=(
                f"wait for pid {snap.command_pid} to finish, OR kill it and "
                f"re-run /lp-bootstrap --recover after confirming the "
                f"process is dead"
            ),
        )

    # Dead PID -> recover.
    clear_sentinel(cwd)
    return snap, [
        f"recovered stale sentinel (dead pid={snap.command_pid}, "
        f"started_at={snap.started_at})"
    ]


# --- Manifest tampering check (engine step 4) ----------------------------


def _verify_manifest_integrity(
    cwd: Path,
) -> tuple[BootstrapManifest | None, list[str]]:
    """Read existing manifest (if any); verify plugin-shipped sha integrity.

    Returns `(manifest_or_None, warnings)`. Raises
    `BootstrapEngineError(MANIFEST_TAMPERED)` when manifest entries diverge
    from the cached source-template shas (harden B3); raises
    `BootstrapEngineError(MANIFEST_CORRUPT)` for malformed JSON / wrong
    envelope shape.
    """
    cfg = _plugin_config_loader()
    try:
        result = cfg.read_bootstrap_manifest(cwd)
    except Exception as exc:  # noqa: BLE001
        raise BootstrapEngineError(
            f"manifest read failed: {exc}",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            remediation=(
                "delete .launchpad/bootstrap-manifest.json to force a clean "
                "re-bootstrap; the existing file is unreadable"
            ),
        ) from exc

    if not result.present:
        return None, []

    payload = result.payload
    # Reserved security_fields v2.2-downgrade defense (harden B9 / section 6.2)
    sec = payload.get("security_fields", [])
    if not isinstance(sec, list) or sec:
        raise BootstrapEngineError(
            f"manifest carries non-empty security_fields {sec!r}; v2.1 "
            f"reader does not understand security extensions",
            reason=BootstrapErrorCode.MANIFEST_TAMPERED,
            remediation=(
                "downgrade-attack defense; investigate the source of this "
                "manifest before proceeding"
            ),
        )

    files = payload.get("files", [])
    if not isinstance(files, list):
        raise BootstrapEngineError(
            "manifest `files` must be a list",
            reason=BootstrapErrorCode.MANIFEST_CORRUPT,
            remediation="rebuild manifest by removing it and re-running /lp-bootstrap",
        )

    entries: list[BootstrapManifestEntry] = []
    for f in files:
        try:
            entries.append(
                BootstrapManifestEntry(
                    path=f["path"],
                    source_template_sha256=f["source_template_sha256"],
                    rendered_content_sha256=f["rendered_content_sha256"],
                    policy=f["policy"],
                    mode=int(f["mode"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BootstrapEngineError(
                f"manifest file entry malformed: {f!r} ({exc})",
                reason=BootstrapErrorCode.MANIFEST_CORRUPT,
                remediation=("delete .launchpad/bootstrap-manifest.json to rebuild"),
            ) from exc

    manifest = BootstrapManifest(
        manifest_schema_version=payload.get("manifest_schema_version", "1.0"),
        plugin_version=str(payload.get("plugin_version", "")),
        last_render_timestamp=str(payload.get("last_render_timestamp", "")),
        files=tuple(entries),
    )

    expected = source_template_shas()
    try:
        verify_source_template_shas(manifest, expected_shas=expected)
    except BootstrapManifestError as exc:
        raise BootstrapEngineError(
            str(exc),
            reason=exc.reason,
            path=exc.path,
            remediation=exc.remediation,
        ) from exc
    return manifest, []


# --- Render loop helpers --------------------------------------------------


def _entry_sha_for(
    manifest: BootstrapManifest | None, target_relpath: str
) -> str | None:
    if manifest is None:
        return None
    for entry in manifest.files:
        if entry.path == target_relpath:
            return entry.rendered_content_sha256
    return None


def _yaml_dumper(value: Any) -> str:
    import yaml  # type: ignore[import-not-found]

    return yaml.safe_dump(value, default_flow_style=False, sort_keys=True)


def _serializer_for(target_relpath: str) -> str:
    if target_relpath == ".github/CODEOWNERS":
        return "codeowners"
    if target_relpath.endswith(".json"):
        return "json"
    if target_relpath.endswith((".yml", ".yaml")):
        return "yaml"
    return "json"


def _selected_targets(
    refresh_paths: Sequence[str] | None,
) -> list[tuple[str, str, BootstrapPolicy, int]]:
    """Filter INFRASTRUCTURE_FILES to the active targets for this run.

    `refresh_paths is None` means full bootstrap (all 30). Otherwise the
    iteration restricts to the explicitly requested targets, preserving
    INFRASTRUCTURE_FILES order so `.gitignore` still renders first when
    requested.
    """
    if refresh_paths is None:
        return list(INFRASTRUCTURE_FILES)
    allowed = set(refresh_paths)
    return [row for row in INFRASTRUCTURE_FILES if row[1] in allowed]


def _validate_refresh_paths(refresh_paths: Sequence[str]) -> None:
    """Reject unknown `--refresh <path>` arguments per harden A15."""
    from lp_bootstrap.manifest_writer import _normalize_path

    for raw in refresh_paths:
        try:
            normalized = _normalize_path(raw)
        except BootstrapManifestError as exc:
            raise BootstrapEngineError(
                str(exc),
                reason=exc.reason,
                path=exc.path,
                remediation=exc.remediation,
            ) from exc
        if normalized not in INFRASTRUCTURE_TARGETS:
            raise BootstrapEngineError(
                f"--refresh path {raw!r} is not in the v2.1 30-path inventory",
                reason=BootstrapErrorCode.UNKNOWN_REFRESH_PATH,
                path=Path(raw),
                remediation=(
                    "see /lp-bootstrap --help for the canonical infrastructure "
                    "inventory; kernel files (LICENSE, README.md, etc.) refresh "
                    "via /lp-update-identity, NOT /lp-bootstrap --refresh"
                ),
            )


# --- Main entrypoint ------------------------------------------------------


def run_bootstrap(
    cwd: Path,
    *,
    mode: BootstrapMode = "greenfield",
    refresh_paths: Sequence[str] | None = None,
    identity: Mapping[str, Any] | None = None,
    accept_plugin_version_drift: bool = False,
    dry_run: bool = False,
) -> BootstrapResult:
    """Materialize the v2.1 30-path infrastructure overlay under `cwd`.

    `mode` selects the dispatch flow:
      * `greenfield`: full bootstrap; identity supplied by caller
        (lp_scaffold_stack Step 4.6 wiring) -> always renders all 30 paths.
      * `brownfield-auto`: full bootstrap from `/lp-define`; identity read
        from scaffold-decision; consent prompt (caller's responsibility);
        fast-path skips clean overlay paths.
      * `refresh`: `--refresh <path> ...`; uses overwrite-with-backup; auto
        triggered by `--accept-plugin-version-drift` to re-align manifest
        shas after a `/plugin update`.
      * `refresh-all`: every infrastructure path re-rendered with backup.
      * `recover`: inspect sentinel + on-disk reality; auto-complete an
        interrupted run OR fail with structured guidance. (Engine step
        through items 1, 2 only; render loop is a no-op.)

    Identity is required for greenfield (caller injects sealed identity);
    inferred from scaffold-decision.json otherwise.
    """
    repo_root = cwd
    launchpad_dir = cwd / LAUNCHPAD_DIR_NAME
    launchpad_dir.mkdir(parents=True, exist_ok=True)

    lock_path = launchpad_dir / LOCK_NAME
    plugin_version: str | None = None
    warnings: list[str] = []
    backup_dir: Path | None = None

    try:
        if refresh_paths is not None:
            _validate_refresh_paths(refresh_paths)

        with advisory_flock(lock_path):
            # Step 2: sentinel preflight.
            recovered_snap, info = _sentinel_preflight(cwd)
            warnings.extend(info)

            if mode == "recover":
                # Recover-mode terminates after preflight; sentinel cleared
                # if stale, error if live process owned it.
                _emit_telemetry(
                    repo_root,
                    "success",
                    mode,
                    files_processed=0,
                    files_written=0,
                    files_skipped=0,
                    files_kept=0,
                )
                return BootstrapResult(
                    outcome="success",
                    mode=mode,
                    files_processed=0,
                    files_written=0,
                    files_skipped=0,
                    files_kept_user_edits=0,
                    errors=(),
                    warnings=tuple(warnings),
                    manifest_path=None,
                    backup_dir=None,
                    plugin_version=None,
                )

            # v2.1 Codex PR #50 P1 + Greptile #2 (D8): write_sentinel becomes
            # the FIRST mutable action so the 5 operations below execute
            # under the bootstrap sentinel. Closes the cross-detect window
            # race (another /lp-bootstrap or /lp-update-identity could
            # squeeze its own atomic-replace through between this run's
            # _check_plugin_version_pin and the prior write_sentinel
            # location). The 5 ops + render path are wrapped in try/finally
            # so clear_sentinel fires on every exit path.
            #
            # Provisional sentinel content: pre_edit_manifest_sha256 + the
            # final target_paths list are not yet known (they come after
            # _verify_manifest_integrity + refresh-mode degradation). We
            # write provisional values up-front; the sentinel is treated
            # as a lock + observability marker, not a forensic record.
            write_sentinel(
                cwd,
                mode=mode,
                pre_edit_manifest_sha256=None,
                target_paths=[],
            )

            try:
                # Step 3: plugin-version pin check FIRST.
                running, vinfos = _check_plugin_version_pin(
                    cwd,
                    accept_drift=accept_plugin_version_drift,
                )
                plugin_version = running
                warnings.extend(vinfos)

                # Step 4: manifest tampering integrity check.
                existing_manifest, mwarn = _verify_manifest_integrity(cwd)
                warnings.extend(mwarn)

                if mode in ("refresh", "refresh-all") and existing_manifest is None:
                    # Harden A8: silently degrade to full bootstrap with INFO log.
                    warnings.append(
                        "no manifest found; running full bootstrap "
                        "(mode degraded from refresh to greenfield-class)"
                    )
                    refresh_paths = None
                    # Treat as full bootstrap from here.

                if (
                    accept_plugin_version_drift
                    and refresh_paths is None
                    and mode in ("brownfield-auto", "greenfield")
                ):
                    # Section 3.4 + 6.1: drift-accepted runs auto-trigger
                    # --refresh-all to realign manifest shas.
                    mode = "refresh-all"

                # Resolve identity.
                if identity is None:
                    resolved_identity = _resolve_identity(cwd)
                else:
                    resolved_identity = identity
            except BaseException:
                # Any failure in the 5 moved ops MUST clear the sentinel.
                clear_sentinel(cwd)
                raise

            # v2.1 Codex PR #50 P1.D (D4): dry_run short-circuit. The
            # sentinel is acquired-and-cleared above; no manifest write,
            # no render-loop side effects. Returns a minimal success
            # result so callers can verify the sentinel lifecycle.
            if dry_run:
                clear_sentinel(cwd)
                _emit_telemetry(
                    repo_root,
                    "success",
                    mode,
                    files_processed=0,
                    files_written=0,
                    files_skipped=0,
                    files_kept=0,
                )
                return BootstrapResult(
                    outcome="success",
                    mode=mode,
                    files_processed=0,
                    files_written=0,
                    files_skipped=0,
                    files_kept_user_edits=0,
                    errors=(),
                    warnings=tuple(warnings),
                    manifest_path=None,
                    backup_dir=None,
                    plugin_version=plugin_version,
                )

            # Refresh modes: ensure backups dir is gitignored, then create
            # a fresh backup directory.
            if mode in ("refresh", "refresh-all"):
                ensure_backups_in_gitignore(cwd)
                backup_dir = make_backup_dir(cwd)

            # Step 6 + 7: render loop with fast-path + atomic-write + chmod.
            files_processed = 0
            files_written = 0
            files_skipped = 0
            files_kept = 0
            errors: list[BootstrapError] = []
            new_entries: list[BootstrapManifestEntry] = []

            try:
                rendered_results = _render_loop(
                    cwd,
                    identity=resolved_identity,
                    targets=_selected_targets(refresh_paths),
                    existing_manifest=existing_manifest,
                    mode=mode,
                    backup_dir=backup_dir,
                )
            except (
                BootstrapPolicyError,
                InfrastructureRenderError,
                BootstrapManifestError,
            ) as exc:
                # Step 8 inversion: NO manifest write on partial render failure
                # (harden B16). Preserve the prior manifest's shas.
                _emit_telemetry(
                    repo_root,
                    _outcome_for(exc),
                    mode,
                    files_processed=0,
                    files_written=0,
                    files_skipped=0,
                    files_kept=0,
                )
                clear_sentinel(cwd)
                return BootstrapResult(
                    outcome=_outcome_for(exc),
                    mode=mode,
                    files_processed=0,
                    files_written=0,
                    files_skipped=0,
                    files_kept_user_edits=0,
                    errors=(
                        BootstrapError(
                            code=exc.reason,
                            path=exc.path,
                            remediation=exc.remediation,
                        ),
                    ),
                    warnings=tuple(warnings),
                    manifest_path=None,
                    backup_dir=backup_dir,
                    plugin_version=plugin_version,
                )

            for rec in rendered_results:
                files_processed += 1
                if rec.action == PolicyAction.WRITE:
                    files_written += 1
                elif rec.action == PolicyAction.OVERWROTE_WITH_BACKUP:
                    files_written += 1
                elif rec.action == PolicyAction.APPENDED:
                    files_written += 1
                elif rec.action == PolicyAction.MERGED:
                    files_written += 1
                elif rec.action == PolicyAction.SKIP_UNCHANGED:
                    files_skipped += 1
                elif rec.action == PolicyAction.KEPT_USER_EDITS:
                    files_kept += 1
                if rec.warnings:
                    warnings.extend(rec.warnings)
                if rec.entry is not None:
                    new_entries.append(rec.entry)

            # Step 8: write manifest atomically (LAST), full-run success only.
            manifest_path: Path | None = None
            if files_processed and refresh_paths is None:
                # Full-bootstrap path: rebuild manifest from current run.
                manifest = build_manifest(
                    plugin_version=plugin_version,
                    files=new_entries,
                )
                manifest_path = write_manifest(cwd, manifest)
            elif refresh_paths is not None and existing_manifest is not None:
                # Refresh subset: merge new entries onto existing manifest.
                merged_entries = _merge_manifest_entries(
                    existing_manifest,
                    new_entries,
                )
                manifest = build_manifest(
                    plugin_version=plugin_version,
                    files=merged_entries,
                )
                manifest_path = write_manifest(cwd, manifest)
            elif refresh_paths is not None and existing_manifest is None:
                # Refresh degraded to full bootstrap (harden A8).
                manifest = build_manifest(
                    plugin_version=plugin_version,
                    files=new_entries,
                )
                manifest_path = write_manifest(cwd, manifest)

            # Append warnings ledger if any new warnings surfaced.
            if warnings:
                _record_warnings_safe(cwd, list(warnings))

            # Step 9: clear sentinel.
            clear_sentinel(cwd)

            outcome: BootstrapOutcome = (
                "brownfield_auto_rendered" if mode == "brownfield-auto" else "success"
            )

            # Step 11: telemetry.
            _emit_telemetry(
                repo_root,
                outcome,
                mode,
                files_processed=files_processed,
                files_written=files_written,
                files_skipped=files_skipped,
                files_kept=files_kept,
            )

            # Step 12: return result.
            return BootstrapResult(
                outcome=outcome,
                mode=mode,
                files_processed=files_processed,
                files_written=files_written,
                files_skipped=files_skipped,
                files_kept_user_edits=files_kept,
                errors=tuple(errors),
                warnings=tuple(warnings),
                manifest_path=manifest_path,
                backup_dir=backup_dir,
                plugin_version=plugin_version,
            )
    except BootstrapEngineError as exc:
        clear_sentinel(cwd)
        _emit_telemetry(
            repo_root,
            _outcome_for(exc),
            mode,
            files_processed=0,
            files_written=0,
            files_skipped=0,
            files_kept=0,
        )
        return BootstrapResult(
            outcome=_outcome_for(exc),
            mode=mode,
            files_processed=0,
            files_written=0,
            files_skipped=0,
            files_kept_user_edits=0,
            errors=(
                BootstrapError(
                    code=exc.reason,
                    path=exc.path,
                    remediation=exc.remediation,
                ),
            ),
            warnings=tuple(warnings),
            manifest_path=None,
            backup_dir=backup_dir,
            plugin_version=plugin_version,
        )


# --- Render loop ----------------------------------------------------------


@dataclass(frozen=True)
class _RenderRecord:
    """Per-target outcome carried through the render loop."""

    action: PolicyAction
    target_relpath: str
    rendered_sha256: str
    entry: BootstrapManifestEntry | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RenderContext:
    """Per-target render state captured in Phase A and replayed in Phase C.

    Phase A renders + computes shas; Phase B scans the batch refuse-all-on-
    finding; Phase C policy-dispatches using the pre-rendered bytes. Holds
    everything the dispatch branches need so Phase C never re-renders.
    """

    template_relpath: str
    target_relpath: str
    target_path: Path
    policy: BootstrapPolicy
    file_mode: int
    rendered_bytes: bytes
    rendered_sha: str
    manifest_sha: str | None
    on_disk_sha: str | None


def _render_loop(
    cwd: Path,
    *,
    identity: Mapping[str, Any],
    targets: Iterable[tuple[str, str, BootstrapPolicy, int]],
    existing_manifest: BootstrapManifest | None,
    mode: BootstrapMode,
    backup_dir: Path | None,
) -> list[_RenderRecord]:
    """Three-phase render-then-scan-then-write loop.

    Phase A — render-collect (NO writes; refresh-mode included): build
    `rendered_batch: dict[Path, bytes]` plus a per-target `_RenderContext`
    capturing shas. Phase A is render-only; even refresh-mode's
    `write_backup_then_overwrite` MUST live in Phase C so a finding on a
    later target refuses-all writes including backups.

    Phase B — secret-scan gate: invoke `_RENDERER.scan_batch` and refuse
    every write on any finding. Fail-closed on scanner infra failure
    (OSError / UnicodeDecodeError / ValueError / re.error from a malformed
    user-supplied regex). `.is_file()` guards on `patterns_file` /
    `allowlist_path` so greenfield bootstrap (where the project-local
    secret-patterns.txt is itself one of the 30 render targets) falls
    through to bundled defaults via `None`.

    Phase C — policy dispatch: replay the per-target contexts; identical
    behavior to the prior single-pass loop except renders are reused.
    """
    refresh_modes = ("refresh", "refresh-all")

    # Phase A — render-collect. NO writes.
    contexts: list[_RenderContext] = []
    rendered_batch: dict[Path, bytes] = {}
    for template_relpath, target_relpath, policy, file_mode in targets:
        target_path = cwd / target_relpath
        rendered_bytes = _RENDERER.render_target(target_relpath, identity)
        rendered_batch[target_path] = rendered_bytes
        rendered_sha = sha256_bytes(rendered_bytes)
        manifest_sha = _entry_sha_for(existing_manifest, target_relpath)
        on_disk_sha: str | None = None
        if target_path.exists() and not target_path.is_symlink():
            on_disk_sha = sha256_file(target_path)
        contexts.append(
            _RenderContext(
                template_relpath=template_relpath,
                target_relpath=target_relpath,
                target_path=target_path,
                policy=policy,
                file_mode=file_mode,
                rendered_bytes=rendered_bytes,
                rendered_sha=rendered_sha,
                manifest_sha=manifest_sha,
                on_disk_sha=on_disk_sha,
            )
        )

    # Phase B — secret-scan gate. Refuse-all on finding; fail-closed on
    # scanner infra failure. `.is_file()` guards mirror lp_define_runner
    # scan_all:261-262 verbatim. `template_sources=None` matches the
    # /lp-define convention (Jinja-comment allowlists not used at the
    # bootstrap surface).
    patterns_file = cwd / ".launchpad" / "secret-patterns.txt"
    allowlist_path = cwd / ".launchpad" / "secret-allowlist.txt"
    try:
        findings = _RENDERER.scan_batch(
            rendered_batch,
            patterns_file=patterns_file if patterns_file.is_file() else None,
            allowlist_path=allowlist_path if allowlist_path.is_file() else None,
            template_sources=None,
        )
    except (OSError, UnicodeDecodeError, ValueError, re.error) as exc:
        # `re.error` is NOT a ValueError subclass (Python stdlib: inherits
        # from Exception directly), so it must be listed explicitly.
        # `type(exc).__name__` instead of `{exc}` keeps potentially
        # secret-shaped bytes from UnicodeDecodeError.args out of the
        # surfaced message.
        raise BootstrapEngineError(
            f"Secret scanner failed during /lp-bootstrap render: {type(exc).__name__}",
            reason=BootstrapErrorCode.SECRET_SCANNER_VIOLATION,
            path=cwd,
            remediation=(
                "Scanner infrastructure error; ALL writes refused. Verify "
                ".launchpad/secret-patterns.txt and "
                ".launchpad/secret-allowlist.txt are readable, then re-run."
            ),
        ) from exc
    if findings:
        # Normalize finding sources to repo-relative paths for cleaner
        # operator output. `cwd_abs = cwd.resolve()` upfront so a relative
        # cwd input (e.g. Path(".") from a CLI caller) does not fall
        # through the ValueError branch and leak absolute paths. Mirrors
        # lp_define_runner scan_all:267-271.
        cwd_abs = cwd.resolve()
        sources: set[str] = set()
        for f in findings:
            src = getattr(f, "source", None)
            if not src:
                continue
            try:
                sources.add(str(Path(src).resolve().relative_to(cwd_abs)))
            except ValueError:
                sources.add(src)
        raise BootstrapEngineError(
            f"Secret scanner found {len(findings)} match(es) across "
            f"{len(sources) or len(rendered_batch)} file(s) during render; "
            f"refused all {len(rendered_batch)} writes.",
            reason=BootstrapErrorCode.SECRET_SCANNER_VIOLATION,
            path=cwd,
            remediation=(
                "Inspect findings in the BootstrapResult.errors output and "
                "stderr; edit the offending source (template or identity "
                "field), and re-run /lp-bootstrap. Scanner patterns are "
                "configurable at .launchpad/secret-patterns.txt."
            ),
        )

    # Phase C — policy dispatch. Replays Phase A contexts; only place writes
    # happen.
    records: list[_RenderRecord] = []
    for ctx in contexts:
        target_relpath = ctx.target_relpath
        target_path = ctx.target_path
        policy = ctx.policy
        file_mode = ctx.file_mode
        rendered_bytes = ctx.rendered_bytes
        rendered_sha = ctx.rendered_sha
        manifest_sha = ctx.manifest_sha
        on_disk_sha = ctx.on_disk_sha

        # Refresh modes: skip the fast-path; force overwrite-with-backup.
        if mode in refresh_modes:
            assert backup_dir is not None
            policy_result = write_backup_then_overwrite(
                target=target_path,
                new_bytes=rendered_bytes,
                backup_dir=backup_dir,
                target_relpath=target_relpath,
                mode=file_mode,
                cwd=cwd,
            )
            try:
                os.chmod(target_path, file_mode)
            except OSError:
                pass
            entry = BootstrapManifestEntry(
                path=target_relpath,
                source_template_sha256=source_template_shas()[target_relpath],
                rendered_content_sha256=policy_result.rendered_sha256 or rendered_sha,
                policy=policy.value,
                mode=file_mode,
            )
            records.append(
                _RenderRecord(
                    action=policy_result.action,
                    target_relpath=target_relpath,
                    rendered_sha256=rendered_sha,
                    entry=entry,
                    warnings=tuple(policy_result.warnings),
                )
            )
            continue

        # Fast-path (harden A16): manifest_sha matches on_disk_sha matches
        # rendered_sha -> skip atomic write entirely. Brownfield-auto on
        # clean overlay drops 30 fsyncs to 0.
        if (
            manifest_sha is not None
            and on_disk_sha == manifest_sha
            and on_disk_sha == rendered_sha
        ):
            entry = BootstrapManifestEntry(
                path=target_relpath,
                source_template_sha256=source_template_shas()[target_relpath],
                rendered_content_sha256=rendered_sha,
                policy=policy.value,
                mode=file_mode,
            )
            records.append(
                _RenderRecord(
                    action=PolicyAction.SKIP_UNCHANGED,
                    target_relpath=target_relpath,
                    rendered_sha256=rendered_sha,
                    entry=entry,
                )
            )
            continue

        # Policy dispatch.
        if policy is BootstrapPolicy.OVERWRITE_IF_UNCHANGED:
            policy_result = apply_overwrite_if_unchanged(
                target=target_path,
                rendered_bytes=rendered_bytes,
                manifest_rendered_sha=manifest_sha,
                mode=file_mode,
                cwd=cwd,
            )
        elif policy is BootstrapPolicy.APPEND_ONLY:
            policy_result = apply_append_only(
                target=target_path,
                rendered_bytes=rendered_bytes,
                mode=file_mode,
                cwd=cwd,
            )
        elif policy is BootstrapPolicy.MERGE_KEYS:
            policy_result = apply_merge_keys(
                target=target_path,
                rendered_bytes=rendered_bytes,
                mode=file_mode,
                cwd=cwd,
                serializer=_serializer_for(target_relpath),
                yaml_dumper=_yaml_dumper,
            )
        else:
            raise BootstrapEngineError(
                f"engine invariant: unhandled policy {policy!r} for "
                f"target {target_relpath!r}",
                reason=BootstrapErrorCode.POLICY_COLLISION,
                path=target_path,
                remediation="this is a plugin defect; report it",
            )

        # Post-replace chmod (harden B8 belt-and-braces).
        if policy_result.action in (
            PolicyAction.WRITE,
            PolicyAction.APPENDED,
            PolicyAction.MERGED,
        ):
            try:
                os.chmod(target_path, file_mode)
            except OSError:
                pass

        if policy_result.action in (
            PolicyAction.WRITE,
            PolicyAction.APPENDED,
            PolicyAction.MERGED,
        ):
            stamped_sha = policy_result.rendered_sha256 or rendered_sha
        elif policy_result.action == PolicyAction.SKIP_UNCHANGED:
            stamped_sha = manifest_sha or rendered_sha
        else:  # KEPT_USER_EDITS
            stamped_sha = manifest_sha or rendered_sha

        entry = BootstrapManifestEntry(
            path=target_relpath,
            source_template_sha256=source_template_shas()[target_relpath],
            rendered_content_sha256=stamped_sha,
            policy=policy.value,
            mode=file_mode,
        )
        records.append(
            _RenderRecord(
                action=policy_result.action,
                target_relpath=target_relpath,
                rendered_sha256=rendered_sha,
                entry=entry,
                warnings=tuple(policy_result.warnings),
            )
        )

    return records


# --- Misc helpers ---------------------------------------------------------


def _manifest_sha(cwd: Path) -> str | None:
    """sha256 of the existing manifest file (for sentinel pre_edit field)."""
    target = cwd / LAUNCHPAD_DIR_NAME / "bootstrap-manifest.json"
    if not target.is_file():
        return None
    return sha256_file(target)


def _merge_manifest_entries(
    existing: BootstrapManifest,
    new: Sequence[BootstrapManifestEntry],
) -> list[BootstrapManifestEntry]:
    """Replace prior entries for refreshed paths; preserve untouched ones."""
    new_paths = {e.path for e in new}
    out = [e for e in existing.files if e.path not in new_paths]
    out.extend(new)
    return out


def _outcome_for(exc: Exception) -> BootstrapOutcome:
    code = getattr(exc, "reason", None)
    if code == BootstrapErrorCode.SENTINEL_BLOCKING:
        return "sentinel_blocked"
    if code == BootstrapErrorCode.MANIFEST_TAMPERED:
        return "manifest_tampered"
    if code == BootstrapErrorCode.MANIFEST_CORRUPT:
        return "manifest_corrupt"
    if code == BootstrapErrorCode.PLUGIN_VERSION_MISMATCH:
        return "plugin_version_mismatch"
    if code == BootstrapErrorCode.POLICY_COLLISION:
        return "policy_collision"
    return "render_failed"


_CANONICAL_OUTCOME_MAP: dict[BootstrapOutcome, str] = {
    "success": "completed",
    "brownfield_auto_rendered": "completed",
    "sentinel_blocked": "aborted",
    "plugin_version_mismatch": "aborted",
    "manifest_tampered": "aborted",
    "manifest_corrupt": "aborted",
    "policy_collision": "failed",
    "render_failed": "failed",
}


def _emit_telemetry(
    repo_root: Path,
    outcome: BootstrapOutcome,
    mode: BootstrapMode,
    *,
    files_processed: int,
    files_written: int,
    files_skipped: int,
    files_kept: int,
) -> None:
    """Append a structured event to `.harness/observations/v2-pipeline-*.jsonl`.

    Honors `telemetry: off` opt-out via the writer. Maps the engine's
    fine-grained `BootstrapOutcome` onto OPERATIONS section 5's canonical
    outcome enum (`completed`, `aborted`, `failed`, `accepted`, `rejected`)
    so cross-command analytics queries do not have to know the
    bootstrap-specific dialect; the original code rides through the
    `bootstrap_outcome` field for forensic detail.
    """
    payload = {
        "command": "lp-bootstrap",
        "mode": mode,
        "outcome": _CANONICAL_OUTCOME_MAP.get(outcome, "failed"),
        "bootstrap_outcome": outcome,
        "files_processed": files_processed,
        "files_written": files_written,
        "files_skipped": files_skipped,
        "files_kept_user_edits": files_kept,
    }
    try:
        write_telemetry_entry(repo_root, payload)
    except Exception:  # noqa: BLE001
        # Telemetry is best-effort; never block the bootstrap on it.
        pass


def _record_warnings_safe(cwd: Path, warnings: list[str]) -> None:
    """Best-effort warning-ledger append; never raises."""
    try:
        record_warnings(cwd, warnings)
    except Exception:  # noqa: BLE001
        pass


__all__ = [
    "BootstrapEngineError",
    "BootstrapMode",
    "BootstrapOutcome",
    "BootstrapResult",
    "run_bootstrap",
]
