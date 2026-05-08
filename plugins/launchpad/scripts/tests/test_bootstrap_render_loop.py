"""Render-loop tests for the v2.1.0 secret-scanner gate (PR #50 follow-up).

Pins the §3.2 three-phase contract:
    Phase A — render-collect (no writes, refresh-mode included)
    Phase B — secret-scan gate (refuse-all on finding; fail-closed on infra)
    Phase C — policy-dispatch (only place writes happen)

Each test calls `_render_loop` directly with a small, focused target subset
so the assertions are tight; the fast-path / refresh-mode / IOError cases
exercise the gate's invariants without paying the cost of the full 31-target
INFRASTRUCTURE_FILES batch.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from plugin_default_generators._renderer_base import sha256_bytes  # noqa: E402

from lp_bootstrap import (  # noqa: E402
    BootstrapErrorCode,
    BootstrapPolicy,
)
from lp_bootstrap.engine import (  # noqa: E402
    _RENDERER,
    BootstrapEngineError,
    _render_loop,
)
from lp_bootstrap.manifest_writer import (  # noqa: E402
    BootstrapManifest,
    BootstrapManifestEntry,
    source_template_shas,
)


# Three targets covering the active policy types (overwrite-if-unchanged,
# append-only, merge-keys) so Phase C's dispatch branches are exercised on
# the happy path. Modes mirror INFRASTRUCTURE_FILES.
_T_GITIGNORE = (
    "gitignore.j2", ".gitignore", BootstrapPolicy.APPEND_ONLY, 0o644,
)
_T_LIB = (
    "scripts/compound/lib.sh.j2", "scripts/compound/lib.sh",
    BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644,
)
_T_GREPTILE = (
    "greptile.json.j2", ".greptile.json",
    BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644,
)

_TARGETS_3 = (_T_GITIGNORE, _T_LIB, _T_GREPTILE)


def _identity():
    return {
        "pii_opt_in": True,
        "project_name": "demo",
        "email": "demo@example.com",
        "copyright_holder": "@demo",
        "repo_url": "https://github.com/demo/demo",
        "license": "MIT",
        "license_other_body": "",
    }


# Synthetic finding shape with the optional `source` attribute that
# `_render_loop` consults via `getattr(..., "source", None)`.
@dataclass
class _StubMatch:
    line_no: int
    preview: str
    source: str | None = None


# ---------------------------------------------------------------------------
# §3.4 #1 — happy path: zero findings, all 3 targets written
# ---------------------------------------------------------------------------
def test_render_loop_happy_path_no_findings(tmp_path):
    records = _render_loop(
        tmp_path,
        identity=_identity(),
        targets=_TARGETS_3,
        existing_manifest=None,
        mode="greenfield",
        backup_dir=None,
    )
    assert len(records) == 3
    for _tpl, target_relpath, _policy, _mode in _TARGETS_3:
        assert (tmp_path / target_relpath).is_file(), (
            f"{target_relpath} not written on happy path"
        )


# ---------------------------------------------------------------------------
# §3.4 #2 — refuse-all on finding: 0 files written, structured error raised
# ---------------------------------------------------------------------------
def test_render_loop_refuse_all_on_finding(tmp_path, monkeypatch):
    finding = _StubMatch(
        line_no=1,
        preview="<REDACTED>",
        source=str(tmp_path / "scripts" / "compound" / "lib.sh"),
    )

    def _fake_scan_batch(self, batch, **_kwargs):
        return [finding]

    monkeypatch.setattr(
        type(_RENDERER), "scan_batch", _fake_scan_batch, raising=True,
    )

    with pytest.raises(BootstrapEngineError) as excinfo:
        _render_loop(
            tmp_path,
            identity=_identity(),
            targets=_TARGETS_3,
            existing_manifest=None,
            mode="greenfield",
            backup_dir=None,
        )

    assert excinfo.value.reason == BootstrapErrorCode.SECRET_SCANNER_VIOLATION
    msg = str(excinfo.value)
    assert "1 match" in msg
    # Refused-all-writes count tracks the full batch size.
    assert "refused all 3 writes" in msg
    # Zero writes happened: none of the 3 targets exist on disk.
    for _tpl, target_relpath, _policy, _mode in _TARGETS_3:
        assert not (tmp_path / target_relpath).exists(), (
            f"{target_relpath} written despite scan-batch refuse-all"
        )


# ---------------------------------------------------------------------------
# §3.4 #3 — fast-path still renders for scan (defends against future
# "skip render entirely on fast-path" optimization)
# ---------------------------------------------------------------------------
def test_render_loop_fast_path_still_renders_for_scan(tmp_path, monkeypatch):
    """Pre-stage 3 targets so `manifest_sha == on_disk_sha == rendered_sha`
    for all of them (fast-path eligible). Monkey-patch `scan_batch` to
    inject a finding for one. Assert: Phase A renders all 3 (i.e. no
    `_RENDERER.render_target` short-circuit), Phase B fires, Phase C never
    executes (zero writes, zero records returned).
    """
    # Pre-render + pre-stage to make the fast-path eligible.
    rendered_byte_map: dict[str, bytes] = {}
    entries: list[BootstrapManifestEntry] = []
    template_shas = source_template_shas()
    for _tpl, target_relpath, policy, file_mode in _TARGETS_3:
        rendered = _RENDERER.render_target(target_relpath, _identity())
        rendered_byte_map[target_relpath] = rendered
        target_path = tmp_path / target_relpath
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(rendered)
        entries.append(BootstrapManifestEntry(
            path=target_relpath,
            source_template_sha256=template_shas[target_relpath],
            rendered_content_sha256=sha256_bytes(rendered),
            policy=policy.value,
            mode=file_mode,
        ))

    existing_manifest = BootstrapManifest(
        manifest_schema_version="1.0",
        plugin_version="test",
        last_render_timestamp="",
        files=tuple(entries),
    )

    # Track render_target calls so we can assert Phase A still ran.
    real_render_target = _RENDERER.render_target
    call_count = {"n": 0}

    def _counting_render_target(target_relpath, identity):
        call_count["n"] += 1
        return real_render_target(target_relpath, identity)

    monkeypatch.setattr(_RENDERER, "render_target", _counting_render_target)

    finding = _StubMatch(
        line_no=1,
        preview="<REDACTED>",
        source=str(tmp_path / ".greptile.json"),
    )

    def _fake_scan_batch(self, batch, **_kwargs):
        # Phase B receives the rendered batch keyed by absolute target
        # paths. Confirm Phase A populated it for every target despite
        # fast-path eligibility on disk.
        assert len(batch) == 3
        return [finding]

    monkeypatch.setattr(
        type(_RENDERER), "scan_batch", _fake_scan_batch, raising=True,
    )

    with pytest.raises(BootstrapEngineError) as excinfo:
        _render_loop(
            tmp_path,
            identity=_identity(),
            targets=_TARGETS_3,
            existing_manifest=existing_manifest,
            mode="greenfield",
            backup_dir=None,
        )

    assert excinfo.value.reason == BootstrapErrorCode.SECRET_SCANNER_VIOLATION
    # Phase A rendered all 3 even though fast-path on-disk sha equality
    # would have allowed a "skip render" optimization. Pinning here.
    assert call_count["n"] == 3


# ---------------------------------------------------------------------------
# §3.4 #4 — refresh-mode refuses writes AND backups (cycle-1 SEC-P1-1)
# ---------------------------------------------------------------------------
def test_render_loop_refresh_mode_refuses_writes(tmp_path, monkeypatch):
    """Pin the cycle-1 P1: refresh-mode's `write_backup_then_overwrite`
    MUST live in Phase C, not Phase A. Otherwise refuse-all is defeated:
    a finding on a later target would still leave backup files behind.
    """
    # Pre-stage targets so refresh has something to back up.
    for _tpl, target_relpath, _policy, _mode in _TARGETS_3:
        target_path = tmp_path / target_relpath
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"# user-edited\n")

    backup_dir = tmp_path / ".launchpad" / "backups" / "20260508-12345-abcd"
    backup_dir.mkdir(parents=True)

    finding = _StubMatch(
        line_no=1,
        preview="<REDACTED>",
        source=str(tmp_path / "scripts" / "compound" / "lib.sh"),
    )

    def _fake_scan_batch(self, batch, **_kwargs):
        return [finding]

    monkeypatch.setattr(
        type(_RENDERER), "scan_batch", _fake_scan_batch, raising=True,
    )

    with pytest.raises(BootstrapEngineError) as excinfo:
        _render_loop(
            tmp_path,
            identity=_identity(),
            targets=_TARGETS_3,
            existing_manifest=None,
            mode="refresh-all",
            backup_dir=backup_dir,
        )

    assert excinfo.value.reason == BootstrapErrorCode.SECRET_SCANNER_VIOLATION
    # No backup files in the backup-dir: Phase A did not call
    # write_backup_then_overwrite.
    assert list(backup_dir.iterdir()) == [], (
        "refresh-mode wrote backup before scan-batch refused; Phase A "
        "must be render-only"
    )
    # Targets retain user-edited content (no overwrite happened).
    for _tpl, target_relpath, _policy, _mode in _TARGETS_3:
        assert (tmp_path / target_relpath).read_bytes() == b"# user-edited\n"


# ---------------------------------------------------------------------------
# §3.4 #5 — scanner IOError is fail-closed (cycle-1 SEC-P1-4)
# ---------------------------------------------------------------------------
def test_render_loop_scanner_ioerror_fail_closed(tmp_path, monkeypatch):
    """Defend against fail-open on scanner infra failure. A bare `OSError`
    leaking past the gate would let policy-dispatch run unscanned.
    """
    def _fake_scan_batch(self, batch, **_kwargs):
        raise OSError("simulated patterns_file unreadable")

    monkeypatch.setattr(
        type(_RENDERER), "scan_batch", _fake_scan_batch, raising=True,
    )

    with pytest.raises(BootstrapEngineError) as excinfo:
        _render_loop(
            tmp_path,
            identity=_identity(),
            targets=_TARGETS_3,
            existing_manifest=None,
            mode="greenfield",
            backup_dir=None,
        )

    assert excinfo.value.reason == BootstrapErrorCode.SECRET_SCANNER_VIOLATION
    # The original OSError is preserved as __cause__ for forensic detail.
    assert isinstance(excinfo.value.__cause__, OSError)
    # Type-name surfaced in the message; the OSError args (potentially
    # secret-shaped on UnicodeDecodeError) are NOT.
    assert "OSError" in str(excinfo.value)
    # Zero writes happened.
    for _tpl, target_relpath, _policy, _mode in _TARGETS_3:
        assert not (tmp_path / target_relpath).exists()
