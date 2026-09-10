"""Section 9 CI tiers, surface inventory, and whole-corpus acceptance tests."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SCRIPTS.parent
REPOSITORY_ROOT = SCRIPTS.parents[2]
ACCEPTANCE_PATH = SCRIPTS / "plugin-codex-acceptance.py"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/codex-compatibility.yml"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


acceptance = _load("plugin_codex_acceptance_tests", ACCEPTANCE_PATH)


@pytest.fixture()
def staged_package(tmp_path: Path) -> tuple[Path, Any]:
    staged = tmp_path / "launchpad"
    shutil.copytree(
        PLUGIN_ROOT,
        staged,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    assert acceptance._MANIFEST.sync_manifest(PLUGIN_ROOT, staged, write=True)
    candidate = acceptance._SUPPORT.build_test_candidate(staged)
    package = tmp_path / "package"
    package.mkdir()
    acceptance._MANIFEST.project_package(
        candidate,
        staged,
        package,
        include_generated=False,
    )
    return package, candidate


def test_compatibility_workflow_covers_all_tiers_paths_and_pinned_actions() -> None:
    result = acceptance.validate_workflow()
    assert result["events"] == [
        "pull_request",
        "push",
        "schedule",
        "workflow_dispatch",
    ]
    assert result["jobs"] == [
        "hermetic-compatibility",
        "nightly-release",
        "pinned-host",
    ]
    assert result["pins"] == {
        "CLAUDE_CODE_VERSION": "2.1.258",
        "CODEX_CLI_VERSION": "0.153.4",
        "PYTHON_VERSION": "3.13",
    }
    assert result["sha_pinned_actions"] == 8


@pytest.mark.parametrize("event_name", ("pull_request", "push"))
@pytest.mark.parametrize("protected_path", sorted(acceptance._REQUIRED_PROTECTED_PATHS))
def test_trigger_meta_gate_rejects_each_missing_protected_path(
    event_name: str,
    protected_path: str,
    tmp_path: Path,
) -> None:
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    line = f'      - "{protected_path}"\n'
    assert source.count(line) == 2
    index = source.index(line) if event_name == "pull_request" else source.rindex(line)
    candidate = tmp_path / "workflow.yml"
    candidate.write_text(
        source[:index] + source[index + len(line) :],
        encoding="utf-8",
    )
    with pytest.raises(acceptance.AcceptanceError) as raised:
        acceptance.validate_workflow(candidate)
    assert raised.value.code == "CI_TRIGGER_INCOMPLETE"


def test_workflow_rejects_unpinned_action_and_gate_bypass(tmp_path: Path) -> None:
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    unpinned = tmp_path / "unpinned.yml"
    unpinned.write_text(
        source.replace(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/checkout@v7",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(acceptance.AcceptanceError) as action:
        acceptance.validate_workflow(unpinned)
    assert action.value.code == "CI_ACTION_UNPINNED"

    bypass = tmp_path / "bypass.yml"
    bypass.write_text(
        source.replace(
            "    name: Hermetic", "    continue-on-error: true\n    name: Hermetic", 1
        ),
        encoding="utf-8",
    )
    with pytest.raises(acceptance.AcceptanceError) as weakened:
        acceptance.validate_workflow(bypass)
    assert weakened.value.code == "CI_TIER_INCOMPLETE"


@pytest.mark.parametrize(
    "replacement",
    (
        '        run: "# python plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py"\n',
        '        run: echo "python plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py"\n',
        '        run: \': "python plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py"\'\n',
        "        run: true || python plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py\n",
        "        run: python plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py --no-op\n",
        (
            "        if: false\n"
            "        run: python "
            "plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py\n"
        ),
        (
            "        shell: bash -n {0}\n"
            "        run: python "
            "plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py\n"
        ),
    ),
)
def test_workflow_execution_commands_cannot_be_comments_or_no_ops(
    replacement: str,
    tmp_path: Path,
) -> None:
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    required = (
        "        run: python "
        "plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py\n"
    )
    assert source.count(required) == 1
    candidate = tmp_path / "workflow.yml"
    candidate.write_text(source.replace(required, replacement), encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError) as raised:
        acceptance.validate_workflow(candidate)
    assert raised.value.code == "CI_TIER_INCOMPLETE"


@pytest.mark.parametrize(
    ("removed", "expected_code"),
    [
        ("          tests/test_plugin_codex_support.py\n", "CI_TIER_INCOMPLETE"),
        ("          --check\n", "CI_TIER_INCOMPLETE"),
        ("    needs: hermetic-compatibility\n", "CI_TIER_INCOMPLETE"),
        (
            "          python plugins/launchpad/scripts/tests/fixtures/codex_compatibility/run_conformance.py \\\n",
            "CI_TIER_INCOMPLETE",
        ),
        ("  cancel-in-progress: true\n", "CI_TIER_INCOMPLETE"),
    ],
)
def test_workflow_rejects_missing_tier_execution_or_dependency(
    removed: str,
    expected_code: str,
    tmp_path: Path,
) -> None:
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert removed in source
    candidate = tmp_path / "workflow.yml"
    candidate.write_text(source.replace(removed, "", 1), encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError) as raised:
        acceptance.validate_workflow(candidate)
    assert raised.value.code == expected_code


def test_source_surface_inventory_is_projection_only() -> None:
    inventory = acceptance.generate_surface_inventory(
        PLUGIN_ROOT, stage="qualified_source"
    )
    active = [item for item in inventory.records if item.disposition == "active"]
    source_only = [
        item for item in inventory.records if item.disposition == "source_only"
    ]
    assert active == []
    assert len(source_only) == 61
    assert sum(item.kind == "canonical_command" for item in source_only) == 43
    assert {item.kind for item in source_only} == {
        "canonical_command",
        "canonical_skill",
        "compatibility_manifest",
        "router_skill",
    }
    assert all(
        item.reason == "excluded_by_package_projection"
        for item in source_only
        if item.kind in {"canonical_command", "canonical_skill"}
    )
    assert (PLUGIN_ROOT / ".codex-plugin/plugin.json").is_file()
    assert set(inventory.confirmed_absent) == set(acceptance._CONFIRMED_ABSENT)


def test_candidate_surface_inventory_has_exactly_manifest_and_bare_lp_router(
    staged_package: tuple[Path, Any],
) -> None:
    package, candidate = staged_package
    canonical_skills = frozenset(
        node.source_path for node in candidate.runtime.nodes if node.kind == "skill"
    )
    inventory = acceptance.generate_surface_inventory(
        package,
        stage="test_candidate",
        canonical_skill_paths=canonical_skills,
    )
    assert {
        item.path for item in inventory.records if item.disposition == "active"
    } == {".codex-plugin/plugin.json", "codex/skills/lp/SKILL.md"}
    assert not list((package / "codex/skills").glob("*/agents/openai.yaml"))
    assert {
        path.relative_to(package).as_posix()
        for path in (package / "codex/skills").glob("*/SKILL.md")
    } == {"codex/skills/lp/SKILL.md"}


@pytest.mark.parametrize(
    "relative",
    [
        "plugin.json",
        "mcp.json",
        ".mcp.json",
        ".app.json",
        "hooks/hooks.json",
        "codex/skills/rogue/SKILL.md",
        "codex/skills/lp/agents/openai.yaml",
        "codex/agents/rogue.toml",
    ],
)
def test_surface_inventory_denies_every_unapproved_conventional_surface(
    staged_package: tuple[Path, Any],
    relative: str,
) -> None:
    package, candidate = staged_package
    target = package / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("fixture\n", encoding="utf-8")
    canonical_skills = frozenset(
        node.source_path for node in candidate.runtime.nodes if node.kind == "skill"
    )
    with pytest.raises(acceptance.AcceptanceError) as raised:
        acceptance.generate_surface_inventory(
            package,
            stage="test_candidate",
            canonical_skill_paths=canonical_skills,
        )
    assert raised.value.code == "UNEXPECTED_CODEX_SURFACE"


def test_whole_corpus_classification_is_complete_deterministic_and_blocked() -> None:
    report = acceptance.build_report()
    corpus = report["corpus"]
    assert corpus["nodes"] == 94
    assert corpus["commands"] == 42
    assert corpus["public_builtin_skills"] == 2
    assert corpus["classified_roots"] == 44
    assert corpus["advertised_roots"] == []
    assert corpus["advertised_capability_families"] == []
    classifications = corpus["classifications"]
    assert [item["resource_id"] for item in classifications] == sorted(
        item["resource_id"] for item in classifications
    )
    assert all(item["base_support_state"] == "blocked" for item in classifications)
    assert all(
        item["blocked_reason_codes"] == ["WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN"]
        for item in classifications
    )
    assert all(not item["qualification_ids"] for item in classifications)
    assert report["ci_acceptance"] == "pass"
    assert report["beta_release_acceptance"] == "blocked"


def test_fixed_beta_fixture_gates_do_not_promote_real_host_support() -> None:
    report = acceptance.build_report()
    fixed = report["fixed_beta_minimum"]
    assert set(fixed) == {"router_help", "zero_mutation", "harden_plan"}
    assert all(item["fixture_acceptance"] == "pass" for item in fixed.values())
    assert all(item["real_host_acceptance"] == "blocked" for item in fixed.values())
    assert fixed["router_help"]["reason_codes"] == [
        "HOST_NO_AUTHENTICATED_EXPLICIT_INVOCATION_PROVENANCE",
        "HOST_NO_LOSSLESS_AUTHENTICATED_ARGUMENT_TAIL",
    ]
    assert fixed["zero_mutation"]["resource_id"] == "lp-hydrate"
    assert fixed["harden_plan"]["resource_id"] == "lp-harden-plan"


def test_observations_are_bounded_and_never_invent_authoritative_cost() -> None:
    report = acceptance.build_report()
    observations = report["observations"]
    protocol = acceptance._PROTOCOL.load_protocol()
    assert observations["package_file_count"] > 0
    assert observations["package_bytes"] > 0
    assert observations["catalog_cold_nanoseconds"] >= 0
    assert observations["catalog_warm_nanoseconds"] >= 0
    assert observations["estimated_allocations"] == {
        "child_starts": protocol.limits["child_starts"],
        "input_tokens": protocol.limits["estimated_input_tokens"],
        "output_tokens": protocol.limits["estimated_output_tokens"],
        "outbound_bytes": protocol.limits["aggregate_outbound_bytes"],
        "wall_clock_seconds": protocol.limits["wall_clock_seconds"],
    }
    assert observations["authoritative_usage"] == {
        "available": False,
        "reason_code": "HOST_NO_AUTHORITATIVE_BUDGET_PRICING_CAP",
        "monetary_enforcement_claimed": False,
    }


def test_every_fixed_limit_and_aggregate_deadline_relationship_is_reported() -> None:
    report = acceptance.build_report()
    boundaries = report["boundaries"]
    protocol = acceptance._PROTOCOL.load_protocol()
    assert set(boundaries["fixed_limits"]) == set(protocol.limits)
    for name, item in boundaries["fixed_limits"].items():
        assert item == {
            "limit": protocol.limits[name],
            "at_limit": "PASS",
            "plus_one": "LIMIT_EXCEEDED",
        }
    assert all(boundaries["relationships"].values())


def test_support_producer_closure_limit_accepts_limit_and_rejects_plus_one() -> None:
    protocol = acceptance._PROTOCOL.load_protocol()
    limit = protocol.limits["aggregate_edges"]
    exact_node = SimpleNamespace(
        id="lp-root",
        direct=SimpleNamespace(commands=(), skills=(), agents=(), count=limit),
    )
    exact_runtime = SimpleNamespace(nodes=(exact_node,), root_ids=("lp-root",))
    assert acceptance._SUPPORT._reachable_nodes(exact_runtime, protocol) == (
        exact_node,
    )

    overflow_node = SimpleNamespace(
        id="lp-root",
        direct=SimpleNamespace(commands=(), skills=(), agents=(), count=limit + 1),
    )
    overflow_runtime = SimpleNamespace(nodes=(overflow_node,), root_ids=("lp-root",))
    with pytest.raises(acceptance._SUPPORT.SupportError) as raised:
        acceptance._SUPPORT._reachable_nodes(overflow_runtime, protocol)
    assert raised.value.code == "LIMIT_EXCEEDED"


def _router_receipt() -> dict[str, object]:
    blocked = {
        "app-server-argument-tail-binding",
        "bare-lp-authenticated-routing",
        "cli-bare-lp-binding",
        "plugin-hook-ingress",
    }
    probes = (
        "app-server-argument-tail-binding",
        "app-server-typed-skill-selection",
        "bare-lp-authenticated-routing",
        "cli-bare-lp-binding",
        "codex-version",
        "internal-plugin-discovery",
        "plugin-hook-ingress",
        "sealed-install",
    )
    return {
        "codex_home": "/private/tmp/lp-codex-router-fixture",
        "runtime_payload_digest": "a" * 64,
        "results": [
            {
                "probe": probe,
                "result": "BLOCKED" if probe in blocked else "PASS",
                "detail": "codex-cli 0.153.4" if probe == "codex-version" else probe,
            }
            for probe in probes
        ],
    }


def test_router_host_receipt_preserves_real_host_blockers(tmp_path: Path) -> None:
    path = tmp_path / "router.json"
    path.write_text(json.dumps(_router_receipt()), encoding="utf-8")
    result = acceptance.verify_router_host_receipt(
        path,
        expected_codex_version="0.153.4",
    )
    assert result["status"] == "pass"
    assert result["runtime_payload_digest"] == "a" * 64
    assert result["advertised_capability_families"] == []
    assert result["blocked_reason_codes"] == [
        "HOST_NO_AUTHENTICATED_EXPLICIT_INVOCATION_PROVENANCE",
        "HOST_NO_LOSSLESS_AUTHENTICATED_ARGUMENT_TAIL",
    ]

    changed = _router_receipt()
    changed["results"][2]["result"] = "PASS"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError) as raised:
        acceptance.verify_router_host_receipt(
            path,
            expected_codex_version="0.153.4",
        )
    assert raised.value.code == "HOST_RECEIPT_INVALID"

    normal_state = _router_receipt()
    normal_state["codex_home"] = "/Users/example/.codex"
    path.write_text(json.dumps(normal_state), encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError) as raised:
        acceptance.verify_router_host_receipt(
            path,
            expected_codex_version="0.153.4",
        )
    assert raised.value.code == "HOST_RECEIPT_INVALID"


def _lifecycle_receipt() -> dict[str, object]:
    passed = (
        "claude-current-strict-validation",
        "claude-current-validation",
        "claude-user-invocable-runtime-discovery",
        "codex-plugin-cleanup",
        "codex-plugin-install-list",
        "codex-plugin-update-disable",
        "host-versions",
        "installed-root-and-dual-manifest",
        "openai-yaml-omission",
        "typed-skill-input",
    )
    blocked = ("duplicate-skill-resolution", "enforcement-boundaries")
    return {
        "overall": "BLOCKED",
        "fixture": "/fixture",
        "codex_home": "/private/tmp/lp-codex-lifecycle-fixture",
        "results": [
            {
                "id": identifier,
                "status": "PASS",
                "detail": (
                    "codex-cli 0.153.4; 2.1.258 (Claude Code)"
                    if identifier == "host-versions"
                    else identifier
                ),
            }
            for identifier in passed
        ]
        + [
            {"id": identifier, "status": "BLOCKED", "detail": identifier}
            for identifier in blocked
        ],
    }


def test_lifecycle_receipt_keeps_coexistence_green_and_enforcement_blocked(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lifecycle.json"
    path.write_text(json.dumps(_lifecycle_receipt()), encoding="utf-8")
    result = acceptance.verify_lifecycle_host_receipt(
        path,
        expected_codex_version="0.153.4",
        expected_claude_version="2.1.258",
    )
    assert result == {
        "status": "pass",
        "codex_host": "codex-cli 0.153.4",
        "claude_host": "Claude Code 2.1.258",
        "overall_support": "blocked",
        "advertised_capability_families": [],
    }

    malformed = json.dumps(_lifecycle_receipt())[:-1] + ',"overall":"PASS"}'
    path.write_text(malformed, encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError) as raised:
        acceptance.verify_lifecycle_host_receipt(
            path,
            expected_codex_version="0.153.4",
            expected_claude_version="2.1.258",
        )
    assert raised.value.code == "RECORD_INVALID"


def test_no_public_command_uses_a_product_qualified_prefix() -> None:
    source = ACCEPTANCE_PATH.read_bytes() + WORKFLOW_PATH.read_bytes()
    assert b"$" + b"launchpad:" not in source
    assert b"$lp" not in WORKFLOW_PATH.read_bytes()
