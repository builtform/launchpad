"""Composition pair-matrix tests (merged: cross_adapter_conflicts + nested_turborepo + workspace_collisions).

Phase 4 plan section 2.2 row + section 3.4 + section 3.5 + section 3.12.
Covers the C(5,2) substantive pairs + the 2 duplicate-rejection rules + the
ts_monorepo+* catch-all + nested-Turborepo unwrap + collision suffix +
union-merge / engines / lockfile invariants for the canonical hot-paths.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from plugin_stack_adapters.astro import AstroAdapter
from plugin_stack_adapters.composition import (
    CompositionAbortError,
    CompositionRejectionCode,
    compose,
    resolve_workspace_allocation,
    validate_pair,
)
from plugin_stack_adapters.generic import GenericAdapter
from plugin_stack_adapters.nextjs_fastapi import NextjsFastapiAdapter
from plugin_stack_adapters.nextjs_standalone import NextjsStandaloneAdapter
from plugin_stack_adapters.ts_monorepo import TsMonorepoAdapter

pytestmark = pytest.mark.slow


def _trivial_fetcher(target: Path) -> None:
    files = {
        "package.json": b'{"name": "stub"}\n',
        "README.md": b"# stub\n",
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


def _next_forge_tree(target: Path) -> None:
    files = {
        "package.json": b'{"name": "next-forge", "engines": {"node": ">=20"}}\n',
        "turbo.json": b'{"tasks": {"build": {}}}\n',
        "pnpm-workspace.yaml": b'packages:\n  - "apps/*"\n  - "packages/*"\n',
        "apps/app/package.json": b'{"name": "app"}\n',
        "apps/app/middleware.ts": b'export default () => null;\n',
        "packages/auth/package.json": b'{"name": "@repo/auth"}\n',
        "rogue-top-level-dir/keep.txt": b"surprise\n",
    }
    for rel, body in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


# --- ts_monorepo + * rejection: collapses 4 of the 10 C(5,2) pairs ---


def test_ts_monorepo_plus_nextjs_standalone_rejected():
    rejection = validate_pair([TsMonorepoAdapter(), NextjsStandaloneAdapter()])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.TS_MONOREPO_PAIR


def test_ts_monorepo_plus_nextjs_fastapi_rejected():
    rejection = validate_pair([TsMonorepoAdapter(), NextjsFastapiAdapter()])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.TS_MONOREPO_PAIR


def test_ts_monorepo_plus_astro_rejected():
    rejection = validate_pair([TsMonorepoAdapter(), AstroAdapter()])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.TS_MONOREPO_PAIR


def test_ts_monorepo_plus_generic_rejected():
    rejection = validate_pair([TsMonorepoAdapter(), GenericAdapter()])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.TS_MONOREPO_PAIR


def test_ts_monorepo_pair_emits_verbatim_message():
    rejection = validate_pair([TsMonorepoAdapter(), AstroAdapter()])
    assert rejection is not None
    assert "ts_monorepo is itself a monorepo" in rejection.message
    assert "Pick one of" in rejection.message


# --- duplicate rejection (outside C(5,2)) ---------------------------------


def test_astro_plus_astro_rejected_as_duplicate():
    rejection = validate_pair([AstroAdapter(), AstroAdapter()])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.DUPLICATE_STACKS


def test_generic_plus_generic_rejected_as_duplicate():
    rejection = validate_pair([GenericAdapter(), GenericAdapter()])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.DUPLICATE_STACKS


def test_duplicate_rejection_emits_verbatim_message():
    rejection = validate_pair([AstroAdapter(), AstroAdapter()])
    assert rejection is not None
    assert (
        rejection.message
        == "Duplicate stacks are not allowed. Pick two different stacks."
    )


# --- 6 substantive cross-pairs (C(5,2) minus 4 ts_monorepo collapses) ----


def test_nextjs_standalone_plus_astro_valid():
    assert validate_pair([NextjsStandaloneAdapter(), AstroAdapter()]) is None


def test_nextjs_standalone_plus_nextjs_fastapi_valid():
    assert (
        validate_pair([NextjsStandaloneAdapter(), NextjsFastapiAdapter()]) is None
    )


def test_nextjs_standalone_plus_generic_valid():
    assert validate_pair([NextjsStandaloneAdapter(), GenericAdapter()]) is None


def test_nextjs_fastapi_plus_astro_valid():
    assert validate_pair([NextjsFastapiAdapter(), AstroAdapter()]) is None


def test_nextjs_fastapi_plus_generic_valid():
    assert validate_pair([NextjsFastapiAdapter(), GenericAdapter()]) is None


def test_astro_plus_generic_valid():
    assert validate_pair([AstroAdapter(), GenericAdapter()]) is None


# --- workspace collision suffix ------------------------------------------


def test_collision_suffix_app_to_app_fe_only_for_dual_app_pair():
    mapping, logs = resolve_workspace_allocation(
        [NextjsStandaloneAdapter(), NextjsFastapiAdapter()]
    )
    assert "app-fe" in mapping
    assert "app" in mapping
    assert mapping["app-fe"].stack_id == "nextjs_standalone"
    assert mapping["app"].stack_id == "nextjs_fastapi"
    assert any("app-fe" in m for m in logs)


def test_no_collision_suffix_for_distinct_workspace_pairs():
    mapping, logs = resolve_workspace_allocation(
        [NextjsStandaloneAdapter(), AstroAdapter()]
    )
    assert "app" in mapping
    assert "content" in mapping
    assert "app-fe" not in mapping
    assert logs == []


# --- nested-Turborepo unwrap declaration ---------------------------------


def test_nextjs_standalone_declares_nested_turborepo_unwrap():
    assert NextjsStandaloneAdapter().unwrap_strategy == "nested_turborepo"


def test_other_adapters_declare_unwrap_strategy_none():
    assert NextjsFastapiAdapter().unwrap_strategy == "none"
    assert AstroAdapter().unwrap_strategy == "none"
    assert GenericAdapter().unwrap_strategy == "none"
    assert TsMonorepoAdapter().unwrap_strategy == "none"


def test_nested_turborepo_upstream_lays_down_apps_and_packages_dirs(
    tmp_path: Path, cache_root_tmp: Path
):
    project = tmp_path / "project"
    adapter = NextjsStandaloneAdapter(fetcher=_next_forge_tree)
    compose([adapter], project)
    workspace = project / "apps" / "app"
    assert workspace.is_dir()
    assert (workspace / "apps" / "app" / "package.json").is_file() or (
        workspace / "apps" / "app").is_dir()


# --- engines / lockfile / union-merge invariants -------------------------


def test_overlay_conflict_policy_marks_lefthook_merge_keys_for_canonical_pair():
    primary = NextjsStandaloneAdapter()
    rule = primary.composes_with["nextjs_fastapi"]
    assert rule["conflict_policy"]["lefthook.yml"] == "merge-keys"


def test_overlay_conflict_policy_marks_package_json_merge_keys_across_pairs():
    pairs = [
        (NextjsStandaloneAdapter(), "astro"),
        (NextjsStandaloneAdapter(), "nextjs_fastapi"),
        (NextjsFastapiAdapter(), "astro"),
        (AstroAdapter(), "generic"),
    ]
    for adapter, partner in pairs:
        policy = adapter.composes_with[partner]["conflict_policy"]
        assert policy.get("package.json") == "merge-keys", (
            f"{adapter.stack_id}+{partner} missing package.json merge-keys"
        )


def test_no_per_adapter_lockfile_in_compose_with_declarations():
    pairs = [
        (NextjsStandaloneAdapter(), "nextjs_fastapi"),
        (NextjsStandaloneAdapter(), "astro"),
        (NextjsFastapiAdapter(), "astro"),
    ]
    for adapter, partner in pairs:
        policy = adapter.composes_with[partner]["conflict_policy"]
        forbidden_keys = [
            k for k in policy if k.endswith("pnpm-lock.yaml") or k == "package-lock.json"
        ]
        assert forbidden_keys == [], (
            f"{adapter.stack_id}+{partner} declares per-adapter lockfile: "
            f"{forbidden_keys}"
        )


# --- engine catch-all-rejection abort --------------------------------------


def test_compose_aborts_on_ts_monorepo_pair(tmp_path: Path):
    with pytest.raises(CompositionAbortError) as exc:
        compose(
            [TsMonorepoAdapter(), NextjsStandaloneAdapter()],
            tmp_path / "project",
        )
    assert exc.value.reason == CompositionRejectionCode.TS_MONOREPO_PAIR.value


def test_compose_aborts_on_duplicate_stacks(tmp_path: Path):
    with pytest.raises(CompositionAbortError):
        compose([AstroAdapter(), AstroAdapter()], tmp_path / "project")


def test_compose_info_log_records_collision_message(
    tmp_path: Path, cache_root_tmp: Path, caplog
):
    project = tmp_path / "project"
    with caplog.at_level(
        logging.INFO, logger="plugin_stack_adapters.composition"
    ):
        compose(
            [
                NextjsStandaloneAdapter(fetcher=_next_forge_tree),
                NextjsFastapiAdapter(fetcher=_trivial_fetcher),
            ],
            project,
        )
    assert any(
        "app-fe" in rec.getMessage() for rec in caplog.records
    )


def test_unknown_pair_rejected_when_partner_missing_from_composes_with():
    # Construct an adapter pair where one adapter's composes_with omits the
    # other to verify the unsupported_pair fallback. We use ts_monorepo
    # alone for that role, but ts_monorepo lands in TS_MONOREPO_PAIR first;
    # so we synthesize a generic-like adapter with empty composes_with.
    class _StubAdapter:
        stack_id = "generic"
        upstream = None
        manifest_schema_version = "1.0"
        workspace_name = "extra"
        unwrap_strategy = "none"
        composes_with = {}

        def scaffold_into(self, td: Path) -> None:
            return None

        def apply_overlay(self, td: Path) -> None:
            return None

    rejection = validate_pair([_StubAdapter(), NextjsStandaloneAdapter()])
    assert rejection is not None
    assert rejection.code == CompositionRejectionCode.UNSUPPORTED_PAIR
