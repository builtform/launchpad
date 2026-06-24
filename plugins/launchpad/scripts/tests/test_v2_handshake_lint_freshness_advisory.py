"""Regression: catalog/pattern `last_validated:` staleness is ADVISORY in the
default PR lint and HARD-gating under `--check-freshness` (release time).

Rationale: re-stamping the catalog is a time-based maintenance task unrelated to
the content of any given PR, so a lapsed window must not block unrelated changes
(e.g. a Dependabot bump). The window is enforced at release via the explicit
gate. See plugin-v2-handshake-lint.py:_freshness_finding and SCAFFOLD_OPERATIONS
§4.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
LINT_SCRIPT = (
    REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin-v2-handshake-lint.py"
)
FRESHNESS_SCRIPT = (
    REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin-freshness-check.py"
)

# A date far enough past every shipped `last_validated:` to force staleness
# regardless of when the suite runs.
FAR_FUTURE = _dt.date(2099, 1, 1)
FRESH = _dt.date(2026, 6, 23)


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("v2_lint_freshness", LINT_SCRIPT)
    assert spec is not None and spec.loader is not None, (
        f"could not load lint module from {LINT_SCRIPT}"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v2_lint_freshness"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_freshness_module():
    spec = importlib.util.spec_from_file_location("freshness_check", FRESHNESS_SCRIPT)
    assert spec is not None and spec.loader is not None, (
        f"could not load freshness module from {FRESHNESS_SCRIPT}"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["freshness_check"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


@pytest.fixture(scope="module")
def freshness():
    return _load_freshness_module()


def test_freshness_finding_classifies_staleness_as_warn(lint):
    sev, msg = lint._freshness_finding("2026-01-01", today=FAR_FUTURE)
    assert sev == "warn"
    assert "old (>" in msg


def test_freshness_finding_fresh_returns_none(lint):
    assert lint._freshness_finding("2099-01-01", today=FAR_FUTURE) is None


def test_freshness_finding_malformed_is_hard_fail(lint):
    sev, _ = lint._freshness_finding("not-a-date", today=FAR_FUTURE)
    assert sev == "fail"


def test_freshness_finding_malformed_containing_staleness_marker_is_hard_fail(lint):
    """Codex PR #104 P1 regression: a malformed value that happens to contain
    the staleness-message substring ("d old (>") must still classify as a
    structural hard failure, not an advisory warning. The earlier substring-
    sentinel implementation misclassified this as "warn"."""
    for malformed in ("d old (>", "0d old (>30d window)", "x is 1d old (>30d window)"):
        sev, msg = lint._freshness_finding(malformed, today=FRESH)
        assert sev == "fail", f"{malformed!r} must be structural fail, got {sev}"
        assert "unparseable" in msg


def test_freshness_finding_future_dated_is_hard_fail(lint):
    sev, msg = lint._freshness_finding("2030-01-01", today=FRESH)
    assert sev == "fail"
    assert "future" in msg


def test_freshness_finding_wrong_type_is_hard_fail(lint):
    sev, _ = lint._freshness_finding(None, today=FRESH)
    assert sev == "fail"


def test_anchor_doc_staleness_routes_to_warnings_not_failures(lint):
    """With a far-future `today`, the (currently fresh) pattern docs read as
    stale. In the default (advisory) mode they must land in `warnings`, leaving
    `failures` empty."""
    failures: list[str] = []
    warnings: list[str] = []
    lint.check_anchor_doc_freshness(failures, today=FAR_FUTURE, warnings=warnings)
    assert failures == [], f"staleness leaked into failures: {failures}"
    assert warnings, "expected advisory staleness warnings"
    assert all("old (>" in w for w in warnings)


def test_anchor_doc_staleness_blocks_when_freshness_blocking(lint):
    """The release-time gate flips staleness into a hard failure."""
    failures: list[str] = []
    warnings: list[str] = []
    lint.check_anchor_doc_freshness(
        failures, today=FAR_FUTURE, warnings=warnings, freshness_blocking=True
    )
    assert failures, "expected staleness to block under freshness_blocking"
    assert warnings == []


def test_scaffolders_catalog_staleness_routes_to_warnings_not_failures(lint):
    """Greptile PR #104 P2 regression: the same advisory-vs-blocking routing
    that anchor-doc staleness has must hold for check_scaffolders_catalog, so a
    future refactor cannot silently drop the warnings path. With a far-future
    `today` the (otherwise valid) catalog entries read as stale and must land in
    `warnings`, leaving `failures` empty."""
    failures: list[str] = []
    warnings: list[str] = []
    lint.check_scaffolders_catalog(failures, today=FAR_FUTURE, warnings=warnings)
    assert failures == [], f"staleness leaked into failures: {failures}"
    assert warnings, "expected advisory staleness warnings"
    assert all("old (>" in w for w in warnings)


def test_scaffolders_catalog_staleness_blocks_when_freshness_blocking(lint):
    failures: list[str] = []
    warnings: list[str] = []
    lint.check_scaffolders_catalog(
        failures, today=FAR_FUTURE, warnings=warnings, freshness_blocking=True
    )
    assert failures, "expected staleness to block under freshness_blocking"
    assert warnings == []


def test_category_patterns_catalog_staleness_routes_to_warnings_not_failures(lint):
    """Greptile PR #104 P2 regression: parallel routing guarantee for
    check_category_patterns_catalog. It needs scaffolder_ids to avoid spurious
    cross-reference failures, so we seed it from check_scaffolders_catalog."""
    seed_failures: list[str] = []
    scaffolder_ids = lint.check_scaffolders_catalog(seed_failures, today=FRESH)
    failures: list[str] = []
    warnings: list[str] = []
    lint.check_category_patterns_catalog(
        failures,
        scaffolder_ids=scaffolder_ids,
        today=FAR_FUTURE,
        warnings=warnings,
    )
    assert failures == [], f"staleness leaked into failures: {failures}"
    assert warnings, "expected advisory staleness warnings"
    assert all("old (>" in w for w in warnings)


def test_category_patterns_catalog_staleness_blocks_when_freshness_blocking(lint):
    seed_failures: list[str] = []
    scaffolder_ids = lint.check_scaffolders_catalog(seed_failures, today=FRESH)
    failures: list[str] = []
    warnings: list[str] = []
    lint.check_category_patterns_catalog(
        failures,
        scaffolder_ids=scaffolder_ids,
        today=FAR_FUTURE,
        warnings=warnings,
        freshness_blocking=True,
    )
    assert failures, "expected staleness to block under freshness_blocking"
    assert warnings == []


def test_default_lint_is_time_robust_against_staleness(lint):
    """The default lint must stay green regardless of how stale the shipped
    catalog dates have become — that time-independence is the whole fix. We do
    NOT assert run_check_freshness_gate() here against the real dates: that gate
    is intentionally time-dependent (it goes red >30d after a re-stamp), so
    asserting it green in the always-run suite would re-introduce the very
    time-bomb this change removes. The gate's blocking behavior is covered by
    test_anchor_doc_staleness_blocks_when_freshness_blocking with a fixed
    `today`."""
    assert lint.run_default_lint() == 0


# --- Release-time FULL §4 freshness contract (plugin-freshness-check.py) ---
# Codex PR #104 P1: the catalog-subset gate (--check-freshness) omits
# pillar-framework.md and the SCAFFOLD_HANDSHAKE/OPERATIONS contract docs. The
# release workflow closes that gap by also running plugin-freshness-check.py
# --gating, which owns the complete §4 target list. These tests lock the full
# list and the gating behavior in with fixed dates (no real-date dependency).

# The catalog-subset gate (run_check_freshness_gate) deliberately does NOT cover
# these three; the full release gate must.
_CONTRACT_ONLY_TARGETS = (
    "plugins/launchpad/scripts/lp_pick_stack/data/pillar-framework.md",
    "docs/architecture/SCAFFOLD_HANDSHAKE.md",
    "docs/architecture/SCAFFOLD_OPERATIONS.md",
)
_CATALOG_TARGETS = (
    "plugins/launchpad/scaffolders.yml",
    "plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml",
)


def test_release_freshness_gate_covers_full_operations_4_target_set(freshness):
    """Time-robust: the canonical gate's target enumeration must include the
    full §4 set — both the catalog files AND the three the catalog-subset gate
    omits (pillar-framework + the two contract docs) — plus the pattern-doc
    glob. This is the direct lock against the P1 coverage gap reopening."""
    enumerated = {
        p.resolve().relative_to(REPO_ROOT).as_posix()
        for p in freshness._enumerate_targets()
    }
    for required in (*_CATALOG_TARGETS, *_CONTRACT_ONLY_TARGETS):
        assert required in enumerated, f"{required} missing from release freshness gate"
    assert any(p.endswith("-pattern.md") for p in enumerated), (
        "expected scaffolders/*-pattern.md docs in the target set"
    )


def test_release_freshness_gate_blocks_on_stale_with_fixed_date(freshness):
    """Gating mode returns 1 when targets are stale (FAR_FUTURE forces every
    shipped date past the window). Fixed date — never flaky."""
    assert freshness.check_freshness(advisory=False, today=FAR_FUTURE) == 1


def test_release_freshness_gate_advisory_mode_never_fails(freshness):
    """PR-context advisory mode prints findings but always returns 0, even when
    everything is stale — the property that keeps PRs unblocked."""
    assert freshness.check_freshness(advisory=True, today=FAR_FUTURE) == 0
