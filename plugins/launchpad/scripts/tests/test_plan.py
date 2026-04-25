#!/usr/bin/env python3
"""Acceptance tests for /lp-plan.

Covers:
  - Section registry reader: loads from SECTION_REGISTRY.md when present
  - Back-compat shim: loads from PRD.md with deprecation warning when registry absent
  - Absent registry + absent PRD: raises FileNotFoundError
  - Autonomous guard: returns False in clean git state; True when section
    commit also touched autonomous-ack.md
  - pipeline.plan.design_review: skipped honors cleanly through config loader
  - lp-plan.md command: has Step 0, references section_registry, mentions /lp-build
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_SCRIPTS.parent.parent.parent
sys.path.insert(0, str(PLUGIN_SCRIPTS))

from plugin_stack_adapters import autonomous_guard, section_registry  # noqa: E402

# Load config loader
_spec = importlib.util.spec_from_file_location(
    "plugin_config_loader", PLUGIN_SCRIPTS / "plugin-config-loader.py"
)
_loader_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_loader_mod)  # type: ignore[union-attr]
load_config = _loader_mod.load


# --- Fixtures ---

def make_fixture(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase4-"))
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def cleanup(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)


def make_git_repo(files: dict[str, str]) -> Path:
    """Fixture that initializes a git repo and creates files as separate commits."""
    d = Path(tempfile.mkdtemp(prefix="lp-phase4-git-"))
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=d, check=True)
    return d


def git_commit(repo: Path, files: dict[str, str], msg: str) -> None:
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        subprocess.run(["git", "add", rel], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)


# --- Tests ---

def test_loads_registry_when_present() -> list[str]:
    errors = []
    fixture = make_fixture({
        "docs/tasks/SECTION_REGISTRY.md": """# Section Registry

### auth-redesign
- **Status:** shaped
- **Spec:** [sections/auth-redesign.md](sections/auth-redesign.md)
- **Added:** 2026-04-20

### dashboard
- **Status:** planned
- **Spec:** [sections/dashboard.md](sections/dashboard.md)
- **Added:** 2026-04-19
""",
    })
    try:
        entries = section_registry.load_sections(fixture, warn=False)
        if len(entries) != 2:
            errors.append(f"expected 2 sections, got {len(entries)}: {[e.name for e in entries]}")
            return errors
        names = {e.name for e in entries}
        if names != {"auth-redesign", "dashboard"}:
            errors.append(f"wrong section names: {names}")
        auth = next(e for e in entries if e.name == "auth-redesign")
        if auth.status != "shaped":
            errors.append(f"auth-redesign status={auth.status!r}, expected 'shaped'")
    finally:
        cleanup(fixture)
    return errors


def test_backcompat_shim_reads_prd() -> list[str]:
    """When SECTION_REGISTRY.md is absent but PRD.md has section markers,
    shim reads PRD and emits deprecation warning."""
    errors = []
    fixture = make_fixture({
        "docs/architecture/PRD.md": """# PRD

Content here.

### legacy-section
- **Status:** planned
- **Spec:** [sections/legacy-section.md](sections/legacy-section.md)
- **Added:** 2025-12-01
""",
    })
    try:
        # Capture stderr to verify deprecation warning fires
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            entries = section_registry.load_sections(fixture, warn=True)

        if len(entries) != 1 or entries[0].name != "legacy-section":
            errors.append(f"shim didn't parse PRD correctly: {[e.name for e in entries]}")

        stderr_output = buf.getvalue()
        if "DeprecationWarning" not in stderr_output:
            errors.append(f"shim didn't emit DeprecationWarning; stderr: {stderr_output!r}")
        if "/lp-define" not in stderr_output:
            errors.append(f"deprecation warning missing /lp-define suggestion: {stderr_output!r}")
    finally:
        cleanup(fixture)
    return errors


def test_absent_registry_and_prd_raises() -> list[str]:
    errors = []
    fixture = make_fixture({"README.md": "no registry, no prd"})
    try:
        try:
            section_registry.load_sections(fixture)
            errors.append("expected FileNotFoundError, got success")
        except FileNotFoundError as e:
            if "/lp-define" not in str(e):
                errors.append(f"error didn't mention /lp-define: {e}")
    finally:
        cleanup(fixture)
    return errors


def test_get_section_by_name() -> list[str]:
    errors = []
    fixture = make_fixture({
        "docs/tasks/SECTION_REGISTRY.md": """# Section Registry

### foo
- **Status:** shaped

### bar
- **Status:** planned
""",
    })
    try:
        entry = section_registry.get_section(fixture, "bar", warn=False)
        if entry is None:
            errors.append("get_section returned None for existing 'bar'")
        elif entry.status != "planned":
            errors.append(f"bar.status={entry.status!r}, expected 'planned'")

        missing = section_registry.get_section(fixture, "does-not-exist", warn=False)
        if missing is not None:
            errors.append(f"get_section returned {missing} for missing name, expected None")
    finally:
        cleanup(fixture)
    return errors


def test_autonomous_guard_clean_repo() -> list[str]:
    """Section committed separately from ack → guard returns False (safe)."""
    errors = []
    repo = make_git_repo({})
    try:
        # Commit 1: the section
        git_commit(repo, {
            "docs/tasks/SECTION_REGISTRY.md": "# Registry\n\n### safe-section\n- **Status:** shaped\n",
        }, "add safe-section")

        # Commit 2 (SEPARATE): autonomous-ack
        git_commit(repo, {
            ".launchpad/autonomous-ack.md": "I acknowledge autonomous risks",
        }, "ack autonomous")

        result = autonomous_guard.section_added_with_ack(repo, "safe-section")
        if result is not False:
            errors.append(f"clean-repo section 'safe-section' flagged as ack-coupled (got {result!r})")
    finally:
        cleanup(repo)
    return errors


def test_autonomous_guard_hostile_same_commit() -> list[str]:
    """Section + ack in the SAME commit → guard returns True (refuse)."""
    errors = []
    repo = make_git_repo({})
    try:
        # Single hostile commit touching both files
        git_commit(repo, {
            "docs/tasks/SECTION_REGISTRY.md": "# Registry\n\n### hostile-section\n- **Status:** shaped\n",
            ".launchpad/autonomous-ack.md": "I acknowledge autonomous risks",
        }, "add section and ack together (hostile pattern)")

        result = autonomous_guard.section_added_with_ack(repo, "hostile-section")
        if result is not True:
            errors.append(f"hostile same-commit section not flagged (got {result!r})")
    finally:
        cleanup(repo)
    return errors


def test_autonomous_guard_section_not_in_registry() -> list[str]:
    """Section name not present in any commit → guard returns False (no-op)."""
    errors = []
    repo = make_git_repo({})
    try:
        git_commit(repo, {"README.md": "empty"}, "init")
        result = autonomous_guard.section_added_with_ack(repo, "does-not-exist")
        if result is not False:
            errors.append(f"missing section flagged as coupled: {result}")
    finally:
        cleanup(repo)
    return errors


def test_autonomous_guard_no_git_repo() -> list[str]:
    """Non-git directory → guard returns False (doesn't crash)."""
    errors = []
    fixture = make_fixture({"README.md": "not a git repo"})
    try:
        result = autonomous_guard.section_added_with_ack(fixture, "anything")
        if result is not False:
            errors.append(f"non-git fixture: guard returned {result}, expected False")
    finally:
        cleanup(fixture)
    return errors


def test_config_pipeline_skip_honored() -> list[str]:
    """config.yml with pipeline.plan.design_review: skipped → loader surfaces it."""
    errors = []
    fixture = make_fixture({
        ".launchpad/config.yml": """
pipeline:
  plan:
    design_review: skipped
    pnf: enabled
    harden: enabled
"""
    })
    try:
        cfg = load_config(fixture)
        plan = cfg.get("pipeline", {}).get("plan", {})
        if plan.get("design_review") != "skipped":
            errors.append(
                f"pipeline.plan.design_review expected 'skipped', got {plan.get('design_review')!r}"
            )
    finally:
        cleanup(fixture)
    return errors


def test_load_sections_accepts_str_repo_root() -> list[str]:
    """load_sections must accept repo_root as str or Path. Earlier versions
    crashed with TypeError when callers passed a string. Must coerce str → Path
    internally."""
    errors = []
    fixture = make_fixture({
        "docs/tasks/SECTION_REGISTRY.md": """# Section Registry

### foo
- **Status:** shaped
""",
    })
    try:
        # Pass as plain str — must not raise TypeError
        entries = section_registry.load_sections(str(fixture), warn=False)
        if len(entries) != 1 or entries[0].name != "foo":
            errors.append(f"str repo_root: parse failed ({[e.name for e in entries]})")
        # Same for get_section
        entry = section_registry.get_section(str(fixture), "foo", warn=False)
        if entry is None:
            errors.append("get_section(str) returned None for present section")
    except TypeError as e:
        errors.append(f"load_sections raised TypeError on str input: {e}")
    finally:
        cleanup(fixture)
    return errors


def test_lp_plan_command_has_step0() -> list[str]:
    """The lp-plan command file should reference Step 0, section_registry, and /lp-build."""
    errors = []
    cmd = REPO_ROOT / "plugins" / "launchpad" / "commands" / "lp-plan.md"
    if not cmd.is_file():
        errors.append(f"{cmd} missing")
        return errors
    content = cmd.read_text()
    must_have = [
        ("Step 0", "Step 0 section"),
        ("SECTION_REGISTRY.md", "section registry reference"),
        ("section_registry", "section_registry helper reference"),
        ("autonomous_guard", "autonomous_guard helper reference"),
        ("pipeline.plan.design_review", "pipeline skip-gate reference"),
        ("/lp-build", "transition to /lp-build"),
    ]
    for needle, desc in must_have:
        if needle not in content:
            errors.append(f"lp-plan.md missing: {desc} ({needle!r})")
    return errors


def main() -> int:
    tests = [
        ("loads_registry_when_present", test_loads_registry_when_present),
        ("backcompat_shim_reads_prd", test_backcompat_shim_reads_prd),
        ("absent_registry_and_prd_raises", test_absent_registry_and_prd_raises),
        ("get_section_by_name", test_get_section_by_name),
        ("autonomous_guard_clean_repo", test_autonomous_guard_clean_repo),
        ("autonomous_guard_hostile_same_commit", test_autonomous_guard_hostile_same_commit),
        ("autonomous_guard_section_not_in_registry", test_autonomous_guard_section_not_in_registry),
        ("autonomous_guard_no_git_repo", test_autonomous_guard_no_git_repo),
        ("config_pipeline_skip_honored", test_config_pipeline_skip_honored),
        ("load_sections_accepts_str_repo_root", test_load_sections_accepts_str_repo_root),
        ("lp_plan_command_has_step0", test_lp_plan_command_has_step0),
    ]
    all_errors = []
    for name, test in tests:
        errs = test()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: plan acceptance")
        for e in all_errors:
            print(e)
        return 1

    print(f"PASS: plan acceptance ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
