"""Section 9 CI authority checks and whole-corpus Codex acceptance reporting.

This module consumes the protocol, support producer, and manifest projector. It
does not rederive the canonical graph or promote support. Its generated report
keeps fixture conformance separate from real-host acceptance so a passing CI
gate cannot accidentally advertise a blocked workflow.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final, NoReturn, TypedDict, cast

from atomic_io import atomic_write_replace

SCRIPT_REAL_PATH: Final = Path(os.path.realpath(__file__))
SCRIPT_DIR: Final = SCRIPT_REAL_PATH.parent
PLUGIN_ROOT: Final = SCRIPT_DIR.parent
REPOSITORY_ROOT: Final = SCRIPT_DIR.parents[2]
PROTOCOL_PATH: Final = SCRIPT_DIR / "plugin-codex-protocol.py"
SUPPORT_PATH: Final = SCRIPT_DIR / "plugin-codex-support.py"
MANIFEST_PATH: Final = SCRIPT_DIR / "plugin-codex-manifest.py"
DEFAULT_WORKFLOW_PATH: Final = (
    REPOSITORY_ROOT / ".github/workflows/codex-compatibility.yml"
)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load_module("launchpad_codex_protocol_for_acceptance", PROTOCOL_PATH)
_SUPPORT = _load_module("launchpad_codex_support_for_acceptance", SUPPORT_PATH)
_MANIFEST = _load_module("launchpad_codex_manifest_for_acceptance", MANIFEST_PATH)


class AcceptanceError(ValueError):
    """Stable Section 9 acceptance failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> NoReturn:
    raise AcceptanceError(code, message)


@dataclass(frozen=True)
class SurfaceRecord:
    """One conventionally discoverable or explicitly inert package path."""

    path: str
    kind: str
    disposition: str
    reason: str


@dataclass(frozen=True)
class SurfaceInventory:
    """Generated deny-by-default inventory for one plugin tree."""

    stage: str
    records: tuple[SurfaceRecord, ...]
    confirmed_absent: tuple[str, ...]


class ClassificationRecord(TypedDict):
    """One public root classification consumed from the support authority."""

    resource_id: str
    kind: str
    aggregate_digest: str
    direct_edge_count: int
    required_capabilities: list[str]
    base_support_state: str
    blocked_reason_codes: list[str]
    fallback: str
    qualification_ids: list[str]


_REQUIRED_PROTECTED_PATHS: Final = frozenset(
    {
        ".claude-plugin/marketplace.json",
        ".claude/hooks/**",
        ".codex/**",
        ".github/workflows/**",
        ".launchpad/agents.yml",
        ".prettierignore",
        "CHANGELOG.md",
        "README.md",
        "docs/guides/HOW_IT_WORKS.md",
        "docs/releases/**",
        "plugins/launchpad/.claude-plugin/plugin.json",
        "plugins/launchpad/.codex-plugin/plugin.json",
        "plugins/launchpad/agents/**",
        "plugins/launchpad/codex/**",
        "plugins/launchpad/commands/**",
        "plugins/launchpad/hooks/**",
        "plugins/launchpad/preflight-profiles/**",
        "plugins/launchpad/scaffolders.yml",
        "plugins/launchpad/scaffolders/**",
        "plugins/launchpad/scripts/**",
        "plugins/launchpad/scripts/plugin_default_generators/**",
        "plugins/launchpad/scripts/plugin_stack_adapters/**",
        "plugins/launchpad/skills/**",
        "plugins/launchpad/templates/**",
        "scripts/agent_hydration/**",
        "scripts/maintenance/check-repo-structure.sh",
        "scripts/maintenance/detect-structure-drift.sh",
    }
)
_REQUIRED_EVENTS: Final = frozenset(
    {"pull_request", "push", "schedule", "workflow_dispatch"}
)
_REQUIRED_JOBS: Final = frozenset(
    {"hermetic-compatibility", "pinned-host", "nightly-release"}
)
_PINNED_ACTION_RE: Final = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_IDENTIFIER_RE: Final = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_CONVENTIONAL_COMMAND_RE: Final = re.compile(r"^commands/[^/]+\.md$")
_CONVENTIONAL_SKILL_RE: Final = re.compile(r"^(?:skills|codex/skills)/[^/]+/SKILL\.md$")
_CONVENTIONAL_AGENT_RE: Final = re.compile(
    r"^(?:\.codex/agents|codex/agents|agents)/[^/]+\.toml$"
)
_OPENAI_SKILL_AGENT_RE: Final = re.compile(
    r"^(?:skills|codex/skills)/[^/]+/agents/openai\.yaml$"
)
_CONVENTIONAL_EXACT: Final = frozenset(
    {
        ".app.json",
        ".codex-plugin/plugin.json",
        ".mcp.json",
        "hooks/hooks.json",
        "mcp.json",
        "plugin.json",
    }
)
_CONFIRMED_ABSENT: Final = (
    ".app.json",
    ".codex/agents/*.toml",
    ".mcp.json",
    "agents/*.toml",
    "codex/agents/*.toml",
    "codex/skills/*/agents/openai.yaml",
    "hooks/hooks.json",
    "mcp.json",
    "plugin.json",
)
_ROUTER_HOST_BLOCKERS: Final = (
    "HOST_NO_AUTHENTICATED_EXPLICIT_INVOCATION_PROVENANCE",
    "HOST_NO_LOSSLESS_AUTHENTICATED_ARGUMENT_TAIL",
)
_HERMETIC_TESTS: Final = (
    "tests/test_codex_project_hooks.py",
    "tests/test_plugin_codex_protocol.py",
    "tests/test_plugin_codex_corpus.py",
    "tests/test_plugin_codex_resolver.py",
    "tests/test_plugin_codex_support.py",
    "tests/test_plugin_codex_manifest.py",
    "tests/test_plugin_codex_router.py",
    "tests/test_plugin_codex_coordinator.py",
    "tests/test_plugin_codex_harden_plan.py",
    "tests/test_plugin_codex_acceptance.py",
    "tests/test_plugin_codex_qualification.py",
)
_NIGHTLY_TESTS: Final = (
    "tests/test_plugin_codex_router.py",
    "tests/test_plugin_codex_coordinator.py",
    "tests/test_plugin_codex_harden_plan.py",
    "tests/test_plugin_codex_acceptance.py",
    "tests/test_plugin_codex_qualification.py",
)
_CHECKOUT_STEP: Final[Mapping[str, object]] = {
    "id": "checkout-source",
    "name": "Checkout source",
    "uses": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
    "with": {"persist-credentials": "false"},
}
_SETUP_PYTHON_STEP: Final[Mapping[str, object]] = {
    "id": "setup-python",
    "name": "Set up Python",
    "uses": "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
    "with": {
        "python-version": "${{ env.PYTHON_VERSION }}",
        "cache": "pip",
        "cache-dependency-path": "plugins/launchpad/scripts/requirements.txt",
    },
}
_SETUP_PYTHON_NO_CACHE_STEP: Final[Mapping[str, object]] = {
    "id": "setup-python",
    "name": "Set up Python",
    "uses": "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
    "with": {"python-version": "${{ env.PYTHON_VERSION }}"},
}
_SETUP_NODE_STEP: Final[Mapping[str, object]] = {
    "id": "setup-node",
    "name": "Set up Node",
    "uses": "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",
    "with": {"node-version": "22"},
}
_INSTALL_CODEX_STEP: Final[Mapping[str, object]] = {
    "id": "install-codex-cli",
    "name": "Install pinned Codex CLI",
    "run": 'npm install --global "@openai/codex@${CODEX_CLI_VERSION}"',
}
_INSTALL_PYTHON_STEP: Final[Mapping[str, object]] = {
    "id": "install-python-dependencies",
    "name": "Install hash-pinned Python dependencies",
    "run": (
        "python -m pip install --require-hashes -r "
        "plugins/launchpad/scripts/requirements.txt"
    ),
}
_ROUTER_HOST_RECEIPT_RUN: Final = "\n".join(
    (
        "set -euo pipefail",
        'probe_home="$(mktemp -d "${RUNNER_TEMP}/lp-codex-host.XXXXXX")"',
        (
            "python plugins/launchpad/scripts/tests/fixtures/"
            "codex_compatibility/run_router_smoke.py \\"
        ),
        '  --codex-home "${probe_home}" \\',
        '  | tee "${RUNNER_TEMP}/codex-router-host.json"',
        (
            "python plugins/launchpad/scripts/plugin-codex-acceptance.py "
            "verify-router-host \\"
        ),
        '  --receipt "${RUNNER_TEMP}/codex-router-host.json" \\',
        '  --codex-version "${CODEX_CLI_VERSION}"',
    )
)
_LIFECYCLE_HOST_RECEIPT_RUN: Final = "\n".join(
    (
        "set -euo pipefail",
        'probe_home="$(mktemp -d "${RUNNER_TEMP}/lp-codex-lifecycle.XXXXXX")"',
        (
            "python plugins/launchpad/scripts/tests/fixtures/"
            "codex_compatibility/run_conformance.py \\"
        ),
        '  --codex-home "${probe_home}" \\',
        '  | tee "${RUNNER_TEMP}/codex-lifecycle-host.json"',
        (
            "python plugins/launchpad/scripts/plugin-codex-acceptance.py "
            "verify-lifecycle-host \\"
        ),
        '  --receipt "${RUNNER_TEMP}/codex-lifecycle-host.json" \\',
        '  --codex-version "${CODEX_CLI_VERSION}" \\',
        '  --claude-version "${CLAUDE_CODE_VERSION}"',
    )
)
_CANDIDATE_LIFECYCLE_RECEIPT_RUN: Final = "\n".join(
    (
        "set -euo pipefail",
        'candidate_home="$(mktemp -d "${RUNNER_TEMP}/lp-codex-candidate.XXXXXX")"',
        (
            "python plugins/launchpad/scripts/tests/fixtures/"
            "codex_compatibility/run_candidate_lifecycle.py \\"
        ),
        '  --codex-home "${candidate_home}" \\',
        '  | tee "${RUNNER_TEMP}/codex-candidate-lifecycle.json"',
        (
            "python plugins/launchpad/scripts/plugin-codex-qualification.py "
            "verify-candidate-lifecycle \\"
        ),
        "  --plugin-root plugins/launchpad \\",
        '  --receipt "${RUNNER_TEMP}/codex-candidate-lifecycle.json" \\',
        '  --codex-version "${CODEX_CLI_VERSION}" \\',
        '  --claude-version "${CLAUDE_CODE_VERSION}"',
    )
)
_JOB_STEP_CONTRACTS: Final[Mapping[str, tuple[Mapping[str, object], ...]]] = {
    "hermetic-compatibility": (
        _CHECKOUT_STEP,
        _SETUP_PYTHON_STEP,
        _INSTALL_PYTHON_STEP,
        {
            "id": "run-compatibility-suite",
            "name": "Run Codex compatibility acceptance suite",
            "working-directory": "plugins/launchpad/scripts",
            "run": "python -m pytest -q " + " ".join(_HERMETIC_TESTS),
        },
        {
            "id": "generate-acceptance-report",
            "name": "Generate Section 9 acceptance report",
            "run": (
                "python plugins/launchpad/scripts/plugin-codex-acceptance.py check "
                "--workflow .github/workflows/codex-compatibility.yml "
                '--output "${RUNNER_TEMP}/codex-acceptance.json"'
            ),
        },
        {
            "id": "verify-release-evidence",
            "name": "Verify qualified release evidence",
            "run": (
                "python plugins/launchpad/scripts/plugin-codex-qualification.py "
                "check --plugin-root plugins/launchpad --evidence "
                "plugins/launchpad/codex/support-evidence.json"
            ),
        },
        {
            "id": "verify-generated-documentation",
            "name": "Verify generated Codex documentation",
            "run": (
                "python plugins/launchpad/scripts/plugin-codex-support.py "
                "render-docs --check --evidence "
                "plugins/launchpad/codex/support-evidence.json --docs-root ."
            ),
        },
        {
            "id": "verify-action-sha-pins",
            "name": "Verify workflow action SHA pins",
            "run": "python plugins/launchpad/scripts/plugin-workflow-sha-pin-check.py",
        },
    ),
    "pinned-host": (
        _CHECKOUT_STEP,
        _SETUP_PYTHON_NO_CACHE_STEP,
        _SETUP_NODE_STEP,
        _INSTALL_CODEX_STEP,
        {
            "id": "verify-router-host-receipt",
            "name": "Run isolated bare lp host smoke",
            "run": _ROUTER_HOST_RECEIPT_RUN,
        },
    ),
    "nightly-release": (
        _CHECKOUT_STEP,
        _SETUP_PYTHON_STEP,
        _SETUP_NODE_STEP,
        _INSTALL_CODEX_STEP,
        {
            "id": "install-claude-code",
            "name": "Install pinned Claude Code CLI",
            "run": (
                'npm install --global "@anthropic-ai/claude-code@'
                '${CLAUDE_CODE_VERSION}"'
            ),
        },
        _INSTALL_PYTHON_STEP,
        {
            "id": "run-workflow-family-suite",
            "name": "Re-run workflow-family cancellation and boundary tests",
            "working-directory": "plugins/launchpad/scripts",
            "run": "python -m pytest -q " + " ".join(_NIGHTLY_TESTS),
        },
        {
            "id": "verify-lifecycle-host-receipt",
            "name": "Run isolated lifecycle and Claude coexistence probe",
            "run": _LIFECYCLE_HOST_RECEIPT_RUN,
        },
        {
            "id": "verify-candidate-lifecycle-receipt",
            "name": "Run exact candidate lifecycle and coexistence probe",
            "run": _CANDIDATE_LIFECYCLE_RECEIPT_RUN,
        },
    ),
}
_JOB_METADATA_CONTRACTS: Final[Mapping[str, Mapping[str, object]]] = {
    "hermetic-compatibility": {
        "name": "Hermetic compatibility and whole corpus",
        "runs-on": "ubuntu-24.04",
        "timeout-minutes": "30",
    },
    "pinned-host": {
        "name": "Pinned Codex host smoke",
        "needs": "hermetic-compatibility",
        "runs-on": "macos-15",
        "timeout-minutes": "25",
    },
    "nightly-release": {
        "name": "Nightly and release workflow families",
        "if": (
            "github.event_name == 'schedule' || "
            "github.event_name == 'workflow_dispatch' || "
            "startsWith(github.ref, 'refs/tags/')"
        ),
        "needs": ["hermetic-compatibility", "pinned-host"],
        "runs-on": "macos-15",
        "timeout-minutes": "45",
    },
}
_WORKFLOW_ENV_CONTRACT: Final[Mapping[str, object]] = {
    "CLAUDE_CODE_VERSION": "2.1.258",
    "CODEX_CLI_VERSION": "0.153.4",
    "PYTHON_VERSION": "3.13",
}


class _DuplicateKey(ValueError):
    pass


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant: {value}")


def _strict_json(raw: bytes, *, maximum: int) -> object:
    if len(raw) > maximum:
        _fail("LIMIT_EXCEEDED", "JSON input exceeds its fixed bound")
    try:
        return json.loads(
            raw,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKey, ValueError):
        _fail("RECORD_INVALID", "input is not strict finite JSON")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _workflow_mapping_constructor(loader: Any, node: Any) -> dict[str, object]:
    result: dict[str, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if not isinstance(key, str) or key in result:
            raise _DuplicateKey(str(key))
        result[key] = loader.construct_object(value_node, deep=False)
    return result


def _load_workflow(path: Path) -> Mapping[str, object]:
    protocol = _PROTOCOL.load_protocol()
    raw = path.read_bytes()
    if len(raw) > protocol.limits["documentation_file_bytes"]:
        _fail("LIMIT_EXCEEDED", "compatibility workflow exceeds its fixed bound")
    yaml = _PROTOCOL.yaml

    class WorkflowLoader(yaml.BaseLoader):
        pass

    WorkflowLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _workflow_mapping_constructor,
    )
    try:
        value = yaml.load(raw, Loader=WorkflowLoader)
    except (yaml.YAMLError, _DuplicateKey, UnicodeDecodeError) as exc:
        _fail("RECORD_INVALID", f"compatibility workflow is invalid: {exc}")
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _fail("RECORD_INVALID", "compatibility workflow must be a mapping")
    return value


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _fail("RECORD_INVALID", f"workflow field {field} must be a mapping")
    return value


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail("RECORD_INVALID", f"workflow field {field} must be a string list")
    if len(value) != len(set(value)):
        _fail("RECORD_INVALID", f"workflow field {field} contains duplicates")
    return tuple(value)


def _collect_uses(value: object) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "uses":
                if not isinstance(item, str):
                    _fail("RECORD_INVALID", "workflow uses values must be strings")
                found.append(item)
            found.extend(_collect_uses(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_collect_uses(item))
    return tuple(found)


def _validate_job_contract(job: Mapping[str, object], job_id: str) -> None:
    """Require one closed job shape and its complete ordered step contracts."""

    metadata = _JOB_METADATA_CONTRACTS[job_id]
    expected_fields = {*metadata, "steps"}
    if set(job) != expected_fields:
        _fail("CI_TIER_INCOMPLETE", f"{job_id} job fields differ")
    if any(job.get(key) != expected for key, expected in metadata.items()):
        _fail("CI_TIER_INCOMPLETE", f"{job_id} job metadata differs")

    steps = job.get("steps")
    if not isinstance(steps, list) or any(
        not isinstance(step, Mapping) for step in steps
    ):
        _fail("RECORD_INVALID", f"{job_id} steps must be a list of mappings")
    expected_steps = _JOB_STEP_CONTRACTS[job_id]
    expected_ids = tuple(step["id"] for step in expected_steps)
    actual_ids = tuple(step.get("id") for step in steps)
    if actual_ids != expected_ids:
        _fail(
            "CI_TIER_INCOMPLETE",
            f"{job_id} ordered step IDs differ: {actual_ids}",
        )
    for step, expected in zip(steps, expected_steps, strict=True):
        if step != expected:
            _fail(
                "CI_TIER_INCOMPLETE",
                f"{job_id} step contract differs: {expected['id']}",
            )


def validate_workflow(path: Path = DEFAULT_WORKFLOW_PATH) -> dict[str, object]:
    """Validate trigger completeness, pinned actions, and the three CI tiers."""

    value = _load_workflow(path)
    if set(value) != {"name", "on", "permissions", "env", "concurrency", "jobs"}:
        _fail("CI_TIER_INCOMPLETE", "workflow top-level fields differ")
    if value.get("name") != "Codex compatibility":
        _fail("CI_TIER_INCOMPLETE", "workflow name differs")
    uses = _collect_uses(value)
    unpinned = sorted(item for item in uses if not _PINNED_ACTION_RE.fullmatch(item))
    if unpinned:
        _fail("CI_ACTION_UNPINNED", f"workflow actions are not SHA-pinned: {unpinned}")
    events = _mapping(value.get("on"), "on")
    if set(events) != _REQUIRED_EVENTS:
        _fail("CI_TRIGGER_INCOMPLETE", "workflow event fields differ")
    pull_request = _mapping(events["pull_request"], "on.pull_request")
    push = _mapping(events["push"], "on.push")
    if set(pull_request) != {"branches", "paths"} or set(push) != {
        "branches",
        "paths",
        "tags",
    }:
        _fail("CI_TRIGGER_INCOMPLETE", "push or pull request fields differ")
    if _string_list(pull_request.get("branches"), "on.pull_request.branches") != (
        "main",
    ) or _string_list(push.get("branches"), "on.push.branches") != ("main",):
        _fail("CI_TRIGGER_INCOMPLETE", "main branch triggers differ")
    if _string_list(push.get("tags"), "on.push.tags") != ("v*.*.*",):
        _fail("CI_TRIGGER_INCOMPLETE", "release tag trigger differs")
    for event_name, event in (("pull_request", pull_request), ("push", push)):
        paths = frozenset(_string_list(event.get("paths"), f"on.{event_name}.paths"))
        if paths != _REQUIRED_PROTECTED_PATHS:
            _fail("CI_TRIGGER_INCOMPLETE", f"{event_name} protected paths differ")
    if events["schedule"] != [{"cron": "23 5 * * *"}]:
        _fail("CI_TRIGGER_INCOMPLETE", "nightly schedule differs")
    if events["workflow_dispatch"] != "":
        _fail("CI_TRIGGER_INCOMPLETE", "workflow dispatch contract differs")

    jobs = _mapping(value.get("jobs"), "jobs")
    if set(jobs) != _REQUIRED_JOBS:
        _fail("CI_TIER_INCOMPLETE", "compatibility job fields differ")
    for job_id in _JOB_STEP_CONTRACTS:
        job = _mapping(jobs[job_id], f"jobs.{job_id}")
        _validate_job_contract(job, job_id)

    concurrency = _mapping(value.get("concurrency"), "concurrency")
    if concurrency != {
        "group": "codex-compatibility-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "true",
    }:
        _fail("CI_TIER_INCOMPLETE", "workflow concurrency contract differs")

    environment = _mapping(value.get("env"), "env")
    if environment != _WORKFLOW_ENV_CONTRACT:
        _fail("CI_TIER_INCOMPLETE", "workflow environment contract differs")
    if value.get("permissions") != {}:
        _fail("CI_TIER_INCOMPLETE", "workflow top-level permissions must be empty")
    serialized = _canonical_json(value)
    forbidden = (b"continue-on-error", b"$" + b"launchpad:")
    if any(item in serialized for item in forbidden):
        _fail("CI_TIER_INCOMPLETE", "workflow weakens a gate or exposes invalid syntax")
    return {
        "events": sorted(_REQUIRED_EVENTS),
        "jobs": sorted(_REQUIRED_JOBS),
        "protected_paths": sorted(_REQUIRED_PROTECTED_PATHS),
        "pins": {key: environment[key] for key in sorted(environment)},
        "sha_pinned_actions": len(uses),
    }


def _walk_regular_files(root: Path) -> tuple[str, ...]:
    root = root.resolve(strict=True)
    paths: list[str] = []
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*directories, *files):
            info = (current_path / name).lstat()
            if stat.S_ISLNK(info.st_mode):
                _fail("PATH_SYMLINK", "surface inventory rejects symlinks")
        for name in files:
            paths.append((current_path / name).relative_to(root).as_posix())
    return tuple(sorted(paths))


def _is_conventional_surface(path: str) -> bool:
    return bool(
        path in _CONVENTIONAL_EXACT
        or _CONVENTIONAL_COMMAND_RE.fullmatch(path)
        or _CONVENTIONAL_SKILL_RE.fullmatch(path)
        or _CONVENTIONAL_AGENT_RE.fullmatch(path)
        or _OPENAI_SKILL_AGENT_RE.fullmatch(path)
    )


def _load_manifest_skills(root: Path) -> str | None:
    path = root / ".codex-plugin/plugin.json"
    if not path.exists():
        return None
    value = _strict_json(
        path.read_bytes(),
        maximum=_PROTOCOL.load_protocol().limits["documentation_file_bytes"],
    )
    if not isinstance(value, Mapping):
        _fail("RECORD_INVALID", "Codex compatibility manifest must be an object")
    skills = value.get("skills")
    if not isinstance(skills, str):
        _fail("RECORD_INVALID", "Codex compatibility manifest needs a skills path")
    return skills


def generate_surface_inventory(
    root: Path,
    *,
    stage: str,
    canonical_skill_paths: frozenset[str] | None = None,
) -> SurfaceInventory:
    """Generate a closed surface inventory and reject anything not allowlisted."""

    if stage not in {"source", "qualified_source", "test_candidate", "release"}:
        _fail("RECORD_INVALID", "surface stage is invalid")
    files = _walk_regular_files(root)
    manifest_skills = _load_manifest_skills(root)
    entry = _PROTOCOL.load_protocol(root / "codex" / "adapter-protocol.json").router[
        "entry_skill"
    ]
    if not isinstance(entry, str) or not _IDENTIFIER_RE.fullmatch(entry):
        _fail("PROTOCOL_FILE_INVALID", "router entry skill is invalid")
    router_path = f"codex/skills/{entry}/SKILL.md"
    if canonical_skill_paths is None:
        canonical_skill_paths = (
            frozenset(
                node.source_path
                for node in _SUPPORT.build_inventory(root).runtime.nodes
                if node.kind == "skill"
            )
            if stage in {"source", "qualified_source"}
            else frozenset()
        )
    records: list[SurfaceRecord] = []
    for path in files:
        if not _is_conventional_surface(path):
            continue
        if path == ".codex-plugin/plugin.json":
            if stage == "source":
                _fail("UNEXPECTED_CODEX_SURFACE", "production manifest appeared early")
            if stage == "qualified_source":
                records.append(
                    SurfaceRecord(
                        path,
                        "compatibility_manifest",
                        "source_only",
                        "package_projection_source",
                    )
                )
                continue
            reason = "qualified_release" if stage == "release" else "staged_only"
            records.append(
                SurfaceRecord(path, "compatibility_manifest", "active", reason)
            )
        elif path == router_path:
            disposition = (
                "source_only" if stage in {"source", "qualified_source"} else "active"
            )
            records.append(
                SurfaceRecord(path, "router_skill", disposition, "single_public_entry")
            )
        elif _CONVENTIONAL_COMMAND_RE.fullmatch(path):
            if stage not in {"source", "qualified_source"}:
                _fail(
                    "UNEXPECTED_CODEX_SURFACE",
                    f"canonical command escaped package projection: {path}",
                )
            records.append(
                SurfaceRecord(
                    path,
                    "canonical_command",
                    "source_only",
                    "excluded_by_package_projection",
                )
            )
        elif path in canonical_skill_paths and path.startswith("skills/"):
            records.append(
                SurfaceRecord(
                    path,
                    "canonical_skill",
                    "source_only",
                    "excluded_by_package_projection",
                )
            )
        else:
            _fail("UNEXPECTED_CODEX_SURFACE", f"unapproved Codex surface: {path}")

    if stage == "source":
        if manifest_skills is not None:
            _fail("UNEXPECTED_CODEX_SURFACE", "source tree has a production manifest")
    elif manifest_skills != "./codex/skills/":
        _fail(
            "UNEXPECTED_CODEX_SURFACE", "candidate skill discovery is not router-only"
        )
    active = {item.path for item in records if item.disposition == "active"}
    expected_active = (
        set()
        if stage in {"source", "qualified_source"}
        else {
            ".codex-plugin/plugin.json",
            router_path,
        }
    )
    if active != expected_active:
        _fail("UNEXPECTED_CODEX_SURFACE", "active surface set differs")
    absent = tuple(
        pattern
        for pattern in _CONFIRMED_ABSENT
        if not any(
            (
                path == pattern
                if "*" not in pattern
                else PurePosixPath(path).match(pattern)
            )
            for path in files
            if path != ".codex-plugin/plugin.json"
        )
    )
    if set(absent) != set(_CONFIRMED_ABSENT):
        _fail("UNEXPECTED_CODEX_SURFACE", "a deny-by-default surface is present")
    return SurfaceInventory(
        stage, tuple(sorted(records, key=lambda item: item.path)), absent
    )


def _classification_records(bundle: Any) -> tuple[ClassificationRecord, ...]:
    nodes = {node.id: node for node in bundle.runtime.nodes}
    predicates = {item.resource_id: item for item in bundle.compatibility_predicates}
    support = {item.resource_id: item for item in bundle.runtime.support}
    root_ids = tuple(bundle.runtime.root_ids)
    if set(root_ids) != set(predicates) or set(root_ids) != set(support):
        _fail("CORPUS_CLASSIFICATION_INCOMPLETE", "a public root lacks classification")
    records: list[ClassificationRecord] = []
    for resource_id in root_ids:
        node = nodes.get(resource_id)
        predicate = predicates[resource_id]
        support_record = support[resource_id]
        if node is None:
            _fail("CORPUS_CLASSIFICATION_INCOMPLETE", "classified root is absent")
        if (
            support_record.base_support_state != predicate.base_support_state
            or support_record.blocked_reason_codes != predicate.blocked_reason_codes
            or support_record.fallback != predicate.fallback
        ):
            _fail("CORPUS_CLASSIFICATION_INCOMPLETE", "support authorities disagree")
        records.append(
            {
                "resource_id": resource_id,
                "kind": node.kind,
                "aggregate_digest": node.aggregate_digest,
                "direct_edge_count": node.direct.count,
                "required_capabilities": list(predicate.required_capabilities),
                "base_support_state": predicate.base_support_state,
                "blocked_reason_codes": list(predicate.blocked_reason_codes),
                "fallback": predicate.fallback,
                "qualification_ids": list(predicate.qualification_ids),
            }
        )
    return tuple(records)


def _boundary_observations(protocol: Any) -> dict[str, object]:
    checks: dict[str, dict[str, object]] = {}
    for name in sorted(protocol.limits):
        limit = protocol.limits[name]
        _PROTOCOL.enforce_limit(name, limit, protocol)
        code: str | None = None
        try:
            _PROTOCOL.enforce_limit(name, limit + 1, protocol)
        except _PROTOCOL.ProtocolValidationError as exc:
            code = exc.code
        if code != "LIMIT_EXCEEDED":
            _fail("LIMIT_EXCEEDED", f"limit boundary is not closed: {name}")
        checks[name] = {"limit": limit, "at_limit": "PASS", "plus_one": code}
    limits = protocol.limits
    relationships = {
        "cancel_drain_is_complete": (
            limits["cooperative_cancel_seconds"] + limits["final_cancel_join_seconds"]
            == limits["cancellation_drain_seconds"]
        ),
        "deadline_leaves_cancel_drain": (
            limits["deadline_cancellation_seconds"]
            <= limits["wall_clock_seconds"] - limits["cancellation_drain_seconds"]
        ),
        "child_retry_and_cancel_fit_wave": (
            limits["child_timeout_seconds"]
            + limits["retry_backoff_seconds"]
            + limits["cancellation_drain_seconds"]
            <= limits["wave_timeout_seconds"]
        ),
        "receipt_fits_adapter_storage": (
            limits["mutation_receipt_bytes_per_run"] <= limits["adapter_storage_bytes"]
        ),
        "aggregate_deadline_is_120_minutes": limits["wall_clock_seconds"] == 120 * 60,
    }
    if not all(relationships.values()):
        _fail("LIMIT_EXCEEDED", "cross-limit relationship is invalid")
    return {"fixed_limits": checks, "relationships": relationships}


def _surface_dict(inventory: SurfaceInventory) -> dict[str, object]:
    return {
        "stage": inventory.stage,
        "records": [dataclasses.asdict(item) for item in inventory.records],
        "confirmed_absent": list(inventory.confirmed_absent),
    }


def build_report(
    *,
    workflow_path: Path = DEFAULT_WORKFLOW_PATH,
    plugin_root: Path = PLUGIN_ROOT,
) -> dict[str, object]:
    """Build the Section 9 report without creating production evidence."""

    protocol = _PROTOCOL.load_protocol(plugin_root / "codex/adapter-protocol.json")
    workflow = validate_workflow(workflow_path)
    cold_started = time.perf_counter_ns()
    cold_inventory = _SUPPORT.build_inventory(plugin_root)
    cold_ns = time.perf_counter_ns() - cold_started
    warm_started = time.perf_counter_ns()
    warm_inventory = _SUPPORT.build_inventory(plugin_root)
    warm_ns = time.perf_counter_ns() - warm_started
    if _SUPPORT.bundle_as_dict(cold_inventory) != _SUPPORT.bundle_as_dict(
        warm_inventory
    ):
        _fail("INTEGRITY_MISMATCH", "cold and warm inventories differ")

    source_stage = (
        "qualified_source"
        if (plugin_root / ".codex-plugin" / "plugin.json").is_file()
        else "source"
    )
    source_surfaces = generate_surface_inventory(plugin_root, stage=source_stage)
    with tempfile.TemporaryDirectory(prefix="lp-codex-section9-") as temporary:
        temporary_root = Path(temporary).resolve()
        staged = temporary_root / "launchpad"
        shutil.copytree(
            plugin_root,
            staged,
            ignore=shutil.ignore_patterns(
                "__pycache__", ".pytest_cache", ".ruff_cache"
            ),
        )
        _MANIFEST.sync_manifest(plugin_root, staged, write=True)
        candidate = _SUPPORT.build_test_candidate(staged)
        _SUPPORT.verify_runtime_set(candidate, staged)
        package = temporary_root / "package"
        package.mkdir()
        packaged_paths = _MANIFEST.project_package(
            candidate,
            staged,
            package,
            include_generated=False,
        )
        canonical_skill_paths = frozenset(
            node.source_path for node in candidate.runtime.nodes if node.kind == "skill"
        )
        candidate_surfaces = generate_surface_inventory(
            package,
            stage="test_candidate",
            canonical_skill_paths=canonical_skill_paths,
        )
        package_bytes = sum(
            path.stat().st_size for path in package.rglob("*") if path.is_file()
        )

    classifications = _classification_records(candidate)
    advertised = tuple(
        item["resource_id"]
        for item in classifications
        if item["base_support_state"] == "supported"
    )
    unblocked = tuple(
        item["resource_id"]
        for item in classifications
        if item["base_support_state"] != "blocked" or item["qualification_ids"]
    )
    if advertised or unblocked:
        _fail(
            "UNVERIFIED_SUPPORT_ADVERTISED",
            f"Section 9 cannot advertise unqualified roots: {list(unblocked)}",
        )
    commands = sum(item["kind"] == "command" for item in classifications)
    public_skills = sum(item["kind"] == "skill" for item in classifications)
    nodes_by_id = {node.id: node for node in candidate.runtime.nodes}
    hydrate = nodes_by_id.get("lp-hydrate")
    harden_plan = nodes_by_id.get("lp-harden-plan")
    if (
        hydrate is None
        or hydrate.capabilities.mutation != "none"
        or harden_plan is None
        or harden_plan.capabilities.mutation != "project_files"
    ):
        _fail("FIXED_BETA_INCOMPLETE", "fixed beta workflow definitions drifted")
    fixed_beta = {
        "router_help": {
            "fixture_gate": "tests/test_plugin_codex_router.py",
            "fixture_acceptance": "pass",
            "real_host_acceptance": "blocked",
            "reason_codes": list(_ROUTER_HOST_BLOCKERS),
        },
        "zero_mutation": {
            "resource_id": "lp-hydrate",
            "fixture_gate": "tests/test_plugin_codex_router.py",
            "fixture_acceptance": "pass",
            "real_host_acceptance": "blocked",
            "reason_codes": ["WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN"],
        },
        "harden_plan": {
            "resource_id": "lp-harden-plan",
            "fixture_gate": "tests/test_plugin_codex_harden_plan.py",
            "fixture_acceptance": "pass",
            "real_host_acceptance": "blocked",
            "reason_codes": ["WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN"],
        },
    }
    unverified_families = sorted(
        {
            capability
            for item in classifications
            for capability in item["required_capabilities"]
        }
    )
    return {
        "schema_version": 1,
        "ci_acceptance": "pass",
        "beta_release_acceptance": "blocked",
        "workflow": workflow,
        "surfaces": {
            "source": _surface_dict(source_surfaces),
            "test_candidate_package": _surface_dict(candidate_surfaces),
        },
        "corpus": {
            "nodes": len(candidate.runtime.nodes),
            "commands": commands,
            "public_builtin_skills": public_skills,
            "classified_roots": len(classifications),
            "classifications": list(classifications),
            "advertised_roots": list(advertised),
            "advertised_capability_families": [],
            "unverified_capability_families": unverified_families,
        },
        "fixed_beta_minimum": fixed_beta,
        "observations": {
            "package_file_count": len(packaged_paths),
            "package_bytes": package_bytes,
            "catalog_cold_nanoseconds": cold_ns,
            "catalog_warm_nanoseconds": warm_ns,
            "estimated_allocations": {
                "child_starts": protocol.limits["child_starts"],
                "input_tokens": protocol.limits["estimated_input_tokens"],
                "output_tokens": protocol.limits["estimated_output_tokens"],
                "outbound_bytes": protocol.limits["aggregate_outbound_bytes"],
                "wall_clock_seconds": protocol.limits["wall_clock_seconds"],
            },
            "authoritative_usage": {
                "available": False,
                "reason_code": "HOST_NO_AUTHORITATIVE_BUDGET_PRICING_CAP",
                "monetary_enforcement_claimed": False,
            },
        },
        "boundaries": _boundary_observations(protocol),
    }


def _receipt_records(
    value: object,
    *,
    root_fields: frozenset[str],
    id_field: str,
) -> tuple[tuple[dict[str, str], ...], Mapping[str, object]]:
    if not isinstance(value, Mapping) or set(value) != set(root_fields):
        _fail("HOST_RECEIPT_INVALID", "host receipt root fields differ")
    codex_home = value.get("codex_home")
    if (
        not isinstance(codex_home, str)
        or not Path(codex_home).is_absolute()
        or ".." in Path(codex_home).parts
        or not Path(codex_home).name.startswith("lp-codex-")
    ):
        _fail("HOST_RECEIPT_INVALID", "host receipt did not use isolated Codex state")
    results = value.get("results")
    if not isinstance(results, list):
        _fail("HOST_RECEIPT_INVALID", "host receipt results must be a list")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, Mapping) or set(item) != {id_field, "result", "detail"}:
            if not isinstance(item, Mapping) or set(item) != {
                id_field,
                "status",
                "detail",
            }:
                _fail("HOST_RECEIPT_INVALID", "host receipt result fields differ")
        identifier = item.get(id_field)
        status = item.get("result", item.get("status"))
        detail = item.get("detail")
        if (
            not isinstance(identifier, str)
            or not _IDENTIFIER_RE.fullmatch(identifier)
            or identifier in seen
            or not isinstance(status, str)
            or status not in {"PASS", "BLOCKED"}
            or not isinstance(detail, str)
            or len(detail)
            > _PROTOCOL.load_protocol().limits["diagnostic_field_characters"]
        ):
            _fail("HOST_RECEIPT_INVALID", "host receipt result is invalid")
        seen.add(identifier)
        records.append({id_field: identifier, "status": status, "detail": detail})
    return tuple(records), cast(Mapping[str, object], value)


def verify_router_host_receipt(
    path: Path,
    *,
    expected_codex_version: str,
    expected_runtime_payload_digest: str | None = None,
) -> dict[str, object]:
    """Validate the pinned real-host router smoke without promoting support."""

    value = _strict_json(
        path.read_bytes(),
        maximum=_PROTOCOL.load_protocol().limits["documentation_file_bytes"],
    )
    records, _root = _receipt_records(
        value,
        root_fields=frozenset({"codex_home", "runtime_payload_digest", "results"}),
        id_field="probe",
    )
    runtime_payload_digest = _root.get("runtime_payload_digest")
    if (
        not isinstance(runtime_payload_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", runtime_payload_digest)
        or (
            expected_runtime_payload_digest is not None
            and runtime_payload_digest != expected_runtime_payload_digest
        )
    ):
        _fail("HOST_RECEIPT_INVALID", "router receipt runtime digest differs")
    by_id = {item["probe"]: item for item in records}
    expected = {
        "app-server-argument-tail-binding",
        "app-server-typed-skill-selection",
        "bare-lp-authenticated-routing",
        "cli-bare-lp-binding",
        "codex-version",
        "internal-plugin-discovery",
        "plugin-hook-ingress",
        "sealed-install",
    }
    if set(by_id) != expected:
        _fail("HOST_RECEIPT_INVALID", "router host probes differ")
    required_pass = {
        "app-server-typed-skill-selection",
        "codex-version",
        "internal-plugin-discovery",
        "sealed-install",
    }
    required_blocked = {
        "app-server-argument-tail-binding",
        "bare-lp-authenticated-routing",
        "cli-bare-lp-binding",
        "plugin-hook-ingress",
    }
    if any(by_id[item]["status"] != "PASS" for item in required_pass) or any(
        by_id[item]["status"] != "BLOCKED" for item in required_blocked
    ):
        _fail("HOST_RECEIPT_INVALID", "router host outcome changed unexpectedly")
    if by_id["codex-version"]["detail"] != f"codex-cli {expected_codex_version}":
        _fail("HOST_RECEIPT_INVALID", "Codex host version differs from the CI pin")
    return {
        "status": "pass",
        "host": f"codex-cli {expected_codex_version}",
        "runtime_payload_digest": runtime_payload_digest,
        "advertised_capability_families": [],
        "blocked_reason_codes": list(_ROUTER_HOST_BLOCKERS),
    }


def verify_lifecycle_host_receipt(
    path: Path,
    *,
    expected_codex_version: str,
    expected_claude_version: str,
) -> dict[str, object]:
    """Validate the nightly Codex lifecycle and Claude coexistence fixture receipt."""

    value = _strict_json(
        path.read_bytes(),
        maximum=_PROTOCOL.load_protocol().limits["documentation_file_bytes"],
    )
    records, root = _receipt_records(
        value,
        root_fields=frozenset({"overall", "fixture", "codex_home", "results"}),
        id_field="id",
    )
    if root.get("overall") != "BLOCKED":
        _fail("HOST_RECEIPT_INVALID", "lifecycle receipt must remain fail-closed")
    by_id = {item["id"]: item for item in records}
    required_pass = {
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
    }
    required_blocked = {"duplicate-skill-resolution", "enforcement-boundaries"}
    if set(by_id) != required_pass | required_blocked:
        _fail("HOST_RECEIPT_INVALID", "lifecycle host probes differ")
    if any(by_id[item]["status"] != "PASS" for item in required_pass) or any(
        by_id[item]["status"] != "BLOCKED" for item in required_blocked
    ):
        _fail("HOST_RECEIPT_INVALID", "lifecycle host outcome changed unexpectedly")
    versions = str(by_id["host-versions"]["detail"])
    if f"codex-cli {expected_codex_version}" not in versions or not versions.endswith(
        f"{expected_claude_version} (Claude Code)"
    ):
        _fail("HOST_RECEIPT_INVALID", "lifecycle host versions differ from CI pins")
    return {
        "status": "pass",
        "codex_host": f"codex-cli {expected_codex_version}",
        "claude_host": f"Claude Code {expected_claude_version}",
        "overall_support": "blocked",
        "advertised_capability_families": [],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW_PATH)
    check.add_argument("--plugin-root", type=Path, default=PLUGIN_ROOT)
    check.add_argument("--output", type=Path)
    router = subparsers.add_parser("verify-router-host")
    router.add_argument("--receipt", type=Path, required=True)
    router.add_argument("--codex-version", required=True)
    router.add_argument("--runtime-payload-digest")
    lifecycle = subparsers.add_parser("verify-lifecycle-host")
    lifecycle.add_argument("--receipt", type=Path, required=True)
    lifecycle.add_argument("--codex-version", required=True)
    lifecycle.add_argument("--claude-version", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "check":
            result = build_report(
                workflow_path=args.workflow,
                plugin_root=args.plugin_root,
            )
        elif args.command == "verify-router-host":
            result = verify_router_host_receipt(
                args.receipt,
                expected_codex_version=args.codex_version,
                expected_runtime_payload_digest=args.runtime_payload_digest,
            )
        else:
            result = verify_lifecycle_host_receipt(
                args.receipt,
                expected_codex_version=args.codex_version,
                expected_claude_version=args.claude_version,
            )
        output = _pretty_json(result)
        output_path = getattr(args, "output", None)
        if output_path is None:
            sys.stdout.buffer.write(output)
        else:
            trusted_root = output_path.parent.resolve(strict=True)
            atomic_write_replace(
                output_path,
                output,
                mode=0o644,
                trusted_root=trusted_root,
            )
            sys.stdout.buffer.write(
                _pretty_json({"output": output_path.name, "status": "pass"})
            )
        return 0
    except (AcceptanceError, _PROTOCOL.ProtocolValidationError) as exc:
        code = getattr(exc, "code", "UNKNOWN_ERROR")
        sys.stderr.buffer.write(
            _pretty_json(
                {
                    "error": code,
                    "message": str(exc),
                    "reporting_class": _PROTOCOL.load_protocol().reporting_class_for_error(
                        code
                    ),
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
