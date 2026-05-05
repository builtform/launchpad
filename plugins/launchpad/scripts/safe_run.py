"""Subprocess invocation helper (OPERATIONS §1).

Every subprocess call in v2.0 MUST go through `safe_run()`. The module is
internally split into:

  - `_validate_argv()` — pure-CPU argv-shape validator (CI-lint enforced;
    unit-tested without spawning subprocesses).
  - `_safe_run_invoke()` — subprocess-invocation orchestrator (integration path).
  - `safe_run_long()` — long-running variant (Phase 4 v2.1 DA5) for git clone
    + npm-style scaffolders; honors SIGINT via process-group + psutil children
    sweep.

The split keeps the validator hot-path testable without subprocess fork.
"""
from __future__ import annotations

import errno
import os
import re
import signal
import subprocess
import time
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


_DEFAULT_SIGINT_TIMEOUT_S = 2.0
_DEFAULT_SIGTERM_TIMEOUT_S = 3.0


class SafeRunInterrupted(RuntimeError):
    """Raised by safe_run_long when SIGINT propagated through the child group
    and cleanup completed (within the configured ladder budget)."""


class SafeRunTimedOut(RuntimeError):
    """Raised by safe_run_long when the SIGINT/SIGTERM/SIGKILL ladder ran to
    SIGKILL and the child still has surviving descendants per psutil."""


def _kill_descendants(pid: int, sig: int) -> None:
    """Best-effort SIGTERM/SIGKILL ladder targeting all descendants of `pid`.

    Phase 4 plan §3.8: psutil children sweep catches double-fork escapes that
    `os.killpg` alone misses (e.g., when the upstream scaffolder daemonizes).
    psutil import is local + best-effort; if unavailable we degrade to the
    process-group signal which is still POSIX-correct.
    """
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    try:
        children = proc.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    for child in children:
        try:
            child.send_signal(sig)
        except (psutil.NoSuchProcess, OSError):
            continue


def safe_run_long(
    argv: Sequence[str],
    cwd: Path,
    *,
    sigint_timeout_s: float = _DEFAULT_SIGINT_TIMEOUT_S,
    sigterm_timeout_s: float = _DEFAULT_SIGTERM_TIMEOUT_S,
) -> subprocess.CompletedProcess[bytes]:
    """Long-running subprocess variant for git clone + npm-style scaffolders.

    Phase 4 plan §3.8 (DA5 LOCKED at 2s default; opt-in 1s via
    `LAUNCHPAD_SIGINT_TIMEOUT_S`):
      - `subprocess.Popen(argv, start_new_session=True, ...)` so the child
        leads its own process group (`os.setsid`).
      - On `KeyboardInterrupt` / SIGINT: `os.killpg(child_pgid, SIGINT)`,
        then SIGTERM via `psutil.Process.children(recursive=True)` after
        `sigint_timeout_s`, then SIGKILL after a further `sigterm_timeout_s`.
      - Returns `CompletedProcess` on clean exit; raises `SafeRunInterrupted`
        on user SIGINT (after cleanup); raises `SafeRunTimedOut` if SIGKILL
        ladder ran to completion but psutil still reports survivors (rare).

    Reuses `_validate_argv` + `_build_safe_env` so the safety contract from
    `safe_run()` is unchanged.

    Lint exemption (per plan §3.8): this is the only `subprocess.Popen +
    start_new_session` call in v2.0 modules; allowlisted via the safe_run.py
    path-prefix in plugin-v2-handshake-lint.py.
    """
    _validate_argv(argv)
    env = _build_safe_env()

    env_override = os.environ.get("LAUNCHPAD_SIGINT_TIMEOUT_S")
    if env_override is not None:
        try:
            sigint_timeout_s = float(env_override)
        except ValueError:
            pass

    proc = subprocess.Popen(
        list(argv),
        shell=False,
        env=env,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    interrupted = False
    try:
        try:
            stdout, stderr = proc.communicate()
        except KeyboardInterrupt:
            interrupted = True
            stdout, stderr = b"", b""
            _signal_child_group_then_descendants(
                proc, sigint_timeout_s, sigterm_timeout_s
            )
    except BaseException:
        _signal_child_group_then_descendants(
            proc, sigint_timeout_s, sigterm_timeout_s
        )
        raise

    rc = proc.returncode
    if interrupted:
        raise SafeRunInterrupted(
            f"argv[0]={argv[0]!r} interrupted by user; cleanup ran SIGINT -> "
            f"SIGTERM -> SIGKILL ladder within {sigint_timeout_s + sigterm_timeout_s:.1f}s budget"
        )

    return subprocess.CompletedProcess(
        args=list(argv),
        returncode=rc if rc is not None else -1,
        stdout=stdout,
        stderr=stderr,
    )


def _signal_child_group_then_descendants(
    proc: subprocess.Popen,
    sigint_timeout_s: float,
    sigterm_timeout_s: float,
) -> None:
    """SIGINT -> SIGTERM (via psutil) -> SIGKILL ladder on the child group."""
    pid = proc.pid
    try:
        os.killpg(pid, signal.SIGINT)
    except ProcessLookupError:
        return
    except OSError as exc:
        if exc.errno != errno.ESRCH:
            raise

    if _wait_for_exit(proc, sigint_timeout_s):
        return

    _kill_descendants(pid, signal.SIGTERM)
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

    if _wait_for_exit(proc, sigterm_timeout_s):
        return

    _kill_descendants(pid, signal.SIGKILL)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass

    if not _wait_for_exit(proc, 1.0):
        raise SafeRunTimedOut(
            f"safe_run_long pid={pid} did not exit after SIGKILL"
        )


def _wait_for_exit(proc: subprocess.Popen, deadline_s: float) -> bool:
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        if proc.poll() is not None:
            return True
        time.sleep(0.05)
    return proc.poll() is not None


__all__ = [
    "SAFE_ENV_ALLOWLIST",
    "UnsafeArgvError",
    "SafeRunInterrupted",
    "SafeRunTimedOut",
    "safe_run",
    "safe_run_long",
]
