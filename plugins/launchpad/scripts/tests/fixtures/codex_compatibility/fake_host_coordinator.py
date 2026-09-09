"""Fixture-only stateful safety coordinator for Codex compatibility tests.

This module freezes the Section 7 typed endpoint and trace contracts without
creating the production ``plugin-codex-runtime.py`` boundary that Phase 0 did
not prove. Every effect is injected through ``FakeHostRecorder``. Nothing in
this module starts a model, writes a product file, spawns a process, or opens a
network connection.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import importlib.util
import ipaddress
import json
import os
import secrets
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn
from urllib.parse import urlsplit

SCRIPTS = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = SCRIPTS / "plugin-codex-protocol.py"
SECRET_SCANNER_PATH = SCRIPTS / "plugin_stack_adapters" / "secret_scanner.py"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load("launchpad_codex_protocol_for_fake_coordinator", PROTOCOL_PATH)
_SECRET_SCANNER = _load(
    "launchpad_secret_scanner_for_fake_coordinator", SECRET_SCANNER_PATH
)

ZERO_DIGEST = "0" * 64
_DIAGNOSTIC_ENVIRONMENT = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
_BLOCKED_EGRESS_TRANSPORTS = frozenset(
    {"browser", "mcp", "connector", "cli", "subprocess"}
)


class CoordinatorError(ValueError):
    """Stable fixture coordinator failure with protocol-owned classification."""

    def __init__(self, code: str, message: str, protocol: Any | None = None) -> None:
        super().__init__(message)
        contract = protocol or _PROTOCOL.load_protocol()
        self.code = code
        self.reporting_class = contract.reporting_class_for_error(code)


class SimulatedEffectFailure(RuntimeError):
    """Injected failure after the fake host records an effect start."""


def _fail(code: str, message: str, protocol: Any) -> NoReturn:
    raise CoordinatorError(code, message, protocol)


def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_digest(value: object) -> str:
    return _sha256(_canonical_json(value))


def _require_digest(value: object, field: str, protocol: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        _fail("DIGEST_INVALID", f"{field} must be a lowercase sha256", protocol)
    return value


def _require_text(value: object, field: str, protocol: Any) -> str:
    maximum = protocol.limits["diagnostic_field_characters"]
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        _fail("RECORD_INVALID", f"{field} is invalid", protocol)
    return value


def _require_identifier(value: object, field: str, protocol: Any) -> str:
    text = _require_text(value, field, protocol)
    if protocol.name_pattern.fullmatch(text) is None:
        _fail("RECORD_INVALID", f"{field} is not a canonical identifier", protocol)
    return text


def _require_nonce(value: object, field: str, protocol: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        _fail("APPROVAL_INVALID", f"{field} is invalid", protocol)
    return value


def _require_optional_text(value: object, field: str, protocol: Any) -> str | None:
    if value is None:
        return None
    return _require_text(value, field, protocol)


def _require_relative_path(value: object, protocol: Any) -> str:
    text = _require_text(value, "source_relative_path", protocol)
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _fail("PATH_ESCAPE", "persisted paths must be source-relative", protocol)
    return text


def _require_sorted_unique(
    values: object,
    field: str,
    protocol: Any,
    *,
    allowed: frozenset[str] | None = None,
) -> tuple[str, ...]:
    if not isinstance(values, tuple) or any(
        not isinstance(item, str) for item in values
    ):
        _fail("RECORD_INVALID", f"{field} must be a tuple of strings", protocol)
    if values != tuple(sorted(set(values))):
        _fail("RECORD_INVALID", f"{field} must be sorted and unique", protocol)
    if allowed is not None and set(values) - allowed:
        _fail("RECORD_INVALID", f"{field} contains an unknown value", protocol)
    for item in values:
        _require_text(item, field, protocol)
    return values


@dataclass(frozen=True)
class ExecutionFrame:
    run_id: str
    command_id: str
    command_digest: str
    argument_digest: str
    graph_digest: str
    configuration_digest: str
    roster_digest: str
    repository_digest: str
    repository_head: str
    repository_index_digest: str
    package_digest: str
    manifest_digest: str
    entry_skill_digest: str
    resolver_digest: str
    coordinator_digest: str
    protocol_version: str
    protocol_digest: str
    support_evidence_version: str
    evidence_digest: str
    approval_digest: str
    project_admission_digests: tuple[str, ...]
    mutation_class: str
    required_capabilities: tuple[str, ...]
    tool_profile: str
    write_scopes: tuple[str, ...]
    active_call_stack: tuple[str, ...]
    depth: int
    cancellation_token_digest: str
    remaining_child_starts: int
    remaining_context_tokens: int
    loaded_resource_digests: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryState:
    repository_digest: str
    head: str
    index_digest: str


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_digest: str
    expires_at: int
    revoked: bool
    authenticated: bool


@dataclass(frozen=True)
class ExecutableIdentity:
    name: str
    absolute_path: str
    device: int
    inode: int
    mode: int
    digest: str


@dataclass(frozen=True)
class DiagnosticResult:
    executable_digest: str
    argv_digest: str
    environment_digest: str
    exit_code: int
    output_digest: str


@dataclass(frozen=True)
class PreflightRecord:
    run_id: str
    required_capabilities: tuple[str, ...]
    tool_profile: str
    graph_digest: str
    repository_digest: str
    evidence_digest: str
    gate_result: str


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    nonce: str
    expires_at: int
    run_id: str
    project_root_digest: str
    command_argument_digest: str
    graph_digest: str
    mutation_class: str
    effect_scope: tuple[str, ...]
    approval_kind: str
    exact_diff_digest: str | None
    source: str
    state: str


@dataclass(frozen=True)
class OperationRequest:
    run_id: str
    effect_kind: str
    executable_digest: str
    subcommand: str
    allowed_flags: tuple[str, ...]
    cwd_digest: str
    path_digests: tuple[str, ...]
    network_origin: str
    network_method: str
    account_digest: str
    resource_digest: str
    credential_class: str
    expected_mutation_digest: str


@dataclass(frozen=True)
class OperationPermit:
    permit_id: str
    nonce: str
    run_id: str
    effect_kind: str
    executable_digest: str
    subcommand: str
    allowed_flags: tuple[str, ...]
    cwd_digest: str
    path_digests: tuple[str, ...]
    network_origin: str
    network_method: str
    account_digest: str
    resource_digest: str
    credential_class: str
    expected_mutation_digest: str
    request_digest: str
    signature: str


@dataclass(frozen=True)
class ReceiptEvent:
    sequence: int
    run_id: str
    receipt_id: str
    event_type: str
    effect_kind: str
    scope_digest: str
    status: str
    error_code: str | None


@dataclass(frozen=True)
class LogEvent:
    sequence: int
    run_id: str
    capability_id: str
    source_relative_path: str
    digest: str
    status: str
    error_code: str | None
    agent_id: str | None
    timing_ms: int
    gate_result: str


@dataclass(frozen=True)
class TerminalRecord:
    run_id: str
    terminal_state: str
    mutation_state: str
    receipt_id: str | None
    error_code: str | None
    frame_digest: str


@dataclass(frozen=True)
class TraceEvent:
    sequence: int
    run_id: str
    category: str
    operation: str
    record_digest: str


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str
    frame_digest: str
    run_state: str
    mutation_state: str
    approval_state: str | None
    approval_digest: str
    receipt_id: str | None
    receipt_synced: bool
    lease_held: bool
    terminal_state: str | None
    remaining_child_starts: int
    remaining_context_tokens: int
    outbound_bytes: int


@dataclass(frozen=True)
class EgressRecord:
    run_id: str
    effect_kind: str
    transport: str
    destination_digest: str
    payload_digest: str
    payload_bytes: int
    aggregate_outbound_bytes: int


_SCHEMA_TYPES = {
    "execution_frame": ExecutionFrame,
    "run_snapshot": RunSnapshot,
    "preflight_record": PreflightRecord,
    "approval_record": ApprovalRecord,
    "operation_permit": OperationPermit,
    "receipt_event": ReceiptEvent,
    "log_event": LogEvent,
    "terminal_record": TerminalRecord,
    "trace_event": TraceEvent,
}


def assert_protocol_schema_alignment(protocol: Any | None = None) -> None:
    """Fail if fixture endpoint dataclasses drift from the shared protocol."""
    contract = protocol or _PROTOCOL.load_protocol()
    for schema_name, record_type in _SCHEMA_TYPES.items():
        expected = contract.record_schemas[schema_name]
        actual = tuple(field.name for field in dataclasses.fields(record_type))
        if actual != expected:
            _fail(
                "INTEGRITY_MISMATCH",
                f"{schema_name} fixture fields differ from the protocol",
                contract,
            )


def command_argument_digest(command_digest: str, argument_digest: str) -> str:
    return _record_digest((command_digest, argument_digest))


def approval_scope_digest(
    *,
    run_id: str,
    project_root_digest: str,
    command_argument_digest_value: str,
    graph_digest: str,
    mutation_class: str,
    effect_scope: tuple[str, ...],
    approval_kind: str,
    exact_diff_digest: str | None,
) -> str:
    return _record_digest(
        {
            "run_id": run_id,
            "project_root_digest": project_root_digest,
            "command_argument_digest": command_argument_digest_value,
            "graph_digest": graph_digest,
            "mutation_class": mutation_class,
            "effect_scope": effect_scope,
            "approval_kind": approval_kind,
            "exact_diff_digest": exact_diff_digest,
        }
    )


class FakeHostRecorder:
    """Injected authority and effect recorder with no real host side effects."""

    def __init__(
        self,
        *,
        capabilities: tuple[str, ...],
        enforceable_profiles: tuple[str, ...],
        mediated_transports: tuple[str, ...],
        project_root: Path,
        repository_state: RepositoryState,
        evidence: EvidenceRecord,
        diagnostic_identities: Mapping[str, ExecutableIdentity] | None = None,
        diagnostic_allowlist: Mapping[str, tuple[tuple[str, ...], ...]] | None = None,
        diagnostic_outputs: Mapping[tuple[str, tuple[str, ...]], tuple[int, bytes]]
        | None = None,
        network_resolutions: Mapping[str, tuple[str, ...]] | None = None,
        storage_capacity: int | None = None,
        permit_secret: bytes = b"fixture-operation-permit-secret-32",
        protocol: Any | None = None,
    ) -> None:
        self.protocol = protocol or _PROTOCOL.load_protocol()
        assert_protocol_schema_alignment(self.protocol)
        self.capabilities = _require_sorted_unique(
            capabilities,
            "capabilities",
            self.protocol,
            allowed=self.protocol.capability_ids,
        )
        tool_profiles = self.protocol.classes["tool_profile"]
        self.enforceable_profiles = _require_sorted_unique(
            enforceable_profiles,
            "enforceable_profiles",
            self.protocol,
            allowed=tool_profiles,
        )
        transports = self.protocol.classes["egress_transport"]
        self.mediated_transports = _require_sorted_unique(
            mediated_transports,
            "mediated_transports",
            self.protocol,
            allowed=transports,
        )
        self.project_root = project_root.resolve()
        self.project_root_digest = _sha256(os.fspath(self.project_root).encode("utf-8"))
        self.repository_state = repository_state
        self.evidence = evidence
        self.storage_capacity = (
            self.protocol.limits["adapter_storage_bytes"]
            if storage_capacity is None
            else storage_capacity
        )
        if len(permit_secret) < 32:
            _fail(
                "OPERATION_PERMIT_INVALID", "permit secret is too short", self.protocol
            )
        self._permit_secret = permit_secret
        self.diagnostic_identities = dict(diagnostic_identities or {})
        self.diagnostic_allowlist = dict(diagnostic_allowlist or {})
        self.diagnostic_outputs = dict(diagnostic_outputs or {})
        self.diagnostic_shell_values: list[bool] = []
        self.network_resolutions = dict(network_resolutions or {})
        self.trace: list[TraceEvent] = []
        self.effects: list[tuple[str, str, str]] = []
        self.logs: dict[str, list[LogEvent]] = {}
        self.receipts: dict[str, list[ReceiptEvent]] = {}
        self.receipt_synced: set[str] = set()
        self.receipt_reservations: dict[str, tuple[int, int]] = {}
        self.leases: dict[str, str] = {}
        self.terminals: dict[str, TerminalRecord] = {}
        self.active_mutation_runs: set[str] = set()
        self.fail_effects: set[str] = set()
        self._approval_events: dict[str, tuple[str, str, str]] = {}
        self._approval_events_used: set[str] = set()
        self._project_admissions: set[str] = set()
        self.control_snapshot: dict[str, object] | None = None

    def _trace(
        self, run_id: str, category: str, operation: str, record: object
    ) -> TraceEvent:
        event = TraceEvent(
            sequence=len(self.trace) + 1,
            run_id=run_id,
            category=category,
            operation=operation,
            record_digest=_record_digest(record),
        )
        self.trace.append(event)
        return event

    def register_approval_event(
        self,
        event_id: str,
        request_digest: str,
        *,
        decision: str = "approved",
        source: str = "interactive",
    ) -> None:
        _require_text(event_id, "event_id", self.protocol)
        _require_digest(request_digest, "request_digest", self.protocol)
        if decision not in {"approved", "declined"}:
            _fail("APPROVAL_INVALID", "approval decision is invalid", self.protocol)
        if source not in self.protocol.classes["admission_source"]:
            _fail("APPROVAL_INVALID", "approval source is invalid", self.protocol)
        self._approval_events[event_id] = (request_digest, decision, source)

    def authenticate_approval(
        self, run_id: str, event_id: str, request_digest: str
    ) -> tuple[str, str]:
        if event_id in self._approval_events_used:
            _fail(
                "APPROVAL_REPLAYED",
                "approval event was already consumed",
                self.protocol,
            )
        event = self._approval_events.get(event_id)
        if event is None or not hmac.compare_digest(event[0], request_digest):
            _fail(
                "APPROVAL_INVALID",
                "approval event did not bind this request",
                self.protocol,
            )
        self._approval_events_used.add(event_id)
        self._trace(run_id, "gate", "approval.authenticate", request_digest)
        return event[1], event[2]

    def register_project_admission(self, record: object) -> None:
        self._project_admissions.add(_record_digest(record))

    def authenticate_project_admission(self, run_id: str, record: object) -> bool:
        authenticated = _record_digest(record) in self._project_admissions
        self._trace(run_id, "gate", "project_admission.authenticate", record)
        return authenticated

    def verify_evidence(self, run_id: str, evidence: EvidenceRecord) -> bool:
        self._trace(run_id, "gate", "evidence.authenticate", evidence)
        return evidence == self.evidence and evidence.authenticated

    def attest_executable(self, run_id: str, name: str) -> ExecutableIdentity:
        identity = self.diagnostic_identities.get(name)
        if identity is None:
            _fail(
                "EXECUTABLE_IDENTITY_INVALID",
                "diagnostic executable identity is unavailable",
                self.protocol,
            )
        self._trace(run_id, "gate", "diagnostic.attest_executable", identity)
        return identity

    def run_diagnostic(
        self,
        run_id: str,
        identity: ExecutableIdentity,
        arguments: tuple[str, ...],
        environment: Mapping[str, str],
        *,
        shell: bool,
    ) -> DiagnosticResult:
        self.diagnostic_shell_values.append(shell)
        if shell:
            _fail(
                "DIAGNOSTIC_NOT_ALLOWLISTED",
                "diagnostic shell execution is forbidden",
                self.protocol,
            )
        allowed = self.diagnostic_allowlist.get(identity.name, ())
        if arguments not in allowed:
            _fail(
                "DIAGNOSTIC_NOT_ALLOWLISTED",
                "diagnostic argv is not allowlisted",
                self.protocol,
            )
        exit_code, output = self.diagnostic_outputs.get(
            (identity.name, arguments), (0, b"")
        )
        result = DiagnosticResult(
            executable_digest=identity.digest,
            argv_digest=_record_digest((identity.absolute_path, *arguments)),
            environment_digest=_record_digest(environment),
            exit_code=exit_code,
            output_digest=_sha256(output),
        )
        self._trace(run_id, "diagnostic", "diagnostic.simulate", result)
        return result

    def reserve_receipt(
        self, run_id: str, receipt_id: str, byte_capacity: int, event_capacity: int
    ) -> None:
        if receipt_id in self.receipt_reservations:
            _fail("RUN_STATE_INVALID", "receipt was already reserved", self.protocol)
        total_reserved = sum(value[0] for value in self.receipt_reservations.values())
        if (
            byte_capacity > self.storage_capacity
            or total_reserved + byte_capacity > self.storage_capacity
        ):
            _fail(
                "RECEIPT_RESERVATION_UNAVAILABLE",
                "fake host cannot reserve the complete receipt journal",
                self.protocol,
            )
        self.receipt_reservations[receipt_id] = (byte_capacity, event_capacity)
        self.receipts[receipt_id] = []
        self._trace(
            run_id,
            "adapter_internal_write",
            "receipt.reserve",
            {
                "receipt_id": receipt_id,
                "bytes": byte_capacity,
                "events": event_capacity,
            },
        )

    def append_receipt(self, event: ReceiptEvent) -> None:
        reservation = self.receipt_reservations.get(event.receipt_id)
        if reservation is None:
            _fail("RECEIPT_NOT_READY", "receipt journal is not reserved", self.protocol)
        records = self.receipts[event.receipt_id]
        encoded_size = sum(len(_canonical_json(item)) for item in records)
        next_size = encoded_size + len(_canonical_json(event))
        if len(records) + 1 > reservation[1] or next_size > reservation[0]:
            _fail(
                "RECEIPT_CAPACITY_EXCEEDED",
                "receipt journal exceeded its complete reservation",
                self.protocol,
            )
        records.append(event)
        self.receipt_synced.discard(event.receipt_id)
        self._trace(event.run_id, "adapter_internal_write", "receipt.append", event)

    def sync_receipt(self, run_id: str, receipt_id: str) -> None:
        if receipt_id not in self.receipts:
            _fail("RECEIPT_NOT_READY", "receipt journal is unavailable", self.protocol)
        self.receipt_synced.add(receipt_id)
        self._trace(
            run_id,
            "adapter_internal_write",
            "receipt.sync",
            {"receipt_id": receipt_id},
        )

    def acquire_lease(self, run_id: str, repository_digest: str) -> None:
        owner = self.leases.get(repository_digest)
        if owner is not None and owner != run_id:
            _fail(
                "MUTATION_LEASE_UNAVAILABLE",
                "another host owns the checkout mutation lease",
                self.protocol,
            )
        self.leases[repository_digest] = run_id
        self.active_mutation_runs.add(run_id)
        self._trace(run_id, "gate", "mutation_lease.acquire", repository_digest)

    def release_lease(self, run_id: str, repository_digest: str) -> None:
        if self.leases.get(repository_digest) == run_id:
            del self.leases[repository_digest]
        self.active_mutation_runs.discard(run_id)
        self._trace(run_id, "gate", "mutation_lease.release", repository_digest)

    def authorize_operation(self, run_id: str, request_digest: str) -> None:
        self._trace(run_id, "gate", "operation.authorize", request_digest)

    def revalidate_network_origin(self, run_id: str, origin: str) -> None:
        addresses = self.network_resolutions.get(origin)
        if not addresses:
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "network origin was not re-resolved",
                self.protocol,
            )
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                _fail(
                    "OPERATION_SCOPE_MISMATCH",
                    "resolved address is invalid",
                    self.protocol,
                )
            if not address.is_global:
                _fail(
                    "OPERATION_SCOPE_MISMATCH",
                    "resolved address is not global",
                    self.protocol,
                )
        self._trace(
            run_id,
            "gate",
            "network_origin.revalidate",
            {"origin_digest": _record_digest(origin), "address_count": len(addresses)},
        )

    def sign_permit(self, request_digest: str, nonce: str) -> str:
        return hmac.new(
            self._permit_secret,
            f"{request_digest}:{nonce}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    def verify_permit_signature(self, permit: OperationPermit) -> bool:
        expected = self.sign_permit(permit.request_digest, permit.nonce)
        return hmac.compare_digest(expected, permit.signature)

    def record_effect(self, run_id: str, effect_kind: str, scope_digest: str) -> None:
        self.effects.append((run_id, effect_kind, scope_digest))
        self._trace(
            run_id,
            "effect",
            f"{effect_kind}.begin",
            {"scope_digest": scope_digest},
        )
        if effect_kind in self.fail_effects:
            raise SimulatedEffectFailure(effect_kind)
        self._trace(
            run_id,
            "effect",
            f"{effect_kind}.commit",
            {"scope_digest": scope_digest},
        )

    def persist_log(self, event: LogEvent) -> None:
        events = self.logs.setdefault(event.run_id, [])
        events.append(event)
        self._trace(event.run_id, "adapter_internal_write", "log.append", event)

    def persist_terminal(self, record: TerminalRecord) -> None:
        self.terminals[record.run_id] = record
        self._trace(record.run_id, "adapter_internal_write", "terminal.persist", record)
        self.rotate_storage(record.run_id)

    def rotate_storage(self, current_run_id: str) -> None:
        maximum = self.protocol.limits["retained_runs"]
        if len(self.terminals) <= maximum:
            return
        removable = sorted(
            run_id
            for run_id in self.terminals
            if run_id != current_run_id and run_id not in self.active_mutation_runs
        )
        while len(self.terminals) > maximum and removable:
            run_id = removable.pop(0)
            self.terminals.pop(run_id, None)
            self.logs.pop(run_id, None)
            for receipt_id in tuple(self.receipts):
                if receipt_id.startswith(f"receipt-{run_id}-"):
                    self.receipts.pop(receipt_id, None)
                    self.receipt_reservations.pop(receipt_id, None)
                    self.receipt_synced.discard(receipt_id)
            self._trace(
                current_run_id, "adapter_internal_write", "storage.rotate", run_id
            )


class StatefulSafetyCoordinator:
    """Deterministic state owner whose effects exist only on an injected host."""

    def __init__(
        self,
        frame: ExecutionFrame,
        host: FakeHostRecorder,
        *,
        now: int,
        protocol: Any | None = None,
    ) -> None:
        self.protocol = protocol or host.protocol
        assert_protocol_schema_alignment(self.protocol)
        self.host = host
        self.frame = self._validate_frame(frame)
        self.frame_digest = _record_digest(frame)
        self.created_at = now
        self.run_state = "created"
        self.mutation_state = "not_started"
        self.terminal_state: str | None = None
        self.approval: ApprovalRecord | None = None
        self.preflight_record: PreflightRecord | None = None
        self.receipt_id: str | None = None
        self.receipt_synced = False
        self.lease_held = False
        self.outbound_bytes = 0
        self._receipt_sequence = 0
        self._log_sequence = 0
        self._used_permits: set[str] = set()
        self._admitted_project_prompts: set[str] = set()
        self._prepared_effects: list[tuple[str, str, str]] = []
        self._mediated_egress: set[str] = set()
        self._last_effect_kind: str | None = None
        snapshot = self._control_snapshot()
        if self.host.control_snapshot is None:
            self.host.control_snapshot = snapshot
        elif self.host.control_snapshot != snapshot:
            _fail("SNAPSHOT_MISMATCH", "host control snapshot differs", self.protocol)

    def _validate_frame(self, frame: ExecutionFrame) -> ExecutionFrame:
        if not isinstance(frame, ExecutionFrame):
            _fail("RECORD_INVALID", "execution frame is untyped", self.protocol)
        for field in (
            "command_digest",
            "argument_digest",
            "graph_digest",
            "configuration_digest",
            "roster_digest",
            "repository_digest",
            "repository_index_digest",
            "package_digest",
            "manifest_digest",
            "entry_skill_digest",
            "resolver_digest",
            "coordinator_digest",
            "protocol_digest",
            "evidence_digest",
            "approval_digest",
            "cancellation_token_digest",
        ):
            _require_digest(getattr(frame, field), field, self.protocol)
        _require_identifier(frame.run_id, "run_id", self.protocol)
        _require_identifier(frame.command_id, "command_id", self.protocol)
        _require_text(frame.repository_head, "repository_head", self.protocol)
        _require_text(
            frame.support_evidence_version,
            "support_evidence_version",
            self.protocol,
        )
        if frame.protocol_version != self.protocol.protocol_version:
            _fail(
                "PROTOCOL_VERSION_UNSUPPORTED",
                "frame protocol version differs",
                self.protocol,
            )
        if frame.protocol_digest != self.protocol.digest:
            _fail("INTEGRITY_MISMATCH", "frame protocol digest differs", self.protocol)
        self.protocol.require_enum("mutation", frame.mutation_class)
        _require_sorted_unique(
            frame.required_capabilities,
            "required_capabilities",
            self.protocol,
            allowed=self.protocol.capability_ids,
        )
        self.protocol.require_enum("tool_profile", frame.tool_profile)
        _require_sorted_unique(frame.write_scopes, "write_scopes", self.protocol)
        _require_sorted_unique(
            frame.project_admission_digests,
            "project_admission_digests",
            self.protocol,
        )
        _require_sorted_unique(
            frame.loaded_resource_digests,
            "loaded_resource_digests",
            self.protocol,
        )
        for digest in frame.project_admission_digests + frame.loaded_resource_digests:
            _require_digest(digest, "pinned digest", self.protocol)
        if (
            not isinstance(frame.active_call_stack, tuple)
            or any(not isinstance(item, str) for item in frame.active_call_stack)
            or len(set(frame.active_call_stack)) != len(frame.active_call_stack)
        ):
            _fail("RECORD_INVALID", "active call stack contains a cycle", self.protocol)
        if (
            frame.depth != len(frame.active_call_stack) - 1
            or not 0 <= frame.depth <= self.protocol.limits["nested_depth"]
        ):
            _fail("LIMIT_EXCEEDED", "nested call depth is invalid", self.protocol)
        if frame.active_call_stack[-1:] != (frame.command_id,):
            _fail(
                "RECORD_INVALID",
                "active call stack does not end at the command",
                self.protocol,
            )
        if (
            not 0
            <= frame.remaining_child_starts
            <= self.protocol.limits["child_starts"]
        ):
            _fail("LIMIT_EXCEEDED", "remaining child starts are invalid", self.protocol)
        context_ceiling = self.protocol.defaults["fallback_context_tokens"]
        if not 0 <= frame.remaining_context_tokens <= context_ceiling:
            _fail(
                "LIMIT_EXCEEDED", "remaining context budget is invalid", self.protocol
            )
        if frame.mutation_class == "none" and frame.write_scopes:
            _fail(
                "RECORD_INVALID",
                "zero-mutation frame declares write scopes",
                self.protocol,
            )
        return frame

    def _control_snapshot(self) -> dict[str, object]:
        return {
            "command_digest": self.frame.command_digest,
            "argument_digest": self.frame.argument_digest,
            "graph_digest": self.frame.graph_digest,
            "configuration_digest": self.frame.configuration_digest,
            "roster_digest": self.frame.roster_digest,
            "package_digest": self.frame.package_digest,
            "manifest_digest": self.frame.manifest_digest,
            "entry_skill_digest": self.frame.entry_skill_digest,
            "resolver_digest": self.frame.resolver_digest,
            "coordinator_digest": self.frame.coordinator_digest,
            "protocol_digest": self.frame.protocol_digest,
            "evidence_digest": self.frame.evidence_digest,
            "approval_digest": self.frame.approval_digest,
            "required_capabilities": self.frame.required_capabilities,
            "tool_profile": self.frame.tool_profile,
            "project_admission_digests": self.frame.project_admission_digests,
            "loaded_resource_digests": self.frame.loaded_resource_digests,
        }

    def snapshot(self) -> RunSnapshot:
        return RunSnapshot(
            run_id=self.frame.run_id,
            frame_digest=self.frame_digest,
            run_state=self.run_state,
            mutation_state=self.mutation_state,
            approval_state=self.approval.state if self.approval else None,
            approval_digest=(
                _record_digest(self.approval)
                if self.approval is not None
                else self.frame.approval_digest
            ),
            receipt_id=self.receipt_id,
            receipt_synced=self.receipt_synced,
            lease_held=self.lease_held,
            terminal_state=self.terminal_state,
            remaining_child_starts=self.frame.remaining_child_starts,
            remaining_context_tokens=self.frame.remaining_context_tokens,
            outbound_bytes=self.outbound_bytes,
        )

    def diagnostic_help(self, now: int) -> Mapping[str, object]:
        status = "current"
        if self.host.evidence.revoked:
            status = "revoked"
        elif now >= self.host.evidence.expires_at:
            status = "expired"
        self.protocol.require_enum("evidence_status", status)
        return {
            "status": status,
            "recovery": "Disable or update the installed LaunchPad package.",
            "effects_allowed": status == "current",
        }

    def _require_state(self, *states: str) -> None:
        if self.run_state not in states:
            _fail(
                "RUN_STATE_INVALID",
                "endpoint is unavailable in this run state",
                self.protocol,
            )

    def _verify_control_snapshot(self) -> None:
        if self.frame.protocol_digest != self.protocol.digest:
            _fail(
                "SNAPSHOT_MISMATCH",
                "protocol changed after frame creation",
                self.protocol,
            )
        if self.host.control_snapshot != self._control_snapshot():
            _fail("SNAPSHOT_MISMATCH", "pinned control state drifted", self.protocol)
        current = self.host.repository_state
        if (
            current.repository_digest != self.frame.repository_digest
            or current.head != self.frame.repository_head
            or current.index_digest != self.frame.repository_index_digest
        ):
            _fail(
                "REPOSITORY_DRIFT",
                "repository state differs from the pinned frame",
                self.protocol,
            )

    def _verify_effect_evidence(self, now: int) -> None:
        evidence = self.host.evidence
        if not self.host.verify_evidence(self.frame.run_id, evidence):
            _fail(
                "REVOCATION_STATUS_UNAVAILABLE",
                "evidence status is unauthenticated",
                self.protocol,
            )
        if evidence.evidence_digest != self.frame.evidence_digest:
            _fail(
                "INTEGRITY_MISMATCH",
                "evidence digest differs from the frame",
                self.protocol,
            )
        if evidence.revoked:
            _fail("EVIDENCE_REVOKED", "evidence was revoked", self.protocol)
        if now >= evidence.expires_at:
            _fail(
                "EVIDENCE_EXPIRED", "evidence expired before the effect", self.protocol
            )

    def preflight(
        self,
        required_capabilities: tuple[str, ...],
        tool_profile: str,
        *,
        now: int,
    ) -> PreflightRecord:
        self._require_state("created")
        required = _require_sorted_unique(
            required_capabilities,
            "required_capabilities",
            self.protocol,
            allowed=self.protocol.capability_ids,
        )
        self.protocol.require_enum("tool_profile", tool_profile)
        try:
            if (
                required != self.frame.required_capabilities
                or tool_profile != self.frame.tool_profile
            ):
                _fail(
                    "PREFLIGHT_FAILED",
                    "preflight expanded or narrowed the pinned capability profile",
                    self.protocol,
                )
            self._verify_control_snapshot()
            self._verify_effect_evidence(now)
            missing = set(required) - set(self.host.capabilities)
            if missing:
                _fail(
                    "CAPABILITY_BLOCKED",
                    "required host capability is absent",
                    self.protocol,
                )
            if tool_profile not in self.host.enforceable_profiles:
                _fail(
                    "TOOL_PROFILE_UNENFORCEABLE",
                    "host cannot enforce the tool profile",
                    self.protocol,
                )
            if tool_profile == "read_only":
                boundary = {
                    "prompt_free_shell_deny",
                    "repository_read",
                    "serialized_payload_mediation",
                }
                if not boundary.issubset(self.host.capabilities):
                    _fail(
                        "TOOL_PROFILE_UNENFORCEABLE",
                        "read-only boundary is incomplete",
                        self.protocol,
                    )
            if self.frame.mutation_class != "none":
                mutation_boundary = {
                    "atomic_receipt_reservation",
                    "authenticated_user_interaction",
                    "effect_revocation_status",
                    "operation_authorization",
                    "plugin_durable_state",
                    "repository_write",
                }
                if not mutation_boundary.issubset(
                    required
                ) or not mutation_boundary.issubset(self.host.capabilities):
                    _fail(
                        "PREFLIGHT_FAILED",
                        "mutating boundary is incomplete",
                        self.protocol,
                    )
                if tool_profile not in {"workspace_write", "effectful"}:
                    _fail(
                        "TOOL_PROFILE_UNENFORCEABLE",
                        "mutating profile is not enforced",
                        self.protocol,
                    )
        except CoordinatorError as exc:
            blocked = PreflightRecord(
                run_id=self.frame.run_id,
                required_capabilities=required,
                tool_profile=tool_profile,
                graph_digest=self.frame.graph_digest,
                repository_digest=self.frame.repository_digest,
                evidence_digest=self.frame.evidence_digest,
                gate_result="blocked",
            )
            self.host._trace(self.frame.run_id, "gate", "preflight.blocked", blocked)
            raise exc
        record = PreflightRecord(
            run_id=self.frame.run_id,
            required_capabilities=required,
            tool_profile=tool_profile,
            graph_digest=self.frame.graph_digest,
            repository_digest=self.frame.repository_digest,
            evidence_digest=self.frame.evidence_digest,
            gate_result="pass",
        )
        self.preflight_record = record
        self.run_state = "preflight_passed"
        self.host._trace(self.frame.run_id, "gate", "preflight.pass", record)
        return record

    def run_diagnostic(self, name: str, arguments: tuple[str, ...]) -> DiagnosticResult:
        self._require_state("preflight_passed")
        _require_text(name, "diagnostic name", self.protocol)
        if not isinstance(arguments, tuple) or any(
            not isinstance(item, str) for item in arguments
        ):
            _fail(
                "RECORD_INVALID",
                "diagnostic arguments must be a typed tuple",
                self.protocol,
            )
        identity = self.host.attest_executable(self.frame.run_id, name)
        _require_digest(identity.digest, "executable digest", self.protocol)
        executable = Path(identity.absolute_path)
        if not executable.is_absolute() or executable.is_relative_to(
            self.host.project_root
        ):
            _fail(
                "EXECUTABLE_IDENTITY_INVALID",
                "executable is project-controlled",
                self.protocol,
            )
        if (
            not stat.S_ISREG(identity.mode)
            or identity.device < 0
            or identity.inode <= 0
        ):
            _fail(
                "EXECUTABLE_IDENTITY_INVALID",
                "executable identity is not a regular file",
                self.protocol,
            )
        current = self.host.attest_executable(self.frame.run_id, name)
        if current != identity:
            _fail(
                "EXECUTABLE_IDENTITY_INVALID",
                "executable identity changed before spawn",
                self.protocol,
            )
        environment = dict(_DIAGNOSTIC_ENVIRONMENT)
        if set(environment) != {"LANG", "LC_ALL"}:
            _fail(
                "INTEGRITY_MISMATCH", "diagnostic environment expanded", self.protocol
            )
        return self.host.run_diagnostic(
            self.frame.run_id,
            identity,
            arguments,
            environment,
            shell=False,
        )

    def admit_project_prompt(
        self,
        record: object,
        *,
        child_id: str,
        requested_capability: str,
        now: int,
    ) -> str:
        self._require_state("preflight_passed")
        if not self.host.authenticate_project_admission(self.frame.run_id, record):
            _fail(
                "PROJECT_PROMPT_ADMISSION_UNAVAILABLE",
                "project prompt is not authenticated",
                self.protocol,
            )
        expected = {
            "run_id": self.frame.run_id,
            "workflow_id": self.frame.command_id,
            "child_id": child_id,
            "requested_capability": requested_capability,
            "protocol_version": self.protocol.protocol_version,
        }
        if any(
            getattr(record, field, None) != value for field, value in expected.items()
        ):
            _fail(
                "APPROVAL_SCOPE_MISMATCH",
                "project admission scope differs",
                self.protocol,
            )
        expires_at = getattr(record, "expires_at", None)
        if not isinstance(expires_at, int) or now >= expires_at:
            _fail("APPROVAL_EXPIRED", "project admission expired", self.protocol)
        digest = _record_digest(record)
        if digest not in self.frame.project_admission_digests:
            _fail(
                "SNAPSHOT_MISMATCH",
                "project admission was not pinned in the frame",
                self.protocol,
            )
        if digest in self._admitted_project_prompts:
            _fail(
                "APPROVAL_REPLAYED",
                "project admission was already consumed",
                self.protocol,
            )
        self._admitted_project_prompts.add(digest)
        return digest

    def begin_approval(
        self,
        *,
        effect_scope: tuple[str, ...],
        approval_kind: str,
        exact_diff_digest: str | None,
        expires_at: int,
        now: int,
        nonce: str | None = None,
    ) -> ApprovalRecord:
        self._require_state("preflight_passed")
        scope = _require_sorted_unique(effect_scope, "effect_scope", self.protocol)
        if not scope:
            _fail("APPROVAL_INVALID", "approval scope cannot be empty", self.protocol)
        self.protocol.require_enum("approval_kind", approval_kind)
        if (
            expires_at <= now
            or expires_at - now > self.protocol.limits["project_approval_ttl_seconds"]
        ):
            _fail(
                "APPROVAL_INVALID",
                "approval expiry is outside its bound",
                self.protocol,
            )
        if exact_diff_digest is not None:
            _require_digest(exact_diff_digest, "exact_diff_digest", self.protocol)
        if approval_kind == "persistent_instruction_write":
            if (
                "persistent_instruction_write" not in self.host.capabilities
                or exact_diff_digest is None
                or self.frame.depth != 0
            ):
                _fail(
                    "APPROVAL_SCOPE_MISMATCH",
                    "persistent instruction approval is not eligible",
                    self.protocol,
                )
        elif exact_diff_digest is not None:
            _fail(
                "APPROVAL_SCOPE_MISMATCH",
                "generic approval cannot bind an instruction diff",
                self.protocol,
            )
        cmd_args = command_argument_digest(
            self.frame.command_digest, self.frame.argument_digest
        )
        expected_scope = approval_scope_digest(
            run_id=self.frame.run_id,
            project_root_digest=self.host.project_root_digest,
            command_argument_digest_value=cmd_args,
            graph_digest=self.frame.graph_digest,
            mutation_class=self.frame.mutation_class,
            effect_scope=scope,
            approval_kind=approval_kind,
            exact_diff_digest=exact_diff_digest,
        )
        if not hmac.compare_digest(expected_scope, self.frame.approval_digest):
            _fail(
                "APPROVAL_SCOPE_MISMATCH",
                "approval expanded beyond the frame",
                self.protocol,
            )
        value = nonce or secrets.token_hex(32)
        _require_nonce(value, "approval nonce", self.protocol)
        record = ApprovalRecord(
            approval_id=f"approval-{_record_digest((self.frame.run_id, value))[:24]}",
            nonce=value,
            expires_at=expires_at,
            run_id=self.frame.run_id,
            project_root_digest=self.host.project_root_digest,
            command_argument_digest=cmd_args,
            graph_digest=self.frame.graph_digest,
            mutation_class=self.frame.mutation_class,
            effect_scope=scope,
            approval_kind=approval_kind,
            exact_diff_digest=exact_diff_digest,
            source="interactive",
            state="pending",
        )
        self.approval = record
        return record

    def resolve_approval(
        self, request: ApprovalRecord, event_id: str, *, now: int
    ) -> ApprovalRecord:
        self._require_state("preflight_passed")
        if self.approval != request or request.state != "pending":
            _fail(
                "APPROVAL_INVALID", "approval request is stale or forged", self.protocol
            )
        if now >= request.expires_at:
            self.approval = replace(request, state="expired")
            _fail("APPROVAL_EXPIRED", "approval expired", self.protocol)
        request_digest = _record_digest(request)
        decision, source = self.host.authenticate_approval(
            self.frame.run_id, event_id, request_digest
        )
        if (
            request.approval_kind == "persistent_instruction_write"
            and source != "interactive"
        ):
            _fail(
                "APPROVAL_SCOPE_MISMATCH",
                "persistent instruction approval is interactive-only",
                self.protocol,
            )
        state = "approved" if decision == "approved" else "declined"
        approved = replace(request, source=source, state=state)
        self.approval = approved
        if state == "declined":
            return approved
        self.run_state = "approved"
        return approved

    def _require_live_approval(self, scope: str, now: int) -> None:
        if self.approval is None or self.approval.state != "approved":
            _fail(
                "APPROVAL_REQUIRED",
                "an authenticated approval is required",
                self.protocol,
            )
        if now >= self.approval.expires_at:
            self.approval = replace(self.approval, state="expired")
            _fail(
                "APPROVAL_EXPIRED", "approval expired before the effect", self.protocol
            )
        if scope not in self.approval.effect_scope:
            _fail(
                "APPROVAL_SCOPE_MISMATCH",
                "effect is outside the approved scope",
                self.protocol,
            )
        if (
            scope.startswith("instruction-write:")
            and self.approval.approval_kind != "persistent_instruction_write"
        ):
            _fail(
                "APPROVAL_SCOPE_MISMATCH",
                "instruction write lacks its separate approval",
                self.protocol,
            )

    def prepare_receipt(
        self, *, effect_kind: str, scope_digest: str, scope: str, now: int
    ) -> str:
        self._require_state("approved", "receipt_ready")
        self.protocol.require_enum("effect_kind", effect_kind)
        _require_digest(scope_digest, "scope_digest", self.protocol)
        self._require_live_approval(scope, now)
        self._verify_control_snapshot()
        self._verify_effect_evidence(now)
        if self.receipt_id is None:
            receipt_id = f"receipt-{self.frame.run_id}-{self.frame_digest[:16]}"
            self.host.reserve_receipt(
                self.frame.run_id,
                receipt_id,
                self.protocol.limits["mutation_receipt_bytes_per_run"],
                self.protocol.limits["mutation_receipt_events_per_run"],
            )
            self.receipt_id = receipt_id
        self._receipt_sequence += 1
        event = ReceiptEvent(
            sequence=self._receipt_sequence,
            run_id=self.frame.run_id,
            receipt_id=self.receipt_id,
            event_type="intent",
            effect_kind=effect_kind,
            scope_digest=scope_digest,
            status="planned",
            error_code=None,
        )
        self.host.append_receipt(event)
        self.host.sync_receipt(self.frame.run_id, self.receipt_id)
        self.receipt_synced = True
        self._prepared_effects.append((effect_kind, scope, scope_digest))
        self._last_effect_kind = effect_kind
        self.run_state = "receipt_ready"
        return self.receipt_id

    def acquire_mutation_lease(self) -> None:
        self._require_state("receipt_ready")
        if self.frame.mutation_class == "none":
            _fail(
                "RUN_STATE_INVALID",
                "zero-mutation run cannot acquire a lease",
                self.protocol,
            )
        if not self.receipt_synced:
            _fail(
                "RECEIPT_NOT_READY",
                "receipt must be synced before the lease",
                self.protocol,
            )
        self.host.acquire_lease(self.frame.run_id, self.frame.repository_digest)
        self.lease_held = True

    def issue_operation_permit(
        self, request: OperationRequest, *, scope: str, now: int
    ) -> OperationPermit:
        self._require_state("receipt_ready")
        self._require_live_approval(scope, now)
        if (
            request.run_id != self.frame.run_id
            or request.effect_kind != "external_effect"
        ):
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "operation request scope differs",
                self.protocol,
            )
        for field in (
            "executable_digest",
            "cwd_digest",
            "account_digest",
            "resource_digest",
            "expected_mutation_digest",
        ):
            _require_digest(getattr(request, field), field, self.protocol)
        _require_sorted_unique(request.allowed_flags, "allowed_flags", self.protocol)
        _require_sorted_unique(request.path_digests, "path_digests", self.protocol)
        for digest in request.path_digests:
            _require_digest(digest, "path_digest", self.protocol)
        _require_text(request.subcommand, "subcommand", self.protocol)
        _require_text(request.credential_class, "credential_class", self.protocol)
        method = _require_text(request.network_method, "network_method", self.protocol)
        if method != method.upper():
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "network method is not normalized",
                self.protocol,
            )
        self._validate_network_origin(request.network_origin)
        request_digest = _record_digest(request)
        self.host.authorize_operation(self.frame.run_id, request_digest)
        nonce = secrets.token_hex(32)
        signature = self.host.sign_permit(request_digest, nonce)
        return OperationPermit(
            permit_id=f"permit-{_record_digest((request_digest, nonce))[:24]}",
            nonce=nonce,
            request_digest=request_digest,
            signature=signature,
            **dataclasses.asdict(request),
        )

    def _validate_network_origin(self, origin: str) -> None:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.port not in {None, 443}
        ):
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "network origin is not normalized",
                self.protocol,
            )
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost":
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "local network origins are forbidden",
                self.protocol,
            )
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        if not address.is_global:
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "non-global network origins are forbidden",
                self.protocol,
            )

    def mediate_egress(
        self,
        *,
        effect_kind: str,
        transport: str,
        destination: str,
        serialized_payload: bytes,
    ) -> EgressRecord:
        self._require_state("receipt_ready")
        self.protocol.require_enum("effect_kind", effect_kind)
        self.protocol.require_enum("egress_transport", transport)
        if (
            transport in _BLOCKED_EGRESS_TRANSPORTS
            or transport not in self.host.mediated_transports
        ):
            _fail(
                "UNMEDIATED_EFFECT_BLOCKED",
                "egress transport is not fully mediated",
                self.protocol,
            )
        if not isinstance(serialized_payload, bytes):
            _fail(
                "RECORD_INVALID",
                "egress payload must be exact serialized bytes",
                self.protocol,
            )
        payload_size = len(serialized_payload)
        if payload_size > self.protocol.limits["serialized_message_bytes"]:
            _fail(
                "LIMIT_EXCEEDED", "serialized message exceeds its bound", self.protocol
            )
        if (
            self.outbound_bytes + payload_size
            > self.protocol.limits["aggregate_outbound_bytes"]
        ):
            _fail(
                "LIMIT_EXCEEDED",
                "aggregate outbound bytes exceed their bound",
                self.protocol,
            )
        try:
            decoded = serialized_payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            _fail(
                "REPORT_REDACTION_FAILED", "egress payload is not UTF-8", self.protocol
            )
        matches = _SECRET_SCANNER.scan(decoded)
        if matches:
            _fail(
                "EGRESS_SECRET_DETECTED",
                "serialized egress contains a secret",
                self.protocol,
            )
        destination_digest = _record_digest(destination)
        self.outbound_bytes += payload_size
        record = EgressRecord(
            run_id=self.frame.run_id,
            effect_kind=effect_kind,
            transport=transport,
            destination_digest=destination_digest,
            payload_digest=_sha256(serialized_payload),
            payload_bytes=payload_size,
            aggregate_outbound_bytes=self.outbound_bytes,
        )
        self._mediated_egress.add(_record_digest(record))
        self.host._trace(self.frame.run_id, "gate", "egress.scan_exact", record)
        return record

    def _consume_permit(
        self, permit: OperationPermit, request: OperationRequest
    ) -> None:
        if not isinstance(
            permit, OperationPermit
        ) or not self.host.verify_permit_signature(permit):
            _fail(
                "OPERATION_PERMIT_INVALID",
                "operation permit signature is invalid",
                self.protocol,
            )
        expected_permit_id = (
            f"permit-{_record_digest((permit.request_digest, permit.nonce))[:24]}"
        )
        if permit.permit_id != expected_permit_id:
            _fail(
                "OPERATION_PERMIT_INVALID",
                "operation permit identity is invalid",
                self.protocol,
            )
        if (
            permit.run_id != self.frame.run_id
            or permit.request_digest != _record_digest(request)
        ):
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "operation permit scope differs",
                self.protocol,
            )
        expected = dataclasses.asdict(request)
        actual = {key: getattr(permit, key) for key in expected}
        if actual != expected:
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "operation permit fields differ",
                self.protocol,
            )
        if permit.permit_id in self._used_permits:
            _fail(
                "OPERATION_PERMIT_REPLAYED",
                "operation permit was already consumed",
                self.protocol,
            )
        self._used_permits.add(permit.permit_id)

    def _effect_gate(
        self,
        *,
        effect_kind: str,
        scope: str,
        scope_digest: str,
        now: int,
        require_lease: bool,
    ) -> None:
        self._require_state("receipt_ready")
        self._require_live_approval(scope, now)
        if (
            self.receipt_id is None
            or not self.receipt_synced
            or self.receipt_id not in self.host.receipt_synced
        ):
            _fail(
                "RECEIPT_NOT_READY",
                "durable receipt sync must precede the effect",
                self.protocol,
            )
        if require_lease and not self.lease_held:
            _fail(
                "MUTATION_LEASE_UNAVAILABLE",
                "mutation lease must precede the effect",
                self.protocol,
            )
        if (effect_kind, scope, scope_digest) not in self._prepared_effects:
            _fail(
                "RECEIPT_NOT_READY",
                "receipt intent does not bind this exact effect",
                self.protocol,
            )
        self._verify_control_snapshot()
        self._verify_effect_evidence(now)
        self.host._trace(self.frame.run_id, "gate", "effect.ready", self.snapshot())

    def _consume_prepared_effect(
        self, effect_kind: str, scope: str, scope_digest: str
    ) -> None:
        try:
            self._prepared_effects.remove((effect_kind, scope, scope_digest))
        except ValueError:
            _fail(
                "RECEIPT_NOT_READY", "effect intent was already consumed", self.protocol
            )

    def _record_effect_outcome(
        self,
        *,
        effect_kind: str,
        scope_digest: str,
        status: str,
        error_code: str | None,
    ) -> None:
        if self.receipt_id is None:
            _fail("RECEIPT_NOT_READY", "receipt journal disappeared", self.protocol)
        self._receipt_sequence += 1
        event = ReceiptEvent(
            sequence=self._receipt_sequence,
            run_id=self.frame.run_id,
            receipt_id=self.receipt_id,
            event_type="result",
            effect_kind=effect_kind,
            scope_digest=scope_digest,
            status=status,
            error_code=error_code,
        )
        self.host.append_receipt(event)
        self.host.sync_receipt(self.frame.run_id, self.receipt_id)
        self.receipt_synced = True

    def execute_product_mutation(
        self, *, scope: str, scope_digest: str, now: int
    ) -> None:
        self._effect_gate(
            effect_kind="product_mutation",
            scope=scope,
            scope_digest=scope_digest,
            now=now,
            require_lease=True,
        )
        self._consume_prepared_effect("product_mutation", scope, scope_digest)
        self.run_state = "effect_active"
        try:
            self.host.record_effect(self.frame.run_id, "product_mutation", scope_digest)
        except SimulatedEffectFailure as exc:
            self.mutation_state = "partial"
            self._record_effect_outcome(
                effect_kind="product_mutation",
                scope_digest=scope_digest,
                status="partial",
                error_code="PARTIAL_MUTATION",
            )
            self.finish("partial", error_code="PARTIAL_MUTATION")
            raise CoordinatorError(
                "PARTIAL_MUTATION",
                "simulated product mutation was partial",
                self.protocol,
            ) from exc
        self.mutation_state = "committed"
        self._record_effect_outcome(
            effect_kind="product_mutation",
            scope_digest=scope_digest,
            status="committed",
            error_code=None,
        )
        self.run_state = "receipt_ready"

    def execute_external_effect(
        self,
        *,
        scope: str,
        request: OperationRequest,
        permit: OperationPermit,
        egress: EgressRecord,
        now: int,
    ) -> None:
        self._effect_gate(
            effect_kind="external_effect",
            scope=scope,
            scope_digest=request.expected_mutation_digest,
            now=now,
            require_lease=False,
        )
        if (
            egress.effect_kind != "external_effect"
            or egress.run_id != self.frame.run_id
        ):
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "egress record differs from the effect",
                self.protocol,
            )
        if _record_digest(egress) not in self._mediated_egress:
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "egress record was not mediated",
                self.protocol,
            )
        if egress.destination_digest != _record_digest(request.network_origin):
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "egress destination differs from the permit",
                self.protocol,
            )
        self._consume_permit(permit, request)
        self.host.revalidate_network_origin(self.frame.run_id, request.network_origin)
        scope_digest = request.expected_mutation_digest
        self._mediated_egress.remove(_record_digest(egress))
        self._consume_prepared_effect("external_effect", scope, scope_digest)
        self.run_state = "effect_active"
        try:
            self.host.record_effect(self.frame.run_id, "external_effect", scope_digest)
        except SimulatedEffectFailure as exc:
            self.mutation_state = "partial"
            self._record_effect_outcome(
                effect_kind="external_effect",
                scope_digest=scope_digest,
                status="partial",
                error_code="PARTIAL_MUTATION",
            )
            self.finish("partial", error_code="PARTIAL_MUTATION")
            raise CoordinatorError(
                "PARTIAL_MUTATION",
                "simulated external effect was partial",
                self.protocol,
            ) from exc
        self.mutation_state = "committed"
        self._record_effect_outcome(
            effect_kind="external_effect",
            scope_digest=scope_digest,
            status="committed",
            error_code=None,
        )
        self.run_state = "receipt_ready"

    def execute_ai_child(
        self, *, scope: str, scope_digest: str, egress: EgressRecord, now: int
    ) -> None:
        self._effect_gate(
            effect_kind="ai_child",
            scope=scope,
            scope_digest=scope_digest,
            now=now,
            require_lease=False,
        )
        if egress.effect_kind != "ai_child" or egress.run_id != self.frame.run_id:
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "egress record differs from the child",
                self.protocol,
            )
        if _record_digest(egress) not in self._mediated_egress:
            _fail(
                "OPERATION_SCOPE_MISMATCH",
                "child egress was not mediated",
                self.protocol,
            )
        self._mediated_egress.remove(_record_digest(egress))
        self._consume_prepared_effect("ai_child", scope, scope_digest)
        self.run_state = "effect_active"
        try:
            self.host.record_effect(self.frame.run_id, "ai_child", scope_digest)
        except SimulatedEffectFailure as exc:
            self._record_effect_outcome(
                effect_kind="ai_child",
                scope_digest=scope_digest,
                status="failed",
                error_code="UNKNOWN_ERROR",
            )
            self.finish("failed", error_code="UNKNOWN_ERROR")
            raise CoordinatorError(
                "UNKNOWN_ERROR", "simulated AI child failed", self.protocol
            ) from exc
        self._record_effect_outcome(
            effect_kind="ai_child",
            scope_digest=scope_digest,
            status="committed",
            error_code=None,
        )
        self.run_state = "receipt_ready"

    def log_gate(
        self,
        *,
        capability_id: str,
        source_relative_path: str,
        digest: str,
        status: str,
        error_code: str | None,
        agent_id: str | None,
        timing_ms: int,
        gate_result: str,
    ) -> LogEvent:
        if (
            self.approval is not None
            and self.approval.state == "approved"
            and self.receipt_id is None
        ):
            _fail(
                "RECEIPT_NOT_READY",
                "receipt reservation must be the first write after approval",
                self.protocol,
            )
        raw_fields = {
            "capability_id": capability_id,
            "source_relative_path": source_relative_path,
            "status": status,
            "error_code": error_code,
            "agent_id": agent_id,
        }
        if _SECRET_SCANNER.scan(_canonical_json(raw_fields).decode("utf-8")):
            _fail(
                "REPORT_REDACTION_FAILED", "log event contains a secret", self.protocol
            )
        if capability_id not in self.protocol.capability_ids:
            _fail("RECORD_INVALID", "log capability is unknown", self.protocol)
        relative = _require_relative_path(source_relative_path, self.protocol)
        _require_digest(digest, "log digest", self.protocol)
        self.protocol.require_enum("log_status", status)
        if error_code is not None and error_code not in self.protocol.errors:
            error_code = "UNKNOWN_ERROR"
        agent = (
            _require_identifier(agent_id, "agent_id", self.protocol)
            if agent_id is not None
            else None
        )
        self.protocol.require_enum("gate_result", gate_result)
        if (
            not isinstance(timing_ms, int)
            or not 0 <= timing_ms <= self.protocol.limits["wall_clock_seconds"] * 1000
        ):
            _fail("RECORD_INVALID", "log timing is invalid", self.protocol)
        events = self.host.logs.get(self.frame.run_id, [])
        if len(events) >= self.protocol.limits["log_events_per_run"]:
            _fail("LIMIT_EXCEEDED", "log event limit exceeded", self.protocol)
        self._log_sequence += 1
        event = LogEvent(
            sequence=self._log_sequence,
            run_id=self.frame.run_id,
            capability_id=capability_id,
            source_relative_path=relative,
            digest=digest,
            status=status,
            error_code=error_code,
            agent_id=agent,
            timing_ms=timing_ms,
            gate_result=gate_result,
        )
        current_bytes = sum(len(_canonical_json(item)) for item in events)
        if (
            current_bytes + len(_canonical_json(event))
            > self.protocol.limits["log_bytes_per_run"]
        ):
            _fail("LIMIT_EXCEEDED", "log byte limit exceeded", self.protocol)
        if _SECRET_SCANNER.scan(_canonical_json(event).decode("utf-8")):
            _fail(
                "REPORT_REDACTION_FAILED", "log event contains a secret", self.protocol
            )
        self.host.persist_log(event)
        return event

    def issue_diagnostic(self, code: str) -> Mapping[str, object]:
        known = code if code in self.protocol.errors else "UNKNOWN_ERROR"
        return {
            "code": known,
            "reporting_class": self.protocol.reporting_class_for_error(code),
            "fields": ("run_id", "capability_id", "digest", "gate_result"),
            "uploads_automatically": False,
        }

    def finish(
        self, terminal_state: str, *, error_code: str | None = None
    ) -> TerminalRecord:
        self.protocol.require_enum("terminal_state", terminal_state)
        if self.run_state == "terminal":
            _fail("TERMINAL_STATE_INVALID", "run is already terminal", self.protocol)
        if (
            self.approval is not None
            and self.approval.state == "approved"
            and self.receipt_id is None
        ):
            _fail(
                "RECEIPT_NOT_READY",
                "approved run requires a receipt before terminal persistence",
                self.protocol,
            )
        if self.mutation_state == "partial" and terminal_state != "partial":
            _fail(
                "TERMINAL_STATE_INVALID", "partial mutation is fail-stop", self.protocol
            )
        if (
            terminal_state == "succeeded"
            and self.frame.mutation_class != "none"
            and self.mutation_state != "committed"
        ):
            _fail(
                "TERMINAL_STATE_INVALID", "mutating run did not commit", self.protocol
            )
        if error_code is not None and error_code not in self.protocol.errors:
            error_code = "UNKNOWN_ERROR"
        if self.receipt_id is not None:
            self._receipt_sequence += 1
            terminal_event = ReceiptEvent(
                sequence=self._receipt_sequence,
                run_id=self.frame.run_id,
                receipt_id=self.receipt_id,
                event_type="terminal",
                effect_kind=self._last_effect_kind or "product_mutation",
                scope_digest=self.frame.repository_digest,
                status=terminal_state,
                error_code=error_code,
            )
            self.host.append_receipt(terminal_event)
            self.host.sync_receipt(self.frame.run_id, self.receipt_id)
            self.receipt_synced = True
        record = TerminalRecord(
            run_id=self.frame.run_id,
            terminal_state=terminal_state,
            mutation_state=self.mutation_state,
            receipt_id=self.receipt_id,
            error_code=error_code,
            frame_digest=self.frame_digest,
        )
        self.terminal_state = terminal_state
        self.run_state = "terminal"
        self.host.persist_terminal(record)
        if self.lease_held:
            self.host.release_lease(self.frame.run_id, self.frame.repository_digest)
            self.lease_held = False
        return record


assert_protocol_schema_alignment()
