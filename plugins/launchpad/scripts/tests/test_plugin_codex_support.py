"""Section 5 support graph, evidence, digest, and rendering tests."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SCRIPTS.parent
SUPPORT_PATH = SCRIPTS / "plugin-codex-support.py"
MANIFEST_PATH = SCRIPTS / "plugin-codex-manifest.py"
DOC_FIXTURE = Path(__file__).parent / "fixtures" / "codex_compatibility" / "support_docs"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


support = _load("plugin_codex_support_tests", SUPPORT_PATH)
manifest = _load("plugin_codex_manifest_for_support_tests", MANIFEST_PATH)


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


def _release(candidate):
    digest = candidate.runtime.runtime_payload_digest
    qualification = {
        "qualification_id": "qual-section5",
        "runtime_payload_digest": digest,
        "host": "codex-fixture",
        "operating_system": "fixture-os",
        "tool_versions": {"codex": "fixture"},
        "receipt_ids": ["receipt-section5"],
    }
    predicates = []
    for item in candidate.compatibility_predicates:
        value = support._jsonable(item)
        value["qualification_ids"] = ["qual-section5"]
        predicates.append(value)
    return support.promote_release(
        candidate,
        {
            "compatibility_predicates": predicates,
            "qualifications": [qualification],
        },
    )


def test_inventory_uses_one_normalized_direct_edge_graph() -> None:
    bundle = support.build_inventory()
    assert bundle.runtime.stage == "inventory"
    assert len(bundle.runtime.nodes) == 94
    assert len(bundle.runtime.root_ids) == 44
    assert bundle.runtime.runtime_files == ()
    assert len(bundle.compatibility_predicates) == 44
    assert "expanded_reachability" not in support.bundle_as_dict(bundle)["runtime"]


def test_candidate_runtime_set_and_digest_are_deterministic(staged_plugin: Path) -> None:
    first = support.build_test_candidate(staged_plugin)
    second = support.build_test_candidate(staged_plugin)
    assert first == second
    assert first.runtime.stage == "test_candidate"
    assert first.runtime.runtime_payload_digest is not None
    paths = [item.path for item in first.runtime.runtime_files]
    assert paths == sorted(set(paths))
    assert ".codex-plugin/plugin.json" in paths
    assert any(path.startswith("codex/canonical/commands/") for path in paths)
    assert any(path.startswith("codex/canonical/skills/") for path in paths)
    assert any(path.startswith("codex/canonical/agents/") for path in paths)
    assert not any(path.startswith("commands/") for path in paths)
    assert not any(path.startswith("skills/") for path in paths)
    assert not any(path.startswith("agents/") for path in paths)
    assert "codex/support-evidence.json" not in paths
    assert "README.md" not in paths
    support.verify_runtime_set(first, staged_plugin)


def test_runtime_digest_detects_changed_payload(candidate, staged_plugin: Path) -> None:
    target = staged_plugin / "scripts" / "plugin-codex-resolver.py"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(support.SupportError) as raised:
        support.verify_runtime_set(candidate, staged_plugin)
    assert raised.value.code == "INTEGRITY_MISMATCH"


def test_release_promotion_copies_candidate_graph_without_rebuild(candidate) -> None:
    release = _release(candidate)
    assert release.runtime.stage == "release"
    assert release.runtime.runtime_payload_digest == candidate.runtime.runtime_payload_digest
    assert release.runtime.nodes == candidate.runtime.nodes
    assert release.runtime.runtime_files == candidate.runtime.runtime_files
    assert release.runtime.qualification_ids == ("qual-section5",)
    assert len(support.evidence_digest(release)) == 64
    assert "evidence_digest" not in support.bundle_as_dict(release)
    assert "artifact_digest" not in support.bundle_as_dict(release)


def test_qualification_for_another_payload_is_rejected(candidate) -> None:
    qualification = {
        "qualification_id": "qual-wrong",
        "runtime_payload_digest": "0" * 64,
        "host": "fixture",
        "operating_system": "fixture",
        "tool_versions": {},
        "receipt_ids": ["receipt-wrong"],
    }
    predicates = []
    for item in candidate.compatibility_predicates:
        value = support._jsonable(item)
        value["qualification_ids"] = ["qual-wrong"]
        predicates.append(value)
    with pytest.raises(support.SupportError) as raised:
        support.promote_release(
            candidate,
            {
                "compatibility_predicates": predicates,
                "qualifications": [qualification],
            },
        )
    assert raised.value.code == "INTEGRITY_MISMATCH"


def test_specific_predicate_selection_and_overlay_are_monotone(candidate) -> None:
    base = support.select_compatibility_predicate(
        candidate,
        candidate.runtime.root_ids[0],
        host="codex-cli",
        operating_system="darwin",
        capabilities=[],
        tool_versions={},
    )
    assert base.effective_availability == "blocked"
    available = support._PROTOCOL.normalize_availability_record(
        {
            "resource_id": base.resource_id,
            "applicability": "applicable",
            "effective_availability": "available",
            "reason_codes": [],
        }
    )
    with pytest.raises(support.SupportError) as raised:
        support.apply_overlay(base, available)
    assert raised.value.code == "CAPABILITY_BLOCKED"


def test_help_diagnostics_include_support_requirements_and_fixed_bounds(candidate) -> None:
    contract = support._PROTOCOL.load_protocol()
    hydrate = support.build_entry_diagnostics(
        candidate,
        "lp-hydrate",
        host="fixture",
        operating_system="darwin",
        capabilities=sorted(contract.capability_ids),
        tool_versions={},
    )
    assert hydrate.base_support_state == "blocked"
    assert hydrate.reason_codes == ("WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN",)
    assert hydrate.mutation == "none"
    assert hydrate.maximum_child_starts == 0
    assert hydrate.maximum_workers == 0
    assert hydrate.authoritative_cost_available is False
    assert set(contract.router["zero_mutation_required_capabilities"]).issubset(
        hydrate.required_capabilities
    )

    review = support.build_entry_diagnostics(
        candidate,
        "lp-review",
        host="fixture",
        operating_system="darwin",
        capabilities=sorted(contract.capability_ids),
        tool_versions={},
    )
    assert review.maximum_child_starts == contract.limits["child_starts"]
    assert review.maximum_workers == contract.limits["worker_ceiling"]
    assert (
        review.maximum_wave_duration_seconds
        == contract.limits["wave_timeout_seconds"]
    )


def test_render_docs_write_changes_only_marked_regions_and_check_writes_nothing(
    candidate, tmp_path: Path
) -> None:
    release = _release(candidate)
    docs = tmp_path / "docs-root"
    shutil.copytree(DOC_FIXTURE, docs)
    before_readme = (docs / "README.md").read_text(encoding="utf-8")
    changed = support.render_documents(release, docs, write=True)
    assert changed == ("README.md", "docs/guides/HOW_IT_WORKS.md")
    after_readme = (docs / "README.md").read_text(encoding="utf-8")
    assert before_readme.split("<!-- BEGIN", 1)[0] == after_readme.split("<!-- BEGIN", 1)[0]
    assert before_readme.rsplit("<!-- END", 1)[1] == after_readme.rsplit("<!-- END", 1)[1]
    snapshot = {
        path.relative_to(docs): path.read_bytes() for path in docs.rglob("*") if path.is_file()
    }
    assert support.render_documents(release, docs, write=False) == ()
    assert snapshot == {
        path.relative_to(docs): path.read_bytes() for path in docs.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize(
    "content",
    [
        b"no markers\n",
        b"<!-- BEGIN LAUNCHPAD GENERATED:codex-beta-summary -->\n",
        (
            b"<!-- BEGIN LAUNCHPAD GENERATED:codex-beta-summary -->\n"
            b"<!-- BEGIN LAUNCHPAD GENERATED:codex-beta-summary -->\n"
            b"<!-- END LAUNCHPAD GENERATED:codex-beta-summary -->\n"
        ),
    ],
)
def test_render_docs_rejects_missing_duplicate_or_malformed_markers(
    candidate, tmp_path: Path, content: bytes
) -> None:
    release = _release(candidate)
    docs = tmp_path / "docs-root"
    shutil.copytree(DOC_FIXTURE, docs)
    (docs / "README.md").write_bytes(content)
    with pytest.raises(support.SupportError) as raised:
        support.render_documents(release, docs, write=False)
    assert raised.value.code == "RECORD_INVALID"


def test_support_bundle_strict_json_rejects_duplicate_and_unknown_fields(
    candidate, tmp_path: Path
) -> None:
    path = tmp_path / "candidate.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(support.SupportError) as duplicate:
        support.load_bundle(path)
    assert duplicate.value.code == "RECORD_INVALID"
    value = support.bundle_as_dict(candidate)
    value["unknown"] = True
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(support.SupportError) as unknown:
        support.load_bundle(path)
    assert unknown.value.code == "RECORD_INVALID"


def test_render_and_evidence_reads_reject_symlinks(candidate, tmp_path: Path) -> None:
    release = _release(candidate)
    docs = tmp_path / "docs-root"
    shutil.copytree(DOC_FIXTURE, docs)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (docs / "README.md").unlink()
    (docs / "README.md").symlink_to(outside)
    with pytest.raises(OSError):
        support.render_documents(release, docs, write=False)
    evidence = tmp_path / "evidence.json"
    evidence.symlink_to(outside)
    with pytest.raises((OSError, support.SupportError)):
        support.load_bundle(evidence)
