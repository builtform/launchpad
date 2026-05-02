"""Tests for pid_identity.get_pid_start_time (HANDSHAKE §1.4 + Phase -1 §4.7).

Cross-platform format test: asserts ISO 8601 UTC sec-precision pattern.
CI lint asserts no platform-specific shell-out anywhere in code.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# psutil is a Phase -1 vendoring requirement (HANDSHAKE §1.4 + _vendor/PSUTIL_VERSION).
# Skip the test cleanly on environments where it isn't yet installed.
psutil = pytest.importorskip("psutil")

from pid_identity import get_pid_start_time


ISO_8601_UTC_SEC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_format_is_iso_8601_utc_sec_precision():
    out = get_pid_start_time()
    assert ISO_8601_UTC_SEC.fullmatch(out), (
        f"pid_start_time format violates ISO 8601 UTC sec-precision: {out!r}"
    )


def test_signature_accepts_no_arguments():
    """Layer 8 narrowing: signature accepts NO arbitrary pid argument at v2.0.
    Cross-process forensic identity is BL-223 deferred."""
    import inspect
    sig = inspect.signature(get_pid_start_time)
    assert len(sig.parameters) == 0, (
        f"get_pid_start_time must have zero parameters at v2.0; got {sig}"
    )


def test_value_is_in_the_past():
    """The current process started before this test runs."""
    from datetime import datetime, timezone
    out = get_pid_start_time()
    parsed = datetime.strptime(out, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert parsed <= datetime.now(timezone.utc)


def test_repeated_calls_consistent():
    """Same process → same start time, regardless of when called."""
    a = get_pid_start_time()
    b = get_pid_start_time()
    assert a == b
