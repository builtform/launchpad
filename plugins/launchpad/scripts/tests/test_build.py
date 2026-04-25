#!/usr/bin/env python3
"""Acceptance tests for /lp-build + supporting scripts.

Covers:
  - plugin-config-hash.py: canonical sha256 matches across
    semantically-equivalent config.yml files; different on meaningful edits
  - plugin-audit-log.py: appends one line per invocation; content survives
    rebase/amend (content hash used, not commit SHA)
  - plugin-build-runner.py:
    - [] stage silently skips (exit 0)
    - single command runs
    - array form runs serially; stops at first non-zero
    - LP_CONFIG_REVIEWED mismatch refuses loudly (exit 2)
    - LP_CONFIG_REVIEWED match proceeds
  - .gitignore contains audit.log
  - lp-build.md has Step 0 with all required references
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_SCRIPTS.parent.parent.parent
HASH_SCRIPT = str(PLUGIN_SCRIPTS / "plugin-config-hash.py")
AUDIT_SCRIPT = str(PLUGIN_SCRIPTS / "plugin-audit-log.py")
RUNNER = str(PLUGIN_SCRIPTS / "plugin-build-runner.py")


def make_fixture(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-phase5-"))
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def cleanup(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)


def run(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


# --- config-hash tests ---

def test_hash_is_stable_across_whitespace() -> list[str]:
    """Canonical hash must not change for semantically-equivalent YAML."""
    errors = []
    a = make_fixture({".launchpad/config.yml": """
commands:
  test:
    - "pnpm test"
  build:
    - "pnpm build"
"""})
    b = make_fixture({".launchpad/config.yml": """
commands:
  build: ["pnpm build"]
  test: ["pnpm test"]
"""})
    try:
        r1 = run([sys.executable, HASH_SCRIPT, f"--repo-root={a}"])
        r2 = run([sys.executable, HASH_SCRIPT, f"--repo-root={b}"])
        if r1.returncode != 0 or r2.returncode != 0:
            errors.append(f"hash script failed: a={r1.stderr!r} b={r2.stderr!r}")
            return errors
        h1, h2 = r1.stdout.strip(), r2.stdout.strip()
        if h1 != h2:
            errors.append(
                f"canonicalization broken: different hashes for equivalent YAML\n"
                f"  a: {h1}\n  b: {h2}"
            )
    finally:
        cleanup(a)
        cleanup(b)
    return errors


def test_hash_changes_with_meaningful_edit() -> list[str]:
    errors = []
    a = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["pnpm test"]\n'})
    b = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["malicious-cmd"]\n'})
    try:
        h1 = run([sys.executable, HASH_SCRIPT, f"--repo-root={a}"]).stdout.strip()
        h2 = run([sys.executable, HASH_SCRIPT, f"--repo-root={b}"]).stdout.strip()
        if h1 == h2:
            errors.append(f"meaningful edit not detected: both hash to {h1}")
    finally:
        cleanup(a)
        cleanup(b)
    return errors


# --- build-runner tests ---

def test_runner_empty_stage_skips() -> list[str]:
    errors = []
    fixture = make_fixture({".launchpad/config.yml": """
commands:
  test: []
"""})
    try:
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"])
        if r.returncode != 0:
            errors.append(f"empty stage should exit 0, got {r.returncode}. stderr: {r.stderr[:200]}")
        if "skipped" not in r.stderr.lower():
            errors.append(f"empty stage didn't mention skip in stderr: {r.stderr!r}")
    finally:
        cleanup(fixture)
    return errors


def test_runner_serial_execution() -> list[str]:
    errors = []
    fixture = make_fixture({".launchpad/config.yml": """
commands:
  test:
    - "true"
    - "true"
    - "true"
"""})
    try:
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"])
        if r.returncode != 0:
            errors.append(f"all-true sequence should exit 0, got {r.returncode}")
        # Verify all 3 commands were logged
        ran = sum(1 for line in r.stderr.splitlines() if "[test " in line and "true" in line)
        if ran != 3:
            errors.append(f"expected 3 command executions, saw {ran}")
    finally:
        cleanup(fixture)
    return errors


def test_runner_stops_on_first_failure() -> list[str]:
    errors = []
    fixture = make_fixture({".launchpad/config.yml": """
commands:
  test:
    - "true"
    - "false"
    - "echo should-not-run"
"""})
    try:
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"])
        if r.returncode == 0:
            errors.append("failing sequence returned 0; expected non-zero")
        if "should-not-run" in r.stderr:
            errors.append("runner continued after failure (should have stopped)")
    finally:
        cleanup(fixture)
    return errors


def test_runner_ci_override_mismatch_refuses() -> list[str]:
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["true"]\n'})
    try:
        env = dict(os.environ)
        env["LP_CONFIG_REVIEWED"] = "deadbeef-this-is-not-the-right-hash"
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"], env=env)
        if r.returncode != 2:
            errors.append(f"mismatch should exit 2, got {r.returncode}. stderr: {r.stderr[:300]}")
        if "REFUSE" not in r.stderr and "refuse" not in r.stderr.lower():
            errors.append(f"mismatch didn't refuse loudly: {r.stderr[:300]}")
        if "expected:" not in r.stderr.lower():
            errors.append(f"mismatch should print expected hash: {r.stderr[:300]}")
    finally:
        cleanup(fixture)
    return errors


def test_runner_ci_override_match_passes() -> list[str]:
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["true"]\n'})
    try:
        # Compute the correct hash
        h_result = run([sys.executable, HASH_SCRIPT, f"--repo-root={fixture}"])
        current_hash = h_result.stdout.strip()

        env = dict(os.environ)
        env["LP_CONFIG_REVIEWED"] = current_hash
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"], env=env)
        if r.returncode != 0:
            errors.append(f"matching override should exit 0, got {r.returncode}. stderr: {r.stderr[:300]}")
    finally:
        cleanup(fixture)
    return errors


def test_runner_ci_override_accepts_16char_prefix() -> list[str]:
    """When a user copies the 16-char commands_sha from audit.log into
    LP_CONFIG_REVIEWED, the runner accepts it as a prefix match."""
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["true"]\n'})
    try:
        h_result = run([sys.executable, HASH_SCRIPT, f"--repo-root={fixture}"])
        full_hash = h_result.stdout.strip()
        prefix = full_hash[:16]

        env = dict(os.environ)
        env["LP_CONFIG_REVIEWED"] = prefix
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"], env=env)
        if r.returncode != 0:
            errors.append(
                f"16-char prefix should be accepted, got exit {r.returncode}. "
                f"stderr: {r.stderr[:400]}"
            )
        if "REFUSE" in r.stderr:
            errors.append(f"16-char prefix incorrectly refused. stderr: {r.stderr[:400]}")
    finally:
        cleanup(fixture)
    return errors


def test_runner_ci_override_refuse_mentions_audit_truncation() -> list[str]:
    """The runner's refuse message must tell the user about audit.log
    truncation so they understand why a 16-char copy might need to be the full hash."""
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["true"]\n'})
    try:
        env = dict(os.environ)
        env["LP_CONFIG_REVIEWED"] = "notavalidhashnotavalidhashnotvalidhex"
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"], env=env)
        if r.returncode != 2:
            errors.append(f"mismatch should exit 2, got {r.returncode}")
        stderr_lower = r.stderr.lower()
        if "audit.log" not in stderr_lower:
            errors.append(f"refuse message missing audit.log truncation note: {r.stderr[:400]}")
        if "16" not in r.stderr:
            errors.append(f"refuse message missing 16-char explanation: {r.stderr[:400]}")
        if "claude_plugin_root" not in stderr_lower:
            errors.append(f"refuse message missing CLAUDE_PLUGIN_ROOT pointer: {r.stderr[:400]}")
    finally:
        cleanup(fixture)
    return errors


def test_runner_ci_override_rejects_wrong_16char() -> list[str]:
    """A wrong 16-char prefix (valid hex but not a prefix of current) must still refuse."""
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["true"]\n'})
    try:
        env = dict(os.environ)
        env["LP_CONFIG_REVIEWED"] = "deadbeefdeadbeef"  # 16 valid hex, wrong prefix
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"], env=env)
        if r.returncode != 2:
            errors.append(f"wrong 16-char prefix should refuse (exit 2), got {r.returncode}")
        if "REFUSE" not in r.stderr:
            errors.append(f"missing REFUSE message: {r.stderr[:300]}")
    finally:
        cleanup(fixture)
    return errors


def test_runner_missing_config_skips() -> list[str]:
    """No config.yml means no commands — runner skips cleanly."""
    errors = []
    fixture = make_fixture({})
    try:
        r = run([sys.executable, RUNNER, "--stage=test", f"--repo-root={fixture}"])
        if r.returncode != 0:
            errors.append(f"missing config should skip (exit 0), got {r.returncode}")
    finally:
        cleanup(fixture)
    return errors


# --- audit-log tests ---

def test_audit_appends_entry() -> list[str]:
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["pnpm test"]\n'})
    try:
        r = run([sys.executable, AUDIT_SCRIPT, "--command=lp-build", f"--repo-root={fixture}"])
        if r.returncode != 0:
            errors.append(f"audit-log failed: {r.stderr[:200]}")
            return errors

        log = fixture / ".launchpad" / "audit.log"
        if not log.exists():
            errors.append(f"audit.log not created")
            return errors

        content = log.read_text()
        if "command=lp-build" not in content:
            errors.append(f"entry missing command field: {content[:200]}")
        if "commands_sha=" not in content:
            errors.append(f"entry missing commands_sha field: {content[:200]}")
        if "\n" != content[-1]:
            errors.append(f"entry doesn't end with newline: {content[-5:]!r}")
    finally:
        cleanup(fixture)
    return errors


def test_audit_appends_multiple_entries() -> list[str]:
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["pnpm test"]\n'})
    try:
        for _ in range(3):
            r = run([sys.executable, AUDIT_SCRIPT, "--command=lp-build", f"--repo-root={fixture}"])
            if r.returncode != 0:
                errors.append(f"audit-log run failed: {r.stderr[:200]}")
                return errors

        log = fixture / ".launchpad" / "audit.log"
        lines = [l for l in log.read_text().splitlines() if l.strip()]
        if len(lines) != 3:
            errors.append(f"expected 3 entries, got {len(lines)}")
    finally:
        cleanup(fixture)
    return errors


def test_audit_content_hash_survives_rebase() -> list[str]:
    """Content hash (not commit SHA) means rebase/amend doesn't orphan log entries."""
    errors = []
    fixture = make_fixture({".launchpad/config.yml": 'commands:\n  test: ["pnpm test"]\n'})
    try:
        # Compute the hash directly
        h_result = run([sys.executable, HASH_SCRIPT, f"--repo-root={fixture}"])
        current_hash = h_result.stdout.strip()

        # Audit log should record THIS hash (not any commit SHA)
        run([sys.executable, AUDIT_SCRIPT, "--command=lp-build", f"--repo-root={fixture}"])
        log_content = (fixture / ".launchpad" / "audit.log").read_text()

        # 16-char prefix of the hash should appear in the log
        if current_hash[:16] not in log_content:
            errors.append(
                f"audit.log missing content hash prefix {current_hash[:16]!r}. "
                f"Log content: {log_content[:200]}"
            )
    finally:
        cleanup(fixture)
    return errors


# --- gitignore + command file tests ---

def test_gitignore_has_audit_log() -> list[str]:
    errors = []
    gi = REPO_ROOT / ".gitignore"
    content = gi.read_text()
    if "audit.log" not in content:
        errors.append(".gitignore doesn't mention audit.log")
    return errors


def test_lp_build_has_step0() -> list[str]:
    errors = []
    cmd = REPO_ROOT / "plugins" / "launchpad" / "commands" / "lp-build.md"
    content = cmd.read_text()
    must_have = [
        ("Step 0", "Step 0 section"),
        ("autonomous-ack.md", "ack file check"),
        ("plugin-audit-log.py", "audit log invocation"),
        ("plugin-build-runner.py", "build runner reference"),
        ("LP_CONFIG_REVIEWED", "CI override mention"),
        ("pipeline.build.test_browser", "pipeline skip gate"),
        ("autonomous_guard", "integrity check"),
    ]
    for needle, desc in must_have:
        if needle not in content:
            errors.append(f"lp-build.md missing: {desc} ({needle!r})")
    return errors


def main() -> int:
    tests = [
        ("hash_is_stable_across_whitespace", test_hash_is_stable_across_whitespace),
        ("hash_changes_with_meaningful_edit", test_hash_changes_with_meaningful_edit),
        ("runner_empty_stage_skips", test_runner_empty_stage_skips),
        ("runner_serial_execution", test_runner_serial_execution),
        ("runner_stops_on_first_failure", test_runner_stops_on_first_failure),
        ("runner_ci_override_mismatch_refuses", test_runner_ci_override_mismatch_refuses),
        ("runner_ci_override_match_passes", test_runner_ci_override_match_passes),
        ("runner_ci_override_accepts_16char_prefix", test_runner_ci_override_accepts_16char_prefix),
        ("runner_ci_override_refuse_mentions_audit_truncation", test_runner_ci_override_refuse_mentions_audit_truncation),
        ("runner_ci_override_rejects_wrong_16char", test_runner_ci_override_rejects_wrong_16char),
        ("runner_missing_config_skips", test_runner_missing_config_skips),
        ("audit_appends_entry", test_audit_appends_entry),
        ("audit_appends_multiple_entries", test_audit_appends_multiple_entries),
        ("audit_content_hash_survives_rebase", test_audit_content_hash_survives_rebase),
        ("gitignore_has_audit_log", test_gitignore_has_audit_log),
        ("lp_build_has_step0", test_lp_build_has_step0),
    ]
    all_errors = []
    for name, test in tests:
        errs = test()
        if errs:
            all_errors.append(f"FAIL {name}:")
            for e in errs:
                all_errors.append(f"  - {e}")

    if all_errors:
        print("FAIL: build acceptance")
        for e in all_errors:
            print(e)
        return 1

    print(f"PASS: build acceptance ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
