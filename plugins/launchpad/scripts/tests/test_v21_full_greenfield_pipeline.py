"""Phase 11 v3.1 -- E2E greenfield pipeline (DA1).

Drives the v2.1 plugin-owns-everything pipeline end-to-end against a
fresh tmp_path:

  pick-stack -> scaffold-stack -> kernel render -> /lp-define

Pick-stack and scaffold-stack use their library APIs. Structure-check
flows also invoke the define CLI and the rendered Bash check. Brainstorm
has no Python runner, so its output is simulated.

Stack: astro static-blog (uses curate-mode stub scaffolders.yml so no
`npm create` spawn). Pattern lifted from `test_joint_pipeline_smoke.py`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import cwd_state  # noqa: E402

from lp_pick_stack.engine import Outcome as PickStackOutcome  # noqa: E402
from lp_pick_stack.engine import run_pipeline as pick_stack_run  # noqa: E402
from lp_scaffold_stack.engine import (  # noqa: E402
    Outcome as ScaffoldOutcome,
)
from lp_scaffold_stack.engine import run_pipeline as scaffold_stack_run  # noqa: E402

from scaffold_smoke_runner import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
)


CANONICAL_ANSWERS = {
    "Q1": "static-site-or-blog",
    "Q2": "static-content-only",
    "Q3": "no",
    "Q4": "typescript-javascript",
    "Q5": "managed-platform",
}
CANONICAL_PROJECT_DESCRIPTION = (
    "a Markdown blog with TypeScript team and SEO-critical content"
)


def _simulate_brainstorm(cwd: Path) -> None:
    """Write the brainstorm-summary frontmatter and first-run-marker that
    `/lp-pick-stack` Step 0 reads (per HANDSHAKE section 7)."""
    brainstorms = cwd / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True, exist_ok=True)
    (brainstorms / "2026-05-06-blog-brainstorm.md").write_text(
        "# Blog brainstorm\n\n" + CANONICAL_PROJECT_DESCRIPTION * 3 + "\n",
        encoding="utf-8",
    )
    launchpad = cwd / ".launchpad"
    launchpad.mkdir(parents=True, exist_ok=True)
    summary = launchpad / "brainstorm-summary.md"
    summary.write_text(
        "---\n"
        "generated_at: 2026-05-06T12:00:00Z\n"
        "generated_by: /lp-brainstorm\n"
        "greenfield: true\n"
        "cwd_state_when_generated: empty\n"
        "---\n"
        "# Project shape\n\n"
        f"{CANONICAL_PROJECT_DESCRIPTION}\n",
        encoding="utf-8",
    )
    marker = launchpad / ".first-run-marker"
    fd = os.open(str(marker), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)


def _stub_scaffolders_yml(target: Path) -> Path:
    """Re-type astro from `orchestrate` (npm create) to `curate` so no
    real-tool spawn happens during the test. Reuses the production
    knowledge_anchor + sha256 so curate-mode read_and_verify succeeds."""
    target.parent.mkdir(parents=True, exist_ok=True)
    real_catalog = (_SCRIPTS.parent / "scaffolders.yml").read_text(encoding="utf-8")
    astro_sha = re.search(
        r"astro:.*?knowledge_anchor_sha256:\s*\"([0-9a-f]{64})\"",
        real_catalog,
        re.DOTALL,
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


def test_full_greenfield_pipeline(tmp_path: Path) -> None:
    """E2E greenfield: brainstorm-summary -> pick-stack -> scaffold-stack ->
    scaffold-receipt with v2.1 envelope. Asserts schema 1.1 envelope on
    scaffold-decision.json + receipt presence + v2.1 envelope keys."""
    cwd = tmp_path
    os.chmod(cwd, 0o700)

    # Phase 1: simulated brainstorm.
    _simulate_brainstorm(cwd)
    assert cwd_state(cwd) == "empty"

    # Phase 2: pick-stack via library API.
    pick_result = pick_stack_run(
        cwd, CANONICAL_ANSWERS,
        project_description=CANONICAL_PROJECT_DESCRIPTION,
        project_understanding=("Markdown blog with TypeScript team",),
        why_this_fits=("Astro fits TS-first islands + content focus",),
        alternatives=("eleventy: pre-NPM ESM-only constraint",),
        notes=("Phase 11 v2.1 E2E greenfield test",),
        write_telemetry=False,
    )
    assert pick_result.success, (
        f"pick-stack failed: reason={pick_result.reason} "
        f"message={pick_result.message}"
    )
    assert pick_result.outcome == PickStackOutcome.ACCEPTED

    decision_path = cwd / ".launchpad" / "scaffold-decision.json"
    assert decision_path.exists()
    decision = json.loads(decision_path.read_text(encoding="utf-8"))

    # v2.1 envelope assertions: schema_version + identity + plugin_version.
    assert decision["version"] == "1.0"
    assert decision["schema_version"] == "1.1"
    assert isinstance(decision["identity"], dict)
    assert decision["identity"]["pii_opt_in"] is False
    assert isinstance(decision["plugin_version"], str)
    assert isinstance(decision["stacks"], list)
    assert decision["stacks"] == ["astro"]
    assert decision["matched_category_id"] == "static-blog-astro"
    assert decision["layers"][0]["stack"] == "astro"
    assert "sha256" in decision

    # Phase 3: scaffold-stack via engine library API per DA1.
    stub_yml = _stub_scaffolders_yml(cwd / ".launchpad" / "stub-scaffolders.yml")
    scaffold_result = scaffold_stack_run(
        cwd,
        scaffolders_yml=stub_yml,
        category_patterns_yml=DEFAULT_CATEGORY_PATTERNS_YML,
        plugins_root=DEFAULT_PLUGINS_ROOT,
        write_telemetry_flag=False,
    )
    assert scaffold_result.success, (
        f"scaffold-stack failed: reason={scaffold_result.reason} "
        f"message={scaffold_result.message}"
    )
    assert scaffold_result.outcome == ScaffoldOutcome.COMPLETED

    # Receipt must be sealed with the same nonce as the decision.
    receipt_path = cwd / ".launchpad" / "scaffold-receipt.json"
    assert receipt_path.exists(), "scaffold-receipt.json not written"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["decision_nonce"] == decision["nonce"]
    assert receipt["secret_scan_passed"] is True
    assert receipt["layers_materialized"]

    # First-run-marker consumed (renamed) post-scaffold.
    marker = cwd / ".launchpad" / ".first-run-marker"
    assert not marker.exists()
    consumed = list((cwd / ".launchpad").glob(".first-run-marker.consumed.*"))
    assert consumed, "first-run-marker.consumed.* missing post-scaffold"

    # Per Codex PR #50 P1-B harden Slice D §4: astro single-mode declares
    # `workspace_source_map_single == {}` (empty) so the scaffold MUST NOT
    # synthesize an `apps/` wrap; preserves the existing D3 behavior of
    # adapters that own the whole project root.
    assert not (cwd / "apps").exists(), (
        "astro single-mode must not wrap files under apps/"
    )


def test_undecided_answers_after_brainstorm(tmp_path: Path) -> None:
    from lp_pick_stack.brainstorm_summary_validator import validate_brainstorm_summary
    from lp_pick_stack.engine import _load_category_patterns
    from lp_pick_stack.matcher import shortlist_categories
    from test_matcher import _CASE_A, _EXPECTED_A

    os.chmod(tmp_path, 0o700)
    document = tmp_path / "docs/brainstorms/2026-11-08-plan-brainstorm.md"
    document.parent.mkdir(parents=True)
    document.write_text("# Project summary\n\n" + _CASE_A["describe"], encoding="utf-8")
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    (launchpad / "brainstorm-summary.md").write_text(
        "---\n"
        "generated_at: 2026-11-08T12:00:00Z\n"
        "generated_by: /lp-brainstorm\n"
        "greenfield: true\n"
        "cwd_state_when_generated: empty\n"
        "brainstorm_doc: docs/brainstorms/2026-11-08-plan-brainstorm.md\n"
        "---\n\n"
        "# Project summary\n\n" + _CASE_A["describe"] + "\n\n"
        "# Stack-relevant constraints\n\n"
        "- PostgreSQL, an always-on scheduler, passkey sign-in and web push.\n"
        "- Backend language and deployment choice remain undecided.\n",
        encoding="utf-8",
    )
    assert cwd_state(tmp_path) == "empty"
    assert validate_brainstorm_summary(tmp_path).brainstorm_doc == document.resolve()
    candidates = shortlist_categories(_CASE_A, _load_category_patterns(None))
    assert [
        (c.id, c.score, c.matched_by_wildcard, len(c.describe_hits), c.describe_atoms)
        for c in candidates
    ] == _EXPECTED_A

    selection = pick_stack_run(tmp_path, _CASE_A, write_telemetry=True)
    assert not selection.success
    assert selection.reason == "category_selection_required"
    assert not (launchpad / "scaffold-decision.json").exists()
    alternatives = (
        "Python SaaS (Django monolith): a Python backend is not part of the chosen TypeScript stack.",
        "Multi-frontend hybrid: a separate public content site is not needed for this private application.",
        "Realtime Python (Django Channels): the selected stack does not need a Python realtime server.",
        "TypeScript SaaS (Next + Supabase): the user chose to own the API server rather than use a managed backend.",
    )
    sealed = pick_stack_run(
        tmp_path, _CASE_A, chosen_category_id="polyglot-next-hono",
        alternatives=alternatives, write_telemetry=True,
    )
    assert sealed.success, sealed.message
    assert sealed.outcome == PickStackOutcome.ACCEPTED
    decision = json.loads((launchpad / "scaffold-decision.json").read_text(encoding="utf-8"))
    assert decision["matched_category_id"] == "polyglot-next-hono"
    assert next(s["bullets"] for s in decision["rationale_summary"] if s["section"] == "alternatives") == list(alternatives)
    logs = list((tmp_path / ".harness/observations").glob("v2-pipeline-*.jsonl"))
    assert len(logs) == 1
    entries = [json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 1
    assert entries[0]["outcome"] == PickStackOutcome.ACCEPTED
    assert cwd_state(tmp_path) == "empty"


def _finish_structure_project(cwd: Path) -> Path:
    initialized = subprocess.run(
        ["git", "init", "-q"], cwd=cwd, capture_output=True, text=True,
        timeout=30, check=False,
    )
    assert initialized.returncode == 0, initialized.stderr
    defined = subprocess.run(
        [sys.executable, str(_SCRIPTS / "lp_define_runner.py"), "--repo-root", str(cwd), "--force", "--no-trust-banner"],
        cwd=cwd, capture_output=True, text=True, timeout=120, check=False,
    )
    assert defined.returncode == 0, defined.stdout + defined.stderr
    assert (cwd / ".launchpad/agents.yml").is_file()
    return cwd


def _seed_astro_structure_project(cwd: Path) -> Path:
    os.chmod(cwd, 0o700)
    _simulate_brainstorm(cwd)
    picked = pick_stack_run(
        cwd, CANONICAL_ANSWERS, project_description=CANONICAL_PROJECT_DESCRIPTION,
        write_telemetry=False,
    )
    assert picked.success, picked.message
    stub = _stub_scaffolders_yml(cwd / ".launchpad/stub-scaffolders.yml")
    scaffolded = scaffold_stack_run(
        cwd, scaffolders_yml=stub, category_patterns_yml=DEFAULT_CATEGORY_PATTERNS_YML,
        plugins_root=DEFAULT_PLUGINS_ROOT, write_telemetry_flag=False,
    )
    assert scaffolded.success, scaffolded.message
    return _finish_structure_project(cwd)


def _seed_two_layer_structure_project(cwd: Path) -> Path:
    os.chmod(cwd, 0o700)
    picked = pick_stack_run(
        cwd, CANONICAL_ANSWERS, manual_override=True,
        manual_layer_specs=[
            {"stack": "hono", "role": "backend", "path": "apps/api"},
            {"stack": "generic", "role": "frontend", "path": "apps/web"},
        ],
        write_telemetry=False,
    )
    assert picked.success, picked.message
    scaffolded = scaffold_stack_run(
        cwd, plugins_root=DEFAULT_PLUGINS_ROOT,
        category_patterns_yml=DEFAULT_CATEGORY_PATTERNS_YML,
        write_telemetry_flag=False,
    )
    assert scaffolded.success, scaffolded.message
    receipt = json.loads((cwd / ".launchpad/scaffold-receipt.json").read_text(encoding="utf-8"))
    assert receipt["toolchains_detected"] == ["node"]
    for name, text in (
        ("apps/api/src/index.ts", "export const status = 'ok';\n"),
        ("apps/web/index.html", "<!doctype html><title>Example</title>\n"),
        ("packages/.gitkeep", ""),
    ):
        target = cwd / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return _finish_structure_project(cwd)


def _check_structure_project(cwd: Path):
    result = subprocess.run(
        ["bash", str(cwd / "scripts/maintenance/check-repo-structure.sh")],
        cwd=cwd, capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Non-whitelisted" not in result.stdout
    assert "Repository structure violations found" not in result.stdout
    assert "All agents.yml entries resolve" in result.stdout
    return result


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None, reason="bash and git are required")
def test_structure_check_passes_on_astro_project(tmp_path: Path):
    _check_structure_project(_seed_astro_structure_project(tmp_path))


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None, reason="bash and git are required")
def test_structure_check_passes_on_two_layer_project(tmp_path: Path):
    root = _seed_two_layer_structure_project(tmp_path)
    _check_structure_project(root)
    script = (root / "scripts/maintenance/check-repo-structure.sh").read_text(encoding="utf-8")
    block = re.search(r"STACK_AWARE_DIRS_BEGIN[^\n]*\n(.*?)\s*# STACK_AWARE_DIRS_END", script, re.S).group(1)
    assert '"apps"' in block
    assert '"packages"' in block
