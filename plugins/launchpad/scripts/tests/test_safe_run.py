"""Tests for safe_run (OPERATIONS §1).

Covers the pure-CPU `_validate_argv` validator (no subprocess fork) and the
end-to-end `safe_run()` orchestrator with a few light invocations.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from safe_run import (
    SAFE_ENV_ALLOWLIST,
    UnsafeArgvError,
    _build_safe_env,
    _validate_argv,
    safe_run,
)


# --- _validate_argv (pure-CPU) ---

def test_validate_accepts_simple_command():
    _validate_argv(["ls", "-la", "."])


def test_validate_accepts_npm_create():
    _validate_argv(["npm", "create", "astro@latest", "--yes"])


def test_validate_accepts_path_args():
    _validate_argv(["python3", "scripts/foo.py", "--out=apps/web"])


def test_validate_rejects_empty():
    with pytest.raises(UnsafeArgvError):
        _validate_argv([])


def test_validate_rejects_shell_metachar():
    for bad in (";", "|", "&", ">", "<", "$", "`", "\\", "*", "?", '"', "'", "\n"):
        with pytest.raises(UnsafeArgvError):
            _validate_argv(["ls", f"foo{bad}bar"])


def test_validate_rejects_space():
    with pytest.raises(UnsafeArgvError):
        _validate_argv(["ls", "foo bar"])


def test_validate_rejects_non_string():
    with pytest.raises(UnsafeArgvError):
        _validate_argv(["ls", 42])  # type: ignore[list-item]


def test_validate_rejects_null_byte():
    with pytest.raises(UnsafeArgvError):
        _validate_argv(["ls", "foo\x00bar"])


# --- _build_safe_env ---

def test_build_safe_env_forces_lc_ctype():
    env = _build_safe_env()
    assert env["LC_CTYPE"] == "C.UTF-8"


def test_build_safe_env_drops_unknown_vars(monkeypatch):
    monkeypatch.setenv("NPM_CONFIG_REGISTRY", "http://evil.example/")
    monkeypatch.setenv("LD_PRELOAD", "/tmp/evil.so")
    monkeypatch.setenv("PYTHONPATH", "/tmp/evil")
    env = _build_safe_env()
    assert "NPM_CONFIG_REGISTRY" not in env
    assert "LD_PRELOAD" not in env
    assert "PYTHONPATH" not in env


def test_build_safe_env_passes_allowed_vars(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/local/bin:/usr/bin")
    monkeypatch.setenv("HOME", "/home/test")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    env = _build_safe_env()
    assert env["PATH"] == "/usr/local/bin:/usr/bin"
    assert env["HOME"] == "/home/test"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_safe_env_allowlist_is_frozenset():
    assert isinstance(SAFE_ENV_ALLOWLIST, frozenset)


def test_safe_env_allowlist_has_no_dangerous_vars():
    for bad in ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
                "PYTHONPATH", "NODE_OPTIONS", "RUBYOPT", "PERL5OPT",
                "GIT_SSH_COMMAND", "GIT_DIR"):
        assert bad not in SAFE_ENV_ALLOWLIST


# --- safe_run end-to-end ---

def test_safe_run_succeeds(tmp_path: Path):
    """Invoke /bin/echo via safe_run; verify stdout capture + exit 0."""
    res = safe_run(["echo", "hello"], cwd=tmp_path)
    assert res.returncode == 0
    assert res.stdout == b"hello\n"


def test_safe_run_unsafe_argv_rejected(tmp_path: Path):
    """argv with shell metacharacters fails BEFORE subprocess fork."""
    with pytest.raises(UnsafeArgvError):
        safe_run(["echo", "hello; rm -rf /"], cwd=tmp_path)


def test_safe_run_nonzero_exit_raises(tmp_path: Path):
    """check=True is enforced — nonzero exit raises CalledProcessError."""
    import subprocess
    with pytest.raises(subprocess.CalledProcessError):
        safe_run(["false"], cwd=tmp_path)
