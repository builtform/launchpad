"""`/lp-update-identity` orchestration (Phase 10 v2.1 Slice C).

Public surface:
    run_update_identity(
        cwd, identity_input, *,
        dry_run=False, seed_brownfield=False, allow_email_mismatch=False,
        quiet=False, baseline_decision=None,
        stdout=None, stderr=None,
    ) -> UpdateIdentityResult

Engine ordering (locked in plan §4 Slice C step 1):

  1. `_validate_preconditions()` (inline per DA4): 6 checks. Halts cleanly
     with structured error.
  2. Detect re-entry case A-E (per DA5 5-case matrix).
  3. Identity diff: compare identity_input against current scaffold-decision
     identity block (or empty for case B/D).
  4. No-op fast path (case C): print current sealed identity values per
     product-lens P1; return UpdateIdentityResult(status=NO_OP).
  5. Sentinel write via O_CREAT|O_EXCL (per DA3 + F2). FileExistsError
     after liveness check -> IDENTITY_UPDATE_IN_PROGRESS.
  6. Validate new identity (strict_no_placeholders=True per DA2) +
     IDENTITY_COPYRIGHT_FORBIDDEN_CHARS extended set per F3.
  7. Backup directory creation + scaffold-decision atomic re-seal via
     re_seal_decision_atomic (DA9: generated_at preserved byte-identical;
     identity_updated_at + plugin_version + version_drift_log update per
     DA8 + DA9).
  8. KernelRenderer.refresh() invocation (per DA1 direct invocation).
  9. Sentinel clear.
  10. PII WARN print (DA6) + diff summary print (§3.12).
  11. Return UpdateIdentityResult.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, TextIO

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_bootstrap import LAUNCHPAD_DIR_NAME  # noqa: E402

from lp_update_identity import (  # noqa: E402
    IdentityUpdateErrorCode,
    IdentityUpdateSentinelError,
    IdentityUpdateStatus,
)
from lp_update_identity.sentinel import (  # noqa: E402
    clear_sentinel,
    is_pid_alive,
    read_sentinel,
    sentinel_path,
    write_sentinel,
)


PII_WARN_LINES = (
    "WARN: prior identity values persist in git history (LICENSE, CONTRIBUTING.md, ...).",
    "      See docs/guides/IDENTITY_AND_PII.md for removal options.",
)


@dataclass(frozen=True)
class UpdateIdentityResult:
    """Phase 10 §3.4 structured return.

    `status` is the info-class outcome (UPDATED / NO_OP / SEEDED_FIRST_TIME);
    `error_code` is None on success and an `IdentityUpdateErrorCode` on
    halt-class failures. `fields_changed` lists the identity field names
    whose value changed (DA8: NAMES recorded; VALUES omitted in
    version_drift_log entry to prevent PII leak in committed JSON).
    """
    status: IdentityUpdateStatus | None
    fields_changed: list[str] = field(default_factory=list)
    rendered: list[Path] = field(default_factory=list)
    skipped_user_edits: list[Path] = field(default_factory=list)
    template_drift_infos: list[str] = field(default_factory=list)
    error_code: IdentityUpdateErrorCode | None = None
    error_message: str = ""
    remediation: str = ""


def _utc_iso8601_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(stream: TextIO | None, default, line: str) -> None:
    target = stream if stream is not None else default
    print(line, file=target)


def _read_git_config_email(cwd: Path) -> str:
    """Return `git config user.email` value, or empty string if unset.

    Best-effort: subprocess errors are translated to empty-string. Per
    cycle-3 security P2-A the engine treats empty as a mismatch (fail-
    closed posture) when seed_brownfield is set.
    """
    try:
        completed = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def _validate_preconditions(
    cwd: Path,
    *,
    seed_brownfield: bool,
) -> tuple[dict | None, list[str]]:
    """Inline DA4 -- the 6 checks per plan §3.4.

    Returns `(scaffold_decision_payload_or_None, info_messages)`. On hard
    halt, raises a `_PreconditionAbort` carrying the structured error
    reason + remediation. Caller translates into UpdateIdentityResult.

    Check order (locked in plan §3.5 Detection order):
      1. scaffold-decision.json exists / readable -> SCAFFOLD_DECISION_MISSING
         (unless seed_brownfield: case D handled at higher level).
      2. Schema version 1.1 (legacy 1.0 triggers seed-as-first-time per
         re-entry case B).
      3. /lp-update-identity sentinel: dead-PID auto-recover OR
         IDENTITY_UPDATE_IN_PROGRESS refusal.
      4. /lp-bootstrap sentinel concurrent-run: BOOTSTRAP_IN_PROGRESS.
      5. .launchpad/ writable -> PERMISSION_DENIED.
      6. config.yml schema readable -> WARN + fall back to scaffold-decision
         stacks: array (DA4 v2 confirmation: malformed-config fallback IS
         safe -- scaffold-decision is the authoritative source).
    """
    infos: list[str] = []

    decision_path = cwd / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"
    if not decision_path.is_file():
        if seed_brownfield:
            return None, ["scaffold-decision absent; brownfield seed path"]
        raise _PreconditionAbort(
            code=IdentityUpdateErrorCode.SCAFFOLD_DECISION_MISSING,
            message=f"scaffold-decision.json absent at {decision_path}",
            remediation=(
                "no scaffold-decision.json; run /lp-pick-stack first OR "
                "/lp-update-identity --seed-brownfield for legacy v2.0 "
                "migration"
            ),
        )

    try:
        decision_text = decision_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _PreconditionAbort(
            code=IdentityUpdateErrorCode.PERMISSION_DENIED,
            message=f"scaffold-decision.json unreadable: {exc}",
            remediation=f"check {decision_path} permissions",
        ) from exc

    try:
        decision_payload = json.loads(decision_text)
    except ValueError as exc:
        raise _PreconditionAbort(
            code=IdentityUpdateErrorCode.SCAFFOLD_DECISION_MISSING,
            message=f"scaffold-decision.json malformed: {exc}",
            remediation=(
                f"re-run /lp-pick-stack OR remove {decision_path} and run "
                f"/lp-update-identity --seed-brownfield"
            ),
        ) from exc
    if not isinstance(decision_payload, dict):
        raise _PreconditionAbort(
            code=IdentityUpdateErrorCode.SCAFFOLD_DECISION_MISSING,
            message="scaffold-decision.json top-level is not an object",
            remediation=f"remove {decision_path} and re-run /lp-pick-stack",
        )

    # Check 3: /lp-update-identity sentinel preflight.
    try:
        id_snap = read_sentinel(cwd)
    except IdentityUpdateSentinelError as exc:
        raise _PreconditionAbort(
            code=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            message=str(exc),
            remediation=getattr(exc, "remediation", "")
            or f"remove {sentinel_path(cwd)} after confirming no /lp-update-identity is running",
        ) from exc
    if id_snap is not None:
        if is_pid_alive(id_snap.command_pid):
            raise _PreconditionAbort(
                code=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
                message=(
                    f"another /lp-update-identity is running "
                    f"(sentinel pid={id_snap.command_pid})"
                ),
                remediation=(
                    f"wait for pid {id_snap.command_pid} to finish, OR "
                    f"kill it after confirming the process is dead"
                ),
            )
        # Dead PID -> auto-recover: clear sentinel and append INFO.
        clear_sentinel(cwd)
        infos.append(
            f"recovered stale identity-update sentinel "
            f"(dead pid={id_snap.command_pid}, started_at={id_snap.started_at})"
        )

    # Check 4: /lp-bootstrap concurrent-run.
    # Phase 11 hardening A1: same-PID guard mirrors lp_bootstrap engine
    # cross-detect. If the sentinel was written by THIS process (e.g., a
    # future caller invokes update-identity from inside scaffold-stack),
    # don't self-block.
    own_pid = os.getpid()
    try:
        from lp_bootstrap.sentinel import (
            is_pid_alive as _bs_is_pid_alive,
            read_sentinel as _bs_read_sentinel,
        )
        bs_snap = _bs_read_sentinel(cwd)
        if (
            bs_snap is not None
            and bs_snap.command_pid != own_pid
            and _bs_is_pid_alive(bs_snap.command_pid)
        ):
            raise _PreconditionAbort(
                code=IdentityUpdateErrorCode.BOOTSTRAP_IN_PROGRESS,
                message=(
                    f"/lp-bootstrap is running (sentinel pid={bs_snap.command_pid})"
                ),
                remediation=(
                    f"wait for pid {bs_snap.command_pid} to finish before "
                    f"re-running /lp-update-identity"
                ),
            )
    except ImportError:  # pragma: no cover
        pass

    # Check 4b: scaffold-stack concurrent-run (per cycle-2 F9).
    try:
        from lp_scaffold_stack.sentinel import (
            is_pid_alive as _ss_is_pid_alive,
            read_sentinel as _ss_read_sentinel,
        )
        ss_snap = _ss_read_sentinel(cwd)
        if (
            ss_snap is not None
            and ss_snap.command_pid != own_pid
            and _ss_is_pid_alive(ss_snap.command_pid)
        ):
            raise _PreconditionAbort(
                code=IdentityUpdateErrorCode.BOOTSTRAP_IN_PROGRESS,
                message=(
                    f"/lp-scaffold-stack is running (sentinel pid={ss_snap.command_pid})"
                ),
                remediation=(
                    f"wait for pid {ss_snap.command_pid} to finish before "
                    f"re-running /lp-update-identity"
                ),
            )
    except ImportError:  # pragma: no cover
        pass

    # Check 5: .launchpad/ writable.
    if not os.access(str(cwd / LAUNCHPAD_DIR_NAME), os.W_OK):
        raise _PreconditionAbort(
            code=IdentityUpdateErrorCode.PERMISSION_DENIED,
            message=f"{cwd / LAUNCHPAD_DIR_NAME} is not writable",
            remediation=(
                f"check filesystem permissions on {cwd / LAUNCHPAD_DIR_NAME}"
            ),
        )

    return decision_payload, infos


class _PreconditionAbort(Exception):
    """Internal helper: bundles structured error fields raised by
    `_validate_preconditions` so `run_update_identity` can translate to
    `UpdateIdentityResult` cleanly."""

    def __init__(
        self,
        *,
        code: IdentityUpdateErrorCode,
        message: str,
        remediation: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


def _detect_re_entry_case(
    decision_payload: dict | None,
    *,
    seed_brownfield: bool,
) -> str:
    """Per DA5 detection-order matrix. Returns one of A/B/C/D/E/UPDATED.

    UPDATED is the "normal" path: 1.1 envelope present + identity present +
    kernel_render_state present.
    """
    if decision_payload is None:
        return "D" if seed_brownfield else "A"
    schema_version = decision_payload.get("schema_version") or decision_payload.get("version")
    if schema_version not in ("1.1", "1.x"):
        # Legacy 1.0 -> seed-as-first-time per case B.
        return "B"
    if not isinstance(decision_payload.get("identity"), dict):
        return "B"
    if not decision_payload.get("kernel_render_state"):
        return "E"
    return "UPDATED"


def _is_legacy_1_0_envelope(decision_payload: dict | None) -> bool:
    """Phase 1+2 retroactive amendment A3 -- detect legacy 1.0 envelopes.

    Returns True when the on-disk envelope predates the v2.1 1.1 schema:
    `schema_version` field absent OR exactly "1.0". Such envelopes were
    written by v2.0-era /lp-pick-stack and lack the 1.1 identity block;
    /lp-update-identity transparently migrates them on first invocation.
    """
    if decision_payload is None:
        return False
    schema_version = decision_payload.get("schema_version")
    return schema_version is None or schema_version == "1.0"


def _migrate_legacy_envelope_in_memory(decision_payload: dict) -> tuple[str, bool]:
    """Phase 1+2 retroactive amendment A3 -- transparent v1.0 -> v1.1 migration.

    Mutates the in-memory payload to bump `schema_version` to "1.1" and
    seed `default_unset_identity()` when identity is missing. Identity
    values that already exist in the legacy envelope are preserved
    byte-for-byte.

    Returns `(info_message, identity_freshly_seeded)`. The boolean signals
    that the legacy envelope had no prior identity block (so the engine
    should route through Case B / seed-as-first-time, not Case E which
    presumes existing on-disk kernel files).

    Caller is responsible for persisting the mutation to disk via
    `re_seal_decision_atomic`.
    """
    from lp_pick_stack.decision_writer import default_unset_identity

    had_identity = isinstance(decision_payload.get("identity"), dict)
    if not had_identity:
        decision_payload["identity"] = default_unset_identity()
        info = (
            "Detected legacy v2.0 scaffold-decision.json (schema_version 1.0); "
            "migrating to 1.1 with UNSET identity placeholders. Continue with "
            "/lp-update-identity prompts to populate identity."
        )
    else:
        info = (
            "Detected legacy v2.0 scaffold-decision.json (schema_version 1.0) "
            "with identity already present; bumping to 1.1 (identity values "
            "preserved verbatim)."
        )
    decision_payload["schema_version"] = "1.1"
    return info, not had_identity


def _compute_identity_diff(
    old_identity: Mapping[str, Any] | None,
    new_identity: Mapping[str, Any],
) -> list[str]:
    """Return field NAMES whose value changed (DA8: names only, not values).

    `pii_opt_in` and `license_other_body` are included on equal terms
    with the 5 prompted fields per plan §3.2 prompt-count = 7 (5 +
    PII opt-in + conditional Other-body).
    """
    if old_identity is None:
        return [
            k for k in (
                "pii_opt_in", "project_name", "email", "copyright_holder",
                "repo_url", "license", "license_other_body",
            )
            if k in new_identity
        ]
    changed = []
    for key in (
        "pii_opt_in", "project_name", "email", "copyright_holder",
        "repo_url", "license", "license_other_body",
    ):
        if old_identity.get(key) != new_identity.get(key):
            changed.append(key)
    return changed


def _print_pii_warn(
    *,
    quiet: bool,
    stream: TextIO,
) -> None:
    """DA6: always print on every successful invocation when stdout is a
    TTY; non-TTY: single-line WARN to stderr only. --quiet suppresses."""
    if quiet:
        return
    is_tty = getattr(stream, "isatty", lambda: False)()
    if is_tty:
        for line in PII_WARN_LINES:
            print(line, file=stream)
    else:
        print(PII_WARN_LINES[0], file=sys.stderr)


def _truncate_for_diff(value: Any) -> str:
    """Phase 10 §3.12 truncation rules: 80-char cap with ellipsis;
    multi-line collapses to literal `\\n`."""
    text = "" if value is None else str(value)
    text = text.replace("\n", "\\n")
    if len(text) > 80:
        return text[:77] + "…"
    return text


def _format_diff_summary(
    fields_changed: list[str],
    old_identity: Mapping[str, Any] | None,
    new_identity: Mapping[str, Any],
    rendered: list[Path],
    skipped: list[Path],
    cwd: Path,
) -> list[str]:
    """Phase 10 §3.12 literal mock format."""
    lines = ["✓ Identity updated.", "", "Fields changed:"]
    if not fields_changed:
        lines.append("  (none)")
    else:
        max_label = max(len(f) + 1 for f in fields_changed)
        for f in fields_changed:
            old_v = (old_identity or {}).get(f)
            new_v = new_identity.get(f)
            lines.append(
                f"  {f + ':':<{max_label}}  {_truncate_for_diff(old_v)}  →  {_truncate_for_diff(new_v)}"
            )
    lines.append("")
    total = len(rendered) + len(skipped)
    lines.append(f"Kernel files re-rendered ({len(rendered)} of {total}):")
    for path in rendered:
        lines.append(f"  ✓ {path.relative_to(cwd) if path.is_absolute() else path}")
    for path in skipped:
        rel = path.relative_to(cwd) if path.is_absolute() else path
        lines.append(f"  ✗ {rel} (skipped: USER_EDIT_BLOCKS_REFRESH)")
    return lines


def _ensure_backup_dir(cwd: Path) -> Path:
    """Create `.launchpad/backups/<ts>-<pid>/` and return the path."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = cwd / LAUNCHPAD_DIR_NAME / "backups" / f"{ts}-{os.getpid()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def run_update_identity(
    cwd: Path,
    identity_input: Mapping[str, Any] | None,
    *,
    dry_run: bool = False,
    seed_brownfield: bool = False,
    allow_email_mismatch: bool = False,
    quiet: bool = False,
    baseline_decision: str | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> UpdateIdentityResult:
    """Phase 10 v2.1 orchestrator. See module docstring for sequence."""
    out_stream = stdout if stdout is not None else sys.stdout
    err_stream = stderr if stderr is not None else sys.stderr

    # Step 1: preconditions.
    try:
        decision_payload, infos = _validate_preconditions(
            cwd, seed_brownfield=seed_brownfield,
        )
    except _PreconditionAbort as exc:
        return UpdateIdentityResult(
            status=None,
            error_code=exc.code,
            error_message=exc.message,
            remediation=exc.remediation,
        )

    # Phase 1+2 retroactive amendment A3: transparent legacy v1.0 -> v1.1
    # migration. When the on-disk envelope predates the v2.1 schema bump,
    # mutate the in-memory payload BEFORE case detection so the engine sees
    # the migrated shape. The schema bump persists to disk in the same
    # re_seal call that writes the new identity values, via the
    # `_legacy_migration_applied` flag captured into the update closure.
    _legacy_migration_applied = False
    _legacy_identity_freshly_seeded = False
    if _is_legacy_1_0_envelope(decision_payload):
        _legacy_migration_applied = True
        migration_info, _legacy_identity_freshly_seeded = (
            _migrate_legacy_envelope_in_memory(decision_payload)
        )
        infos.append(migration_info)
        print(f"INFO: {migration_info}", file=err_stream)

    # Step 2: re-entry case detection.
    case = _detect_re_entry_case(decision_payload, seed_brownfield=seed_brownfield)
    # When legacy migration just seeded an UNSET identity, route through
    # Case B (seed-as-first-time) rather than Case E -- Case E presumes
    # existing on-disk kernel files whose render-state is recorded, but
    # a freshly-migrated v1.0 envelope predates kernel rendering entirely.
    if _legacy_identity_freshly_seeded:
        case = "B"

    if case == "A":
        # Greptile PR #50: Case A is unreachable here -- _validate_preconditions
        # raises SCAFFOLD_DECISION_MISSING when decision_payload is None and
        # seed_brownfield is False, which is exactly the precondition for
        # _detect_re_entry_case to return "A". A regression on the precondition
        # path should fail loudly rather than be silently absorbed by this
        # branch returning a structured error duplicate.
        raise RuntimeError(
            "Case A reached run_update_identity body; preconditions should "
            "have raised SCAFFOLD_DECISION_MISSING. Check _validate_preconditions"
            " for a regression."
        )

    # Case D brownfield seed gate: refuse if no flag.
    if case == "D" and not seed_brownfield:
        return UpdateIdentityResult(
            status=None,
            error_code=IdentityUpdateErrorCode.BROWNFIELD_SEED_REFUSED,
            error_message=(
                "no scaffold-decision.json present; brownfield seed not "
                "authorized"
            ),
            remediation=(
                "pass --seed-brownfield to seed identity from scratch for "
                "a legacy v2.0 / manually-created project"
            ),
        )

    # Case D: git config user.email cross-check.
    if case == "D" and identity_input is not None:
        proposed_email = identity_input.get("email") or ""
        git_email = _read_git_config_email(cwd)
        # Empty/unset git_email is fail-closed treated as mismatch.
        is_mismatch = (not git_email) or git_email != proposed_email
        if is_mismatch and not allow_email_mismatch:
            return UpdateIdentityResult(
                status=None,
                error_code=IdentityUpdateErrorCode.GIT_CONFIG_EMAIL_MISMATCH,
                error_message=(
                    "proposed email does not match git config user.email "
                    "(or git_email is unset)"
                ),
                remediation=(
                    "either update git config user.email OR pass "
                    "--allow-email-mismatch to override; mismatch is "
                    "blocked by default to defeat PR-based identity forgery"
                ),
            )
        if is_mismatch and allow_email_mismatch:
            print(
                "WARN: git config user.email mismatch; proceeding under "
                "--allow-email-mismatch",
                file=err_stream,
            )

    # Case E: kernel_render_state baseline prompt decision.
    if case == "E":
        if baseline_decision in (None, "N"):
            return UpdateIdentityResult(
                status=None,
                error_code=IdentityUpdateErrorCode.USER_EDIT_BLOCKS_REFRESH,
                error_message=(
                    "no kernel_render_state baseline; refresh refused"
                ),
                remediation=(
                    "for tracked kernel files: git checkout HEAD -- <file>; "
                    "for untracked: rm <file> && /lp-bootstrap --refresh-all"
                ),
            )

    # Step 3: identity diff.
    if identity_input is None:
        # No input means caller is querying preconditions only.
        return UpdateIdentityResult(status=IdentityUpdateStatus.NO_OP)
    old_identity = (decision_payload or {}).get("identity")
    fields_changed = _compute_identity_diff(old_identity, identity_input)

    # Step 4: no-op fast path.
    if not fields_changed and case == "UPDATED":
        if not quiet:
            for k in (
                "project_name", "email", "copyright_holder", "repo_url", "license",
            ):
                v = (old_identity or {}).get(k)
                print(f"  {k}: {_truncate_for_diff(v)}", file=out_stream)
        return UpdateIdentityResult(
            status=IdentityUpdateStatus.NO_OP,
            fields_changed=[],
        )

    if dry_run:
        return UpdateIdentityResult(
            status=IdentityUpdateStatus.UPDATED if old_identity else IdentityUpdateStatus.SEEDED_FIRST_TIME,
            fields_changed=fields_changed,
        )

    # v2.1 Codex PR #50 post-review-2 P1 #1: Case D --seed-brownfield
    # non-dry-run create path is not yet implemented. Without this
    # fail-closed guard, the engine would call `re_seal_decision_atomic`
    # (Step 7) which reads a non-existent scaffold-decision.json and
    # raises an unstructured FileNotFoundError. The full create path
    # (write_decision_file from a fresh seed) is filed as v2.1.1 BL-271.
    # Surface a structured error here so the user sees remediation rather
    # than a stack trace.
    if case == "D" and seed_brownfield:
        return UpdateIdentityResult(
            status=None,
            error_code=IdentityUpdateErrorCode.BROWNFIELD_SEED_NOT_IMPLEMENTED,
            error_message=(
                "Case D --seed-brownfield non-dry-run create path is not "
                "implemented at v2.1.0; the engine cannot write a fresh "
                "scaffold-decision.json from scratch"
            ),
            remediation=(
                "Run /lp-pick-stack to generate a fresh "
                "scaffold-decision.json, then re-run /lp-update-identity. "
                "OR wait for v2.1.1 (BL-271) which adds the seed-brownfield "
                "create path. Use --dry-run to validate preconditions "
                "without writing."
            ),
        )

    # Step 5: validate strict + sentinel write.
    from lp_pick_stack.decision_writer import (
        IdentityValidationError,
        re_seal_decision_atomic,
        validate_identity,
    )
    try:
        validate_identity(identity_input, strict_no_placeholders=True)
    except IdentityValidationError as exc:
        return UpdateIdentityResult(
            status=None,
            error_code=IdentityUpdateErrorCode.IDENTITY_VALIDATION_FAILED,
            error_message=f"identity.{exc.field} failed validation",
            remediation=(
                f"re-run with a valid {exc.field}; consult /lp-pick-stack "
                f"docs for the allowlist regex"
            ),
        )

    # Compute pre-edit decision sha for sentinel rollback.
    decision_path = cwd / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"
    pre_edit_sha = (
        hashlib.sha256(decision_path.read_bytes()).hexdigest()
        if decision_path.is_file() else None
    )

    backup_dir = _ensure_backup_dir(cwd)
    if decision_path.is_file():
        shutil.copy2(decision_path, backup_dir / "scaffold-decision.json")
    target_paths = [
        "LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
        "README.md", "SECURITY.md", "AGENTS.md", "CLAUDE.md",
    ]
    try:
        write_sentinel(
            cwd,
            pre_edit_decision_sha256=pre_edit_sha,
            target_paths=target_paths,
            backup_path=str(backup_dir),
        )
    except FileExistsError:
        return UpdateIdentityResult(
            status=None,
            error_code=IdentityUpdateErrorCode.IDENTITY_UPDATE_IN_PROGRESS,
            error_message="sentinel already exists (concurrent /lp-update-identity)",
            remediation=(
                "wait or kill the running /lp-update-identity PID, then "
                "re-run after confirming the process is dead"
            ),
        )

    rendered: list[Path] = []
    skipped: list[Path] = []
    template_drift_infos: list[str] = []
    try:
        # v2.1 Codex PR #50 Greptile #6 (D6): Case E "y" path skips
        # KernelRenderer.refresh() (which would clobber user edits). It
        # writes a `.pre-migration` backup, computes current on-disk SHAs
        # via `compute_current_on_disk_state()`, and seals
        # kernel_render_state via `mark_kernel_seeded()` without rendering
        # any new content. Result: user files preserved verbatim; only
        # scaffold-decision.json gets the sealed state.
        from plugin_default_generators.kernel_renderer import KernelRenderer
        renderer = KernelRenderer()

        if case == "E" and baseline_decision == "y":
            # Write `.pre-migration` backup BEFORE the migration write so
            # the validator's chain-validation gate (D9.2) can verify the
            # migration_origin_sha256 against the backup. Backup remains
            # for forensic/recovery purposes (cleanup deferred to BL-269).
            decision_path_pm = (
                cwd / LAUNCHPAD_DIR_NAME / "scaffold-decision.json"
            )
            backup_path_pm = (
                cwd / LAUNCHPAD_DIR_NAME / "scaffold-decision.json.pre-migration"
            )
            if decision_path_pm.is_file():
                shutil.copy2(decision_path_pm, backup_path_pm)
            on_disk_state = renderer.compute_current_on_disk_state(cwd)
            all_files_missing = all(
                e.get("missing_on_disk", False) for e in on_disk_state
            )
            new_kernel_state: list[dict] | None = list(on_disk_state)
            if all_files_missing:
                # Stamp meta on the state list so /lp-review can surface
                # the recovery hint per D6.
                new_kernel_state.append({
                    "_meta": "all_files_missing",
                    "remediation": (
                        "all kernel files missing on disk; run "
                        "/lp-bootstrap --refresh to regenerate"
                    ),
                })
        else:
            # Step 6: KernelRenderer.refresh() runs FIRST so any failure
            # leaves scaffold-decision.json with the prior identity rather
            # than a half-applied state where JSON has new identity but
            # kernel files still hold old (Codex PR #50 P1).
            prior_state = (decision_payload or {}).get("kernel_render_state") or []
            result = renderer.refresh(
                cwd, identity_input,
                prior_kernel_render_state=prior_state,
            )
            rendered = [p for p, _sha in result.rendered]
            skipped = list(result.skipped_user_edits)
            template_drift_infos = list(result.template_drift_infos)
            new_kernel_state = (
                list(result.kernel_render_state)
                if result.kernel_render_state else None
            )

        # Step 7: scaffold-decision atomic re-seal -- AFTER successful refresh.
        # Combines identity update + kernel_render_state into one atomic
        # write so the on-disk decision reflects the just-rendered state.

        # v2.1 Codex PR #50 P1.3 (D9.2): identity-update re-seal also
        # routes through `mark_kernel_seeded()` so the ratchet keys
        # (kernel_seed_pending, migration_origin_sha256) are canonically
        # stripped whenever a kernel_render_state lands.
        from lp_scaffold_stack.decision_validator import mark_kernel_seeded

        def _apply_identity_update(payload: dict) -> None:
            payload["identity"] = dict(identity_input)
            payload["identity_updated_at"] = _utc_iso8601_now()
            # Phase 1+2 retroactive amendment A3: persist the legacy
            # v1.0 -> v1.1 migration on disk in the same atomic re-seal
            # that writes the new identity values.
            if _legacy_migration_applied:
                payload["schema_version"] = "1.1"
            # D7 canonical 5-key version_drift_log shape via shared helper.
            from lp_pick_stack.decision_writer import read_running_plugin_version
            from lp_bootstrap.version_drift import (
                Fingerprint,
                Names,
                compute_identity_fields_changed,
            )
            new_plugin_version = read_running_plugin_version()
            old_plugin_version = payload.get("plugin_version")
            old_identity_map: dict[str, str] = {}
            if isinstance(old_identity, dict):
                for k, v in old_identity.items():
                    if v is None:
                        continue
                    old_identity_map[str(k)] = str(v)
            new_identity_map: dict[str, str] = {
                str(k): str(v)
                for k, v in dict(identity_input).items()
                if v is not None
            }
            pii_opt_in = bool(dict(identity_input).get("pii_opt_in"))
            changed = compute_identity_fields_changed(
                old_identity_map, new_identity_map, pii_opt_in=pii_opt_in,
            )
            entry: dict[str, Any] = {
                "from_version": old_plugin_version,
                "to_version": new_plugin_version,
                "via": "/lp-update-identity",
                "accepted_at": _utc_iso8601_now(),
            }
            if isinstance(changed, Names):
                entry["fields_changed"] = list(changed.names)
            elif isinstance(changed, Fingerprint):
                entry["fields_changed_fingerprint"] = changed.digest
            log = list(payload.get("version_drift_log") or [])
            log.append(entry)
            payload["version_drift_log"] = log
            payload["plugin_version"] = new_plugin_version
            # Fold kernel_render_state into the same atomic write via the
            # mark_kernel_seeded helper. Skip when refresh produced no
            # state (no-op cases) to preserve prior behavior.
            if new_kernel_state is not None:
                sealed = mark_kernel_seeded(payload, new_kernel_state)
                payload.clear()
                payload.update(sealed)

        re_seal_decision_atomic(cwd, update_fn=_apply_identity_update)
    finally:
        # Step 8: clear sentinel even on exception so subsequent invocations
        # don't get blocked by a stale-but-not-yet-recovered marker.
        clear_sentinel(cwd)

    # Step 9: PII WARN print.
    _print_pii_warn(quiet=quiet, stream=out_stream)

    # Step 10: diff summary print.
    if not quiet:
        for line in _format_diff_summary(
            fields_changed, old_identity, identity_input, rendered, skipped, cwd,
        ):
            print(line, file=out_stream)

    return UpdateIdentityResult(
        status=IdentityUpdateStatus.SEEDED_FIRST_TIME if old_identity is None else IdentityUpdateStatus.UPDATED,
        fields_changed=fields_changed,
        rendered=rendered,
        skipped_user_edits=skipped,
        template_drift_infos=template_drift_infos,
    )


__all__ = [
    "UpdateIdentityResult",
    "run_update_identity",
]
