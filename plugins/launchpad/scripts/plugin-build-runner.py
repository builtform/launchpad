#!/usr/bin/env python3
"""Execute commands from config.yml arrays serially, with exit-code aggregation.

Replaces hardcoded `pnpm X` invocations in harness commands. Every test,
typecheck, lint, format, or build stage runs via this script so the exact
executable list comes from the user's `.launchpad/config.yml`.

Contract:
  - commands.* is always an array
  - [] means skip silently
  - Serial execution, left-to-right (parallel deferred to v1.1)
  - Any non-zero exit stops the sequence; the stage's exit code is that exit

CI hash-pin:
  - LP_CONFIG_REVIEWED env var pins the reviewed `commands:` content-hash.
    Mismatched current hash refuses with stderr (expected vs received).
  - Unset env var means "trust the current file-state" — appropriate for
    interactive local sessions where the user just edited config.yml. For
    autonomous / CI runs, set LP_CONFIG_REVIEWED so any drift refuses.
  - See SECURITY.md for the full threat model around config.yml commands.

Usage:
  plugin-build-runner.py --stage=test [--repo-root PATH]

Exit codes:
  0   all commands in the stage succeeded (or [] = skip)
  N   first command that failed returned code N
  2   fatal (bad args, config error, CI override mismatch)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR = SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import yaml  # noqa: E402


VALID_STAGES = ("test", "typecheck", "lint", "format", "build")


class ConfigMissingError(FileNotFoundError):
    """Raised when .launchpad/config.yml is absent.

    Distinct from an explicitly-empty `commands.<stage>: []`, which is a
    legitimate skip marker. Missing config means the harness was never
    seeded — caller should refuse rather than silently exit 0.
    """


def load_commands(repo_root: Path, stage: str) -> list[str]:
    """Load config.yml and return the command list for the requested stage.

    Raises ConfigMissingError when the file does not exist. An empty list
    return value means the file exists but the stage is explicitly empty
    (skip marker).
    """
    cfg_path = repo_root / ".launchpad" / "config.yml"
    if not cfg_path.is_file():
        raise ConfigMissingError(
            f".launchpad/config.yml not found at {cfg_path}. "
            "Run /lp-define to seed it."
        )

    doc = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise ValueError(
            f"config.yml: expected top-level mapping, got {type(doc).__name__}"
        )
    commands = doc.get("commands", {}) or {}
    if not isinstance(commands, dict):
        raise ValueError(
            f"config.yml: 'commands' must be a mapping of stage→list, "
            f"got {type(commands).__name__}"
        )
    val = commands.get(stage, [])

    # Be forgiving: scalar → [scalar], empty string → []
    if isinstance(val, str):
        return [val] if val else []
    if not isinstance(val, list):
        raise ValueError(f"commands.{stage}: expected list or string, got {type(val).__name__}")
    # Every item MUST be a string. Previously this used str(v), which
    # silently coerced YAML scalars like `true`, `123`, or mappings into
    # shell command strings — turning a mistyped config into an executed
    # bogus command. Strings only; refuse anything else with a clear
    # config error. Empty strings are skip markers and are filtered out.
    out: list[str] = []
    for i, v in enumerate(val):
        if v is None or (isinstance(v, str) and v == ""):
            continue
        if not isinstance(v, str):
            raise ValueError(
                f"commands.{stage}[{i}]: expected string, got "
                f"{type(v).__name__} (value={v!r}). YAML scalars like "
                "true/123 are not valid shell commands; quote the value "
                "if it should be passed literally."
            )
        out.append(v)
    return out


def _compute_hash(repo_root: Path) -> str:
    """Invoke plugin-config-hash.py and return the hex digest."""
    script = SCRIPT_DIR / "plugin-config-hash.py"
    result = subprocess.run(
        [sys.executable, str(script), f"--repo-root={repo_root}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def check_ci_override(repo_root: Path) -> int:
    """Validate LP_CONFIG_REVIEWED if set.

    Returns:
      0 — env not set OR matches current hash (ok to proceed)
      2 — env set but mismatches current hash (refuse)
    """
    env_val = os.environ.get("LP_CONFIG_REVIEWED", "").strip()
    if not env_val:
        return 0

    current = _compute_hash(repo_root)
    if not current:
        # Can't compute — fail closed. The user explicitly opted into the
        # pin by setting LP_CONFIG_REVIEWED, so an inability to verify
        # the current hash (missing config.yml, unreadable, malformed) is
        # a hard refuse. Otherwise an attacker who deletes config.yml
        # would silently bypass the gate.
        print(
            "REFUSE: LP_CONFIG_REVIEWED is set but the current commands hash "
            "cannot be computed (missing/unreadable .launchpad/config.yml). "
            "Restore config.yml and re-pin LP_CONFIG_REVIEWED to the new hash, "
            "or unset LP_CONFIG_REVIEWED for unpinned interactive runs.",
            file=sys.stderr,
        )
        return 2

    # Accept a 16-char hex prefix as a convenience — matches what .launchpad/audit.log
    # displays as commands_sha=... . Collision resistance at 64 bits (16 hex chars)
    # is still ~1.8×10^19 combinations, sufficient for CI hash pinning.
    if _is_hex(env_val) and len(env_val) == 16 and current.startswith(env_val):
        return 0

    if env_val != current:
        print(
            "REFUSE: LP_CONFIG_REVIEWED does not match current commands section.\n"
            f"  expected: {current}\n"
            f"  got:      {env_val}\n"
            "This CI env var pins the exact commands block that was reviewed. "
            "A mismatch means config.yml changed since the ack — re-review, "
            "update the env var to the new hash, and retry.\n"
            "\n"
            "Note: .launchpad/audit.log records commands_sha truncated to 16 chars\n"
            "for readability. LP_CONFIG_REVIEWED accepts either the full 64-char\n"
            "hash (preferred) or the 16-char prefix. Run\n"
            "${CLAUDE_PLUGIN_ROOT}/scripts/plugin-config-hash.py\n"
            "to print the full current hash.",
            file=sys.stderr,
        )
        return 2

    return 0


def _is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def run_stage(repo_root: Path, stage: str, *, check_only: bool = False) -> int:
    """Run all commands for a stage serially. Returns first non-zero exit or 0.

    With check_only=True, validates the LP_CONFIG_REVIEWED hash pin and that
    config.yml parses for ALL stages (not just the requested one), but does
    not execute any stage command. This is the preflight mode for harness
    commands that want to verify the gate before target resolution and
    audit-log emission, without side effects. All-stage validation prevents
    a malformed `commands.lint` from passing preflight against
    `--stage=test` and only failing later in the autonomous loop.
    """
    if stage not in VALID_STAGES:
        print(f"invalid stage {stage!r}; valid: {VALID_STAGES}", file=sys.stderr)
        return 2

    # Check CI override FIRST — refuses loudly before running anything.
    rc = check_ci_override(repo_root)
    if rc != 0:
        return rc

    if check_only:
        # Validate every stage's commands list parses, not just the
        # caller-supplied one. The flagged --stage value is informational
        # for the report only.
        per_stage_counts: dict[str, int] = {}
        for s in VALID_STAGES:
            try:
                per_stage_counts[s] = len(load_commands(repo_root, s))
            except ConfigMissingError as e:
                print(f"config error: {e}", file=sys.stderr)
                return 2
            except (yaml.YAMLError, ValueError) as e:
                print(
                    f"config error in commands.{s}: {e}",
                    file=sys.stderr,
                )
                return 2
        summary = ", ".join(f"{s}={n}" for s, n in per_stage_counts.items())
        print(
            f"[preflight ok] requested-stage={stage}; "
            f"all-stages-validated ({summary})",
            file=sys.stderr,
        )
        return 0

    try:
        cmds = load_commands(repo_root, stage)
    except ConfigMissingError as e:
        # Refuse rather than silently skip. Missing config.yml means the
        # harness was never seeded; running a no-op stage as success would
        # let test/typecheck/lint quality gates pass without ever executing.
        print(f"config error: {e}", file=sys.stderr)
        return 2
    except (yaml.YAMLError, ValueError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    if not cmds:
        print(f"[{stage}] skipped (empty array in config.yml)", file=sys.stderr)
        return 0

    for i, cmd in enumerate(cmds, start=1):
        prefix = f"[{stage} {i}/{len(cmds)}]"
        print(f"{prefix} {cmd}", file=sys.stderr)
        result = subprocess.run(cmd, shell=True, cwd=repo_root)
        if result.returncode != 0:
            print(f"{prefix} exited {result.returncode}; stopping stage", file=sys.stderr)
            return result.returncode

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True, choices=VALID_STAGES)
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="validate LP_CONFIG_REVIEWED + config.yml parse without executing commands",
    )
    args = ap.parse_args()

    return run_stage(
        Path(args.repo_root).resolve(),
        args.stage,
        check_only=args.check_only,
    )


if __name__ == "__main__":
    sys.exit(main())
