"""One normalized stack source for bootstrap enrichment before and after define."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

from lp_bootstrap._enricher_common import read_decision_payload_safe, read_enricher_stacks
from lp_bootstrap.stack_ignore_patterns import (
    enrich_gitignore_with_stacks,
    enrich_gitleaks_with_stacks,
    enrich_greptile_with_stacks,
)
from lp_bootstrap.stack_lefthook import enrich_lefthook_with_stacks
from lp_bootstrap.stack_pkg_manager import enrich_ci_yml_pkg_setup, enrich_lefthook_yml_pkg_commands
from lp_bootstrap.stack_structure_check import enrich_structure_check_with_stacks
from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM
from plugin_stack_adapters._ignore_patterns import (
    GITIGNORE_PATTERNS_PER_STACK,
    GITLEAKS_PATHS_PER_STACK,
    GREPTILE_IGNORE_PATTERNS_PER_STACK,
)
from plugin_stack_adapters._package_managers import STACK_FAMILY, primary_family_for_stacks
from plugin_stack_adapters._structure_allowlists import STACK_ALLOWED_DIRS
from test_check_repo_structure_per_stack_v216 import _render_kernel_bytes
from test_lp_bootstrap_stack_lefthook import _KERNEL_FIXTURE

_SCRIPTS = Path(__file__).resolve().parents[1]
_CATALOG_NAMES = sorted(yaml.safe_load((_SCRIPTS.parent / "scaffolders.yml").read_text())["stacks"])


def _decision(root: Path, stacks) -> None:
    target = root / ".launchpad/scaffold-decision.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"schema_version": "1.1", "stacks": stacks}), encoding="utf-8")


def _config(root: Path, stacks: list[str]) -> None:
    target = root / ".launchpad/config.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump({"stacks": stacks}), encoding="utf-8")


def _read(root: Path) -> list[str]:
    return read_enricher_stacks(root, module_spec_name="plugin_config_loader_test_enricher_source")


@pytest.mark.parametrize(
    ("config", "decision", "expected"),
    [
        (["rails"], ["astro"], ["rails"]),
        (None, ["astro"], ["astro"]),
        ([], ["astro"], ["astro"]),
        (None, None, []),
        (["django"], ["astro"], ["python_generic"]),
        (["next", "fastapi"], None, ["nextjs_fastapi"]),
    ],
    ids=["config-wins", "decision-fallback", "empty-config-fallback", "neither", "django-family", "composition"],
)
def test_stack_source_precedence(tmp_path: Path, config, decision, expected):
    if config is not None:
        _config(tmp_path, config)
    if decision is not None:
        _decision(tmp_path, decision)
    assert _read(tmp_path) == expected
    if config == ["django"]:
        assert primary_family_for_stacks(_read(tmp_path)) == "python"


@pytest.mark.parametrize("body", ["{bad", "[]", '{"schema_version":"1.1","stacks":"astro"}', '{"schema_version":"1.1","stacks":[42]}', '{"schema_version":"2.0","stacks":["astro"]}'])
def test_invalid_decision_returns_empty(tmp_path: Path, body: str):
    path = tmp_path / ".launchpad/scaffold-decision.json"
    path.parent.mkdir()
    path.write_text(body, encoding="utf-8")
    assert _read(tmp_path) == []


def test_decision_payload_uses_canonical_reader_and_fails_soft(tmp_path: Path):
    assert read_decision_payload_safe(tmp_path, module_spec_name="test_decision_payload") == {}
    _decision(tmp_path, ["astro"])
    payload = read_decision_payload_safe(tmp_path, module_spec_name="test_decision_payload")
    assert payload == {"schema_version": "1.1", "stacks": ["astro"]}
    path = tmp_path / ".launchpad/scaffold-decision.json"
    path.write_text('{"schema_version":"2.0","stacks":["astro"]}', encoding="utf-8")
    assert read_decision_payload_safe(tmp_path, module_spec_name="test_decision_payload") == {}


def test_unknown_decision_ids_are_filtered(tmp_path: Path):
    _decision(tmp_path, ["unknown_future_stack"])
    assert _read(tmp_path) == []
    _decision(tmp_path, ["unknown_future_stack", "astro"])
    assert _read(tmp_path) == ["astro"]


@pytest.mark.parametrize("shortname", _CATALOG_NAMES)
def test_catalog_normalization_has_all_enrichment_data(tmp_path: Path, shortname: str):
    _decision(tmp_path, [shortname])
    stacks = _read(tmp_path)
    assert stacks
    for stack in stacks:
        assert stack in STACK_ALLOWED_DIRS
        assert stack in GITIGNORE_PATTERNS_PER_STACK
        assert stack in STACK_FAMILY


@pytest.mark.parametrize("stack", sorted(STACK_ID_ACTIVE_ENUM))
def test_active_ids_pass_through(tmp_path: Path, stack: str):
    _decision(tmp_path, [stack])
    assert _read(tmp_path) == [stack]


def test_decision_only_lefthook_fragment(tmp_path: Path):
    _decision(tmp_path, ["nextjs_fastapi"])
    result = yaml.safe_load(enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path))
    assert "bandit" in result["pre-commit"]["commands"]
    assert "pyright" in result["pre-push"]["commands"]


def test_decision_only_package_manager_rewrite(tmp_path: Path):
    _decision(tmp_path, ["django"])
    kernel = b"pre-commit:\n  commands:\n    test:\n      run: pnpm test\n"
    result = enrich_lefthook_yml_pkg_commands(kernel, tmp_path).decode()
    assert "run: pytest" in result
    assert "run: pnpm test" not in result


def test_decision_only_ci_commands(tmp_path: Path):
    _decision(tmp_path, ["django"])
    kernel = b"jobs:\n  build:\n    steps:\n      - name: Test\n        run: pnpm test\n"
    result = enrich_ci_yml_pkg_setup(kernel, tmp_path).decode()
    assert "run: pytest" in result
    assert "run: pnpm test" not in result


def test_decision_only_structure_dirs(tmp_path: Path):
    _decision(tmp_path, ["astro"])
    result = enrich_structure_check_with_stacks(_render_kernel_bytes(), tmp_path).decode()
    block = re.search(r"STACK_AWARE_DIRS_BEGIN[^\n]*\n(.*?)\s*# STACK_AWARE_DIRS_END", result, re.S).group(1).strip()
    assert block == '"public"\n  "src"'


def test_decision_only_gitignore(tmp_path: Path):
    _decision(tmp_path, ["astro"])
    kernel = b"# STACK_AWARE_GITIGNORE_BEGIN\n# STACK_AWARE_GITIGNORE_END\n"
    result = enrich_gitignore_with_stacks(kernel, tmp_path).decode()
    patterns = [line for line in result.splitlines() if line and not line.startswith("#")]
    assert patterns == list(GITIGNORE_PATTERNS_PER_STACK["astro"])


def test_decision_only_gitleaks(tmp_path: Path):
    _decision(tmp_path, ["astro"])
    kernel = b"paths = [\n    # STACK_AWARE_GITLEAKS_BEGIN\n    # STACK_AWARE_GITLEAKS_END\n]\n"
    result = enrich_gitleaks_with_stacks(kernel, tmp_path).decode()
    assert tomllib.loads(result)["paths"] == list(GITLEAKS_PATHS_PER_STACK["astro"])


def test_decision_only_greptile(tmp_path: Path):
    _decision(tmp_path, ["astro"])
    kernel = b'{"ignorePatterns": "STACK_AWARE_GREPTILE_BEGIN\\nSTACK_AWARE_GREPTILE_END"}'
    result = json.loads(enrich_greptile_with_stacks(kernel, tmp_path))
    assert result["ignorePatterns"].splitlines() == list(GREPTILE_IGNORE_PATTERNS_PER_STACK["astro"])


def test_reader_failures_return_safe_defaults(tmp_path: Path, monkeypatch):
    import lp_bootstrap._enricher_common as common

    monkeypatch.setattr(common, "_CONFIG_LOADER_PATH", tmp_path / "missing-loader.py")
    assert read_decision_payload_safe(tmp_path, module_spec_name="test_missing_loader") == {}
    assert _read(tmp_path) == []
