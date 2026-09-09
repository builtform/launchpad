"""Strict LaunchPad Codex protocol loader and normalized record authority.

The machine-readable protocol owns every enum, fixed bound, spelling bridge,
and record shape used by later Codex components. This module provides typed,
immutable views over that data and one strict YAML path for canonical metadata.
It does not resolve files, execute workflows, or infer behavior from Markdown.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import json
import math
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
DEFAULT_PROTOCOL_PATH = PLUGIN_ROOT / "codex" / "adapter-protocol.json"
VENDOR_DIR = SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

import yaml  # noqa: E402
from yaml.events import (  # noqa: E402
    AliasEvent,
    DocumentStartEvent,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
)

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class ProtocolValidationError(ValueError):
    """A stable, safely classified protocol or metadata failure."""

    def __init__(
        self,
        code: str,
        message: str,
        reporting_class: str = "private_security",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.reporting_class = reporting_class


class _DuplicateJsonKey(ValueError):
    pass


class _DuplicateYamlKey(ValueError):
    pass


class _StrictSafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """SafeLoader variant that rejects duplicate constructed mapping keys."""

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        if not isinstance(node, yaml.MappingNode):
            raise _DuplicateYamlKey("mapping node required")
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in result
            except TypeError as exc:
                raise _DuplicateYamlKey("mapping keys must be scalar") from exc
            if duplicate:
                raise _DuplicateYamlKey(f"duplicate mapping key: {key!r}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


@dataclass(frozen=True)
class ProtocolContract:
    """Immutable normalized view of ``adapter-protocol.json``."""

    path: Path
    digest: str
    schema_version: int
    protocol_id: str
    protocol_version: str
    name_pattern: re.Pattern[str]
    stack_scope_pattern: re.Pattern[str]
    metadata_namespace: str
    component_kinds: frozenset[str]
    project_extension_roster_fields: tuple[str, ...]
    canonical_dialect: Mapping[str, Mapping[str, str]]
    router: Mapping[str, object]
    metadata_schema: Mapping[str, tuple[str, ...]]
    capability_ids: frozenset[str]
    classes: Mapping[str, frozenset[str]]
    cli_schema_spelling: Mapping[str, str]
    digest_domains: Mapping[str, Mapping[str, object]]
    packaging: Mapping[str, object]
    record_schemas: Mapping[str, tuple[str, ...]]
    defaults: Mapping[str, int]
    minimums: Mapping[str, int]
    limits: Mapping[str, int]
    duration_contract: Mapping[str, bool]
    errors: Mapping[str, str]

    def reporting_class_for_error(self, code: str) -> str:
        """Return the declared class, defaulting unknown codes to private."""
        return self.errors.get(code, "private_security")

    def require_enum(self, family: str, value: object) -> str:
        if not isinstance(value, str) or value not in self.classes.get(
            family, frozenset()
        ):
            raise _error(
                self,
                "PROTOCOL_VALUE_INVALID",
                f"invalid {family} value",
            )
        return value


@dataclass(frozen=True)
class DirectEdges:
    commands: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    external_tools: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return sum(
            len(values)
            for values in (
                self.commands,
                self.skills,
                self.agents,
                self.references,
                self.assets,
                self.scripts,
                self.external_tools,
            )
        )


@dataclass(frozen=True)
class CapabilitySummary:
    required: tuple[str, ...]
    mutation: str
    interaction: str
    external_data_egress: bool
    write_scopes: tuple[str, ...]
    tool_profile: str
    fallback: str


@dataclass(frozen=True)
class BoundedLoop:
    max_iterations: int
    reentry_command: str


@dataclass(frozen=True)
class NormalizedMetadata:
    schema_version: int
    component_kind: str
    direct: DirectEdges
    capabilities: CapabilitySummary
    bounded_loop: BoundedLoop | None


@dataclass(frozen=True)
class NodeRecord:
    id: str
    kind: str
    source_path: str
    source_digest: str
    metadata_digest: str
    aggregate_digest: str
    direct: DirectEdges
    capabilities: CapabilitySummary


@dataclass(frozen=True)
class SupportRecord:
    resource_id: str
    base_support_state: str
    blocked_reason_codes: tuple[str, ...]
    fallback: str


@dataclass(frozen=True)
class RuntimeFileRecord:
    path: str
    digest: str
    size: int


@dataclass(frozen=True)
class CompatibilityPredicateRecord:
    predicate_id: str
    resource_id: str
    host: str
    operating_system: str
    required_capabilities: tuple[str, ...]
    tool_versions: Mapping[str, str]
    base_support_state: str
    blocked_reason_codes: tuple[str, ...]
    fallback: str
    qualification_ids: tuple[str, ...]


@dataclass(frozen=True)
class AvailabilityRecord:
    resource_id: str
    applicability: str
    effective_availability: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class QualificationRecord:
    qualification_id: str
    runtime_payload_digest: str
    host: str
    operating_system: str
    tool_versions: Mapping[str, str]
    receipt_ids: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeRecord:
    stage: str
    release_stage: str
    protocol_version: str
    protocol_digest: str
    runtime_payload_digest: str | None
    root_ids: tuple[str, ...]
    nodes: tuple[NodeRecord, ...]
    runtime_files: tuple[RuntimeFileRecord, ...]
    support: tuple[SupportRecord, ...]
    qualification_ids: tuple[str, ...]
    generated_slots: tuple[str, ...]


@dataclass(frozen=True)
class DigestRecord:
    runtime_payload_digest: str
    evidence_digest: str
    artifact_digest: str


@dataclass(frozen=True)
class AgentScopeRecord:
    resource_id: str
    stack_scope: str


@dataclass(frozen=True)
class ResolverSourceRecord:
    resource_id: str
    kind: str
    origin: str
    source_path: str
    source_digest: str
    metadata_digest: str
    size: int
    user_invocable: bool
    quarantined: bool


@dataclass(frozen=True)
class ResolverResourceRecord:
    owner_id: str
    owner_kind: str
    origin: str
    relative_path: str
    source_digest: str
    size: int
    quarantined: bool


@dataclass(frozen=True)
class ProjectRootRecord:
    canonical_root: str
    repository_identity: str
    root_device: int
    root_inode: int


@dataclass(frozen=True)
class ProjectSelectionRecord:
    resource_id: str
    kind: str
    selection_source: str
    selector_path: str
    selector_key: str
    selector_digest: str
    selection_digest: str


@dataclass(frozen=True)
class ProjectAdmissionRecord:
    nonce: str
    expires_at: int
    repository_identity: str
    canonical_root_digest: str
    relative_path: str
    kind: str
    content_digest: str
    selection_digest: str
    protocol_version: str
    requested_capability: str
    run_id: str
    child_id: str
    workflow_id: str
    repository_ref: str
    source: str


def _error(
    contract: ProtocolContract,
    code: str,
    message: str,
) -> ProtocolValidationError:
    return ProtocolValidationError(
        code,
        message,
        contract.reporting_class_for_error(code),
    )


def _json_pairs(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _as_mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProtocolValidationError(
            "PROTOCOL_TYPE_INVALID",
            f"{context} must be a string-keyed mapping",
        )
    return value


def _as_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolValidationError(
            "PROTOCOL_TYPE_INVALID",
            f"{context} must be a non-empty string",
        )
    return value


def _as_int(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProtocolValidationError(
            "PROTOCOL_TYPE_INVALID",
            f"{context} must be a positive integer",
        )
    return value


def _as_nonnegative_int(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolValidationError(
            "PROTOCOL_TYPE_INVALID",
            f"{context} must be a non-negative integer",
        )
    return value


def _as_bool(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise ProtocolValidationError(
            "PROTOCOL_TYPE_INVALID",
            f"{context} must be a boolean",
        )
    return value


def _string_tuple(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ProtocolValidationError(
            "PROTOCOL_TYPE_INVALID",
            f"{context} must be a list",
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _as_string(item, context)
        if text in seen:
            raise ProtocolValidationError(
                "PROTOCOL_DUPLICATE_VALUE",
                f"{context} contains a duplicate value",
            )
        seen.add(text)
        normalized.append(text)
    return tuple(normalized)


def _exact_keys(
    value: Mapping[str, Any],
    *,
    allowed: Iterable[str],
    required: Iterable[str],
    context: str,
    code: str = "PROTOCOL_UNKNOWN_FIELD",
    contract: ProtocolContract | None = None,
) -> None:
    allowed_set = frozenset(allowed)
    required_set = frozenset(required)
    unknown = sorted(set(value) - allowed_set)
    missing = sorted(required_set - set(value))
    if unknown or missing:
        parts: list[str] = []
        if unknown:
            parts.append(f"unknown fields: {', '.join(unknown)}")
        if missing:
            parts.append(f"missing fields: {', '.join(missing)}")
        message = f"{context}: {'; '.join(parts)}"
        if contract is None:
            raise ProtocolValidationError(code, message)
        raise _error(contract, code, message)


def _immutable_nested_mapping(
    value: Mapping[str, Any], context: str
) -> Mapping[str, Mapping[str, str]]:
    result: dict[str, Mapping[str, str]] = {}
    for key, item in value.items():
        item_map = _as_mapping(item, f"{context}.{key}")
        result[key] = MappingProxyType(
            {
                child_key: _as_string(child_value, f"{context}.{key}.{child_key}")
                for child_key, child_value in item_map.items()
            }
        )
    return MappingProxyType(result)


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, object]:
    return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})


def _validate_cross_limits(contract: ProtocolContract) -> None:
    limits = contract.limits
    defaults = contract.defaults
    minimums = contract.minimums

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise _error(contract, "PROTOCOL_FILE_INVALID", message)

    require(
        defaults["worker_count"] <= limits["worker_ceiling"],
        "worker default exceeds worker ceiling",
    )
    require(
        limits["cooperative_cancel_seconds"] + limits["final_cancel_join_seconds"]
        == limits["cancellation_drain_seconds"],
        "cancellation intervals do not equal the declared drain",
    )
    require(
        limits["child_timeout_seconds"]
        + limits["retry_backoff_seconds"]
        + limits["cancellation_drain_seconds"]
        <= limits["wave_timeout_seconds"],
        "child, retry, and cancellation time exceed a wave",
    )
    require(
        limits["wave_timeout_seconds"]
        + limits["retry_backoff_seconds"]
        + limits["cancellation_drain_seconds"]
        <= limits["wall_clock_seconds"],
        "wave, retry, and cancellation time exceed the wall clock",
    )
    require(
        limits["deadline_cancellation_seconds"]
        <= limits["wall_clock_seconds"] - limits["cancellation_drain_seconds"],
        "deadline cancellation begins too late for the full drain",
    )
    require(
        limits["mutation_receipt_bytes_per_run"] <= limits["adapter_storage_bytes"],
        "one reserved mutation receipt cannot fit adapter storage",
    )
    require(
        limits["serialized_message_bytes"] <= limits["aggregate_outbound_bytes"],
        "one serialized message exceeds aggregate egress",
    )
    require(
        limits["documentation_file_bytes"] <= limits["documentation_aggregate_bytes"],
        "one documentation file exceeds the aggregate scan bound",
    )
    require(
        limits["direct_edges_per_definition"] <= limits["aggregate_edges"],
        "one definition can exceed the graph edge bound",
    )
    require(
        limits["control_instruction_context_percent"]
        + minimums["repository_work_output_context_percent"]
        <= 100,
        "context reservations exceed 100 percent",
    )
    require(
        contract.duration_contract.get("total_includes_retry_backoff") is True
        and contract.duration_contract.get("total_includes_cancellation_drain") is True,
        "wall-clock disclosure must include retry and cancellation drain",
    )


def _load_protocol_uncached(path: Path) -> ProtocolContract:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "protocol file cannot be read"
        ) from exc
    try:
        document = json.loads(raw, object_pairs_hook=_json_pairs)
    except (_DuplicateJsonKey, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "protocol file is not strict JSON"
        ) from exc
    root = _as_mapping(document, "protocol")
    expected_root: Final = (
        "schema_version",
        "protocol_id",
        "protocol_version",
        "name_pattern",
        "stack_scope_pattern",
        "metadata_namespace",
        "component_kinds",
        "project_extension_roster_fields",
        "canonical_dialect",
        "router",
        "metadata_schema",
        "capability_ids",
        "classes",
        "cli_schema_spelling",
        "digest_domains",
        "packaging",
        "record_schemas",
        "defaults",
        "minimums",
        "limits",
        "duration_contract",
        "errors",
    )
    _exact_keys(
        root,
        allowed=expected_root,
        required=expected_root,
        context="protocol",
    )
    schema_version = _as_int(root["schema_version"], "schema_version")
    if schema_version != 1:
        raise ProtocolValidationError(
            "PROTOCOL_VERSION_UNSUPPORTED",
            "unsupported protocol schema version",
            "public_bug",
        )
    name_pattern_text = _as_string(root["name_pattern"], "name_pattern")
    try:
        name_pattern = re.compile(name_pattern_text)
    except re.error as exc:
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "name_pattern is not a valid regex"
        ) from exc
    stack_scope_pattern_text = _as_string(
        root["stack_scope_pattern"], "stack_scope_pattern"
    )
    try:
        stack_scope_pattern = re.compile(stack_scope_pattern_text)
    except re.error as exc:
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "stack_scope_pattern is not a valid regex"
        ) from exc

    metadata_raw = _as_mapping(root["metadata_schema"], "metadata_schema")
    metadata_schema_fields: Final = (
        "top_level_fields",
        "namespace_fields",
        "required_namespace_fields",
        "direct_edge_fields",
        "capability_fields",
        "bounded_loop_fields",
    )
    _exact_keys(
        metadata_raw,
        allowed=metadata_schema_fields,
        required=metadata_schema_fields,
        context="metadata_schema",
    )
    metadata_schema = MappingProxyType(
        {
            key: _string_tuple(value, f"metadata_schema.{key}")
            for key, value in metadata_raw.items()
        }
    )
    classes_raw = _as_mapping(root["classes"], "classes")
    class_fields: Final = (
        "mutation",
        "interaction",
        "base_support_state",
        "applicability",
        "effective_availability",
        "release_stage",
        "lifecycle_stage",
        "reporting",
        "fallback",
        "tool_profile",
        "resource_origin",
        "admission_source",
        "project_selection_source",
        "run_state",
        "approval_state",
        "approval_kind",
        "mutation_state",
        "terminal_state",
        "gate_result",
        "log_status",
        "effect_kind",
        "egress_transport",
        "evidence_status",
    )
    _exact_keys(
        classes_raw,
        allowed=class_fields,
        required=class_fields,
        context="classes",
    )
    classes = MappingProxyType(
        {
            key: frozenset(_string_tuple(value, f"classes.{key}"))
            for key, value in classes_raw.items()
        }
    )
    record_raw = _as_mapping(root["record_schemas"], "record_schemas")
    record_schema_fields: Final = (
        "direct_edges",
        "capability_summary",
        "node_record",
        "support_record",
        "runtime_file_record",
        "compatibility_predicate_record",
        "availability_record",
        "qualification_record",
        "runtime_record",
        "digest_record",
        "agent_scope_record",
        "resolver_source_record",
        "resolver_resource_record",
        "project_root_record",
        "project_selection_record",
        "project_admission_record",
        "execution_frame",
        "run_snapshot",
        "preflight_record",
        "approval_record",
        "operation_permit",
        "receipt_event",
        "log_event",
        "terminal_record",
        "trace_event",
    )
    _exact_keys(
        record_raw,
        allowed=record_schema_fields,
        required=record_schema_fields,
        context="record_schemas",
    )
    record_schemas: dict[str, tuple[str, ...]] = {}
    for key, value in record_raw.items():
        schema = _as_mapping(value, f"record_schemas.{key}")
        _exact_keys(
            schema,
            allowed=("required",),
            required=("required",),
            context=f"record_schemas.{key}",
        )
        record_schemas[key] = _string_tuple(
            schema["required"], f"record_schemas.{key}.required"
        )

    def integer_mapping(field: str) -> Mapping[str, int]:
        values = _as_mapping(root[field], field)
        return MappingProxyType(
            {key: _as_int(value, f"{field}.{key}") for key, value in values.items()}
        )

    errors_raw = _as_mapping(root["errors"], "errors")
    errors = MappingProxyType(
        {key: _as_string(value, f"errors.{key}") for key, value in errors_raw.items()}
    )
    reporting_values = classes.get("reporting", frozenset())
    if set(errors.values()) - reporting_values:
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "an error has an unknown reporting class"
        )
    if "UNKNOWN_ERROR" not in errors or errors["UNKNOWN_ERROR"] != "private_security":
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "unknown errors must fail private"
        )

    dialect_raw = _as_mapping(root["canonical_dialect"], "canonical_dialect")
    dialect_fields: Final = (
        "nested_command",
        "plugin_root",
        "skill_or_resource_load",
        "subagent_dispatch",
        "interaction_request",
        "tool_capability",
        "claude_hook",
        "claude_presentation",
    )
    _exact_keys(
        dialect_raw,
        allowed=dialect_fields,
        required=dialect_fields,
        context="canonical_dialect",
    )
    for dialect_name, dialect_value in dialect_raw.items():
        dialect_mapping = _as_mapping(
            dialect_value, f"canonical_dialect.{dialect_name}"
        )
        _exact_keys(
            dialect_mapping,
            allowed=("source_construct", "typed_operation", "required_capability"),
            required=("source_construct", "typed_operation", "required_capability"),
            context=f"canonical_dialect.{dialect_name}",
        )
    router_raw = _as_mapping(root["router"], "router")
    _exact_keys(
        router_raw,
        allowed=(
            "entry_skill",
            "command_prefix",
            "reserved_tokens",
            "zero_mutation_required_capabilities",
        ),
        required=(
            "entry_skill",
            "command_prefix",
            "reserved_tokens",
            "zero_mutation_required_capabilities",
        ),
        context="router",
    )
    entry_skill = _as_string(router_raw["entry_skill"], "router.entry_skill")
    command_prefix = _as_string(router_raw["command_prefix"], "router.command_prefix")
    reserved_tokens = _string_tuple(
        router_raw["reserved_tokens"], "router.reserved_tokens"
    )
    zero_mutation_required_capabilities = _string_tuple(
        router_raw["zero_mutation_required_capabilities"],
        "router.zero_mutation_required_capabilities",
    )
    if (
        entry_skill != "lp"
        or command_prefix != "lp-"
        or reserved_tokens != tuple(sorted(set(reserved_tokens)))
        or set(reserved_tokens) != {"help", "lp", "skill"}
    ):
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "router grammar authority differs"
        )
    cli_raw = _as_mapping(root["cli_schema_spelling"], "cli_schema_spelling")
    _exact_keys(
        cli_raw,
        allowed=("inventory", "test-candidate", "generate"),
        required=("inventory", "test-candidate", "generate"),
        context="cli_schema_spelling",
    )
    digest_raw = _as_mapping(root["digest_domains"], "digest_domains")
    _exact_keys(
        digest_raw,
        allowed=("runtime_payload_digest", "evidence_digest", "artifact_digest"),
        required=("runtime_payload_digest", "evidence_digest", "artifact_digest"),
        context="digest_domains",
    )
    packaging_raw = _as_mapping(root["packaging"], "packaging")
    _exact_keys(
        packaging_raw,
        allowed=(
            "manifest_shared_fields",
            "manifest_host_fields",
            "runtime_helpers",
            "generated_slots",
            "documentation_regions",
        ),
        required=(
            "manifest_shared_fields",
            "manifest_host_fields",
            "runtime_helpers",
            "generated_slots",
            "documentation_regions",
        ),
        context="packaging",
    )
    manifest_shared_fields = _string_tuple(
        packaging_raw["manifest_shared_fields"],
        "packaging.manifest_shared_fields",
    )
    if set(manifest_shared_fields) != {
        "author",
        "description",
        "homepage",
        "keywords",
        "license",
        "name",
        "repository",
        "version",
    }:
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "manifest shared-field authority differs"
        )
    runtime_helpers = _string_tuple(
        packaging_raw["runtime_helpers"], "packaging.runtime_helpers"
    )
    generated_slots = _string_tuple(
        packaging_raw["generated_slots"], "packaging.generated_slots"
    )
    for name, values in (
        ("manifest_shared_fields", manifest_shared_fields),
        ("runtime_helpers", runtime_helpers),
        ("generated_slots", generated_slots),
    ):
        if values != tuple(sorted(values)):
            raise ProtocolValidationError(
                "PROTOCOL_FILE_INVALID", f"packaging.{name} must be sorted"
            )
    manifest_host_fields = _as_mapping(
        packaging_raw["manifest_host_fields"], "packaging.manifest_host_fields"
    )
    _exact_keys(
        manifest_host_fields,
        allowed=("skills",),
        required=("skills",),
        context="packaging.manifest_host_fields",
    )
    if manifest_host_fields["skills"] != "./codex/skills/":
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "Codex skill discovery path differs"
        )
    documentation_regions = _as_mapping(
        packaging_raw["documentation_regions"], "packaging.documentation_regions"
    )
    _exact_keys(
        documentation_regions,
        allowed=("README.md", "docs/guides/HOW_IT_WORKS.md"),
        required=("README.md", "docs/guides/HOW_IT_WORKS.md"),
        context="packaging.documentation_regions",
    )
    if set(runtime_helpers) & set(generated_slots):
        raise ProtocolValidationError(
            "PROTOCOL_FILE_INVALID", "runtime helpers overlap generated slots"
        )
    packaging = MappingProxyType(
        {
            "manifest_shared_fields": manifest_shared_fields,
            "manifest_host_fields": MappingProxyType(
                {
                    key: _as_string(value, f"packaging.manifest_host_fields.{key}")
                    for key, value in manifest_host_fields.items()
                }
            ),
            "runtime_helpers": runtime_helpers,
            "generated_slots": generated_slots,
            "documentation_regions": MappingProxyType(
                {
                    key: _as_string(value, f"packaging.documentation_regions.{key}")
                    for key, value in documentation_regions.items()
                }
            ),
        }
    )
    duration_raw = _as_mapping(root["duration_contract"], "duration_contract")
    contract = ProtocolContract(
        path=path,
        digest=hashlib.sha256(raw).hexdigest(),
        schema_version=schema_version,
        protocol_id=_as_string(root["protocol_id"], "protocol_id"),
        protocol_version=_as_string(root["protocol_version"], "protocol_version"),
        name_pattern=name_pattern,
        stack_scope_pattern=stack_scope_pattern,
        metadata_namespace=_as_string(root["metadata_namespace"], "metadata_namespace"),
        component_kinds=frozenset(
            _string_tuple(root["component_kinds"], "component_kinds")
        ),
        project_extension_roster_fields=_string_tuple(
            root["project_extension_roster_fields"],
            "project_extension_roster_fields",
        ),
        canonical_dialect=_immutable_nested_mapping(dialect_raw, "canonical_dialect"),
        router=MappingProxyType(
            {
                "entry_skill": entry_skill,
                "command_prefix": command_prefix,
                "reserved_tokens": reserved_tokens,
                "zero_mutation_required_capabilities": zero_mutation_required_capabilities,
            }
        ),
        metadata_schema=metadata_schema,
        capability_ids=frozenset(
            _string_tuple(root["capability_ids"], "capability_ids")
        ),
        classes=classes,
        cli_schema_spelling=MappingProxyType(
            {
                key: _as_string(value, f"cli_schema_spelling.{key}")
                for key, value in cli_raw.items()
            }
        ),
        digest_domains=MappingProxyType(
            {
                key: _freeze_mapping(_as_mapping(value, f"digest_domains.{key}"))
                for key, value in digest_raw.items()
            }
        ),
        packaging=packaging,
        record_schemas=MappingProxyType(record_schemas),
        defaults=integer_mapping("defaults"),
        minimums=integer_mapping("minimums"),
        limits=integer_mapping("limits"),
        duration_contract=MappingProxyType(
            {
                key: _as_bool(value, f"duration_contract.{key}")
                for key, value in duration_raw.items()
            }
        ),
        errors=errors,
    )
    if any(
        entry["required_capability"] not in contract.capability_ids
        for entry in contract.canonical_dialect.values()
    ):
        raise _error(
            contract,
            "PROTOCOL_FILE_INVALID",
            "canonical dialect references an unknown capability",
        )
    if set(zero_mutation_required_capabilities) - contract.capability_ids:
        raise _error(
            contract,
            "PROTOCOL_FILE_INVALID",
            "router zero-mutation requirements reference an unknown capability",
        )
    _validate_cross_limits(contract)
    if contract.cli_schema_spelling.get("test-candidate") != "test_candidate":
        raise _error(
            contract,
            "PROTOCOL_FILE_INVALID",
            "CLI test-candidate must map to schema test_candidate",
        )
    return contract


@functools.cache
def _load_default_protocol() -> ProtocolContract:
    return _load_protocol_uncached(DEFAULT_PROTOCOL_PATH)


def load_protocol(path: Path | None = None) -> ProtocolContract:
    """Load and strictly validate the protocol contract."""
    if path is None or path.resolve() == DEFAULT_PROTOCOL_PATH.resolve():
        return _load_default_protocol()
    return _load_protocol_uncached(path)


def enforce_limit(
    limit_name: str,
    observed: int,
    contract: ProtocolContract | None = None,
) -> int:
    """Validate one non-negative observation against a protocol maximum."""
    protocol = contract or load_protocol()
    if limit_name not in protocol.limits:
        raise _error(protocol, "PROTOCOL_VALUE_INVALID", "unknown limit name")
    if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
        raise _error(protocol, "PROTOCOL_TYPE_INVALID", "observed must be an integer")
    if observed > protocol.limits[limit_name]:
        raise _error(protocol, "LIMIT_EXCEEDED", f"{limit_name} exceeds its limit")
    return observed


def enforce_minimum(
    minimum_name: str,
    observed: int,
    contract: ProtocolContract | None = None,
) -> int:
    protocol = contract or load_protocol()
    if minimum_name not in protocol.minimums:
        raise _error(protocol, "PROTOCOL_VALUE_INVALID", "unknown minimum name")
    if isinstance(observed, bool) or not isinstance(observed, int):
        raise _error(protocol, "PROTOCOL_TYPE_INVALID", "observed must be an integer")
    if observed < protocol.minimums[minimum_name]:
        raise _error(protocol, "LIMIT_EXCEEDED", f"{minimum_name} is below its minimum")
    return observed


def estimate_input_tokens(payload: bytes | str) -> int:
    """Apply the protocol's conservative one-token-per-UTF-8-byte estimate."""
    encoded = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    return len(encoded)


def schema_stage_for_cli(
    subcommand: str, contract: ProtocolContract | None = None
) -> str:
    """Translate CLI spelling to schema spelling without accepting aliases."""
    protocol = contract or load_protocol()
    try:
        return protocol.cli_schema_spelling[subcommand]
    except KeyError as exc:
        raise _error(
            protocol,
            "PROTOCOL_VALUE_INVALID",
            "unknown protocol CLI subcommand",
        ) from exc


def _constructed_size(value: object, protocol: ProtocolContract) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, bool):
        return 1
    if isinstance(value, float) and not math.isfinite(value):
        raise _error(
            protocol, "METADATA_INVALID", "non-finite YAML numbers are forbidden"
        )
    if isinstance(value, (int, float)):
        return len(str(value).encode("ascii"))
    if isinstance(value, list):
        return sum(_constructed_size(item, protocol) for item in value)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise _error(
                protocol,
                "METADATA_INVALID",
                "YAML mappings must use string keys",
            )
        return sum(
            _constructed_size(key, protocol) + _constructed_size(item, protocol)
            for key, item in value.items()
        )
    raise _error(
        protocol,
        "METADATA_INVALID",
        "YAML contains a non-JSON scalar type",
    )


def validate_constructed_yaml_size(
    value: object, contract: ProtocolContract | None = None
) -> int:
    protocol = contract or load_protocol()
    size = _constructed_size(value, protocol)
    if size > protocol.limits["yaml_aggregate_bytes"]:
        raise _error(
            protocol,
            "YAML_AGGREGATE_LIMIT_EXCEEDED",
            "constructed YAML exceeds aggregate limit",
        )
    return size


def _inspect_yaml_events(text: str, protocol: ProtocolContract) -> None:
    documents = 0
    nodes = 0
    depth = 0
    max_depth = 0
    try:
        events = yaml.parse(text, Loader=yaml.SafeLoader)
        for event in events:
            if isinstance(event, DocumentStartEvent):
                documents += 1
                if documents > 1:
                    raise _error(
                        protocol,
                        "YAML_MULTIDOC_FORBIDDEN",
                        "multiple YAML documents are forbidden",
                    )
            if isinstance(event, AliasEvent):
                raise _error(
                    protocol,
                    "YAML_ALIAS_FORBIDDEN",
                    "YAML aliases are forbidden",
                )
            if getattr(event, "anchor", None) is not None:
                raise _error(
                    protocol,
                    "YAML_ANCHOR_FORBIDDEN",
                    "YAML anchors are forbidden",
                )
            if getattr(event, "tag", None) is not None:
                raise _error(
                    protocol,
                    "YAML_EXPLICIT_TAG_FORBIDDEN",
                    "explicit YAML tags are forbidden",
                )
            if isinstance(event, (MappingStartEvent, SequenceStartEvent)):
                nodes += 1
                depth += 1
                max_depth = max(max_depth, depth)
            elif isinstance(event, ScalarEvent):
                nodes += 1
                max_depth = max(max_depth, depth + 1)
                if event.value == "<<":
                    raise _error(
                        protocol,
                        "YAML_MERGE_KEY_FORBIDDEN",
                        "YAML merge keys are forbidden",
                    )
                if (
                    len(event.value.encode("utf-8"))
                    > protocol.limits["yaml_scalar_bytes"]
                ):
                    raise _error(
                        protocol,
                        "YAML_SCALAR_LIMIT_EXCEEDED",
                        "YAML scalar exceeds its limit",
                    )
            elif isinstance(event, (MappingEndEvent, SequenceEndEvent)):
                depth -= 1
            if nodes > protocol.limits["yaml_nodes"]:
                raise _error(
                    protocol,
                    "YAML_NODE_LIMIT_EXCEEDED",
                    "YAML node count exceeds its limit",
                )
            if max_depth > protocol.limits["yaml_depth"]:
                raise _error(
                    protocol,
                    "YAML_DEPTH_LIMIT_EXCEEDED",
                    "YAML nesting exceeds its limit",
                )
    except ProtocolValidationError:
        raise
    except (ValueError, yaml.YAMLError) as exc:
        raise _error(protocol, "YAML_SYNTAX_INVALID", "YAML syntax is invalid") from exc


def strict_load_yaml(
    source: bytes | str,
    *,
    source_limit: str = "frontmatter_bytes",
    allowed_fields: Iterable[str] | None = None,
    required_fields: Iterable[str] = (),
    contract: ProtocolContract | None = None,
) -> Mapping[str, Any]:
    """Load one bounded YAML mapping with hostile YAML features disabled."""
    protocol = contract or load_protocol()
    raw = source if isinstance(source, bytes) else source.encode("utf-8")
    if source_limit not in protocol.limits:
        raise _error(protocol, "PROTOCOL_VALUE_INVALID", "unknown source limit")
    if len(raw) > protocol.limits[source_limit]:
        raise _error(
            protocol,
            "YAML_SOURCE_TOO_LARGE",
            "YAML source exceeds its limit",
        )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _error(
            protocol, "YAML_INVALID_UTF8", "YAML source is not valid UTF-8"
        ) from exc
    _inspect_yaml_events(text, protocol)
    try:
        loaded = yaml.load(text, Loader=_StrictSafeLoader)  # noqa: S506  # nosec B506
    except _DuplicateYamlKey as exc:
        raise _error(
            protocol, "YAML_DUPLICATE_KEY", "YAML contains a duplicate key"
        ) from exc
    except yaml.YAMLError as exc:
        raise _error(protocol, "YAML_SYNTAX_INVALID", "YAML syntax is invalid") from exc
    if not isinstance(loaded, Mapping) or any(
        not isinstance(key, str) for key in loaded
    ):
        raise _error(
            protocol,
            "METADATA_INVALID",
            "YAML root must be a string-keyed mapping",
        )
    validate_constructed_yaml_size(loaded, protocol)
    if allowed_fields is not None:
        _exact_keys(
            loaded,
            allowed=allowed_fields,
            required=required_fields,
            context="YAML mapping",
            code="METADATA_UNKNOWN_FIELD",
            contract=protocol,
        )
    return MappingProxyType(dict(loaded))


def extract_frontmatter(
    document: bytes | str,
    contract: ProtocolContract | None = None,
) -> tuple[Mapping[str, Any], bytes]:
    """Extract and strictly parse one leading Markdown frontmatter block."""
    protocol = contract or load_protocol()
    raw = document if isinstance(document, bytes) else document.encode("utf-8")
    if not raw.startswith(b"---\n"):
        raise _error(protocol, "FRONTMATTER_MISSING", "leading frontmatter is required")
    end = raw.find(b"\n---\n", 4)
    if end < 0:
        raise _error(
            protocol,
            "FRONTMATTER_UNTERMINATED",
            "frontmatter closing delimiter is missing",
        )
    frontmatter = raw[4:end]
    body = raw[end + 5 :]
    if len(frontmatter) > protocol.limits["frontmatter_bytes"]:
        raise _error(protocol, "FRONTMATTER_TOO_LARGE", "frontmatter exceeds its limit")
    if len(body) > protocol.limits["body_bytes"]:
        raise _error(protocol, "BODY_TOO_LARGE", "Markdown body exceeds its limit")
    loaded = strict_load_yaml(
        frontmatter,
        allowed_fields=protocol.metadata_schema["top_level_fields"],
        contract=protocol,
    )
    return loaded, body


def _normalize_values(
    value: object,
    context: str,
    protocol: ProtocolContract,
    *,
    names: bool = False,
) -> tuple[str, ...]:
    try:
        values = _string_tuple(value, context)
    except ProtocolValidationError as exc:
        raise _error(protocol, exc.code, str(exc)) from exc
    for item in values:
        if len(item.encode("utf-8")) > protocol.limits["yaml_scalar_bytes"]:
            raise _error(
                protocol,
                "YAML_SCALAR_LIMIT_EXCEEDED",
                f"{context} contains an oversized scalar",
            )
        if names and protocol.name_pattern.fullmatch(item) is None:
            raise _error(protocol, "METADATA_INVALID", f"{context} has an invalid ID")
    return values


def _normalize_direct_edges(
    value: object,
    protocol: ProtocolContract,
    *,
    metadata_spelling: bool,
) -> DirectEdges:
    mapping = _as_mapping(value, "direct edges")
    declared_fields = protocol.metadata_schema["direct_edge_fields"]
    fields = (
        declared_fields
        if metadata_spelling
        else tuple(field.replace("-", "_") for field in declared_fields)
    )
    _exact_keys(
        mapping,
        allowed=fields,
        required=() if metadata_spelling else fields,
        context="direct edges",
        code="METADATA_UNKNOWN_FIELD" if metadata_spelling else "RECORD_INVALID",
        contract=protocol,
    )

    def get(field: str, *, names: bool = False) -> tuple[str, ...]:
        key = field if metadata_spelling else field.replace("-", "_")
        return _normalize_values(mapping.get(key, []), key, protocol, names=names)

    direct = DirectEdges(
        commands=get("commands", names=True),
        skills=get("skills", names=True),
        agents=get("agents", names=True),
        references=get("references"),
        assets=get("assets"),
        scripts=get("scripts"),
        external_tools=get("external-tools"),
    )
    if direct.count > protocol.limits["direct_edges_per_definition"]:
        raise _error(
            protocol,
            "METADATA_EDGE_LIMIT_EXCEEDED",
            "direct edge count exceeds its limit",
        )
    return direct


def _normalize_capabilities(
    value: object,
    protocol: ProtocolContract,
    *,
    metadata_spelling: bool,
) -> CapabilitySummary:
    mapping = _as_mapping(value, "capabilities")
    declared_fields = protocol.metadata_schema["capability_fields"]
    fields = (
        declared_fields
        if metadata_spelling
        else tuple(field.replace("-", "_") for field in declared_fields)
    )
    required_fields = ("mutation", "interaction") if metadata_spelling else fields
    _exact_keys(
        mapping,
        allowed=fields,
        required=required_fields,
        context="capabilities",
        code="METADATA_UNKNOWN_FIELD" if metadata_spelling else "RECORD_INVALID",
        contract=protocol,
    )

    def key(name: str) -> str:
        return name if metadata_spelling else name.replace("-", "_")

    required = _normalize_values(
        mapping.get(key("required"), []), "capabilities.required", protocol
    )
    unknown = sorted(set(required) - protocol.capability_ids)
    if unknown:
        raise _error(
            protocol,
            "METADATA_INVALID",
            "capabilities.required contains an unknown capability",
        )
    mutation = protocol.require_enum("mutation", mapping[key("mutation")])
    interaction = protocol.require_enum("interaction", mapping[key("interaction")])
    external_data_egress = mapping.get(key("external-data-egress"), False)
    if not isinstance(external_data_egress, bool):
        raise _error(
            protocol,
            "METADATA_INVALID",
            "external-data-egress must be a boolean",
        )
    write_scopes = _normalize_values(
        mapping.get(key("write-scopes"), []),
        "capabilities.write-scopes",
        protocol,
    )
    tool_profile = protocol.require_enum(
        "tool_profile", mapping.get(key("tool-profile"), "inspect_only")
    )
    fallback = protocol.require_enum("fallback", mapping.get(key("fallback"), "none"))
    if mutation == "none" and write_scopes:
        raise _error(
            protocol,
            "METADATA_INVALID",
            "mutation none cannot declare write scopes",
        )
    if mutation != "none" and tool_profile in {"inspect_only", "read_only"}:
        raise _error(
            protocol,
            "METADATA_INVALID",
            "a mutating declaration requires a mutating tool profile",
        )
    if external_data_egress and "serialized_payload_mediation" not in required:
        raise _error(
            protocol,
            "METADATA_INVALID",
            "external egress requires serialized_payload_mediation",
        )
    return CapabilitySummary(
        required=required,
        mutation=mutation,
        interaction=interaction,
        external_data_egress=external_data_egress,
        write_scopes=write_scopes,
        tool_profile=tool_profile,
        fallback=fallback,
    )


def normalize_metadata(
    value: object,
    contract: ProtocolContract | None = None,
) -> NormalizedMetadata:
    """Normalize the value beneath the ``x-launchpad`` namespace."""
    protocol = contract or load_protocol()
    mapping = _as_mapping(value, protocol.metadata_namespace)
    _exact_keys(
        mapping,
        allowed=protocol.metadata_schema["namespace_fields"],
        required=protocol.metadata_schema["required_namespace_fields"],
        context=protocol.metadata_namespace,
        code="METADATA_UNKNOWN_FIELD",
        contract=protocol,
    )
    schema_version = mapping["schema-version"]
    if isinstance(schema_version, bool) or schema_version != protocol.schema_version:
        raise _error(
            protocol,
            "METADATA_INVALID",
            "metadata schema-version does not match the protocol",
        )
    component_kind = mapping["component-kind"]
    if (
        not isinstance(component_kind, str)
        or component_kind not in protocol.component_kinds
    ):
        raise _error(protocol, "METADATA_INVALID", "unknown component-kind")
    direct = _normalize_direct_edges(
        mapping.get("direct", {}), protocol, metadata_spelling=True
    )
    capabilities = _normalize_capabilities(
        mapping["capabilities"], protocol, metadata_spelling=True
    )
    bounded_loop: BoundedLoop | None = None
    if "bounded-loop" in mapping:
        loop = _as_mapping(mapping["bounded-loop"], "bounded-loop")
        fields = protocol.metadata_schema["bounded_loop_fields"]
        _exact_keys(
            loop,
            allowed=fields,
            required=fields,
            context="bounded-loop",
            code="METADATA_UNKNOWN_FIELD",
            contract=protocol,
        )
        iterations = loop["max-iterations"]
        if (
            isinstance(iterations, bool)
            or not isinstance(iterations, int)
            or iterations < 1
            or iterations > protocol.limits["bounded_loop_iterations"]
        ):
            raise _error(
                protocol, "METADATA_INVALID", "bounded-loop iterations are invalid"
            )
        reentry = loop["reentry-command"]
        if (
            not isinstance(reentry, str)
            or protocol.name_pattern.fullmatch(reentry) is None
        ):
            raise _error(
                protocol, "METADATA_INVALID", "bounded-loop command is invalid"
            )
        bounded_loop = BoundedLoop(iterations, reentry)
    return NormalizedMetadata(
        schema_version=schema_version,
        component_kind=component_kind,
        direct=direct,
        capabilities=capabilities,
        bounded_loop=bounded_loop,
    )


def normalize_document_metadata(
    document: bytes | str,
    contract: ProtocolContract | None = None,
) -> tuple[NormalizedMetadata, bytes]:
    """Parse Markdown and normalize its namespaced LaunchPad declaration."""
    protocol = contract or load_protocol()
    frontmatter, body = extract_frontmatter(document, protocol)
    if protocol.metadata_namespace not in frontmatter:
        raise _error(
            protocol,
            "METADATA_INVALID",
            f"{protocol.metadata_namespace} metadata is required",
        )
    return normalize_metadata(frontmatter[protocol.metadata_namespace], protocol), body


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: object, context: str, protocol: ProtocolContract) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise _error(protocol, "DIGEST_INVALID", f"{context} is not a SHA-256 digest")
    return value


def _record_mapping(
    value: object,
    schema_name: str,
    protocol: ProtocolContract,
) -> Mapping[str, Any]:
    mapping = _as_mapping(value, schema_name)
    fields = protocol.record_schemas[schema_name]
    _exact_keys(
        mapping,
        allowed=fields,
        required=fields,
        context=schema_name,
        code="RECORD_INVALID",
        contract=protocol,
    )
    return mapping


def _record_id(value: object, context: str, protocol: ProtocolContract) -> str:
    text = _as_string(value, context)
    if protocol.name_pattern.fullmatch(text) is None:
        raise _error(protocol, "RECORD_INVALID", f"{context} is invalid")
    return text


def _relative_path(value: object, context: str, protocol: ProtocolContract) -> str:
    text = _as_string(value, context)
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise _error(protocol, "RECORD_INVALID", f"{context} is not a relative path")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise _error(protocol, "RECORD_INVALID", f"{context} contains a control")
    return text


def normalize_node_record(
    value: object, contract: ProtocolContract | None = None
) -> NodeRecord:
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "node_record", protocol)
    kind = mapping["kind"]
    if not isinstance(kind, str) or kind not in protocol.component_kinds:
        raise _error(protocol, "RECORD_INVALID", "node kind is invalid")
    return NodeRecord(
        id=_record_id(mapping["id"], "node id", protocol),
        kind=kind,
        source_path=_relative_path(mapping["source_path"], "source_path", protocol),
        source_digest=_digest(mapping["source_digest"], "source_digest", protocol),
        metadata_digest=_digest(
            mapping["metadata_digest"], "metadata_digest", protocol
        ),
        aggregate_digest=_digest(
            mapping["aggregate_digest"], "aggregate_digest", protocol
        ),
        direct=_normalize_direct_edges(
            mapping["direct"], protocol, metadata_spelling=False
        ),
        capabilities=_normalize_capabilities(
            mapping["capabilities"], protocol, metadata_spelling=False
        ),
    )


def normalize_support_record(
    value: object, contract: ProtocolContract | None = None
) -> SupportRecord:
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "support_record", protocol)
    reasons = _normalize_values(
        mapping["blocked_reason_codes"], "blocked_reason_codes", protocol
    )
    if set(reasons) - set(protocol.errors):
        raise _error(protocol, "RECORD_INVALID", "unknown blocked reason code")
    state = protocol.require_enum("base_support_state", mapping["base_support_state"])
    if state == "supported" and reasons:
        raise _error(
            protocol,
            "RECORD_INVALID",
            "supported records cannot contain blocked reasons",
        )
    if state == "blocked" and not reasons:
        raise _error(
            protocol,
            "RECORD_INVALID",
            "blocked records require at least one reason",
        )
    return SupportRecord(
        resource_id=_record_id(mapping["resource_id"], "resource_id", protocol),
        base_support_state=state,
        blocked_reason_codes=reasons,
        fallback=protocol.require_enum("fallback", mapping["fallback"]),
    )


def normalize_runtime_file_record(
    value: object, contract: ProtocolContract | None = None
) -> RuntimeFileRecord:
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "runtime_file_record", protocol)
    size = _as_int(mapping["size"], "runtime file size")
    if size < 0:
        raise _error(protocol, "RECORD_INVALID", "runtime file size is negative")
    return RuntimeFileRecord(
        path=_relative_path(mapping["path"], "runtime file path", protocol),
        digest=_digest(mapping["digest"], "runtime file digest", protocol),
        size=size,
    )


def normalize_compatibility_predicate_record(
    value: object, contract: ProtocolContract | None = None
) -> CompatibilityPredicateRecord:
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "compatibility_predicate_record", protocol)
    capabilities = _normalize_values(
        mapping["required_capabilities"], "required_capabilities", protocol
    )
    if set(capabilities) - protocol.capability_ids:
        raise _error(protocol, "RECORD_INVALID", "predicate capability is unknown")
    versions_raw = _as_mapping(mapping["tool_versions"], "tool_versions")
    versions = MappingProxyType(
        {
            _as_string(key, "tool name"): _as_string(version, "tool version")
            for key, version in sorted(versions_raw.items())
        }
    )
    reasons = _normalize_values(
        mapping["blocked_reason_codes"], "blocked_reason_codes", protocol
    )
    if set(reasons) - set(protocol.errors):
        raise _error(protocol, "RECORD_INVALID", "unknown blocked reason code")
    state = protocol.require_enum("base_support_state", mapping["base_support_state"])
    if (state == "supported") == bool(reasons):
        raise _error(
            protocol,
            "RECORD_INVALID",
            "predicate support state and blocked reasons disagree",
        )
    return CompatibilityPredicateRecord(
        predicate_id=_record_id(mapping["predicate_id"], "predicate_id", protocol),
        resource_id=_record_id(mapping["resource_id"], "resource_id", protocol),
        host=_as_string(mapping["host"], "host"),
        operating_system=_as_string(mapping["operating_system"], "operating_system"),
        required_capabilities=capabilities,
        tool_versions=versions,
        base_support_state=state,
        blocked_reason_codes=reasons,
        fallback=protocol.require_enum("fallback", mapping["fallback"]),
        qualification_ids=_normalize_values(
            mapping["qualification_ids"], "qualification_ids", protocol, names=True
        ),
    )


def normalize_availability_record(
    value: object, contract: ProtocolContract | None = None
) -> AvailabilityRecord:
    """Normalize a run-local availability result without changing base support."""
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "availability_record", protocol)
    reasons = _normalize_values(mapping["reason_codes"], "reason_codes", protocol)
    if set(reasons) - set(protocol.errors):
        raise _error(protocol, "RECORD_INVALID", "unknown availability reason code")
    applicability = protocol.require_enum("applicability", mapping["applicability"])
    availability = protocol.require_enum(
        "effective_availability", mapping["effective_availability"]
    )
    if availability == "available" and reasons:
        raise _error(
            protocol,
            "RECORD_INVALID",
            "available records cannot contain reason codes",
        )
    if availability == "blocked" and not reasons:
        raise _error(
            protocol,
            "RECORD_INVALID",
            "blocked availability requires at least one reason",
        )
    return AvailabilityRecord(
        resource_id=_record_id(mapping["resource_id"], "resource_id", protocol),
        applicability=applicability,
        effective_availability=availability,
        reason_codes=reasons,
    )


def normalize_qualification_record(
    value: object, contract: ProtocolContract | None = None
) -> QualificationRecord:
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "qualification_record", protocol)
    versions_raw = _as_mapping(mapping["tool_versions"], "tool_versions")
    versions = MappingProxyType(
        {
            _as_string(key, "tool name"): _as_string(version, "tool version")
            for key, version in versions_raw.items()
        }
    )
    return QualificationRecord(
        qualification_id=_record_id(
            mapping["qualification_id"], "qualification_id", protocol
        ),
        runtime_payload_digest=_digest(
            mapping["runtime_payload_digest"], "runtime_payload_digest", protocol
        ),
        host=_as_string(mapping["host"], "host"),
        operating_system=_as_string(mapping["operating_system"], "operating_system"),
        tool_versions=versions,
        receipt_ids=_normalize_values(mapping["receipt_ids"], "receipt_ids", protocol),
    )


def normalize_runtime_record(
    value: object, contract: ProtocolContract | None = None
) -> RuntimeRecord:
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "runtime_record", protocol)
    stage = protocol.require_enum("lifecycle_stage", mapping["stage"])
    release_stage = protocol.require_enum("release_stage", mapping["release_stage"])
    if mapping["protocol_version"] != protocol.protocol_version:
        raise _error(
            protocol, "PROTOCOL_VERSION_UNSUPPORTED", "runtime protocol mismatch"
        )
    protocol_digest = _digest(mapping["protocol_digest"], "protocol_digest", protocol)
    if protocol_digest != protocol.digest:
        raise _error(protocol, "INTEGRITY_MISMATCH", "protocol digest mismatch")
    runtime_digest_value = mapping["runtime_payload_digest"]
    runtime_digest: str | None
    if stage == "inventory":
        if runtime_digest_value is not None:
            raise _error(
                protocol,
                "RECORD_STAGE_INVALID",
                "inventory must not claim a runtime payload digest",
            )
        runtime_digest = None
    else:
        runtime_digest = _digest(
            runtime_digest_value, "runtime_payload_digest", protocol
        )

    nodes_value = mapping["nodes"]
    runtime_files_value = mapping["runtime_files"]
    support_value = mapping["support"]
    if (
        not isinstance(nodes_value, list)
        or not isinstance(runtime_files_value, list)
        or not isinstance(support_value, list)
    ):
        raise _error(
            protocol,
            "RECORD_INVALID",
            "nodes, runtime_files, and support must be lists",
        )
    nodes = tuple(normalize_node_record(item, protocol) for item in nodes_value)
    runtime_files = tuple(
        normalize_runtime_file_record(item, protocol) for item in runtime_files_value
    )
    support = tuple(normalize_support_record(item, protocol) for item in support_value)
    if (
        len(nodes)
        > len(protocol.component_kinds) * protocol.limits["definitions_per_type"]
    ):
        raise _error(protocol, "LIMIT_EXCEEDED", "runtime node table is too large")
    node_ids = [node.id for node in nodes]
    support_ids = [item.resource_id for item in support]
    runtime_paths = [item.path for item in runtime_files]
    if node_ids != sorted(node_ids) or len(node_ids) != len(set(node_ids)):
        raise _error(
            protocol, "RECORD_INVALID", "node records must be unique and sorted"
        )
    if support_ids != sorted(support_ids) or len(support_ids) != len(set(support_ids)):
        raise _error(
            protocol, "RECORD_INVALID", "support records must be unique and sorted"
        )
    if runtime_paths != sorted(runtime_paths) or len(runtime_paths) != len(
        set(runtime_paths)
    ):
        raise _error(
            protocol, "RECORD_INVALID", "runtime files must be unique and sorted"
        )
    root_ids = _normalize_values(mapping["root_ids"], "root_ids", protocol, names=True)
    if not set(root_ids).issubset(node_ids):
        raise _error(protocol, "RECORD_INVALID", "a root ID is absent from nodes")
    qualification_ids = _normalize_values(
        mapping["qualification_ids"], "qualification_ids", protocol, names=True
    )
    if stage == "release" and not qualification_ids:
        raise _error(
            protocol,
            "RECORD_STAGE_INVALID",
            "release records require qualification IDs",
        )
    generated_slots = tuple(
        _relative_path(item, "generated slot", protocol)
        for item in _normalize_values(
            mapping["generated_slots"], "generated_slots", protocol
        )
    )
    return RuntimeRecord(
        stage=stage,
        release_stage=release_stage,
        protocol_version=protocol.protocol_version,
        protocol_digest=protocol_digest,
        runtime_payload_digest=runtime_digest,
        root_ids=root_ids,
        nodes=nodes,
        runtime_files=runtime_files,
        support=support,
        qualification_ids=qualification_ids,
        generated_slots=generated_slots,
    )


def normalize_digest_record(
    value: object, contract: ProtocolContract | None = None
) -> DigestRecord:
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "digest_record", protocol)
    return DigestRecord(
        runtime_payload_digest=_digest(
            mapping["runtime_payload_digest"], "runtime_payload_digest", protocol
        ),
        evidence_digest=_digest(
            mapping["evidence_digest"], "evidence_digest", protocol
        ),
        artifact_digest=_digest(
            mapping["artifact_digest"], "artifact_digest", protocol
        ),
    )


def normalize_agent_scope_record(
    value: object, contract: ProtocolContract | None = None
) -> AgentScopeRecord:
    """Normalize the pure stack-filter record supplied by corpus discovery."""
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "agent_scope_record", protocol)
    resource_id = _record_id(mapping["resource_id"], "resource_id", protocol)
    stack_scope = mapping["stack_scope"]
    if (
        not isinstance(stack_scope, str)
        or protocol.stack_scope_pattern.fullmatch(stack_scope) is None
    ):
        raise _error(protocol, "RECORD_INVALID", "stack_scope is invalid")
    return AgentScopeRecord(resource_id=resource_id, stack_scope=stack_scope)


def normalize_resolver_source_record(
    value: object, contract: ProtocolContract | None = None
) -> ResolverSourceRecord:
    """Normalize one immutable command, skill, or agent inspection."""
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "resolver_source_record", protocol)
    kind = mapping["kind"]
    if not isinstance(kind, str) or kind not in protocol.component_kinds:
        raise _error(protocol, "RECORD_INVALID", "resolver source kind is invalid")
    origin = protocol.require_enum("resource_origin", mapping["origin"])
    user_invocable = _as_bool(mapping["user_invocable"], "user_invocable")
    quarantined = _as_bool(mapping["quarantined"], "quarantined")
    if (origin == "project") != quarantined:
        raise _error(
            protocol, "RECORD_INVALID", "source quarantine differs from origin"
        )
    if user_invocable and (origin != "built_in" or kind == "agent"):
        raise _error(protocol, "RECORD_INVALID", "source cannot be user invocable")
    return ResolverSourceRecord(
        resource_id=_record_id(mapping["resource_id"], "resource_id", protocol),
        kind=kind,
        origin=origin,
        source_path=_relative_path(mapping["source_path"], "source_path", protocol),
        source_digest=_digest(mapping["source_digest"], "source_digest", protocol),
        metadata_digest=_digest(
            mapping["metadata_digest"], "metadata_digest", protocol
        ),
        size=_as_nonnegative_int(mapping["size"], "size"),
        user_invocable=user_invocable,
        quarantined=quarantined,
    )


def normalize_resolver_resource_record(
    value: object, contract: ProtocolContract | None = None
) -> ResolverResourceRecord:
    """Normalize one owner-confined resource inspection."""
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "resolver_resource_record", protocol)
    owner_kind = mapping["owner_kind"]
    if not isinstance(owner_kind, str) or owner_kind not in protocol.component_kinds:
        raise _error(protocol, "RECORD_INVALID", "resource owner kind is invalid")
    origin = protocol.require_enum("resource_origin", mapping["origin"])
    quarantined = _as_bool(mapping["quarantined"], "quarantined")
    if (origin == "project") != quarantined:
        raise _error(
            protocol, "RECORD_INVALID", "resource quarantine differs from origin"
        )
    return ResolverResourceRecord(
        owner_id=_record_id(mapping["owner_id"], "owner_id", protocol),
        owner_kind=owner_kind,
        origin=origin,
        relative_path=_relative_path(
            mapping["relative_path"], "relative_path", protocol
        ),
        source_digest=_digest(mapping["source_digest"], "source_digest", protocol),
        size=_as_nonnegative_int(mapping["size"], "size"),
        quarantined=quarantined,
    )


def normalize_project_root_record(
    value: object, contract: ProtocolContract | None = None
) -> ProjectRootRecord:
    """Normalize an explicitly anchored active-workspace root."""
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "project_root_record", protocol)
    canonical_root = _as_string(mapping["canonical_root"], "canonical_root")
    path = Path(canonical_root)
    if not path.is_absolute() or any(ord(char) < 32 for char in canonical_root):
        raise _error(protocol, "RECORD_INVALID", "canonical_root is invalid")
    return ProjectRootRecord(
        canonical_root=canonical_root,
        repository_identity=_digest(
            mapping["repository_identity"], "repository_identity", protocol
        ),
        root_device=_as_nonnegative_int(mapping["root_device"], "root_device"),
        root_inode=_as_nonnegative_int(mapping["root_inode"], "root_inode"),
    )


def normalize_project_selection_record(
    value: object, contract: ProtocolContract | None = None
) -> ProjectSelectionRecord:
    """Normalize proof that a project extension was explicitly selected."""
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "project_selection_record", protocol)
    kind = mapping["kind"]
    if not isinstance(kind, str) or kind not in {"skill", "agent"}:
        raise _error(protocol, "RECORD_INVALID", "project selection kind is invalid")
    selector_key = _as_string(mapping["selector_key"], "selector_key")
    if (
        any(ord(char) < 32 or ord(char) == 127 for char in selector_key)
        or len(selector_key.encode("utf-8")) > protocol.limits["yaml_scalar_bytes"]
    ):
        raise _error(protocol, "RECORD_INVALID", "selector_key is invalid")
    selection_source = protocol.require_enum(
        "project_selection_source", mapping["selection_source"]
    )
    selector_path = _relative_path(mapping["selector_path"], "selector_path", protocol)
    if selection_source == "roster" and (
        kind != "agent"
        or selector_path != ".launchpad/agents.yml"
        or selector_key not in protocol.project_extension_roster_fields
        or not selector_key.endswith("_agents")
    ):
        raise _error(protocol, "RECORD_INVALID", "roster selection is invalid")
    if selection_source == "canonical_reference" and selector_key not in {
        "skills",
        "agents",
    }:
        raise _error(protocol, "RECORD_INVALID", "canonical selection is invalid")
    if selection_source == "canonical_reference" and selector_key != f"{kind}s":
        raise _error(protocol, "RECORD_INVALID", "canonical selector kind differs")
    selector_digest = _digest(mapping["selector_digest"], "selector_digest", protocol)
    selection_digest = _digest(
        mapping["selection_digest"], "selection_digest", protocol
    )
    selection_payload = {
        "resource_id": _record_id(mapping["resource_id"], "resource_id", protocol),
        "kind": kind,
        "selection_source": selection_source,
        "selector_path": selector_path,
        "selector_key": selector_key,
        "selector_digest": selector_digest,
    }
    expected_digest = hashlib.sha256(
        json.dumps(
            selection_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if selection_digest != expected_digest:
        raise _error(protocol, "DIGEST_INVALID", "selection_digest differs")
    return ProjectSelectionRecord(
        resource_id=selection_payload["resource_id"],
        kind=kind,
        selection_source=selection_source,
        selector_path=selector_path,
        selector_key=selector_key,
        selector_digest=selector_digest,
        selection_digest=selection_digest,
    )


def normalize_project_admission_record(
    value: object, contract: ProtocolContract | None = None
) -> ProjectAdmissionRecord:
    """Normalize one exact-digest, one-child, one-run admission envelope."""
    protocol = contract or load_protocol()
    mapping = _record_mapping(value, "project_admission_record", protocol)
    kind = mapping["kind"]
    if not isinstance(kind, str) or kind not in {"skill", "agent"}:
        raise _error(protocol, "RECORD_INVALID", "admission kind is invalid")
    requested_capability = _as_string(
        mapping["requested_capability"], "requested_capability"
    )
    if requested_capability not in protocol.capability_ids:
        raise _error(protocol, "RECORD_INVALID", "admission capability is invalid")
    protocol_version = _as_string(mapping["protocol_version"], "protocol_version")
    if protocol_version != protocol.protocol_version:
        raise _error(protocol, "RECORD_INVALID", "admission protocol differs")
    repository_ref = _as_string(mapping["repository_ref"], "repository_ref")
    if len(repository_ref.encode("utf-8")) > protocol.limits["yaml_scalar_bytes"]:
        raise _error(protocol, "LIMIT_EXCEEDED", "repository_ref is too large")
    if any(ord(char) < 32 or ord(char) == 127 for char in repository_ref):
        raise _error(protocol, "RECORD_INVALID", "repository_ref contains a control")
    return ProjectAdmissionRecord(
        nonce=_digest(mapping["nonce"], "nonce", protocol),
        expires_at=_as_int(mapping["expires_at"], "expires_at"),
        repository_identity=_digest(
            mapping["repository_identity"], "repository_identity", protocol
        ),
        canonical_root_digest=_digest(
            mapping["canonical_root_digest"], "canonical_root_digest", protocol
        ),
        relative_path=_relative_path(
            mapping["relative_path"], "relative_path", protocol
        ),
        kind=kind,
        content_digest=_digest(mapping["content_digest"], "content_digest", protocol),
        selection_digest=_digest(
            mapping["selection_digest"], "selection_digest", protocol
        ),
        protocol_version=protocol_version,
        requested_capability=requested_capability,
        run_id=_record_id(mapping["run_id"], "run_id", protocol),
        child_id=_record_id(mapping["child_id"], "child_id", protocol),
        workflow_id=_record_id(mapping["workflow_id"], "workflow_id", protocol),
        repository_ref=repository_ref,
        source=protocol.require_enum("admission_source", mapping["source"]),
    )


def detect_duplicate_protocol_constants(
    paths: Sequence[Path], contract: ProtocolContract | None = None
) -> tuple[str, ...]:
    """Find downstream assignments that attempt to re-own protocol constants."""
    protocol = contract or load_protocol()
    forbidden_names = {
        *(name.upper() for name in protocol.limits),
        *(name.upper() for name in protocol.defaults),
        *(name.upper() for name in protocol.minimums),
        "CAPABILITY_IDS",
        "COMPONENT_KINDS",
        "PROTOCOL_ERRORS",
        "CANONICAL_DIALECT",
        *(f"{name.upper()}_CLASSES" for name in protocol.classes),
    }
    findings: list[str] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            findings.append(f"{path}: unreadable Python source: {type(exc).__name__}")
            continue
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets.append(node.target)
            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id.upper() in forbidden_names
                ):
                    findings.append(f"{path}:{getattr(node, 'lineno', 0)}:{target.id}")
    return tuple(sorted(findings))


__all__ = [
    "AgentScopeRecord",
    "AvailabilityRecord",
    "BoundedLoop",
    "CapabilitySummary",
    "CompatibilityPredicateRecord",
    "DigestRecord",
    "DirectEdges",
    "NodeRecord",
    "NormalizedMetadata",
    "ProtocolContract",
    "ProtocolValidationError",
    "ProjectAdmissionRecord",
    "ProjectRootRecord",
    "ProjectSelectionRecord",
    "QualificationRecord",
    "ResolverResourceRecord",
    "ResolverSourceRecord",
    "RuntimeRecord",
    "RuntimeFileRecord",
    "SupportRecord",
    "detect_duplicate_protocol_constants",
    "enforce_limit",
    "enforce_minimum",
    "estimate_input_tokens",
    "extract_frontmatter",
    "load_protocol",
    "normalize_digest_record",
    "normalize_agent_scope_record",
    "normalize_availability_record",
    "normalize_compatibility_predicate_record",
    "normalize_document_metadata",
    "normalize_metadata",
    "normalize_node_record",
    "normalize_project_admission_record",
    "normalize_project_root_record",
    "normalize_project_selection_record",
    "normalize_qualification_record",
    "normalize_runtime_record",
    "normalize_runtime_file_record",
    "normalize_resolver_resource_record",
    "normalize_resolver_source_record",
    "normalize_support_record",
    "schema_stage_for_cli",
    "strict_load_yaml",
    "validate_constructed_yaml_size",
]
