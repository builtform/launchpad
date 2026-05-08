"""nextjs_fastapi adapter (vintasoftware/nextjs-fastapi-template wrap-and-overlay) tests.

Phase 4 plan section 2.1 / section 2.2 row / section 3.4. Adapter Protocol
conformance + app/ + api/ workspace shape + LaunchPad scripts/ overlay +
unwrap_strategy="none".
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from plugin_stack_adapters.contracts import Adapter
from plugin_stack_adapters.nextjs_fastapi import (
    ADAPTER,
    NextjsFastapiAdapter,
    _OVERLAY,
)
from plugin_stack_adapters.pin_registry import get_pin

pytestmark = pytest.mark.slow


def _vinta_synthetic_tree() -> dict[str, bytes]:
    return {
        "package.json": (
            b'{\n  "name": "nextjs-fastapi-template",\n  "version": "0.0.8"\n}\n'
        ),
        "pnpm-workspace.yaml": b'packages:\n  - "app"\n',
        "app/package.json": b'{"name": "frontend"}\n',
        "app/pages/index.tsx": (
            b'export default function Home() { return null; }\n'
        ),
        "api/main.py": (
            b'from fastapi import FastAPI\n'
            b'app = FastAPI()\n'
            b'@app.get("/health")\n'
            b'def health() -> dict[str, str]:\n'
            b'    return {"status": "ok"}\n'
        ),
        "api/requirements.txt": b"fastapi==0.115.0\nuvicorn==0.32.0\n",
        "README.md": b"# nextjs-fastapi-template\n",
    }


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


@pytest.fixture
def synthetic_fetcher() -> Callable[[Path], None]:
    files = _vinta_synthetic_tree()

    def fetcher(target: Path) -> None:
        for rel, body in files.items():
            p = target / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)

    return fetcher


def test_adapter_satisfies_adapter_protocol():
    assert isinstance(ADAPTER, Adapter)


def test_stack_id_is_nextjs_fastapi():
    assert ADAPTER.stack_id == "nextjs_fastapi"


def test_unwrap_strategy_is_none():
    assert ADAPTER.unwrap_strategy == "none"


def test_workspace_name_primary_is_app():
    assert ADAPTER.workspace_name == "app"


def test_additional_workspaces_includes_api():
    assert "api" in ADAPTER.additional_workspaces


def test_pin_registry_resolves_to_vinta_with_mit_license():
    pin = get_pin("nextjs_fastapi")
    assert pin["repo_url"] == "https://github.com/vintasoftware/nextjs-fastapi-template"
    assert pin["license"] == "MIT"


def test_composes_with_includes_three_partners():
    partners = set(ADAPTER.composes_with.keys())
    assert partners == {"astro", "nextjs_standalone", "generic"}
    assert "ts_monorepo" not in partners
    assert "nextjs_fastapi" not in partners


def test_overlay_config_adds_launchpad_scripts_layout():
    add = set(_OVERLAY["add"])
    assert any(p.startswith("scripts/") for p in add), add


def test_scaffold_into_materializes_app_and_api_workspaces(
    tmp_path: Path, cache_root_tmp: Path, synthetic_fetcher
):
    adapter = NextjsFastapiAdapter(fetcher=synthetic_fetcher)
    target = tmp_path / "lp-nextjs_fastapi-tmp"
    adapter.scaffold_into(target)
    assert (target / "app" / "pages" / "index.tsx").is_file()
    assert (target / "api" / "main.py").is_file()
    assert (target / "api" / "requirements.txt").is_file()


def test_apply_overlay_adds_launchpad_scripts_directories(
    tmp_path: Path, cache_root_tmp: Path, synthetic_fetcher
):
    adapter = NextjsFastapiAdapter(fetcher=synthetic_fetcher)
    target = tmp_path / "lp-nextjs_fastapi-tmp"
    adapter.scaffold_into(target)
    adapter.apply_overlay(target)
    assert (target / "scripts" / "compound").is_dir()
    assert (target / "scripts" / "maintenance").is_dir()
    assert (target / "scripts" / "agent_hydration").is_dir()


def test_overlay_conflict_policy_marks_package_json_merge_keys():
    assert _OVERLAY["conflict_policy"]["package.json"] == "merge-keys"
    assert _OVERLAY["conflict_policy"]["pnpm-workspace.yaml"] == "merge-keys"
    assert _OVERLAY["conflict_policy"][".gitignore"] == "append-only"


def test_composes_with_nextjs_standalone_pair_marks_app_collision():
    rule = ADAPTER.composes_with["nextjs_standalone"]
    assert rule["workspace_name"] == "app"
    assert rule["conflict_policy"]["package.json"] == "merge-keys"
