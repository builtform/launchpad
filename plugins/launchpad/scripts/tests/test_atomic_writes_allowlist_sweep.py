"""Phase 11 v3.1 -- atomic_write_replace caller-allowlist AST sweep (DA4).

Runtime equivalent of the Phase 8.5 ALLOWLIST-based handshake-lint at
`plugin-v2-handshake-lint.py:1336-1410`. The lint enforces at commit
time; this test enforces at pytest time so a CI run that bypasses
lefthook (e.g., `--no-verify` re-run after a server-side rule change)
still catches violations.

Asserts three properties:

  1. Each allowlisted caller actually imports + invokes
     `atomic_write_replace`. No silent-allowlist drift (plan section 3.4
     property #1).
  2. The allowlist matches the lint constant byte-for-byte. Drift between
     lint and runtime would mask one or the other.
  3. AST sweep over `plugins/launchpad/scripts/**/*.py` finds zero
     unallowlisted callers (plan section 3.4 property #3).

Vendor exclusions per DA12: `**/_vendor/**` (catches both
`scripts/_vendor/` and `scripts/plugin_stack_adapters/_vendor/`) +
`**/tests/**`.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest


_SCRIPTS = Path(__file__).resolve().parent.parent
REPO_ROOT = _SCRIPTS.parent.parent.parent
LINT_PATH = _SCRIPTS / "plugin-v2-handshake-lint.py"


def _load_lint_constants() -> dict:
    """Load the lint module by file path so we can read its public constants
    without importing as a Python module (the file uses dashes in its name)."""
    spec = importlib.util.spec_from_file_location("plugin_v2_handshake_lint", LINT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        "ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS": tuple(
            module.ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS
        ),
        "ATOMIC_WRITE_REPLACE_NAMES": tuple(module.ATOMIC_WRITE_REPLACE_NAMES),
    }


def _scan_for_atomic_write_replace_callers(
    py_path: Path, allowed_names: tuple[str, ...]
) -> list[tuple[int, str]]:
    """Return [(line, callsite_repr), ...] for every `atomic_write_replace`
    call in `py_path`, including aliased imports per the lint's import-
    binding resolution."""
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    bound_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").endswith("atomic_io"):
                for alias in node.names:
                    if alias.name in allowed_names:
                        bound_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "atomic_io":
                    bound_names.add(alias.asname or alias.name)

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in bound_names:
                hits.append((node.lineno, f"{func.id}(...)"))
            elif (
                isinstance(func, ast.Attribute)
                and func.attr in allowed_names
                and isinstance(func.value, ast.Name)
                and func.value.id in bound_names
            ):
                hits.append(
                    (node.lineno, f"{func.value.id}.{func.attr}(...)")
                )
    return hits


# ---------------------------------------------------------------------------
# Property 1 -- allowlisted callers actually invoke atomic_write_replace
# ---------------------------------------------------------------------------


def test_each_allowlisted_caller_invokes_atomic_write_replace() -> None:
    """No silent-allowlist drift: every entry in
    ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS must contain at least one
    invocation of atomic_write_replace (or an aliased binding)."""
    constants = _load_lint_constants()
    allowed_callers = constants["ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS"]
    allowed_names = constants["ATOMIC_WRITE_REPLACE_NAMES"]

    drift: list[str] = []
    for rel in allowed_callers:
        path = REPO_ROOT / rel
        assert path.exists(), f"allowlisted caller missing: {rel}"

        # The atomic_io module is the source; it defines + re-exports the
        # symbol so it is permitted to use it without a separate import.
        if rel.endswith("atomic_io.py"):
            source = path.read_text(encoding="utf-8")
            assert "def atomic_write_replace" in source, (
                f"atomic_io.py must define atomic_write_replace; got source "
                f"first 200 chars: {source[:200]!r}"
            )
            continue

        hits = _scan_for_atomic_write_replace_callers(path, allowed_names)
        if not hits:
            drift.append(rel)

    assert not drift, (
        "allowlist drift: caller(s) listed in "
        "ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS but no longer invoke "
        f"atomic_write_replace: {drift!r}. Either restore the call OR "
        "remove the allowlist entry (with CODEOWNERS review)."
    )


# ---------------------------------------------------------------------------
# Property 2 -- runtime allowlist matches the lint constant byte-for-byte
# ---------------------------------------------------------------------------


def test_allowlist_constant_byte_for_byte_match() -> None:
    """Reading the lint constant via importlib must give the same tuple
    that the lint expects. Drift between this test's view and the lint's
    view would mask either side."""
    constants = _load_lint_constants()
    allowed = constants["ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS"]

    # The current expected set per Phase 10 Slice D + Phase 8.5,
    # narrowed at Phase 11 hardening A4 (lp_bootstrap/sentinel.py
    # harmonized to O_CREAT|O_EXCL and dropped its atomic_write_replace
    # dependency, mirroring the other two sentinels). Order matches the
    # source listing.
    #
    # v2.1 Codex PR #50 cycle 6 F9: `lp_bootstrap/engine.py` REMOVED after
    # `_record_version_drift` was refactored to route through
    # `re_seal_decision_atomic` in `lp_pick_stack.decision_writer`. The
    # decision_writer entry (already in the list) covers the resealed
    # scaffold-decision write; engine.py no longer holds the primitive.
    #
    # v2.1.8 BL-370 / BL-371 / BL-372: three new entries cover the
    # autonomy-polish lane (preflight-config proposer, preflight receipt
    # writer, Claude Code settings merger). All three are
    # bootstrap-tier writers covered by the `/lp_bootstrap/` CODEOWNERS
    # rule (the lp_preflight.py addition is module-local rather than
    # under lp_bootstrap/ but still requires the same review gate via
    # the line-level entry below).
    expected = (
        "plugins/launchpad/scripts/atomic_io.py",
        "plugins/launchpad/scripts/plugin_default_generators/_renderer_base.py",
        "plugins/launchpad/scripts/lp_bootstrap/policy.py",
        "plugins/launchpad/scripts/lp_bootstrap/manifest_writer.py",
        "plugins/launchpad/scripts/lp_bootstrap/preflight_proposer.py",
        "plugins/launchpad/scripts/lp_preflight.py",
        "plugins/launchpad/scripts/lp_bootstrap/claude_settings_merger.py",
        "plugins/launchpad/scripts/lp_pick_stack/decision_writer.py",
        # v2.1 Codex PR #50 Slice E: pre-squash audit-log filter.
        "plugins/launchpad/scripts/plugin-restamp-redact-wip.py",
    )
    assert allowed == expected, (
        f"ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS drifted from expected:\n"
        f"  expected: {expected!r}\n  got:      {allowed!r}\n"
        "If the allowlist legitimately grew/shrunk, update this test "
        "AND the Phase 11 plan section 3.4 inventory in the same PR."
    )


# ---------------------------------------------------------------------------
# Property 3 -- AST sweep finds zero unallowlisted callers
# ---------------------------------------------------------------------------


_EXCLUDE_GLOBS = (
    "**/_vendor/**",
    "**/tests/**",
    "**/__pycache__/**",
)


def _excluded(rel_posix: str) -> bool:
    """Mirror the lint's exclusion logic (DA12 vendor + tests)."""
    return (
        "/_vendor/" in rel_posix
        or "/__pycache__/" in rel_posix
        or "/tests/" in rel_posix
        or rel_posix.endswith("_test.py")
        or rel_posix.startswith("plugins/launchpad/scripts/tests/")
    )


def test_no_unallowlisted_atomic_write_replace_callers() -> None:
    """Sweep `plugins/launchpad/scripts/**/*.py` and assert no module
    outside the allowlist invokes atomic_write_replace. Mirrors the
    Phase 8.5 lint at runtime so CI re-runs that bypass lefthook still
    surface drift."""
    constants = _load_lint_constants()
    allowed_callers = set(constants["ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS"])
    allowed_names = constants["ATOMIC_WRITE_REPLACE_NAMES"]

    scan_root = REPO_ROOT / "plugins" / "launchpad" / "scripts"
    py_files = list(scan_root.rglob("*.py"))
    # Sanity: at least one vendor file should be present so the exclusion
    # actually kicks in (DA12 v3 verification).
    vendor_dirs = list(scan_root.rglob("_vendor"))
    assert vendor_dirs, (
        "expected at least one _vendor/ directory under scripts/; the "
        "exclusion glob would be a no-op without one. DA12 verification."
    )

    violations: list[str] = []
    for py_path in py_files:
        rel = py_path.relative_to(REPO_ROOT).as_posix()
        if rel in allowed_callers:
            continue
        if _excluded(rel):
            continue
        hits = _scan_for_atomic_write_replace_callers(py_path, allowed_names)
        for line_no, callsite in hits:
            violations.append(f"{rel}:{line_no}: {callsite}")

    assert not violations, (
        "Unallowlisted atomic_write_replace caller(s) found. Add to "
        "ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS via CODEOWNERS-reviewed "
        "PR, or remove the call. Violations:\n  "
        + "\n  ".join(sorted(violations))
    )
