"""Concurrent /lp-pick-stack race test (Phase 2 §4.4 T2).

Two concurrent /lp-pick-stack invocations on the same cwd should produce
exactly 1 success + 1 refusal with reason `scaffold_decision_already_exists`
(per HANDSHAKE §7 + §4.1 Step 5/6 atomic-write semantics).

The race is simulated via threading.Thread (POSIX `O_CREAT|O_EXCL` is
process-atomic; threads exercise the same path without requiring
multiprocessing.Process boilerplate). Per the v2.0 acceptance scope
(HANDSHAKE §7 concurrent-/lp-pick-stack subsection): single-process
invocation model is the contract; the O_CREAT|O_EXCL race protection is
defense-in-depth.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.engine import run_pipeline


VALID_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}


def _race_run(cwd: Path, results: list, barrier: threading.Barrier) -> None:
    """Worker: wait at the barrier, then race to write the decision file."""
    try:
        barrier.wait(timeout=5)
        result = run_pipeline(
            cwd,
            VALID_ANSWERS,
            project_description="A static blog with TypeScript islands",
            write_telemetry=False,
        )
        results.append(result)
    except Exception as exc:  # pragma: no cover — barrier timeout
        results.append(exc)


def test_concurrent_pick_stack_one_wins_one_refuses(tmp_path: Path):
    results: list = []
    barrier = threading.Barrier(2)
    t1 = threading.Thread(target=_race_run, args=(tmp_path, results, barrier))
    t2 = threading.Thread(target=_race_run, args=(tmp_path, results, barrier))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert len(results) == 2
    successes = [r for r in results if hasattr(r, "success") and r.success]
    failures = [r for r in results if hasattr(r, "success") and not r.success]
    assert len(successes) == 1, f"expected 1 success, got {len(successes)}"
    assert len(failures) == 1, f"expected 1 failure, got {len(failures)}"
    assert failures[0].reason == "scaffold_decision_already_exists"


def test_repeated_invocation_after_success_refuses(tmp_path: Path):
    """Sequential second invocation hits the O_EXCL refusal too."""
    first = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript-first islands",
        write_telemetry=False,
    )
    assert first.success
    second = run_pipeline(
        tmp_path,
        VALID_ANSWERS,
        project_description="A static blog with TypeScript-first islands",
        write_telemetry=False,
    )
    assert not second.success
    assert second.reason == "scaffold_decision_already_exists"


def test_only_one_decision_file_written(tmp_path: Path):
    """After the race, exactly one .launchpad/scaffold-decision.json exists."""
    results: list = []
    barrier = threading.Barrier(2)
    t1 = threading.Thread(target=_race_run, args=(tmp_path, results, barrier))
    t2 = threading.Thread(target=_race_run, args=(tmp_path, results, barrier))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    decisions = list((tmp_path / ".launchpad").glob("scaffold-decision.json"))
    assert len(decisions) == 1
