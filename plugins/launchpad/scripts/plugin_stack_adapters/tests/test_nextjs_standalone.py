"""nextjs_standalone adapter (vercel/next-forge wrap-and-overlay) tests.

Phase 4 plan section 2.1 / section 3.3 / section 3.5 / section 2.2 row.
Adapter Protocol conformance + OverlayConfig (Clerk -> Auth.js v5) +
nested-Turborepo unwrap_strategy + pin_registry sourcing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from plugin_stack_adapters.contracts import Adapter
from plugin_stack_adapters.nextjs_standalone import (
    ADAPTER,
    NextjsStandaloneAdapter,
    _OVERLAY,
)
from plugin_stack_adapters.pin_registry import get_pin
from template_cache import _store

pytestmark = pytest.mark.slow


def _next_forge_synthetic_tree() -> dict[str, bytes]:
    return {
        "package.json": (
            b'{\n'
            b'  "name": "next-forge",\n'
            b'  "version": "6.0.2",\n'
            b'  "packageManager": "pnpm@9.0.0"\n'
            b'}\n'
        ),
        "turbo.json": b'{"tasks": {"build": {}}}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "apps/*"\n  - "packages/*"\n',
        "apps/app/package.json": b'{"name": "app"}\n',
        "apps/app/middleware.ts": (
            b'import { clerkMiddleware } from "@clerk/nextjs/server";\n'
            b'export default clerkMiddleware();\n'
        ),
        "apps/app/lib/auth.ts": (
            b'import { auth } from "@clerk/nextjs/server";\n'
            b'export const session = auth();\n'
        ),
        "apps/app/components/page.tsx": (
            b'import { ClerkProvider } from "@clerk/nextjs";\n'
            b'export default function App({ children }) {\n'
            b'  return <ClerkProvider>{children}</ClerkProvider>;\n'
            b'}\n'
        ),
        "apps/storybook/package.json": b'{"name": "storybook"}\n',
        "apps/storybook/.storybook/main.ts": b'export default {};\n',
        "packages/auth/clerk.ts": b'export {};\n',
        "README.md": b"# next-forge\n",
    }


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


@pytest.fixture
def synthetic_fetcher() -> Callable[[Path], None]:
    files = _next_forge_synthetic_tree()

    def fetcher(target: Path) -> None:
        for rel, body in files.items():
            p = target / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)

    return fetcher


def test_adapter_satisfies_adapter_protocol():
    assert isinstance(ADAPTER, Adapter)


def test_stack_id_is_nextjs_standalone():
    assert ADAPTER.stack_id == "nextjs_standalone"


def test_unwrap_strategy_is_nested_turborepo():
    assert ADAPTER.unwrap_strategy == "nested_turborepo"


def test_workspace_name_is_app():
    assert ADAPTER.workspace_name == "app"


def test_manifest_schema_version_is_1_0():
    assert ADAPTER.manifest_schema_version == "1.0"


def test_upstream_points_to_pin_registry_entry():
    assert ADAPTER.upstream is not None
    assert ADAPTER.upstream["adapter_id"] == "nextjs_standalone"
    assert ADAPTER.upstream["sub_template_id"] is None


def test_pin_registry_resolves_to_next_forge_with_mit_license():
    pin = get_pin("nextjs_standalone")
    assert pin["repo_url"] == "https://github.com/vercel/next-forge"
    assert pin["license"] == "MIT"


def test_composes_with_includes_three_partners_excludes_self_and_ts_monorepo():
    partners = set(ADAPTER.composes_with.keys())
    assert partners == {"astro", "nextjs_fastapi", "generic"}
    assert "ts_monorepo" not in partners
    assert "nextjs_standalone" not in partners


def test_composes_with_nextjs_fastapi_pair_claims_app_workspace():
    rule = ADAPTER.composes_with["nextjs_fastapi"]
    assert rule["workspace_name"] == "app"


def test_overlay_config_replaces_clerk_modules():
    targets = set(_OVERLAY["replace"])
    assert "apps/app/lib/auth.ts" in targets
    assert "apps/app/middleware.ts" in targets


def test_overlay_config_removes_apps_storybook():
    assert "apps/storybook" in set(_OVERLAY["remove"])


def test_scaffold_into_materializes_upstream_into_tempdir(
    tmp_path: Path, cache_root_tmp: Path, synthetic_fetcher
):
    adapter = NextjsStandaloneAdapter(fetcher=synthetic_fetcher)
    target = tmp_path / "lp-nextjs_standalone-tmp"
    adapter.scaffold_into(target)
    assert (target / "package.json").is_file()
    assert (target / "turbo.json").is_file()
    assert (target / "apps" / "app" / "middleware.ts").is_file()


def test_apply_overlay_strips_clerk_imports_and_provider(
    tmp_path: Path, cache_root_tmp: Path, synthetic_fetcher
):
    adapter = NextjsStandaloneAdapter(fetcher=synthetic_fetcher)
    target = tmp_path / "lp-nextjs_standalone-tmp"
    adapter.scaffold_into(target)
    adapter.apply_overlay(target)
    middleware = (target / "apps" / "app" / "middleware.ts").read_text(
        encoding="utf-8"
    )
    assert "@clerk/" not in middleware
    page = (target / "apps" / "app" / "components" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "ClerkProvider" not in page
    assert "@clerk/" not in page


def test_apply_overlay_removes_apps_storybook(
    tmp_path: Path, cache_root_tmp: Path, synthetic_fetcher
):
    adapter = NextjsStandaloneAdapter(fetcher=synthetic_fetcher)
    target = tmp_path / "lp-nextjs_standalone-tmp"
    adapter.scaffold_into(target)
    adapter.apply_overlay(target)
    assert not (target / "apps" / "storybook").exists()


def test_scaffold_uses_template_cache(
    tmp_path: Path, cache_root_tmp: Path, synthetic_fetcher
):
    adapter = NextjsStandaloneAdapter(fetcher=synthetic_fetcher)
    target = tmp_path / "lp-nextjs_standalone-tmp"
    adapter.scaffold_into(target)
    pin = get_pin("nextjs_standalone")
    cached = _store.entry_path(pin["repo_url"], pin["sha"])
    assert cached.is_dir()
    assert (cached / _store.READY_SENTINEL).is_file()
