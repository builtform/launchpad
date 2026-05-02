"""Phase 7 §4.1 — joint pipeline smoke (brainstorm → pick-stack → scaffold → define).

Drives the full v2.0 pipeline end-to-end against a single greenfield tmpdir
in stub mode (handoff §4.10). Three variants per handoff §4.1 final paragraph:

  - **canonical**: clean Markdown blog input → all 4 phases succeed.
  - **adversarial-sanitization**: input contains a script-tag bullet →
    pick-stack `extract_summary` filters it out (defense-in-depth);
    scaffold-stack succeeds with a clean decision.
  - **brownfield-refusal**: pre-populate package.json BEFORE scaffold step →
    scaffold-stack rejects with `cwd_state_brownfield`; pipeline halts.

Each phase's verification is shape-based (does the receipt load? does the
decision validate?) rather than UI-shape — `/lp-brainstorm` and `/lp-define`
are Claude-driven markdown commands, so we simulate their cwd_state-routing
and receipt-consumption logic in Python.

Stub-mode default: scaffold-stack is invoked via the CLI but with the
synthetic-receipt fast-path that Phase 5 introduced (orchestrate scaffolders
mocked when `LP_PHASE7_MODE=stub`). Total runtime budget: <10s.
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

from cwd_state import cwd_state  # noqa: E402

from lp_pick_stack.engine import Outcome as PickStackOutcome  # noqa: E402
from lp_pick_stack.engine import run_pipeline as pick_stack_run  # noqa: E402

from scaffold_smoke_runner import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
    DEFAULT_SCAFFOLDERS_YML,
    PLUGIN_SCAFFOLD_STACK,
    _read_latest_rejection,
)


PLUGIN_SCAFFOLD_RECEIPT_LOADER = (
    _SCRIPTS / "plugin-scaffold-receipt-loader.py"
)


def _make_tempdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-joint-smoke-"))
    os.chmod(d, 0o700)
    return d


def _stub_scaffolders_yml(target: Path) -> Path:
    """Write a stub scaffolders.yml that re-types astro as `curate` (drops
    the knowledge-anchor as `README.scaffold.md`, no `npm create` spawn).

    Per Phase 7 handoff §4.10 stub-mode default: tests must not depend on
    real-tool spawn. The production catalog uses `orchestrate` for astro
    (spawns `npm create astro@latest`) which would fail in CI/tests without
    network and pnpm scaffolding noise. Re-typing to `curate` keeps the
    full §4 validation pipeline + receipt write path under test while
    skipping the scaffolder spawn itself.

    Reuses the real `knowledge_anchor` + `knowledge_anchor_sha256` from the
    production catalog so the curate-mode `read_and_verify` succeeds.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    # Read the real anchor sha256 from the production catalog so we don't
    # hardcode/drift.
    real_catalog = (
        _SCRIPTS.parent / "scaffolders.yml"
    ).read_text(encoding="utf-8")
    import re
    astro_sha = re.search(
        r"astro:.*?knowledge_anchor_sha256:\s*\"([0-9a-f]{64})\"",
        real_catalog, re.DOTALL,
    ).group(1)
    target.write_text(
        f"""schema_version: "1.0"
stacks:
  astro:
    pillar: "Frontend Content/Performance"
    type: "curate"
    flavor: "n/a"
    knowledge_anchor: "plugins/launchpad/scaffolders/astro-pattern.md"
    knowledge_anchor_sha256: "{astro_sha}"
    options_schema:
      template: "string"
    last_validated: "2026-04-30"
""",
        encoding="utf-8",
    )
    return target


# --- Phase 1: simulated /lp-brainstorm ------------------------------------

def _simulate_brainstorm(cwd: Path, *, project_description: str) -> dict:
    """Simulate `/lp-brainstorm` Phase 0 routing per HANDSHAKE §7 +
    commands/lp-brainstorm.md.

    Returns a dict shaped like the brainstorm-summary frontmatter Phase 0
    writes; raises AssertionError if the cwd is not greenfield.
    """
    state = cwd_state(cwd)
    assert state == "empty", (
        f"brainstorm phase: cwd_state={state!r}, expected 'empty'"
    )

    launchpad = cwd / ".launchpad"
    launchpad.mkdir(parents=True, exist_ok=True)
    summary = launchpad / "brainstorm-summary.md"
    summary.write_text(
        "---\n"
        "greenfield: true\n"
        "cwd_state_when_generated: empty\n"
        "---\n"
        "# Project shape\n\n"
        f"{project_description}\n",
        encoding="utf-8",
    )
    marker = launchpad / ".first-run-marker"
    fd = os.open(str(marker), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    return {
        "greenfield": True,
        "cwd_state_when_generated": "empty",
        "summary_path": summary,
        "marker_path": marker,
        "transition_to": "/lp-pick-stack",
    }


# --- Phase 2: pick-stack via library API ----------------------------------

# Canned answers for the canonical Markdown-blog flow per handoff §4.1 step 2.
# Q5 is required by the question_funnel; managed-platform fits a typical
# "Vercel/Netlify static-blog deploy" intent. The handoff's stated answer
# set (Q1-Q4) is extended with Q5 here per the pick-stack plan §1.1
# evolution to a 5-question funnel.
CANONICAL_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}

# Canonical project description — contains "TypeScript" so the static-blog-
# astro `fits_when` predicate fires uniquely (the eleventy/hugo siblings need
# 'eleventy'/'hugo' tokens). Avoids the ambiguity-cluster disambiguation path.
CANONICAL_PROJECT_DESCRIPTION = (
    "a Markdown blog with TypeScript team and SEO-critical content"
)


def _run_pick_stack(
    cwd: Path,
    *,
    answers=CANONICAL_ANSWERS,
    project_description: str = CANONICAL_PROJECT_DESCRIPTION,
    project_understanding=("Markdown blog with TypeScript team",),
):
    """Drive pick-stack via the library API (faster than spawning a CLI)."""
    return pick_stack_run(
        cwd, answers,
        project_description=project_description,
        project_understanding=tuple(project_understanding),
        why_this_fits=("Astro fits TS-first islands + content focus",),
        alternatives=("eleventy: pre-NPM ESM-only constraint",),
        notes=("Phase 7 joint smoke",),
        write_telemetry=False,  # noise-free for tests
    )


# --- Phase 3: scaffold via CLI subprocess ----------------------------------

def _invoke_scaffold_cli(
    cwd: Path,
    *,
    scaffolders_yml: Path | None = None,
) -> subprocess.CompletedProcess:
    """Drive the CLI per handoff §4.1: tests must drive the CLI binary, not
    `engine.run_pipeline()` directly.

    `scaffolders_yml` defaults to a stub catalog that re-types astro as
    `curate` (no `npm create` spawn — see `_stub_scaffolders_yml`).
    """
    if scaffolders_yml is None:
        scaffolders_yml = _stub_scaffolders_yml(cwd / ".launchpad" / "stub-scaffolders.yml")
    return subprocess.run(
        [
            sys.executable, str(PLUGIN_SCAFFOLD_STACK),
            "--cwd", str(cwd),
            "--scaffolders-yml", str(scaffolders_yml),
            "--category-patterns-yml", str(DEFAULT_CATEGORY_PATTERNS_YML),
            "--plugins-root", str(DEFAULT_PLUGINS_ROOT),
            "--no-telemetry",
        ],
        capture_output=True, timeout=60, check=False,
    )


# --- Phase 4: simulated /lp-define receipt consumption --------------------

def _simulate_define_receipt_load(cwd: Path) -> dict:
    """Simulate `/lp-define` Phase 0.5 receipt consumption.

    Drives `plugin-scaffold-receipt-loader.py` library API to validate the
    receipt schema + sha256 envelope; this is the SAME path `/lp-define`
    takes before adapter dispatch.
    """
    sys.path.insert(0, str(_SCRIPTS))
    # Use importlib to load the dashed-name module per Phase 0.5 pattern.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "plugin_scaffold_receipt_loader",
        str(PLUGIN_SCAFFOLD_RECEIPT_LOADER),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    receipt_path = cwd / ".launchpad" / "scaffold-receipt.json"
    return mod.load_receipt(receipt_path)


# --- Variant 1: canonical --------------------------------------------------

def test_joint_smoke_canonical():
    """Canonical Markdown-blog flow: brainstorm → pick-stack → scaffold →
    define-receipt-load all succeed."""
    cwd = _make_tempdir()
    try:
        # Phase 1: brainstorm
        brainstorm = _simulate_brainstorm(
            cwd,
            project_description="a Markdown blog with TS team and SEO-critical content",
        )
        assert brainstorm["greenfield"] is True
        assert brainstorm["marker_path"].exists()

        # Phase 2: pick-stack (library API)
        pick_result = _run_pick_stack(cwd)
        assert pick_result.success, (
            f"pick-stack failed: reason={pick_result.reason}, "
            f"message={pick_result.message}"
        )
        assert pick_result.outcome == PickStackOutcome.ACCEPTED
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        assert decision_path.exists()
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        # The TypeScript bias in the project_description picks
        # static-blog-astro uniquely from the static-blog-trio cluster.
        assert decision["matched_category_id"] == "static-blog-astro"
        assert decision["layers"][0]["stack"] == "astro"
        assert decision["version"] == "1.0"
        assert len(decision["nonce"]) == 32  # UUIDv4 hex

        # Phase 3: scaffold (CLI)
        rv = _invoke_scaffold_cli(cwd)
        assert rv.returncode == 0, (
            f"scaffold-stack CLI failed: stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )
        receipt_path = cwd / ".launchpad" / "scaffold-receipt.json"
        assert receipt_path.exists(), "scaffold-receipt.json not written"

        # Verify the marker was consumed (renamed to .consumed.<ts>).
        marker = cwd / ".launchpad" / ".first-run-marker"
        assert not marker.exists(), (
            "first-run-marker should be consumed (renamed) after scaffold"
        )
        consumed = list(
            (cwd / ".launchpad").glob(".first-run-marker.consumed.*"),
        )
        assert consumed, (
            "no .first-run-marker.consumed.* found; marker_consumer broke"
        )

        # Phase 4: define receipt-load
        receipt = _simulate_define_receipt_load(cwd)
        assert receipt["version"] == "1.0"
        assert receipt["decision_sha256"]  # populated
        assert receipt["decision_nonce"] == decision["nonce"]
        assert receipt["secret_scan_passed"] is True
        assert receipt["layers_materialized"]
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


# --- Variant 2: adversarial-sanitization ----------------------------------

def test_joint_smoke_adversarial_sanitization():
    """Pick-stack input contains an HTML-tag bullet; the
    `extract_summary` defense filters it out before the bullet ever enters
    `scaffold-decision.json`. Scaffold succeeds with a clean decision."""
    cwd = _make_tempdir()
    try:
        _simulate_brainstorm(
            cwd,
            project_description="a Markdown blog with TS team",
        )
        # Adversarial bullet in project_understanding — pick-stack runs the
        # rationale renderer which embeds it via FORBIDDEN_BULLET_RE check.
        pick_result = _run_pick_stack(
            cwd,
            project_understanding=(
                "Clean bullet about static blogging",
                "<script>alert('XSS')</script>",  # filtered by extractor
                "＜script＞FULLWIDTH alert＜/script＞",  # filtered post-§10 patch
            ),
        )
        assert pick_result.success, (
            f"pick-stack failed: reason={pick_result.reason}, "
            f"message={pick_result.message}"
        )
        decision = json.loads(
            (cwd / ".launchpad" / "scaffold-decision.json").read_text(
                encoding="utf-8",
            ),
        )
        # The adversarial bullets should be DROPPED from rationale_summary.
        understanding = next(
            s for s in decision["rationale_summary"]
            if s["section"] == "project-understanding"
        )
        joined = " ".join(understanding["bullets"])
        assert "<script>" not in joined, (
            f"ASCII script tag leaked into rationale_summary: {joined!r}"
        )
        assert "＜script＞" not in joined, (
            f"FULLWIDTH script confusable leaked into rationale_summary: {joined!r}"
        )
        assert "Clean bullet" in joined, (
            f"clean bullet was dropped: {joined!r}"
        )

        # Scaffold succeeds (decision is clean post-extraction).
        rv = _invoke_scaffold_cli(cwd)
        assert rv.returncode == 0, (
            f"scaffold-stack CLI failed: stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )
        receipt = _simulate_define_receipt_load(cwd)
        assert receipt["secret_scan_passed"] is True
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


# --- Variant 3: brownfield-refusal ----------------------------------------

def test_joint_smoke_brownfield_refusal():
    """Pre-populate package.json BEFORE scaffold step → scaffold-stack rejects
    with `cwd_state_brownfield`. Pipeline halts at phase 3.

    This variant SKIPS phase 1 (brainstorm) and phase 2 (pick-stack) by
    pre-building a valid decision file in the brownfield cwd; the test is
    that scaffold-stack's Step 0 greenfield gate fires regardless.
    """
    cwd = _make_tempdir()
    try:
        # Build a valid decision in a TEMP greenfield dir, then move artifacts
        # into the brownfield cwd before the scaffold-stack invocation.
        prep_dir = _make_tempdir()
        try:
            _simulate_brainstorm(
                prep_dir,
                project_description="a Markdown blog with TS team",
            )
            pick_result = _run_pick_stack(prep_dir)
            assert pick_result.success
            # Move .launchpad/ into the brownfield cwd.
            shutil.move(
                str(prep_dir / ".launchpad"),
                str(cwd / ".launchpad"),
            )
        finally:
            shutil.rmtree(prep_dir, ignore_errors=True)

        # Brownfield indicator: package.json
        (cwd / "package.json").write_text(
            '{"name":"existing-project"}', encoding="utf-8",
        )

        # Scaffold MUST refuse with cwd_state_brownfield.
        rv = _invoke_scaffold_cli(cwd)
        assert rv.returncode != 0, (
            f"scaffold-stack accepted brownfield cwd (expected reject): "
            f"stderr={rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )
        rejection = _read_latest_rejection(cwd)
        assert rejection is not None
        # Note: the bound_cwd-mismatch could also fire because the decision
        # was built against prep_dir's bound_cwd, not the brownfield cwd.
        # Greenfield gate runs FIRST (Step 0), so we expect cwd_state_brownfield.
        assert rejection.get("reason") == "cwd_state_brownfield", (
            f"expected 'cwd_state_brownfield', got {rejection.get('reason')!r}"
        )
        # No receipt should exist.
        assert not (cwd / ".launchpad" / "scaffold-receipt.json").exists()
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
