"""Section 5 Codex manifest and sealed package projection tests."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SCRIPTS.parent
MANIFEST_PATH = SCRIPTS / "plugin-codex-manifest.py"
SUPPORT_PATH = SCRIPTS / "plugin-codex-support.py"
DOC_FIXTURE = (
    Path(__file__).parent / "fixtures" / "codex_compatibility" / "support_docs"
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


manifest = _load("plugin_codex_manifest_tests", MANIFEST_PATH)
support = _load("plugin_codex_support_for_manifest_tests", SUPPORT_PATH)


@pytest.fixture()
def staged_plugin(tmp_path: Path) -> Path:
    root = tmp_path / "stage"
    shutil.copytree(
        PLUGIN_ROOT,
        root,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    return root


def _candidate(root: Path):
    manifest.sync_manifest(PLUGIN_ROOT, root, write=True)
    return support.build_test_candidate(root)


def _release(candidate):
    digest = candidate.runtime.runtime_payload_digest
    qualifications = [
        {
            "qualification_id": "qual-package",
            "runtime_payload_digest": digest,
            "host": "fixture",
            "operating_system": "fixture",
            "tool_versions": {},
            "receipt_ids": ["receipt-package"],
        }
    ]
    predicates = []
    for item in candidate.compatibility_predicates:
        value = support._jsonable(item)
        value["qualification_ids"] = ["qual-package"]
        predicates.append(value)
    return support.promote_release(
        candidate,
        {"compatibility_predicates": predicates, "qualifications": qualifications},
    )


def test_manifest_projects_shared_identity_and_only_fixed_host_fields(
    staged_plugin: Path,
) -> None:
    assert (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").is_file()
    assert manifest.sync_manifest(PLUGIN_ROOT, staged_plugin, write=True)
    value = json.loads((staged_plugin / ".codex-plugin" / "plugin.json").read_text())
    authority = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    for key, item in authority.items():
        assert value[key] == item
    assert value["skills"] == "./codex/skills/"
    assert set(value) == set(authority) | {"skills"}
    assert manifest.sync_manifest(PLUGIN_ROOT, staged_plugin, write=False)


def test_manifest_check_is_side_effect_free_when_absent(staged_plugin: Path) -> None:
    shutil.rmtree(staged_plugin / ".codex-plugin")
    before = set(path.relative_to(staged_plugin) for path in staged_plugin.rglob("*"))
    assert not manifest.sync_manifest(PLUGIN_ROOT, staged_plugin, write=False)
    after = set(path.relative_to(staged_plugin) for path in staged_plugin.rglob("*"))
    assert before == after
    assert not (staged_plugin / ".codex-plugin").exists()


def test_manifest_rejects_unknown_source_fields(staged_plugin: Path) -> None:
    source = json.loads((staged_plugin / ".claude-plugin" / "plugin.json").read_text())
    source["unknown"] = True
    (staged_plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps(source))
    with pytest.raises(manifest.ManifestError) as raised:
        manifest.projected_manifest(staged_plugin)
    assert raised.value.code == "RECORD_INVALID"


def test_manifest_rejects_symlinked_target_and_parent(
    staged_plugin: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    target_dir = staged_plugin / ".codex-plugin"
    shutil.rmtree(target_dir)
    target_dir.mkdir()
    (target_dir / "plugin.json").symlink_to(outside)
    with pytest.raises((manifest.ManifestError, OSError)):
        manifest.sync_manifest(PLUGIN_ROOT, staged_plugin, write=True)
    (target_dir / "plugin.json").unlink()
    target_dir.rmdir()
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    target_dir.symlink_to(outside_dir, target_is_directory=True)
    with pytest.raises(OSError):
        manifest.sync_manifest(PLUGIN_ROOT, staged_plugin, write=True)


def test_identical_concurrent_manifest_writes_are_recoverable(
    staged_plugin: Path,
) -> None:
    assert manifest.sync_manifest(PLUGIN_ROOT, staged_plugin, write=True)
    first = (staged_plugin / ".codex-plugin" / "plugin.json").read_bytes()
    assert manifest.sync_manifest(PLUGIN_ROOT, staged_plugin, write=True)
    assert (staged_plugin / ".codex-plugin" / "plugin.json").read_bytes() == first
    assert not list(staged_plugin.rglob("*.tmp"))


def test_package_consumes_sealed_set_plus_generated_slots_only(
    staged_plugin: Path, tmp_path: Path
) -> None:
    candidate = _candidate(staged_plugin)
    release = _release(candidate)
    shutil.copy2(DOC_FIXTURE / "README.md", staged_plugin / "README.md")
    guide = staged_plugin / "docs" / "guides" / "HOW_IT_WORKS.md"
    guide.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOC_FIXTURE / "docs" / "guides" / "HOW_IT_WORKS.md", guide)
    support.render_documents(release, staged_plugin, write=True)
    evidence_path = staged_plugin / "codex" / "support-evidence.json"
    support.write_bundle(release, evidence_path, trusted_root=staged_plugin)
    package = tmp_path / "package"
    package.mkdir()
    paths = manifest.project_package(
        release,
        staged_plugin,
        package,
        include_generated=True,
    )
    assert set(release.runtime.generated_slots).issubset(paths)
    assert manifest.check_package(release, package, include_generated=True) == paths
    first = manifest.artifact_digest(release, package)
    detached = tmp_path / "attestation.json"
    detached.write_text(json.dumps({"artifact_digest": first}), encoding="utf-8")
    assert manifest.artifact_digest(release, package) == first
    assert detached.resolve().is_relative_to(tmp_path)
    assert "artifact_digest" not in evidence_path.read_text(encoding="utf-8")


def test_runtime_package_contains_router_import_closure(
    staged_plugin: Path, tmp_path: Path
) -> None:
    candidate = _candidate(staged_plugin)
    package = tmp_path / "runtime-package"
    package.mkdir()
    paths = set(
        manifest.project_package(
            candidate,
            staged_plugin,
            package,
            include_generated=False,
        )
    )
    required = {
        "scripts/atomic_io.py",
        "scripts/plugin-codex-corpus.py",
        "scripts/plugin-codex-manifest.py",
        "scripts/plugin-codex-protocol.py",
        "scripts/plugin-codex-resolver.py",
        "scripts/plugin-codex-router.py",
        "scripts/plugin-codex-support.py",
        "scripts/plugin_stack_adapters/_vendor/yaml/__init__.py",
        "scripts/safe_run.py",
    }
    assert required.issubset(paths)
    assert not (package / "commands").exists()
    assert not (package / "skills").exists()
    assert not (package / "agents").exists()
    assert any(path.startswith("codex/canonical/commands/") for path in paths)
    assert any(path.startswith("codex/canonical/skills/") for path in paths)
    assert any(path.startswith("codex/canonical/agents/") for path in paths)

    sys.path.insert(0, str(package / "scripts"))
    try:
        _load(
            "plugin_codex_router_from_sealed_package",
            package / "scripts" / "plugin-codex-router.py",
        )
        packaged_resolver = _load(
            "plugin_codex_resolver_from_sealed_package",
            package / "scripts" / "plugin-codex-resolver.py",
        )
        catalog = packaged_resolver.SecureResolver().catalog()
        command_paths = {
            path
            for path in paths
            if path.startswith("codex/canonical/commands/")
            and path.count("/") == 3
            and path.endswith(".md")
        }
        skill_paths = {
            path
            for path in paths
            if path.startswith("codex/canonical/skills/")
            and path.endswith("/SKILL.md")
        }
        agent_paths = {
            path
            for path in paths
            if path.startswith("codex/canonical/agents/") and path.endswith(".md")
        }
        assert {item.source_path for item in catalog.commands.values()} == command_paths
        assert {item.source_path for item in catalog.skills.values()} == skill_paths
        assert {item.source_path for item in catalog.agents.values()} == agent_paths
        assert catalog.invalid_entries == ()
    finally:
        sys.path.remove(str(package / "scripts"))


def test_package_rejects_extra_file_symlink_and_interrupted_temp(
    staged_plugin: Path, tmp_path: Path
) -> None:
    candidate = _candidate(staged_plugin)
    package = tmp_path / "package"
    package.mkdir()
    manifest.project_package(candidate, staged_plugin, package, include_generated=False)
    extra = package / "extra.txt"
    extra.write_text("extra", encoding="utf-8")
    with pytest.raises(manifest.ManifestError) as extra_error:
        manifest.check_package(candidate, package, include_generated=False)
    assert extra_error.value.code == "INTEGRITY_MISMATCH"
    extra.unlink()
    (package / ".interrupted.tmp").write_text("partial", encoding="utf-8")
    with pytest.raises(manifest.ManifestError) as interrupted:
        manifest.check_package(candidate, package, include_generated=False)
    assert interrupted.value.code == "INTEGRITY_MISMATCH"
    (package / ".interrupted.tmp").unlink()
    target = package / "outside-link"
    target.symlink_to(tmp_path / "outside")
    with pytest.raises(manifest.ManifestError) as symlink:
        manifest.check_package(candidate, package, include_generated=False)
    assert symlink.value.code == "PATH_SYMLINK"


def test_package_recovery_rewrites_corrupt_file(
    staged_plugin: Path, tmp_path: Path
) -> None:
    candidate = _candidate(staged_plugin)
    package = tmp_path / "package"
    package.mkdir()
    manifest.project_package(candidate, staged_plugin, package, include_generated=False)
    target = package / "scripts" / "plugin-codex-protocol.py"
    target.write_text("corrupt", encoding="utf-8")
    manifest.project_package(candidate, staged_plugin, package, include_generated=False)
    assert manifest.check_package(candidate, package, include_generated=False)
