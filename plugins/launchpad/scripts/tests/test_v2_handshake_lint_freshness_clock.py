"""Regression: the freshness clock is UTC and tolerates one day of stamp skew.

Two properties are pinned here, both of which a UTC-only test would assert
vacuously (on a UTC runner `date.today()` and `datetime.now(UTC).date()` are
identical, so a revert to local time is invisible unless the test shifts TZ):

  1. `_today_utc()` is UTC-based, not local. `plugin-freshness-check.py` gates
     an overlapping file set in the adjacent release step, and the two must
     agree on "today".
  2. `_freshness_finding` tolerates a `last_validated` stamp up to one day
     ahead of UTC. `last_validated` is hand-authored, and a contributor as far
     east as UTC+14 writing their local date legitimately produces tomorrow's
     UTC date. That branch returns `fail` and is NOT gated by
     `freshness_blocking`, so a false positive there blocks unrelated PRs.

See plugin-v2-handshake-lint.py:_today_utc / _freshness_finding.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
LINT_SCRIPT = (
    REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin-v2-handshake-lint.py"
)

# UTC+14 and UTC-12: the two extremes of real-world offsets. On either side of
# UTC, `date.today()` can disagree with the UTC date.
TZ_EAST = "Pacific/Kiritimati"  # UTC+14
TZ_WEST = "Etc/GMT+12"  # UTC-12


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("v2_lint_clock", LINT_SCRIPT)
    assert spec is not None and spec.loader is not None, (
        f"could not load lint module from {LINT_SCRIPT}"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v2_lint_clock"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


@pytest.fixture
def in_timezone():
    """Run the body under a fixed TZ, restoring the process clock afterwards.

    Deliberately does NOT use `monkeypatch.setenv`: monkeypatch restores the
    env var in ITS finalizer, which runs *after* this fixture's post-yield
    code. A `time.tzset()` here would therefore re-read the still-shifted TZ
    and leak it into every subsequent test in the session. Restore the value
    ourselves, then tzset, so ordering is explicit.
    """
    original = os.environ.get("TZ")

    def _set(tz: str) -> None:
        os.environ["TZ"] = tz
        time.tzset()

    try:
        yield _set
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()


@pytest.mark.parametrize("tz", [TZ_EAST, TZ_WEST, "UTC"])
def test_today_utc_ignores_local_timezone(lint, in_timezone, tz):
    """`_today_utc()` must equal the UTC date regardless of local TZ."""
    in_timezone(tz)
    assert lint._today_utc() == _dt.datetime.now(_dt.UTC).date()


def test_today_utc_differs_from_local_today_in_the_far_east(lint, in_timezone):
    """Guard the guard: prove the TZ shift actually moves `date.today()`.

    Without this, `test_today_utc_ignores_local_timezone` could pass on a
    machine where tzset() silently no-ops, making the whole file vacuous.
    """
    in_timezone(TZ_EAST)
    if _dt.date.today() == _dt.datetime.now(_dt.UTC).date():
        pytest.skip("UTC+14 local date coincides with UTC right now")
    assert lint._today_utc() != _dt.date.today()


def test_stamp_one_day_ahead_of_utc_is_tolerated(lint):
    """A hand-stamped UTC+14 local date must not hard-fail."""
    today = _dt.date(2026, 7, 31)
    tomorrow = today + _dt.timedelta(days=1)
    assert lint._freshness_finding(tomorrow.isoformat(), today=today) is None


def test_stamp_two_days_ahead_still_fails(lint):
    """Tolerance is exactly one day; a real typo must still be caught."""
    today = _dt.date(2026, 7, 31)
    way_ahead = today + _dt.timedelta(days=2)
    finding = lint._freshness_finding(way_ahead.isoformat(), today=today)
    assert finding is not None
    severity, message = finding
    assert severity == "fail"
    assert "is in the future" in message


def test_wrong_year_stamp_still_fails(lint):
    """The error class that matters (wrong year) is unaffected by tolerance."""
    today = _dt.date(2026, 7, 31)
    finding = lint._freshness_finding("2027-07-31", today=today)
    assert finding is not None
    assert finding[0] == "fail"
