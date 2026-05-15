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
import json
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

VALID_STAGES = ("test", "typecheck", "lint", "format", "build", "dev")


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
            f".launchpad/config.yml not found at {cfg_path}. Run /lp-define to seed it."
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
        raise ValueError(
            f"commands.{stage}: expected list or string, got {type(val).__name__}"
        )
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


def _resolve_review_state(repo_root: Path) -> tuple[str, str, int]:
    """Invoke plugin-config-hash.py --resolve-review-state and return
    (outcome, new_hash, returncode).

    Outcomes per HANDSHAKE §3 5-branch truth table:
      ACCEPTED — current scheme matches OR legacy YAML matches (soft-warn)
      REPROMPT — neither matches; config genuinely changed
      REPROMPT_FIRST_TIME — env var unset entirely
      REPROMPT_AUTO_REVIEW_OUTSIDE_CI — auto-review opt-in outside CI

    Returns ("", "", code) on subprocess error so caller can fail closed.
    """
    script = SCRIPT_DIR / "plugin-config-hash.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            f"--repo-root={repo_root}",
            "--resolve-review-state",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 1:
        # plugin-config-hash.py prints to stdout/stderr already; surface as
        # error state.
        return "", "", result.returncode
    try:
        payload = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return "", "", result.returncode
    return (
        str(payload.get("outcome", "")),
        str(payload.get("hash", "")),
        result.returncode,
    )


def check_ci_override(repo_root: Path) -> int:
    """Validate LP_CONFIG_REVIEWED if set, honoring the v1.x→v2.0
    legacy-hash migration path.

    Per PR #41 cycle-12 #1 closure (v2.0.1 BL-244 #1): delegates to
    plugin-config-hash.py's resolve_review_state() so the v1.x legacy
    YAML hash is honored through the v2.0.x soak window. Previously this
    function did its own raw-string compare against `_compute_hash`,
    which silently rejected the v1.x legacy hash even though
    plugin-config-hash.py had a documented migration path for it.
    Result: v1.x users upgrading to v2.0 with a valid `LP_CONFIG_REVIEWED`
    pin would be refused on first run despite the documented soft-warn
    semantics.

    Returns:
      0 — env not set OR matches new hash OR matches legacy hash (ok)
      2 — env set but neither new nor legacy matches (refuse)
    """
    outcome, new_hash, rc = _resolve_review_state(repo_root)

    # Subprocess failure (rc != 0 with no parsed outcome) — fail closed.
    if rc not in (0, 2) or not outcome:
        print(
            "REFUSE: LP_CONFIG_REVIEWED could not be resolved "
            "(plugin-config-hash.py --resolve-review-state failed). "
            "Restore .launchpad/config.yml and retry, or unset "
            "LP_CONFIG_REVIEWED for unpinned interactive runs.",
            file=sys.stderr,
        )
        return 2

    # Allowed-to-proceed outcomes per the 5-branch truth table.
    if outcome in ("ACCEPTED", "REPROMPT_FIRST_TIME"):
        return 0

    # REPROMPT or REPROMPT_AUTO_REVIEW_OUTSIDE_CI — refuse with the same
    # diagnostic the previous shape produced. Keep the 16-char prefix
    # acceptance hint for users running locally.
    env_val = os.environ.get("LP_CONFIG_REVIEWED", "").strip()
    print(
        "REFUSE: LP_CONFIG_REVIEWED does not match current commands section "
        "(neither the v2.0 hash nor the v1.x legacy hash matched).\n"
        f"  expected (v2.0):  {new_hash}\n"
        f"  got:              {env_val}\n"
        "This env var pins the exact commands block that was reviewed. "
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
            f"[preflight ok] requested-stage={stage}; all-stages-validated ({summary})",
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

    if stage == "dev":
        if len(cmds) > 1:
            print(
                f"error: commands.dev must contain at most 1 entry; got {len(cmds)}. "
                "For multiple dev servers, use 'concurrently' or 'npm-run-all'.",
                file=sys.stderr,
            )
            return 2
        # DA2 (flipped) + DA3: route through safe_run_long_shell which inherits
        # Phase 4's SIGINT/SIGTERM/SIGKILL ladder. POSIX-only refusal happens
        # inside the helper; non-POSIX raises SafeRunUnsupportedPlatform.
        from safe_run import (
            SafeRunInterrupted,
            SafeRunInvalidCommand,
            SafeRunTimedOut,
            SafeRunUnsupportedPlatform,
            safe_run_long_shell,
        )

        cmd = cmds[0]
        prefix = f"[{stage} 1/1]"
        print(f"{prefix} {cmd}", file=sys.stderr)
        try:
            result = safe_run_long_shell(cmd, repo_root)
        except SafeRunInterrupted:
            return 130
        except SafeRunTimedOut:
            return 137
        except SafeRunUnsupportedPlatform as exc:
            print(f"error: dev_stage_unsupported_on_platform: {exc}", file=sys.stderr)
            return 2
        except SafeRunInvalidCommand as exc:
            print(f"error: invalid commands.dev entry: {exc}", file=sys.stderr)
            return 2
        if result.returncode != 0:
            print(
                f"{prefix} exited {result.returncode}; stopping stage",
                file=sys.stderr,
            )
            return result.returncode
        return 0

    for i, cmd in enumerate(cmds, start=1):
        prefix = f"[{stage} {i}/{len(cmds)}]"
        print(f"{prefix} {cmd}", file=sys.stderr)
        rc, prompt_bail = _run_cmd_with_prompt_detection(cmd, repo_root)
        # v2.1.5 BL-340: if the command exited 0 but bailed silently on a
        # non-TTY interactive prompt, treat as failure. Without this, e.g.
        # `pnpm astro check` would auto-install-prompt → exit 0 → false-pass.
        if rc == 0 and prompt_bail:
            print(
                f"{prefix} false-pass: exit 0 but interactive prompt detected "
                f"on non-TTY stdin ({prompt_bail!r}). The command likely bailed "
                f"silently on missing dev-deps. /lp-define should wire the deps "
                f"as devDependencies, or the command should have a non-interactive "
                f"flag (e.g., --yes / --no).",
                file=sys.stderr,
            )
            return 2
        if rc != 0:
            print(f"{prefix} exited {rc}; stopping stage", file=sys.stderr)
            return rc

    return 0


# v2.1.5 BL-340: prompt-pattern strings that, when seen in command output
# alongside an exit-0, indicate the command bailed on a non-TTY interactive
# prompt (e.g. `pnpm astro check` prompting to install @astrojs/check then
# silently exiting when stdin isn't a TTY).
#
# Codex/Greptile review fix on PR #68: narrowed to anchored prompt-shaped
# strings to avoid false-positives on legitimate tool output. Specifically
# dropped `[Y/n]` / `[y/N]` / `(yes)` / `non-interactive` (all too broad —
# `pnpm install --reporter=append-only` or any tool that logs "running in
# non-interactive mode" while completing successfully would have been
# mis-flagged). Kept the unambiguous "Continue? …" pnpm shape and tools
# that state they're bailing because no TTY ("Not running in a TTY").
_PROMPT_BAIL_PATTERNS: tuple[str, ...] = (
    "Continue? Yes / No",
    "Continue? (Y/n)",
    "Continue? (y/N)",
    "Continue? [Y/n]",
    "Continue? [y/N]",
    "Do you want to install",
    "Press y to install",
    "Not running in a TTY",
)


def _run_cmd_with_prompt_detection(cmd: str, repo_root: Path) -> tuple[int, str | None]:
    """Run `cmd` via shell, tee stdout/stderr to the terminal, and scan
    each line for known interactive-prompt patterns.

    Returns `(returncode, prompt_bail_pattern_or_None)`. When the command
    exits 0 but a prompt pattern was seen, the caller treats the run as
    a false-pass and returns a non-zero exit. v2.1.5 BL-340.

    Subprocess invocation parity with the prior `subprocess.run(...,
    shell=True, cwd=repo_root)` call site: same shell=True semantics
    (commands.<stage> array is the LP_CONFIG_REVIEWED-gated boundary;
    see BL-308 | HANDSHAKE §6 | Phase 3 §6 threat-model). Stdin is
    NOT redirected — preserves prior behavior where non-TTY-detecting
    tools see the runner's stdin (inherits from the parent process).
    """

    proc = subprocess.Popen(  # nosec B602 -- shell=True intentional, see run_stage call site comment
        cmd,
        shell=True,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    # v2.1.5 round-3 review fix B13 (ts-reviewer P2): `assert proc.stdout
    # is not None` is stripped under `python -O`. Use a runtime check
    # that survives optimization mode. Popen with stdout=PIPE guarantees
    # a non-None stdout per the stdlib contract, so the early-return
    # branch is defensive — never reached in practice.
    stdout = proc.stdout
    detected: str | None = None
    if stdout is None:  # defensive; Popen(stdout=PIPE) contract makes this unreachable
        proc.wait()
        return proc.returncode, None
    try:
        for line in iter(stdout.readline, ""):
            # Tee to terminal so the user sees real-time output.
            sys.stdout.write(line)
            sys.stdout.flush()
            if detected is None:
                for pattern in _PROMPT_BAIL_PATTERNS:
                    if pattern in line:
                        detected = pattern
                        break
    finally:
        # Codex/Greptile review fix on PR #68: reap the subprocess inside
        # `finally` so a stdout-write exception (e.g. broken pipe) doesn't
        # leave a zombie process. Prior shape called `proc.wait()` outside
        # the finally and would skip reaping on any exception in the loop.
        stdout.close()
        proc.wait()
    return proc.returncode, detected


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
