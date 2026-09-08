"""Section 2 tests for the strict Codex adapter protocol authority."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SCRIPTS.parent
PROTOCOL_PATH = PLUGIN_ROOT / "codex" / "adapter-protocol.json"
FIXTURES = Path(__file__).parent / "fixtures" / "codex_compatibility" / "protocol_yaml"
MODULE_PATH = SCRIPTS / "plugin-codex-protocol.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("plugin_codex_protocol", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


protocol = _load_module()


def _assert_code(code: str, call: Any) -> None:
    with pytest.raises(protocol.ProtocolValidationError) as raised:
        call()
    assert raised.value.code == code


def _metadata(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema-version": 1,
        "component-kind": "command",
        "direct": {},
        "capabilities": {
            "mutation": "none",
            "interaction": "none",
        },
    }
    value.update(updates)
    return value


def _direct_record(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "commands": [],
        "skills": [],
        "agents": [],
        "references": [],
        "assets": [],
        "scripts": [],
        "external_tools": [],
    }
    value.update(updates)
    return value


def _capability_record(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "required": [],
        "mutation": "none",
        "interaction": "none",
        "external_data_egress": False,
        "write_scopes": [],
        "tool_profile": "inspect_only",
        "fallback": "none",
    }
    value.update(updates)
    return value


def _node(node_id: str = "lp-alpha", **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": node_id,
        "kind": "command",
        "source_path": f"commands/{node_id}.md",
        "source_digest": "a" * 64,
        "metadata_digest": "b" * 64,
        "aggregate_digest": "c" * 64,
        "direct": _direct_record(),
        "capabilities": _capability_record(),
    }
    value.update(updates)
    return value


def _support(resource_id: str = "lp-alpha", **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "resource_id": resource_id,
        "base_support_state": "supported",
        "blocked_reason_codes": [],
        "fallback": "none",
    }
    value.update(updates)
    return value


def _runtime(stage: str = "inventory", **updates: object) -> dict[str, object]:
    contract = protocol.load_protocol()
    value: dict[str, object] = {
        "stage": stage,
        "release_stage": "dogfood",
        "protocol_version": contract.protocol_version,
        "protocol_digest": contract.digest,
        "runtime_payload_digest": None if stage == "inventory" else "d" * 64,
        "root_ids": ["lp-alpha"],
        "nodes": [_node()],
        "support": [_support()],
        "qualification_ids": ["qual-1"] if stage == "release" else [],
        "generated_slots": ["codex/support-evidence.json"],
    }
    value.update(updates)
    return value


def test_protocol_loads_as_immutable_single_authority() -> None:
    contract = protocol.load_protocol()
    assert contract.schema_version == 1
    assert contract.protocol_version == "1.0.0"
    assert contract.path == PROTOCOL_PATH
    assert len(contract.digest) == 64
    assert contract.limits["frontmatter_bytes"] == 64 * 1024
    assert contract.limits["wall_clock_seconds"] == 120 * 60
    assert contract.defaults["worker_count"] == 3
    with pytest.raises(TypeError):
        contract.limits["frontmatter_bytes"] = 1
    assert isinstance(
        contract.digest_domains["runtime_payload_digest"]["excludes"], tuple
    )


def test_fresh_protocol_process_uses_vendored_pyyaml() -> None:
    probe = (
        "import importlib.util,sys;"
        f"p={str(MODULE_PATH)!r};"
        "s=importlib.util.spec_from_file_location('protocol_probe',p);"
        "m=importlib.util.module_from_spec(s);"
        "sys.modules[s.name]=m;"
        "s.loader.exec_module(m);"
        "print(m.yaml.__file__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
    )
    loaded_from = Path(result.stdout.strip()).resolve()
    vendor = (SCRIPTS / "plugin_stack_adapters" / "_vendor").resolve()
    assert loaded_from.is_relative_to(vendor)


def test_protocol_contract_has_no_per_command_aliases() -> None:
    raw = PROTOCOL_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "aliases" not in data
    assert set(data["canonical_dialect"]) == {
        "nested_command",
        "plugin_root",
        "skill_or_resource_load",
        "subagent_dispatch",
        "interaction_request",
        "tool_capability",
        "claude_hook",
        "claude_presentation",
    }
    assert not any(key.startswith("lp-") for key in data["canonical_dialect"])


def test_test_candidate_spelling_is_explicit_and_one_way() -> None:
    assert protocol.schema_stage_for_cli("test-candidate") == "test_candidate"
    _assert_code(
        "PROTOCOL_VALUE_INVALID",
        lambda: protocol.schema_stage_for_cli("test_candidate"),
    )


def test_unknown_error_classification_is_private() -> None:
    contract = protocol.load_protocol()
    assert contract.reporting_class_for_error("UNKNOWN_COMMAND") == "public_bug"
    assert (
        contract.reporting_class_for_error("UNDECLARED_FUTURE_ERROR")
        == "private_security"
    )


def test_section_one_block_reason_codes_are_frozen() -> None:
    contract = protocol.load_protocol()
    expected = {
        "SKILL_COLLISION_PRECEDENCE_UNSPECIFIED",
        "HOST_NO_AUTHENTICATED_EXPLICIT_INVOCATION_PROVENANCE",
        "HOST_NO_LOSSLESS_AUTHENTICATED_ARGUMENT_TAIL",
        "HOST_NO_INTERACTION_MODE_ATTESTATION",
        "HOST_NO_DETACHED_DIGEST_ATTESTATION",
        "HOST_NO_FIRST_EXECUTABLE_VERIFICATION_CHAIN",
        "HOST_NO_PROMPT_FREE_SHELL_DENY_PROFILE",
        "HOST_NO_COMPLETE_SERIALIZED_PAYLOAD_MEDIATION",
        "HOST_NO_NON_BYPASSABLE_OPERATION_AUTHORIZATION",
        "HOST_NO_AUTHENTICATED_PROJECT_PROMPT_ADMISSION",
        "HOST_NO_PLUGIN_DURABLE_STATE_API",
        "HOST_NO_ATOMIC_RECEIPT_RESERVATION",
        "HOST_NO_AUTHORITATIVE_BUDGET_PRICING_CAP",
        "HOST_NO_AUTHENTICATED_EFFECT_REVOCATION_STATUS",
        "HOST_NO_CANCEL_FINAL_JOIN_GUARANTEE",
        "CLAUDE_MINIMUM_VERSION_UNDECLARED",
        "CODEX_MINIMUM_VERSION_UNDECLARED",
        "HOST_DESKTOP_RUNTIME_CONFORMANCE_UNAVAILABLE",
        "WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN",
    }
    assert expected.issubset(contract.errors)


def test_protocol_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    raw = PROTOCOL_PATH.read_text(encoding="utf-8")
    duplicate = raw.replace(
        '"schema_version": 1,',
        '"schema_version": 1,\n  "schema_version": 1,',
        1,
    )
    candidate = tmp_path / "duplicate.json"
    candidate.write_text(duplicate, encoding="utf-8")
    _assert_code("PROTOCOL_FILE_INVALID", lambda: protocol.load_protocol(candidate))


def test_protocol_rejects_unknown_root_field(tmp_path: Path) -> None:
    data = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    data["unknown"] = True
    candidate = tmp_path / "unknown.json"
    candidate.write_text(json.dumps(data), encoding="utf-8")
    _assert_code("PROTOCOL_UNKNOWN_FIELD", lambda: protocol.load_protocol(candidate))


def test_cross_limit_inequalities_are_frozen() -> None:
    contract = protocol.load_protocol()
    limits = contract.limits
    assert (
        limits["cooperative_cancel_seconds"] + limits["final_cancel_join_seconds"]
        == limits["cancellation_drain_seconds"]
    )
    assert (
        limits["deadline_cancellation_seconds"]
        <= limits["wall_clock_seconds"] - limits["cancellation_drain_seconds"]
    )
    assert (
        limits["child_timeout_seconds"]
        + limits["retry_backoff_seconds"]
        + limits["cancellation_drain_seconds"]
        <= limits["wave_timeout_seconds"]
    )
    assert limits["mutation_receipt_bytes_per_run"] <= limits["adapter_storage_bytes"]
    assert contract.duration_contract == {
        "total_includes_retry_backoff": True,
        "total_includes_cancellation_drain": True,
    }


@pytest.mark.parametrize("limit_name", sorted(protocol.load_protocol().limits))
def test_every_protocol_maximum_accepts_limit_and_rejects_plus_one(
    limit_name: str,
) -> None:
    value = protocol.load_protocol().limits[limit_name]
    assert protocol.enforce_limit(limit_name, value) == value
    _assert_code(
        "LIMIT_EXCEEDED",
        lambda: protocol.enforce_limit(limit_name, value + 1),
    )


@pytest.mark.parametrize("minimum_name", sorted(protocol.load_protocol().minimums))
def test_every_protocol_minimum_accepts_limit_and_rejects_minus_one(
    minimum_name: str,
) -> None:
    value = protocol.load_protocol().minimums[minimum_name]
    assert protocol.enforce_minimum(minimum_name, value) == value
    _assert_code(
        "LIMIT_EXCEEDED",
        lambda: protocol.enforce_minimum(minimum_name, value - 1),
    )


def test_dependency_free_token_estimate_is_utf8_byte_length() -> None:
    assert protocol.estimate_input_tokens("") == 0
    assert protocol.estimate_input_tokens("é") == 2
    assert protocol.estimate_input_tokens(b"\x00\xff") == 2


def test_valid_fixture_normalizes_to_typed_immutable_records() -> None:
    raw = FIXTURES.joinpath("valid.yaml").read_bytes()
    document = b"---\n" + raw + b"---\n# Body\n"
    metadata, body = protocol.normalize_document_metadata(document)
    assert metadata.component_kind == "command"
    assert metadata.direct.skills == ("lp-probe-explicit",)
    assert metadata.direct.scripts == ("scripts/probe.py",)
    assert metadata.capabilities.required == ("canonical_resource_read",)
    assert metadata.capabilities.tool_profile == "read_only"
    assert body == b"# Body\n"


@pytest.mark.parametrize(
    ("fixture", "code"),
    [
        ("duplicate-key.yaml", "YAML_DUPLICATE_KEY"),
        ("anchor.yaml", "YAML_ANCHOR_FORBIDDEN"),
        ("alias.yaml", "YAML_ALIAS_FORBIDDEN"),
        ("merge-key.yaml", "YAML_MERGE_KEY_FORBIDDEN"),
        ("explicit-tag.yaml", "YAML_EXPLICIT_TAG_FORBIDDEN"),
        ("multi-document.yaml", "YAML_MULTIDOC_FORBIDDEN"),
    ],
)
def test_adversarial_yaml_fixture_is_rejected(fixture: str, code: str) -> None:
    source = FIXTURES.joinpath(fixture).read_bytes()
    _assert_code(code, lambda: protocol.strict_load_yaml(source))


def test_unknown_frontmatter_field_is_rejected() -> None:
    raw = FIXTURES.joinpath("unknown-field.yaml").read_bytes()
    document = b"---\n" + raw + b"---\nbody\n"
    _assert_code(
        "METADATA_UNKNOWN_FIELD",
        lambda: protocol.normalize_document_metadata(document),
    )


def test_invalid_utf8_and_malformed_yaml_are_private() -> None:
    for source in (b"value: \xff", b"value: [unterminated"):
        with pytest.raises(protocol.ProtocolValidationError) as raised:
            protocol.strict_load_yaml(source)
        assert raised.value.reporting_class == "private_security"


@pytest.mark.parametrize(
    "source",
    [
        "value: 2026-09-08\n",
        "value: .nan\n",
        "value:\n  1: nested-non-string-key\n",
    ],
)
def test_yaml_rejects_non_json_constructed_values(source: str) -> None:
    _assert_code("METADATA_INVALID", lambda: protocol.strict_load_yaml(source))


def test_yaml_source_limit_and_plus_one() -> None:
    limit = protocol.load_protocol().limits["frontmatter_bytes"]
    prefix = b"description: "
    exact = prefix + b"x" * (limit - len(prefix))
    assert protocol.strict_load_yaml(exact)["description"]
    _assert_code(
        "YAML_SOURCE_TOO_LARGE",
        lambda: protocol.strict_load_yaml(exact + b"x"),
    )


def test_yaml_scalar_limit_and_plus_one() -> None:
    limit = protocol.load_protocol().limits["yaml_scalar_bytes"]
    exact = b"value: " + b"x" * limit
    loaded = protocol.strict_load_yaml(exact, source_limit="yaml_aggregate_bytes")
    assert len(loaded["value"]) == limit
    _assert_code(
        "YAML_SCALAR_LIMIT_EXCEEDED",
        lambda: protocol.strict_load_yaml(
            exact + b"x", source_limit="yaml_aggregate_bytes"
        ),
    )


def test_yaml_node_limit_and_plus_one() -> None:
    limit = protocol.load_protocol().limits["yaml_nodes"]
    item_count = limit - 3  # root mapping, key scalar, and sequence node
    exact = "items:\n" + "".join("  - x\n" for _ in range(item_count))
    assert len(protocol.strict_load_yaml(exact)["items"]) == item_count
    too_many = exact + "  - x\n"
    _assert_code(
        "YAML_NODE_LIMIT_EXCEEDED",
        lambda: protocol.strict_load_yaml(too_many),
    )


def test_yaml_depth_limit_and_plus_one() -> None:
    limit = protocol.load_protocol().limits["yaml_depth"]
    exact = "- " * (limit - 2) + "x\n"
    assert protocol.strict_load_yaml("value:\n  " + exact)["value"]
    too_deep = "- " * (limit - 1) + "x\n"
    _assert_code(
        "YAML_DEPTH_LIMIT_EXCEEDED",
        lambda: protocol.strict_load_yaml("value:\n  " + too_deep),
    )


def test_constructed_yaml_aggregate_limit_and_plus_one() -> None:
    limit = protocol.load_protocol().limits["yaml_aggregate_bytes"]
    assert protocol.validate_constructed_yaml_size("x" * limit) == limit
    _assert_code(
        "YAML_AGGREGATE_LIMIT_EXCEEDED",
        lambda: protocol.validate_constructed_yaml_size("x" * (limit + 1)),
    )


def test_frontmatter_and_body_limits_and_plus_one() -> None:
    limits = protocol.load_protocol().limits
    prefix = b"description: "
    frontmatter = prefix + b"x" * (limits["frontmatter_bytes"] - len(prefix))
    body = b"x" * limits["body_bytes"]
    parsed, parsed_body = protocol.extract_frontmatter(
        b"---\n" + frontmatter + b"\n---\n" + body
    )
    assert parsed["description"]
    assert parsed_body == body
    _assert_code(
        "FRONTMATTER_TOO_LARGE",
        lambda: protocol.extract_frontmatter(b"---\n" + frontmatter + b"x\n---\n"),
    )
    _assert_code(
        "BODY_TOO_LARGE",
        lambda: protocol.extract_frontmatter(
            b"---\nname: lp-probe\n---\n" + body + b"x"
        ),
    )


def test_direct_edge_limit_and_plus_one() -> None:
    limit = protocol.load_protocol().limits["direct_edges_per_definition"]
    exact = [f"lp-edge-{index}" for index in range(limit)]
    normalized = protocol.normalize_metadata(_metadata(direct={"commands": exact}))
    assert normalized.direct.count == limit
    _assert_code(
        "METADATA_EDGE_LIMIT_EXCEEDED",
        lambda: protocol.normalize_metadata(
            _metadata(direct={"commands": exact + ["lp-edge-overflow"]})
        ),
    )


def test_bounded_loop_limit_and_plus_one() -> None:
    limit = protocol.load_protocol().limits["bounded_loop_iterations"]
    normalized = protocol.normalize_metadata(
        _metadata(
            **{
                "bounded-loop": {
                    "max-iterations": limit,
                    "reentry-command": "lp-loop",
                }
            }
        )
    )
    assert normalized.bounded_loop is not None
    assert normalized.bounded_loop.max_iterations == limit
    _assert_code(
        "METADATA_INVALID",
        lambda: protocol.normalize_metadata(
            _metadata(
                **{
                    "bounded-loop": {
                        "max-iterations": limit + 1,
                        "reentry-command": "lp-loop",
                    }
                }
            )
        ),
    )


def test_metadata_rejects_unknown_capability_and_invalid_effect_combinations() -> None:
    _assert_code(
        "METADATA_INVALID",
        lambda: protocol.normalize_metadata(
            _metadata(
                capabilities={
                    "required": ["made_up_capability"],
                    "mutation": "none",
                    "interaction": "none",
                }
            )
        ),
    )
    _assert_code(
        "METADATA_INVALID",
        lambda: protocol.normalize_metadata(
            _metadata(
                capabilities={
                    "mutation": "project_files",
                    "interaction": "none",
                    "tool-profile": "read_only",
                }
            )
        ),
    )
    _assert_code(
        "METADATA_INVALID",
        lambda: protocol.normalize_metadata(
            _metadata(
                capabilities={
                    "mutation": "none",
                    "interaction": "none",
                    "external-data-egress": True,
                }
            )
        ),
    )


def test_node_support_qualification_and_digest_records_normalize() -> None:
    node = protocol.normalize_node_record(_node())
    assert node.id == "lp-alpha"
    support = protocol.normalize_support_record(
        _support(
            base_support_state="blocked",
            blocked_reason_codes=["CAPABILITY_BLOCKED"],
            fallback="inspect_only",
        )
    )
    assert support.base_support_state == "blocked"
    availability = protocol.normalize_availability_record(
        {
            "resource_id": "lp-alpha",
            "applicability": "applicable",
            "effective_availability": "blocked",
            "reason_codes": ["HOST_NO_PROMPT_FREE_SHELL_DENY_PROFILE"],
        }
    )
    assert availability.effective_availability == "blocked"
    qualification = protocol.normalize_qualification_record(
        {
            "qualification_id": "qual-1",
            "runtime_payload_digest": "d" * 64,
            "host": "codex-cli",
            "operating_system": "darwin",
            "tool_versions": {"codex": "0.153.4"},
            "receipt_ids": ["receipt-1"],
        }
    )
    assert qualification.tool_versions["codex"] == "0.153.4"
    digests = protocol.normalize_digest_record(
        {
            "runtime_payload_digest": "a" * 64,
            "evidence_digest": "b" * 64,
            "artifact_digest": "c" * 64,
        }
    )
    assert digests.artifact_digest == "c" * 64


@pytest.mark.parametrize("stage", ["inventory", "test_candidate", "release"])
def test_all_runtime_stages_normalize(stage: str) -> None:
    record = protocol.normalize_runtime_record(_runtime(stage))
    assert record.stage == stage
    assert record.release_stage == "dogfood"


def test_runtime_stage_rules_fail_closed() -> None:
    _assert_code(
        "RECORD_STAGE_INVALID",
        lambda: protocol.normalize_runtime_record(
            _runtime("inventory", runtime_payload_digest="d" * 64)
        ),
    )
    _assert_code(
        "RECORD_STAGE_INVALID",
        lambda: protocol.normalize_runtime_record(
            _runtime("release", qualification_ids=[])
        ),
    )
    candidate = _runtime("test_candidate")
    candidate["expanded_reachability"] = ["forbidden"]
    _assert_code(
        "RECORD_INVALID",
        lambda: protocol.normalize_runtime_record(candidate),
    )


def test_runtime_records_require_sorted_unique_nodes() -> None:
    _assert_code(
        "RECORD_INVALID",
        lambda: protocol.normalize_runtime_record(
            _runtime(
                nodes=[_node("lp-zulu"), _node("lp-alpha")],
                root_ids=["lp-alpha"],
                support=[_support("lp-alpha")],
            )
        ),
    )


def test_duplicate_protocol_constant_detector(tmp_path: Path) -> None:
    duplicate = tmp_path / "plugin-codex-fake.py"
    duplicate.write_text("WALL_CLOCK_SECONDS = 7200\n", encoding="utf-8")
    findings = protocol.detect_duplicate_protocol_constants([duplicate])
    assert len(findings) == 1
    assert "WALL_CLOCK_SECONDS" in findings[0]


def test_no_downstream_codex_component_reowns_protocol_constants() -> None:
    downstream = sorted(
        path for path in SCRIPTS.glob("plugin-codex-*.py") if path != MODULE_PATH
    )
    assert protocol.detect_duplicate_protocol_constants(downstream) == ()
