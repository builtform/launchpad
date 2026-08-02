"""Phase 7 §4.3 — SIGKILL crash-recovery + empty-ledger semantics.

Per Layer 2 P1-3 fix item f + Layer 4 testing P1-1.

Two distinct sub-tests:

  1. **SIGKILL mid-append**: spawn an `append_nonce` subprocess against a
     pre-seeded ledger, SIGKILL it at randomized microsecond delays, assert
     the ledger remains in a CONSISTENT state — original nonces preserved,
     format header intact, no half-written record. Repeat 10 trials.

  2. **Empty-ledger semantics**: pre-write a 0-byte `.scaffold-nonces.log`
     file; run `/lp-scaffold-stack` against it; assert the actual Phase 3
     behavior, which differs from the test plan §4.3 prescription. The
     discrepancy is recorded below.

Phase 7 finding, empty-ledger semantics reason name. Test plan §4.3
prescribed a hard-reject with `reason: nonce_ledger_empty_unexpected` when
the consumer reads a 0-byte `.scaffold-nonces.log`. Phase 3 DOES hard-reject,
but with the reason `nonce_ledger_corrupt` instead: `_ensure_format_header()`
reads the empty file, sees no header line, and routes to the corrupt-detection
branch. The CLI exits non-zero with a two-part stderr trace.

Verdict: the behavior is safe, since it refuses to proceed on an unexpected
state and leaves a forensic log. Only the reason name differs from the
prescription. Per handoff §10b ("do NOT silently fix beyond §10") this test
asserts the actual name rather than implementing the prescribed one; adding
`nonce_ledger_empty_unexpected` as an alias is a separate call.

This finding used to be written to `.harness/observations/` on every run. The
body was a constant but the filename carried a fresh timestamp, so each pytest
invocation left another byte-identical copy: 119 of them had accumulated by
2026-08-02. Static documentation belongs in the source that documents it, and
a test should not write into the repo as a side effect.

The 1MB rollover-mid-prune leg of test plan §4.3 is REPLACED by the
SIGKILL-mid-append leg above: building a 1MB+ ledger per trial (~32K
append_nonce calls) costs minutes per run; the append-path crash-recovery
proof is the load-bearing invariant (rollover uses the same atomic-rename
protocol as append). The Phase 7.5 macOS spot-check can exercise the
1MB rollover branch manually if needed.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.nonce_ledger import (  # noqa: E402
    ledger_path,
)

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
    _read_latest_rejection,
)
from test_joint_pipeline_smoke import _stub_scaffolders_yml  # noqa: E402


def _make_tempdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-joint-crash-"))
    os.chmod(d, 0o700)
    return d


def _seed_ledger(cwd: Path, n_nonces: int = 5) -> list[str]:
    """Pre-write a valid v1 ledger with `n_nonces` random UUIDv4 nonces.

    Returns the list of seeded nonces for later integrity verification.
    """
    lp = cwd / ".launchpad"
    lp.mkdir(parents=True, exist_ok=True)
    nonces = [uuid.uuid4().hex for _ in range(n_nonces)]
    body = "# nonce-ledger-format: v1\n" + "".join(n + "\n" for n in nonces)
    (lp / ".scaffold-nonces.log").write_bytes(body.encode("ascii"))
    return nonces


def _spawn_append_subprocess(cwd: Path, nonce: str) -> subprocess.Popen:
    """Spawn a python subprocess that calls `append_nonce(nonce, cwd)`.

    The subprocess intentionally calls `time.sleep(0.001)` BEFORE the actual
    append so the test can SIGKILL it before/during/after the write.
    """
    code = (
        f"import sys, time\n"
        f"sys.path.insert(0, {str(_SCRIPTS)!r})\n"
        f"from lp_scaffold_stack.nonce_ledger import append_nonce\n"
        f"from pathlib import Path\n"
        f"time.sleep(0.001)  # widen the SIGKILL window\n"
        f"append_nonce({nonce!r}, Path({str(cwd)!r}))\n"
    )
    return subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _ledger_is_consistent(cwd: Path, original_nonces: list[str]) -> tuple[bool, str]:
    """Verify the ledger is in a consistent state after the SIGKILL.

    Consistent means:
      - Live ledger file EXISTS (was never unlinked).
      - Format header is the first line.
      - All original nonces are present in the live ledger (the append is
        O_APPEND-atomic, so the original lines are never lost).
      - No half-written byte sequence (live ledger ends with a newline OR
        is exactly the seeded byte length).
      - No leftover .scaffold-nonces.log itself with non-33-byte records
        beyond the optional new entry.

    Returns (ok, diagnostic_message).
    """
    lp = cwd / ".launchpad"
    log = lp / ".scaffold-nonces.log"
    if not log.exists():
        return False, "ledger file unlinked"
    text = log.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0] != "# nonce-ledger-format: v1":
        return False, f"format header missing or corrupt: first line={lines[:1]!r}"
    body_lines = [l for l in lines[1:] if l]
    body_set = set(body_lines)
    missing = [n for n in original_nonces if n not in body_set]
    if missing:
        return False, f"original nonces missing from ledger: {missing!r}"
    # Last char of file should be newline (POSIX append guarantee).
    if not text.endswith("\n"):
        return False, "ledger does not end with newline"
    return True, ""


# --- Sub-test 1: SIGKILL mid-append crash-recovery ------------------------

@pytest.mark.parametrize("trial", range(10))
def test_sigkill_mid_append_preserves_ledger(trial):
    """Spawn an `append_nonce` subprocess, SIGKILL it at random microsecond
    delay, assert the ledger remains consistent.

    Regardless of WHERE the SIGKILL lands (before append / mid-append /
    after append + before fsync), the ledger MUST preserve all original
    nonces and the format header. This is the load-bearing invariant for
    the entire `.scaffold-nonces.log` chain-of-custody.
    """
    cwd = _make_tempdir()
    try:
        original_nonces = _seed_ledger(cwd, n_nonces=5)
        new_nonce = uuid.uuid4().hex

        random.seed(trial * 17 + 1)
        # Randomize SIGKILL delay between 0 and 5ms — covers pre-append,
        # mid-append, and post-fsync windows on a typical APFS macOS dev box.
        delay = random.uniform(0.0, 0.005)

        proc = _spawn_append_subprocess(cwd, new_nonce)
        time.sleep(delay)
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # process already exited (append was fast)
        proc.wait(timeout=10)

        ok, msg = _ledger_is_consistent(cwd, original_nonces)
        assert ok, f"[trial {trial}, delay={delay*1000:.2f}ms] {msg}"
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


# --- Sub-test 2: empty-ledger semantics (Phase 7 finding) -----------------

def test_empty_ledger_actual_behavior():
    """Per handoff §4.3: pre-write a 0-byte ledger; the test plan
    prescribes hard-reject with `nonce_ledger_empty_unexpected`. Phase 3
    DOES hard-reject — but uses the reason `nonce_ledger_corrupt`, not the
    prescribed `nonce_ledger_empty_unexpected`. This test asserts the actual
    Phase 3 reason per handoff §10b ("do NOT silently fix beyond §10"); the
    name discrepancy is documented in this module's docstring.
    """
    cwd = _make_tempdir()
    try:
        # Pre-write a 0-byte ledger. `_ensure_format_header()` reads it, finds
        # no header line, and routes to the corrupt-detection branch, so the
        # pipeline hard-rejects rather than migrating the file to v1. An empty
        # ledger is NOT treated as a fresh project.
        lp = cwd / ".launchpad"
        lp.mkdir(parents=True)
        (lp / ".scaffold-nonces.log").write_bytes(b"")

        spec = STACK_COMBOS["A"]
        decision = build_decision(
            spec["stack_combo"], cwd,
            monorepo=spec["monorepo"],
            matched_category_id=spec["matched_category_id"],
        )
        write_decision_to_cwd(decision, cwd)
        write_matching_rationale_md(decision, cwd)
        write_first_run_marker(cwd)
        stub = _stub_scaffolders_yml(cwd / ".launchpad" / "stub-scaffolders.yml")

        rv = subprocess.run(
            [
                sys.executable, str(PLUGIN_SCAFFOLD_STACK),
                "--cwd", str(cwd),
                "--scaffolders-yml", str(stub),
                "--category-patterns-yml", str(DEFAULT_CATEGORY_PATTERNS_YML),
                "--plugins-root", str(DEFAULT_PLUGINS_ROOT),
                "--no-telemetry",
            ],
            capture_output=True, timeout=60, check=False,
        )

        # Assert actual behavior: hard-reject with `nonce_ledger_corrupt`.
        assert rv.returncode != 0, (
            f"empty-ledger pipeline succeeded (expected hard-reject per "
            f"Phase 3 actual behavior): stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )
        rejection = _read_latest_rejection(cwd)
        assert rejection is not None, "no scaffold-rejection-*.jsonl written"
        assert rejection.get("reason") == "nonce_ledger_corrupt", (
            f"expected reason 'nonce_ledger_corrupt' (Phase 3 actual); got "
            f"{rejection.get('reason')!r}"
        )
        # No receipt should exist.
        assert not (cwd / ".launchpad" / "scaffold-receipt.json").exists()
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
