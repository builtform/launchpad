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


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


def test_freshness_finding_classifies_staleness_as_warn(lint):
    sev, msg = lint._freshness_finding("2026-01-01", today=FAR_FUTURE)
    assert sev == "warn"
    assert "old (>" in msg


def test_freshness_finding_fresh_returns_none(lint):
    assert lint._freshness_finding("2099-01-01", today=FAR_FUTURE) is None


def test_freshness_finding_malformed_is_hard_fail(lint):
    sev, _ = lint._freshness_finding("not-a-date", today=FAR_FUTURE)
    assert sev == "fail"


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
