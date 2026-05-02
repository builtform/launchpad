"""Subprocess invocation helper (OPERATIONS §1).

Every subprocess call in v2.0 MUST go through `safe_run()`. The module is
internally split into:

  - `_validate_argv()` — pure-CPU argv-shape validator (CI-lint enforced;
    unit-tested without spawning subprocesses).
  - `_safe_run_invoke()` — subprocess-invocation orchestrator (integration path).

The split keeps the validator hot-path testable without subprocess fork.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Sequence

# argv-element shape: alphanumerics + path-safe punctuation + flag glue.
_ARGV_SAFE_RE = re.compile(r"^[A-Za-z0-9@._\-/=:]+$")


SAFE_ENV_ALLOWLIST = frozenset({
    "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR",
    # Git terminal hardening: GIT_TERMINAL_PROMPT=0 is the only GIT_* allowed
    "GIT_TERMINAL_PROMPT",
})


class UnsafeArgvError(ValueError):
    """An argv element fails the allowlist regex."""


def _validate_argv(argv: Sequence[str]) -> None:
    """Validate every argv element against the allowlist regex.

    Pure-CPU. No subprocess fork. Raises UnsafeArgvError on first bad element.
    """
    if not argv:
        raise UnsafeArgvError("argv is empty")
    for i, el in enumerate(argv):
        if not isinstance(el, str):
            raise UnsafeArgvError(
                f"argv[{i}] is not a string (got {type(el).__name__})"
            )
        if not _ARGV_SAFE_RE.fullmatch(el):
            raise UnsafeArgvError(
                f"argv[{i}] fails allowlist: {el!r}"
            )


def _build_safe_env() -> dict[str, str]:
    """Construct the spawned-process env from the strict allowlist + LC_CTYPE
    override.

    Unknown vars are dropped. LC_CTYPE is forced to C.UTF-8 for byte-deterministic
    scaffolder output across user shells. Per OPERATIONS §1 honest-scope note:
    the override applies to spawned subprocesses only; the orchestrator's own
    LC_CTYPE inherits parent.
    """
    env: dict[str, str] = {}
    for k in SAFE_ENV_ALLOWLIST:
        v = os.environ.get(k)
        if v is not None:
            env[k] = v
    env["LC_CTYPE"] = "C.UTF-8"
    return env


def _safe_run_invoke(
    argv: Sequence[str],
    cwd: Path,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Subprocess-invocation orchestrator. Caller already validated argv."""
    return subprocess.run(
        list(argv),
        shell=False,
        check=True,
        env=_build_safe_env(),
        cwd=str(cwd),
        capture_output=True,
        timeout=timeout,
    )


def safe_run(
    argv: Sequence[str],
    cwd: Path,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run argv as a subprocess with the v2.0 safety contract:

    - argv-list form only (no shell=True)
    - every argv element matches `^[A-Za-z0-9@._\\-/=:]+$`
    - strict env allowlist (unknown vars dropped); LC_CTYPE forced to C.UTF-8
    - cwd is a validated Path (caller's responsibility — use path_validator)
    - stdout/stderr captured; treated as untrusted-as-data
    - subprocess.run(check=True) — raises CalledProcessError on non-zero exit

    Per OPERATIONS §1 + HANDSHAKE §6.
    """
    _validate_argv(argv)
    return _safe_run_invoke(argv, cwd, timeout=timeout)


__all__ = [
    "SAFE_ENV_ALLOWLIST",
    "UnsafeArgvError",
    "safe_run",
]
