"""Receipt-driven frontend roles and toolchain-backed editable commands."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lp_pick_stack.decision_writer import write_decision_file
from lp_scaffold_stack.receipt_writer import build_receipt_payload, write_receipt
from plugin_stack_adapters import generic, polyglot
from plugin_stack_adapters._package_managers import lefthook_hooks_for_family
from plugin_stack_adapters._vendor import yaml

_SCRIPTS = Path(__file__).resolve().parent.parent
_FIELDS = ("test", "typecheck", "lint", "format", "build")
_TS_COMMANDS = {field: [lefthook_hooks_for_family("ts")[field + "_command"]] for field in _FIELDS}


def _layers(*entries: tuple[str, str, str]) -> list[dict]:
    return [dict(stack=stack, role=role, path=path, options={}) for stack, role, path in entries]


def _seed_project(root: Path, layers: list[dict], toolchains: list[str]) -> None:
    (root / ".launchpad").mkdir()
    _, decision = write_decision_file(
        layers=layers,
        matched_category_id="manual",
        rationale_summary=[],
        rationale_sha256="0" * 64,
        cwd=root,
    )
    payload = build_receipt_payload(
        decision_sha256=decision["sha256"],
        decision_nonce=decision["nonce"],
        layers_materialized=[dict(layer, adapter_used=layer["stack"], files_created=[]) for layer in layers],
        cross_cutting_files=[],
        toolchains_detected=toolchains,
        secret_scan_passed=True,
    )
    write_receipt(cwd=root, **payload)


def _run_define(root: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "lp_define_runner.py"), "--repo-root", str(root), "--force", "--no-trust-banner"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["summary"]


@pytest.mark.parametrize(
    "layers,toolchains,ui,docs_restricted,seeded,component_dir",
    [
        (_layers(("hono", "backend", "apps/api"), ("generic", "frontend", "apps/web")), ["node"], True, False, True, "apps/web/"),
        (_layers(("next", "frontend", "apps/web"), ("hono", "backend", "apps/api")), ["node"], True, False, False, None),
        (_layers(("next", "frontend", "apps/web"), ("django", "backend", "apps/api")), ["node", "python"], True, True, False, None),
        (_layers(("django", "backend", "apps/api"), ("generic", "frontend", "apps/web")), ["node"], True, True, False, "apps/web/"),
        (_layers(("generic", "frontend", ".")), ["node"], True, False, True, "./"),
        (_layers(("generic", "backend", ".")), [], False, True, False, None),
        (_layers(("hono", "backend", "apps/api"), ("generic", "backend", "services/worker")), ["node"], False, True, True, None),
    ],
    ids=["hono-generic-ui", "next-hono", "next-django", "django-generic-ui", "generic-ui", "generic-backend", "two-backends"],
)
def test_declared_roles(
    tmp_path: Path, layers: list[dict], toolchains: list[str], ui: bool,
    docs_restricted: bool, seeded: bool, component_dir: str | None,
) -> None:
    _seed_project(tmp_path, layers, toolchains)
    summary = _run_define(tmp_path)
    config = yaml.safe_load((tmp_path / ".launchpad/config.yml").read_text())
    output = polyglot.compose_with_layers(layers)
    assert (output["frontend"] is not None) is ui
    assert (output["pipeline_overrides"].get("frontend_docs_enabled") is False) is docs_restricted
    if component_dir is not None:
        assert output["frontend"]["framework"] == "Unknown"
        assert output["frontend"]["component_dir"] == component_dir
    stage = "enabled" if ui else "skipped"
    assert config["pipeline"]["define"]["design"] == stage
    assert config["pipeline"]["plan"]["design_review"] == stage
    assert config["pipeline"]["build"]["test_browser"] == stage
    app_flow = (tmp_path / "docs/architecture/APP_FLOW.md").read_text()
    if ui:
        assert "## Entry routes" in app_flow
        assert "## Navigation structure" in app_flow
        assert "backend-only" not in app_flow
    else:
        assert "backend-only" in app_flow
    if seeded:
        assert summary["seeded_commands"] == _TS_COMMANDS
        assert config["commands"] == _TS_COMMANDS
    else:
        assert "seeded_commands" not in summary
        assert config["commands"] == output["commands"]
    if layers[0]["stack"] == "next":
        assert "pnpm test" in config["commands"]["test"]
    if layers == _layers(("generic", "backend", ".")):
        assert all(not commands for commands in config["commands"].values())


def test_declared_frontend_copy_and_role_priority() -> None:
    original = generic.run()
    layers = _layers(("generic", "frontend-dashboard", "apps/dashboard"), ("generic", "frontend-main", "apps/main"))
    result = polyglot.apply_declared_frontend(original, layers)
    assert result is not original
    assert original["frontend"] is None
    assert original["pipeline_overrides"]["design_enabled"] is False
    assert result["frontend"]["component_dir"] == "apps/main/"
    assert result["app_flow"] == dict(entry_routes=[], auth_flow=None, primary_journeys=[])
    assert result["pipeline_overrides"] == {}
