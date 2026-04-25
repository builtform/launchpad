#!/usr/bin/env python3
"""Acceptance tests for L2 command adaptation.

Scope:
  L2 commands read from `.launchpad/config.yml` and work standalone in a
  configured brownfield.

Validates:
  - Every migrated L2 command declares a Step 0 (Lite) that calls
    plugin-prereq-check.sh with --mode=lite
  - Shell-invoking L2 commands (/lp-commit, /lp-ship) route quality gates
    through plugin-build-runner.py instead of hardcoded pnpm strings
  - /lp-test-browser has an explicit pipeline.build.test_browser skip gate
  - /lp-harden-plan honors create-if-missing semantics for agents.yml
    (never overwrites)
  - /lp-pnf reads from SECTION_REGISTRY.md via section_registry helper
    (back-compat shim to PRD preserved)
  - Frontmatter integrity still holds (no regressions)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
CMD_DIR = PLUGIN_SCRIPTS.parent / "commands"


def read_cmd(name: str) -> str:
    p = CMD_DIR / f"{name}.md"
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8")


# --- Tests ---

def test_step0_lite_on_all_migrated_commands() -> list[str]:
    """Every migrated L2 command must declare a Step 0 and invoke
    plugin-prereq-check.sh --mode=lite."""
    errors = []
    migrated = [
        "lp-commit",
        "lp-ship",
        "lp-review",
        "lp-inf",
        "lp-resolve-todo-parallel",
        "lp-learn",
        "lp-harden-plan",
        "lp-pnf",
        "lp-shape-section",
        "lp-create-agent",
        "lp-create-skill",
    ]
    for cmd in migrated:
        content = read_cmd(cmd)
        if not content:
            errors.append(f"{cmd}: file not found")
            continue
        if "## Step 0" not in content:
            errors.append(f"{cmd}: missing '## Step 0' section")
        if "plugin-prereq-check.sh" not in content:
            errors.append(f"{cmd}: missing plugin-prereq-check.sh invocation")
        if "--mode=lite" not in content:
            errors.append(f"{cmd}: Step 0 doesn't specify --mode=lite")
    return errors


def test_quality_gates_via_build_runner() -> list[str]:
    """Commands running quality gates must route through plugin-build-runner.py,
    not hardcoded pnpm strings.

    We allow 'pnpm' to appear in commentary/prose but the EXECUTABLE path
    should be the build runner.
    """
    errors = []
    for cmd in ("lp-commit", "lp-ship"):
        content = read_cmd(cmd)
        if "plugin-build-runner.py" not in content:
            errors.append(f"{cmd}: missing plugin-build-runner.py reference")
        # A fenced code block with literal `pnpm test` + `pnpm typecheck` on
        # consecutive lines would be the hardcoded pattern we're replacing.
        # Be precise: look for that exact triplet in a bash block.
        pattern = re.compile(r"```bash\s*\n\s*pnpm test\s*\n\s*pnpm typecheck\s*\n\s*pnpm lint\s*\n", re.MULTILINE)
        if pattern.search(content):
            errors.append(f"{cmd}: still has hardcoded `pnpm test/typecheck/lint` block (regression)")
    return errors


def test_test_browser_pipeline_skip_gate() -> list[str]:
    errors = []
    content = read_cmd("lp-test-browser")
    if "pipeline.build.test_browser" not in content:
        errors.append("lp-test-browser: missing pipeline.build.test_browser reference")
    if "skipped" not in content:
        errors.append("lp-test-browser: no reference to 'skipped' state")
    # Step 0 must precede Step 1
    step0_idx = content.find("## Step 0")
    step1_idx = content.find("## Step 1")
    if step0_idx == -1 or step1_idx == -1 or step0_idx > step1_idx:
        errors.append("lp-test-browser: Step 0 must precede Step 1")
    return errors


def test_harden_plan_create_if_missing() -> list[str]:
    errors = []
    content = read_cmd("lp-harden-plan")
    if "never overwrites" not in content.lower() and "never writes" not in content.lower():
        errors.append("lp-harden-plan: must state agents.yml is never overwritten")
    if "create-if-missing" not in content.lower() and "create-if-absent" not in content.lower():
        errors.append("lp-harden-plan: must mention create-if-missing semantics")
    return errors


def test_pnf_uses_section_registry() -> list[str]:
    errors = []
    content = read_cmd("lp-pnf")
    if "section_registry" not in content:
        errors.append("lp-pnf: missing section_registry helper reference")
    if "SECTION_REGISTRY.md" not in content:
        errors.append("lp-pnf: missing SECTION_REGISTRY.md canonical path")
    if "back-compat" not in content.lower() and "shim" not in content.lower():
        errors.append("lp-pnf: should mention back-compat shim to PRD")
    # Paths should be config-driven (prose uses $paths.* or references paths.*)
    if "paths.architecture_dir" not in content and "paths.sections_dir" not in content:
        errors.append("lp-pnf: should reference config.yml paths.* for adaptability")
    return errors


def test_pnf_not_only_prd_for_registry() -> list[str]:
    """Regression: /lp-pnf must NOT read ONLY from PRD for section lookups."""
    errors = []
    content = read_cmd("lp-pnf")
    # Count PRD-based registry reads vs SECTION_REGISTRY references
    prd_registry_refs = len(re.findall(r"PRD\.md.{0,40}(section|registry)", content, re.IGNORECASE))
    section_reg_refs = content.count("SECTION_REGISTRY")
    if section_reg_refs == 0:
        errors.append("lp-pnf: no SECTION_REGISTRY references at all")
    if prd_registry_refs > 0 and section_reg_refs == 0:
        errors.append(
            f"lp-pnf: still reads section registry ONLY from PRD (found {prd_registry_refs} "
            f"PRD+registry refs; 0 SECTION_REGISTRY refs)"
        )
    return errors


def test_shape_section_writes_registry() -> list[str]:
    errors = []
    content = read_cmd("lp-shape-section")
    if "SECTION_REGISTRY.md" not in content and "section_registry" not in content.lower():
        # Accept either explicit path ref or helper module mention
        errors.append("lp-shape-section: should reference SECTION_REGISTRY.md")
    return errors


def test_frontmatter_integrity_still_passes() -> list[str]:
    """L2 command edits shouldn't have corrupted any frontmatter."""
    errors = []
    import subprocess
    script = TESTS_DIR / "test_frontmatter_integrity.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if r.returncode != 0:
        errors.append(f"frontmatter integrity regressed: {r.stdout + r.stderr}")
    return errors


def test_no_regression_on_main_harness_commands() -> list[str]:
    """The four core harness commands must still have their Step 0 sections."""
    errors = []
    for cmd in ("lp-kickoff", "lp-define", "lp-plan", "lp-build"):
        content = read_cmd(cmd)
        if "## Step 0" not in content:
            errors.append(f"{cmd}: lost its Step 0 section (regression)")
    return errors


def main() -> int:
    tests = [
        ("step0_lite_on_all_migrated_commands", test_step0_lite_on_all_migrated_commands),
        ("quality_gates_via_build_runner", test_quality_gates_via_build_runner),
        ("test_browser_pipeline_skip_gate", test_test_browser_pipeline_skip_gate),
        ("harden_plan_create_if_missing", test_harden_plan_create_if_missing),
        ("pnf_uses_section_registry", test_pnf_uses_section_registry),
        ("pnf_not_only_prd_for_registry", test_pnf_not_only_prd_for_registry),
        ("shape_section_writes_registry", test_shape_section_writes_registry),
        ("frontmatter_integrity_still_passes", test_frontmatter_integrity_still_passes),
        ("no_regression_on_main_harness_commands", test_no_regression_on_main_harness_commands),
    ]
    all_errors = []
    for name, test in tests:
        errs = test()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: L2 commands acceptance")
        for e in all_errors:
            print(e)
        return 1

    print(f"PASS: L2 commands acceptance ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
