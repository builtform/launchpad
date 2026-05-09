"""Bootstrap-manifest writer (v2.1 Phase 3, plan section 2.1 + 3.3 + 3.8).

Writes `.launchpad/bootstrap-manifest.json` with the schema 1.0 envelope:

  * `manifest_schema_version: "1.0"`
  * `plugin_version: <semver>` (from plugin.json)
  * `last_render_timestamp: <UTC ISO-8601>`
  * `files: [<entry>, ...]` per `BootstrapManifestEntry`
  * `security_fields: []` (always empty in v2.1; canonical reader treats
    non-empty as `unsupported_security_extension` abort per harden B9 +
    section 6.2 v2.2-downgrade defense)

Adding a new infrastructure file is additive (a new entry in `files[]` plus
extending `INFRASTRUCTURE_FILES`); no `manifest_schema_version` bump.
Removing or renaming an entry IS a schema change (bumps to 1.1 + canonical
reader migration rule per Phase 1 ladder) per the C5 docstring contract.

Reads via Phase 1's canonical
`plugin-config-loader.read_bootstrap_manifest(cwd)` (4-rule ladder); never
re-reads the file by hand. The reader does NOT verify per-file sha256
fields; that integrity check is `verify_source_template_shas()` here +
the engine.

Per harden B16: `rendered_content_sha256` is updated only on full-run
success. Partial-failure runs do NOT write the manifest, preserving the
prior shas for the next attempt.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import atomic_write_replace  # noqa: E402
from plugin_default_generators._renderer_base import (  # noqa: E402
    GENERATORS_ROOT,
    sha256_file,
)

from lp_bootstrap import (  # noqa: E402
    INFRASTRUCTURE_FILES,
    LAUNCHPAD_DIR_NAME,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    BootstrapErrorCode,
)

# --- Per-module typed exception (section 3.7) -----------------------------

class BootstrapManifestError(RuntimeError):
    """Manifest read/write/integrity failure raised by this module.

    `.reason: BootstrapErrorCode`, `.path: Path | None`, `.remediation: str`
    let the engine wire a structured `BootstrapError` into the public
    `BootstrapResult.errors` surface.
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


# --- Manifest envelope ----------------------------------------------------

@dataclass(frozen=True)
class BootstrapManifestEntry:
    """One row in the manifest's `files[]` array.

    `path` is POSIX-relative-to-project-root, normalized via
    `_normalize_path()`. `policy` is the snake-cased
    `BootstrapPolicy.value`; `mode` is the integer chmod target stored as
    octal-style int (e.g., 0o644 == 420). Stored as int rather than string
    to round-trip cleanly through `json.dumps` (an octal string would need
    bespoke parsing).
    """
    path: str
    source_template_sha256: str
    rendered_content_sha256: str
    policy: str
    mode: int


@dataclass(frozen=True)
class BootstrapManifest:
    """Schema 1.0 envelope per section 3.8.

    `security_fields` is reserved for forward-compat security extensions
    (e.g., signed-template attestations in v2.2). Always empty in v2.1.
    Canonical reader treats non-empty as an `unsupported_security_extension`
    abort.

    v2.1 Codex PR #50 P1.D (D4): `created_at` is sealed at write-time
    (alongside the existing `last_render_timestamp`). The `--recover`
    flow reads `created_at` to decide whether to unlink a stale manifest
    (`manifest.created_at < sentinel.acquired_at` is provably stale).
    Legacy manifests without `created_at` fall back to filesystem mtime
    with a stderr warning per D4.
    """
    manifest_schema_version: str
    plugin_version: str
    last_render_timestamp: str
    files: tuple[BootstrapManifestEntry, ...]
    security_fields: tuple[Any, ...] = field(default_factory=tuple)
    created_at: str = ""


# --- Path normalization (section 3.3) -------------------------------------

def _normalize_path(raw: str) -> str:
    """Normalize a manifest target path to POSIX-relative-to-project-root.

    Rules:
      * Forward slashes always (cross-platform).
      * No leading `./` (strip).
      * No `..` traversal anywhere in the path -> raises with
        `PATH_TRAVERSAL_REJECTED`.
      * No absolute paths -> raises with `PATH_TRAVERSAL_REJECTED`.

    Called both during manifest write AND during `--refresh <path>`
    argument validation per harden A15. Case-folded variant rejection on
    case-insensitive filesystems is performed by the engine via
    `Path.resolve()` of the eventual target relative to cwd; this helper is
    purely string-level.
    """
    if not isinstance(raw, str):
        raise BootstrapManifestError(
            f"path must be a string; got {type(raw).__name__}",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            remediation="pass a string path relative to the project root",
        )

    s = raw.replace("\\", "/")
    if s.startswith("./"):
        s = s[2:]

    if not s:
        raise BootstrapManifestError(
            "path must be non-empty",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            remediation="pass a non-empty relative path",
        )

    if s.startswith("/"):
        raise BootstrapManifestError(
            f"path {raw!r} is absolute; only project-root-relative paths allowed",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            remediation=(
                "remove the leading slash so the path is relative to the "
                "project root"
            ),
        )

    parts = s.split("/")
    if any(p == ".." for p in parts):
        raise BootstrapManifestError(
            f"path {raw!r} contains parent-directory traversal (`..`)",
            reason=BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
            remediation=(
                "remove `..` segments; refresh paths must remain inside the "
                "project root"
            ),
        )

    return s


# --- Source-template SHA cache (harden B3) --------------------------------
#
# Lazy module-load cache: computed once on first access, frozen via
# `MappingProxyType`, immutable in single Python process. Lazy because Slice
# A lands before Slice B writes the .j2 templates; loading the SHAs at
# import time would fail the test suite during Slice A.
#
# After Slice B ships, the first access populates the cache and every
# subsequent `verify_source_template_shas()` call is a dict lookup.

_INFRA_TEMPLATE_ROOT: Path = GENERATORS_ROOT / "infrastructure"

_cached_source_template_shas: dict[str, str] | None = None


def compute_source_template_shas(
    *, root: Path | None = None
) -> Mapping[str, str]:
    """Compute the per-target sha of every .j2 source template.

    `root` defaults to `plugin_default_generators/infrastructure/`; tests
    may inject a tmp_path-based fixture root. Missing template files raise
    `BootstrapManifestError(reason=TEMPLATE_NOT_FOUND)` so a half-installed
    plugin surfaces fast.
    """
    base = root if root is not None else _INFRA_TEMPLATE_ROOT
    out: dict[str, str] = {}
    for template_relpath, target_relpath, _policy, _mode in INFRASTRUCTURE_FILES:
        template_path = base / template_relpath
        if not template_path.is_file():
            raise BootstrapManifestError(
                f"infrastructure template missing: {template_path}",
                reason=BootstrapErrorCode.TEMPLATE_NOT_FOUND,
                path=template_path,
                remediation=(
                    f"reinstall the LaunchPad plugin; expected template at "
                    f"plugin_default_generators/infrastructure/{template_relpath}"
                ),
            )
        out[target_relpath] = sha256_file(template_path)
    return MappingProxyType(out)


def source_template_shas() -> Mapping[str, str]:
    """Return the lazily-cached per-target source-template sha map.

    Cache is populated once per Python process. Tests that need a different
    root use `compute_source_template_shas(root=...)` directly.
    """
    global _cached_source_template_shas
    if _cached_source_template_shas is None:
        _cached_source_template_shas = dict(compute_source_template_shas())
    return MappingProxyType(_cached_source_template_shas)


def reset_source_template_shas_cache_for_tests() -> None:
    """Test-only helper: drops the cache so the next call re-reads templates.

    Production code never calls this. Surfaced as a public name (without
    leading underscore on the call site by tests) to make the intent
    explicit at the call site.
    """
    global _cached_source_template_shas
    _cached_source_template_shas = None


# --- Integrity check (section 3.8 (a)) ------------------------------------

def verify_source_template_shas(
    manifest: BootstrapManifest,
    *,
    expected_shas: Mapping[str, str] | None = None,
) -> None:
    """Validate manifest entries against the plugin-shipped template shas.

    `expected_shas` defaults to the cached `source_template_shas()`; tests
    may inject a fixture mapping. Mismatches raise
    `BootstrapManifestError(reason=MANIFEST_TAMPERED)` with structured
    remediation pointing at `--accept-plugin-version-drift` or `/plugin
    update`.

    The check covers ONLY plugin-shipped template integrity (section 3.8
    (a)). On-disk content fidelity (section 3.8 (b)) is the policy
    dispatcher's job and is a snapshot for next-run comparison, not an
    integrity claim.
    """
    if expected_shas is None:
        expected_shas = source_template_shas()

    by_path: dict[str, BootstrapManifestEntry] = {e.path: e for e in manifest.files}

    for target, expected in expected_shas.items():
        entry = by_path.get(target)
        if entry is None:
            raise BootstrapManifestError(
                f"manifest missing entry for plugin-shipped target {target!r}",
                reason=BootstrapErrorCode.MANIFEST_TAMPERED,
                path=Path(target),
                remediation=(
                    "Re-run /lp-bootstrap to regenerate, or pass "
                    "--accept-plugin-version-drift if the missing entry is "
                    "from a newer plugin version."
                ),
            )
        if entry.source_template_sha256 != expected:
            raise BootstrapManifestError(
                f"manifest source_template_sha256 mismatch for {target}: "
                f"manifest={entry.source_template_sha256!r}, "
                f"plugin={expected!r}",
                reason=BootstrapErrorCode.MANIFEST_TAMPERED,
                path=Path(target),
                remediation=(
                    "Either /plugin update was run between bootstraps "
                    "(pass --accept-plugin-version-drift to accept) or the "
                    "manifest was hand-edited (delete bootstrap-manifest.json "
                    "to force a clean re-bootstrap)."
                ),
            )


# --- Manifest write (section 3.8 + harden B16) ----------------------------

def _utc_iso8601_now() -> str:
    """UTC ISO-8601 timestamp with `Z` suffix; second precision is enough."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_manifest(
    *,
    plugin_version: str,
    files: Sequence[BootstrapManifestEntry],
    timestamp: str | None = None,
) -> BootstrapManifest:
    """Compose a `BootstrapManifest` envelope.

    Path-normalizes each entry's `.path` before assembling the tuple so
    every persisted entry round-trips through the same canonicalization
    that `_normalize_path()` enforces.
    """
    normalized: list[BootstrapManifestEntry] = []
    for entry in files:
        normalized.append(
            BootstrapManifestEntry(
                path=_normalize_path(entry.path),
                source_template_sha256=entry.source_template_sha256,
                rendered_content_sha256=entry.rendered_content_sha256,
                policy=entry.policy,
                mode=entry.mode,
            )
        )
    now = _utc_iso8601_now()
    return BootstrapManifest(
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
        plugin_version=plugin_version,
        last_render_timestamp=timestamp or now,
        files=tuple(normalized),
        # v2.1 Codex PR #50 P1.D (D4): seal created_at alongside
        # last_render_timestamp. Both reflect the same moment on first
        # write; readers compare against sentinel.acquired_at to detect
        # stale-manifest-after-abandoned-bootstrap.
        created_at=timestamp or now,
    )


def manifest_to_json_bytes(manifest: BootstrapManifest) -> bytes:
    """Encode the manifest as canonical JSON (sorted keys, `\\n` newline).

    Sorted keys + 2-space indent + trailing newline matches the existing
    receipt-writer / decision-writer convention so byte-for-byte diffs
    surface manifest changes in PR review the same way they surface other
    `.launchpad/*.json` envelopes.
    """
    payload: dict[str, Any] = {
        "manifest_schema_version": manifest.manifest_schema_version,
        "plugin_version": manifest.plugin_version,
        "last_render_timestamp": manifest.last_render_timestamp,
        "files": [asdict(e) for e in manifest.files],
        "security_fields": list(manifest.security_fields),
    }
    # v2.1 Codex PR #50 P1.D (D4): emit created_at when sealed.
    if manifest.created_at:
        payload["created_at"] = manifest.created_at
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_manifest(
    cwd: Path,
    manifest: BootstrapManifest,
) -> Path:
    """Atomically write the manifest under `<cwd>/.launchpad/`.

    Uses `atomic_io.atomic_write_replace` (tempfile-in-same-dir + os.replace +
    fsync + parent-dir fsync). Mode is 0o644 since the manifest is
    user-readable for inspection and round-trips through git diffs.

    Returns the resolved manifest path.

    Engine ordering (section 3.8 + harden B16): callers MUST only invoke
    this helper at the END of a successful render loop. Partial-failure
    runs preserve the prior manifest by NOT calling this function.
    """
    target = cwd / LAUNCHPAD_DIR_NAME / MANIFEST_FILENAME
    encoded = manifest_to_json_bytes(manifest)
    atomic_write_replace(target, encoded, mode=0o644, trusted_root=cwd)
    return target


# --- Re-export: BootstrapError + path helpers ------------------------------

__all__ = [
    "BootstrapManifest",
    "BootstrapManifestEntry",
    "BootstrapManifestError",
    "_normalize_path",
    "build_manifest",
    "compute_source_template_shas",
    "manifest_to_json_bytes",
    "reset_source_template_shas_cache_for_tests",
    "source_template_shas",
    "verify_source_template_shas",
    "write_manifest",
]
