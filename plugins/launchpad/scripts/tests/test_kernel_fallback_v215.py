"""BL-341 v2.1.5 round-3 review fix (A7): regression tests for
`_kernel_fallback_render` in `lp_define_runner.py`.

The fallback exists so a brownfield project that ran `/lp-define` without
first running `/lp-scaffold-stack` still has the 7 kernel files (LICENSE,
SECURITY.md, etc.) rendered. The round-3 review surfaced FIVE distinct
branches with zero coverage:

  1. no scaffold-decision.json → no-op
  2. all kernel files already present → no-op (no overwrite)
  3. one kernel file missing + valid identity → renders ONLY that file
     (A1 only_paths fix — must NOT clobber user-edited files)
  4. malformed scaffold-decision.json → warns + returns
  5. render failure → warns + returns

Plus the load-bearing regression test:

  - existing edited README.md is NOT overwritten when LICENSE is missing.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _runner():
    """Fresh import each test to avoid module-cache contamination."""
    if "lp_define_runner" in sys.modules:
        return importlib.reload(sys.modules["lp_define_runner"])
    return importlib.import_module("lp_define_runner")


_VALID_IDENTITY: dict[str, Any] = {
    "project_name": "test-proj",
    "email": "security@example.com",
    "repo_url": "https://github.com/test-org/test-proj",
    "license": "MIT",
    "copyright_holder": "Test Holder",
}


def _write_decision(repo_root: Path, identity: Any) -> None:
    launchpad = repo_root / ".launchpad"
    launchpad.mkdir(parents=True, exist_ok=True)
    decision_path = launchpad / "scaffold-decision.json"
    payload = {"identity": identity} if identity is not None else {}
    decision_path.write_text(json.dumps(payload), encoding="utf-8")


def test_no_scaffold_decision_is_noop(tmp_path: Path) -> None:
    """Without `.launchpad/scaffold-decision.json` the fallback must not
    touch the filesystem (brownfield project that never ran lp-scaffold).
    """
    mod = _runner()
    mod._kernel_fallback_render(tmp_path)
    # No files created.
    assert not (tmp_path / "LICENSE").exists()
    assert not (tmp_path / ".launchpad").exists()


def test_all_kernel_files_present_is_noop(tmp_path: Path, capsys) -> None:
    """When every kernel file is already on disk the fallback must
    no-op silently — nothing is missing, nothing to render."""
    mod = _runner()
    from plugin_default_generators.kernel_renderer import KERNEL_FILES

    _write_decision(tmp_path, _VALID_IDENTITY)
    for _template, output_relpath in KERNEL_FILES:
        target = tmp_path / output_relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("user-content", encoding="utf-8")

    mod._kernel_fallback_render(tmp_path)

    # User content must be untouched.
    for _template, output_relpath in KERNEL_FILES:
        assert (tmp_path / output_relpath).read_text(encoding="utf-8") == "user-content"

    captured = capsys.readouterr()
    assert "BL-341 kernel-fallback" not in captured.err


def test_malformed_scaffold_decision_warns_and_returns(tmp_path: Path, capsys) -> None:
    """Unparseable JSON triggers a single collapsed warning (C6 fix:
    the unparseable-JSON and missing-identity branches now share one
    message)."""
    mod = _runner()
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    (launchpad / "scaffold-decision.json").write_text("not json", encoding="utf-8")

    # Need at least one kernel file missing to reach the JSON read.
    # (otherwise the early-return on `all present` short-circuits)
    # Most kernel files are absent in a fresh tmp_path so the check fires.
    mod._kernel_fallback_render(tmp_path)

    err = capsys.readouterr().err
    assert "BL-341 kernel-fallback skipped" in err
    assert "scaffold-decision.json malformed" in err
    # No kernel files written.
    assert not (tmp_path / "LICENSE").exists()


def test_missing_identity_block_warns_and_returns(tmp_path: Path, capsys) -> None:
    """Parseable JSON without an `identity` block emits the same
    collapsed warning."""
    mod = _runner()
    _write_decision(tmp_path, identity=None)  # empty payload

    mod._kernel_fallback_render(tmp_path)

    err = capsys.readouterr().err
    assert "BL-341 kernel-fallback skipped" in err
    assert "scaffold-decision.json malformed" in err
    assert not (tmp_path / "LICENSE").exists()


def test_missing_project_name_warns_and_returns(tmp_path: Path, capsys) -> None:
    """An identity block lacking the load-bearing `project_name` field is
    treated as malformed (same collapsed warning)."""
    mod = _runner()
    _write_decision(tmp_path, identity={"license": "MIT"})

    mod._kernel_fallback_render(tmp_path)

    err = capsys.readouterr().err
    assert "BL-341 kernel-fallback skipped" in err
    assert not (tmp_path / "LICENSE").exists()


def test_only_missing_files_are_rendered(tmp_path: Path) -> None:
    """A1 regression: render must scope to `only_paths=missing`. If user
    has edited README.md but LICENSE is absent, ONLY LICENSE gets written;
    README.md retains user content."""
    mod = _runner()
    from plugin_default_generators.kernel_renderer import KERNEL_FILES

    _write_decision(tmp_path, _VALID_IDENTITY)

    # Pre-populate every kernel file EXCEPT LICENSE with user content.
    user_marker = "USER-EDITED-DO-NOT-OVERWRITE"
    for _template, output_relpath in KERNEL_FILES:
        if output_relpath == "LICENSE":
            continue
        target = tmp_path / output_relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(user_marker, encoding="utf-8")

    mod._kernel_fallback_render(tmp_path)

    # LICENSE must now exist (it was missing before).
    assert (tmp_path / "LICENSE").is_file()
    license_text = (tmp_path / "LICENSE").read_text(encoding="utf-8")
    assert user_marker not in license_text  # not from the user
    assert (
        _VALID_IDENTITY["project_name"] in license_text or "MIT" in license_text.upper()
    )

    # Every other kernel file must still carry the user's content.
    for _template, output_relpath in KERNEL_FILES:
        if output_relpath == "LICENSE":
            continue
        on_disk = (tmp_path / output_relpath).read_text(encoding="utf-8")
        assert on_disk == user_marker, (
            f"BL-341 A1 regression: {output_relpath} was overwritten "
            f"even though it was already present on disk."
        )


def test_render_exception_is_caught_and_logged(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """A generic render failure must NOT crash /lp-define; the warning
    is logged and execution continues."""
    mod = _runner()
    _write_decision(tmp_path, _VALID_IDENTITY)

    # Force KernelRenderer.render_all to raise an unexpected error.
    from plugin_default_generators import kernel_renderer

    def boom(self, cwd, identity, only_paths=None):  # type: ignore[no-untyped-def]
        raise RuntimeError("synthetic-render-failure")

    monkeypatch.setattr(kernel_renderer.KernelRenderer, "render_all", boom)
    mod._kernel_fallback_render(tmp_path)

    err = capsys.readouterr().err
    assert "BL-341 kernel-fallback render failed" in err
    assert "synthetic-render-failure" in err


def test_secret_scanner_violation_is_not_swallowed(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """A6 regression + v2.1.5 round-5 Codex P1-A: a SecretScannerViolation
    during fallback render must surface as an `error:` message AND
    return `HARD_FAIL_SCANNER` so /lp-define's main pipeline halts."""
    mod = _runner()
    _write_decision(tmp_path, _VALID_IDENTITY)

    from plugin_default_generators import _renderer_base, kernel_renderer

    def boom(self, cwd, identity, only_paths=None):  # type: ignore[no-untyped-def]
        raise _renderer_base.SecretScannerViolation(
            findings=[],
            refused_count=2,
            message="synthetic-scanner-violation",
        )

    monkeypatch.setattr(kernel_renderer.KernelRenderer, "render_all", boom)
    status = mod._kernel_fallback_render(tmp_path)

    err = capsys.readouterr().err
    assert "BL-341 kernel-fallback REFUSED" in err
    assert "secret scanner" in err
    assert "2 match" in err
    # Round-5 fix: hard-fail status surfaces to caller.
    assert status == mod.KernelFallbackStatus.HARD_FAIL_SCANNER


def test_os_error_is_surfaced_not_swallowed(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """A6 regression + v2.1.5 round-5 Codex P1-A: OSError during
    atomic-write means partial disk state — surface as `error:` AND
    return `HARD_FAIL_DISK` so /lp-define's main pipeline halts."""
    mod = _runner()
    _write_decision(tmp_path, _VALID_IDENTITY)

    from plugin_default_generators import kernel_renderer

    def boom(self, cwd, identity, only_paths=None):  # type: ignore[no-untyped-def]
        raise OSError("synthetic-disk-full")

    monkeypatch.setattr(kernel_renderer.KernelRenderer, "render_all", boom)
    status = mod._kernel_fallback_render(tmp_path)

    err = capsys.readouterr().err
    assert "BL-341 kernel-fallback aborted" in err
    assert "synthetic-disk-full" in err
    # Round-5 fix: hard-fail status surfaces to caller.
    assert status == mod.KernelFallbackStatus.HARD_FAIL_DISK


def test_generate_halts_on_hard_fail_scanner(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """v2.1.5 round-5 Codex P1-A integration test: when the fallback
    returns HARD_FAIL_SCANNER, `generate()` MUST exit non-zero before
    writing any `docs/architecture/*` files.

    The Codex P1-A finding: prior shape returned None from the fallback
    and let /lp-define continue against a hostile identity value. The
    fix makes hard-fail status halt the caller."""
    mod = _runner()
    _write_decision(tmp_path, _VALID_IDENTITY)

    from plugin_default_generators import _renderer_base, kernel_renderer

    def boom(self, cwd, identity, only_paths=None):  # type: ignore[no-untyped-def]
        raise _renderer_base.SecretScannerViolation(
            findings=[],
            refused_count=1,
            message="synthetic",
        )

    monkeypatch.setattr(kernel_renderer.KernelRenderer, "render_all", boom)
    exit_code = mod.generate(tmp_path, emit_trust_banner=False)

    err = capsys.readouterr().err
    assert exit_code == 1, "generate() must return non-zero on HARD_FAIL_SCANNER"
    assert "/lp-define halted" in err
    assert "hard_fail_scanner" in err
    # NO docs/architecture/* files written.
    assert not (tmp_path / "docs" / "architecture" / "PRD.md").exists()


def test_generate_halts_on_hard_fail_disk(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """v2.1.5 round-5 Codex P1-A integration test: HARD_FAIL_DISK
    (atomic-write OSError mid-batch → partial disk state) must halt
    /lp-define so the user inspects before writing more files on top."""
    mod = _runner()
    _write_decision(tmp_path, _VALID_IDENTITY)

    from plugin_default_generators import kernel_renderer

    def boom(self, cwd, identity, only_paths=None):  # type: ignore[no-untyped-def]
        raise OSError("synthetic-disk-full")

    monkeypatch.setattr(kernel_renderer.KernelRenderer, "render_all", boom)
    exit_code = mod.generate(tmp_path, emit_trust_banner=False)

    err = capsys.readouterr().err
    assert exit_code == 1, "generate() must return non-zero on HARD_FAIL_DISK"
    assert "/lp-define halted" in err
    assert "hard_fail_disk" in err
    assert not (tmp_path / "docs" / "architecture" / "PRD.md").exists()


def test_generate_continues_on_soft_fail(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """v2.1.5 round-5 Codex P1-A: SOFT_FAIL (generic render error, OR
    malformed scaffold-decision.json) must NOT halt /lp-define — the
    user's canonical recovery is /lp-scaffold-stack, but the main
    pipeline can safely run with the prior shape (placeholder docs)."""
    mod = _runner()
    # No scaffold-decision.json present → fallback returns OK_NOOP, not
    # SOFT_FAIL. To exercise SOFT_FAIL, plant a malformed decision.
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    (launchpad / "scaffold-decision.json").write_text("not-json")

    # generate() should NOT exit non-zero just because the fallback
    # warned. It may still fail downstream for other reasons (no
    # adapter detected, etc.), but the fallback's soft-fail should not
    # be the cause. Check the err message rather than the exit code.
    try:
        mod.generate(tmp_path, emit_trust_banner=False)
    except Exception:
        # downstream failures are fine for this test's purpose
        pass

    err = capsys.readouterr().err
    # SOFT_FAIL warning should appear, but the halt message should NOT.
    assert "scaffold-decision.json malformed" in err
    assert "/lp-define halted" not in err


# ---------------------------------------------------------------------------
# v2.1.5 round-4 fix testing-P2-2: C6 OSError-on-read_text branch coverage
# ---------------------------------------------------------------------------


import sys as _sys  # noqa: E402  (sys already imported at top; re-import for clarity)
import pytest  # noqa: E402


@pytest.mark.skipif(
    _sys.platform == "win32",
    reason="chmod 0o000 does not reliably block reads on Windows NTFS",
)
def test_unreadable_scaffold_decision_warns_and_returns(
    tmp_path: Path, capsys
) -> None:
    """C6 regression: the collapsed-warning catch tuple
    `(OSError, JSONDecodeError, ValueError)` must also fire for an
    unreadable scaffold-decision.json (permission denied).

    Prior tests covered JSONDecodeError (malformed JSON) and ValueError
    (missing identity / project_name) but NOT OSError from `read_text`.
    That branch is reachable in real-world permission errors during
    repo recovery."""
    mod = _runner()
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    decision = launchpad / "scaffold-decision.json"
    import json as _json

    decision.write_text(
        _json.dumps({"identity": _VALID_IDENTITY}), encoding="utf-8"
    )
    # Make read_text raise PermissionError (an OSError subclass).
    decision.chmod(0o000)
    try:
        mod._kernel_fallback_render(tmp_path)
    finally:
        # Restore mode so pytest's tmp cleanup works.
        decision.chmod(0o600)

    err = capsys.readouterr().err
    assert "BL-341 kernel-fallback skipped" in err
    assert "scaffold-decision.json malformed" in err
    # No kernel files written.
    assert not (tmp_path / "LICENSE").exists()
