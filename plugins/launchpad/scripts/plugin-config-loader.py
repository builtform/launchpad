#!/usr/bin/env python3
"""Load and validate `.launchpad/config.yml` once per process.

Contract:
  - Parse YAML into a single merged config object (pipeline / commands / paths)
  - Realpath-confinement on all `paths.*` values — reject absolute paths,
    `..` segments, and paths that resolve outside the repo root
  - Section-by-section re-parse on error: a malformed `commands:` does NOT
    prevent `/lp-kickoff` (which only reads `paths:`) from running. Unused
    sections log a warning; required sections fail hard.
  - `commands.*` is always-array; any `""` or scalar is coerced to a list
  - Caller queries the parsed object; never re-reads the file.

Usage (CLI):
    plugin-config-loader.py [--repo-root PATH] [--section pipeline|commands|paths|all]

Exit code 0 on success; 1 on unrecoverable parse/validation error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple


# --- Phase 5 v2.1 (DA4) -- --get-config-value path allowlist ---
#
# Module-level compiled regex. Single source of truth: depth bound is encoded
# directly in `{0,4}` (5 segments max). Phase 5 plan section 3.4 +
# architecture P3-C drops the runtime path.count(".") <= 4 duplicate check.
_PATH_ALLOWLIST_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+){0,4}$")
_PATH_LENGTH_CAP_BYTES = 256


# --- YAML parsing: minimal, no external dep ---
# PyYAML would be ideal but we don't want to add it to the vendor bundle just
# for config loading. Use a tiny hand-rolled parser that handles the shapes
# config.yml actually uses (flat dict, nested dict, lists, scalars).
# If config.yml grows more complex shapes, swap to yaml.safe_load. For now,
# tomllib can't help (TOML), and json is too rigid.
#
# Decision: use PyYAML from the _vendor dir if available, else bootstrap.


# Bootstrap the vendor dir onto sys.path before any YAML import.
_VENDOR = Path(__file__).resolve().parent / "plugin_stack_adapters" / "_vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))


def _load_yaml_safe(text: str) -> Any:
    """Load YAML using vendored PyYAML (falls back to system if vendor missing)."""
    try:
        import yaml  # type: ignore
    except ImportError:
        raise ConfigError(
            "PyYAML not available; vendor it into scripts/plugin-stack-adapters/_vendor/ "
            "or install system-wide."
        )
    return yaml.safe_load(text)


class ConfigError(Exception):
    """Raised for config-loading failures the caller should surface to the user."""


# --- Path confinement ---

def _confine_path(raw: str, repo_root: Path, key: str) -> str:
    """Validate a single `paths.*` value is inside the repo root.

    Rejects:
      - absolute paths (anything starting with '/')
      - paths containing '..' segments
      - paths that resolve outside repo_root after realpath expansion
    """
    if not isinstance(raw, str):
        raise ConfigError(f"paths.{key}: expected string, got {type(raw).__name__}")
    if raw.startswith("/"):
        raise ConfigError(f"paths.{key}={raw!r}: absolute paths are not allowed")
    if ".." in Path(raw).parts:
        raise ConfigError(f"paths.{key}={raw!r}: '..' segments are not allowed")

    # Resolve and verify containment
    resolved = (repo_root / raw).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        raise ConfigError(
            f"paths.{key}={raw!r} resolves to {resolved}, outside repo root {repo_root}"
        )
    return raw


# --- Command coercion ---

def _coerce_commands(commands: dict[str, Any]) -> dict[str, list[str]]:
    """Normalize every commands.* value to a list[str].

    Scalars become single-element lists; empty strings become empty lists
    (skip marker); missing keys become empty lists.
    """
    out: dict[str, list[str]] = {}
    for key in ("test", "typecheck", "lint", "format", "build", "dev"):
        val = commands.get(key, [])
        if isinstance(val, str):
            val = [val] if val else []
        elif isinstance(val, list):
            # Every item must be a string. Previously str(v) coerced YAML
            # scalars like true/123 or mappings into command strings —
            # silently turning typos into executed bogus commands. Refuse
            # non-strings with a clear ConfigError instead.
            cleaned: list[str] = []
            for i, v in enumerate(val):
                if v is None or (isinstance(v, str) and v == ""):
                    continue
                if not isinstance(v, str):
                    raise ConfigError(
                        f"commands.{key}[{i}]: expected string, got "
                        f"{type(v).__name__} (value={v!r}). Quote the "
                        "value in YAML if it should be passed literally."
                    )
                cleaned.append(v)
            val = cleaned
        else:
            raise ConfigError(f"commands.{key}: expected list or string, got {type(val).__name__}")
        out[key] = val
    return out


# --- Section-by-section loader ---

def load(repo_root: Path | None = None, path: Path | None = None) -> dict[str, Any]:
    """Load and validate .launchpad/config.yml.

    Returns a dict with keys: pipeline, commands, paths, overwrite, audit.
    Each section is validated independently — a failure in one section
    surfaces a warning but does not prevent other sections from being returned
    (the caller can check for '__errors__' key to detect partial loads).
    """
    repo_root = (repo_root or Path.cwd()).resolve()
    path = path or (repo_root / ".launchpad" / "config.yml")

    result: dict[str, Any] = {
        "pipeline": {},
        "commands": {"test": [], "typecheck": [], "lint": [], "format": [], "build": [], "dev": []},
        "paths": {
            "architecture_dir": "docs/architecture",
            "tasks_dir": "docs/tasks",
            "sections_dir": "docs/tasks/sections",
            "plans_file_pattern": "docs/tasks/sections/{section_name}-plan.md",
            "reports_dir": "docs/reports",
            "solutions_dir": "docs/solutions",
            "brainstorms_dir": "docs/brainstorms",
            "harness_dir": ".harness",
            "launchpad_dir": ".launchpad",
        },
        "overwrite": "prompt",
        "audit": {"committed": False},
        "__errors__": [],
    }

    if not path.is_file():
        # Missing config is not an error — downstream code uses defaults.
        return result

    text = path.read_text(encoding="utf-8")
    try:
        raw = _load_yaml_safe(text) or {}
    except Exception as e:
        raise ConfigError(f"{path}: YAML parse error: {e}")

    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top-level must be a mapping, got {type(raw).__name__}")

    # --- pipeline section ---
    if "pipeline" in raw:
        if isinstance(raw["pipeline"], dict):
            result["pipeline"] = raw["pipeline"]
        else:
            result["__errors__"].append("pipeline: expected mapping")

    # --- commands section ---
    if "commands" in raw:
        if isinstance(raw["commands"], dict):
            try:
                result["commands"] = _coerce_commands(raw["commands"])
            except ConfigError as e:
                result["__errors__"].append(str(e))
        else:
            result["__errors__"].append("commands: expected mapping")

    # --- paths section (critical: realpath-confinement) ---
    if "paths" in raw:
        if isinstance(raw["paths"], dict):
            for key, val in raw["paths"].items():
                try:
                    confined = _confine_path(val, repo_root, key)
                    result["paths"][key] = confined
                except ConfigError as e:
                    result["__errors__"].append(str(e))
        else:
            result["__errors__"].append("paths: expected mapping")

    # --- overwrite ---
    if "overwrite" in raw:
        val = raw["overwrite"]
        if val in ("skip", "prompt", "force"):
            result["overwrite"] = val
        else:
            result["__errors__"].append(f"overwrite={val!r}: expected skip|prompt|force")

    # --- audit ---
    if "audit" in raw and isinstance(raw["audit"], dict):
        result["audit"]["committed"] = bool(raw["audit"].get("committed", False))

    return result


# --- Canonical readers for v2.1 envelopes (V3 plan §11.3 + §11.7 + §10.v2.1) ---

# Known top-level fields for each schema_version. Used by the reader to
# compute "unknown fields" for forward-compat INFO messages. Keep in sync
# with decision_writer.py's `build_decision_payload` and the bootstrap-
# manifest writer (Phase 3+).

_SCAFFOLD_DECISION_KNOWN_FIELDS_1_0 = frozenset({
    "version", "layers", "monorepo", "matched_category_id",
    "rationale_path", "rationale_sha256", "rationale_summary",
    "generated_by", "generated_at", "nonce", "bound_cwd", "sha256",
})
_SCAFFOLD_DECISION_KNOWN_FIELDS_1_1 = _SCAFFOLD_DECISION_KNOWN_FIELDS_1_0 | frozenset({
    "schema_version", "plugin_version", "stacks", "identity",
    "identity_updated_at",  # added by /lp-update-identity (Phase 10)
    "kernel_render_state",  # added by KernelRenderer.render_all (Phase 10 DA7-flipped)
    "version_drift_log",    # appended by /lp-update-identity (Phase 10 DA8)
})

_BOOTSTRAP_MANIFEST_KNOWN_FIELDS_1_0 = frozenset({
    "manifest_schema_version", "plugin_version", "last_render_timestamp", "files",
})


class ScaffoldDecisionRead(NamedTuple):
    """Result of `read_scaffold_decision()`.

    `payload` is the raw envelope when the file exists, or `{}` when absent.
    `schema_version` is "1.0", "1.1", "1.x", or None (file absent / no
    indicator). `present` is False iff the file did not exist. `warnings`
    and `infos` are diagnostics the caller surfaces to the user.
    """
    payload: dict[str, Any]
    schema_version: str | None
    warnings: list[str]
    infos: list[str]
    present: bool


class BootstrapManifestRead(NamedTuple):
    """Result of `read_bootstrap_manifest()`.

    Same shape as `ScaffoldDecisionRead` but keyed off `manifest_schema_version`
    instead of `schema_version` (the field rename closes the cross-envelope
    collision documented in V3 plan §10.2).
    """
    payload: dict[str, Any]
    manifest_schema_version: str | None
    warnings: list[str]
    infos: list[str]
    present: bool


def _parse_major_minor(version: Any) -> tuple[int, int] | None:
    """Parse a "1.0", "1.1", "2.x" version string into (major, minor).

    Returns None when the value is not a string or has the wrong shape.
    The caller treats None as "malformed" and fails closed.
    """
    if not isinstance(version, str):
        return None
    parts = version.split(".")
    if len(parts) < 2:
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except (TypeError, ValueError):
        return None


def read_scaffold_decision(cwd: Path) -> ScaffoldDecisionRead:
    """Read `<cwd>/.launchpad/scaffold-decision.json` with the v2.1 ladder.

    Acceptance rules (V3 plan §10.v2.1, locked in HANDSHAKE §10):

      File missing
        Returns ScaffoldDecisionRead(payload={}, schema_version=None,
        warnings=[], infos=[], present=False). The caller decides whether
        an absent decision is an error (e.g., /lp-scaffold-stack requires
        one; /lp-define accepts absence as the brownfield-cold case).

      `schema_version` absent OR "1.0"
        Legacy 1.0 envelope. The reader returns the raw payload and emits
        WARN: "scaffold-decision schema_version absent or 1.0; identity
        defaults to UNSET sentinels". Identity validation is a no-op in
        this case (callers seed an UNSET identity in memory).

      `schema_version` "1.1"
        Full v2.1 read. The reader returns the payload unchanged. Identity
        validation is the caller's responsibility (decision_writer's
        validate_identity is the canonical validator).

      `schema_version` "1.x" where x > 1
        Forward-compat. Reader returns payload as-is and emits INFO listing
        unknown fields it does not recognize. Callers should not rely on
        unknown fields but may pass them through to writers (e.g., on
        re-write the unknown fields are preserved verbatim, NOT stripped).

      Major >= 2
        Fail closed: raises ConfigError(
            f"scaffold-decision schema_version {v}: major version >= 2 "
            f"is not readable by this plugin; update plugin or downgrade "
            f"manifest"
        ).

      Malformed JSON or non-mapping top-level
        Fail closed: ConfigError with parse error context.

    Identity validation is intentionally NOT performed here. Callers that
    need it import `validate_identity` from `lp_pick_stack.decision_writer`
    and call it on `result.payload["identity"]`. This split keeps the reader
    pure I/O so it can be called from contexts that legitimately want to
    inspect a malformed-identity envelope (e.g., /lp-update-identity's
    placeholder detection runs on raw values, not validated ones).
    """
    target = cwd / ".launchpad" / "scaffold-decision.json"
    if not target.is_file():
        return ScaffoldDecisionRead(
            payload={}, schema_version=None,
            warnings=[], infos=[], present=False,
        )

    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{target}: read failed: {exc}") from exc

    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ConfigError(f"{target}: JSON parse error: {exc}") from exc

    if not isinstance(payload, dict):
        raise ConfigError(
            f"{target}: top-level must be a mapping, got {type(payload).__name__}"
        )

    warnings: list[str] = []
    infos: list[str] = []

    schema_version = payload.get("schema_version")

    # Acceptance branch 1: schema_version absent or "1.0"
    if schema_version is None or schema_version == "1.0":
        warnings.append(
            f"{target}: schema_version absent or 1.0; identity defaults to "
            f"UNSET sentinels and is not validated. Run /lp-update-identity "
            f"to seed v2.1 identity fields."
        )
        return ScaffoldDecisionRead(
            payload=payload,
            schema_version=schema_version if schema_version else None,
            warnings=warnings, infos=infos, present=True,
        )

    parsed = _parse_major_minor(schema_version)
    if parsed is None:
        raise ConfigError(
            f"{target}: schema_version {schema_version!r} is malformed "
            f"(expected 'MAJOR.MINOR' e.g. '1.1')"
        )

    major, minor = parsed

    # Acceptance branch 4: major >= 2 fail closed
    if major >= 2:
        raise ConfigError(
            f"{target}: schema_version {schema_version!r}: major version >= 2 "
            f"is not readable by this plugin. Either update the plugin or "
            f"downgrade the manifest."
        )

    # Acceptance branch 2: schema_version "1.1" full read
    if schema_version == "1.1":
        return ScaffoldDecisionRead(
            payload=payload, schema_version=schema_version,
            warnings=warnings, infos=infos, present=True,
        )

    # Acceptance branch 3: schema_version "1.x" where x > 1, forward-compat
    if major == 1 and minor > 1:
        unknown = sorted(set(payload.keys()) - _SCAFFOLD_DECISION_KNOWN_FIELDS_1_1)
        if unknown:
            infos.append(
                f"{target}: schema_version {schema_version!r}: forward-compat "
                f"read; ignoring unknown top-level fields {unknown!r}. The "
                f"running plugin recognizes through 1.1; please upgrade to "
                f"read the new fields natively."
            )
        return ScaffoldDecisionRead(
            payload=payload, schema_version=schema_version,
            warnings=warnings, infos=infos, present=True,
        )

    # major == 1 and minor < 0 is impossible (minor parsed as int);
    # the only remaining case is malformed reaching here, which is a defect.
    raise ConfigError(  # pragma: no cover
        f"{target}: schema_version {schema_version!r} reached the reader's "
        f"unreachable fallback branch; this is a plugin defect."
    )


def read_bootstrap_manifest(cwd: Path) -> BootstrapManifestRead:
    """Read `<cwd>/.launchpad/bootstrap-manifest.json` with the v2.1 ladder.

    Acceptance rules (V3 plan §11.7, locked in HANDSHAKE §10):

      File missing
        Returns BootstrapManifestRead(payload={},
        manifest_schema_version=None, warnings=[], infos=[], present=False).
        Phase 3+ /lp-bootstrap writes the first manifest; before then,
        a brownfield project legitimately has none.

      `manifest_schema_version` absent OR "1.0"
        Full read. Required fields: plugin_version, last_render_timestamp,
        files (list). Missing required fields raise ConfigError.

      `manifest_schema_version` "1.x" where x > 0
        Forward-compat. INFO emitted for unknown fields.

      Major >= 2
        Fail closed.

      Malformed
        Fail closed.

    The reader does NOT verify per-file source_template_sha256 / rendered_
    content_sha256 hashes — that integrity check is /lp-bootstrap's job
    (manifest-tampering integrity check, V3 §10.7). This reader only
    enforces envelope shape.
    """
    target = cwd / ".launchpad" / "bootstrap-manifest.json"
    if not target.is_file():
        return BootstrapManifestRead(
            payload={}, manifest_schema_version=None,
            warnings=[], infos=[], present=False,
        )

    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{target}: read failed: {exc}") from exc

    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ConfigError(f"{target}: JSON parse error: {exc}") from exc

    if not isinstance(payload, dict):
        raise ConfigError(
            f"{target}: top-level must be a mapping, got {type(payload).__name__}"
        )

    warnings: list[str] = []
    infos: list[str] = []

    msv = payload.get("manifest_schema_version")

    if msv is None or msv == "1.0":
        # Required-field check applies in 1.0 mode; 1.1+ caller decides.
        for required in ("plugin_version", "last_render_timestamp", "files"):
            if required not in payload:
                raise ConfigError(
                    f"{target}: manifest_schema_version 1.0 requires field "
                    f"{required!r}"
                )
        if not isinstance(payload["files"], list):
            raise ConfigError(
                f"{target}: `files` must be a list, got "
                f"{type(payload['files']).__name__}"
            )
        return BootstrapManifestRead(
            payload=payload,
            manifest_schema_version=msv if msv else None,
            warnings=warnings, infos=infos, present=True,
        )

    parsed = _parse_major_minor(msv)
    if parsed is None:
        raise ConfigError(
            f"{target}: manifest_schema_version {msv!r} is malformed "
            f"(expected 'MAJOR.MINOR' e.g. '1.0')"
        )

    major, minor = parsed

    if major >= 2:
        raise ConfigError(
            f"{target}: manifest_schema_version {msv!r}: major version >= 2 "
            f"is not readable by this plugin. Either update the plugin or "
            f"downgrade the manifest."
        )

    if major == 1 and minor > 0:
        unknown = sorted(set(payload.keys()) - _BOOTSTRAP_MANIFEST_KNOWN_FIELDS_1_0)
        if unknown:
            infos.append(
                f"{target}: manifest_schema_version {msv!r}: forward-compat "
                f"read; ignoring unknown top-level fields {unknown!r}."
            )
        return BootstrapManifestRead(
            payload=payload, manifest_schema_version=msv,
            warnings=warnings, infos=infos, present=True,
        )

    raise ConfigError(  # pragma: no cover
        f"{target}: manifest_schema_version {msv!r} reached the reader's "
        f"unreachable fallback branch; this is a plugin defect."
    )


# --- Phase 5 v2.1 (DA4 + DA6) -- --get-config-value helpers -----------------


def _validate_config_path(path: str) -> None:
    """Phase 5 plan section 3.4: 256-byte length cap BEFORE regex; then
    allowlist match. Raises ConfigError on rejection.

    Length-cap message intentionally does NOT echo the rejected input
    (cycle-2 P2-B input-echo guard): pre-regex inputs may carry ANSI
    escape sequences or terminal-control chars that the character class
    has not yet excluded. Regex-rejection message echoes the input, since
    by then `[a-z0-9_.]` is the only character class allowed.
    """
    if len(path.encode("utf-8")) > _PATH_LENGTH_CAP_BYTES:
        raise ConfigError(
            f"error: config path exceeds {_PATH_LENGTH_CAP_BYTES} bytes"
        )
    if not _PATH_ALLOWLIST_RE.fullmatch(path):
        raise ConfigError(
            f"error: invalid config path {path!r}; must match "
            f"{_PATH_ALLOWLIST_RE.pattern}"
        )


def _get_value_at_path(config: dict[str, Any], path: str) -> Any:
    """Walk a dotted path through the merged config. The `path` MUST already
    have passed `_validate_config_path`; this helper is the second leg."""
    segments = path.split(".")
    cur: Any = config
    walked: list[str] = []
    for seg in segments:
        walked.append(seg)
        if not isinstance(cur, dict) or seg not in cur:
            full = ".".join(segments)
            raise ConfigError(
                f"error: config key {seg!r} not found at path {full!r}; "
                "check config.yml"
            )
        cur = cur[seg]
    return cur


# --- CLI entry ---

# --- Phase 4 v2.1 (Slice D) minimal stacks-array lift -----------------------


_STACK_TO_STACKS_WARN = (
    "config.yml uses legacy 'stack:' scalar; auto-promoted to "
    "'stacks: [%s]'. Update config.yml to silence this warning."
)


def auto_promote_stack_to_stacks(
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Phase 4 plan section 3.12 minimal lift.

    If `config.yml` carries a legacy `stack:` scalar, copy it into a
    single-element `stacks: [<value>]` list (without removing the original
    so older callers still find their key). Returns the mutated config plus
    a list of WARN strings for the caller to surface to the user.
    """
    if not isinstance(config, dict):
        return config, []
    warnings: list[str] = []
    legacy = config.get("stack")
    has_stacks = isinstance(config.get("stacks"), list)
    if legacy is not None and not has_stacks:
        if isinstance(legacy, list):
            config["stacks"] = list(legacy)
        else:
            config["stacks"] = [legacy]
        warnings.append(_STACK_TO_STACKS_WARN % (legacy,))
    return config, warnings


# --- Phase 6 v2.1 (DA6) -- read_stacks helper for /lp-define ---------------


def read_stacks(cwd: Path) -> list[str]:
    """Phase 6 plan §3.6: layer over `auto_promote_stack_to_stacks` and
    discard the returned warnings list (caller-side tuple-discard per
    cycle-3 simplicity P1-S1 + security P1-NEW-B; NO helper modification).

    Returns:
      * top-level `stacks: [...]` array if present (authoritative).
      * else `auto_promote_stack_to_stacks({"stack": <legacy>})[0]["stacks"]`
        if a legacy `stack:` scalar is present.
      * else empty list (caller decides whether to re-detect).

    Reads the raw YAML directly because `load()` projects to a fixed
    section schema and intentionally drops top-level `stack` / `stacks`
    keys; the layered call here keeps the auto_promote signature
    byte-equivalent to Phase 4's ship.
    """
    config_path = (cwd / ".launchpad" / "config.yml").resolve()
    if not config_path.is_file():
        return []
    try:
        raw = _load_yaml_safe(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    if not isinstance(raw, dict):
        return []
    stacks = raw.get("stacks")
    if isinstance(stacks, list):
        return [str(s) for s in stacks]
    if raw.get("stack") is not None:
        config_lifted, _warnings = auto_promote_stack_to_stacks(raw)
        return [str(s) for s in config_lifted.get("stacks", [])]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    ap.add_argument("--section", choices=["pipeline", "commands", "paths", "overwrite", "audit", "all"], default="all")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if any section had errors")
    ap.add_argument(
        "--get-config-value",
        metavar="DOTTED_PATH",
        help=(
            "read a single config value at the given dotted path "
            "(e.g. commands.test). Output is JSON-encoded to stdout. "
            "Takes precedence over --section if both are passed."
        ),
    )
    args = ap.parse_args()

    # Phase 5 v2.1 (DA4): validate path BEFORE config load so malformed
    # inputs are rejected cheaply (security F4) without I/O.
    if args.get_config_value is not None:
        try:
            _validate_config_path(args.get_config_value)
        except ConfigError as e:
            print(str(e), file=sys.stderr)
            return 2

    try:
        cfg = load(Path(args.repo_root))
    except ConfigError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1

    errors = cfg.pop("__errors__")
    if errors:
        for err in errors:
            print(f"WARN: {err}", file=sys.stderr)
        if args.strict:
            return 1

    # Phase 5 v2.1 (DA6): --get-config-value branch precedence over --section.
    if args.get_config_value is not None:
        try:
            value = _get_value_at_path(cfg, args.get_config_value)
        except ConfigError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(json.dumps(value))
        return 0

    if args.section == "all":
        print(json.dumps(cfg, indent=2))
    else:
        print(json.dumps(cfg[args.section], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
