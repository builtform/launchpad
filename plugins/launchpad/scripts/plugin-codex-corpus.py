"""Canonical LaunchPad corpus audit and provisional inventory producer.

This module is deliberately metadata-first. It treats canonical Markdown bodies
as opaque bytes, validates the additive ``x-launchpad`` declarations through the
shared protocol module, resolves only declared direct edges, and emits a
non-authoritative ``inventory`` runtime record. It never executes workflow prose
or derives release support.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final, cast

from safe_run import safe_run

SCRIPT_DIR: Final = Path(__file__).resolve().parent
PLUGIN_ROOT: Final = SCRIPT_DIR.parent
DEFAULT_BASELINE_PATH: Final = PLUGIN_ROOT / "codex" / "canonical-corpus-baseline.json"
PROTOCOL_MODULE_PATH: Final = SCRIPT_DIR / "plugin-codex-protocol.py"


def _load_protocol_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "launchpad_codex_protocol_for_corpus", PROTOCOL_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load the LaunchPad Codex protocol module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load_protocol_module()


class CorpusIntegrityError(ValueError):
    """A deterministic corpus or baseline integrity failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CorpusEntry:
    """One validated canonical command, skill, or agent."""

    resource_id: str
    kind: str
    source_path: str
    source_bytes: bytes
    body: bytes
    host_frontmatter_bytes: bytes
    metadata: Any
    user_invocable: bool
    stack_scope: str | None


@dataclass(frozen=True)
class CorpusAudit:
    """Validated corpus plus its normalized provisional inventory."""

    entries: tuple[CorpusEntry, ...]
    inventory: Any
    legacy_unreleased_paths: tuple[str, ...]
    unowned_skill_files: tuple[str, ...]


_BASELINE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "protocol_version",
        "baseline_commit",
        "canonical",
        "additive_files",
    }
)
_CANONICAL_BASELINE_FIELDS: Final = frozenset(
    {
        "id",
        "kind",
        "path",
        "body_sha256",
        "host_frontmatter_sha256",
        "metadata_floor",
    }
)
_ADDITIVE_BASELINE_FIELDS: Final = frozenset(
    {
        "path",
        "original_line_sha256",
        "allowed_insert_offsets",
        "required_fragments",
    }
)
_MUTATION_EFFECTS: Final = MappingProxyType(
    {
        "none": frozenset(),
        "project_files": frozenset({"project_files"}),
        "repository_state": frozenset({"repository_state"}),
        "external_state": frozenset({"external_state"}),
        "project_and_external": frozenset(
            {"project_files", "repository_state", "external_state"}
        ),
    }
)
_INTERACTION_RANK: Final = MappingProxyType(
    {"none": 0, "optional": 1, "required": 2, "authenticated_approval": 3}
)
_TOOL_PROFILE_RANK: Final = MappingProxyType(
    {"inspect_only": 0, "read_only": 1, "workspace_write": 2, "effectful": 3}
)
_IGNORED_SKILL_FILES: Final = frozenset({".gitkeep"})
_PLUGIN_ROOT_FILE_RE: Final = re.compile(
    r"\$\{CLAUDE_PLUGIN_ROOT\}/((?:scripts|skills)/[A-Za-z0-9_./-]+\.(?:md|py|sh))"
)
_SKILL_RESOURCE_RE: Final = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:references|assets)/[A-Za-z0-9_.-]+\.md)"
)
_TASK_AGENT_RE: Final = re.compile(
    r"Task\(\s*subagent_type\s*=\s*[\"'](lp-[a-z0-9-]+)[\"']"
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _strict_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusIntegrityError("INTEGRITY_MISMATCH", "duplicate baseline key")
        result[key] = value
    return result


def _exact_fields(
    value: object, expected: frozenset[str], context: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise CorpusIntegrityError("INTEGRITY_MISMATCH", f"{context} must be a mapping")
    actual = frozenset(value)
    if actual != expected:
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH",
            f"{context} fields differ: missing={sorted(expected - actual)!r}, "
            f"unknown={sorted(actual - expected)!r}",
        )
    return value


def _split_raw_frontmatter(document: bytes) -> tuple[bytes, bytes]:
    if not document.startswith(b"---\n"):
        raise CorpusIntegrityError(
            "FRONTMATTER_MISSING", "leading frontmatter is required"
        )
    end = document.find(b"\n---\n", 4)
    if end < 0:
        raise CorpusIntegrityError(
            "FRONTMATTER_UNTERMINATED", "frontmatter closing delimiter is missing"
        )
    return document[4:end], document[end + 5 :]


def _strip_additive_metadata(frontmatter: bytes) -> bytes:
    """Remove one final top-level x-launchpad block without reserializing YAML."""
    lines = frontmatter.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line == b"x-launchpad:\n"]
    if len(starts) != 1:
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH",
            "frontmatter must contain one top-level x-launchpad block",
        )
    start = starts[0]
    if any(line and not line.startswith((b" ", b"\t")) for line in lines[start + 1 :]):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH",
            "x-launchpad must be the final top-level frontmatter field",
        )
    return b"".join(lines[:start]).removesuffix(b"\n")


def _entry_paths(plugin_root: Path) -> tuple[list[Path], list[str]]:
    command_paths: list[Path] = []
    legacy: list[str] = []
    for path in sorted((plugin_root / "commands").glob("lp-*.md")):
        relative = path.relative_to(plugin_root).as_posix()
        if path.read_bytes().startswith(b"---\n"):
            command_paths.append(path)
        else:
            legacy.append(relative)
    paths = command_paths
    paths.extend(sorted((plugin_root / "agents").glob("**/lp-*.md")))
    paths.extend(sorted((plugin_root / "skills").glob("lp-*/SKILL.md")))
    return paths, legacy


def _resource_id(path: Path) -> str:
    return path.parent.name if path.name == "SKILL.md" else path.stem


def _kind(path: Path) -> str:
    if path.name == "SKILL.md":
        return "skill"
    if "commands" in path.parts:
        return "command"
    return "agent"


def discover_corpus(
    plugin_root: Path = PLUGIN_ROOT,
) -> tuple[tuple[CorpusEntry, ...], tuple[str, ...]]:
    """Discover and strictly normalize every released canonical definition."""
    protocol = _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json")
    entries: list[CorpusEntry] = []
    paths, legacy = _entry_paths(plugin_root)
    seen: set[str] = set()
    for path in paths:
        source = path.read_bytes()
        top_level, body = _PROTOCOL.extract_frontmatter(source, protocol)
        metadata, normalized_body = _PROTOCOL.normalize_document_metadata(
            source, protocol
        )
        if body != normalized_body:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"{path}: body split mismatch"
            )
        resource_id = _resource_id(path)
        if resource_id in seen:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"duplicate canonical id: {resource_id}"
            )
        seen.add(resource_id)
        declared_name = top_level.get("name")
        if (kind := _kind(path)) != "command" and declared_name != resource_id:
            raise CorpusIntegrityError(
                "METADATA_INVALID", f"{path}: name must equal {resource_id}"
            )
        if kind == "command" and declared_name not in {None, resource_id}:
            raise CorpusIntegrityError(
                "METADATA_INVALID",
                f"{path}: name must equal {resource_id} when present",
            )
        if metadata.component_kind != kind:
            raise CorpusIntegrityError(
                "METADATA_INVALID", f"{path}: component-kind must equal {kind}"
            )
        user_invocable = kind == "command" or (
            kind == "skill" and top_level.get("user-invocable", True) is True
        )
        stack_scope = top_level.get("stack_scope") if kind == "agent" else None
        if kind == "agent" and not isinstance(stack_scope, str):
            raise CorpusIntegrityError(
                "METADATA_INVALID", f"{path}: stack_scope is required"
            )
        frontmatter, _ = _split_raw_frontmatter(source)
        entries.append(
            CorpusEntry(
                resource_id=resource_id,
                kind=kind,
                source_path=path.relative_to(plugin_root).as_posix(),
                source_bytes=source,
                body=body,
                host_frontmatter_bytes=_strip_additive_metadata(frontmatter),
                metadata=metadata,
                user_invocable=user_invocable,
                stack_scope=stack_scope,
            )
        )
    return tuple(sorted(entries, key=lambda item: item.resource_id)), tuple(legacy)


def _component_targets(entry: CorpusEntry) -> tuple[str, ...]:
    direct = entry.metadata.direct
    return tuple((*direct.commands, *direct.skills, *direct.agents))


def _resolve_owned_path(
    plugin_root: Path, entry: CorpusEntry, value: str, family: str
) -> Path:
    lexical = PurePosixPath(value)
    if lexical.is_absolute() or any(part in {"", ".", ".."} for part in lexical.parts):
        raise CorpusIntegrityError(
            "METADATA_INVALID", f"{entry.resource_id}: invalid {family} path"
        )
    source = plugin_root / entry.source_path
    if family in {"references", "assets"} and entry.kind == "skill":
        target = source.parent.joinpath(*lexical.parts)
    else:
        target = plugin_root.joinpath(*lexical.parts)
    try:
        resolved = target.resolve(strict=True)
    except OSError as exc:
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH",
            f"{entry.resource_id}: missing declared {family} path {value}",
        ) from exc
    root_resolved = plugin_root.resolve(strict=True)
    if (
        not resolved.is_relative_to(root_resolved)
        or target.is_symlink()
        or not resolved.is_file()
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH",
            f"{entry.resource_id}: unsafe declared {family} path {value}",
        )
    return resolved


def validate_direct_edges(
    entries: Sequence[CorpusEntry], plugin_root: Path = PLUGIN_ROOT
) -> None:
    """Validate direct ownership, structural closure, and deterministic ordering."""
    by_id = {entry.resource_id: entry for entry in entries}
    owned_resources: dict[str, str] = {}
    for entry in entries:
        direct = entry.metadata.direct
        families = {
            "commands": direct.commands,
            "skills": direct.skills,
            "agents": direct.agents,
            "references": direct.references,
            "assets": direct.assets,
            "scripts": direct.scripts,
            "external-tools": direct.external_tools,
        }
        for family, values in families.items():
            if tuple(values) != tuple(sorted(set(values))):
                raise CorpusIntegrityError(
                    "METADATA_INVALID",
                    f"{entry.resource_id}: direct {family} values must be sorted and unique",
                )
        for family, values in (
            ("commands", direct.commands),
            ("skills", direct.skills),
            ("agents", direct.agents),
        ):
            for target_id in values:
                target = by_id.get(target_id)
                singular = family.removesuffix("s")
                if target is None or target.kind != singular:
                    raise CorpusIntegrityError(
                        "INTEGRITY_MISMATCH",
                        f"{entry.resource_id}: unresolved direct {singular} {target_id}",
                    )
        for family, values in (
            ("references", direct.references),
            ("assets", direct.assets),
            ("scripts", direct.scripts),
        ):
            for value in values:
                resolved = _resolve_owned_path(plugin_root, entry, value, family)
                if family in {"references", "assets"} and entry.kind == "skill":
                    key = resolved.relative_to(plugin_root.resolve()).as_posix()
                    prior = owned_resources.setdefault(key, entry.resource_id)
                    if prior != entry.resource_id:
                        raise CorpusIntegrityError(
                            "INTEGRITY_MISMATCH",
                            f"resource {key} has multiple owners: {prior}, {entry.resource_id}",
                        )


def audit_declared_reference_hints(entries: Sequence[CorpusEntry]) -> None:
    """Flag only high-confidence literal references; never parse Markdown semantics."""
    by_id = {entry.resource_id: entry for entry in entries}
    for entry in entries:
        try:
            body = entry.body.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"{entry.source_path}: body is not UTF-8"
            ) from exc
        direct = entry.metadata.direct
        for value in _PLUGIN_ROOT_FILE_RE.findall(body):
            if value.startswith("scripts/") and value not in direct.scripts:
                raise CorpusIntegrityError(
                    "INTEGRITY_MISMATCH",
                    f"{entry.resource_id}: literal plugin script is undeclared: {value}",
                )
            if value.startswith("skills/"):
                skill_path = PurePosixPath(value)
                parts = skill_path.parts
                skill_id = parts[1] if len(parts) > 2 else ""
                if skill_path.name == "SKILL.md" and skill_id in by_id:
                    if skill_id not in direct.skills:
                        raise CorpusIntegrityError(
                            "INTEGRITY_MISMATCH",
                            f"{entry.resource_id}: literal plugin skill is undeclared: {skill_id}",
                        )
                elif value not in direct.references:
                    raise CorpusIntegrityError(
                        "INTEGRITY_MISMATCH",
                        f"{entry.resource_id}: literal plugin reference is undeclared: {value}",
                    )
        if entry.kind == "skill":
            for value in _SKILL_RESOURCE_RE.findall(body):
                if value.startswith("references/FILE-") or "{{" in value:
                    continue
                family_values = (
                    direct.assets if value.startswith("assets/") else direct.references
                )
                if value not in family_values:
                    raise CorpusIntegrityError(
                        "INTEGRITY_MISMATCH",
                        f"{entry.resource_id}: literal skill resource is undeclared: {value}",
                    )
        for agent_id in _TASK_AGENT_RE.findall(body):
            if agent_id not in direct.agents:
                raise CorpusIntegrityError(
                    "INTEGRITY_MISMATCH",
                    f"{entry.resource_id}: literal Task agent is undeclared: {agent_id}",
                )


def _skill_unowned_files(
    entries: Sequence[CorpusEntry], plugin_root: Path
) -> tuple[str, ...]:
    owned: set[str] = set()
    for entry in entries:
        for family, values in (
            ("references", entry.metadata.direct.references),
            ("assets", entry.metadata.direct.assets),
        ):
            for value in values:
                resolved = _resolve_owned_path(plugin_root, entry, value, family)
                owned.add(resolved.relative_to(plugin_root.resolve()).as_posix())
    unowned: list[str] = []
    for path in sorted((plugin_root / "skills").glob("lp-*/*/*")):
        if (
            not path.is_file()
            or path.name in _IGNORED_SKILL_FILES
            or "evals" in path.parts
        ):
            continue
        relative = path.resolve().relative_to(plugin_root.resolve()).as_posix()
        if relative not in owned:
            unowned.append(relative)
    return tuple(unowned)


def _direct_record(direct: Any) -> dict[str, list[str]]:
    return {
        "commands": list(direct.commands),
        "skills": list(direct.skills),
        "agents": list(direct.agents),
        "references": list(direct.references),
        "assets": list(direct.assets),
        "scripts": list(direct.scripts),
        "external_tools": list(direct.external_tools),
    }


def _capability_record(capabilities: Any) -> dict[str, object]:
    return {
        "required": list(capabilities.required),
        "mutation": capabilities.mutation,
        "interaction": capabilities.interaction,
        "external_data_egress": capabilities.external_data_egress,
        "write_scopes": list(capabilities.write_scopes),
        "tool_profile": capabilities.tool_profile,
        "fallback": capabilities.fallback,
    }


def _metadata_floor(metadata: Any) -> dict[str, object]:
    loop = metadata.bounded_loop
    return {
        "schema_version": metadata.schema_version,
        "component_kind": metadata.component_kind,
        "direct": _direct_record(metadata.direct),
        "capabilities": _capability_record(metadata.capabilities),
        "bounded_loop": (
            None
            if loop is None
            else {
                "max_iterations": loop.max_iterations,
                "reentry_command": loop.reentry_command,
            }
        ),
    }


def check_security_monotonicity(
    resource_id: str, floor: Mapping[str, Any], current: Any
) -> None:
    """Reject hidden/removal-style reductions in audited security metadata."""
    if (
        floor.get("schema_version") != current.schema_version
        or floor.get("component_kind") != current.component_kind
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: metadata identity changed"
        )
    floor_direct = _exact_fields(
        floor.get("direct"),
        frozenset(_direct_record(current.direct)),
        f"{resource_id} direct floor",
    )
    current_direct = _direct_record(current.direct)
    for family, old_values in floor_direct.items():
        if not isinstance(old_values, list) or not set(old_values).issubset(
            current_direct[family]
        ):
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH",
                f"{resource_id}: direct {family} metadata was reduced",
            )
    floor_cap = _exact_fields(
        floor.get("capabilities"),
        frozenset(_capability_record(current.capabilities)),
        f"{resource_id} capability floor",
    )
    cap = current.capabilities
    if not set(floor_cap["required"]).issubset(cap.required):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: required capabilities were reduced"
        )
    if not _MUTATION_EFFECTS[str(floor_cap["mutation"])].issubset(
        _MUTATION_EFFECTS[cap.mutation]
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: mutation declaration was reduced"
        )
    if (
        _INTERACTION_RANK[str(floor_cap["interaction"])]
        > _INTERACTION_RANK[cap.interaction]
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: interaction declaration was reduced"
        )
    if floor_cap["external_data_egress"] is True and not cap.external_data_egress:
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH",
            f"{resource_id}: external egress declaration was reduced",
        )
    if not set(floor_cap["write_scopes"]).issubset(cap.write_scopes):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: write scopes were reduced"
        )
    if (
        _TOOL_PROFILE_RANK[str(floor_cap["tool_profile"])]
        > _TOOL_PROFILE_RANK[cap.tool_profile]
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: tool profile was reduced"
        )
    if floor_cap["fallback"] != cap.fallback:
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: fallback class changed"
        )
    floor_loop = floor.get("bounded_loop")
    current_loop = current.bounded_loop
    if floor_loop is None:
        if current_loop is not None:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"{resource_id}: unreviewed bounded loop added"
            )
    elif (
        current_loop is None
        or floor_loop.get("reentry_command") != current_loop.reentry_command
        or current_loop.max_iterations > floor_loop.get("max_iterations")
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"{resource_id}: bounded loop safety was reduced"
        )


def _leaf_digest(plugin_root: Path, entry: CorpusEntry, family: str, value: str) -> str:
    if family == "external_tools":
        return _sha256(f"external-tool:{value}".encode())
    path = _resolve_owned_path(plugin_root, entry, value, family)
    return _sha256(path.read_bytes())


def _aggregate_capability_records(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Conservatively combine direct summaries using the protocol vocabulary."""
    required: set[str] = set()
    mutations: set[str] = set()
    interactions: list[str] = []
    write_scopes: set[str] = set()
    tool_profiles: list[str] = []
    fallbacks: set[str] = set()
    external_data_egress = False
    for record in records:
        required.update(cast(Sequence[str], record["required"]))
        mutations.add(cast(str, record["mutation"]))
        interactions.append(cast(str, record["interaction"]))
        write_scopes.update(cast(Sequence[str], record["write_scopes"]))
        tool_profiles.append(cast(str, record["tool_profile"]))
        fallbacks.add(cast(str, record["fallback"]))
        external_data_egress = external_data_egress or cast(
            bool, record["external_data_egress"]
        )
    effects = set().union(*(_MUTATION_EFFECTS[item] for item in mutations))
    if "external_state" in effects and effects & {"project_files", "repository_state"}:
        mutation = "project_and_external"
    elif "external_state" in effects:
        mutation = "external_state"
    elif "repository_state" in effects:
        mutation = "repository_state"
    elif "project_files" in effects:
        mutation = "project_files"
    else:
        mutation = "none"
    if "none" in fallbacks:
        fallback = "none"
    elif "inspect_only" in fallbacks:
        fallback = "inspect_only"
    else:
        fallback = "read_only_manual"
    return {
        "required": sorted(required),
        "mutation": mutation,
        "interaction": max(interactions, key=_INTERACTION_RANK.__getitem__),
        "external_data_egress": external_data_egress,
        "write_scopes": sorted(write_scopes),
        "tool_profile": max(tool_profiles, key=_TOOL_PROFILE_RANK.__getitem__),
        "fallback": fallback,
    }


def build_inventory(
    entries: Sequence[CorpusEntry], plugin_root: Path = PLUGIN_ROOT
) -> Any:
    """Build one deterministic O(V + E) provisional inventory record."""
    protocol = _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json")
    by_id = {entry.resource_id: entry for entry in entries}
    state: dict[str, int] = {}
    aggregate: dict[str, str] = {}
    aggregate_capabilities: dict[str, dict[str, object]] = {}

    def visit(resource_id: str) -> str:
        marker = state.get(resource_id, 0)
        if marker == 1:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"direct component cycle contains {resource_id}"
            )
        if marker == 2:
            return aggregate[resource_id]
        state[resource_id] = 1
        entry = by_id[resource_id]
        child_digests = [
            (target, visit(target)) for target in _component_targets(entry)
        ]
        aggregate_capabilities[resource_id] = _aggregate_capability_records(
            [
                _capability_record(entry.metadata.capabilities),
                *(aggregate_capabilities[target] for target, _digest in child_digests),
            ]
        )
        leaf_digests: list[tuple[str, str, str]] = []
        direct = entry.metadata.direct
        for family, values in (
            ("references", direct.references),
            ("assets", direct.assets),
            ("scripts", direct.scripts),
            ("external_tools", direct.external_tools),
        ):
            leaf_digests.extend(
                (family, value, _leaf_digest(plugin_root, entry, family, value))
                for value in values
            )
        payload = {
            "id": resource_id,
            "source_digest": _sha256(entry.source_bytes),
            "metadata_digest": _sha256(
                _canonical_json(_metadata_floor(entry.metadata))
            ),
            "children": child_digests,
            "leaves": leaf_digests,
        }
        aggregate[resource_id] = _sha256(_canonical_json(payload))
        state[resource_id] = 2
        return aggregate[resource_id]

    for entry in entries:
        visit(entry.resource_id)
    nodes = []
    for entry in entries:
        metadata = _metadata_floor(entry.metadata)
        nodes.append(
            {
                "id": entry.resource_id,
                "kind": entry.kind,
                "source_path": entry.source_path,
                "source_digest": _sha256(entry.source_bytes),
                "metadata_digest": _sha256(_canonical_json(metadata)),
                "aggregate_digest": aggregate[entry.resource_id],
                "direct": metadata["direct"],
                "capabilities": aggregate_capabilities[entry.resource_id],
            }
        )
    root_ids = sorted(entry.resource_id for entry in entries if entry.user_invocable)
    raw = {
        "stage": "inventory",
        "release_stage": "dogfood",
        "protocol_version": protocol.protocol_version,
        "protocol_digest": protocol.digest,
        "runtime_payload_digest": None,
        "root_ids": root_ids,
        "nodes": nodes,
        "runtime_files": [],
        "support": [],
        "qualification_ids": [],
        "generated_slots": [],
    }
    return _PROTOCOL.normalize_runtime_record(raw, protocol)


def build_agent_scope_records(
    entries: Sequence[CorpusEntry], plugin_root: Path = PLUGIN_ROOT
) -> Mapping[str, object]:
    """Return protocol-normalized records for the pure stack-scope filter API."""
    protocol = _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json")
    records = {
        entry.resource_id: _PROTOCOL.normalize_agent_scope_record(
            {"resource_id": entry.resource_id, "stack_scope": entry.stack_scope},
            protocol,
        )
        for entry in entries
        if entry.kind == "agent"
    }
    return MappingProxyType(records)


def _load_baseline(path: Path) -> Mapping[str, Any]:
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_strict_json_pairs
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", "baseline is unreadable"
        ) from exc
    return _exact_fields(raw, _BASELINE_FIELDS, "baseline")


def _check_additive_file(plugin_root: Path, item: Mapping[str, Any]) -> None:
    item = _exact_fields(item, _ADDITIVE_BASELINE_FIELDS, "additive baseline entry")
    relative = item["path"]
    if not isinstance(relative, str):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", "additive path must be a string"
        )
    current_lines = (plugin_root / relative).read_bytes().splitlines(keepends=True)
    current_hashes = [_sha256(line) for line in current_lines]
    original = item["original_line_sha256"]
    allowed = item["allowed_insert_offsets"]
    required = item["required_fragments"]
    if (
        not isinstance(original, list)
        or not all(isinstance(part, str) for part in original)
        or not isinstance(allowed, list)
        or not all(
            isinstance(part, int) and not isinstance(part, bool) for part in allowed
        )
        or not isinstance(required, list)
        or not all(isinstance(part, str) for part in required)
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", "additive baseline arrays are invalid"
        )
    matcher = difflib.SequenceMatcher(a=original, b=current_hashes, autojunk=False)
    for (
        operation,
        original_start,
        _original_end,
        _current_start,
        _current_end,
    ) in matcher.get_opcodes():
        if operation == "equal":
            continue
        if operation != "insert":
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH",
                f"{relative}: baseline line removed, changed, or reordered",
            )
        if original_start not in allowed:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH",
                f"{relative}: addition outside an approved boundary",
            )
    text = b"".join(current_lines).decode("utf-8", errors="strict")
    for fragment in required:
        if text.count(fragment) != 1:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH",
                f"{relative}: required additive fragment missing or duplicated",
            )


def check_baseline(
    entries: Sequence[CorpusEntry],
    plugin_root: Path = PLUGIN_ROOT,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
) -> None:
    """Enforce canonical paths, body bytes, legal insertion, and security floors."""
    baseline = _load_baseline(baseline_path)
    protocol = _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json")
    if (
        baseline["schema_version"] != 1
        or baseline["protocol_version"] != protocol.protocol_version
    ):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", "baseline protocol identity differs"
        )
    canonical_raw = baseline["canonical"]
    additive_raw = baseline["additive_files"]
    if not isinstance(canonical_raw, list) or not isinstance(additive_raw, list):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", "baseline tables must be lists"
        )
    expected: dict[str, Mapping[str, Any]] = {}
    for raw_item in canonical_raw:
        item = _exact_fields(
            raw_item, _CANONICAL_BASELINE_FIELDS, "canonical baseline entry"
        )
        path = item["path"]
        if not isinstance(path, str) or path in expected:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", "baseline canonical paths are invalid"
            )
        expected[path] = item
    current = {entry.source_path: entry for entry in entries}
    if frozenset(current) != frozenset(expected):
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH",
            f"canonical paths differ: missing={sorted(set(expected) - set(current))!r}, "
            f"unknown={sorted(set(current) - set(expected))!r}",
        )
    for path, entry in current.items():
        item = expected[path]
        if item["id"] != entry.resource_id or item["kind"] != entry.kind:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"{path}: canonical identity changed"
            )
        if item["body_sha256"] != _sha256(entry.body):
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"{path}: canonical body bytes changed"
            )
        if item["host_frontmatter_sha256"] != _sha256(entry.host_frontmatter_bytes):
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"{path}: pre-existing frontmatter changed"
            )
        floor = item["metadata_floor"]
        if not isinstance(floor, Mapping):
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", f"{path}: metadata floor invalid"
            )
        check_security_monotonicity(entry.resource_id, floor, entry.metadata)
    for raw_item in additive_raw:
        if not isinstance(raw_item, Mapping):
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH", "additive entry must be a mapping"
            )
        _check_additive_file(plugin_root, raw_item)


def audit_corpus(
    plugin_root: Path = PLUGIN_ROOT,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
) -> CorpusAudit:
    entries, legacy = discover_corpus(plugin_root)
    validate_direct_edges(entries, plugin_root)
    audit_declared_reference_hints(entries)
    check_baseline(entries, plugin_root, baseline_path)
    inventory = build_inventory(entries, plugin_root)
    return CorpusAudit(
        entries=entries,
        inventory=inventory,
        legacy_unreleased_paths=legacy,
        unowned_skill_files=_skill_unowned_files(entries, plugin_root),
    )


def inventory_as_dict(inventory: Any) -> dict[str, object]:
    """Serialize the normalized provisional record without copying protocol rules."""
    value = dataclasses.asdict(inventory)
    return json.loads(json.dumps(value, sort_keys=True))


def _git_file_bytes(repository_root: Path, ref: str, relative: str) -> bytes:
    try:
        completed = safe_run(
            ["git", "show", f"{ref}:{relative}"], repository_root, timeout=30
        )
    except subprocess.CalledProcessError as exc:
        raise CorpusIntegrityError(
            "INTEGRITY_MISMATCH", f"baseline ref lacks {relative}"
        ) from exc
    return completed.stdout


def write_baseline(
    *,
    repository_root: Path,
    plugin_root: Path,
    baseline_path: Path,
    baseline_ref: str,
    additive_specs: Sequence[Mapping[str, object]],
) -> None:
    """Maintainer-only writer for the single canonical integrity baseline."""
    entries, _legacy = discover_corpus(plugin_root)
    canonical = []
    for entry in entries:
        repository_path = (
            (plugin_root / entry.source_path).relative_to(repository_root).as_posix()
        )
        original_source = _git_file_bytes(
            repository_root, baseline_ref, repository_path
        )
        original_frontmatter, original_body = _split_raw_frontmatter(original_source)
        if original_body != entry.body:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH",
                f"{entry.source_path}: body differs from baseline ref",
            )
        if original_frontmatter != entry.host_frontmatter_bytes:
            raise CorpusIntegrityError(
                "INTEGRITY_MISMATCH",
                f"{entry.source_path}: non-adapter frontmatter differs from baseline ref",
            )
        canonical.append(
            {
                "id": entry.resource_id,
                "kind": entry.kind,
                "path": entry.source_path,
                "body_sha256": _sha256(original_body),
                "host_frontmatter_sha256": _sha256(original_frontmatter),
                "metadata_floor": _metadata_floor(entry.metadata),
            }
        )
    additive_files = []
    for spec in additive_specs:
        relative = spec.get("path")
        allowed_after = spec.get("allowed_after")
        required_fragments = spec.get("required_fragments")
        if (
            not isinstance(relative, str)
            or not isinstance(allowed_after, list)
            or not all(
                isinstance(value, Mapping)
                and isinstance(value.get("line"), str)
                and isinstance(value.get("following_lines", 0), int)
                and not isinstance(value.get("following_lines", 0), bool)
                and value.get("following_lines", 0) >= 0
                for value in allowed_after
            )
            or not isinstance(required_fragments, list)
            or not all(isinstance(value, str) for value in required_fragments)
        ):
            raise CorpusIntegrityError("INTEGRITY_MISMATCH", "additive spec is invalid")
        repository_path = (
            (plugin_root / relative).relative_to(repository_root).as_posix()
        )
        original = _git_file_bytes(repository_root, baseline_ref, repository_path)
        original_lines = original.splitlines(keepends=True)
        original_hashes = [_sha256(line) for line in original_lines]
        allowed_offsets: list[int] = []
        for anchor_spec in allowed_after:
            encoded = anchor_spec["line"].encode("utf-8")
            matches = [
                index
                for index, line in enumerate(original_lines)
                if line.rstrip(b"\r\n") == encoded
            ]
            if len(matches) != 1:
                raise CorpusIntegrityError(
                    "INTEGRITY_MISMATCH", f"{relative}: additive anchor must occur once"
                )
            offset = matches[0] + 1 + anchor_spec.get("following_lines", 0)
            if offset < 0 or offset > len(original_lines):
                raise CorpusIntegrityError(
                    "INTEGRITY_MISMATCH",
                    f"{relative}: additive offset is outside the file",
                )
            allowed_offsets.append(offset)
        additive_files.append(
            {
                "path": relative,
                "original_line_sha256": original_hashes,
                "allowed_insert_offsets": sorted(set(allowed_offsets)),
                "required_fragments": required_fragments,
            }
        )
    protocol = _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json")
    payload = {
        "schema_version": 1,
        "protocol_version": protocol.protocol_version,
        "baseline_commit": baseline_ref,
        "canonical": canonical,
        "additive_files": additive_files,
    }
    baseline_path.write_bytes(
        json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"
    )


def _main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", action="store_true", help="print provisional inventory JSON"
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        audit = audit_corpus()
    except (CorpusIntegrityError, _PROTOCOL.ProtocolValidationError) as exc:
        code = getattr(exc, "code", "INTEGRITY_MISMATCH")
        print(f"FAIL [{code}]: {exc}", file=sys.stderr)
        return 1
    if args.inventory:
        print(json.dumps(inventory_as_dict(audit.inventory), indent=2, sort_keys=True))
    else:
        command_count = sum(entry.kind == "command" for entry in audit.entries)
        agent_count = sum(entry.kind == "agent" for entry in audit.entries)
        skill_count = sum(entry.kind == "skill" for entry in audit.entries)
        print(
            "PASS: canonical corpus integrity "
            f"({command_count} commands, {agent_count} agents, {skill_count} skills)"
        )
        for path in audit.legacy_unreleased_paths:
            print(
                f"INFO: audited unreleased legacy command without frontmatter: {path}"
            )
        for path in audit.unowned_skill_files:
            print(f"INFO: audited non-runtime skill file: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
