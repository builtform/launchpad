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

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from atomic_io import atomic_write_excl
from decision_integrity import canonical_hash
from lp_pick_stack import (
    IDENTITY_COPYRIGHT_FORBIDDEN_CHARS,
    IDENTITY_COPYRIGHT_HOLDER_RE,
    IDENTITY_EMAIL_RE,
    IDENTITY_PLACEHOLDERS,
    IDENTITY_PROJECT_NAME_LITERAL_REJECTS,
    IDENTITY_PROJECT_NAME_RE,
    IDENTITY_REPO_URL_RE,
    LICENSE_ENUM,
    LICENSE_OTHER_FORBIDDEN_SUBSTRINGS,
    LICENSE_OTHER_MAX_BYTES,
    SCHEMA_VERSION_V2_1,
    WRITTEN_DECISION_VERSION,
)

# Constant filename per HANDSHAKE §4 schema.
DECISION_FILENAME = "scaffold-decision.json"
RATIONALE_FILENAME = "rationale.md"

# Plugin manifest path used by `read_running_plugin_version()`. Resolved
# relative to the scripts/ directory so the lookup works whether the plugin
# is checked out as a workspace or installed via Claude marketplace.
_PLUGIN_JSON = (
    Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "plugin.json"
)


class IdentityValidationError(ValueError):
    """Raised by validate_identity() when an identity field fails its allowlist.

    Carries `field` so the caller can surface a structured error with the
    exact field that needs correction (e.g., re-prompt only that field).
    """

    def __init__(self, message: str, field: str):
        super().__init__(message)
        self.field = field

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
    target = cwd / ".launchpad" / RATIONALE_FILENAME

    try:
        atomic_write_excl(target, encoded, trusted_root=cwd)
    except FileExistsError as exc:
        raise DecisionWriteError(
            f"{target} already exists; remove .launchpad/ and re-run /lp-pick-stack",
            reason="scaffold_decision_already_exists",
        ) from exc

    return target, hashlib.sha256(encoded).hexdigest()


def read_running_plugin_version() -> str:
    """Read the running plugin version from `plugins/launchpad/.claude-plugin/plugin.json`.

    Used to seal the v2.1 envelope's `plugin_version` field at /lp-pick-stack
    time. /lp-scaffold-stack and /lp-bootstrap (Phase 3+) compare against
    this recorded value and abort on mismatch per V3 plan §11.1, preventing
    a `/plugin update` between pipeline steps from silently invalidating the
    sealed manifest.

    Returns the literal `version` string from plugin.json. Raises
    FileNotFoundError if the manifest is missing (a defect in the plugin
    install, not a runtime user error).
    """
    text = _PLUGIN_JSON.read_text(encoding="utf-8")
    return str(json.loads(text)["version"])


# v2.1 Codex PR #50 Greptile #5 (D5): catalog-shortname → STACK_ID_ACTIVE_ENUM
# fallback mapping. Composition-first matches happen elsewhere; this map
# resolves uncomposed singletons. Ordered as in plan §2 D5.
_CATALOG_FALLBACK_MAP: Mapping[str, str] = {
    # Catalog-fallback: each maps to a STACK_ID_ACTIVE_ENUM member.
    "supabase": "generic",
    "expo": "generic",
    "eleventy": "generic",
    "hugo": "generic",
    "hono": "generic",          # uncomposed singleton; composition-first
                                # promotes ["next", "hono"] to nextjs_hono_cloudflare.
    "next": "nextjs_standalone",
    "django": "python_generic", # NOT python_django at v2.1 — widening invariant
                                # deferred to BL-263.
    "fastapi": "python_generic",
}

# v2.1 Codex PR #50 Greptile #5 (D5): composition reductions. Composition-
# first ordering — these matches fire BEFORE the singleton fallback so
# `["next", "fastapi"]` → `["nextjs_fastapi"]` rather than
# `["nextjs_standalone", "python_generic"]`.
_COMPOSITION_REDUCTIONS: Mapping[frozenset[str], str] = {
    frozenset({"next", "fastapi"}): "nextjs_fastapi",
    frozenset({"next", "hono"}): "nextjs_hono_cloudflare",
}


def derive_stacks(layers: Sequence[Mapping[str, Any]]) -> list[str]:
    """Derive the v2.1 envelope's flat `stacks` array from the layers list.

    First-occurrence-preserved deduplication: a polyglot project with
    `[{stack: astro, role: frontend-main}, {stack: astro, role:
    frontend-dashboard}, {stack: nextjs_standalone, role: backend}]` collapses
    to `["astro", "nextjs_standalone"]`. Order matches first appearance in
    `layers` so /lp-scaffold-stack can iterate stacks deterministically.

    v2.1 Codex PR #50 Greptile #5 (D5): catalog-shortname stacks (e.g.
    `next`, `django`, `supabase`) translate through the composition-first
    + singleton fallback to STACK_ID_ACTIVE_ENUM members so downstream
    `decision_validator.validate_decision()` v1.1 envelope check passes.
    Stacks already in the active enum (e.g. `astro`, `nextjs_standalone`,
    `python_django`) pass through unchanged. The per-layer `layers[].stack`
    field is NOT translated — scaffolders.yml still consumes catalog
    shortnames; only the top-level flat `stacks` array is translated for
    cross-tooling consumption.
    """
    seen: dict[str, None] = {}
    for layer in layers:
        stack = layer.get("stack")
        if isinstance(stack, str) and stack and stack not in seen:
            seen[stack] = None
    raw_ids = list(seen.keys())

    # Composition-first: check the multi-stack reductions before
    # singleton fallback.
    raw_set = frozenset(raw_ids)
    composed: list[str] = []
    consumed: set[str] = set()
    for combo, target_id in _COMPOSITION_REDUCTIONS.items():
        if combo.issubset(raw_set):
            composed.append(target_id)
            consumed.update(combo)

    # Singleton fallback for unconsumed ids; pass through ids already in
    # the active enum unchanged.
    try:
        from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM
    except ImportError:  # pragma: no cover
        STACK_ID_ACTIVE_ENUM = frozenset()  # type: ignore[assignment]
    out: list[str] = []
    out.extend(composed)
    for sid in raw_ids:
        if sid in consumed:
            continue
        if sid in STACK_ID_ACTIVE_ENUM:
            if sid not in out:
                out.append(sid)
        elif sid in _CATALOG_FALLBACK_MAP:
            mapped = _CATALOG_FALLBACK_MAP[sid]
            if mapped not in out:
                out.append(mapped)
        else:
            # Unknown id — leave unchanged so the validator surfaces a
            # specific rejection at validate_decision time rather than a
            # silent translation hiding the bug.
            if sid not in out:
                out.append(sid)
    return out


def default_unset_identity() -> dict[str, Any]:
    """Build the all-placeholder identity block written when PII opt-in is False.

    /lp-update-identity (Phase 10) detects placeholder values via the
    `<...>` leading/trailing-bracket shape check in validate_identity and
    re-asks the PII Y/N prompt. The placeholder strings are documented in
    HANDSHAKE §10.v2.1 so downstream consumers (LICENSE/CONTRIBUTING
    renderers) can render them verbatim or substitute their own defaults.

    Five identity fields (matching HANDSHAKE §10.v2.1 Phase 0.3 lock):
    project_name, email, copyright_holder, repo_url, license. The
    `license_other_body` sub-field is only meaningful when `license=Other`.
    """
    return {
        "pii_opt_in": False,
        "project_name": IDENTITY_PLACEHOLDERS["project_name"],
        "email": IDENTITY_PLACEHOLDERS["email"],
        "copyright_holder": IDENTITY_PLACEHOLDERS["copyright_holder"],
        "repo_url": IDENTITY_PLACEHOLDERS["repo_url"],
        "license": "Other",
        "license_other_body": "",
    }


def validate_identity(
    identity: Mapping[str, Any],
    *,
    strict_no_placeholders: bool = False,
) -> None:
    """Validate an identity dict against the V3 plan §10.v2.1 allowlists.

    Placeholder values (matching `<lower-with-dashes>`) are accepted in any
    field that allows them (author_name, author_email, copyright_holder,
    repo_url) so the PII opt-out path round-trips through the validator.

    Phase 10 (DA2 + security-auditor F3): when `strict_no_placeholders` is
    True, placeholder shapes are REJECTED rather than round-tripped.
    /lp-update-identity passes `strict=True` because re-sealing identity
    with placeholder values would silently degrade prior PII opt-in state.

    Raises IdentityValidationError(field=...) on the first failure. The
    caller wires `field` into a structured re-prompt or rejection message.
    """
    if not isinstance(identity, Mapping):
        raise IdentityValidationError(
            f"identity must be a mapping; got {type(identity).__name__}",
            field="<root>",
        )

    pii_opt_in = identity.get("pii_opt_in")
    if not isinstance(pii_opt_in, bool):
        raise IdentityValidationError(
            "identity.pii_opt_in must be a boolean", field="pii_opt_in"
        )

    def _placeholder_or(value: Any, regex, field: str) -> None:
        if not isinstance(value, str):
            raise IdentityValidationError(
                f"identity.{field} must be a string", field=field
            )
        if value.startswith("<") and value.endswith(">"):
            if strict_no_placeholders:
                raise IdentityValidationError(
                    f"identity.{field} contains placeholder shape; refused under strict_no_placeholders",
                    field=field,
                )
            return  # placeholder; round-trip allowed (non-strict)
        if not regex.fullmatch(value):
            raise IdentityValidationError(
                f"identity.{field}={value!r} fails allowlist regex",
                field=field,
            )

    project_name = identity.get("project_name")
    if not isinstance(project_name, str):
        raise IdentityValidationError(
            "identity.project_name must be a string", field="project_name"
        )
    if project_name.startswith("<") and project_name.endswith(">"):
        if strict_no_placeholders:
            raise IdentityValidationError(
                "identity.project_name contains placeholder shape; refused under strict_no_placeholders",
                field="project_name",
            )
    else:
        # Phase 1+2 retroactive amendment A2: explicit reject for "." and
        # ".." even though the leading-letter regex already excludes them.
        if project_name in IDENTITY_PROJECT_NAME_LITERAL_REJECTS:
            raise IdentityValidationError(
                f"identity.project_name={project_name!r} is reserved (path traversal); "
                f"pick a name starting with a letter",
                field="project_name",
            )
        if not IDENTITY_PROJECT_NAME_RE.fullmatch(project_name):
            raise IdentityValidationError(
                f"identity.project_name={project_name!r} fails allowlist regex",
                field="project_name",
            )

    _placeholder_or(identity.get("email"), IDENTITY_EMAIL_RE, "email")

    copyright_holder = identity.get("copyright_holder")
    if not isinstance(copyright_holder, str):
        raise IdentityValidationError(
            "identity.copyright_holder must be a string", field="copyright_holder"
        )
    if copyright_holder.startswith("<") and copyright_holder.endswith(">"):
        if strict_no_placeholders:
            raise IdentityValidationError(
                "identity.copyright_holder contains placeholder shape; refused under strict_no_placeholders",
                field="copyright_holder",
            )
    else:
        if not IDENTITY_COPYRIGHT_HOLDER_RE.fullmatch(copyright_holder):
            raise IdentityValidationError(
                f"identity.copyright_holder fails printable-ASCII allowlist",
                field="copyright_holder",
            )
        bad = IDENTITY_COPYRIGHT_FORBIDDEN_CHARS.intersection(copyright_holder)
        if bad:
            raise IdentityValidationError(
                f"identity.copyright_holder contains forbidden chars {sorted(bad)}",
                field="copyright_holder",
            )

    _placeholder_or(identity.get("repo_url"), IDENTITY_REPO_URL_RE, "repo_url")

    license_value = identity.get("license")
    if license_value not in LICENSE_ENUM:
        raise IdentityValidationError(
            f"identity.license={license_value!r} not in {sorted(LICENSE_ENUM)}",
            field="license",
        )

    license_other_body = identity.get("license_other_body", "")
    if not isinstance(license_other_body, str):
        raise IdentityValidationError(
            "identity.license_other_body must be a string",
            field="license_other_body",
        )
    if license_value == "Other":
        body_bytes = license_other_body.encode("utf-8")
        if len(body_bytes) > LICENSE_OTHER_MAX_BYTES:
            raise IdentityValidationError(
                f"identity.license_other_body exceeds {LICENSE_OTHER_MAX_BYTES}-byte cap",
                field="license_other_body",
            )
        if not all(0x20 <= ord(c) <= 0x7E or c == "\n" for c in license_other_body):
            raise IdentityValidationError(
                "identity.license_other_body must be printable ASCII",
                field="license_other_body",
            )
        for forbidden in LICENSE_OTHER_FORBIDDEN_SUBSTRINGS:
            if forbidden in license_other_body:
                raise IdentityValidationError(
                    f"identity.license_other_body contains forbidden substring {forbidden!r}",
                    field="license_other_body",
                )
    elif license_other_body:
        raise IdentityValidationError(
            f"identity.license_other_body must be empty when license={license_value!r}",
            field="license_other_body",
        )


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
    identity: Mapping[str, Any] | None = None,
    plugin_version: str | None = None,
) -> dict:
    """Construct the scaffold-decision.json payload (sans `sha256` field).

    The `sha256` field is computed by `seal_decision_payload()` over the
    canonical hash of this payload. Splitting build/seal lets unit tests
    assert the payload shape without the chicken-and-egg of the integrity
    envelope.

    v2.1 envelope additions (§11.1, §10.v2.1 acceptance rules):
      - `schema_version: "1.1"` — the v2.1 reader indicator. Legacy v2.0
        readers that key off `version` continue to see "1.0".
      - `plugin_version` — the running plugin version, sealed at writer
        time. /lp-scaffold-stack and /lp-bootstrap abort on mismatch with
        the runtime plugin version (§11.1 plugin-update-mid-pipeline guard).
      - `stacks` — flat dedup'd array derived from layers[].stack.
      - `identity` — sealed identity block. When the caller passes None,
        we emit the all-placeholder default and the caller is responsible
        for verifying that the project's intended PII posture matches.

    Per HANDSHAKE §4 + §1.5 strip-back: `brainstorm_session_id` is OMITTED.
    """
    if monorepo is None:
        monorepo = len(layers) > 1

    if identity is None:
        identity = default_unset_identity()
    else:
        validate_identity(identity)

    if plugin_version is None:
        plugin_version = read_running_plugin_version()

    payload: dict[str, Any] = {
        "version": version or WRITTEN_DECISION_VERSION,
        "schema_version": SCHEMA_VERSION_V2_1,
        "plugin_version": plugin_version,
        "layers": [dict(layer) for layer in layers],
        "stacks": derive_stacks(layers),
        "monorepo": bool(monorepo),
        "matched_category_id": matched_category_id,
        "rationale_path": f".launchpad/{RATIONALE_FILENAME}",
        "rationale_sha256": rationale_sha256,
        "rationale_summary": [dict(s) for s in rationale_summary],
        "identity": dict(identity),
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
    target = cwd / ".launchpad" / DECISION_FILENAME

    try:
        atomic_write_excl(target, encoded, trusted_root=cwd)
    except FileExistsError as exc:
        raise DecisionWriteError(
            f"{target} already exists; remove .launchpad/ and re-run /lp-pick-stack",
            reason="scaffold_decision_already_exists",
        ) from exc

    return target


def read_decision_atomic(cwd: Path) -> dict[str, Any]:
    """Read `.launchpad/scaffold-decision.json` and return the parsed dict.

    Phase 10 helper (per cycle-3 pattern-finder P3-1): the only readers
    that ship today are `plugin-config-loader.read_scaffold_decision()`
    (returns a NamedTuple wrapper for diagnostics) and engine-side raw
    `json.loads`. /lp-update-identity needs a parsed dict for in-process
    re-write, so we expose this convenience reader rather than threading
    NamedTuple unwrapping through Phase 10's engine.

    Raises FileNotFoundError if the file is absent; raises ValueError
    (from json.loads) if the contents are malformed. Caller decides how
    to translate (IdentityUpdateErrorCode.SCAFFOLD_DECISION_MISSING etc.).
    """
    target = cwd / ".launchpad" / DECISION_FILENAME
    text = target.read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(
            f"{target} top-level is not a JSON object (got {type(payload).__name__})"
        )
    return payload


def re_seal_decision_atomic(
    cwd: Path,
    *,
    update_fn,
) -> dict[str, Any]:
    """Read scaffold-decision, apply `update_fn(payload) -> payload`, re-seal.

    Phase 10 atomic re-seal helper (per DA9 + adversarial #1):
      * Reads the on-disk envelope via `read_decision_atomic`.
      * Captures the existing `generated_at` value BEFORE delegating to
        `update_fn`.
      * Applies `update_fn(mutable_dict)` so the caller can mutate any
        field in-place (identity block, plugin_version, etc.).
      * Strips the prior `sha256` field, re-asserts `generated_at` byte-
        identical to the pre-edit value (DA9 immutability), re-seals via
        `seal_decision_payload`.
      * Atomically writes via `atomic_write_replace` (NOT `atomic_write_excl`
        per security-auditor F5 -- the file ALREADY exists for a re-seal).

    Returns the new sealed payload. Caller is responsible for sentinel
    lifecycle around this call; this function performs the on-disk
    mutation only.
    """
    from atomic_io import atomic_write_replace
    payload = read_decision_atomic(cwd)
    pre_generated_at = payload.get("generated_at")

    update_fn(payload)

    # DA9 + adversarial P1: read-old, copy-forward, byte-identical assert.
    if pre_generated_at is not None and payload.get("generated_at") != pre_generated_at:
        # Caller's update_fn must NOT mutate generated_at. Restore.
        payload["generated_at"] = pre_generated_at

    payload.pop("sha256", None)
    sealed = seal_decision_payload(payload)

    line = json.dumps(
        sealed,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    target = cwd / ".launchpad" / DECISION_FILENAME
    atomic_write_replace(target, line.encode("utf-8"), mode=0o600, trusted_root=cwd)
    return sealed


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
    identity: Mapping[str, Any] | None = None,
    plugin_version: str | None = None,
) -> tuple[Path, dict]:
    """End-to-end build + seal + atomic write.

    Convenience wrapper around build_decision_payload + seal_decision_payload
    + write_decision_atomic. Returns (target_path, sealed_payload).

    `identity` and `plugin_version` extend the v1.1 envelope per V3 plan
    §11.1. Both default to safe placeholders when omitted: identity becomes
    the all-placeholder block (PII opt-out posture) and plugin_version is
    read from `plugins/launchpad/.claude-plugin/plugin.json` at write time.
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
        identity=identity,
        plugin_version=plugin_version,
    )
    sealed = seal_decision_payload(payload)
    target = write_decision_atomic(sealed, cwd)
    return target, sealed


__all__ = [
    "DECISION_FILENAME",
    "DecisionWriteError",
    "EMPTY_FILE_SHA256",
    "IdentityValidationError",
    "RATIONALE_FILENAME",
    "build_decision_payload",
    "compute_bound_cwd",
    "default_unset_identity",
    "derive_stacks",
    "read_decision_atomic",
    "read_running_plugin_version",
    "re_seal_decision_atomic",
    "seal_decision_payload",
    "validate_identity",
    "write_decision_atomic",
    "write_decision_file",
    "write_rationale_atomic",
]
