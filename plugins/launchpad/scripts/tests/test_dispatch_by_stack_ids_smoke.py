"""Step 0 proof-of-life smoke for `dispatch_by_stack_ids`.

Per `docs/plans/launchpad_plans/2026-05-08-v2.1.0-completion-plan.md` §3.0:
exercises `dispatch_by_stack_ids` against `tmp_path` for ALL 5 active
stack-ids + 1 composition before §3.1+ touches `engine.py`. Halt rule:
any failure means the dispatch surface has hidden bugs and the
architectural rewire (§3.3) is unsafe to land. Run all 6 cases (do NOT
stop at first failure).

Hermetic: no network. fetcher-loaded singletons replace the module-level
ADAPTERs for the upstream-needing adapters (nextjs_*, astro); ts_monorepo
and generic use their real singletons (no fetcher required).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from lp_scaffold_stack.v21_adapter_dispatch import dispatch_by_stack_ids
from plugin_stack_adapters.composition import CompositionResult
from plugin_stack_adapters import (
    astro as astro_mod,
    nextjs_fastapi as nextjs_fastapi_mod,
    nextjs_standalone as nextjs_standalone_mod,
)


def _next_forge_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "next-forge", "private": true}\n',
        "turbo.json": b'{"tasks": {"build": {}}}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "apps/*"\n  - "packages/*"\n',
        "apps/app/package.json": b'{"name": "app"}\n',
        "apps/app/middleware.ts": b'export default () => null;\n',
        "packages/auth/package.json": b'{"name": "@repo/auth"}\n',
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def _vinta_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "vinta-template"}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "app"\n',
        "app/package.json": b'{"name": "frontend"}\n',
        "app/pages/index.tsx": b'export default () => null;\n',
        "api/main.py": b"app = 'fastapi'\n",
        "api/requirements.txt": b"fastapi==0.115.0\n",
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def _astro_tree(target: Path) -> None:
    """Mirror withastro/astro's `examples/portfolio` (the default
    "marketing" sub-template per `astro._DEFAULT_SUB_TEMPLATE`)."""
    files = {
        "examples/portfolio/package.json": b'{"name": "portfolio"}\n',
        "examples/portfolio/src/content/index.md": b"# portfolio\n",
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


@pytest.fixture
def hermetic_dispatch_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Redirect template cache + swap upstream-needing ADAPTERs for
    fetcher-loaded instances so `dispatch_by_stack_ids` runs without network."""
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(tmp_path / "lp-template-cache"))
    monkeypatch.setattr(
        nextjs_standalone_mod,
        "ADAPTER",
        nextjs_standalone_mod.NextjsStandaloneAdapter(fetcher=_next_forge_tree),
    )
    monkeypatch.setattr(
        nextjs_fastapi_mod,
        "ADAPTER",
        nextjs_fastapi_mod.NextjsFastapiAdapter(fetcher=_vinta_tree),
    )
    monkeypatch.setattr(
        astro_mod,
        "ADAPTER",
        astro_mod.AstroAdapter(fetcher=_astro_tree),
    )
    return tmp_path


@pytest.mark.parametrize(
    "stack_id",
    ["ts_monorepo", "nextjs_standalone", "nextjs_fastapi", "astro", "generic"],
)
def test_dispatch_single_id_smoke(
    stack_id: str, hermetic_dispatch_env: Path
) -> None:
    """Per plan §3.0: each of the 5 active stack-ids dispatches via
    `dispatch_by_stack_ids` and produces a Path with at least one file
    (or, for ts_monorepo/generic which are pure project shells, a
    populated workspace dir)."""
    workspace = hermetic_dispatch_env / f"smoke-{stack_id}"
    result = dispatch_by_stack_ids([stack_id], workspace)
    assert isinstance(result, Path), f"{stack_id}: expected Path, got {type(result).__name__}"
    assert result == workspace
    assert workspace.is_dir()
    files = [p for p in workspace.rglob("*") if p.is_file()]
    if stack_id in {"nextjs_standalone", "nextjs_fastapi", "astro"}:
        assert files, (
            f"{stack_id}: workspace empty after dispatch — fetcher/cache wiring broken"
        )


def test_dispatch_composition_smoke(hermetic_dispatch_env: Path) -> None:
    """Per plan §3.0: 1 multi-id composition smoke. Use
    nextjs_standalone + astro (a valid composition pair per
    `_COMPOSES_WITH`). Asserts `CompositionResult.placed_paths` is
    non-empty — the architectural fix in §3.3 depends on this surface."""
    workspace = hermetic_dispatch_env / "smoke-composition"
    result = dispatch_by_stack_ids(["nextjs_standalone", "astro"], workspace)
    assert isinstance(result, CompositionResult), (
        f"composition: expected CompositionResult, got {type(result).__name__}"
    )
    assert result.placed_paths, "composition: placed_paths empty — composition.compose() broken"
