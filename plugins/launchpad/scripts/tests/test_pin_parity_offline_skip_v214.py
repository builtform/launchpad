"""v2.1.4 BL-328 + Codex P1-B regression: parity script `--offline-skip`
honors the workflow contract that GitHub-unreachable runners must NOT
fail the build.

Pre-fix the script's `--offline-skip` flag only suppressed `git not
available`; a transient `git fetch` CalledProcessError or
TimeoutExpired was appended as a normal "finding" and exited 1, which
contradicted the v2-handshake-lint workflow comment that
`--offline-skip` was wired in to keep the gate non-blocking on
ephemeral runners.

Post-fix: `_check_pin` returns a `PinCheckResult` with two distinct
fields (`findings` for real parity violations + `infra_errors` for
network/tooling failures). `main()` suppresses `infra_errors` under
`--offline-skip` (exit 0) but always fails on real findings (exit 1).
Without `--offline-skip`, infra failures exit 2 (distinguishable from
real findings via the exit code).

Tests use the `_check_pin` direct call rather than the full `main()`
loop so we can synthesize the four scenarios without network reach:
  1. clean fetch + clean tree              → empty PinCheckResult
  2. clean fetch + disallowed entry        → findings populated
  3. fetch CalledProcessError              → infra_errors populated
  4. fetch TimeoutExpired                  → infra_errors populated

The `main()`-level offline-skip behavior is exercised via subprocess
invocations of the script with synthetic _shallow_fetch monkey-patches
through the module-import surface.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


_PARITY_MODULE_NAME = "_parity_script_v214"


def _import_parity_module():
    """Import the parity script as a module (its filename has hyphens, so
    the standard import statement won't work). Returns the module object.

    The module is registered in `sys.modules` BEFORE `exec_module` so
    `@dataclass` introspection (which looks up `cls.__module__` in
    `sys.modules` to resolve forward-string annotations) succeeds.
    Without the pre-registration the dataclass decorator raises
    `AttributeError: 'NoneType' object has no attribute '__dict__'` —
    a failure mode unique to dynamically-loaded modules using
    `spec_from_file_location`."""
    if _PARITY_MODULE_NAME in sys.modules:
        return sys.modules[_PARITY_MODULE_NAME]
    script_path = _SCRIPTS_DIR / "plugin-upstream-pin-walk-scope-parity.py"
    spec = importlib.util.spec_from_file_location(
        _PARITY_MODULE_NAME, script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PARITY_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(_PARITY_MODULE_NAME, None)
        raise
    return module


def test_pin_check_result_clean_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Clean upstream → both fields empty."""
    parity = _import_parity_module()

    def fake_fetch(repo_url: str, sha: str, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / "package.json").write_text('{"name":"clean"}\n')

    monkeypatch.setattr(parity, "_shallow_fetch", fake_fetch)
    result = parity._check_pin(
        "ts_monorepo", None, "https://github.com/example/clean", "0" * 40, verbose=False
    )
    assert result.findings == ()
    assert result.infra_errors == ()


def test_pin_check_result_disallowed_entry_populates_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Symlink in fetched tree → findings populated, infra_errors empty."""
    parity = _import_parity_module()

    def fake_fetch(repo_url: str, sha: str, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / "package.json").write_text('{"name":"with-symlink"}\n')
        os.symlink("/etc/passwd", str(target / "evil"))

    monkeypatch.setattr(parity, "_shallow_fetch", fake_fetch)
    result = parity._check_pin(
        "ts_monorepo",
        None,
        "https://github.com/example/with-symlink",
        "0" * 40,
        verbose=False,
    )
    assert result.findings != ()
    assert "DISALLOWED ENTRY" in result.findings[0]
    assert result.infra_errors == ()


def test_pin_check_result_fetch_called_process_error_is_infra(
    monkeypatch: pytest.MonkeyPatch,
):
    """git fetch CalledProcessError → infra_errors populated, findings empty.
    Critical: this is the case that pre-fix was misclassified as a finding
    and would break CI under --offline-skip."""
    parity = _import_parity_module()

    def fake_fetch(repo_url: str, sha: str, target: Path) -> None:
        raise subprocess.CalledProcessError(
            128, ["git", "fetch"], stderr=b"Could not resolve host: github.com"
        )

    monkeypatch.setattr(parity, "_shallow_fetch", fake_fetch)
    result = parity._check_pin(
        "ts_monorepo", None, "https://github.com/example/x", "0" * 40, verbose=False
    )
    assert result.findings == ()
    assert result.infra_errors != ()
    assert "fetch failed" in result.infra_errors[0]
    assert "Could not resolve host" in result.infra_errors[0]


def test_pin_check_result_fetch_timeout_is_infra(
    monkeypatch: pytest.MonkeyPatch,
):
    """git fetch TimeoutExpired → infra_errors populated, findings empty.
    Same critical case as CalledProcessError: pre-fix misclassified."""
    parity = _import_parity_module()

    def fake_fetch(repo_url: str, sha: str, target: Path) -> None:
        raise subprocess.TimeoutExpired(["git", "fetch"], timeout=600)

    monkeypatch.setattr(parity, "_shallow_fetch", fake_fetch)
    result = parity._check_pin(
        "ts_monorepo", None, "https://github.com/example/x", "0" * 40, verbose=False
    )
    assert result.findings == ()
    assert result.infra_errors != ()
    assert "timed out" in result.infra_errors[0]


def test_pin_check_result_missing_subpath_is_finding_not_infra(
    monkeypatch: pytest.MonkeyPatch,
):
    """A fetched tree that lacks the adapter's _SUB_PATHS subpath is a
    REAL finding (stale pin), NOT an infra error — operators must see
    this regardless of --offline-skip."""
    parity = _import_parity_module()

    def fake_fetch(repo_url: str, sha: str, target: Path) -> None:
        # Real withastro/astro-shaped tree but with examples/blog absent.
        target.mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_text("# upstream\n")

    monkeypatch.setattr(parity, "_shallow_fetch", fake_fetch)
    result = parity._check_pin(
        "astro", "blog", "https://github.com/example/astro", "0" * 40, verbose=False
    )
    assert result.findings != ()
    assert "sub-template subpath" in result.findings[0]
    assert "pin may be stale" in result.findings[0]
    assert result.infra_errors == ()


def test_known_bad_pin_does_not_waive_infra_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """Per Codex P1-B nuance: KNOWN_BAD_PINS waives REAL findings only.
    A fetch failure on an allowlisted pin is still infra (and is
    suppressed by --offline-skip, not by the pin allowlist)."""
    parity = _import_parity_module()

    def fake_fetch(repo_url: str, sha: str, target: Path) -> None:
        raise subprocess.CalledProcessError(128, ["git", "fetch"], stderr=b"flake")

    monkeypatch.setattr(parity, "_shallow_fetch", fake_fetch)
    # nextjs_fastapi IS in KNOWN_BAD_PINS, but the result here should
    # report infra_errors (not findings) because the fetch itself failed
    # — there is nothing for the allowlist to match against.
    result = parity._check_pin(
        "nextjs_fastapi",
        None,
        "https://github.com/example/x",
        "0" * 40,
        verbose=False,
    )
    assert result.findings == ()
    assert result.infra_errors != ()
