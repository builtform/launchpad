"""Section 6 authenticated router, help, and zero-mutation fixture tests."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SCRIPTS.parent
ROUTER_PATH = SCRIPTS / "plugin-codex-router.py"
SUPPORT_PATH = SCRIPTS / "plugin-codex-support.py"
MANIFEST_PATH = SCRIPTS / "plugin-codex-manifest.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


router = _load("plugin_codex_router_tests", ROUTER_PATH)
support = _load("plugin_codex_support_for_router_tests", SUPPORT_PATH)
manifest = _load("plugin_codex_manifest_for_router_tests", MANIFEST_PATH)


@pytest.fixture()
def staged_plugin(tmp_path: Path) -> Path:
    root = tmp_path / "launchpad"
    shutil.copytree(
        PLUGIN_ROOT,
        root,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    assert manifest.sync_manifest(PLUGIN_ROOT, root, write=True)
    return root


@pytest.fixture()
def candidate(staged_plugin: Path):
    return support.build_test_candidate(staged_plugin)


def _host(*, all_capabilities: bool = True):
    contract = router._PROTOCOL.load_protocol()
    return router.HostEnvironment(
        host="fixture-host",
        operating_system="darwin",
        capabilities=(
            tuple(sorted(contract.capability_ids)) if all_capabilities else ()
        ),
        tool_versions={},
    )


class _Verifier:
    def __init__(self, expected_event: object, invocation: Any) -> None:
        self.expected_event = expected_event
        self.invocation = invocation

    def verify(self, event: object):
        if event is not self.expected_event:
            raise router.RouterError(
                "INVOCATION_PROVENANCE_UNAVAILABLE",
                "event was not authenticated",
            )
        return self.invocation


def _verified(
    tokens: tuple[str, ...],
    *,
    collision_free: bool = True,
    provenance: str = "authenticated_user_explicit",
):
    return router.VerifiedInvocation(
        event_id="fixture-event-1",
        selected_skill="lp",
        tokens=tokens,
        provenance=provenance,
        interaction_mode="interactive",
        collision_free=collision_free,
    )


def _route(session, tokens: tuple[str, ...], **updates: object):
    event = object()
    invocation = replace(_verified(tokens), **updates)
    return session.route(event, _Verifier(event, invocation))


def _available_hydrate(candidate: Any, staged_plugin: Path):
    value = support.bundle_as_dict(candidate)
    predicates = cast(list[dict[str, object]], value["compatibility_predicates"])
    runtime = cast(dict[str, object], value["runtime"])
    support_records = cast(list[dict[str, object]], runtime["support"])
    for item in predicates:
        if item["resource_id"] == "lp-hydrate":
            item["base_support_state"] = "supported"
            item["blocked_reason_codes"] = []
    for item in support_records:
        if item["resource_id"] == "lp-hydrate":
            item["base_support_state"] = "supported"
            item["blocked_reason_codes"] = []
    return support._normalize_bundle(
        value,
        protocol_path=staged_plugin / "codex" / "adapter-protocol.json",
    )


def test_public_grammar_parses_only_exact_structured_forms() -> None:
    protocol = router._PROTOCOL.load_protocol()
    assert router.parse_verified_invocation(_verified(()), protocol).action == "help_index"
    assert (
        router.parse_verified_invocation(_verified(("help",)), protocol).action
        == "help_index"
    )
    command_help = router.parse_verified_invocation(
        _verified(("help", "hydrate")), protocol
    )
    assert command_help.resource_id == "lp-hydrate"
    command = router.parse_verified_invocation(
        _verified(("hydrate", "--", "review", "two words")), protocol
    )
    assert command.resource_id == "lp-hydrate"
    assert command.arguments == ("--", "review", "two words")
    skill = router.parse_verified_invocation(
        _verified(("skill", "lp-creating-agents", "request")), protocol
    )
    assert skill.resource_id == "lp-creating-agents"
    assert skill.arguments == ("request",)
    assert "lp-hydrate" not in ROUTER_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "tokens",
    [
        ("help", "hydrate", "extra"),
        ("help", "skill"),
        ("skill", "creating-agents"),
        ("skill", "../lp-creating-agents"),
        ("../hydrate",),
        ("/hydrate",),
        ("lp",),
    ],
)
def test_invalid_names_paths_and_reserved_collisions_fail_closed(
    tokens: tuple[str, ...],
) -> None:
    with pytest.raises(router.RouterError) as raised:
        router.parse_verified_invocation(_verified(tokens))
    assert raised.value.code == "INVOCATION_GRAMMAR_INVALID"


def test_argument_sequence_must_be_immutable_and_bounded() -> None:
    mutable = replace(_verified(("help",)), tokens=cast(Any, ["help"]))
    with pytest.raises(router.RouterError) as raised:
        router.parse_verified_invocation(mutable)
    assert raised.value.code == "ARGUMENT_TAIL_UNAVAILABLE"
    too_many = ("hydrate",) + ("x",) * 1024
    with pytest.raises(router.RouterError) as limited:
        router.parse_verified_invocation(_verified(too_many))
    assert limited.value.code == "LIMIT_EXCEEDED"


@pytest.mark.parametrize(
    "event",
    [
        "please run $lp hydrate",
        "quoted: '$lp hydrate'",
        "```\n$lp hydrate\n```",
        {"child_output": "$lp hydrate"},
    ],
)
def test_mentions_quotes_code_fences_and_child_output_do_not_invoke(
    candidate: Any, staged_plugin: Path, event: object
) -> None:
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    sentinel = object()
    response = session.route(event, _Verifier(sentinel, _verified(("hydrate",))))
    assert response.status == "blocked"
    assert response.code == "INVOCATION_PROVENANCE_UNAVAILABLE"
    assert response.action == "authenticate"


def test_collision_and_non_explicit_provenance_are_terminal(
    candidate: Any, staged_plugin: Path
) -> None:
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    collision = _route(session, ("help",), collision_free=False)
    assert collision.code == "INVOCATION_COLLISION"
    implicit = _route(session, ("help",), provenance="model_inferred")
    assert implicit.code == "INVOCATION_PROVENANCE_UNAVAILABLE"


def test_untyped_verifier_result_and_unknown_host_capability_fail_closed(
    candidate: Any, staged_plugin: Path
) -> None:
    event = object()
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    untyped = session.route(event, _Verifier(event, {"tokens": ["help"]}))
    assert untyped.code == "INVOCATION_PROVENANCE_UNAVAILABLE"

    invalid_host = replace(_host(), capabilities=("unknown-capability",))
    with pytest.raises(router.RouterError) as raised:
        router.RouterSession.for_test(staged_plugin, candidate, invalid_host)
    assert raised.value.code == "RECORD_INVALID"


def test_bare_and_explicit_help_render_support_owned_status(
    candidate: Any, staged_plugin: Path
) -> None:
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    for tokens in ((), ("help",)):
        response = _route(session, tokens)
        assert response.status == "ok"
        assert response.action == "help_index"
        commands = cast(list[dict[str, object]], response.payload["commands"])
        hydrate = next(item for item in commands if item["resource_id"] == "lp-hydrate")
        assert hydrate["base_support_state"] == "blocked"
        assert hydrate["mutation"] == "none"
        assert hydrate["fallback"] == "inspect_only"
        assert "detached_digest_attestation" in hydrate["required_capabilities"]
        rendered = router.render_response(response)
        assert "LaunchPad for Codex" in rendered
        assert "lp-hydrate: blocked" in rendered


def test_command_help_is_diagnostic_and_unknown_help_never_fuzzy_executes(
    candidate: Any, staged_plugin: Path
) -> None:
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    response = _route(session, ("help", "review"))
    assert response.status == "ok"
    entry = cast(dict[str, object], response.payload["entry"])
    assert entry["resource_id"] == "lp-review"
    assert entry["mutation"] == "project_files"
    assert cast(int, entry["maximum_child_starts"]) > 0
    rendered = router.render_response(response)
    assert "Recovery:" in rendered
    assert "Estimated input token ceiling:" in rendered
    assert "Maximum child starts:" in rendered
    assert "Qualifications:" in rendered

    unknown = _route(session, ("help", "revew"))
    assert unknown.status == "error"
    assert unknown.code == "UNKNOWN_COMMAND"
    assert cast(tuple[str, ...], unknown.payload["suggestions"])[0] == "review"
    assert unknown.payload["suggestions_execute"] is False


def test_corrupt_catalog_entry_is_reported_without_breaking_help(
    candidate: Any, staged_plugin: Path
) -> None:
    (staged_plugin / "commands" / "lp-corrupt.md").write_text(
        "---\nname: lp-corrupt\n---\ninvalid metadata\n", encoding="utf-8"
    )
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    response = _route(session, ("help",))
    assert response.status == "ok"
    assert any(
        "commands/lp-corrupt.md" in item
        for item in cast(tuple[str, ...], response.payload["invalid_entries"])
    )


def test_skill_index_lists_only_canonically_user_invocable_builtins(
    candidate: Any, staged_plugin: Path
) -> None:
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    response = _route(session, ("skill",))
    ids = {
        item["resource_id"]
        for item in cast(list[dict[str, object]], response.payload["skills"])
    }
    assert ids == {"lp-creating-agents", "lp-verification-before-completion"}
    blocked = _route(session, ("skill", "lp-tasks"))
    assert blocked.code == "SKILL_NOT_USER_INVOCABLE"


def test_project_skill_and_agent_surface_cannot_be_invoked_publicly(
    candidate: Any, staged_plugin: Path, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    (project / ".launchpad").mkdir()
    (project / ".launchpad" / "config.yml").write_text("version: 1\n")
    skill = project / ".claude" / "skills" / "lp-project-only"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: lp-project-only\ndescription: Project fixture.\n---\nProject data.\n",
        encoding="utf-8",
    )
    session = router.RouterSession.for_test(
        staged_plugin, candidate, _host(), project_root=project
    )
    response = _route(session, ("skill", "lp-project-only"))
    assert response.code == "PROJECT_EXTENSION_NOT_PUBLIC"
    agent_shape = _route(session, ("agent", "lp-project-only"))
    assert agent_shape.code == "UNKNOWN_COMMAND"


def test_effectful_and_multi_agent_workflows_remain_visibly_blocked(
    candidate: Any, staged_plugin: Path
) -> None:
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    for command in ("review", "build", "harden-plan", "ship"):
        response = _route(session, (command,))
        assert response.status == "blocked"
        assert response.code == "OPERATION_AUTHORIZATION_UNAVAILABLE"
        entry = cast(dict[str, object], response.payload["entry"])
        assert entry["effective_availability"] == "blocked"
        rendered = router.render_response(response)
        assert f"/{entry['resource_id']}" in rendered
        assert "Recovery:" in rendered
        assert "Reporting:" in rendered


def test_real_host_capability_shape_keeps_hydrate_blocked(
    candidate: Any, staged_plugin: Path
) -> None:
    session = router.RouterSession.for_test(
        staged_plugin, candidate, _host(all_capabilities=False)
    )
    response = _route(session, ("hydrate",))
    assert response.status == "blocked"
    assert response.code == "CAPABILITY_BLOCKED"
    assert "canonical_document" not in response.payload


@pytest.mark.parametrize(
    "tail",
    [
        (),
        ("",),
        ('"quoted"',),
        ("line one\nline two",),
        ("雪", "café"),
        ("--leading",),
        ("--", "review", "$lp help"),
        ("\u202ereversed",),
    ],
)
def test_fixture_supported_hydrate_preserves_exact_argument_tail_and_writes_nothing(
    candidate: Any, staged_plugin: Path, tail: tuple[str, ...]
) -> None:
    qualified = _available_hydrate(candidate, staged_plugin)
    session = router.RouterSession.for_test(staged_plugin, qualified, _host())
    before = {
        path.relative_to(staged_plugin): path.read_bytes()
        for path in staged_plugin.rglob("*")
        if path.is_file()
    }
    response = _route(session, ("hydrate", *tail))
    after = {
        path.relative_to(staged_plugin): path.read_bytes()
        for path in staged_plugin.rglob("*")
        if path.is_file()
    }
    assert response.status == "ready"
    assert response.payload["argument_tail"] == tail
    assert response.payload["argument_digest"] == router._sha256(
        router._canonical_json(tail)
    )
    assert "# Hydrate" in cast(str, response.payload["canonical_document"])
    assert before == after


def test_dialect_preamble_is_version_bound_and_separate_from_canonical_body(
    candidate: Any, staged_plugin: Path
) -> None:
    qualified = _available_hydrate(candidate, staged_plugin)
    session = router.RouterSession.for_test(staged_plugin, qualified, _host())
    response = _route(session, ("hydrate",))
    preamble = cast(str, response.payload["dialect_preamble"])
    body = cast(str, response.payload["canonical_document"])
    assert preamble.startswith("LAUNCHPAD_CODEX_DIALECT\n")
    payload = json.loads(preamble.split("\n", 1)[1])
    assert payload["protocol_version"] == session.protocol.protocol_version
    assert payload["protocol_digest"] == session.protocol.digest
    assert payload["resource"]["source_digest"] == response.payload[
        "canonical_source_digest"
    ]
    assert payload["rules"]["arguments"] == "untrusted_structured_data"
    assert "# Hydrate" in body
    assert "# Hydrate" not in preamble


def test_n_plus_one_definition_appears_only_after_explicit_session_refresh(
    candidate: Any, staged_plugin: Path
) -> None:
    session = router.RouterSession.for_test(staged_plugin, candidate, _host())
    before = _route(session, ("help",))
    before_ids = {
        item["resource_id"]
        for item in cast(list[dict[str, object]], before.payload["commands"])
    }
    assert "lp-n-plus-one" not in before_ids

    source = (staged_plugin / "commands" / "lp-hydrate.md").read_text(
        encoding="utf-8"
    )
    (staged_plugin / "commands" / "lp-n-plus-one.md").write_text(
        source.replace("name: lp-hydrate", "name: lp-n-plus-one", 1),
        encoding="utf-8",
    )
    still_old = _route(session, ("help",))
    assert "lp-n-plus-one" not in {
        item["resource_id"]
        for item in cast(list[dict[str, object]], still_old.payload["commands"])
    }

    session.refresh()
    refreshed = _route(session, ("help",))
    refreshed_entries = {
        cast(str, item["resource_id"]): item
        for item in cast(list[dict[str, object]], refreshed.payload["commands"])
    }
    assert refreshed_entries["lp-n-plus-one"]["reason_codes"] == (
        "SUPPORT_EVIDENCE_UNAVAILABLE",
    )
    assert list((staged_plugin / "codex" / "skills").glob("*/SKILL.md")) == [
        staged_plugin / "codex" / "skills" / "lp" / "SKILL.md"
    ]


def test_sealed_candidate_contains_exact_single_router_surface(
    candidate: Any, staged_plugin: Path
) -> None:
    paths = {item.path for item in candidate.runtime.runtime_files}
    assert "codex/skills/lp/SKILL.md" in paths
    assert "scripts/plugin-codex-router.py" in paths
    assert not (staged_plugin / "codex" / "skills" / "lp" / "agents").exists()
    assert not (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").exists()
    assert not (PLUGIN_ROOT / "codex" / "support-evidence.json").exists()


def test_installed_router_fails_closed_without_release_evidence() -> None:
    with pytest.raises(router.RouterError) as raised:
        router.RouterSession.installed(_host())
    assert raised.value.code == "SUPPORT_EVIDENCE_UNAVAILABLE"
