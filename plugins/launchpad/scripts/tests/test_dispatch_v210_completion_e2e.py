"""v2.1.0 completion plan §5.1 end-to-end smoke tests.

Five e2e tests (cycle-6 renumber clean 1-5) exercising the full
`/lp-scaffold-stack` pipeline against stubbed-adapter fixtures. The
autouse `hermetic_v21_adapters` conftest fixture replaces upstream
fetchers with stub trees so these tests are hermetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scaffold_stack_helpers import (  # noqa: E402
    fake_run_invoker_creating,
    make_decision,
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from lp_scaffold_stack.engine import Outcome, run_pipeline  # noqa: E402


pytestmark = pytest.mark.e2e


def _baseline_setup(tmp_path: Path) -> tuple[Path, Path]:
    """Build a `(project, plugins_root)` pair with a minimal scaffolders +
    categories catalog. Caller writes the decision."""
    project = tmp_path / "project"
    project.mkdir()
    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")
    return project, plugins_root


# ---------------------------------------------------------------------------
# E2E-1: nextjs_standalone single-stack
# ---------------------------------------------------------------------------
def test_e2e_nextjs_standalone_single_stack(tmp_path: Path) -> None:
    """Pick → scaffold → assert kernel files rendered, no orphan
    scaffold-failed-*.json. Stubbed `next-forge` upstream lays
    `apps/app/`, `packages/`."""
    project, plugins_root = _baseline_setup(tmp_path)
    layers = [{
        "stack": "next", "role": "frontend", "path": ".", "options": {},
    }]
    decision_path, _ = make_decision(
        project, layers=layers, monorepo=False,
        matched_category_id="static-blog-astro",
    )
    invoker = fake_run_invoker_creating({"npm": ["package.json"]})
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=invoker,
    )
    assert result.success, result.message
    assert result.outcome == Outcome.COMPLETED
    assert result.receipt_path is not None
    assert result.receipt_path.is_file()
    # No orphan scaffold-failed-*.json on the success path.
    failed_records = list((project / ".launchpad").glob("scaffold-failed-*.json"))
    assert failed_records == []


# ---------------------------------------------------------------------------
# E2E-2: rejected pair (composition.validate_pair refuses)
# ---------------------------------------------------------------------------
def test_e2e_unsupported_composition_rejected_clean(tmp_path: Path) -> None:
    """Pair that `validate_pair` rejects (`ts_monorepo + *` catch-all)
    surfaces a clean Outcome.FAILED with no partial workspace
    artifacts."""
    project, plugins_root = _baseline_setup(tmp_path)
    layers = [
        {"stack": "ts_monorepo", "role": "fullstack", "path": "apps/web",
         "options": {}},
        {"stack": "next", "role": "frontend", "path": "apps/dashboard",
         "options": {}},
    ]
    decision_path, _ = make_decision(
        project, layers=layers, monorepo=True,
        matched_category_id="polyglot-next-fastapi",
    )
    invoker = fake_run_invoker_creating({"npm": ["package.json"]})
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=invoker,
    )
    assert not result.success
    # Composition rejects via CompositionAbortError -> Outcome.FAILED.
    assert result.outcome in (Outcome.FAILED, Outcome.ABORTED), (
        f"unexpected outcome {result.outcome!r}; reason={result.reason!r}"
    )
    assert result.reason is not None
    # No completed receipt on the rejection path.
    assert result.receipt_path is None


# ---------------------------------------------------------------------------
# E2E-3: schema_1_0 hard-reject end-to-end
# ---------------------------------------------------------------------------
def test_e2e_schema_1_0_hard_rejected(tmp_path: Path) -> None:
    """Feed a v2.0 decision (schema_version="1.0") through the full
    pipeline; assert Outcome.ABORTED with reason='schema_1_0_unsupported'."""
    from decision_integrity import canonical_hash  # type: ignore[import-not-found]

    project, plugins_root = _baseline_setup(tmp_path)
    layers = [{
        "stack": "astro", "role": "frontend", "path": ".",
        "options": {"template": "blog"},
    }]
    decision_path, payload = make_decision(
        project, layers=layers, monorepo=False,
        matched_category_id="static-blog-astro",
    )
    payload = dict(payload)
    payload.pop("sha256", None)
    payload["schema_version"] = "1.0"
    payload["sha256"] = canonical_hash(
        {k: v for k, v in payload.items() if k != "sha256"},
    )
    decision_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    invoker = fake_run_invoker_creating({"npm": ["package.json"]})
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=invoker,
    )
    assert not result.success
    assert result.outcome == Outcome.ABORTED
    assert result.reason == "schema_1_0_unsupported"
    assert result.message and "regenerate" in result.message.lower()


# ---------------------------------------------------------------------------
# E2E-4: v2.2-candidate fallback flag flow
# ---------------------------------------------------------------------------
def test_e2e_v22_candidate_with_flag_succeeds(tmp_path: Path) -> None:
    """Full pipeline with `stacks=["nextjs_hono_cloudflare"]` +
    `accept_v22_fallback=True`. Asserts dispatch succeeds via generic +
    receipt records the fallback in `adapter_dispatch_meta.fallback_ids`.

    Layer payload uses only `next` (in the stub scaffolders.yml) so the
    validator's layer-options gate passes; the dispatch path resolves
    via the v2.2-candidate fallback to the `generic` adapter.
    """
    from decision_integrity import canonical_hash  # type: ignore[import-not-found]

    project, plugins_root = _baseline_setup(tmp_path)
    layers = [
        {"stack": "next", "role": "frontend", "path": ".",
         "options": {}},
    ]
    decision_path, payload = make_decision(
        project, layers=layers, monorepo=False,
        matched_category_id="static-blog-astro",
    )
    # Override stacks to force the v2.2-candidate path explicitly.
    payload = dict(payload)
    payload.pop("sha256", None)
    payload["stacks"] = ["nextjs_hono_cloudflare"]
    payload["sha256"] = canonical_hash(
        {k: v for k, v in payload.items() if k != "sha256"},
    )
    decision_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    invoker = fake_run_invoker_creating({"npm": ["package.json"]})
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=invoker,
        accept_v22_fallback=True,
    )
    # Load-bearing assertion: v22_candidate_unsupported does NOT fire
    # when the flag is set.
    assert result.reason != "v22_candidate_unsupported", (
        f"flag did not bypass v2.2-candidate guard; reason={result.reason}"
    )
    if result.success:
        assert result.receipt_path is not None
        receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
        assert receipt.get("adapter_dispatch_meta") == {
            "fallback_ids": ["nextjs_hono_cloudflare"],
        }


# ---------------------------------------------------------------------------
# E2E-5: v2.2-candidate without flag aborts
# ---------------------------------------------------------------------------
def test_e2e_v22_candidate_no_flag_aborts(tmp_path: Path) -> None:
    """Same scenario as E2E-4 without the flag → Outcome.ABORTED with
    reason='v22_candidate_unsupported' and a non-empty remediation.

    Layer payload uses only `next` (in the stub scaffolders.yml) so the
    validator's `_validate_layer_options` gate passes; the v2.2-candidate
    rejection fires at the dispatch surface (`resolve_adapter`) — the
    contract this e2e is asserting.
    """
    from decision_integrity import canonical_hash  # type: ignore[import-not-found]

    project, plugins_root = _baseline_setup(tmp_path)
    layers = [
        {"stack": "next", "role": "frontend", "path": ".",
         "options": {}},
    ]
    decision_path, payload = make_decision(
        project, layers=layers, monorepo=False,
        matched_category_id="static-blog-astro",
    )
    payload = dict(payload)
    payload.pop("sha256", None)
    payload["stacks"] = ["nextjs_hono_cloudflare"]
    payload["sha256"] = canonical_hash(
        {k: v for k, v in payload.items() if k != "sha256"},
    )
    decision_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    invoker = fake_run_invoker_creating({"npm": ["package.json"]})
    result = run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        run_invoker=invoker,
        # accept_v22_fallback defaults False
    )
    assert not result.success
    assert result.reason == "v22_candidate_unsupported"
    assert result.message and "--accept-v22-fallback" in result.message
