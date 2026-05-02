"""Decision-file writer (Phase 2 §4.1 Step 6).

Builds the integrity envelope per HANDSHAKE §4 and atomically writes
`.launchpad/scaffold-decision.json` via `os.open(... O_WRONLY|O_CREAT|O_EXCL,
0o600)` + fsync + F_FULLFSYNC on darwin.

Per HANDSHAKE §1.5 strip-back: `brainstorm_session_id` field is OMITTED at
v2.0 (BL-235 deferred). Validation rule 12 does NOT ship at v2.0; this
writer does NOT read `.launchpad/.first-run-marker` for a session_id.

Per HANDSHAKE §7 concurrent-/lp-pick-stack subsection (Layer 9 hardening):
the engine writes `.launchpad/rationale.md` FIRST with O_CREAT|O_EXCL, then
this writer writes `scaffold-decision.json` SECOND with O_CREAT|O_EXCL. On
FileExistsError from EITHER file, the engine refuses with reason
`scaffold_decision_already_exists`. The rationale-first ordering closes the
L9 footgun where the loser's rationale.md would otherwise overwrite the
survivor's, surfacing later as a confusing scaffold-stack rationale_sha256
mismatch.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from decision_integrity import canonical_hash
from lp_pick_stack import WRITTEN_DECISION_VERSION

# Constant filename per HANDSHAKE §4 schema.
DECISION_FILENAME = "scaffold-decision.json"
RATIONALE_FILENAME = "rationale.md"

# rationale_sha256 sentinel for --no-rationale flag mode (per Phase 2 §4.1
# Step 5: when --no-rationale skips rationale.md write, rationale_sha256 is
# the empty-file hash).
EMPTY_FILE_SHA256 = hashlib.sha256(b"").hexdigest()


class DecisionWriteError(RuntimeError):
    """Raised when the decision-file write fails for a structured reason.

    Carries `reason` field that the engine wires into the user-facing error
    + telemetry. v2.0 reasons:

    - `scaffold_decision_already_exists`: O_CREAT|O_EXCL refused (concurrent
      pick-stack or stale `.launchpad/`)
    - `bound_cwd_compute_failed`: realpath/stat failed unexpectedly
    """

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


def _utc_now_iso_sec() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_bound_cwd(cwd: Path) -> dict:
    """Compute the (realpath, st_dev, st_ino) triple per HANDSHAKE §4 rule 11.

    Realpath is computed via `os.path.realpath`, stat via `os.stat`. Both run
    against the resolved cwd (NOT a path the caller might have crafted with a
    relative-path indirection).
    """
    try:
        cwd_real = os.path.realpath(str(cwd))
        st = os.stat(cwd_real)
    except OSError as exc:
        raise DecisionWriteError(
            f"bound_cwd compute failed: {exc}", reason="bound_cwd_compute_failed"
        ) from exc
    return {
        "realpath": cwd_real,
        "st_dev": int(st.st_dev),
        "st_ino": int(st.st_ino),
    }


def write_rationale_atomic(
    body: str,
    cwd: Path,
) -> tuple[Path, str]:
    """Write `body` to `<cwd>/.launchpad/rationale.md` via O_CREAT|O_EXCL.

    Returns (rationale_path, rationale_sha256). On FileExistsError, raises
    DecisionWriteError(reason="scaffold_decision_already_exists").

    Per HANDSHAKE §7: this is invoked FIRST, before the decision-file write,
    so a concurrent pick-stack loser refuses BEFORE writing decision.json
    (closes the L9 hash-mismatch footgun).
    """
    encoded = body.encode("utf-8")
    launchpad = cwd / ".launchpad"
    launchpad.mkdir(parents=True, exist_ok=True)
    target = launchpad / RATIONALE_FILENAME

    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise DecisionWriteError(
            f"{target} already exists; remove .launchpad/ and re-run /lp-pick-stack",
            reason="scaffold_decision_already_exists",
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

    return target, hashlib.sha256(encoded).hexdigest()


def build_decision_payload(
    *,
    layers: Sequence[Mapping[str, Any]],
    matched_category_id: str,
    rationale_summary: Sequence[Mapping[str, Any]],
    rationale_sha256: str,
    cwd: Path,
    monorepo: bool | None = None,
    nonce: str | None = None,
    generated_at: str | None = None,
    version: str | None = None,
) -> dict:
    """Construct the scaffold-decision.json payload (sans `sha256` field).

    The `sha256` field is computed by `seal_decision_payload()` over the
    canonical hash of this payload. Splitting build/seal lets unit tests
    assert the payload shape without the chicken-and-egg of the integrity
    envelope.

    Per HANDSHAKE §4 + §1.5 strip-back: `brainstorm_session_id` is OMITTED.
    """
    if monorepo is None:
        monorepo = len(layers) > 1

    payload: dict[str, Any] = {
        "version": version or WRITTEN_DECISION_VERSION,
        "layers": [dict(layer) for layer in layers],
        "monorepo": bool(monorepo),
        "matched_category_id": matched_category_id,
        "rationale_path": f".launchpad/{RATIONALE_FILENAME}",
        "rationale_sha256": rationale_sha256,
        "rationale_summary": [dict(s) for s in rationale_summary],
        "generated_by": "/lp-pick-stack",
        "generated_at": generated_at or _utc_now_iso_sec(),
        "nonce": nonce or uuid.uuid4().hex,
        "bound_cwd": compute_bound_cwd(cwd),
    }
    return payload


def seal_decision_payload(payload: Mapping[str, Any]) -> dict:
    """Compute `sha256` over canonical_hash(payload) and return the sealed dict.

    Raises ValueError if `payload` already carries a `sha256` field (caller
    bug — sealing twice would compute over the prior seal).
    """
    if "sha256" in payload:
        raise ValueError("seal_decision_payload: payload already carries sha256")
    sealed = dict(payload)
    sealed["sha256"] = canonical_hash(dict(payload))
    return sealed


def write_decision_atomic(
    sealed: Mapping[str, Any],
    cwd: Path,
) -> Path:
    """Write the sealed decision dict to `.launchpad/scaffold-decision.json`.

    Atomic write via O_CREAT|O_EXCL + fsync + F_FULLFSYNC on darwin. On
    FileExistsError, raises DecisionWriteError(reason=
    `scaffold_decision_already_exists`).

    The serialization uses the same canonical JSON shape (sort_keys + tight
    separators + ensure_ascii) the canonical_hash function uses, so the
    on-disk bytes are byte-identical to what the consumer would
    re-canonicalize for re-validation.
    """
    import json

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
    target = launchpad / DECISION_FILENAME

    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise DecisionWriteError(
            f"{target} already exists; remove .launchpad/ and re-run /lp-pick-stack",
            reason="scaffold_decision_already_exists",
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


def write_decision_file(
    *,
    layers: Sequence[Mapping[str, Any]],
    matched_category_id: str,
    rationale_summary: Sequence[Mapping[str, Any]],
    rationale_sha256: str,
    cwd: Path,
    monorepo: bool | None = None,
    nonce: str | None = None,
    generated_at: str | None = None,
    version: str | None = None,
) -> tuple[Path, dict]:
    """End-to-end build + seal + atomic write.

    Convenience wrapper around build_decision_payload + seal_decision_payload
    + write_decision_atomic. Returns (target_path, sealed_payload).
    """
    payload = build_decision_payload(
        layers=layers,
        matched_category_id=matched_category_id,
        rationale_summary=rationale_summary,
        rationale_sha256=rationale_sha256,
        cwd=cwd,
        monorepo=monorepo,
        nonce=nonce,
        generated_at=generated_at,
        version=version,
    )
    sealed = seal_decision_payload(payload)
    target = write_decision_atomic(sealed, cwd)
    return target, sealed


__all__ = [
    "DECISION_FILENAME",
    "DecisionWriteError",
    "EMPTY_FILE_SHA256",
    "RATIONALE_FILENAME",
    "build_decision_payload",
    "compute_bound_cwd",
    "seal_decision_payload",
    "write_decision_atomic",
    "write_decision_file",
    "write_rationale_atomic",
]
