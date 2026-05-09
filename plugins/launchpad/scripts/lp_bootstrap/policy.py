"""Per-file conflict policies + backup-dir helper (v2.1 Phase 3 section 3.2).

Three active policies (v2.1 ship surface) plus one `--refresh`-mode variant:

  * `overwrite-if-unchanged` -- 26 of 30 paths. Compare on-disk-sha to
    manifest's `rendered_content_sha256`; match -> write new content,
    mismatch -> skip with `kept-user-edits` action message.
  * `merge-keys` -- 3 paths (`lefthook.yml`, `scripts/compound/config.json`,
    `.github/CODEOWNERS`). Plugin can ADD top-level keys; CANNOT delete
    user keys. Within an existing user-defined key (e.g., `pre-commit.commands`
    list), plugin appends new entries but never deletes user-defined ones.
    Value-type conflicts: user wins, structured warning to
    `.launchpad/bootstrap-warnings.json`.
  * `append-only` -- 1 path (`.gitignore`). Append plugin-required entries
    that aren't already present. NEVER reorder, deduplicate, or remove
    user entries. Symlink target is rejected fail-closed (harden A14).
  * `overwrite-with-backup` -- reserved for `--refresh` / `--refresh-all`.
    Writes pre-edit on-disk content to
    `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>` before atomic-write.
    Backup contents must be byte-equal pre-edit; symlink rejected.

Two policies named in the original V3 contract (`skip-if-exists`,
`overwrite-always`) are NOT shipped per harden B1; they defer to Phase 4
if an adapter overlay demands them, else v2.2.

Atomic-write primitives ride Phase 1's `atomic_io.atomic_write_replace`.
chmod runs AFTER `os.replace` per harden B8 to avoid the tempfile-mode
race (chmod on the tempfile is overwritten by replace).
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import atomic_write_replace  # noqa: E402
from plugin_default_generators._renderer_base import (  # noqa: E402
    sha256_bytes,
    sha256_file,
)

from lp_bootstrap import (  # noqa: E402
    BACKUP_DIR_NAME,
    LAUNCHPAD_DIR_NAME,
    WARNINGS_FILENAME,
    BootstrapErrorCode,
)


class BootstrapPolicyError(RuntimeError):
    """Per-file policy failure raised by this module.

    Carries `.reason: BootstrapErrorCode`, `.path: Path | None`,
    `.remediation: str` so the engine wires structured `BootstrapError`
    instances into `BootstrapResult.errors`.
    """

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


# --- Policy action result -------------------------------------------------


class PolicyAction(StrEnum):
    """What the policy applicator decided to do for this target.

    Surfaced through engine.run_bootstrap so callers can render
    user-friendly summaries and so test fixtures can assert exact
    branching.
    """

    WRITE = "write"  # write rendered content to target
    SKIP_UNCHANGED = "skip-unchanged"  # on-disk == rendered; no-op
    KEPT_USER_EDITS = "kept-user-edits"  # on-disk diverges from manifest; preserve
    APPENDED = "appended"  # append-only added new lines
    MERGED = "merged"  # merge-keys merged user + plugin
    OVERWROTE_WITH_BACKUP = "overwrote-with-backup"  # --refresh wrote backup


@dataclass(frozen=True)
class PolicyResult:
    """Outcome of one policy applicator call."""

    action: PolicyAction
    path: Path
    bytes_written: bytes | None
    rendered_sha256: str | None
    warnings: tuple[str, ...] = ()


# --- Backup directory helper (section 3.2 + harden C1) --------------------


def make_backup_dir(cwd: Path, *, command_pid: int | None = None) -> Path:
    """Create a fresh backup directory beneath `.launchpad/backups/`.

    Naming scheme: `<ts>-<PID>-<rand4>/`. The 4-char hex random suffix
    defuses same-second + same-PID collisions per harden C1 (the previous
    `<ts>-<PID>` shape collided when `--refresh` was scripted in a tight
    loop sharing a parent shell PID).

    Returns the resolved backup directory path; the parent
    `.launchpad/backups/` exists (created with parents=True) but the
    subdirectory itself is empty until callers write per-file backups.
    """
    pid = command_pid if command_pid is not None else os.getpid()
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    rand4 = secrets.token_hex(2)
    backup_root = cwd / LAUNCHPAD_DIR_NAME / BACKUP_DIR_NAME / f"{ts}-{pid}-{rand4}"
    backup_root.mkdir(parents=True, exist_ok=False)
    return backup_root


def write_backup_then_overwrite(
    *,
    target: Path,
    new_bytes: bytes,
    backup_dir: Path,
    target_relpath: str,
    mode: int,
    cwd: Path,
) -> PolicyResult:
    """Apply `overwrite-with-backup` policy for `--refresh` / `--refresh-all`.

    Steps:
      1. Reject if `target` is a symlink (harden A14; symlink-followed
         backups don't preserve the on-disk-content contract).
      2. Read pre-edit bytes from `target` (if it exists).
      3. Write pre-edit bytes to `<backup_dir>/<target_relpath>`.
      4. Verify backup bytes match the source byte-for-byte (post-write
         re-read; if any other process is racing, fail closed).
      5. Atomic-write `new_bytes` to `target`; chmod after replace.

    Tests cover steps 1-5 individually plus the byte-equality round-trip.
    """
    if target.is_symlink():
        raise BootstrapPolicyError(
            f"refusing to refresh symlink {target}; refusing to follow",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            path=target,
            remediation=(
                f"resolve the symlink at {target} and replace it with a "
                f"regular file before re-running /lp-bootstrap --refresh"
            ),
        )

    pre_edit_bytes = b""
    if target.exists():
        pre_edit_bytes = target.read_bytes()

    backup_path = backup_dir / target_relpath
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_replace(backup_path, pre_edit_bytes, mode=0o644, trusted_root=cwd)

    verify_bytes = backup_path.read_bytes()
    if verify_bytes != pre_edit_bytes:
        raise BootstrapPolicyError(
            f"backup verification failed for {target}: post-write bytes "
            f"diverge from pre-edit content",
            reason=BootstrapErrorCode.PERMISSION_DENIED,
            path=target,
            remediation=(
                "Inspect the backup directory for filesystem corruption; "
                "rerun after resolving."
            ),
        )

    atomic_write_replace(target, new_bytes, mode=mode, trusted_root=cwd)
    rendered_sha = sha256_bytes(new_bytes)
    return PolicyResult(
        action=PolicyAction.OVERWROTE_WITH_BACKUP,
        path=target,
        bytes_written=new_bytes,
        rendered_sha256=rendered_sha,
    )


# --- overwrite-if-unchanged (section 3.2 row 1) ---------------------------


def apply_overwrite_if_unchanged(
    *,
    target: Path,
    rendered_bytes: bytes,
    manifest_rendered_sha: str | None,
    mode: int,
    cwd: Path,
) -> PolicyResult:
    """Compare on-disk sha to manifest's `rendered_content_sha256`.

    Decision matrix:

      target absent
        Write rendered_bytes; action=WRITE.

      target present, manifest_rendered_sha is None
        First-bootstrap or manifest-deleted; treat as ABSENT and write.
        action=WRITE.

      target present, on_disk_sha == manifest_rendered_sha
        User has not edited; safe to overwrite. action=WRITE if rendered
        differs from on-disk (new template version), else SKIP_UNCHANGED.

      target present, on_disk_sha != manifest_rendered_sha
        User edited; preserve. action=KEPT_USER_EDITS, no write.

    Per harden A16 the engine layers a fast-path on top: if
    `policy_action == WRITE` AND `on_disk_sha == rendered_sha`, skip the
    atomic_write entirely. This applicator returns `SKIP_UNCHANGED` for
    that case so the engine has explicit branching rather than "WRITE
    that happens to be a no-op".
    """
    if target.is_symlink():
        raise BootstrapPolicyError(
            f"refusing to write through symlink {target}",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            path=target,
            remediation=(
                f"replace the symlink at {target} with a regular file or "
                f"remove it; /lp-bootstrap will re-create it on next run."
            ),
        )

    rendered_sha = sha256_bytes(rendered_bytes)

    if not target.exists():
        atomic_write_replace(target, rendered_bytes, mode=mode, trusted_root=cwd)
        return PolicyResult(
            action=PolicyAction.WRITE,
            path=target,
            bytes_written=rendered_bytes,
            rendered_sha256=rendered_sha,
        )

    on_disk_sha = sha256_file(target)

    if manifest_rendered_sha is not None and on_disk_sha != manifest_rendered_sha:
        return PolicyResult(
            action=PolicyAction.KEPT_USER_EDITS,
            path=target,
            bytes_written=None,
            rendered_sha256=rendered_sha,
        )

    if on_disk_sha == rendered_sha:
        return PolicyResult(
            action=PolicyAction.SKIP_UNCHANGED,
            path=target,
            bytes_written=None,
            rendered_sha256=rendered_sha,
        )

    atomic_write_replace(target, rendered_bytes, mode=mode, trusted_root=cwd)
    return PolicyResult(
        action=PolicyAction.WRITE,
        path=target,
        bytes_written=rendered_bytes,
        rendered_sha256=rendered_sha,
    )


# --- append-only (section 3.2 row 3 + harden A14) -------------------------


def apply_append_only(
    *,
    target: Path,
    rendered_bytes: bytes,
    mode: int,
    cwd: Path,
) -> PolicyResult:
    """Append plugin-required entries that aren't already present.

    Reads existing target if any, splits to lines, builds a set of existing
    lines (whitespace-stripped), and appends each plugin line that's not
    already present in document order. Never reorders, deduplicates, or
    removes user entries.

    Symlink target is rejected fail-closed per harden A14. Post-write
    verification re-reads the file and confirms every plugin-required
    line is present; if not, raises `GITIGNORE_APPEND_FAILED` aborting
    the entire bootstrap.

    The `.gitignore` allowlist scan (renderer-side per harden A12) runs
    BEFORE this function on the rendered content; unknown entries are
    surfaced via `record_warning()` here.
    """
    if target.is_symlink():
        raise BootstrapPolicyError(
            f"refusing to append through symlink {target}",
            reason=BootstrapErrorCode.GITIGNORE_APPEND_FAILED,
            path=target,
            remediation=(
                f"replace the symlink at {target} with a regular file or "
                f"remove it before re-running /lp-bootstrap"
            ),
        )

    plugin_text = rendered_bytes.decode("utf-8")
    plugin_lines = plugin_text.splitlines()

    existing_text = ""
    if target.exists():
        existing_text = target.read_text(encoding="utf-8")

    existing_lines = existing_text.splitlines()
    existing_set = {line.strip() for line in existing_lines}

    to_append: list[str] = []
    for line in plugin_lines:
        if not line.strip():
            continue
        if line.strip() in existing_set:
            continue
        to_append.append(line)
        existing_set.add(line.strip())

    if not to_append:
        rendered_sha = sha256_bytes(existing_text.encode("utf-8"))
        return PolicyResult(
            action=PolicyAction.SKIP_UNCHANGED,
            path=target,
            bytes_written=None,
            rendered_sha256=rendered_sha,
        )

    if existing_text and not existing_text.endswith("\n"):
        existing_text += "\n"

    new_text = existing_text + "\n".join(to_append) + "\n"
    new_bytes = new_text.encode("utf-8")

    atomic_write_replace(target, new_bytes, mode=mode, trusted_root=cwd)

    verify_text = target.read_text(encoding="utf-8")
    verify_lines = {line.strip() for line in verify_text.splitlines()}
    missing = [line for line in to_append if line.strip() not in verify_lines]
    if missing:
        raise BootstrapPolicyError(
            f"gitignore append verification failed: {missing!r} not present "
            f"after write",
            reason=BootstrapErrorCode.GITIGNORE_APPEND_FAILED,
            path=target,
            remediation=(
                f"add the missing entries {missing!r} manually to {target} "
                f"and re-run /lp-bootstrap"
            ),
        )

    rendered_sha = sha256_bytes(new_bytes)
    return PolicyResult(
        action=PolicyAction.APPENDED,
        path=target,
        bytes_written=new_bytes,
        rendered_sha256=rendered_sha,
    )


# --- merge-keys (section 3.2 row 2 + harden A13) --------------------------


def _is_mapping(v: Any) -> bool:
    return isinstance(v, Mapping)


def _is_list(v: Any) -> bool:
    return isinstance(v, list)


def merge_keys_additive(
    *,
    user: Mapping[str, Any] | None,
    plugin: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Merge `plugin` into `user` additively per harden A13.

    Contract:
      * Plugin can ADD new top-level keys; never deletes user keys.
      * Within an existing user-defined key whose value is a list, plugin
        may append new list items but NEVER deletes user-defined entries.
      * Within an existing user-defined key whose value is a mapping, the
        merge recurses with the same additive contract.
      * Value-type conflicts (user has list, plugin has mapping; or scalar
        vs sequence; etc.): user wins, a structured warning is collected.
      * Scalar conflicts (both leaf, different values): user wins, warning.

    Returns `(merged_dict, warnings)`. Warnings are descriptive strings
    that the engine writes one-per-line to
    `.launchpad/bootstrap-warnings.json`.
    """
    user_dict: dict[str, Any] = dict(user) if user is not None else {}
    warnings: list[str] = []

    def _merge(u: dict[str, Any], p: Mapping[str, Any], path: str) -> None:
        for key, plugin_value in p.items():
            here = f"{path}.{key}" if path else key
            if key not in u:
                u[key] = _deepcopy_jsonish(plugin_value)
                continue
            user_value = u[key]

            if _is_mapping(user_value) and _is_mapping(plugin_value):
                # recurse into mapping
                if not isinstance(user_value, dict):
                    user_value = dict(user_value)
                    u[key] = user_value
                _merge(user_value, plugin_value, here)
                continue

            if _is_list(user_value) and _is_list(plugin_value):
                user_set = {_jsonish_repr(x) for x in user_value}
                for item in plugin_value:
                    if _jsonish_repr(item) not in user_set:
                        user_value.append(_deepcopy_jsonish(item))
                        user_set.add(_jsonish_repr(item))
                continue

            if type(user_value) is not type(plugin_value) or _is_mapping(
                user_value
            ) != _is_mapping(plugin_value):
                warnings.append(
                    f"merge-keys: value-type conflict at {here}; user value "
                    f"({type(user_value).__name__}) wins over plugin value "
                    f"({type(plugin_value).__name__})"
                )
                continue

            if user_value != plugin_value:
                warnings.append(
                    f"merge-keys: scalar conflict at {here}; user value wins"
                )

    _merge(user_dict, plugin, "")
    return user_dict, warnings


def _jsonish_repr(value: Any) -> str:
    """Stable hashable repr for jsonish values used in `merge_keys_additive`.

    `json.dumps(sort_keys=True)` gives a deterministic hashable string for
    list-membership comparisons (lists in YAML / JSON commonly carry
    mappings whose key order is irrelevant for equality).
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _deepcopy_jsonish(value: Any) -> Any:
    """Deep-copy a json-ish value (list / dict / scalar)."""
    if isinstance(value, dict):
        return {k: _deepcopy_jsonish(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deepcopy_jsonish(v) for v in value]
    return value


def apply_merge_keys(
    *,
    target: Path,
    rendered_bytes: bytes,
    mode: int,
    cwd: Path,
    serializer: str = "json",
    yaml_dumper: Any = None,
) -> PolicyResult:
    """Apply additive merge-keys for `lefthook.yml`, `config.json`, `CODEOWNERS`.

    `serializer` is `"json"` for `scripts/compound/config.json`, `"yaml"`
    for `lefthook.yml`, and `"codeowners"` for `.github/CODEOWNERS`. Each
    branch parses both sides, calls `merge_keys_additive`, and writes the
    merged result.

    For YAML serialization the caller passes a `yaml_dumper` callable to
    avoid pulling PyYAML at module import (the renderer-base already
    imports it lazily).
    """
    if target.is_symlink():
        raise BootstrapPolicyError(
            f"refusing to merge through symlink {target}",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            path=target,
            remediation=(
                f"replace the symlink at {target} with a regular file or "
                f"remove it; /lp-bootstrap will recreate it"
            ),
        )

    if serializer == "json":
        plugin_obj = json.loads(rendered_bytes.decode("utf-8"))
        user_obj = None
        if target.exists():
            user_text = target.read_text(encoding="utf-8")
            try:
                user_obj = json.loads(user_text) if user_text.strip() else {}
            except ValueError as exc:
                raise BootstrapPolicyError(
                    f"merge-keys: existing target {target} is not valid JSON: {exc}",
                    reason=BootstrapErrorCode.POLICY_COLLISION,
                    path=target,
                    remediation=(
                        f"fix the JSON syntax of {target} manually before "
                        f"re-running /lp-bootstrap"
                    ),
                ) from exc
        if not _is_mapping(plugin_obj):
            raise BootstrapPolicyError(
                f"merge-keys: rendered template is not a mapping ({type(plugin_obj).__name__})",
                reason=BootstrapErrorCode.POLICY_COLLISION,
                path=target,
                remediation="re-render the template; merge-keys requires a mapping at the top",
            )
        merged, warnings = merge_keys_additive(user=user_obj, plugin=plugin_obj)
        new_bytes = (json.dumps(merged, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )

    elif serializer == "yaml":
        if yaml_dumper is None:
            raise BootstrapPolicyError(
                "merge-keys yaml serializer requires a yaml_dumper callable",
                reason=BootstrapErrorCode.POLICY_COLLISION,
                path=target,
                remediation="pass yaml_dumper=yaml.safe_dump from the caller",
            )
        import yaml  # type: ignore[import-not-found]

        plugin_obj = yaml.safe_load(rendered_bytes.decode("utf-8")) or {}
        user_obj = None
        if target.exists():
            user_text = target.read_text(encoding="utf-8")
            try:
                user_obj = yaml.safe_load(user_text) if user_text.strip() else {}
            except yaml.YAMLError as exc:
                raise BootstrapPolicyError(
                    f"merge-keys: existing target {target} is not valid YAML: {exc}",
                    reason=BootstrapErrorCode.POLICY_COLLISION,
                    path=target,
                    remediation=(
                        f"fix the YAML syntax of {target} manually before "
                        f"re-running /lp-bootstrap"
                    ),
                ) from exc
        if not _is_mapping(plugin_obj):
            raise BootstrapPolicyError(
                f"merge-keys: rendered template is not a mapping ({type(plugin_obj).__name__})",
                reason=BootstrapErrorCode.POLICY_COLLISION,
                path=target,
                remediation="re-render the template; merge-keys requires a mapping at the top",
            )
        merged, warnings = merge_keys_additive(user=user_obj, plugin=plugin_obj)
        new_bytes = yaml_dumper(merged).encode("utf-8")

    elif serializer == "codeowners":
        # CODEOWNERS is line-oriented (path + owners). We treat it like
        # append-only at the line level: every plugin line that is not
        # already present is appended in document order. User lines are
        # never reordered or deleted.
        return apply_append_only(
            target=target, rendered_bytes=rendered_bytes, mode=mode, cwd=cwd
        )

    else:
        raise BootstrapPolicyError(
            f"merge-keys: unknown serializer {serializer!r}",
            reason=BootstrapErrorCode.POLICY_COLLISION,
            path=target,
            remediation="caller must pass serializer in {'json','yaml','codeowners'}",
        )

    atomic_write_replace(target, new_bytes, mode=mode, trusted_root=cwd)
    rendered_sha = sha256_bytes(new_bytes)
    return PolicyResult(
        action=PolicyAction.MERGED,
        path=target,
        bytes_written=new_bytes,
        rendered_sha256=rendered_sha,
        warnings=tuple(warnings),
    )


# --- Warnings ledger ------------------------------------------------------


def record_warnings(cwd: Path, warnings: list[str]) -> None:
    """Append structured warnings to `.launchpad/bootstrap-warnings.json`.

    Atomic write; the file is overwritten with the merged warning history
    on each call. Format is `{"warnings": ["...", ...]}` so future readers
    can extend without a schema bump.
    """
    if not warnings:
        return
    target = cwd / LAUNCHPAD_DIR_NAME / WARNINGS_FILENAME
    payload: dict[str, Any] = {"warnings": []}
    if target.is_file():
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(payload.get("warnings"), list):
                payload = {"warnings": []}
        except (OSError, ValueError):
            payload = {"warnings": []}
    payload["warnings"].extend(warnings)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_replace(target, encoded, mode=0o644, trusted_root=cwd)


# --- Gitignore append helper for backups dir (harden A14) -----------------


def ensure_backups_in_gitignore(cwd: Path) -> None:
    """Make sure `.launchpad/backups/` is gitignored before the first refresh.

    Called by the engine right before `make_backup_dir()` so a `--refresh`
    on a brownfield project that has only a partial `.gitignore` overlay
    cannot accidentally leak a pre-edit backup into git history.

    Symlink target is rejected fail-closed; missing `.gitignore` is
    created with the single line. Verification re-reads the file and
    aborts the bootstrap if the entry is not present
    (`GITIGNORE_APPEND_FAILED`).
    """
    target = cwd / ".gitignore"
    entry = ".launchpad/backups/"
    if target.is_symlink():
        raise BootstrapPolicyError(
            f"refusing to append to symlinked {target}",
            reason=BootstrapErrorCode.GITIGNORE_APPEND_FAILED,
            path=target,
            remediation=(
                "replace the .gitignore symlink with a regular file before "
                "running /lp-bootstrap --refresh"
            ),
        )
    existing = ""
    if target.exists():
        existing = target.read_text(encoding="utf-8")
    if entry in {line.strip() for line in existing.splitlines()}:
        return
    if existing and not existing.endswith("\n"):
        existing += "\n"
    new_text = existing + entry + "\n"
    atomic_write_replace(target, new_text.encode("utf-8"), mode=0o644, trusted_root=cwd)
    verify = target.read_text(encoding="utf-8")
    if entry not in {line.strip() for line in verify.splitlines()}:
        raise BootstrapPolicyError(
            "gitignore append verification failed for .launchpad/backups/",
            reason=BootstrapErrorCode.GITIGNORE_APPEND_FAILED,
            path=target,
            remediation=(
                "add `.launchpad/backups/` to .gitignore manually before "
                "re-running /lp-bootstrap --refresh"
            ),
        )


# --- Phase 6 v2.1 lp-define config.yml writer (DA6 + cycle-3 architecture P1-A) ----


def write_config_yaml_atomic(path: Path, content: str, *, cwd: Path) -> None:
    """Atomically write `.launchpad/config.yml` for /lp-define.

    Wraps `atomic_write_replace` so `lp_define_runner.py` does NOT need to
    import `atomic_io` directly (Phase 8.5 lint allowlist limits direct
    `atomic_write_replace` imports to a small set; this helper keeps
    /lp-define on that allowlist via `lp_bootstrap.policy`).

    Symlink target is rejected fail-closed (mirrors the rest of this
    module). Parent directory is created if missing.
    """
    if path.is_symlink():
        raise BootstrapPolicyError(
            f"refusing to write through symlink {path}",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            path=path,
            remediation=(
                f"replace the symlink at {path} with a regular file before "
                "re-running /lp-define"
            ),
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_replace(path, content.encode("utf-8"), mode=0o644, trusted_root=cwd)


__all__ = [
    "BootstrapPolicyError",
    "PolicyAction",
    "PolicyResult",
    "apply_append_only",
    "apply_merge_keys",
    "apply_overwrite_if_unchanged",
    "ensure_backups_in_gitignore",
    "make_backup_dir",
    "merge_keys_additive",
    "record_warnings",
    "write_backup_then_overwrite",
    "write_config_yaml_atomic",
]
