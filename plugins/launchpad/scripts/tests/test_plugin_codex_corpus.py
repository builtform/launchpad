"""Section 3 canonical corpus, additive integrity, and inventory tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = SCRIPTS.parent
CORPUS_PATH = SCRIPTS / "plugin-codex-corpus.py"


def _load_corpus():
    spec = importlib.util.spec_from_file_location("plugin_codex_corpus_tests", CORPUS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def corpus():
    return _load_corpus()


@pytest.fixture(scope="module")
def audit(corpus):
    return corpus.audit_corpus()


def test_whole_corpus_audit_and_inventory_counts(audit) -> None:
    assert sum(entry.kind == "command" for entry in audit.entries) == 42
    assert sum(entry.kind == "agent" for entry in audit.entries) == 36
    assert sum(entry.kind == "skill" for entry in audit.entries) == 16
    assert len(audit.inventory.nodes) == 94
    assert len(audit.inventory.root_ids) == 44
    assert audit.inventory.stage == "inventory"
    assert audit.inventory.runtime_payload_digest is None
    assert audit.inventory.support == ()
    assert audit.inventory.qualification_ids == ()
    assert audit.inventory.generated_slots == ()


def test_every_released_command_and_user_invocable_skill_is_one_root(audit) -> None:
    expected = {
        entry.resource_id for entry in audit.entries if entry.user_invocable
    }
    assert set(audit.inventory.root_ids) == expected
    assert len(audit.inventory.root_ids) == len(set(audit.inventory.root_ids))
    assert {"lp-creating-agents", "lp-verification-before-completion"}.issubset(expected)


def test_legacy_and_non_runtime_files_are_audited_without_becoming_roots(audit) -> None:
    assert audit.legacy_unreleased_paths == ("commands/lp-research-codebase.md",)
    assert "lp-research-codebase" not in audit.inventory.root_ids
    assert audit.unowned_skill_files == (
        "skills/lp-compound-docs/assets/critical-pattern-template.md",
    )


def test_baseline_is_single_sorted_canonical_table(audit) -> None:
    baseline = json.loads(
        (PLUGIN_ROOT / "codex" / "canonical-corpus-baseline.json").read_text(
            encoding="utf-8"
        )
    )
    paths = [entry["path"] for entry in baseline["canonical"]]
    assert paths == [entry.source_path for entry in audit.entries]
    assert len(paths) == len(set(paths)) == 94
    assert baseline["baseline_commit"] == "ade7492f46d08591bc7e67d35f59947c808ca3e8"


def test_agent_scope_records_are_protocol_normalized(corpus, audit) -> None:
    records = corpus.build_agent_scope_records(audit.entries)
    assert len(records) == 36
    assert records["lp-file-locator"].stack_scope == "core_pipeline"
    assert records["lp-security-auditor"].stack_scope == "stack:any"


def test_security_floor_rejects_capability_reduction(corpus, audit) -> None:
    entry = next(item for item in audit.entries if item.resource_id == "lp-build")
    floor = corpus._metadata_floor(entry.metadata)
    reduced_capabilities = SimpleNamespace(
        required=tuple(
            value
            for value in entry.metadata.capabilities.required
            if value != "operation_authorization"
        ),
        mutation=entry.metadata.capabilities.mutation,
        interaction=entry.metadata.capabilities.interaction,
        external_data_egress=entry.metadata.capabilities.external_data_egress,
        write_scopes=entry.metadata.capabilities.write_scopes,
        tool_profile=entry.metadata.capabilities.tool_profile,
        fallback=entry.metadata.capabilities.fallback,
    )
    reduced = SimpleNamespace(
        schema_version=entry.metadata.schema_version,
        component_kind=entry.metadata.component_kind,
        direct=entry.metadata.direct,
        capabilities=reduced_capabilities,
        bounded_loop=entry.metadata.bounded_loop,
    )
    with pytest.raises(corpus.CorpusIntegrityError, match="required capabilities"):
        corpus.check_security_monotonicity(entry.resource_id, floor, reduced)


def test_additive_gate_accepts_only_declared_insert_offset(corpus, tmp_path: Path) -> None:
    original = [b"alpha\n", b"omega\n"]
    path = tmp_path / "template.md"
    path.write_bytes(b"alpha\nnew metadata\nomega\n")
    item = {
        "path": "template.md",
        "original_line_sha256": [hashlib.sha256(line).hexdigest() for line in original],
        "allowed_insert_offsets": [1],
        "required_fragments": ["new metadata"],
    }
    corpus._check_additive_file(tmp_path, item)
    path.write_bytes(b"outside\nalpha\nnew metadata\nomega\n")
    with pytest.raises(corpus.CorpusIntegrityError, match="approved boundary"):
        corpus._check_additive_file(tmp_path, item)


def test_additive_gate_rejects_changed_baseline_line(corpus, tmp_path: Path) -> None:
    original = [b"alpha\n", b"omega\n"]
    path = tmp_path / "template.md"
    path.write_bytes(b"alpha changed\nnew metadata\nomega\n")
    item = {
        "path": "template.md",
        "original_line_sha256": [hashlib.sha256(line).hexdigest() for line in original],
        "allowed_insert_offsets": [1],
        "required_fragments": ["new metadata"],
    }
    with pytest.raises(corpus.CorpusIntegrityError, match="removed, changed, or reordered"):
        corpus._check_additive_file(tmp_path, item)


def test_high_confidence_literal_reference_requires_owner_declaration(corpus) -> None:
    empty = SimpleNamespace(
        commands=(),
        skills=(),
        agents=(),
        references=(),
        assets=(),
        scripts=(),
        external_tools=(),
    )
    entry = SimpleNamespace(
        resource_id="lp-probe",
        kind="command",
        source_path="commands/lp-probe.md",
        body=b"Run ${CLAUDE_PLUGIN_ROOT}/scripts/probe.py.\n",
        metadata=SimpleNamespace(direct=empty),
    )
    with pytest.raises(corpus.CorpusIntegrityError, match="literal plugin script"):
        corpus.audit_declared_reference_hints((entry,))


def test_inventory_serialization_round_trips_through_protocol(corpus, audit) -> None:
    serialized = corpus.inventory_as_dict(audit.inventory)
    normalized = corpus._PROTOCOL.normalize_runtime_record(serialized)
    assert normalized == audit.inventory
