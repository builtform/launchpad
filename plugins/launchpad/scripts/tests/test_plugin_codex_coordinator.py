"""Section 7 fixture coordinator and fake-host effect-gate tests."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import stat
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType, ModuleType

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SCRIPTS.parent
FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "codex_compatibility"
    / "fake_host_coordinator.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "plugin_codex_fake_coordinator_tests", FIXTURE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


coordinator = _load_module()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required_capabilities() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                "atomic_receipt_reservation",
                "authenticated_user_interaction",
                "effect_revocation_status",
                "operation_authorization",
                "plugin_durable_state",
                "repository_read",
                "repository_write",
                "serialized_payload_mediation",
            }
        )
    )


def _approval_scope(scope: str) -> tuple[str, ...]:
    return (scope,)


def _frame(
    protocol,
    host,
    *,
    run_id: str = "run-001",
    scope: str = "product-write:approved-artifact",
    mutation_class: str = "project_files",
    approval_kind: str = "effect",
    exact_diff_digest: str | None = None,
    approval_digest: str | None = None,
    project_admission_digests: tuple[str, ...] = (),
    active_call_stack: tuple[str, ...] = ("lp-harden-plan",),
    required_capabilities: tuple[str, ...] | None = None,
    tool_profile: str = "workspace_write",
) -> coordinator.ExecutionFrame:
    command_digest = _digest("command")
    argument_digest = _digest("arguments")
    pinned_approval = coordinator.approval_scope_digest(
        run_id=run_id,
        project_root_digest=host.project_root_digest,
        command_argument_digest_value=coordinator.command_argument_digest(
            command_digest, argument_digest
        ),
        graph_digest=_digest("graph"),
        mutation_class=mutation_class,
        effect_scope=_approval_scope(scope),
        approval_kind=approval_kind,
        exact_diff_digest=exact_diff_digest,
    )
    return coordinator.ExecutionFrame(
        run_id=run_id,
        command_id="lp-harden-plan",
        command_digest=command_digest,
        argument_digest=argument_digest,
        graph_digest=_digest("graph"),
        configuration_digest=_digest("configuration"),
        roster_digest=_digest("roster"),
        repository_digest=host.repository_state.repository_digest,
        repository_head=host.repository_state.head,
        repository_index_digest=host.repository_state.index_digest,
        package_digest=_digest("package"),
        manifest_digest=_digest("manifest"),
        entry_skill_digest=_digest("entry-skill"),
        resolver_digest=_digest("resolver"),
        coordinator_digest=_digest("fixture-coordinator"),
        protocol_version=protocol.protocol_version,
        protocol_digest=protocol.digest,
        support_evidence_version="fixture-1",
        evidence_digest=host.evidence.evidence_digest,
        approval_digest=approval_digest or pinned_approval,
        project_admission_digests=project_admission_digests,
        mutation_class=mutation_class,
        required_capabilities=required_capabilities or _required_capabilities(),
        tool_profile=tool_profile,
        write_scopes=() if mutation_class == "none" else ("docs/plans/",),
        active_call_stack=active_call_stack,
        depth=len(active_call_stack) - 1,
        cancellation_token_digest=_digest("cancel"),
        remaining_child_starts=protocol.limits["child_starts"],
        remaining_context_tokens=protocol.defaults["fallback_context_tokens"],
        loaded_resource_digests=tuple(sorted({_digest("command"), _digest("graph")})),
    )


def _host(
    tmp_path: Path,
    protocol,
    *,
    capabilities: tuple[str, ...] | None = None,
    evidence: coordinator.EvidenceRecord | None = None,
    storage_capacity: int | None = None,
) -> coordinator.FakeHostRecorder:
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    repository = coordinator.RepositoryState(
        repository_digest=_digest("repository"),
        head="abc123",
        index_digest=_digest("index"),
    )
    executable = coordinator.ExecutableIdentity(
        name="git-version",
        absolute_path="/usr/bin/git",
        device=1,
        inode=2,
        mode=stat.S_IFREG | 0o755,
        digest=_digest("/usr/bin/git"),
    )
    return coordinator.FakeHostRecorder(
        protocol=protocol,
        capabilities=capabilities or _required_capabilities(),
        enforceable_profiles=("effectful", "read_only", "workspace_write"),
        mediated_transports=("host_provider", "subagent"),
        project_root=project,
        repository_state=repository,
        evidence=evidence
        or coordinator.EvidenceRecord(
            evidence_digest=_digest("evidence"),
            expires_at=1_000,
            revoked=False,
            authenticated=True,
        ),
        diagnostic_identities={"git-version": executable},
        diagnostic_allowlist={"git-version": (("--version",),)},
        diagnostic_outputs={
            ("git-version", ("--version",)): (0, b"git version fixture\n")
        },
        network_resolutions={"https://api.example.com": ("93.184.216.34",)},
        storage_capacity=storage_capacity,
    )


def _opened(
    tmp_path: Path,
    *,
    protocol=None,
    scope: str = "product-write:approved-artifact",
    mutation_class: str = "project_files",
    approval_kind: str = "effect",
    exact_diff_digest: str | None = None,
    capabilities: tuple[str, ...] | None = None,
    evidence: coordinator.EvidenceRecord | None = None,
    storage_capacity: int | None = None,
    frame_updates: dict[str, object] | None = None,
    frame_required_capabilities: tuple[str, ...] | None = None,
    tool_profile: str = "workspace_write",
):
    contract = protocol or coordinator._PROTOCOL.load_protocol()
    host = _host(
        tmp_path,
        contract,
        capabilities=capabilities,
        evidence=evidence,
        storage_capacity=storage_capacity,
    )
    frame = _frame(
        contract,
        host,
        scope=scope,
        mutation_class=mutation_class,
        approval_kind=approval_kind,
        exact_diff_digest=exact_diff_digest,
        required_capabilities=frame_required_capabilities,
        tool_profile=tool_profile,
    )
    if frame_updates:
        frame = replace(frame, **frame_updates)
    runtime = coordinator.StatefulSafetyCoordinator(
        frame, host, protocol=contract, now=100
    )
    return contract, host, runtime


def _preflight(runtime) -> None:
    runtime.preflight(_required_capabilities(), "workspace_write", now=100)


def _approve(
    host,
    runtime,
    *,
    scope: str = "product-write:approved-artifact",
    approval_kind: str = "effect",
    exact_diff_digest: str | None = None,
    event_id: str = "event-001",
    source: str = "interactive",
):
    request = runtime.begin_approval(
        effect_scope=(scope,),
        approval_kind=approval_kind,
        exact_diff_digest=exact_diff_digest,
        expires_at=200,
        now=100,
        nonce="a" * 64,
    )
    host.register_approval_event(
        event_id,
        coordinator._record_digest(request),
        source=source,
    )
    return runtime.resolve_approval(request, event_id, now=101)


def _prepare_product(host, runtime, scope: str = "product-write:approved-artifact"):
    scope_digest = _digest(scope)
    runtime.prepare_receipt(
        effect_kind="product_mutation",
        scope_digest=scope_digest,
        scope=scope,
        now=102,
    )
    runtime.acquire_mutation_lease()
    return scope_digest


def _assert_code(code: str, call) -> coordinator.CoordinatorError:
    with pytest.raises(coordinator.CoordinatorError) as raised:
        call()
    assert raised.value.code == code
    return raised.value


def test_fixture_contract_is_protocol_owned_and_release_runtime_is_declarative() -> None:
    protocol = coordinator._PROTOCOL.load_protocol()
    coordinator.assert_protocol_schema_alignment(protocol)
    assert "persistent_instruction_write" in protocol.capability_ids
    assert set(coordinator._SCHEMA_TYPES) <= set(protocol.record_schemas)
    assert not (SCRIPTS / "plugin-codex-runtime.py").exists()
    assert (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").is_file()
    assert (PLUGIN_ROOT / "codex" / "support-evidence.json").is_file()


def test_frame_pins_control_state_and_rejects_cycle_depth_and_digest_forgery(
    tmp_path: Path,
) -> None:
    protocol = coordinator._PROTOCOL.load_protocol()
    host = _host(tmp_path, protocol)
    valid = _frame(protocol, host)
    runtime = coordinator.StatefulSafetyCoordinator(valid, host, now=100)
    assert runtime.snapshot().frame_digest == coordinator._record_digest(valid)

    cycle = replace(
        valid,
        active_call_stack=("lp-harden-plan", "lp-harden-plan"),
        depth=1,
    )
    _assert_code(
        "RECORD_INVALID",
        lambda: coordinator.StatefulSafetyCoordinator(cycle, host, now=100),
    )
    _assert_code(
        "DIGEST_INVALID",
        lambda: coordinator.StatefulSafetyCoordinator(
            replace(valid, package_digest="forged"), host, now=100
        ),
    )
    _assert_code(
        "RECORD_INVALID",
        lambda: coordinator.StatefulSafetyCoordinator(
            replace(
                valid,
                required_capabilities=(
                    "repository_read",
                    "repository_read",
                ),
            ),
            host,
            now=100,
        ),
    )


def test_preflight_fails_closed_for_missing_profile_capability_drift_and_evidence(
    tmp_path: Path,
) -> None:
    protocol = coordinator._PROTOCOL.load_protocol()
    missing = tuple(
        item for item in _required_capabilities() if item != "operation_authorization"
    )
    _contract, host, runtime = _opened(
        tmp_path / "missing", protocol=protocol, capabilities=missing
    )
    _assert_code(
        "CAPABILITY_BLOCKED",
        lambda: runtime.preflight(_required_capabilities(), "workspace_write", now=100),
    )
    assert host.effects == []

    _contract, host, runtime = _opened(tmp_path / "expanded-profile", protocol=protocol)
    narrowed = tuple(
        item
        for item in _required_capabilities()
        if item != "serialized_payload_mediation"
    )
    _assert_code(
        "PREFLIGHT_FAILED",
        lambda: runtime.preflight(narrowed, "workspace_write", now=100),
    )
    assert host.effects == []

    _contract, host, runtime = _opened(tmp_path / "profile", protocol=protocol)
    host.enforceable_profiles = ("read_only",)
    _assert_code(
        "TOOL_PROFILE_UNENFORCEABLE",
        lambda: runtime.preflight(_required_capabilities(), "workspace_write", now=100),
    )
    assert host.effects == []

    _contract, host, runtime = _opened(tmp_path / "drift", protocol=protocol)
    host.repository_state = replace(host.repository_state, head="changed")
    _assert_code(
        "REPOSITORY_DRIFT",
        lambda: runtime.preflight(_required_capabilities(), "workspace_write", now=100),
    )
    assert host.effects == []

    stale = coordinator.EvidenceRecord(
        evidence_digest=_digest("evidence"),
        expires_at=99,
        revoked=False,
        authenticated=True,
    )
    _contract, host, runtime = _opened(
        tmp_path / "stale", protocol=protocol, evidence=stale
    )
    assert runtime.diagnostic_help(100)["status"] == "expired"
    _assert_code(
        "EVIDENCE_EXPIRED",
        lambda: runtime.preflight(_required_capabilities(), "workspace_write", now=100),
    )
    assert host.effects == []

    revoked = replace(stale, expires_at=1_000, revoked=True)
    _contract, host, runtime = _opened(
        tmp_path / "revoked", protocol=protocol, evidence=revoked
    )
    assert runtime.diagnostic_help(100)["status"] == "revoked"
    _assert_code(
        "EVIDENCE_REVOKED",
        lambda: runtime.preflight(_required_capabilities(), "workspace_write", now=100),
    )
    assert host.effects == []


def test_read_only_profile_requires_prompt_free_denial_and_payload_mediation(
    tmp_path: Path,
) -> None:
    protocol = coordinator._PROTOCOL.load_protocol()
    required = tuple(
        sorted(
            {
                "prompt_free_shell_deny",
                "repository_read",
                "serialized_payload_mediation",
            }
        )
    )
    host = _host(tmp_path, protocol, capabilities=required)
    frame = _frame(
        protocol,
        host,
        mutation_class="none",
        approval_digest=coordinator.ZERO_DIGEST,
        required_capabilities=required,
        tool_profile="read_only",
    )
    runtime = coordinator.StatefulSafetyCoordinator(frame, host, now=100)
    assert runtime.preflight(required, "read_only", now=100).gate_result == "pass"

    missing = tuple(item for item in required if item != "prompt_free_shell_deny")
    host = _host(tmp_path / "blocked", protocol, capabilities=missing)
    frame = _frame(
        protocol,
        host,
        mutation_class="none",
        approval_digest=coordinator.ZERO_DIGEST,
        required_capabilities=missing,
        tool_profile="read_only",
    )
    runtime = coordinator.StatefulSafetyCoordinator(frame, host, now=100)
    _assert_code(
        "TOOL_PROFILE_UNENFORCEABLE",
        lambda: runtime.preflight(missing, "read_only", now=100),
    )


def test_diagnostic_uses_attested_absolute_identity_typed_argv_and_minimal_env(
    tmp_path: Path,
) -> None:
    _protocol, host, runtime = _opened(tmp_path)
    _preflight(runtime)
    result = runtime.run_diagnostic("git-version", ("--version",))
    assert result.exit_code == 0
    assert result.environment_digest == coordinator._record_digest(
        {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    )
    assert result.argv_digest == coordinator._record_digest(
        ("/usr/bin/git", "--version")
    )
    assert host.diagnostic_shell_values == [False]
    _assert_code(
        "DIAGNOSTIC_NOT_ALLOWLISTED",
        lambda: runtime.run_diagnostic("git-version", ("status",)),
    )

    identity = host.diagnostic_identities["git-version"]
    host.diagnostic_identities["project-tool"] = replace(
        identity,
        name="project-tool",
        absolute_path=str(host.project_root / "git"),
    )
    _assert_code(
        "EXECUTABLE_IDENTITY_INVALID",
        lambda: runtime.run_diagnostic("project-tool", ("--version",)),
    )

    _protocol, host, runtime = _opened(tmp_path / "swap")
    _preflight(runtime)
    original = host.diagnostic_identities["git-version"]
    identities = iter((original, replace(original, inode=original.inode + 1)))
    host.attest_executable = lambda _run_id, _name: next(identities)
    _assert_code(
        "EXECUTABLE_IDENTITY_INVALID",
        lambda: runtime.run_diagnostic("git-version", ("--version",)),
    )


@dataclass(frozen=True)
class _Admission:
    run_id: str
    workflow_id: str
    child_id: str
    requested_capability: str
    protocol_version: str
    expires_at: int
    content_digest: str


def test_project_prompt_admission_is_pinned_scoped_authenticated_and_one_use(
    tmp_path: Path,
) -> None:
    protocol = coordinator._PROTOCOL.load_protocol()
    provisional = _Admission(
        run_id="run-001",
        workflow_id="lp-harden-plan",
        child_id="child-1",
        requested_capability="repository_read",
        protocol_version=protocol.protocol_version,
        expires_at=200,
        content_digest=_digest("project prompt"),
    )
    admission_digest = coordinator._record_digest(provisional)
    host = _host(tmp_path, protocol)
    frame = _frame(
        protocol,
        host,
        project_admission_digests=(admission_digest,),
    )
    runtime = coordinator.StatefulSafetyCoordinator(frame, host, now=100)
    _preflight(runtime)
    host.register_project_admission(provisional)
    assert (
        runtime.admit_project_prompt(
            provisional,
            child_id="child-1",
            requested_capability="repository_read",
            now=101,
        )
        == admission_digest
    )
    _assert_code(
        "APPROVAL_REPLAYED",
        lambda: runtime.admit_project_prompt(
            provisional,
            child_id="child-1",
            requested_capability="repository_read",
            now=101,
        ),
    )

    host = _host(tmp_path / "forged", protocol)
    forged = replace(provisional, child_id="child-forged")
    frame = _frame(
        protocol,
        host,
        project_admission_digests=(coordinator._record_digest(forged),),
    )
    runtime = coordinator.StatefulSafetyCoordinator(frame, host, now=100)
    _preflight(runtime)
    _assert_code(
        "PROJECT_PROMPT_ADMISSION_UNAVAILABLE",
        lambda: runtime.admit_project_prompt(
            forged,
            child_id="child-forged",
            requested_capability="repository_read",
            now=101,
        ),
    )


def test_approval_rejects_forgery_expansion_expiry_replay_and_decline(
    tmp_path: Path,
) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(tmp_path / "expanded", scope=scope)
    _preflight(runtime)
    _assert_code(
        "APPROVAL_SCOPE_MISMATCH",
        lambda: runtime.begin_approval(
            effect_scope=(scope, "product-write:extra"),
            approval_kind="effect",
            exact_diff_digest=None,
            expires_at=200,
            now=100,
        ),
    )
    assert host.effects == []

    _protocol, host, runtime = _opened(tmp_path / "forged", scope=scope)
    _preflight(runtime)
    request = runtime.begin_approval(
        effect_scope=(scope,),
        approval_kind="effect",
        exact_diff_digest=None,
        expires_at=200,
        now=100,
        nonce="a" * 64,
    )
    host.register_approval_event("forged", _digest("another request"))
    _assert_code(
        "APPROVAL_INVALID",
        lambda: runtime.resolve_approval(request, "forged", now=101),
    )
    assert host.effects == []

    _protocol, host, runtime = _opened(tmp_path / "expired", scope=scope)
    _preflight(runtime)
    request = runtime.begin_approval(
        effect_scope=(scope,),
        approval_kind="effect",
        exact_diff_digest=None,
        expires_at=101,
        now=100,
    )
    _assert_code(
        "APPROVAL_EXPIRED",
        lambda: runtime.resolve_approval(request, "unused", now=101),
    )
    assert host.effects == []

    _protocol, host, runtime = _opened(tmp_path / "declined", scope=scope)
    _preflight(runtime)
    request = runtime.begin_approval(
        effect_scope=(scope,),
        approval_kind="effect",
        exact_diff_digest=None,
        expires_at=200,
        now=100,
    )
    host.register_approval_event(
        "declined",
        coordinator._record_digest(request),
        decision="declined",
    )
    assert runtime.resolve_approval(request, "declined", now=101).state == "declined"
    assert host.effects == []

    _protocol, host, runtime = _opened(tmp_path / "replay", scope=scope)
    _preflight(runtime)
    request = runtime.begin_approval(
        effect_scope=(scope,),
        approval_kind="effect",
        exact_diff_digest=None,
        expires_at=200,
        now=100,
        nonce="b" * 64,
    )
    digest = coordinator._record_digest(request)
    host.register_approval_event("replay", digest)
    runtime.resolve_approval(request, "replay", now=101)
    _assert_code(
        "APPROVAL_REPLAYED",
        lambda: host.authenticate_approval("run-001", "replay", digest),
    )


def test_persistent_instruction_write_is_separate_interactive_and_exact_diff_bound(
    tmp_path: Path,
) -> None:
    protocol = coordinator._PROTOCOL.load_protocol()
    capabilities = tuple(
        sorted(set(_required_capabilities()) | {"persistent_instruction_write"})
    )
    diff_digest = _digest("escaped exact diff")
    scope = "instruction-write:agents-md"
    _contract, host, runtime = _opened(
        tmp_path,
        protocol=protocol,
        scope=scope,
        approval_kind="persistent_instruction_write",
        exact_diff_digest=diff_digest,
        capabilities=capabilities,
        frame_required_capabilities=capabilities,
    )
    runtime.preflight(capabilities, "workspace_write", now=100)
    request = runtime.begin_approval(
        effect_scope=(scope,),
        approval_kind="persistent_instruction_write",
        exact_diff_digest=diff_digest,
        expires_at=200,
        now=100,
    )
    host.register_approval_event(
        "headless",
        coordinator._record_digest(request),
        source="headless",
    )
    _assert_code(
        "APPROVAL_SCOPE_MISMATCH",
        lambda: runtime.resolve_approval(request, "headless", now=101),
    )
    assert host.effects == []

    _contract, host, runtime = _opened(
        tmp_path / "generic",
        protocol=protocol,
        scope=scope,
        capabilities=capabilities,
        frame_required_capabilities=capabilities,
    )
    runtime.preflight(capabilities, "workspace_write", now=100)
    _assert_code(
        "APPROVAL_SCOPE_MISMATCH",
        lambda: runtime.begin_approval(
            effect_scope=(scope,),
            approval_kind="effect",
            exact_diff_digest=diff_digest,
            expires_at=200,
            now=100,
        ),
    )


def test_receipt_reserve_intent_and_sync_precede_mutation_effect(
    tmp_path: Path,
) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(tmp_path, scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    scope_digest = _prepare_product(host, runtime, scope)
    runtime.execute_product_mutation(scope=scope, scope_digest=scope_digest, now=103)
    terminal = runtime.finish("succeeded")
    assert terminal.mutation_state == "committed"
    assert not runtime.snapshot().lease_held

    operations = [event.operation for event in host.trace]
    reserve = operations.index("receipt.reserve")
    intent = operations.index("receipt.append")
    sync = operations.index("receipt.sync")
    effect = operations.index("product_mutation.begin")
    assert reserve < intent < sync < effect
    adapter_writes = [
        event.operation
        for event in host.trace
        if event.category == "adapter_internal_write"
    ]
    assert adapter_writes[0] == "receipt.reserve"


def test_missing_receipt_capacity_and_lease_block_with_zero_effects(
    tmp_path: Path,
) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(
        tmp_path / "capacity", scope=scope, storage_capacity=1
    )
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    _assert_code(
        "RECEIPT_RESERVATION_UNAVAILABLE",
        lambda: runtime.prepare_receipt(
            effect_kind="product_mutation",
            scope_digest=_digest(scope),
            scope=scope,
            now=102,
        ),
    )
    assert host.effects == []

    _protocol, host, runtime = _opened(tmp_path / "lease", scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    runtime.prepare_receipt(
        effect_kind="product_mutation",
        scope_digest=_digest(scope),
        scope=scope,
        now=102,
    )
    _assert_code(
        "MUTATION_LEASE_UNAVAILABLE",
        lambda: runtime.execute_product_mutation(
            scope=scope, scope_digest=_digest(scope), now=103
        ),
    )
    assert host.effects == []


def _operation_request(run_id: str = "run-001") -> coordinator.OperationRequest:
    return coordinator.OperationRequest(
        run_id=run_id,
        effect_kind="external_effect",
        executable_digest=_digest("host-api"),
        subcommand="publish",
        allowed_flags=("--dry-run=false",),
        cwd_digest=_digest("cwd"),
        path_digests=(_digest("artifact"),),
        network_origin="https://api.example.com",
        network_method="POST",
        account_digest=_digest("account"),
        resource_digest=_digest("resource"),
        credential_class="host-managed",
        expected_mutation_digest=_digest("external mutation"),
    )


def test_external_permit_is_exact_signed_one_use_and_scope_bound(
    tmp_path: Path,
) -> None:
    scope = "external:publish-artifact"
    _protocol, host, runtime = _opened(
        tmp_path, scope=scope, mutation_class="external_state"
    )
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    request = _operation_request()
    runtime.prepare_receipt(
        effect_kind="external_effect",
        scope_digest=request.expected_mutation_digest,
        scope=scope,
        now=102,
    )
    permit = runtime.issue_operation_permit(request, scope=scope, now=103)
    payload = b'{"artifact":"safe"}'
    egress = runtime.mediate_egress(
        effect_kind="external_effect",
        transport="host_provider",
        destination=request.network_origin,
        serialized_payload=payload,
    )
    runtime.execute_external_effect(
        scope=scope,
        request=request,
        permit=permit,
        egress=egress,
        now=104,
    )
    runtime.prepare_receipt(
        effect_kind="external_effect",
        scope_digest=request.expected_mutation_digest,
        scope=scope,
        now=105,
    )
    replay_egress = runtime.mediate_egress(
        effect_kind="external_effect",
        transport="host_provider",
        destination=request.network_origin,
        serialized_payload=payload,
    )
    _assert_code(
        "OPERATION_PERMIT_REPLAYED",
        lambda: runtime.execute_external_effect(
            scope=scope,
            request=request,
            permit=permit,
            egress=replay_egress,
            now=105,
        ),
    )

    forged = replace(permit, network_method="DELETE")
    _assert_code(
        "OPERATION_SCOPE_MISMATCH",
        lambda: runtime._consume_permit(forged, request),
    )
    _assert_code(
        "OPERATION_SCOPE_MISMATCH",
        lambda: runtime.issue_operation_permit(
            replace(request, network_origin="http://127.0.0.1"),
            scope=scope,
            now=105,
        ),
    )


def test_egress_scans_exact_bytes_and_blocks_secrets_and_unmediated_transports(
    tmp_path: Path,
) -> None:
    scope = "ai-child:review"
    _protocol, host, runtime = _opened(tmp_path, scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    runtime.prepare_receipt(
        effect_kind="ai_child",
        scope_digest=_digest(scope),
        scope=scope,
        now=102,
    )
    _assert_code(
        "EGRESS_SECRET_DETECTED",
        lambda: runtime.mediate_egress(
            effect_kind="ai_child",
            transport="subagent",
            destination="fixture-child",
            serialized_payload=b"api_key=ABCDEFGHIJKLMNOPQRSTUVWX",
        ),
    )
    _assert_code(
        "UNMEDIATED_EFFECT_BLOCKED",
        lambda: runtime.mediate_egress(
            effect_kind="ai_child",
            transport="browser",
            destination="https://example.com",
            serialized_payload=b"safe",
        ),
    )
    safe = runtime.mediate_egress(
        effect_kind="ai_child",
        transport="subagent",
        destination="fixture-child",
        serialized_payload=b'{"task":"review"}',
    )
    runtime.execute_ai_child(
        scope=scope,
        scope_digest=_digest(scope),
        egress=safe,
        now=103,
    )
    persisted = coordinator._canonical_json(
        {"trace": host.trace, "receipts": host.receipts}
    )
    assert b"api_key" not in persisted
    assert b"ABCDEFGHIJKLMNOPQRSTUVWX" not in persisted
    operations = [event.operation for event in host.trace]
    assert operations.index("receipt.sync") < operations.index("ai_child.begin")


def test_persistence_contains_only_closed_metadata_not_raw_data_plane_values(
    tmp_path: Path,
) -> None:
    scope = "ai-child:review"
    _protocol, host, runtime = _opened(tmp_path, scope=scope)
    host.diagnostic_outputs[("git-version", ("--version",))] = (
        0,
        b"RAW_CHILD_OUTPUT_MARKER",
    )
    _preflight(runtime)
    runtime.run_diagnostic("git-version", ("--version",))
    _approve(host, runtime, scope=scope)
    runtime.prepare_receipt(
        effect_kind="ai_child",
        scope_digest=_digest(scope),
        scope=scope,
        now=102,
    )
    payload = (
        b'{"prompt":"RAW_PROMPT_MARKER","arguments":"RAW_ARGUMENT_MARKER",'
        b'"environment":"RAW_ENVIRONMENT_MARKER"}'
    )
    egress = runtime.mediate_egress(
        effect_kind="ai_child",
        transport="subagent",
        destination="fixture-child",
        serialized_payload=payload,
    )
    runtime.execute_ai_child(
        scope=scope,
        scope_digest=_digest(scope),
        egress=egress,
        now=103,
    )
    runtime.log_gate(
        capability_id="repository_read",
        source_relative_path="commands/lp-harden-plan.md",
        digest=_digest("source"),
        status="checked",
        error_code=None,
        agent_id="review-agent",
        timing_ms=4,
        gate_result="pass",
    )
    persisted = coordinator._canonical_json(
        {
            "trace": host.trace,
            "receipts": host.receipts,
            "logs": host.logs,
            "terminals": host.terminals,
        }
    )
    for marker in (
        b"RAW_PROMPT_MARKER",
        b"RAW_ARGUMENT_MARKER",
        b"RAW_ENVIRONMENT_MARKER",
        b"RAW_CHILD_OUTPUT_MARKER",
        str(host.project_root).encode("utf-8"),
    ):
        assert marker not in persisted


def test_repository_drift_after_receipt_still_blocks_before_effect(
    tmp_path: Path,
) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(tmp_path, scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    scope_digest = _prepare_product(host, runtime, scope)
    host.repository_state = replace(
        host.repository_state, index_digest=_digest("drift")
    )
    _assert_code(
        "REPOSITORY_DRIFT",
        lambda: runtime.execute_product_mutation(
            scope=scope, scope_digest=scope_digest, now=103
        ),
    )
    assert host.effects == []


def test_effect_requires_exact_receipt_intent_and_unchanged_control_snapshot(
    tmp_path: Path,
) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(tmp_path / "intent", scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    _prepare_product(host, runtime, scope)
    _assert_code(
        "RECEIPT_NOT_READY",
        lambda: runtime.execute_product_mutation(
            scope=scope,
            scope_digest=_digest("different effect"),
            now=103,
        ),
    )
    assert host.effects == []

    _protocol, host, runtime = _opened(tmp_path / "control", scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    scope_digest = _prepare_product(host, runtime, scope)
    assert host.control_snapshot is not None
    host.control_snapshot["configuration_digest"] = _digest("changed config")
    _assert_code(
        "SNAPSHOT_MISMATCH",
        lambda: runtime.execute_product_mutation(
            scope=scope,
            scope_digest=scope_digest,
            now=103,
        ),
    )
    assert host.effects == []


def test_approval_and_evidence_are_rechecked_immediately_before_effect(
    tmp_path: Path,
) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(tmp_path / "approval", scope=scope)
    _preflight(runtime)
    request = runtime.begin_approval(
        effect_scope=(scope,),
        approval_kind="effect",
        exact_diff_digest=None,
        expires_at=102,
        now=100,
    )
    host.register_approval_event("short", coordinator._record_digest(request))
    runtime.resolve_approval(request, "short", now=101)
    scope_digest = _digest(scope)
    runtime.prepare_receipt(
        effect_kind="product_mutation",
        scope_digest=scope_digest,
        scope=scope,
        now=101,
    )
    runtime.acquire_mutation_lease()
    _assert_code(
        "APPROVAL_EXPIRED",
        lambda: runtime.execute_product_mutation(
            scope=scope, scope_digest=scope_digest, now=102
        ),
    )
    assert host.effects == []

    evidence = coordinator.EvidenceRecord(
        evidence_digest=_digest("evidence"),
        expires_at=103,
        revoked=False,
        authenticated=True,
    )
    _protocol, host, runtime = _opened(
        tmp_path / "evidence", scope=scope, evidence=evidence
    )
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    scope_digest = _prepare_product(host, runtime, scope)
    _assert_code(
        "EVIDENCE_EXPIRED",
        lambda: runtime.execute_product_mutation(
            scope=scope, scope_digest=scope_digest, now=103
        ),
    )
    assert host.effects == []


def test_external_effect_rejects_fabricated_egress_and_private_reresolution(
    tmp_path: Path,
) -> None:
    scope = "external:publish-artifact"
    _protocol, host, runtime = _opened(
        tmp_path / "forged-egress", scope=scope, mutation_class="external_state"
    )
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    request = _operation_request()
    runtime.prepare_receipt(
        effect_kind="external_effect",
        scope_digest=request.expected_mutation_digest,
        scope=scope,
        now=102,
    )
    permit = runtime.issue_operation_permit(request, scope=scope, now=103)
    egress = runtime.mediate_egress(
        effect_kind="external_effect",
        transport="host_provider",
        destination=request.network_origin,
        serialized_payload=b"safe",
    )
    forged = replace(egress, payload_digest=_digest("forged payload"))
    _assert_code(
        "OPERATION_SCOPE_MISMATCH",
        lambda: runtime.execute_external_effect(
            scope=scope,
            request=request,
            permit=permit,
            egress=forged,
            now=104,
        ),
    )
    assert host.effects == []

    host.network_resolutions[request.network_origin] = ("127.0.0.1",)
    _assert_code(
        "OPERATION_SCOPE_MISMATCH",
        lambda: runtime.execute_external_effect(
            scope=scope,
            request=request,
            permit=permit,
            egress=egress,
            now=104,
        ),
    )
    assert host.effects == []


def test_mutation_lease_excludes_an_existing_checkout_owner(tmp_path: Path) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(tmp_path, scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    runtime.prepare_receipt(
        effect_kind="product_mutation",
        scope_digest=_digest(scope),
        scope=scope,
        now=102,
    )
    host.leases[runtime.frame.repository_digest] = "other-host-run"
    _assert_code("MUTATION_LEASE_UNAVAILABLE", runtime.acquire_mutation_lease)
    assert host.effects == []


def test_partial_mutation_is_fail_stop_durable_and_releases_lease(
    tmp_path: Path,
) -> None:
    scope = "product-write:approved-artifact"
    _protocol, host, runtime = _opened(tmp_path, scope=scope)
    _preflight(runtime)
    _approve(host, runtime, scope=scope)
    scope_digest = _prepare_product(host, runtime, scope)
    host.fail_effects.add("product_mutation")
    _assert_code(
        "PARTIAL_MUTATION",
        lambda: runtime.execute_product_mutation(
            scope=scope, scope_digest=scope_digest, now=103
        ),
    )
    snapshot = runtime.snapshot()
    assert snapshot.run_state == "terminal"
    assert snapshot.mutation_state == "partial"
    assert snapshot.terminal_state == "partial"
    assert snapshot.receipt_synced is True
    assert snapshot.lease_held is False
    assert host.terminals["run-001"].terminal_state == "partial"
    _assert_code("TERMINAL_STATE_INVALID", lambda: runtime.finish("succeeded"))


def test_logs_are_closed_bounded_redacted_and_unknown_reporting_is_private(
    tmp_path: Path,
) -> None:
    base = coordinator._PROTOCOL.load_protocol()
    limits = dict(base.limits)
    limits["log_events_per_run"] = 1
    protocol = dataclasses.replace(base, limits=MappingProxyType(limits))
    _contract, _host_value, runtime = _opened(tmp_path, protocol=protocol)
    event = runtime.log_gate(
        capability_id="repository_read",
        source_relative_path="commands/lp-harden-plan.md",
        digest=_digest("source"),
        status="checked",
        error_code=None,
        agent_id="review-agent",
        timing_ms=4,
        gate_result="pass",
    )
    assert tuple(dataclasses.asdict(event)) == protocol.record_schemas["log_event"]
    _assert_code(
        "LIMIT_EXCEEDED",
        lambda: runtime.log_gate(
            capability_id="repository_read",
            source_relative_path="commands/lp-harden-plan.md",
            digest=_digest("source"),
            status="checked",
            error_code=None,
            agent_id=None,
            timing_ms=5,
            gate_result="pass",
        ),
    )
    assert runtime.issue_diagnostic("future-unknown") == {
        "code": "UNKNOWN_ERROR",
        "reporting_class": "private_security",
        "fields": ("run_id", "capability_id", "digest", "gate_result"),
        "uploads_automatically": False,
    }

    _contract, _host_value, runtime = _opened(tmp_path / "paths")
    _assert_code(
        "PATH_ESCAPE",
        lambda: runtime.log_gate(
            capability_id="repository_read",
            source_relative_path="/Users/example/private.txt",
            digest=_digest("source"),
            status="checked",
            error_code=None,
            agent_id=None,
            timing_ms=5,
            gate_result="pass",
        ),
    )
    _assert_code(
        "REPORT_REDACTION_FAILED",
        lambda: runtime.log_gate(
            capability_id="repository_read",
            source_relative_path="commands/lp-harden-plan.md",
            digest=_digest("source"),
            status="checked",
            error_code=None,
            agent_id="token=ABCDEFGHIJKLMNOPQRSTUVWX",
            timing_ms=5,
            gate_result="pass",
        ),
    )


def test_rotation_is_deterministic_and_does_not_drop_active_mutation_evidence(
    tmp_path: Path,
) -> None:
    base = coordinator._PROTOCOL.load_protocol()
    limits = dict(base.limits)
    limits["retained_runs"] = 2
    protocol = dataclasses.replace(base, limits=MappingProxyType(limits))
    host = _host(tmp_path, protocol)
    host.active_mutation_runs.add("run-active")
    for run_id in ("run-active", "run-old", "run-current"):
        host.persist_terminal(
            coordinator.TerminalRecord(
                run_id=run_id,
                terminal_state="partial" if run_id == "run-active" else "failed",
                mutation_state="partial" if run_id == "run-active" else "not_started",
                receipt_id=None,
                error_code="PARTIAL_MUTATION"
                if run_id == "run-active"
                else "PREFLIGHT_FAILED",
                frame_digest=_digest(run_id),
            )
        )
    assert set(host.terminals) == {"run-active", "run-current"}
    assert any(event.operation == "storage.rotate" for event in host.trace)


def test_terminal_state_refuses_success_without_committed_mutation(
    tmp_path: Path,
) -> None:
    _protocol, host, runtime = _opened(tmp_path)
    _preflight(runtime)
    _approve(host, runtime)
    _assert_code("RECEIPT_NOT_READY", lambda: runtime.finish("succeeded"))
    runtime.prepare_receipt(
        effect_kind="product_mutation",
        scope_digest=_digest("product-write:approved-artifact"),
        scope="product-write:approved-artifact",
        now=102,
    )
    _assert_code("TERMINAL_STATE_INVALID", lambda: runtime.finish("succeeded"))
    terminal = runtime.finish("blocked", error_code="PREFLIGHT_FAILED")
    assert terminal.mutation_state == "not_started"
    assert host.effects == []
