"""Phase 11 v3.1 -- E2E greenfield pipeline (DA1).

Drives the v2.1 plugin-owns-everything pipeline end-to-end against a
fresh tmp_path:

  pick-stack -> scaffold-stack -> kernel render -> /lp-define

Per Phase 11 plan section 3.1: tests invoke Python runners directly via
the library API, NOT slash commands or CLI subprocess. Brainstorm has no
Python runner so the E2E starts at pick-stack (R2 acknowledged).

Stack: astro static-blog (uses curate-mode stub scaffolders.yml so no
`npm create` spawn). Pattern lifted from `test_joint_pipeline_smoke.py`.
"""
from __future__ import annotations

import json
import os
import re
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
    assert cwd_state(cwd) in {"empty", "launchpad-only"}

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
