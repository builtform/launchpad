"""Shared pytest fixtures for the LaunchPad scripts test suite.

`lp_define_invoke` -- session-scoped fixture wrapping the v2.1 /lp-define
orchestrator (lp_define_runner.py).

`hermetic_v21_adapters` -- autouse function-scoped fixture replacing the
upstream-fetching ADAPTER singletons (`nextjs_standalone`, `nextjs_fastapi`,
`astro`) with stub-fetcher instances. Tests that exercise
`dispatch_by_stack_ids` indirectly through `run_pipeline` no longer touch
the network; tests that want real fetcher behavior (e.g.
`test_v21_adapter_dispatch.py`'s `slow` markers) can pass real adapter
instances directly to `dispatch_single_adapter`/`dispatch_composition`,
which bypasses the singleton swap.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
_VENDOR = _SCRIPTS / "plugin_stack_adapters" / "_vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _next_forge_stub(target: Path) -> None:
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


def _vinta_stub(target: Path) -> None:
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


def _astro_stub(target: Path) -> None:
    """`withastro/astro` `examples/portfolio` mirror — the default
    `astro/marketing` sub-template per `astro._DEFAULT_SUB_TEMPLATE`."""
    files = {
        "examples/portfolio/package.json": b'{"name": "portfolio"}\n',
        "examples/portfolio/src/content/index.md": b"# portfolio\n",
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def _prepopulate_template_cache(cache_root: Path) -> None:
    """Pre-populate the template cache with stub trees at the registered
    pinned SHAs so subprocess invocations of /lp-scaffold-stack (which
    cannot see this conftest's monkeypatched ADAPTER singletons) hit the
    cache instead of the network.

    Each cache entry follows the `template_cache._store` shape:
      - `<cache_root>/<slug>@<sha>/<files>` — content
      - `.ready` sentinel
      - `.fetched_at` timestamp
      - `.expected_files.json` manifest
    """
    import json
    from plugin_stack_adapters.pin_registry import _PINS

    stubs: dict[tuple[str, str | None], dict[str, bytes]] = {
        ("nextjs_standalone", None): {
            "package.json": b'{"name": "next-forge", "private": true}\n',
            "turbo.json": b'{"tasks": {"build": {}}}\n',
            "pnpm-workspace.yaml": (
                b'packages:\n  - "apps/*"\n  - "packages/*"\n'
            ),
            "apps/app/package.json": b'{"name": "app"}\n',
            "apps/app/middleware.ts": b'export default () => null;\n',
            "packages/auth/package.json": b'{"name": "@repo/auth"}\n',
        },
        ("nextjs_fastapi", None): {
            "package.json": b'{"name": "vinta-template"}\n',
            "pnpm-workspace.yaml": b'packages:\n  - "app"\n',
            "app/package.json": b'{"name": "frontend"}\n',
            "app/pages/index.tsx": b'export default () => null;\n',
            "api/main.py": b"app = 'fastapi'\n",
            "api/requirements.txt": b"fastapi==0.115.0\n",
        },
        ("astro", "marketing"): {
            "examples/portfolio/package.json": b'{"name": "portfolio"}\n',
            "examples/portfolio/src/content/index.md": b"# portfolio\n",
        },
    }

    cache_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    locks = cache_root / ".locks"
    locks.mkdir(mode=0o700, parents=True, exist_ok=True)

    for key, files in stubs.items():
        if key not in _PINS:
            continue
        pin = _PINS[key]
        slug = (
            pin["repo_url"]
            .removeprefix("https://github.com/")
            .removesuffix(".git")
            .rstrip("/")
            .replace("/", "-")
        )
        entry = cache_root / f"{slug}@{pin['sha']}"
        if entry.exists():
            continue
        entry.mkdir(mode=0o700, parents=True, exist_ok=True)
        for rel, body in files.items():
            p = entry / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
        manifest = sorted(files.keys())
        (entry / ".expected_files.json").write_text(
            json.dumps({"files": manifest}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        (entry / ".fetched_at").write_text(
            "2026-05-08T00:00:00Z\n", encoding="utf-8",
        )
        (entry / ".ready").write_text("ok\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def hermetic_v21_adapters(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v2.1.0 completion plan §3.3: replace upstream-fetching ADAPTER
    singletons with stub-fetcher instances so the v2.1 dispatch path runs
    hermetically by default. Opt out by adding the `real_v21_adapters`
    marker to a test (used by `test_v21_adapter_dispatch.py` slow tests).

    Also redirects `LAUNCHPAD_CACHE_DIR` to a per-test tempdir AND
    pre-populates that tempdir with stub trees at every adapter's pinned
    SHA. The pre-populate path covers subprocess invocations of
    /lp-scaffold-stack — those run in a separate Python process and
    cannot see the in-process ADAPTER monkeypatch, but they DO inherit
    the env var and read the cache.
    """
    if "real_v21_adapters" in request.keywords:
        return
    cache_root = tmp_path_factory.mktemp("lp-template-cache-test")
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(cache_root))
    try:
        from plugin_stack_adapters import (
            astro as astro_mod,
            nextjs_fastapi as nextjs_fastapi_mod,
            nextjs_standalone as nextjs_standalone_mod,
        )
    except ImportError:  # pragma: no cover - adapter modules optional
        return
    monkeypatch.setattr(
        nextjs_standalone_mod,
        "ADAPTER",
        nextjs_standalone_mod.NextjsStandaloneAdapter(fetcher=_next_forge_stub),
    )
    monkeypatch.setattr(
        nextjs_fastapi_mod,
        "ADAPTER",
        nextjs_fastapi_mod.NextjsFastapiAdapter(fetcher=_vinta_stub),
    )
    monkeypatch.setattr(
        astro_mod,
        "ADAPTER",
        astro_mod.AstroAdapter(fetcher=_astro_stub),
    )
    _prepopulate_template_cache(cache_root)


@pytest.fixture(scope="session")
def lp_define_invoke():
    """Return a callable `(repo_root, **kwargs) -> int` that invokes the
    v2.1 /lp-define orchestrator in-process. Emits banner suppressed by
    default; callers can override by passing `emit_trust_banner=True`.

    Phase 8.5 plan section 2.1 surface for test_define + test_pipeline_matrix
    migrations. Renderer environment instantiation amortizes across the
    test session via the LpDefineRenderer's loader cache.
    """
    import lp_define_runner

    def _invoke(repo_root: Path, **kwargs) -> int:
        kwargs.setdefault("emit_trust_banner", False)
        return lp_define_runner.generate(repo_root, **kwargs)

    return _invoke
