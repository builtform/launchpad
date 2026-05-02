"""Phase 5 smoke-test driver — Tests A through I.

Per Phase 5 handoff §4.1, this module ships TWO use-faces:

1. **pytest discoverable**: each test is a `test_smoke_<id>_<name>` function,
   selectable via `pytest -k smoke_a` / `pytest -k smoke_h` / etc.
2. **direct CLI invocation**: `python3 scaffold_smoke_runner.py [--allow-dirty]
   [--only=A,B,C,...] [--mode={stub,integration}]` for ad-hoc batch runs,
   producing a final summary table with elapsed-time-per-test.

Each test follows the contract from handoff §4.3-§4.6:
  1. tempfile.mkdtemp(prefix="lp-scaffold-test-", mode=0o700)
  2. build_decision() + write_decision_to_cwd() + write_matching_rationale_md()
     + write_first_run_marker()
  3. invoke `python3 plugin-scaffold-stack.py --cwd <tmpdir>` via subprocess
  4. assert per-test acceptance criteria
  5. cleanup tempdir (atexit-style via shutil.rmtree)

§4.8 Tool detection: orchestrate scaffolders need tools (npm/npx, uv, ruby,
expo, supabase). When the prereq tool is absent, the test emits SKIP-WITH-STUB
and writes a synthetic receipt containing `skipped_reason: "tool_missing:..."`
— the driver-level test still PASSES, but its assertions degrade to
"stub written correctly." (Curate scaffolders e.g. fastapi need NO tools at
scaffold time and always run for real.)

§5 mode flag: pytest invocations default to `mode=stub` (set via env var
`LP_PHASE5_MODE`) so the test suite stays fast (seconds, not minutes). CI or
manual sessions can flip to `mode=integration` to actually spawn the
orchestrate scaffolders. Tests that never spawn (B/H/I + adversarial corpus)
ignore the mode flag entirely.

§5 isolation guard: direct invocation refuses to run when `os.getcwd()` is
inside a git working tree (would scaffold INTO the repo) unless the user
passes `--allow-dirty`. pytest invocations skip the guard (pytest is itself
running inside the repo).

§5 4h time-box: each subprocess invocation is wrapped in
`subprocess.run(timeout=14400)`. On TimeoutExpired the test is marked
BLOCKED:timeout in direct mode, and the pytest test fails with a clear
diagnostic.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import cwd_state  # noqa: E402

from _phase5_decision_builder import (  # noqa: E402
    STACK_COMBOS,
    build_decision,
    write_decision_to_cwd,
    write_first_run_marker,
    write_matching_rationale_md,
)


# --- §4.8 Tool probes -------------------------------------------------------

TOOL_PROBES: dict[str, list[str]] = {
    "pnpm": ["pnpm", "--version"],
    "npm": ["npm", "--version"],
    "npx": ["npx", "--version"],
    "uv": ["uv", "--version"],
    "bundle": ["bundle", "--version"],
    "ruby": ["ruby", "--version"],
    "expo": ["npx", "expo", "--version"],
    "supabase": ["supabase", "--version"],
}

# Cache so we probe each tool ONCE per process, even across many tests.
_TOOL_CACHE: dict[str, bool] = {}

# Path to the CLI we drive (single source of truth — tests invoke this).
PLUGIN_SCAFFOLD_STACK = (
    _SCRIPTS / "plugin-scaffold-stack.py"
)

# Path to the scaffolders catalog and category-patterns catalog (full v2.0
# 10-stack catalog — tests use the real catalog for realism).
DEFAULT_SCAFFOLDERS_YML = (
    _SCRIPTS.parent / "scaffolders.yml"
)
DEFAULT_CATEGORY_PATTERNS_YML = (
    _SCRIPTS / "lp_pick_stack" / "data" / "category-patterns.yml"
)
DEFAULT_PLUGINS_ROOT = _SCRIPTS.parent.parent.parent

# Per-test timeout per handoff §5 (4h ≈ 14400s; capped here for safety).
PER_TEST_TIMEOUT_SECONDS = int(os.environ.get("LP_PHASE5_TIMEOUT", "14400"))

# Phase 5 mode — `stub` (fast, default) skips real-scaffolder spawn for
# orchestrate tests; `integration` runs them for real when the tool is
# present. See module docstring §5.
PHASE5_MODE = os.environ.get("LP_PHASE5_MODE", "stub").lower()


@dataclass
class SmokeResult:
    """Result row for the per-test summary table.

    Class deliberately NOT named `Test*` to avoid pytest's auto-collection
    of `Test*`-prefixed classes (PytestCollectionWarning).
    """

    test_id: str
    name: str
    status: str  # "PASS" | "FAIL" | "SKIP-WITH-STUB" | "SKIP" | "BLOCKED"
    elapsed_seconds: float
    detail: str = ""
    tempdir: Path | None = None


def _probe_tool(name: str) -> bool:
    """Returns True if the tool is available on PATH. Cached per-process."""
    if name in _TOOL_CACHE:
        return _TOOL_CACHE[name]
    argv = TOOL_PROBES.get(name)
    if argv is None:
        _TOOL_CACHE[name] = False
        return False
    try:
        rv = subprocess.run(
            argv, capture_output=True, timeout=10, check=False,
        )
        present = rv.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        present = False
    _TOOL_CACHE[name] = present
    return present


def _make_tempdir() -> Path:
    """tempfile.mkdtemp with the Phase 5 prefix + 0o700 mode (handoff §4.1)."""
    d = tempfile.mkdtemp(prefix="lp-scaffold-test-")
    os.chmod(d, 0o700)
    return Path(d)


def _cleanup_tempdir(tempdir: Path) -> None:
    """Best-effort recursive cleanup; never raises."""
    try:
        shutil.rmtree(tempdir, ignore_errors=True)
    except OSError:
        pass


def _invoke_cli(
    cwd: Path,
    *,
    extra_args: list[str] | None = None,
    timeout: int = PER_TEST_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    """Run the scaffold-stack CLI against `cwd`. Returns CompletedProcess."""
    argv = [
        sys.executable, str(PLUGIN_SCAFFOLD_STACK),
        "--cwd", str(cwd),
        "--scaffolders-yml", str(DEFAULT_SCAFFOLDERS_YML),
        "--category-patterns-yml", str(DEFAULT_CATEGORY_PATTERNS_YML),
        "--plugins-root", str(DEFAULT_PLUGINS_ROOT),
        "--no-telemetry",
    ]
    if extra_args:
        argv.extend(extra_args)
    return subprocess.run(
        argv, capture_output=True, timeout=timeout, check=False,
    )


def _write_synthetic_receipt(
    cwd: Path,
    *,
    skipped_reason: str,
    layers: list[dict[str, Any]],
) -> Path:
    """SKIP-WITH-STUB receipt write per handoff §4.8.

    The synthetic receipt is intentionally NOT canonical-hash sealed — it
    carries `skipped_reason` instead, which consumer-side loaders treat as
    "this is a stub, not a real scaffold receipt." This is the driver-level
    fallback; production receipts are always sealed via
    `receipt_writer.seal_receipt_payload()`.
    """
    target = cwd / ".launchpad" / "scaffold-receipt.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "skipped_reason": skipped_reason,
        "layers_materialized": [
            {"stack": layer["stack"], "path": layer["path"],
             "scaffolder_used": "stub", "files_created": ["<stub>"]}
            for layer in layers
        ],
        "cross_cutting_files": [],
        "toolchains_detected": [],
        "secret_scan_passed": True,
    }
    target.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return target


def _read_receipt(cwd: Path) -> dict | None:
    """Read scaffold-receipt.json from a test cwd. Returns None if absent."""
    p = cwd / ".launchpad" / "scaffold-receipt.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_latest_rejection(cwd: Path) -> dict | None:
    """Read the most recent .harness/observations/scaffold-rejection-*.jsonl
    file. Returns the parsed payload or None if absent."""
    obs = cwd / ".harness" / "observations"
    if not obs.exists():
        return None
    rejections = sorted(obs.glob("scaffold-rejection-*.jsonl"))
    if not rejections:
        return None
    try:
        # Each file is a single JSON line.
        line = rejections[-1].read_text(encoding="utf-8").strip().splitlines()[0]
        return json.loads(line)
    except (json.JSONDecodeError, OSError, IndexError):
        return None


# --- Per-test driver helpers -----------------------------------------------

def _run_orchestrate_test(
    test_id: str,
    name: str,
    *,
    required_tools: list[str],
) -> SmokeResult:
    """Standard runner for orchestrate-scaffolder tests (A, C, D, E, F, G).

    Behavior:
      - In `stub` mode (default): SKIP-WITH-STUB regardless of tool presence.
      - In `integration` mode: probe tools; if any absent → SKIP-WITH-STUB;
        if all present → invoke the real CLI.

    Returns a SmokeResult with status PASS / SKIP-WITH-STUB / FAIL / BLOCKED.
    """
    start = time.monotonic()
    spec = STACK_COMBOS[test_id]
    tempdir = _make_tempdir()
    try:
        decision = build_decision(
            spec["stack_combo"], tempdir,
            monorepo=spec["monorepo"],
            matched_category_id=spec["matched_category_id"],
        )
        write_decision_to_cwd(decision, tempdir)
        write_matching_rationale_md(decision, tempdir)
        write_first_run_marker(tempdir)

        missing = [t for t in required_tools if not _probe_tool(t)]
        if PHASE5_MODE == "stub" or missing:
            why = (
                f"tool_missing:{','.join(missing)}" if missing
                else "phase5_mode=stub (set LP_PHASE5_MODE=integration to spawn)"
            )
            _write_synthetic_receipt(
                tempdir,
                skipped_reason=why,
                layers=spec["stack_combo"],
            )
            elapsed = time.monotonic() - start
            return SmokeResult(
                test_id=test_id, name=name, status="SKIP-WITH-STUB",
                elapsed_seconds=elapsed, detail=f"reason: {why}",
                tempdir=tempdir,
            )

        # Integration mode + all tools present — run the real CLI.
        try:
            rv = _invoke_cli(tempdir)
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return SmokeResult(
                test_id=test_id, name=name, status="BLOCKED",
                elapsed_seconds=elapsed,
                detail=f"timeout after {PER_TEST_TIMEOUT_SECONDS}s",
                tempdir=tempdir,
            )

        elapsed = time.monotonic() - start
        if rv.returncode != 0:
            return SmokeResult(
                test_id=test_id, name=name, status="FAIL",
                elapsed_seconds=elapsed,
                detail=(
                    f"CLI exit {rv.returncode}; "
                    f"stderr={rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
                ),
                tempdir=tempdir,
            )
        receipt = _read_receipt(tempdir)
        if receipt is None or "sha256" not in receipt:
            return SmokeResult(
                test_id=test_id, name=name, status="FAIL",
                elapsed_seconds=elapsed,
                detail="scaffold-receipt.json missing or unsigned",
                tempdir=tempdir,
            )
        layers = receipt.get("layers_materialized") or []
        if not layers or not any(layer.get("files_created") for layer in layers):
            return SmokeResult(
                test_id=test_id, name=name, status="FAIL",
                elapsed_seconds=elapsed,
                detail="layers_materialized empty or files_created empty",
                tempdir=tempdir,
            )
        return SmokeResult(
            test_id=test_id, name=name, status="PASS",
            elapsed_seconds=elapsed,
            detail=f"layers={len(layers)}, sha256={receipt['sha256'][:12]}...",
            tempdir=tempdir,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return SmokeResult(
            test_id=test_id, name=name, status="FAIL",
            elapsed_seconds=elapsed, detail=f"unexpected: {exc!r}",
            tempdir=tempdir,
        )


def _run_curate_test(test_id: str, name: str) -> SmokeResult:
    """Runner for curate-only tests (B = fastapi). No spawn — always real CLI."""
    start = time.monotonic()
    spec = STACK_COMBOS[test_id]
    tempdir = _make_tempdir()
    try:
        decision = build_decision(
            spec["stack_combo"], tempdir,
            monorepo=spec["monorepo"],
            matched_category_id=spec["matched_category_id"],
        )
        write_decision_to_cwd(decision, tempdir)
        write_matching_rationale_md(decision, tempdir)
        write_first_run_marker(tempdir)

        try:
            rv = _invoke_cli(tempdir, timeout=120)
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return SmokeResult(
                test_id=test_id, name=name, status="BLOCKED",
                elapsed_seconds=elapsed, detail="timeout after 120s",
                tempdir=tempdir,
            )

        elapsed = time.monotonic() - start
        if rv.returncode != 0:
            return SmokeResult(
                test_id=test_id, name=name, status="FAIL",
                elapsed_seconds=elapsed,
                detail=(
                    f"CLI exit {rv.returncode}; "
                    f"stderr={rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
                ),
                tempdir=tempdir,
            )
        receipt = _read_receipt(tempdir)
        if receipt is None or "sha256" not in receipt:
            return SmokeResult(
                test_id=test_id, name=name, status="FAIL",
                elapsed_seconds=elapsed,
                detail="scaffold-receipt.json missing or unsigned",
                tempdir=tempdir,
            )
        layers = receipt.get("layers_materialized") or []
        # Curate emits README.scaffold.md → files_created length should be ≥1.
        if not any(layer.get("files_created") for layer in layers):
            return SmokeResult(
                test_id=test_id, name=name, status="FAIL",
                elapsed_seconds=elapsed, detail="files_created empty",
                tempdir=tempdir,
            )
        return SmokeResult(
            test_id=test_id, name=name, status="PASS",
            elapsed_seconds=elapsed,
            detail=f"layers={len(layers)}, sha256={receipt['sha256'][:12]}...",
            tempdir=tempdir,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return SmokeResult(
            test_id=test_id, name=name, status="FAIL",
            elapsed_seconds=elapsed, detail=f"unexpected: {exc!r}",
            tempdir=tempdir,
        )


# --- Test functions --------------------------------------------------------
# Each `_run_<id>()` returns a SmokeResult. The corresponding `test_smoke_<id>`
# pytest function asserts that result.status is in {PASS, SKIP-WITH-STUB} and
# emits a clear failure message otherwise.

def _run_a() -> SmokeResult:
    return _run_orchestrate_test(
        "A", "Astro static-blog (Mode 1: orchestrate)",
        required_tools=["pnpm", "npx"],
    )


def _run_b() -> SmokeResult:
    return _run_curate_test("B", "FastAPI backend (Mode 2: curate)")


def _run_c() -> SmokeResult:
    return _run_orchestrate_test(
        "C", "Polyglot Next + FastAPI (Mode 3)",
        required_tools=["pnpm", "npx"],
    )


def _run_d() -> SmokeResult:
    return _run_orchestrate_test(
        "D", "Rails 8 monolith",
        required_tools=["bundle", "ruby"],
    )


def _run_e() -> SmokeResult:
    return _run_orchestrate_test(
        "E", "Supabase + Next auth-gated",
        required_tools=["supabase", "npx"],
    )


def _run_f() -> SmokeResult:
    return _run_orchestrate_test(
        "F", "Multi-frontend Astro + Next dashboard",
        required_tools=["pnpm", "npx"],
    )


def _run_g() -> SmokeResult:
    """Test G is OPTIONAL per handoff §4.4 — clean SKIP if Expo absent."""
    if not _probe_tool("expo"):
        return SmokeResult(
            test_id="G", name="Expo mobile (optional)",
            status="SKIP", elapsed_seconds=0.0,
            detail="Expo CLI absent — Test G is optional per handoff §4.4",
        )
    return _run_orchestrate_test(
        "G", "Expo mobile (optional)",
        required_tools=["expo", "npx"],
    )


def _run_h() -> SmokeResult:
    """Brownfield refusal per handoff §4.5.

    Pre-populate package.json in the tmpdir → CLI must reject with
    `cwd_state_brownfield` AND emit a scaffold-rejection-<ts>.jsonl in
    .harness/observations/.
    """
    start = time.monotonic()
    spec = STACK_COMBOS["H"]
    tempdir = _make_tempdir()
    try:
        # Pre-populate brownfield indicator (package.json triggers cwd_state →
        # brownfield via cwd_state.BROWNFIELD_MANIFESTS).
        (tempdir / "package.json").write_text(
            '{"name":"existing-project"}', encoding="utf-8",
        )
        decision = build_decision(
            spec["stack_combo"], tempdir,
            monorepo=spec["monorepo"],
            matched_category_id=spec["matched_category_id"],
        )
        write_decision_to_cwd(decision, tempdir)
        write_matching_rationale_md(decision, tempdir)
        # NB: do NOT write first-run-marker — brownfield should refuse before
        # marker consumption.

        try:
            rv = _invoke_cli(tempdir, timeout=60)
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return SmokeResult(
                test_id="H", name="Brownfield refusal",
                status="BLOCKED", elapsed_seconds=elapsed,
                detail="timeout after 60s", tempdir=tempdir,
            )

        elapsed = time.monotonic() - start
        if rv.returncode == 0:
            return SmokeResult(
                test_id="H", name="Brownfield refusal",
                status="FAIL", elapsed_seconds=elapsed,
                detail="CLI accepted brownfield cwd (expected reject)",
                tempdir=tempdir,
            )
        # No scaffold-receipt should exist.
        if (tempdir / ".launchpad" / "scaffold-receipt.json").exists():
            return SmokeResult(
                test_id="H", name="Brownfield refusal",
                status="FAIL", elapsed_seconds=elapsed,
                detail="receipt was written despite brownfield refusal",
                tempdir=tempdir,
            )
        # Verify scaffold-rejection-<ts>.jsonl was written with the expected
        # reason (read taxonomy directly from Phase 3's engine.py Step 0:
        # cwd_state == "brownfield" → reason "cwd_state_brownfield").
        rejection = _read_latest_rejection(tempdir)
        if rejection is None:
            return SmokeResult(
                test_id="H", name="Brownfield refusal",
                status="FAIL", elapsed_seconds=elapsed,
                detail="no scaffold-rejection-*.jsonl written under .harness/observations/",
                tempdir=tempdir,
            )
        if rejection.get("reason") != "cwd_state_brownfield":
            return SmokeResult(
                test_id="H", name="Brownfield refusal",
                status="FAIL", elapsed_seconds=elapsed,
                detail=(
                    f"unexpected rejection reason: {rejection.get('reason')!r} "
                    f"(expected 'cwd_state_brownfield')"
                ),
                tempdir=tempdir,
            )
        # Verify two-part stderr surfacing (handoff §4.5: Part 1 reason
        # BEFORE write, Part 2 path AFTER).
        stderr_text = rv.stderr.decode("utf-8", errors="replace")
        part1_seen = "reason: cwd_state_brownfield" in stderr_text
        part2_seen = (
            "log written to:" in stderr_text or "forensic log unavailable" in stderr_text
        )
        if not (part1_seen and part2_seen):
            return SmokeResult(
                test_id="H", name="Brownfield refusal",
                status="FAIL", elapsed_seconds=elapsed,
                detail=(
                    f"two-part stderr surfacing missing: part1={part1_seen}, "
                    f"part2={part2_seen}; stderr={stderr_text[:512]!r}"
                ),
                tempdir=tempdir,
            )
        return SmokeResult(
            test_id="H", name="Brownfield refusal",
            status="PASS", elapsed_seconds=elapsed,
            detail=f"reason={rejection['reason']}, two-part stderr seen",
            tempdir=tempdir,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return SmokeResult(
            test_id="H", name="Brownfield refusal",
            status="FAIL", elapsed_seconds=elapsed,
            detail=f"unexpected: {exc!r}", tempdir=tempdir,
        )


def _simulate_brainstorm_phase0(cwd: Path) -> bool:
    """Simulate the /lp-brainstorm Phase 0 cwd_state routing per HANDSHAKE §7
    + commands/lp-brainstorm.md Phase 0 (read by handoff §4.6).

    Per the routing logic: ONLY proceed with marker write when state == "empty".
    For brownfield/ambiguous cwds, the marker MUST NOT be written.

    Returns True if the marker was written, False if the routing skipped.
    """
    state = cwd_state(cwd)
    if state != "empty":
        # Routing skipped marker write per HANDSHAKE §7 brainstorm contract.
        return False
    # Greenfield path: write the marker (matches Phase 0 lp-brainstorm.md).
    target = cwd / ".launchpad" / ".first-run-marker"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    return True


def _run_i() -> SmokeResult:
    """`.first-run-marker` brownfield-skip per handoff §4.6.

    Pre-populate package.json in the tmpdir; simulate `/lp-brainstorm` Phase 0
    routing; assert NO `.launchpad/.first-run-marker` is created.
    """
    start = time.monotonic()
    tempdir = _make_tempdir()
    try:
        (tempdir / "package.json").write_text(
            '{"name":"existing-project"}', encoding="utf-8",
        )
        wrote = _simulate_brainstorm_phase0(tempdir)
        elapsed = time.monotonic() - start
        marker = tempdir / ".launchpad" / ".first-run-marker"
        if wrote:
            return SmokeResult(
                test_id="I", name="first-run-marker brownfield-skip",
                status="FAIL", elapsed_seconds=elapsed,
                detail="Phase 0 wrote marker into a brownfield cwd",
                tempdir=tempdir,
            )
        if marker.exists():
            return SmokeResult(
                test_id="I", name="first-run-marker brownfield-skip",
                status="FAIL", elapsed_seconds=elapsed,
                detail="marker file exists after brownfield Phase 0",
                tempdir=tempdir,
            )
        return SmokeResult(
            test_id="I", name="first-run-marker brownfield-skip",
            status="PASS", elapsed_seconds=elapsed,
            detail="brownfield routing skipped marker write (cwd_state=brownfield)",
            tempdir=tempdir,
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return SmokeResult(
            test_id="I", name="first-run-marker brownfield-skip",
            status="FAIL", elapsed_seconds=elapsed,
            detail=f"unexpected: {exc!r}", tempdir=tempdir,
        )


# --- Pytest test functions -------------------------------------------------

def _assert_test_result(result: SmokeResult) -> None:
    """Pass on PASS / SKIP-WITH-STUB / SKIP; fail otherwise. Cleanup tempdir
    after assertion (we keep the tempdir during assertion so failure
    diagnostics can inspect it; we still clean up post-test)."""
    try:
        if result.status in {"PASS", "SKIP-WITH-STUB", "SKIP"}:
            return
        # FAIL or BLOCKED — surface the detail.
        pytest.fail(
            f"[{result.test_id}] {result.name}: {result.status} "
            f"({result.elapsed_seconds:.2f}s) — {result.detail}"
        )
    finally:
        if result.tempdir is not None:
            _cleanup_tempdir(result.tempdir)


def test_smoke_a_astro_static_blog():
    _assert_test_result(_run_a())


def test_smoke_b_fastapi_curate():
    _assert_test_result(_run_b())


def test_smoke_c_polyglot_next_fastapi():
    _assert_test_result(_run_c())


def test_smoke_d_rails_monolith():
    _assert_test_result(_run_d())


def test_smoke_e_supabase_next():
    _assert_test_result(_run_e())


def test_smoke_f_multi_frontend_astro_next():
    _assert_test_result(_run_f())


def test_smoke_g_expo_mobile_optional():
    _assert_test_result(_run_g())


def test_smoke_h_brownfield_refusal():
    _assert_test_result(_run_h())


def test_smoke_i_first_run_marker_brownfield_skip():
    _assert_test_result(_run_i())


# --- Negative test for the isolation guard (handoff §6 acceptance) ---------

def test_isolation_guard_refuses_git_repo_without_allow_dirty(tmp_path):
    """Negative test: invoke the smoke runner directly inside a git repo
    without `--allow-dirty` and assert it refuses.

    Builds a temp git repo (so we don't lean on the LaunchPad repo state) and
    invokes scaffold_smoke_runner.py from there — the guard should fire.
    """
    # Make tmp_path a git repo.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, timeout=30)
    rv = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--only=H"],
        cwd=str(tmp_path),
        capture_output=True, timeout=60, check=False,
    )
    # Refusal: non-zero exit + stderr mentions "git" + "allow-dirty".
    assert rv.returncode != 0, (
        f"isolation guard did not refuse git-repo cwd: stdout={rv.stdout!r}, "
        f"stderr={rv.stderr!r}"
    )
    stderr = rv.stderr.decode("utf-8", errors="replace")
    assert "git" in stderr.lower() and "allow-dirty" in stderr.lower(), (
        f"refusal stderr does not mention 'git' + 'allow-dirty': {stderr!r}"
    )


# --- Direct CLI invocation (`python3 scaffold_smoke_runner.py`) ------------

ALL_TESTS: list[tuple[str, Callable[[], SmokeResult]]] = [
    ("A", _run_a),
    ("B", _run_b),
    ("C", _run_c),
    ("D", _run_d),
    ("E", _run_e),
    ("F", _run_f),
    ("G", _run_g),
    ("H", _run_h),
    ("I", _run_i),
]


def _isolation_guard(allow_dirty: bool) -> None:
    """Refuse direct invocation if cwd is inside a git repo unless --allow-dirty
    is set. Per handoff §4.1.

    Pytest invocation does NOT call this — the guard fires only at __main__.
    """
    if allow_dirty:
        return
    try:
        rv = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, timeout=10, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return  # git not installed → no repo to refuse
    if rv.returncode == 0 and rv.stdout.strip() == b"true":
        print(
            "scaffold_smoke_runner: cwd is inside a git working tree; refuse "
            "to run without --allow-dirty (would scaffold INTO the repo).",
            file=sys.stderr,
        )
        sys.exit(2)


def _format_summary(results: list[SmokeResult], wall_seconds: float) -> str:
    """Build the per-test summary table (handoff §4.1.4)."""
    lines = [
        "",
        "=" * 78,
        "Phase 5 smoke-runner summary",
        "=" * 78,
        f"{'ID':<3} {'STATUS':<16} {'ELAPSED':>9}  NAME",
        "-" * 78,
    ]
    for r in results:
        lines.append(
            f"{r.test_id:<3} {r.status:<16} {r.elapsed_seconds:>7.2f}s  {r.name}"
        )
        if r.detail:
            lines.append(f"      └ {r.detail}")
    lines.append("-" * 78)
    counts = {s: sum(1 for r in results if r.status == s)
              for s in ("PASS", "FAIL", "SKIP-WITH-STUB", "SKIP", "BLOCKED")}
    summary = " | ".join(f"{k}={v}" for k, v in counts.items() if v)
    lines.append(f"Totals: {summary}")
    lines.append(f"Wall time: {wall_seconds:.2f}s "
                 f"(phase cap: {18*3600}s = 18h per handoff §5)")
    lines.append("=" * 78)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 5 scaffold-stack smoke-test driver. "
                    "Runs Tests A-I against per-test temp directories.",
    )
    parser.add_argument(
        "--allow-dirty", action="store_true",
        help="Bypass the git-repo isolation guard (handoff §4.1).",
    )
    parser.add_argument(
        "--only", default="",
        help="Comma-separated subset of test IDs (e.g. --only=A,H,I).",
    )
    parser.add_argument(
        "--mode", choices=["stub", "integration"], default=None,
        help=("'stub' (default in pytest): SKIP-WITH-STUB orchestrate tests; "
              "'integration': spawn real scaffolders when tools present."),
    )
    args = parser.parse_args(argv)

    _isolation_guard(args.allow_dirty)
    if args.mode is not None:
        global PHASE5_MODE
        PHASE5_MODE = args.mode

    only_ids = {t.strip().upper() for t in args.only.split(",") if t.strip()}
    selected = [
        (tid, fn) for tid, fn in ALL_TESTS
        if not only_ids or tid in only_ids
    ]

    phase_start = time.monotonic()
    results: list[SmokeResult] = []
    blocked_count = 0
    phase_cap_seconds = 18 * 3600
    for tid, fn in selected:
        if (time.monotonic() - phase_start) > phase_cap_seconds:
            print(f"phase-level 18h cap reached; aborting", file=sys.stderr)
            break
        result = fn()
        results.append(result)
        if result.tempdir is not None:
            _cleanup_tempdir(result.tempdir)
        if result.status == "BLOCKED":
            blocked_count += 1
            if blocked_count >= 3:
                print("3+ tests BLOCKED; needs design rework, not iteration "
                      "(handoff §4.1.6)", file=sys.stderr)
                break

    wall = time.monotonic() - phase_start
    print(_format_summary(results, wall))
    # Exit non-zero if any mandatory test (A-F + H + I + adversarial) failed.
    # Test G is optional per §4.4.
    mandatory = {"A", "B", "C", "D", "E", "F", "H", "I"}
    failures = [r for r in results
                if r.test_id in mandatory and r.status in {"FAIL", "BLOCKED"}]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
