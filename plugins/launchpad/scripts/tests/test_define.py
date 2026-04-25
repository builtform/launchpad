#!/usr/bin/env python3
"""Behavioral contract tests for /lp-define + plugin-doc-generator.py.

Acceptance invariants:
  - Greenfield (empty repo): LaunchPad defaults; 4-doc scaffold + config.yml
  - Brownfield TS monorepo (BuiltForm-shaped): detects stack; docs reflect it
  - Brownfield Django: detects Python; pipeline skips design; no frontend
  - Brownfield polyglot (TS + Python): commands arrays contain both suites
  - Re-running on configured repo: skip-if-exists default, no data loss
  - Never imposes Next.js on non-Next.js
  - Zero-manifest fallthrough: prompts user (simulated here by generic adapter)
  - Generated config.yml round-trips through the loader without errors
  - Secret scan blocks write when patterns match
  - `[a]ll-overwrite` cannot overwrite .launchpad/*.yml
  - TECH_STACK doesn't contain secret-bearing manifest fields

Run:
  python3 plugins/launchpad/scripts/tests/test_define.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
GENERATOR = str(PLUGIN_SCRIPTS / "plugin-doc-generator.py")
LOADER = str(PLUGIN_SCRIPTS / "plugin-config-loader.py")

# Load config loader as a module for programmatic checks
_spec = importlib.util.spec_from_file_location("plugin_config_loader", LOADER)
_loader_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_loader_mod)  # type: ignore[union-attr]
load_config = _loader_mod.load


def make_fixture(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase3-test-"))
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def cleanup(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)


def run_generator(repo: Path, *args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, GENERATOR, f"--repo-root={repo}", *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_ts_monorepo_happy_path() -> list[str]:
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({
            "name": "ts-mono",
            "workspaces": ["apps/*"],
            "dependencies": {"next": "15.0.0", "hono": "4.0.0"},
        }),
    })
    try:
        rc, out, err = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"ts_monorepo: exited {rc}. stderr: {err[:300]}")
            return errors

        # All 6 canonical docs should exist
        for rel in [
            "docs/architecture/PRD.md",
            "docs/architecture/TECH_STACK.md",
            "docs/architecture/BACKEND_STRUCTURE.md",
            "docs/architecture/APP_FLOW.md",
            "docs/tasks/SECTION_REGISTRY.md",
            ".launchpad/config.yml",
        ]:
            if not (fixture / rel).exists():
                errors.append(f"ts_monorepo: missing {rel}")

        # Sanity-check content
        tech_stack = (fixture / "docs/architecture/TECH_STACK.md").read_text()
        if "TypeScript" not in tech_stack:
            errors.append("ts_monorepo: TECH_STACK missing TypeScript")
        if "Next.js" not in tech_stack:
            errors.append("ts_monorepo: TECH_STACK missing Next.js")
    finally:
        cleanup(fixture)
    return errors


def test_django_backend_only() -> list[str]:
    """Django detection → pipeline skips design, no frontend info."""
    errors = []
    fixture = make_fixture({
        "pyproject.toml": '[project]\nname = "djapp"\ndependencies = ["django>=5"]\n',
    })
    try:
        rc, out, err = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"django: exited {rc}. stderr: {err[:300]}")
            return errors

        cfg = load_config(fixture)
        pipeline = cfg.get("pipeline", {})
        define = pipeline.get("define", {})
        plan = pipeline.get("plan", {})
        build = pipeline.get("build", {})

        # Design stage should be skipped (backend-only)
        if define.get("design") != "skipped":
            errors.append(f"django: pipeline.define.design expected 'skipped', got {define.get('design')!r}")
        if plan.get("design_review") != "skipped":
            errors.append(f"django: pipeline.plan.design_review expected 'skipped', got {plan.get('design_review')!r}")
        if build.get("test_browser") != "skipped":
            errors.append(f"django: pipeline.build.test_browser expected 'skipped', got {build.get('test_browser')!r}")

        # Commands should be python-flavored
        commands = cfg.get("commands", {})
        if "pytest" not in commands.get("test", []):
            errors.append(f"django: commands.test missing pytest: {commands.get('test')}")
        if any("pnpm" in c for c in commands.get("test", [])):
            errors.append(f"django: commands.test should not have pnpm: {commands.get('test')}")

        # APP_FLOW should note backend-only (placeholder content)
        app_flow = (fixture / "docs/architecture/APP_FLOW.md").read_text()
        if "backend-only" not in app_flow.lower() and "no UI" not in app_flow.lower():
            errors.append("django: APP_FLOW should note backend-only shape")
    finally:
        cleanup(fixture)
    return errors


def test_polyglot_ts_python_shape() -> list[str]:
    """Polyglot (TS + Python) shape. Commands must include both suites."""
    errors = []
    # Polyglot fixture declares workspaces so the package.json maps to
    # ts_monorepo (a bare single-app package.json now maps to generic).
    fixture = make_fixture({
        "package.json": json.dumps({
            "name": "poly",
            "workspaces": ["apps/*"],
            "dependencies": {"next": "15.0.0"},
        }),
        "pyproject.toml": '[project]\nname = "poly-be"\ndependencies = ["django>=5"]\n',
    })
    try:
        rc, out, err = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"polyglot: exited {rc}. stderr: {err[:300]}")
            return errors

        cfg = load_config(fixture)
        test_cmds = cfg["commands"]["test"]
        if "pnpm test" not in test_cmds:
            errors.append(f"polyglot: commands.test missing 'pnpm test': {test_cmds}")
        if "pytest" not in test_cmds:
            errors.append(f"polyglot: commands.test missing 'pytest': {test_cmds}")

        tech_stack = (fixture / "docs/architecture/TECH_STACK.md").read_text()
        if "TypeScript" not in tech_stack or "Python" not in tech_stack:
            errors.append("polyglot: TECH_STACK should mention both TS and Python")
    finally:
        cleanup(fixture)
    return errors


def test_zero_manifest_generic() -> list[str]:
    """Zero-manifest repo → generic adapter, no crashes, empty commands."""
    errors = []
    fixture = make_fixture({"README.md": "docs-only repo"})
    try:
        rc, out, err = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"zero-manifest: exited {rc}. stderr: {err[:300]}")
            return errors

        cfg = load_config(fixture)
        commands = cfg["commands"]
        # Generic adapter returns empty arrays → config has empty arrays
        for key in ("test", "typecheck", "lint", "format", "build"):
            if commands[key] != []:
                errors.append(f"zero-manifest: commands.{key} should be [], got {commands[key]!r}")
    finally:
        cleanup(fixture)
    return errors


def test_config_roundtrip() -> list[str]:
    """Generated config.yml must load cleanly through the config loader."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        rc, _, err = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"roundtrip: generator exited {rc}. stderr: {err[:300]}")
            return errors

        cfg = load_config(fixture)
        if cfg.get("__errors__"):
            errors.append(f"roundtrip: loader reported errors: {cfg['__errors__']}")
    finally:
        cleanup(fixture)
    return errors


def test_secret_scan_blocks_write() -> list[str]:
    """If a template somehow interpolates a secret-like string, the generator
    must refuse to write."""
    errors = []
    # Seed a malicious product name that would embed a plausible secret into
    # the generated PRD (the generator uses --product-name in PRD.md.j2).
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        # Note: we use a well-known fake pattern (AWS-like) that the built-in
        # scanner WILL flag. If the scanner doesn't fire, the test fails.
        rc, out, err = run_generator(
            fixture, "--force", "--product-name=AKIAIOSFODNN7EXAMPLE",
        )
        if rc == 0:
            errors.append("secret scan did not block write; exited 0 for hostile product name")
        if "Refusing to write" not in err and "secret" not in err.lower():
            errors.append(f"secret scan error message missing: {err[:300]}")
    finally:
        cleanup(fixture)
    return errors


def test_skip_existing_defaults() -> list[str]:
    """Re-running on a repo with existing docs — default behavior is keep
    (without --force and without interactive input, it keeps)."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        # First run creates everything
        rc1, _, err1 = run_generator(fixture, "--force")
        if rc1 != 0:
            errors.append(f"initial gen failed: {err1[:300]}")
            return errors

        # Touch PRD to prove it won't be overwritten
        prd = fixture / "docs/architecture/PRD.md"
        prd.write_text("USER-AUTHORED SENTINEL")

        # Re-run without --force and without TTY → should default to keep
        rc2, out2, _ = run_generator(fixture)
        if rc2 != 0:
            errors.append(f"re-run failed: rc={rc2}")
            return errors

        # PRD content should be untouched
        if prd.read_text() != "USER-AUTHORED SENTINEL":
            errors.append("re-run clobbered user-authored PRD (expected keep-default)")

        # Summary should report this file as kept
        summary = json.loads(out2)["summary"]
        if not any("PRD.md" in k for k in summary["kept"]):
            errors.append(f"summary didn't report PRD.md as kept: {summary}")
    finally:
        cleanup(fixture)
    return errors


def test_launchpad_yml_protected_from_force() -> list[str]:
    """--force should still prompt for .launchpad/config.yml (and default to
    keep in non-TTY context); never silently clobber user-tuned config."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        # Initial gen
        run_generator(fixture, "--force")

        # Mark config.yml as user-tuned
        cfg_path = fixture / ".launchpad/config.yml"
        original = cfg_path.read_text()
        cfg_path.write_text(original + "\n# user-added comment")
        modified = cfg_path.read_text()

        # Re-run with --force — the generator's prompt_overwrite falls back to
        # 'keep' in non-interactive mode (stdin is not a TTY in subprocess).
        rc, out, _ = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"--force on existing: rc={rc}")
            return errors

        after = cfg_path.read_text()
        if after != modified:
            errors.append(
                "--force clobbered .launchpad/config.yml in non-interactive mode "
                "(expected keep — TTY-gated)"
            )
    finally:
        cleanup(fixture)
    return errors


def test_tech_stack_strips_manifest_scripts() -> list[str]:
    """TECH_STACK.md should NOT contain secret-bearing package.json scripts values."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({
            "name": "risky",
            "dependencies": {"next": "15"},
            "scripts": {
                "start": "DATABASE_URL=postgres://user:sensitivepass@db/prod node server.js",
            },
        }),
    })
    try:
        rc, _, err = run_generator(fixture, "--force")
        if rc != 0:
            # The secret scanner might fire before write — that's fine too.
            # Only fail if rc != 0 for a reason OTHER than secret detection.
            if "secret" not in err.lower() and "refus" not in err.lower():
                errors.append(f"gen unexpectedly failed: {err[:300]}")
            return errors

        tech_stack = (fixture / "docs/architecture/TECH_STACK.md").read_text()
        if "sensitivepass" in tech_stack:
            errors.append("TECH_STACK.md leaked the literal DB password")
    finally:
        cleanup(fixture)
    return errors


def test_agents_yml_seeded_polyglot() -> list[str]:
    """/lp-define seeds .launchpad/agents.yml with stack-aware agent roster.
    Polyglot (TS + Python) must include both kieran-foad-ts-reviewer and
    kieran-foad-python-reviewer."""
    errors = []
    fixture = make_fixture({
        # Workspaces declared so package.json maps to ts_monorepo (a bare
        # single-app package.json now maps to generic, which would not
        # exercise the TS-reviewer-roster-seeded path this test covers).
        "package.json": json.dumps({
            "workspaces": ["apps/*"],
            "dependencies": {"next": "15"},
        }),
        "pyproject.toml": '[project]\nname = "poly"\ndependencies = ["django"]\n',
    })
    try:
        rc, out, err = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"polyglot agents.yml: rc={rc}. stderr: {err[:300]}")
            return errors

        agents_path = fixture / ".launchpad/agents.yml"
        if not agents_path.is_file():
            errors.append(".launchpad/agents.yml not written for polyglot fixture")
            return errors

        summary = json.loads(out)["summary"]
        if ".launchpad/agents.yml" not in summary["written"]:
            errors.append(f"agents.yml missing from generator 'written' list: {summary['written']}")

        content = agents_path.read_text()
        required = [
            "review_agents:", "review_db_agents:", "review_design_agents:",
            "review_copy_agents:", "harden_plan_agents:", "harden_plan_conditional_agents:",
            "harden_document_agents:", "protected_branches:",
        ]
        for section in required:
            if section not in content:
                errors.append(f"agents.yml missing required section: {section}")

        if "lp-kieran-foad-ts-reviewer" not in content:
            errors.append("polyglot agents.yml missing lp-kieran-foad-ts-reviewer (TS detected)")
        if "lp-kieran-foad-python-reviewer" not in content:
            errors.append("polyglot agents.yml missing lp-kieran-foad-python-reviewer (Python detected)")
        if "lp-frontend-races-reviewer" not in content:
            errors.append("polyglot agents.yml missing lp-frontend-races-reviewer (TS has frontend)")
        # Must NOT accidentally include non-existent agents
        if "lp-lp-" in content:
            errors.append("agents.yml has double-prefix lp-lp-")
    finally:
        cleanup(fixture)
    return errors


def test_agents_yml_ts_only_omits_python_reviewer() -> list[str]:
    """TS-only stack must not list lp-kieran-foad-python-reviewer."""
    errors = []
    # Workspaces declared so package.json maps to ts_monorepo. A bare
    # single-app package.json now maps to generic, which would not seed
    # the lp-kieran-foad-ts-reviewer the test asserts is present.
    fixture = make_fixture({
        "package.json": json.dumps({
            "workspaces": ["apps/*"],
            "dependencies": {"next": "15"},
        }),
    })
    try:
        run_generator(fixture, "--force")
        content = (fixture / ".launchpad/agents.yml").read_text()
        if "lp-kieran-foad-python-reviewer" in content:
            errors.append("ts-only agents.yml erroneously includes python reviewer")
        if "lp-kieran-foad-ts-reviewer" not in content:
            errors.append("ts-only agents.yml missing ts reviewer")
    finally:
        cleanup(fixture)
    return errors


def test_agents_yml_python_only_omits_ts_reviewer() -> list[str]:
    """Python-only stack must not list lp-kieran-foad-ts-reviewer or lp-frontend-races-reviewer."""
    errors = []
    fixture = make_fixture({
        "pyproject.toml": '[project]\nname = "py"\ndependencies = ["django"]\n',
    })
    try:
        run_generator(fixture, "--force")
        content = (fixture / ".launchpad/agents.yml").read_text()
        if "lp-kieran-foad-ts-reviewer" in content:
            errors.append("python-only agents.yml erroneously includes ts reviewer")
        if "lp-frontend-races-reviewer" in content:
            errors.append("python-only agents.yml erroneously includes frontend-races")
        if "lp-kieran-foad-python-reviewer" not in content:
            errors.append("python-only agents.yml missing python reviewer")
    finally:
        cleanup(fixture)
    return errors


def test_agents_yml_protected_from_force_overwrite() -> list[str]:
    """Like config.yml: .launchpad/agents.yml is protected from [a]ll-overwrite.
    --force in non-TTY mode defaults to keep → user-tuned content preserved."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        run_generator(fixture, "--force")
        agents_path = fixture / ".launchpad/agents.yml"
        original = agents_path.read_text()
        marker = "\n# user-tuned comment — must not be clobbered"
        agents_path.write_text(original + marker)
        modified = agents_path.read_text()

        rc, _, _ = run_generator(fixture, "--force")
        if rc != 0:
            errors.append(f"--force on existing agents.yml: rc={rc}")
            return errors

        after = agents_path.read_text()
        if after != modified:
            errors.append("--force clobbered user-tuned agents.yml (non-TTY should keep)")
        if marker not in after:
            errors.append(f"user marker lost: {after[-200:]!r}")
    finally:
        cleanup(fixture)
    return errors


def test_sections_dir_created_by_generator() -> list[str]:
    """/lp-define should mkdir -p paths.sections_dir so /lp-shape-section
    doesn't fail on a missing-directory error."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        run_generator(fixture, "--force")
        sections_dir = fixture / "docs/tasks/sections"
        if not sections_dir.is_dir():
            errors.append(f"docs/tasks/sections not created by generator")
    finally:
        cleanup(fixture)
    return errors


def test_sections_dir_respects_custom_paths() -> list[str]:
    """If the user customizes paths.sections_dir, the generator must create
    the customized path (not the default)."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        # Initial run creates config.yml with default
        run_generator(fixture, "--force")
        cfg_path = fixture / ".launchpad/config.yml"
        # Replace sections_dir in the config
        cfg_text = cfg_path.read_text()
        cfg_text = cfg_text.replace(
            'sections_dir: "docs/tasks/sections"',
            'sections_dir: "docs/custom-sections"',
        )
        cfg_path.write_text(cfg_text)

        # Second run should mkdir the custom path (we only need the mkdir step
        # to pick up the customized config; writes beyond config.yml may be
        # skipped in non-TTY mode which is fine).
        run_generator(fixture, "--force")

        if not (fixture / "docs/custom-sections").is_dir():
            errors.append("generator did not create user-customized sections_dir")
    finally:
        cleanup(fixture)
    return errors


def test_sections_dir_rejects_path_traversal() -> list[str]:
    """Realpath confinement: sections_dir with ../ must be rejected, not created."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        run_generator(fixture, "--force")
        cfg_path = fixture / ".launchpad/config.yml"
        # Note: the config loader ALSO defends against this on read, but this
        # test specifically checks the generator's mkdir step for defense-in-depth.
        # We have to bypass the loader's rejection by writing directly.
        cfg_text = cfg_path.read_text()
        cfg_text = cfg_text.replace(
            'sections_dir: "docs/tasks/sections"',
            'sections_dir: "../escape-attempt"',
        )
        cfg_path.write_text(cfg_text)

        run_generator(fixture, "--force")

        # Parent of the fixture should NOT have the escape-attempt dir
        escaped = fixture.parent / "escape-attempt"
        if escaped.exists():
            escaped.rmdir()  # cleanup in case the guard failed
            errors.append("path traversal not blocked — created ../escape-attempt")
    finally:
        cleanup(fixture)
    return errors


def test_audit_gitignore_added_when_missing() -> list[str]:
    """/lp-define must append .launchpad/audit.log to .gitignore when
    the file doesn't already have it, so committing audit.log is not the default."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        run_generator(fixture, "--force")
        gi = fixture / ".gitignore"
        if not gi.is_file():
            errors.append(".gitignore not created after /lp-define on greenfield")
            return errors
        content = gi.read_text()
        if ".launchpad/audit.log" not in content:
            errors.append(f".gitignore missing audit.log entry: {content!r}")
    finally:
        cleanup(fixture)
    return errors


def test_audit_gitignore_appended_to_existing() -> list[str]:
    """Preserves pre-existing .gitignore content and appends the audit entry."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
        ".gitignore": "node_modules/\n.env.local\n",
    })
    try:
        run_generator(fixture, "--force")
        content = (fixture / ".gitignore").read_text()
        if "node_modules/" not in content:
            errors.append("pre-existing node_modules/ line lost after append")
        if ".env.local" not in content:
            errors.append("pre-existing .env.local line lost after append")
        if ".launchpad/audit.log" not in content:
            errors.append("audit.log entry not appended to existing .gitignore")
    finally:
        cleanup(fixture)
    return errors


def test_audit_gitignore_idempotent_on_rerun() -> list[str]:
    """Second /lp-define run must not add a duplicate audit.log line."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
    })
    try:
        run_generator(fixture, "--force")
        run_generator(fixture, "--force")
        content = (fixture / ".gitignore").read_text()
        count = content.count(".launchpad/audit.log")
        if count != 1:
            errors.append(f"expected 1 audit.log entry after 2 runs, got {count}")
    finally:
        cleanup(fixture)
    return errors


def test_audit_gitignore_respects_existing_entry() -> list[str]:
    """If .gitignore already has .launchpad/audit.log, no duplicate appended."""
    errors = []
    fixture = make_fixture({
        "package.json": json.dumps({"dependencies": {"next": "15"}}),
        ".gitignore": "node_modules/\n.launchpad/audit.log\n",
    })
    try:
        run_generator(fixture, "--force")
        content = (fixture / ".gitignore").read_text()
        count = content.count(".launchpad/audit.log")
        if count != 1:
            errors.append(f"expected 1 audit.log entry, got {count}. content: {content!r}")
    finally:
        cleanup(fixture)
    return errors


def main() -> int:
    tests = [
        ("ts_monorepo_happy_path", test_ts_monorepo_happy_path),
        ("django_backend_only", test_django_backend_only),
        ("polyglot_ts_python_shape", test_polyglot_ts_python_shape),
        ("zero_manifest_generic", test_zero_manifest_generic),
        ("config_roundtrip", test_config_roundtrip),
        ("secret_scan_blocks_write", test_secret_scan_blocks_write),
        ("skip_existing_defaults", test_skip_existing_defaults),
        ("launchpad_yml_protected_from_force", test_launchpad_yml_protected_from_force),
        ("tech_stack_strips_manifest_scripts", test_tech_stack_strips_manifest_scripts),
        ("agents_yml_seeded_polyglot", test_agents_yml_seeded_polyglot),
        ("agents_yml_ts_only_omits_python_reviewer", test_agents_yml_ts_only_omits_python_reviewer),
        ("agents_yml_python_only_omits_ts_reviewer", test_agents_yml_python_only_omits_ts_reviewer),
        ("agents_yml_protected_from_force_overwrite", test_agents_yml_protected_from_force_overwrite),
        ("sections_dir_created_by_generator", test_sections_dir_created_by_generator),
        ("sections_dir_respects_custom_paths", test_sections_dir_respects_custom_paths),
        ("sections_dir_rejects_path_traversal", test_sections_dir_rejects_path_traversal),
        ("audit_gitignore_added_when_missing", test_audit_gitignore_added_when_missing),
        ("audit_gitignore_appended_to_existing", test_audit_gitignore_appended_to_existing),
        ("audit_gitignore_idempotent_on_rerun", test_audit_gitignore_idempotent_on_rerun),
        ("audit_gitignore_respects_existing_entry", test_audit_gitignore_respects_existing_entry),
    ]
    all_errors = []
    for name, test in tests:
        errs = test()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: define acceptance")
        for e in all_errors:
            print(e)
        return 1

    print(f"PASS: define acceptance ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
