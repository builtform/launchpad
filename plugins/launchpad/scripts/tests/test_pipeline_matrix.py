#!/usr/bin/env python3
"""End-to-end pipeline tests across ephemeral brownfield scaffolds.

Validates the underlying pipeline that `/lp-kickoff` → `/lp-define` → `/lp-plan`
→ `/lp-build` delegate to, by driving each script against fresh `/tmp` fixtures.
We can't literally invoke slash commands from a test (that needs Claude Code),
but we CAN validate every script and module they call.

Fixture shapes (4):
  1. TS monorepo (non-LaunchPad): plain Next.js + Express, no Turborepo,
     no Prisma. Proves detection doesn't require the template's exact shape.
  2. Django + Postgres: validates Python stack adaptation + pipeline.design=skipped
  3. Go CLI: validates the Go adapter end-to-end
  4. Polyglot (TS + Python): simulates a multi-language brownfield shape

Explicitly out of scope:
  - Real-repo quirks of any specific brownfield (covered by user testing)
  - node_modules at scale, real CI configs, real .env files, commit-history
    interactions — known limitations of fixture-based testing

Pipeline steps validated per fixture:
  A. Stack detector returns correct stacks + frameworks
  B. Doc generator produces all 6 canonical artifacts
  C. Generated config.yml round-trips through the config loader (zero errors)
  D. Prereq-check lite passes on the configured fixture
  E. Build runner handles the commands.test stage (empty or populated per stack)
  F. Audit log appender writes a valid entry
  G. "No silent failures": every script exits with a status code; any non-zero
     includes a user-facing stderr message

Run:
  python3 plugins/launchpad/scripts/tests/test_pipeline_matrix.py
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
DETECTOR = str(PLUGIN_SCRIPTS / "plugin-stack-detector.py")
LOADER = str(PLUGIN_SCRIPTS / "plugin-config-loader.py")
PREREQ = str(PLUGIN_SCRIPTS / "plugin-prereq-check.sh")
RUNNER = str(PLUGIN_SCRIPTS / "plugin-build-runner.py")
AUDIT = str(PLUGIN_SCRIPTS / "plugin-audit-log.py")
HASH_SCRIPT = str(PLUGIN_SCRIPTS / "plugin-config-hash.py")


# --- Fixture builders ---

def _make(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase7-"))
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def _cleanup(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)


def fixture_ts_nonlaunchpad() -> Path:
    """Plain Next.js + Express, no workspaces, no Prisma — not LaunchPad-shaped."""
    return _make({
        "package.json": json.dumps({
            "name": "plain-ts",
            "version": "1.0.0",
            "dependencies": {"next": "15.0.0", "express": "4.18.0", "react": "18.0.0"},
        }),
        "README.md": "# plain-ts\n\nJust a plain Next + Express app.\n",
    })


def fixture_django() -> Path:
    """Django + Postgres backend-only."""
    return _make({
        "pyproject.toml": """
[project]
name = "djapp"
version = "0.1.0"
dependencies = ["django>=5.0", "psycopg2>=2.9"]
""",
        "manage.py": "#!/usr/bin/env python\nimport django\n",
        "README.md": "# djapp\n",
    })


def fixture_go() -> Path:
    return _make({
        "go.mod": "module example.com/hello\n\ngo 1.22\n",
        "main.go": "package main\n\nfunc main() {}\n",
        "README.md": "# go cli\n",
    })


def fixture_polyglot() -> Path:
    """Polyglot fixture: TS + Python together. Includes typescript dep so
    the package.json satisfies all three ts_monorepo gates (workspaces +
    typescript + relevant framework)."""
    return _make({
        "package.json": json.dumps({
            "name": "poly",
            "workspaces": ["apps/*"],
            "dependencies": {"next": "15.0.0"},
            "devDependencies": {"typescript": "5.0.0"},
        }),
        "pyproject.toml": """
[project]
name = "poly-be"
version = "0.1.0"
dependencies = ["django>=5.0"]
""",
        "README.md": "# polyglot\n",
    })


# --- Per-step validators ---

def _run(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, env=env)


def step_A_detector(fixture: Path, expected_stacks: set[str], expected_frameworks: set[str] | None = None) -> list[str]:
    errors = []
    env = dict(os.environ)
    env["LP_REPO_ROOT"] = str(fixture)
    r = _run([sys.executable, DETECTOR], env=env)
    if r.returncode != 0:
        errors.append(f"detector exited {r.returncode}: {r.stderr[:200]}")
        return errors
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        errors.append(f"detector output not valid JSON: {e}")
        return errors
    actual = set(report.get("stacks", []))
    if actual != expected_stacks:
        errors.append(f"detector stacks: expected {expected_stacks}, got {actual}")
    if expected_frameworks is not None:
        actual_fw = set(report.get("frameworks", []))
        missing = expected_frameworks - actual_fw
        if missing:
            errors.append(f"detector frameworks missing: {missing} (got {actual_fw})")
    return errors


def step_B_generator(fixture: Path) -> list[str]:
    errors = []
    r = _run([sys.executable, GENERATOR, f"--repo-root={fixture}", "--force", "--product-name=TestApp"])
    if r.returncode != 0:
        errors.append(f"generator exited {r.returncode}: {r.stderr[:400]}")
        return errors
    expected_artifacts = [
        "docs/architecture/PRD.md",
        "docs/architecture/TECH_STACK.md",
        "docs/architecture/BACKEND_STRUCTURE.md",
        "docs/architecture/APP_FLOW.md",
        "docs/tasks/SECTION_REGISTRY.md",
        ".launchpad/config.yml",
    ]
    for rel in expected_artifacts:
        if not (fixture / rel).is_file():
            errors.append(f"generator missing artifact: {rel}")
    return errors


def step_C_config_roundtrip(fixture: Path) -> list[str]:
    errors = []
    r = _run([sys.executable, LOADER, f"--repo-root={fixture}", "--strict"])
    if r.returncode != 0:
        errors.append(f"config loader (strict) exited {r.returncode}: {r.stderr[:200]}")
        return errors
    try:
        cfg = json.loads(r.stdout)
    except json.JSONDecodeError:
        errors.append(f"config loader output not JSON: {r.stdout[:200]}")
    return errors


def step_D_prereq_lite(fixture: Path) -> list[str]:
    errors = []
    # Simulate an L2 command requiring config.yml exists (which it does after step B)
    env = dict(os.environ)
    env["LP_CACHE_DIR"] = str(Path(tempfile.mkdtemp(prefix="lp-cache-")))
    r = _run(
        [PREREQ, "--mode=lite", "--command=lp-commit", f"--repo-root={fixture}",
         "--require=.launchpad/config.yml"],
        env=env,
    )
    _cleanup(Path(env["LP_CACHE_DIR"]))
    if r.returncode != 0:
        errors.append(f"prereq lite exited {r.returncode}: {r.stderr[:300]}")
    return errors


def step_E_build_runner(fixture: Path, stage: str, expected_empty: bool) -> list[str]:
    """Validate the build runner handles the stage correctly for this fixture."""
    errors = []
    # Replace command values with 'true' so the runner's output is deterministic
    # (we don't actually want to `pnpm test` in CI). We copy the config, rewrite
    # commands[stage] to ["true"] if non-empty, and invoke.
    cfg = fixture / ".launchpad" / "config.yml"
    original = cfg.read_text()

    import re
    # Swap the stage's list entries to ["true"] if present; leave [] alone.
    # Simple line-oriented edit: find the stage block and neutralize.
    swapped = re.sub(
        rf"^  {stage}:\s*\n(\s+-[^\n]+\n)+",
        f"  {stage}:\n    - \"true\"\n",
        original,
        flags=re.MULTILINE,
    )
    cfg.write_text(swapped)

    try:
        r = _run([sys.executable, RUNNER, f"--stage={stage}", f"--repo-root={fixture}"])
        if expected_empty:
            # Empty [] should exit 0 with skip
            if r.returncode != 0:
                errors.append(f"{stage} empty: expected rc=0, got {r.returncode}. stderr: {r.stderr[:200]}")
        else:
            # Populated → `true` command succeeds
            if r.returncode != 0:
                errors.append(f"{stage} populated: expected rc=0, got {r.returncode}. stderr: {r.stderr[:200]}")
    finally:
        cfg.write_text(original)
    return errors


def step_F_audit(fixture: Path) -> list[str]:
    errors = []
    r = _run([sys.executable, AUDIT, "--command=lp-build", f"--repo-root={fixture}"])
    if r.returncode != 0:
        errors.append(f"audit exited {r.returncode}: {r.stderr[:200]}")
        return errors
    log = fixture / ".launchpad" / "audit.log"
    if not log.is_file():
        errors.append("audit.log not created")
        return errors
    content = log.read_text()
    if "command=lp-build" not in content:
        errors.append(f"audit entry missing command field: {content[:200]}")
    return errors


def step_G_no_silent_failures(fixture: Path) -> list[str]:
    """Intentionally break a command and ensure the build runner surfaces it."""
    errors = []
    cfg = fixture / ".launchpad" / "config.yml"
    original = cfg.read_text()

    import re
    # Try the in-place rewrite first (handles non-empty test arrays).
    broken = re.sub(
        r"^  test:\s*\n(\s+-[^\n]+\n)+",
        '  test:\n    - "exit 42"\n',
        original,
        flags=re.MULTILINE,
    )
    if broken == original:
        # Empty test array (generic-adapter shape: 'test: []') needs an
        # array-form rewrite. Match either 'test: []' on one line or
        # 'test:\n' followed by no list items.
        broken = re.sub(
            r"^  test:\s*\[\]\s*$",
            '  test:\n    - "exit 42"',
            original,
            flags=re.MULTILINE,
        )
        if broken == original:
            broken = re.sub(
                r"^  test:\s*\n(?!\s+-)",
                '  test:\n    - "exit 42"\n',
                original,
                flags=re.MULTILINE,
            )
    cfg.write_text(broken)

    try:
        r = _run([sys.executable, RUNNER, f"--stage=test", f"--repo-root={fixture}"])
        if r.returncode != 42:
            errors.append(f"no-silent-failures: expected rc=42 (bubbled), got {r.returncode}")
        if not r.stderr.strip():
            errors.append("no-silent-failures: empty stderr on failure — invisible")
    finally:
        cfg.write_text(original)
    return errors


# --- Per-fixture harness ---

def run_matrix_row(
    name: str,
    fixture: Path,
    *,
    expected_stacks: set[str],
    expected_frameworks: set[str] | None,
    expected_test_empty: bool,
    expected_design_skipped: bool,
) -> list[str]:
    errors: list[str] = []
    try:
        errors.extend(f"{name}.A_detector: {e}" for e in step_A_detector(fixture, expected_stacks, expected_frameworks))
        errors.extend(f"{name}.B_generator: {e}" for e in step_B_generator(fixture))
        errors.extend(f"{name}.C_config: {e}" for e in step_C_config_roundtrip(fixture))
        errors.extend(f"{name}.D_prereq: {e}" for e in step_D_prereq_lite(fixture))
        errors.extend(f"{name}.E_runner_test: {e}" for e in step_E_build_runner(fixture, "test", expected_test_empty))
        errors.extend(f"{name}.F_audit: {e}" for e in step_F_audit(fixture))
        errors.extend(f"{name}.G_no_silent_failures: {e}" for e in step_G_no_silent_failures(fixture))

        # Design-skipped assertion (backend-only shapes)
        if expected_design_skipped:
            cfg_path = fixture / ".launchpad" / "config.yml"
            text = cfg_path.read_text()
            if "design: skipped" not in text and "design_review: skipped" not in text:
                errors.append(f"{name}: expected design to be skipped for backend-only, but config.yml has it enabled")
    finally:
        _cleanup(fixture)
    return errors


# --- Entry ---

MATRIX = [
    {
        # Plain single-app Next + Express, no workspaces, no Turborepo —
        # detector now correctly maps this to 'generic' rather than
        # ts_monorepo, since the ts_monorepo adapter hardcodes pnpm,
        # Turborepo, apps/web/, apps/api/, packages/db/ defaults that do
        # not match a single-app shape. The frameworks list (next.js,
        # express) is still surfaced via the detector's framework
        # detection so docs can mention them; only the *adapter routing*
        # shifts to generic. A future ts_app adapter would handle this
        # better — tracked in ROADMAP for v1.1.
        "name": "ts_non_launchpad",
        "builder": fixture_ts_nonlaunchpad,
        "expected_stacks": {"generic"},
        "expected_frameworks": {"next.js", "express"},
        "expected_test_empty": True,  # generic adapter seeds empty
        "expected_design_skipped": True,  # generic disables design pipeline
    },
    {
        "name": "django",
        "builder": fixture_django,
        "expected_stacks": {"python_django"},
        "expected_frameworks": {"django"},
        "expected_test_empty": False,  # django adapter seeds pytest
        "expected_design_skipped": True,
    },
    {
        "name": "go_cli",
        "builder": fixture_go,
        "expected_stacks": {"go_cli"},
        "expected_frameworks": {"go"},
        "expected_test_empty": False,  # go adapter seeds 'go test ./...'
        "expected_design_skipped": True,
    },
    {
        "name": "polyglot_ts_python_shape",
        "builder": fixture_polyglot,
        "expected_stacks": {"ts_monorepo", "python_django"},
        "expected_frameworks": {"next.js", "django"},
        "expected_test_empty": False,  # both adapters contribute → array with pnpm + pytest
        "expected_design_skipped": False,  # TS precedence keeps design enabled
    },
]


def main() -> int:
    all_errors: list[str] = []
    for row in MATRIX:
        name = row["name"]
        fixture = row["builder"]()
        print(f"--- matrix: {name} at {fixture}")
        errs = run_matrix_row(
            name,
            fixture,
            expected_stacks=row["expected_stacks"],
            expected_frameworks=row["expected_frameworks"],
            expected_test_empty=row["expected_test_empty"],
            expected_design_skipped=row["expected_design_skipped"],
        )
        if errs:
            all_errors.extend(errs)
        else:
            print(f"    PASS")

    if all_errors:
        print(f"\nFAIL: pipeline matrix ({len(all_errors)} findings)")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print(f"\nPASS: pipeline matrix ({len(MATRIX)} fixtures × 7 pipeline steps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
