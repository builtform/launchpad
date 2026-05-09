"""scaffold-receipt.json writer (HANDSHAKE §5).

Atomic O_CREAT|O_EXCL write of `.launchpad/scaffold-receipt.json` with
sha256 self-hash via canonical_hash. fsync + F_FULLFSYNC on darwin per the
canonical pattern from `decision_writer.py`.

Per HANDSHAKE §5: receipt fields are
  version, scaffolded_at, decision_sha256, decision_nonce,
  layers_materialized[], cross_cutting_files[], toolchains_detected[],
  secret_scan_passed, tier1_governance_summary{...}, sha256.

The Tier 1 governance summary's `architecture_docs_rendered` is hardcoded
to the count of `docs/architecture/*` outputs the doc generator emits at
v2.0 (PRD, TECH_STACK, BACKEND_STRUCTURE, APP_FLOW = 4) — single-source
TIER1_ARCHITECTURE_DOCS_RENDERED constant lives in `lp_scaffold_stack/__init__.py`.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

# Sibling-script imports.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash  # noqa: E402

from lp_scaffold_stack import (  # noqa: E402
    TIER1_ARCHITECTURE_DOCS_RENDERED,
    WRITTEN_RECEIPT_VERSION,
)

RECEIPT_FILENAME = "scaffold-receipt.json"


# v2.1.0 completion plan §3.6: typed entry for `layers_materialized`.
# Replaces the deleted `MaterializationResult` dataclass — receipt is the
# publishing surface, so the type lives at the publishing boundary. Each
# entry's `adapter_used` carries the resolved adapter id (e.g.
# "nextjs_standalone") so v2.2 readers can replay forensically when a
# v2.2-candidate routed via the generic fallback at v2.1.0.
class LayerReceiptEntry(TypedDict):
    stack: str
    path: str
    role: str
    adapter_used: str
    files_created: list[str]


# v2.1.0 completion plan §3.5: receipt-side `*_meta` allowlist.
# Mirrors `decision_validator._ALLOWED_DECISION_META_KEYS` on the
# publishing surface; `adapter_dispatch_meta` is the only v2.1.0 sibling.
_ALLOWED_RECEIPT_META_KEYS: frozenset[str] = frozenset({
    "adapter_dispatch_meta",
})

# Cycle-5 lock per v2.1.0 completion plan §3.5: identical regex to the
# validator-side `_META_KEY_REGEX`. Duplicated by-design at this seam to
# keep the two surfaces independent (no shared helper at module scope).
_META_KEY_REGEX = re.compile(r"[a-z][a-z0-9_]*_meta\Z")


class ReceiptWriteError(RuntimeError):
    """Raised on receipt-write failure. Carries `reason:` field."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


class ReceiptBuildError(ValueError):
    """Raised when a receipt payload contains a disallowed `*_meta` key.

    Per v2.1.0 completion plan §3.5: receipts forbid `*_meta` siblings
    outside `_ALLOWED_RECEIPT_META_KEYS`. Symmetric to the validator-side
    `Rejected(reason="unknown_meta_field")` path on scaffold-decision.json.
    """

    def __init__(self, message: str, *, reason: str = "unknown_meta_field"):
        super().__init__(message)
        self.reason = reason


def _utc_now_iso_sec() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_receipt_payload(
    *,
    decision_sha256: str,
    decision_nonce: str,
    layers_materialized: Sequence[Mapping[str, Any]],
    cross_cutting_files: Sequence[str],
    toolchains_detected: Sequence[str],
    secret_scan_passed: bool,
    tier1_governance_summary: Mapping[str, Any] | None = None,
    scaffolded_at: str | None = None,
    version: str | None = None,
    adapter_dispatch_meta: Mapping[str, Any] | None = None,
) -> dict:
    """Build the receipt payload (sans `sha256` field).

    The `tier1_governance_summary` is auto-populated when None: 4 fields per
    HANDSHAKE §5 schema. Callers that need to override any individual count
    pass a complete dict.

    `adapter_dispatch_meta` (per v2.1.0 completion plan §3.5): when a
    v2.2-candidate stack id routes via the `generic` fallback (only
    possible with `--accept-v22-fallback`), the engine passes
    `{"fallback_ids": [...]}` so consumers can detect the fallback for
    forensic replay. Validated against `_ALLOWED_RECEIPT_META_KEYS` at
    write time.
    """
    if tier1_governance_summary is None:
        # Per PR #41 cycle 8 #1 closure (Codex P1 + Greptile P1 dual-flag):
        # `whitelisted_paths` and `slash_commands_wired` are NOT known at
        # scaffold-stack time — `/lp-define` hasn't run yet, so REPOSITORY_
        # STRUCTURE.md and `.launchpad/config.yml` don't exist. Previously
        # these were emitted as `0` with comments "/lp-define populates",
        # but the receipt is sealed (sha256) before /lp-define touches it
        # and nothing rewrote the values. The Tier 1 panel rendered "0
        # paths whitelisted" / "0 slash commands wired" forever.
        #
        # Fix: emit `null` to make "unknown — compute live at panel render
        # time" explicit. lp-define.md Step 3 now computes these from the
        # live filesystem (parses REPOSITORY_STRUCTURE.md + config.yml).
        tier1_governance_summary = {
            "whitelisted_paths": None,
            "lefthook_hooks": ["secret-scan", "structure-drift", "typecheck", "lint"],
            "slash_commands_wired": None,
            "architecture_docs_rendered": TIER1_ARCHITECTURE_DOCS_RENDERED,
        }
    payload: dict[str, Any] = {
        "version": version or WRITTEN_RECEIPT_VERSION,
        "scaffolded_at": scaffolded_at or _utc_now_iso_sec(),
        "decision_sha256": decision_sha256,
        "decision_nonce": decision_nonce,
        "layers_materialized": [dict(layer) for layer in layers_materialized],
        "cross_cutting_files": list(cross_cutting_files),
        "toolchains_detected": list(toolchains_detected),
        "secret_scan_passed": bool(secret_scan_passed),
        "tier1_governance_summary": dict(tier1_governance_summary),
    }
    if adapter_dispatch_meta is not None:
        payload["adapter_dispatch_meta"] = dict(adapter_dispatch_meta)
    _validate_meta_keys_allowlist(payload)
    return payload


def _validate_meta_keys_allowlist(payload: Mapping[str, Any]) -> None:
    """v2.1.0 completion plan §3.5: enforce the receipt-side `*_meta`
    allowlist. Raises `ReceiptBuildError` for any disallowed key.

    Pattern-match rule (NOT additive): non-`*_meta` keys are unaffected
    by this gate; only keys whose shape matches `_META_KEY_REGEX` are
    checked against `_ALLOWED_RECEIPT_META_KEYS`.
    """
    for key in payload:
        if not isinstance(key, str):
            continue
        if not _META_KEY_REGEX.fullmatch(key):
            continue
        if key not in _ALLOWED_RECEIPT_META_KEYS:
            raise ReceiptBuildError(
                f"receipt payload contains *_meta sibling key {key!r} not "
                f"in v1.1 allowlist {sorted(_ALLOWED_RECEIPT_META_KEYS)!r}; "
                f"new *_meta keys require a schema_version bump"
            )


def seal_receipt_payload(payload: Mapping[str, Any]) -> dict:
    """Compute `sha256` over canonical_hash(payload-sans-sha256)."""
    if "sha256" in payload:
        raise ValueError("seal_receipt_payload: payload already carries sha256")
    sealed = dict(payload)
    sealed["sha256"] = canonical_hash(dict(payload))
    return sealed


def write_receipt_atomic(
    sealed: Mapping[str, Any],
    cwd: Path,
) -> Path:
    """Atomic O_CREAT|O_EXCL write of `<cwd>/.launchpad/scaffold-receipt.json`.

    fsync(fd) + fsync(dirfd) + F_FULLFSYNC on darwin.

    On FileExistsError: raises ReceiptWriteError with reason
    `scaffold_receipt_already_exists` and a hint about concurrent invocation.
    """
    line = json.dumps(
        dict(sealed),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    encoded = line.encode("utf-8")

    launchpad = cwd / ".launchpad"
    launchpad.mkdir(parents=True, exist_ok=True)
    target = launchpad / RECEIPT_FILENAME

    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ReceiptWriteError(
            (
                f"{target} already exists; check whether scaffold-stack was "
                f"concurrently invoked, or remove .launchpad/scaffold-receipt.json "
                f"and re-run /lp-scaffold-stack"
            ),
            reason="scaffold_receipt_already_exists",
        ) from exc

    try:
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
        os.write(fd, encoded)
        os.fsync(fd)
        if sys.platform == "darwin":
            try:
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            except (OSError, AttributeError):
                pass
    finally:
        os.close(fd)

    try:
        dirfd = os.open(str(launchpad), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except OSError:
        pass

    return target


def write_receipt(
    *,
    decision_sha256: str,
    decision_nonce: str,
    layers_materialized: Sequence[Mapping[str, Any]],
    cross_cutting_files: Sequence[str],
    toolchains_detected: Sequence[str],
    secret_scan_passed: bool,
    cwd: Path,
    tier1_governance_summary: Mapping[str, Any] | None = None,
    scaffolded_at: str | None = None,
    version: str | None = None,
    adapter_dispatch_meta: Mapping[str, Any] | None = None,
) -> tuple[Path, dict]:
    """Build + seal + atomic write. Returns (path, sealed_payload)."""
    payload = build_receipt_payload(
        decision_sha256=decision_sha256,
        decision_nonce=decision_nonce,
        layers_materialized=layers_materialized,
        cross_cutting_files=cross_cutting_files,
        toolchains_detected=toolchains_detected,
        secret_scan_passed=secret_scan_passed,
        tier1_governance_summary=tier1_governance_summary,
        scaffolded_at=scaffolded_at,
        version=version,
        adapter_dispatch_meta=adapter_dispatch_meta,
    )
    sealed = seal_receipt_payload(payload)
    target = write_receipt_atomic(sealed, cwd)
    return target, sealed


__all__ = [
    "RECEIPT_FILENAME",
    "LayerReceiptEntry",
    "ReceiptBuildError",
    "ReceiptWriteError",
    "build_receipt_payload",
    "seal_receipt_payload",
    "write_receipt",
    "write_receipt_atomic",
]
