"""Phase 7 §4.2 — 100-iteration nonce-ledger race loop (gate #10).

Per OPERATIONS §6 acceptance gate #10. Launches two `plugin-scaffold-stack.py`
subprocesses against the SAME `scaffold-decision.json` simultaneously and
verifies the exactly-one-wins invariant: one exits 0 with a receipt; the
other exits non-zero with `reason: "nonce_seen"` (or `nonce_lock_contention`).

Stub-mode default per handoff §4.10: 10 iterations. Set `LP_PHASE7_MODE=
integration` for the full 100. Total runtime budget: <60s for 100 iters.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _phase5_decision_builder import (  # noqa: E402
    STACK_COMBOS,
    build_decision,
    write_decision_to_cwd,
    write_first_run_marker,
    write_matching_rationale_md,
)
from scaffold_smoke_runner import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
    PLUGIN_SCAFFOLD_STACK,
)
from test_joint_pipeline_smoke import _stub_scaffolders_yml  # noqa: E402


_PHASE7_MODE = os.environ.get("LP_PHASE7_MODE", "stub").lower()
_ITERATIONS = 100 if _PHASE7_MODE == "integration" else 10


def _make_tempdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-joint-race-"))
    os.chmod(d, 0o700)
    return d


def _setup_iteration(cwd: Path) -> Path:
    """Write decision + rationale + marker + stub scaffolders.yml. Returns
    the stub scaffolders.yml path."""
    spec = STACK_COMBOS["A"]
    decision = build_decision(
        spec["stack_combo"], cwd,
        monorepo=spec["monorepo"],
        matched_category_id=spec["matched_category_id"],
    )
    write_decision_to_cwd(decision, cwd)
    write_matching_rationale_md(decision, cwd)
    write_first_run_marker(cwd)
    return _stub_scaffolders_yml(cwd / ".launchpad" / "stub-scaffolders.yml")


def _spawn_two_racers(cwd: Path, scaffolders_yml: Path):
    """Spawn two CLI subprocesses against the same cwd. They race on the
    shared `.scaffold-nonces.log` ledger flock."""
    argv = [
        sys.executable, str(PLUGIN_SCAFFOLD_STACK),
        "--cwd", str(cwd),
        "--scaffolders-yml", str(scaffolders_yml),
        "--category-patterns-yml", str(DEFAULT_CATEGORY_PATTERNS_YML),
        "--plugins-root", str(DEFAULT_PLUGINS_ROOT),
        "--no-telemetry",
    ]
    p1 = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out1, err1 = p1.communicate(timeout=60)
    out2, err2 = p2.communicate(timeout=60)
    return [
        (p1.returncode, err1.decode("utf-8", errors="replace")),
        (p2.returncode, err2.decode("utf-8", errors="replace")),
    ]


def _read_rejection_reasons(cwd: Path) -> list[str]:
    obs = cwd / ".harness" / "observations"
    if not obs.exists():
        return []
    reasons: list[str] = []
    for p in sorted(obs.glob("scaffold-rejection-*.jsonl")):
        try:
            line = p.read_text(encoding="utf-8").strip().splitlines()[0]
            reasons.append(json.loads(line).get("reason", ""))
        except (OSError, json.JSONDecodeError, IndexError):
            continue
    return reasons


def _read_failed_reasons(cwd: Path) -> list[str]:
    """Read all `scaffold-failed-*.json` reasons from `.launchpad/`."""
    lp = cwd / ".launchpad"
    if not lp.exists():
        return []
    reasons: list[str] = []
    for p in sorted(lp.glob("scaffold-failed-*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            reasons.append(data.get("reason", ""))
        except (OSError, json.JSONDecodeError):
            continue
    return reasons


def _ledger_nonce_count(cwd: Path) -> int:
    """Count non-header lines in `.scaffold-nonces.log`."""
    log = cwd / ".launchpad" / ".scaffold-nonces.log"
    if not log.exists():
        return 0
    lines = log.read_text(encoding="utf-8").splitlines()
    return sum(1 for line in lines if line and not line.startswith("#"))


@pytest.mark.parametrize("iteration", range(_ITERATIONS))
def test_concurrent_scaffold_exactly_one_wins(iteration):
    """Two racers against the same decision file: exactly one wins, other
    emits `nonce_seen` (or `nonce_lock_contention`).

    Per Phase 7 handoff §4.2: if even 1 of 100 iterations violates the
    invariant, that's a flake — fail loudly. The pytest-parametrize layer
    surfaces individual iteration failures.
    """
    cwd = _make_tempdir()
    try:
        stub = _setup_iteration(cwd)
        results = _spawn_two_racers(cwd, stub)

        wins = [(rc, err) for rc, err in results if rc == 0]
        losses = [(rc, err) for rc, err in results if rc != 0]
        assert len(wins) == 1 and len(losses) == 1, (
            f"[iter {iteration}] expected exactly-one-wins; got "
            f"wins={len(wins)}, losses={len(losses)}; "
            f"results={results!r}"
        )

        # Loser's rejection log (or scaffold-failed) must mention a known
        # race-resolution reason. We check files under .harness/observations/
        # AND .launchpad/scaffold-failed-*.json — stderr is unreliable when
        # the loser's process hits a write race ahead of stderr flush.
        rejection_reasons = _read_rejection_reasons(cwd)
        failed_reasons = _read_failed_reasons(cwd)
        all_reasons = rejection_reasons + failed_reasons
        loser_err = losses[0][1]
        # The Phase 3 pipeline serializes via several nested ordering points:
        #   Step 1   — validator catches `nonce_seen` if the winner already
        #              committed the nonce ledger entry.
        #   Step 4   — `cross_cutting_wiring_collision` if the winner already
        #              wrote `lefthook.yml`/`pnpm-workspace.yaml` (O_CREAT|O_EXCL).
        #   Step 5a  — `scaffold_receipt_already_exists` if the winner already
        #              wrote `scaffold-receipt.json` (O_CREAT|O_EXCL).
        #   Ledger   — `nonce_lock_contention` if the loser's flock raced.
        # Any of these are valid exactly-one-wins resolutions; the loser
        # MUST trip exactly one of them.
        race_markers = {
            "nonce_seen", "nonce_lock_contention",
            "scaffold_receipt_already_exists",
            "cross_cutting_wiring_collision",
        }
        loser_marker_in_stderr = any(m in loser_err for m in race_markers)
        loser_marker_in_log = bool(set(all_reasons) & race_markers)
        assert loser_marker_in_stderr or loser_marker_in_log, (
            f"[iter {iteration}] no known race-resolution reason found; "
            f"stderr={loser_err[:512]!r}, "
            f"rejection_reasons={rejection_reasons!r}, "
            f"failed_reasons={failed_reasons!r}"
        )
        # Surviving ledger has exactly 1 entry.
        count = _ledger_nonce_count(cwd)
        assert count == 1, (
            f"[iter {iteration}] expected exactly 1 nonce in ledger; got "
            f"{count}; results={results!r}"
        )
        # Receipt was written.
        assert (cwd / ".launchpad" / "scaffold-receipt.json").exists(), (
            f"[iter {iteration}] no receipt despite a winner"
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
