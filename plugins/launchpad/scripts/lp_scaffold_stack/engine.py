"""Top-level /lp-scaffold-stack consumer pipeline (Phase 3 §4.1).

Coordinates Steps 0-5c into a single `run_pipeline()` entrypoint:

  Step 0  — Pre-validation greenfield gate + marker presence check
  Step 1  — Decision file load + 13-rule validation (rule 12 BL-235 deferred)
  Step 2  — Marker consumption (simple os.rename)
  Step 3  — Layer materialization (orchestrate vs curate dispatch)
  Step 4  — Cross-cutting wiring (pnpm-workspace.yaml/turbo.json/lefthook.yml
            + secret-scan)
  Step 5a — Receipt write (atomic O_CREAT|O_EXCL + sha256 self-hash)
  Step 5b — Nonce ledger append (AFTER receipt fsync per HANDSHAKE §4 rule 10)
  Step 5c — Telemetry

Failure paths:

  - Step 1 rejection → emit scaffold-rejection-<ts>.jsonl; outcome=aborted
  - Step 3 partial materialization → emit scaffold-failed-<ts>.json;
    outcome=failed (per gate #11 — nonce NOT consumed; materialized files
    of prior successful layers REMAIN; no auto-cleanup)
  - Step 4 collision → emit scaffold-failed-<ts>.json with reason
    `cross_cutting_wiring_collision`
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

# Sibling-script imports.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import refuse_if_not_greenfield  # noqa: E402
from telemetry_writer import write_telemetry_entry  # noqa: E402

from lp_scaffold_stack import EXPECTED_DECISION_VERSION  # noqa: E402
from lp_scaffold_stack.cleanup_recorder import (  # noqa: E402
    CleanupRecordError,
    write_scaffold_failed,
)
from lp_scaffold_stack.cross_cutting_wirer import (  # noqa: E402
    CrossCuttingError,
    wire_cross_cutting,
)
from lp_scaffold_stack.decision_validator import (  # noqa: E402
    Accepted,
    Rejected,
    validate_decision,
)
from lp_scaffold_stack.dispatch_enumeration import enumerate_files  # noqa: E402
from lp_scaffold_stack.marker_consumer import (  # noqa: E402
    consume_marker,
    marker_present,
)
from lp_scaffold_stack.nonce_ledger import (  # noqa: E402
    NonceLedgerError,
    append_nonce,
    is_nonce_seen,
)
from lp_scaffold_stack.receipt_writer import (  # noqa: E402
    LayerReceiptEntry,
    ReceiptBuildError,
    ReceiptWriteError,
    write_receipt,
)
from lp_scaffold_stack.rejection_logger import write_rejection  # noqa: E402
from lp_scaffold_stack.v21_adapter_dispatch import (  # noqa: E402
    dispatch_by_stack_ids,
    fallback_ids_used,
)
from plugin_stack_adapters.composition import (  # noqa: E402
    CompositionAbortError,
)
from plugin_stack_adapters.contracts import (  # noqa: E402
    ScaffoldStepFailedError,
)


# v2.1.0 completion plan §3.3: legacy `RunInvoker` typed against the
# deleted `layer_materializer.materialize_layer`. The kwarg is kept on
# `run_pipeline` for callers that pass `run_invoker=None`; v2.2 BL-281
# removes it entirely.
RunInvoker = Any

COMMAND_NAME = "/lp-scaffold-stack"

# Default catalog/pattern paths (may be overridden in tests). Path arithmetic:
# this file is at plugins/launchpad/scripts/lp_scaffold_stack/engine.py, so
# parents[0..4] are lp_scaffold_stack / scripts / launchpad / plugins / repo
# root. The repo root is parents[4]; previous parents[3] resolved to plugins/
# which produced `plugins/plugins/launchpad/...` for the catalog defaults
# (PR #41 cycle 4 #1 — silent default-args ship-blocker since fc5b3da).
_REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[4]
DEFAULT_SCAFFOLDERS_YML = _REPO_ROOT_DEFAULT / "plugins" / "launchpad" / "scaffolders.yml"
DEFAULT_CATEGORY_PATTERNS_YML = (
    _REPO_ROOT_DEFAULT / "plugins" / "launchpad" / "scripts"
    / "lp_pick_stack" / "data" / "category-patterns.yml"
)
DEFAULT_PLUGINS_ROOT = _REPO_ROOT_DEFAULT


class Outcome:
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class PipelineResult:
    """Structured result of a `run_pipeline()` invocation.

    v2.1.0 completion plan §3.6: `layers_materialized` is now
    `list[LayerReceiptEntry]` (TypedDict) — the deleted
    `MaterializationResult` dataclass no longer exists. Field shape is
    preserved (caller-side dict construction); only the type flips.
    """

    success: bool
    outcome: str  # one of Outcome.{COMPLETED, FAILED, ABORTED}
    receipt_path: Path | None = None
    decision_path: Path | None = None
    rejection_log_path: Path | None = None
    failed_record_path: Path | None = None
    nonce_consumed: bool = False
    layers_materialized: list[LayerReceiptEntry] = field(default_factory=list)
    reason: str | None = None
    message: str | None = None
    failed_layer_index: int | None = None
    elapsed_seconds: float = 0.0
    install_seconds: float | None = None
    secret_scan_passed: bool | None = None


def _utc_iso_sec() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_yaml(path: Path) -> dict:
    """yaml.safe_load with vendor-bootstrap (matches lp_pick_stack/engine.py)."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "pyyaml is required for /lp-scaffold-stack. Install with: "
            "`pip install -r plugins/launchpad/scripts/requirements.txt` "
            "(pinned version lives in plugins/launchpad/scripts/_vendor/PYYAML_VERSION)."
        ) from exc
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_scaffolders(path: Path) -> dict[str, dict]:
    raw = _load_yaml(path)
    return dict(raw.get("stacks") or {})


def _load_category_ids(path: Path) -> set[str]:
    raw = _load_yaml(path)
    cats = raw.get("categories") or []
    return {c["id"] for c in cats if isinstance(c, dict) and "id" in c}


def _read_decision(path: Path) -> dict | None:
    """Read + parse `.launchpad/scaffold-decision.json`. Returns the dict on
    success or None on parse failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _decision_sha256_from_file(path: Path) -> str:
    """Compute the sha256 of the on-disk decision-file bytes (verbatim).

    The receipt's `decision_sha256` field per HANDSHAKE §5 references the
    INPUT file's bytes (chain-of-custody back to pick-stack). We hash the
    raw bytes here, not canonical_hash(payload) — those are different by
    design (the file already IS the canonical form, but if a future change
    introduces whitespace differences, the receipt should pin the bytes).
    """
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _emit_telemetry(
    repo_root: Path,
    *,
    outcome: str,
    elapsed_seconds: float,
    cwd_state_value: str | None = "empty",
    install_seconds: float | None = None,
    secret_scan_passed: bool | None = None,
    reason: str | None = None,
    failed_layer_index: int | None = None,
) -> None:
    payload: dict[str, Any] = {
        "command": COMMAND_NAME,
        "outcome": outcome,
        "time_seconds": round(elapsed_seconds, 3),
    }
    if cwd_state_value is not None:
        payload["cwd_state"] = cwd_state_value
    if install_seconds is not None:
        payload["install_seconds"] = round(install_seconds, 3)
    if secret_scan_passed is not None:
        payload["secret_scan_passed"] = secret_scan_passed
    if reason is not None:
        payload["reason"] = reason
    if failed_layer_index is not None:
        payload["failed_layer_index"] = failed_layer_index
    try:
        write_telemetry_entry(repo_root, payload)
    except Exception:
        pass  # analytics, not forensic — never propagate


def _emit_rejection(
    repo_root: Path,
    rejected: Rejected,
    *,
    stderr=None,
) -> Path | None:
    """Forward a `Rejected` verdict to the forensic logger.

    Per 2026-05-08-v2.1.0-completion-plan.md §3.1: `rejected.message` is
    now propagated into the JSON payload (cycle-3 fix — pre-cycle the
    message landed nowhere user-visible). The same payload shape is
    asserted parity-equivalent with `_record_partial_failure`'s
    Outcome.ABORTED path so validator-rejection and dispatch-failure
    surfaces emit identical user-facing copy.
    """
    return write_rejection(
        repo_root,
        reason=rejected.reason,
        message=rejected.message,
        field_name=rejected.field_name,
        seen_version=rejected.seen_version,
        extra=dict(rejected.extra) if rejected.extra else None,
        stderr=stderr,
    )


def run_pipeline(
    cwd: Path,
    *,
    decision_file_path: Path | None = None,
    scaffolders_yml: Path | None = None,
    category_patterns_yml: Path | None = None,
    plugins_root: Path | None = None,
    expected_versions: frozenset[str] = EXPECTED_DECISION_VERSION,
    skip_greenfield_gate: bool = False,
    write_telemetry_flag: bool = True,
    run_invoker: RunInvoker | None = None,
    stderr=None,
    repo_root: Path | None = None,
    _now_epoch: float | None = None,
    accept_v22_fallback: bool = False,
) -> PipelineResult:
    """Execute the 8-step scaffold-stack pipeline.

    Returns a PipelineResult; the engine never raises for expected refusal
    paths, instead returning `success=False` with a `reason` tag the
    markdown command surfaces. Programming errors propagate.

    `repo_root` defaults to `cwd` (consumer-project model). Tests that
    want to materialize into a tmp_path while reading scaffolders.yml from
    the LaunchPad repo can override `plugins_root` separately.

    `run_invoker`: layer materializer's safe_run override (gate #11 hook).
    """
    start = time.monotonic()
    cwd = Path(cwd)
    repo_root = repo_root if repo_root is not None else cwd
    plugins_root = plugins_root if plugins_root is not None else DEFAULT_PLUGINS_ROOT
    scaffolders_yml = scaffolders_yml or DEFAULT_SCAFFOLDERS_YML
    category_patterns_yml = category_patterns_yml or DEFAULT_CATEGORY_PATTERNS_YML

    # --- Step 0: greenfield gate ---
    # Recovery exception: if a previous scaffold attempt left a partial-
    # cleanup record (`.launchpad/scaffold-failed-*.json`) AND the original
    # decision file is still present, allow the rerun even if cwd_state()
    # now reports brownfield (any manifest the failed scaffolder created
    # would tip the classifier). This preserves the documented recovery
    # contract ("rerun /lp-scaffold-stack with the same decision after
    # failure") which the strict greenfield gate would otherwise refuse
    # (PR #41 cycle 5 #2 — closes self-contradicting recovery flow).
    if not skip_greenfield_gate:
        recovery_record = next(
            (cwd / ".launchpad").glob("scaffold-failed-*.json"), None
        ) if (cwd / ".launchpad").is_dir() else None
        decision_present = (cwd / ".launchpad" / "scaffold-decision.json").is_file()
        in_recovery_mode = recovery_record is not None and decision_present

        if not in_recovery_mode:
            try:
                refuse_if_not_greenfield(cwd, COMMAND_NAME)
            except (RuntimeError, NotADirectoryError) as exc:
                elapsed = time.monotonic() - start
                reason = ("cwd_state_brownfield" if "brownfield" in str(exc)
                          else "cwd_state_ambiguous")
                rej = Rejected(reason=reason, message=str(exc), field_name="cwd")
                log_path = _emit_rejection(repo_root, rej, stderr=stderr)
                result = PipelineResult(
                    success=False,
                    outcome=Outcome.ABORTED,
                    reason=reason,
                    message=str(exc),
                    rejection_log_path=log_path,
                    elapsed_seconds=elapsed,
                )
                if write_telemetry_flag:
                    _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                                    elapsed_seconds=elapsed,
                                    cwd_state_value=None, reason=reason)
                return result

    # --- Step 1a: decision file load + JSON parse ---
    decision_path = decision_file_path if decision_file_path is not None \
        else (cwd / ".launchpad" / "scaffold-decision.json")
    if not decision_path.exists():
        elapsed = time.monotonic() - start
        rej = Rejected(
            reason="scaffold_decision_missing",
            message=f"{decision_path} does not exist; run /lp-pick-stack first",
            field_name="scaffold-decision.json",
        )
        log_path = _emit_rejection(repo_root, rej, stderr=stderr)
        result = PipelineResult(
            success=False, outcome=Outcome.ABORTED,
            reason=rej.reason, message=rej.message,
            rejection_log_path=log_path, elapsed_seconds=elapsed,
        )
        if write_telemetry_flag:
            _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                            elapsed_seconds=elapsed, reason=rej.reason)
        return result
    decision = _read_decision(decision_path)
    if decision is None:
        elapsed = time.monotonic() - start
        rej = Rejected(
            reason="scaffold_decision_invalid_json",
            message=f"could not parse {decision_path} as JSON",
            field_name="scaffold-decision.json",
        )
        log_path = _emit_rejection(repo_root, rej, stderr=stderr)
        result = PipelineResult(
            success=False, outcome=Outcome.ABORTED,
            reason=rej.reason, message=rej.message,
            rejection_log_path=log_path, elapsed_seconds=elapsed,
        )
        if write_telemetry_flag:
            _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                            elapsed_seconds=elapsed, reason=rej.reason)
        return result

    # --- Step 1b: 12-of-13 rule validation (rule 12 deferred) ---
    try:
        scaffolders = _load_scaffolders(scaffolders_yml)
        category_ids = _load_category_ids(category_patterns_yml)
    except (OSError, ValueError) as exc:
        elapsed = time.monotonic() - start
        rej = Rejected(
            reason="catalog_load_failed",
            message=f"could not load scaffolders/category catalog: {exc}",
            field_name="scaffolders.yml",
        )
        log_path = _emit_rejection(repo_root, rej, stderr=stderr)
        result = PipelineResult(
            success=False, outcome=Outcome.ABORTED,
            reason=rej.reason, message=rej.message,
            rejection_log_path=log_path, elapsed_seconds=elapsed,
        )
        if write_telemetry_flag:
            _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                            elapsed_seconds=elapsed, reason=rej.reason)
        return result

    # Pre-resolve nonce-ledger lookup (filesystem-touching; outside the
    # validator's pure-CPU scope).
    try:
        nonce_value = decision.get("nonce", "")
        seen = (
            isinstance(nonce_value, str)
            and len(nonce_value) == 32
            and all(c in "0123456789abcdef" for c in nonce_value)
            and is_nonce_seen(nonce_value, repo_root, _now_epoch=_now_epoch)
        )
    except NonceLedgerError as exc:
        elapsed = time.monotonic() - start
        rej = Rejected(reason=exc.reason, message=str(exc), field_name="nonce")
        log_path = _emit_rejection(repo_root, rej, stderr=stderr)
        result = PipelineResult(
            success=False, outcome=Outcome.ABORTED,
            reason=rej.reason, message=rej.message,
            rejection_log_path=log_path, elapsed_seconds=elapsed,
        )
        if write_telemetry_flag:
            _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                            elapsed_seconds=elapsed, reason=rej.reason)
        return result

    rationale_path = cwd / ".launchpad" / "rationale.md"
    rationale_for_sha = rationale_path if rationale_path.exists() else None

    verdict = validate_decision(
        decision,
        cwd,
        scaffolders=scaffolders,
        category_ids=category_ids,
        nonce_seen=seen,
        rationale_path_for_sha=rationale_for_sha,
        expected_versions=expected_versions,
    )
    if isinstance(verdict, Rejected):
        elapsed = time.monotonic() - start
        log_path = _emit_rejection(repo_root, verdict, stderr=stderr)
        result = PipelineResult(
            success=False, outcome=Outcome.ABORTED,
            reason=verdict.reason, message=verdict.message,
            rejection_log_path=log_path, decision_path=decision_path,
            elapsed_seconds=elapsed,
        )
        if write_telemetry_flag:
            _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                            elapsed_seconds=elapsed, reason=verdict.reason)
        return result

    accepted: Accepted = verdict
    layers = list(accepted.payload["layers"])
    # v2.1.0 completion plan §3.3: dispatch consumes `decision["stacks"]`
    # (the v2.1 schema field) while `layers` stays for `wire_cross_cutting`
    # toolchain detection. `derive_stacks` populates stacks from layers at
    # /lp-pick-stack write time; `decision_validator._validate_v1_1_envelope`
    # gates membership in STACK_ID_ACTIVE_ENUM.
    stacks = list(accepted.payload.get("stacks") or [])

    # --- Step 2: marker consumption (best-effort, no hard error on miss) ---
    if marker_present(repo_root):
        consume_marker(repo_root)

    # --- Sentinel acquisition (before any filesystem materialization) ---
    # Prevents concurrent /lp-scaffold-stack invocations from both passing
    # the greenfield gate and dispatching adapters in parallel. Bidirectional
    # cross-detect in lp_bootstrap._sentinel_preflight and
    # lp_update_identity._validate_preconditions reads this sentinel and
    # refuses on a live PID.
    from lp_scaffold_stack.sentinel import (  # noqa: PLC0415
        clear_sentinel as _scaffold_stack_clear_sentinel,
        write_sentinel as _scaffold_stack_write_sentinel,
    )
    try:
        _scaffold_stack_write_sentinel(cwd, mode="scaffold-stack")
    except FileExistsError:
        elapsed = time.monotonic() - start
        rej = Rejected(
            reason="scaffold_stack_in_progress",
            message=(
                "another /lp-scaffold-stack appears to be running "
                "(.launchpad/.scaffold-stack-in-progress exists). If "
                "certain no other invocation is active, remove the "
                "sentinel manually after confirming no live PID."
            ),
            field_name=".scaffold-stack-in-progress",
        )
        log_path = _emit_rejection(repo_root, rej, stderr=stderr)
        result = PipelineResult(
            success=False, outcome=Outcome.ABORTED,
            reason=rej.reason, message=rej.message,
            rejection_log_path=log_path, decision_path=decision_path,
            elapsed_seconds=elapsed,
        )
        if write_telemetry_flag:
            _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                            elapsed_seconds=elapsed, reason=rej.reason)
        return result

    try:
        # --- Step 3: v2.1 adapter-protocol dispatch ---
        layer_paths: dict[str, str] = {}
        for layer in layers:
            lid = layer.get("stack")
            lpath = layer.get("path")
            if lid and lpath:
                layer_paths[lid] = lpath

        install_start = time.monotonic()
        install_seconds = 0.0
        try:
            dispatch_result = dispatch_by_stack_ids(
                stacks, cwd,
                accept_v22_fallback=accept_v22_fallback,
                layer_paths=layer_paths or None,
            )
        except (ScaffoldStepFailedError, CompositionAbortError) as exc:
            elapsed = time.monotonic() - start
            if isinstance(exc, CompositionAbortError):
                recovery_path = str(getattr(exc, "path", None) or cwd)
            else:
                recovery_path = (
                    str(exc.path) if exc.path is not None
                    else f"<adapter dispatch for stacks={stacks!r}>"
                )
            return _record_partial_failure(
                repo_root=repo_root,
                decision_path=decision_path,
                materialized_files=[],
                failed_layer_index=None,
                reason=exc.reason,
                message=exc.remediation,
                elapsed=elapsed,
                install_seconds=time.monotonic() - install_start,
                write_telemetry_flag=write_telemetry_flag,
                recovery_action=(
                    f"Adapter dispatch failed for stacks={stacks!r}. The "
                    f"composition layer's existing rmtree-with-backup-and-"
                    f"restore (per composition._rollback) cleans placed_paths "
                    f"on its own failure path; for single-adapter "
                    f"ScaffoldStepFailedError, inspect the partial workspace "
                    f"at {recovery_path} and address the underlying cause "
                    f"before re-running."
                ),
                recovery_layer_path=recovery_path,
            )

        materialized_files = enumerate_files(cwd, dispatch_result)
        install_seconds = time.monotonic() - install_start

        # --- Step 4: cross-cutting wiring + secret-scan ---
        try:
            wiring = wire_cross_cutting(cwd, layers, materialized_files)
        except CrossCuttingError as exc:
            elapsed = time.monotonic() - start
            partial_cross_cutting = getattr(exc, "cross_cutting_files_written", []) or []
            return _record_partial_failure(
                repo_root=repo_root,
                decision_path=decision_path,
                materialized_files=materialized_files,
                failed_layer_index=None,
                reason="cross_cutting_wiring_collision",
                message=str(exc),
                elapsed=elapsed,
                install_seconds=install_seconds,
                write_telemetry_flag=write_telemetry_flag,
                cross_cutting_files=list(partial_cross_cutting) or None,
                recovery_action=(
                    "Cross-cutting wiring (pnpm-workspace.yaml / turbo.json / "
                    "lefthook.yml) collided with existing files. Resolve the "
                    "collision and re-run /lp-scaffold-stack."
                ),
            )

        if not wiring.secret_scan_passed:
            elapsed = time.monotonic() - start
            return _record_partial_failure(
                repo_root=repo_root,
                decision_path=decision_path,
                materialized_files=materialized_files,
                failed_layer_index=None,
                reason="secret_scan_failed",
                message=f"secret-scan findings: {wiring.secret_scan_findings}",
                elapsed=elapsed,
                install_seconds=install_seconds,
                write_telemetry_flag=write_telemetry_flag,
                cross_cutting_files=list(wiring.cross_cutting_files),
                recovery_action=(
                    "Secret-scan flagged content in materialized files. Investigate "
                    "the findings, remove sensitive material, and re-run."
                ),
            )

        return _run_pipeline_after_sentinel(
            cwd=cwd,
            repo_root=repo_root,
            decision_path=decision_path,
            accepted=accepted,
            layers=layers,
            stacks=stacks,
            materialized_files=materialized_files,
            wiring=wiring,
            install_seconds=install_seconds,
            start=start,
            stderr=stderr,
            write_telemetry_flag=write_telemetry_flag,
            accept_v22_fallback=accept_v22_fallback,
        )
    finally:
        _scaffold_stack_clear_sentinel(cwd)


def _run_pipeline_after_sentinel(
    *,
    cwd: Path,
    repo_root: Path,
    decision_path: Path,
    accepted: Accepted,
    layers: list,
    stacks: list[str],
    materialized_files: list[str],
    wiring,
    install_seconds: float,
    start: float,
    stderr,
    write_telemetry_flag: bool,
    accept_v22_fallback: bool,
) -> PipelineResult:
    """Steps 4.5 through 5b, executed inside the scaffold-stack sentinel.

    Extracted from `run_pipeline` for readability. Steps 3-4 (dispatch +
    cross-cutting) are also inside the sentinel-protected try/finally in
    `run_pipeline`, so the full sentinel window covers Steps 3 through 5b.
    """
    # --- Step 4.5: Kernel render (v1.1 envelopes only) ---
    # V3 plan §17.1 Phase 2: render the 7 stack-agnostic identity-bearing
    # kernel files (LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, README,
    # SECURITY, AGENTS, CLAUDE) into the project root using the sealed
    # identity from scaffold-decision.json. Silent no-op for legacy v1.0
    # envelopes (no identity field; would render placeholder-only files
    # for no benefit).
    #
    # Lazy-import so engine consumers that never reach this step do not
    # pull jinja2 in transitively.
    if accepted.payload.get("schema_version") == "1.1":
        identity = accepted.payload.get("identity")
        if isinstance(identity, dict):
            from plugin_default_generators.kernel_renderer import (  # noqa: PLC0415
                KernelRenderer,
            )
            try:
                _rendered, kernel_render_state = KernelRenderer().render_all(
                    cwd, identity,
                )
            except Exception as exc:  # noqa: BLE001
                elapsed = time.monotonic() - start
                return _record_partial_failure(
                    repo_root=repo_root,
                    decision_path=decision_path,
                    materialized_files=materialized_files,
                    failed_layer_index=None,
                    reason="kernel_render_failed",
                    message=f"kernel render failed: {exc}",
                    elapsed=elapsed,
                    install_seconds=install_seconds,
                    write_telemetry_flag=write_telemetry_flag,
                    cross_cutting_files=list(wiring.cross_cutting_files),
                    recovery_action=(
                        "Kernel render (LICENSE / CONTRIBUTING / etc.) failed. "
                        "Inspect the error, fix the underlying cause, and re-run."
                    ),
                )

            # Phase 1+2 retroactive amendment A7: seal kernel_render_state
            # into scaffold-decision.json from the caller side. Best-effort
            # narrow-exception catch with WARN; primary contract is the
            # kernel batch landing on disk.
            try:
                from lp_pick_stack.decision_writer import (  # noqa: PLC0415
                    re_seal_decision_atomic,
                )
                from lp_scaffold_stack.decision_validator import (  # noqa: PLC0415
                    mark_kernel_seeded,
                )

                # v2.1 Codex PR #50 P1.3 (D9.2): route through the
                # mark_kernel_seeded() single-owner helper so the ratchet
                # keys (kernel_seed_pending, migration_origin_sha256) are
                # canonically stripped on every re-seal. Replaces the
                # earlier inline `payload["kernel_render_state"] = ...`
                # mutation.
                def _seal_kernel_render_state(payload: dict) -> None:
                    sealed = mark_kernel_seeded(payload, kernel_render_state)
                    payload.clear()
                    payload.update(sealed)

                re_seal_decision_atomic(cwd, update_fn=_seal_kernel_render_state)
            except (OSError, json.JSONDecodeError, ValueError) as seal_exc:
                print(
                    f"WARN: re-seal of scaffold-decision.json failed: "
                    f"{seal_exc}; kernel files were rendered successfully "
                    f"but render-state bookkeeping is stale. Run "
                    f"/lp-update-identity to re-seal.",
                    file=sys.stderr,
                )

            # --- Step 4.6: Bootstrap (Phase 3 §2.3 wiring) ---
            # Materialize the v2.1 30-path infrastructure overlay via
            # `/lp-bootstrap` engine. Greenfield mode renders all 30 paths;
            # the bootstrap-manifest is written atomically at the end of
            # the loop and seeds Phase 4 adapter overlays + Phase 10
            # /lp-update-identity refresh paths.
            from lp_bootstrap.engine import run_bootstrap  # noqa: PLC0415
            from lp_bootstrap import (  # noqa: PLC0415
                BootstrapError,
                BootstrapErrorCode,
            )
            bootstrap_result = run_bootstrap(
                cwd, mode="greenfield", identity=identity,
            )
            if bootstrap_result.outcome != "success":
                elapsed = time.monotonic() - start
                err = (
                    bootstrap_result.errors[0]
                    if bootstrap_result.errors
                    else BootstrapError(
                        code=BootstrapErrorCode.TEMPLATE_RENDER_FAILED,
                        path=None,
                        remediation="see /lp-bootstrap output above",
                    )
                )
                return _record_partial_failure(
                    repo_root=repo_root,
                    decision_path=decision_path,
                    materialized_files=materialized_files,
                    failed_layer_index=None,
                    reason="bootstrap_failed",
                    message=(
                        f"infrastructure bootstrap failed "
                        f"(outcome={bootstrap_result.outcome}, "
                        f"code={err.code.value}): {err.remediation}"
                    ),
                    elapsed=elapsed,
                    install_seconds=install_seconds,
                    write_telemetry_flag=write_telemetry_flag,
                    cross_cutting_files=list(wiring.cross_cutting_files),
                    recovery_action=(
                        "Infrastructure bootstrap failed. Inspect the error "
                        "above and re-run /lp-scaffold-stack after the "
                        "underlying cause is fixed."
                    ),
                )

    # --- Step 5a: receipt write ---
    # v2.1.0 completion plan §3.5/§3.6: receipt entries are built from
    # `layers` (validated), the post-dispatch enumeration, and the
    # `_resolve_adapter_id_for` helper that maps each layer's stack to
    # the adapter that actually rendered it (with fallback awareness).
    layer_entries: list[LayerReceiptEntry] = _build_layer_receipt_entries(
        layers, materialized_files, accept_v22_fallback=accept_v22_fallback,
    )
    fallback_ids = fallback_ids_used(
        stacks, accept_v22_fallback=accept_v22_fallback,
    )
    adapter_dispatch_meta = (
        {"fallback_ids": fallback_ids} if fallback_ids else None
    )
    decision_bytes_sha = _decision_sha256_from_file(decision_path)
    try:
        receipt_path, _sealed = write_receipt(
            decision_sha256=decision_bytes_sha,
            decision_nonce=accepted.nonce,
            layers_materialized=layer_entries,
            cross_cutting_files=wiring.cross_cutting_files,
            toolchains_detected=wiring.toolchains_detected,
            secret_scan_passed=wiring.secret_scan_passed,
            cwd=cwd,
            adapter_dispatch_meta=adapter_dispatch_meta,
        )
    except (ReceiptWriteError, ReceiptBuildError) as exc:
        elapsed = time.monotonic() - start
        rej = Rejected(reason=exc.reason, message=str(exc),
                       field_name="scaffold-receipt.json")
        log_path = _emit_rejection(repo_root, rej, stderr=stderr)
        result = PipelineResult(
            success=False, outcome=Outcome.ABORTED,
            reason=exc.reason, message=str(exc),
            rejection_log_path=log_path, decision_path=decision_path,
            layers_materialized=layer_entries, elapsed_seconds=elapsed,
        )
        if write_telemetry_flag:
            _emit_telemetry(repo_root, outcome=Outcome.ABORTED,
                            elapsed_seconds=elapsed, reason=exc.reason)
        return result

    # --- Step 5b: nonce ledger append (AFTER receipt fsync) ---
    nonce_appended = True
    try:
        append_nonce(accepted.nonce, repo_root)
    except NonceLedgerError as exc:
        # Receipt was already written; the nonce-append failure is a
        # non-fatal surface here (receipt fsync is the chain-of-custody
        # commit point per Layer 4 P1-4 + gate #11 partial-cleanup contract).
        # We log to rejection but mark success — the user has a valid receipt;
        # they will not be able to re-run pick-stack with the same nonce
        # because the matched receipt already pins it.
        # Note: the failure mode is rare (only on EROFS / corrupt ledger
        # AFTER a clean receipt write).
        rej = Rejected(reason=exc.reason, message=str(exc), field_name="nonce-ledger")
        _emit_rejection(repo_root, rej, stderr=stderr)
        # nonce_consumed reports whether the LEDGER was actually updated.
        # Receipt-based replay protection still holds, but callers checking
        # this field for retry/cleanup decisions need accurate state
        # (PR #41 cycle 5 / Greptile cycle-1 G-A — closes nonce_consumed
        # misreport when the ledger append fails post-receipt).
        nonce_appended = False
        # Continue — receipt is the load-bearing artifact.

    elapsed = time.monotonic() - start
    result = PipelineResult(
        success=True,
        outcome=Outcome.COMPLETED,
        receipt_path=receipt_path,
        decision_path=decision_path,
        nonce_consumed=nonce_appended,
        layers_materialized=layer_entries,
        elapsed_seconds=elapsed,
        install_seconds=install_seconds,
        secret_scan_passed=wiring.secret_scan_passed,
    )
    if write_telemetry_flag:
        _emit_telemetry(
            repo_root,
            outcome=Outcome.COMPLETED,
            elapsed_seconds=elapsed,
            install_seconds=install_seconds,
            secret_scan_passed=wiring.secret_scan_passed,
        )
    return result


def _record_partial_failure(
    *,
    repo_root: Path,
    decision_path: Path,
    materialized_files: list[str],
    failed_layer_index: int | None,
    reason: str,
    message: str,
    elapsed: float,
    install_seconds: float,
    write_telemetry_flag: bool,
    recovery_action: str,
    recovery_layer_path: str | None = None,
    cross_cutting_files: list[str] | None = None,
) -> PipelineResult:
    """Common scaffold-failed emission path used by Step 3 + Step 4 errors.

    v2.1.0 completion plan §3.5: takes `materialized_files: list[str]`
    (the post-dispatch enumeration) instead of the deleted
    `MaterializationResult` dataclass list. Caller-side construction of
    layer-receipt entries is unnecessary on the failure path — the
    recovery record only needs the materialized file list.

    `cross_cutting_files` (lefthook.yml + optional pnpm-workspace.yaml /
    turbo.json) MUST be passed when the failure happened AFTER
    wire_cross_cutting() succeeded — those files are already on disk and a
    rerun would collide on them unless the recovery record names them
    (PR #41 cycle 5 #3 — closes secret-scan-failure-recovery-collision gap).
    """
    if cross_cutting_files:
        materialized_files = materialized_files + list(cross_cutting_files)
    recovery_commands: list[dict] = []
    if recovery_layer_path and recovery_layer_path != ".":
        recovery_commands.append({"op": "rmdir_recursive", "path": recovery_layer_path})
    recovery_commands.append({"op": "rerun", "command": "/lp-scaffold-stack"})

    failed_path: Path | None = None
    try:
        failed_path, _payload = write_scaffold_failed(
            reason=reason,
            failed_layer_index=failed_layer_index,
            materialized_files=materialized_files,
            recovery_commands=recovery_commands,
            recommended_recovery_action=recovery_action,
            repo_root=repo_root,
        )
    except CleanupRecordError as exc:
        # Write-time validation tripped (e.g., recovery_layer_path was a
        # destructive path). Drop the recovery_commands array to the minimum
        # safe shape (a single rerun) and retry.
        try:
            failed_path, _payload = write_scaffold_failed(
                reason=reason,
                failed_layer_index=failed_layer_index,
                materialized_files=materialized_files,
                recovery_commands=[{"op": "rerun", "command": "/lp-scaffold-stack"}],
                recommended_recovery_action=recovery_action + " (auto-stripped poisonous recovery_commands entries)",
                repo_root=repo_root,
            )
        except CleanupRecordError:
            failed_path = None

    if write_telemetry_flag:
        _emit_telemetry(
            repo_root,
            outcome=Outcome.FAILED,
            elapsed_seconds=elapsed,
            install_seconds=install_seconds,
            reason=reason,
            failed_layer_index=failed_layer_index,
        )
    return PipelineResult(
        success=False,
        outcome=Outcome.FAILED,
        reason=reason,
        message=message,
        decision_path=decision_path,
        failed_record_path=failed_path,
        layers_materialized=[],
        failed_layer_index=failed_layer_index,
        elapsed_seconds=elapsed,
        install_seconds=install_seconds,
    )


def _build_layer_receipt_entries(
    layers: list,
    materialized_files: list[str],
    *,
    accept_v22_fallback: bool,
) -> list[LayerReceiptEntry]:
    """v2.1.0 completion plan §3.6: caller-side construction of receipt
    `layers_materialized` entries from validated `layers` + the
    post-dispatch enumeration.

    Each layer's `files_created` is the materialized_files filtered by
    its `path` prefix (most-specific path wins). Files outside any
    declared layer path land in the FIRST layer as a catch-all so the
    receipt schema's "every entry has non-empty files_created" invariant
    holds for layouts where the dispatch produces files at the
    workspace root rather than under a per-layer subtree.

    `adapter_used` records the resolved adapter id post-fallback. For
    v2.2-candidate ids routed via the `--accept-v22-fallback` flag, the
    field reads `"generic"`; the `decision["stacks"]` entry preserves
    the original choice for forensic replay.
    """
    if not layers:
        return []
    sorted_indices = sorted(
        range(len(layers)),
        key=lambda i: len(str(layers[i].get("path") or ".")),
        reverse=True,
    )
    bucket: dict[int, list[str]] = {i: [] for i in range(len(layers))}
    for f in materialized_files:
        assigned = False
        for i in sorted_indices:
            p = str(layers[i].get("path") or ".")
            if p == "." or f == p or f.startswith(p.rstrip("/") + "/"):
                bucket[i].append(f)
                assigned = True
                break
        if not assigned:
            bucket[0].append(f)
    return [
        LayerReceiptEntry(
            stack=str(layers[i].get("stack", "")),
            path=str(layers[i].get("path", ".")),
            role=str(layers[i].get("role", "")),
            adapter_used=_resolved_adapter_id(
                str(layers[i].get("stack", "")),
                accept_v22_fallback=accept_v22_fallback,
            ),
            files_created=sorted(bucket[i]),
        )
        for i in range(len(layers))
    ]


def _resolved_adapter_id(stack_id: str, *, accept_v22_fallback: bool) -> str:
    """Mirror `resolve_adapter` selection for forensic record-keeping.

    v2.2-candidate ids routed via `--accept-v22-fallback` resolve to
    `"generic"`. Active ids resolve to themselves. Truly-unknown ids
    propagate as-is (the dispatch path raises `unknown_v21_stack_id`
    before this helper runs).
    """
    from lp_scaffold_stack.v21_adapter_dispatch import (  # noqa: PLC0415
        _ADAPTER_REGISTRY,
        _V22_CANDIDATE_IDS,
    )
    if stack_id in _ADAPTER_REGISTRY:
        return stack_id
    if stack_id in _V22_CANDIDATE_IDS and accept_v22_fallback:
        return "generic"
    return stack_id


__all__ = [
    "COMMAND_NAME",
    "DEFAULT_CATEGORY_PATTERNS_YML",
    "DEFAULT_PLUGINS_ROOT",
    "DEFAULT_SCAFFOLDERS_YML",
    "Outcome",
    "PipelineResult",
    "run_pipeline",
]
