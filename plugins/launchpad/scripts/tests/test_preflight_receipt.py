"""Tests for the preflight receipt / memoization surface (BL-371).

Covers the receipt schema, ``check_receipt_validity`` decision matrix
(missing / corrupt / stale / config_changed / checklist_changed /
prior_failed / valid), the ``write_receipt`` lifecycle (write on pass,
remove on fail), the freshness-window override path (CLI > config >
default), and the ``--write-receipt`` / ``--read-receipt`` CLI flow.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_preflight import (  # noqa: E402
    AUDIT_LOG_PATH,
    CHECKLIST_PATH,
    CONFIG_PATH,
    DEFAULT_FRESHNESS_WINDOW_SECONDS,
    RECEIPT_PATH,
    RECEIPT_VERSION,
    ReceiptCheckResult,
    _audit_log_event,
    _freshness_window_from_config,
    _sha256_of_file,
    check_receipt_validity,
    main,
    write_receipt,
)


def _seed_config(repo_root: Path, *, providers: list[str] | None = None) -> None:
    body = "providers:\n"
    for provider in providers or ["spec-completeness"]:
        body += f"  - {provider}\n"
    (repo_root / ".launchpad").mkdir(parents=True, exist_ok=True)
    (repo_root / CONFIG_PATH).write_text(body, encoding="utf-8")


def _seed_checklist(repo_root: Path, body: str = "# checklist\n") -> None:
    (repo_root / ".launchpad").mkdir(parents=True, exist_ok=True)
    (repo_root / CHECKLIST_PATH).write_text(body, encoding="utf-8")


def _seed_receipt(repo_root: Path, **overrides: object) -> Path:
    """Write a receipt with sensible defaults; overrides win."""
    _seed_config(repo_root)
    payload: dict[str, object] = {
        "version": RECEIPT_VERSION,
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exit_code": 0,
        "config_sha256": _sha256_of_file(repo_root / CONFIG_PATH),
        "checklist_sha256": _sha256_of_file(repo_root / CHECKLIST_PATH),
        "section_path": None,
        "writer_command": "/lp-build",
        "freshness_window_seconds": DEFAULT_FRESHNESS_WINDOW_SECONDS,
    }
    payload.update(overrides)
    target = repo_root / RECEIPT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


# --- _sha256_of_file --------------------------------------------------------


def test_sha256_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert _sha256_of_file(tmp_path / "nope") is None


def test_sha256_matches_hashlib(tmp_path: Path) -> None:
    f = tmp_path / "f.txt"
    f.write_bytes(b"hello")
    assert _sha256_of_file(f) == hashlib.sha256(b"hello").hexdigest()


# --- _freshness_window_from_config ------------------------------------------


def test_freshness_window_default_when_config_missing(tmp_path: Path) -> None:
    assert _freshness_window_from_config(tmp_path) is None


def test_freshness_window_default_when_key_absent(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    assert _freshness_window_from_config(tmp_path) is None


def test_freshness_window_reads_positive_int(tmp_path: Path) -> None:
    (tmp_path / ".launchpad").mkdir(parents=True, exist_ok=True)
    (tmp_path / CONFIG_PATH).write_text(
        "freshness_window_seconds: 7200\nproviders:\n  - spec-completeness\n",
        encoding="utf-8",
    )
    assert _freshness_window_from_config(tmp_path) == 7200


def test_freshness_window_rejects_non_positive_and_bool(tmp_path: Path) -> None:
    (tmp_path / ".launchpad").mkdir(parents=True, exist_ok=True)
    (tmp_path / CONFIG_PATH).write_text(
        "freshness_window_seconds: 0\nproviders:\n  - spec-completeness\n",
        encoding="utf-8",
    )
    assert _freshness_window_from_config(tmp_path) is None
    (tmp_path / CONFIG_PATH).write_text(
        "freshness_window_seconds: true\nproviders:\n  - spec-completeness\n",
        encoding="utf-8",
    )
    assert _freshness_window_from_config(tmp_path) is None


# --- check_receipt_validity -------------------------------------------------


def test_check_receipt_missing(tmp_path: Path) -> None:
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result == ReceiptCheckResult(False, "missing", None, None)


def test_check_receipt_corrupt_json(tmp_path: Path) -> None:
    (tmp_path / ".launchpad").mkdir(parents=True, exist_ok=True)
    (tmp_path / RECEIPT_PATH).write_text("not json at all", encoding="utf-8")
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "missing"  # unparseable -> treated as missing


def test_check_receipt_future_version_distinct_from_corrupt(
    tmp_path: Path,
) -> None:
    # BL-371 v2 (PR #76 architecture-strategist F1): a receipt written
    # by a newer LaunchPad (version > RECEIPT_VERSION) must surface as
    # `future_version` so the audit log and telemetry can point the
    # user at the upgrade path. "Corrupt" is reserved for actually
    # malformed receipts.
    _seed_receipt(tmp_path, version=999)
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "future_version"
    assert result.writer_command == "/lp-build"


def test_check_receipt_corrupt_for_non_int_version(tmp_path: Path) -> None:
    _seed_receipt(tmp_path, version="not-a-number")
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "corrupt"


def test_check_receipt_corrupt_for_bool_version(tmp_path: Path) -> None:
    # ``bool`` is a subclass of ``int`` in Python; ensure True/False are
    # rejected rather than treated as version 1/0.
    _seed_receipt(tmp_path, version=True)
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "corrupt"


def test_check_receipt_prior_failed(tmp_path: Path) -> None:
    _seed_receipt(tmp_path, exit_code=1)
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "prior_failed"
    assert result.writer_command == "/lp-build"


def test_check_receipt_stale(tmp_path: Path) -> None:
    old = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _seed_receipt(tmp_path, timestamp_utc=old)
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "stale"
    assert result.receipt_age_seconds is not None
    assert result.receipt_age_seconds >= 3600


def test_check_receipt_config_changed(tmp_path: Path) -> None:
    _seed_receipt(tmp_path)
    # Mutate the config after the receipt was sealed.
    (tmp_path / CONFIG_PATH).write_text("providers:\n  - vercel\n", encoding="utf-8")
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "config_changed"


def test_check_receipt_checklist_changed(tmp_path: Path) -> None:
    _seed_checklist(tmp_path, "# initial\n")
    _seed_receipt(tmp_path)
    (tmp_path / CHECKLIST_PATH).write_text("# mutated\n", encoding="utf-8")
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "checklist_changed"


def test_check_receipt_valid(tmp_path: Path) -> None:
    _seed_checklist(tmp_path)
    _seed_receipt(tmp_path)
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.valid is True
    assert result.reason == "valid"
    assert result.writer_command == "/lp-build"


def test_check_receipt_handles_both_files_missing(tmp_path: Path) -> None:
    # Receipt records null shas for both config + checklist; with both still
    # missing, the receipt remains valid.
    target = tmp_path / RECEIPT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": RECEIPT_VERSION,
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exit_code": 0,
        "config_sha256": None,
        "checklist_sha256": None,
        "section_path": None,
        "writer_command": "/lp-preflight",
        "freshness_window_seconds": DEFAULT_FRESHNESS_WINDOW_SECONDS,
    }
    target.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.valid is True


# --- write_receipt ----------------------------------------------------------


def test_write_receipt_writes_on_pass(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    _seed_checklist(tmp_path)
    target = write_receipt(
        tmp_path,
        exit_code=0,
        section_path=None,
        writer_command="/lp-build",
        freshness_window_seconds=DEFAULT_FRESHNESS_WINDOW_SECONDS,
    )
    assert target is not None
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["version"] == RECEIPT_VERSION
    assert payload["exit_code"] == 0
    assert payload["writer_command"] == "/lp-build"
    assert payload["freshness_window_seconds"] == DEFAULT_FRESHNESS_WINDOW_SECONDS
    assert payload["config_sha256"] == _sha256_of_file(tmp_path / CONFIG_PATH)


def test_write_receipt_removes_stale_on_fail(tmp_path: Path) -> None:
    _seed_receipt(tmp_path)
    result = write_receipt(
        tmp_path,
        exit_code=1,
        section_path=None,
        writer_command="/lp-build",
        freshness_window_seconds=DEFAULT_FRESHNESS_WINDOW_SECONDS,
    )
    assert result is None
    assert not (tmp_path / RECEIPT_PATH).exists()


def test_write_receipt_no_op_when_no_receipt_and_fail(tmp_path: Path) -> None:
    # Fail with no prior receipt: nothing to scrub, no write.
    result = write_receipt(
        tmp_path,
        exit_code=2,
        section_path=None,
        writer_command="/lp-ship",
        freshness_window_seconds=DEFAULT_FRESHNESS_WINDOW_SECONDS,
    )
    assert result is None
    assert not (tmp_path / RECEIPT_PATH).exists()


# --- _audit_log_event -------------------------------------------------------


def test_audit_log_appends(tmp_path: Path) -> None:
    _audit_log_event(tmp_path, "hello")
    _audit_log_event(tmp_path, "world")
    body = (tmp_path / AUDIT_LOG_PATH).read_text(encoding="utf-8")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert lines[0].endswith(" hello")
    assert lines[1].endswith(" world")


# --- CLI: --read-receipt / --write-receipt ---------------------------------


def test_cli_write_receipt_after_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_config(tmp_path, providers=["spec-completeness"])
    # Seed minimal docs so spec-completeness passes; spec-completeness only
    # gates A items that this fixture intentionally satisfies via empty repo
    # state (no missing artifacts to flag). We work around by using a config
    # that triggers no failing checks: the bundled `spec-completeness`
    # profile flags missing PRDs etc., so we mock run_preflight instead.
    from types import SimpleNamespace

    fake_report = SimpleNamespace(
        ok=True,
        results=[],
        failures=[],
        needs_confirmation=[],
        providers=["spec-completeness"],
        checklist_path=str(tmp_path / CHECKLIST_PATH),
    )

    import lp_preflight  # noqa: PLC0415

    monkeypatch.setattr(lp_preflight, "run_preflight", lambda *a, **k: fake_report)

    rc = main(
        [
            "--repo-root",
            str(tmp_path),
            "--write-receipt",
            "--writer-command",
            "/lp-build",
        ]
    )
    assert rc == 0
    capsys.readouterr()  # discard
    assert (tmp_path / RECEIPT_PATH).exists()
    payload = json.loads((tmp_path / RECEIPT_PATH).read_text(encoding="utf-8"))
    assert payload["exit_code"] == 0
    assert payload["writer_command"] == "/lp-build"


def test_cli_read_receipt_skip_when_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_checklist(tmp_path)
    _seed_receipt(tmp_path)
    import lp_preflight  # noqa: PLC0415

    called = []

    def _explode(*_a: object, **_k: object) -> None:
        called.append(True)
        raise AssertionError("run_preflight must not be called when receipt is valid")

    monkeypatch.setattr(lp_preflight, "run_preflight", _explode)
    rc = main(
        [
            "--repo-root",
            str(tmp_path),
            "--read-receipt",
            "--writer-command",
            "/lp-ship",
        ]
    )
    assert rc == 0
    assert called == []
    out = capsys.readouterr().out
    assert "receipt valid" in out
    audit = (tmp_path / AUDIT_LOG_PATH).read_text(encoding="utf-8")
    assert "preflight-skipped-via-receipt" in audit
    assert "writer=/lp-build" in audit


def test_cli_read_receipt_runs_probes_when_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_config(tmp_path)
    _seed_checklist(tmp_path)
    old = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _seed_receipt(tmp_path, timestamp_utc=old)
    from types import SimpleNamespace

    fake_report = SimpleNamespace(
        ok=True,
        results=[],
        failures=[],
        needs_confirmation=[],
        providers=["spec-completeness"],
        checklist_path=str(tmp_path / CHECKLIST_PATH),
    )

    import lp_preflight  # noqa: PLC0415

    monkeypatch.setattr(lp_preflight, "run_preflight", lambda *a, **k: fake_report)
    rc = main(
        [
            "--repo-root",
            str(tmp_path),
            "--read-receipt",
            "--write-receipt",
            "--writer-command",
            "/lp-ship",
        ]
    )
    assert rc == 0
    capsys.readouterr()
    audit = (tmp_path / AUDIT_LOG_PATH).read_text(encoding="utf-8")
    assert "preflight-receipt-stale" in audit


def test_cli_freshness_window_override_negative_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(
        [
            "--repo-root",
            str(tmp_path),
            "--freshness-window-seconds",
            "-5",
        ]
    )
    assert rc == 2
    assert "must be a positive integer" in capsys.readouterr().err


# --- section_path scope validation (BL-371 v2, PR #76 P1) -------------------


def test_check_receipt_scope_project_wide_covers_section_scoped(
    tmp_path: Path,
) -> None:
    # A receipt written by a project-wide /lp-preflight (section_path=None)
    # covers a subsequent section-scoped caller. Broader covers narrower.
    _seed_checklist(tmp_path)
    _seed_receipt(tmp_path, section_path=None)
    result = check_receipt_validity(
        tmp_path,
        freshness_window_seconds=3600,
        current_section_path="docs/tasks/sections/hero.md",
    )
    assert result.valid is True


def test_check_receipt_scope_section_scoped_does_not_cover_project_wide(
    tmp_path: Path,
) -> None:
    # The cloud-reviewer headline P1: a section-scoped receipt MUST NOT
    # license skipping a project-wide /lp-ship gate. Section-scoped
    # probes ran a weaker section-specs-approved check than the
    # project-wide caller needs.
    _seed_checklist(tmp_path)
    _seed_receipt(tmp_path, section_path="docs/tasks/sections/hero.md")
    result = check_receipt_validity(
        tmp_path, freshness_window_seconds=3600, current_section_path=None
    )
    assert result.valid is False
    assert result.reason == "scope_changed"


def test_check_receipt_scope_mismatched_sections(tmp_path: Path) -> None:
    _seed_checklist(tmp_path)
    _seed_receipt(tmp_path, section_path="docs/tasks/sections/hero.md")
    result = check_receipt_validity(
        tmp_path,
        freshness_window_seconds=3600,
        current_section_path="docs/tasks/sections/footer.md",
    )
    assert result.valid is False
    assert result.reason == "scope_changed"


def test_check_receipt_scope_exact_section_match(tmp_path: Path) -> None:
    _seed_checklist(tmp_path)
    _seed_receipt(tmp_path, section_path="docs/tasks/sections/hero.md")
    result = check_receipt_validity(
        tmp_path,
        freshness_window_seconds=3600,
        current_section_path="docs/tasks/sections/hero.md",
    )
    assert result.valid is True


def test_check_receipt_future_timestamp_is_corrupt(tmp_path: Path) -> None:
    # BL-371 v2 (PR #76 testing-reviewer P2-1): a clock-skewed or
    # hand-edited future timestamp must NOT silently pass as valid.
    _seed_checklist(tmp_path)
    future = (datetime.now(UTC) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _seed_receipt(tmp_path, timestamp_utc=future)
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "corrupt"
    assert result.receipt_age_seconds is not None
    assert result.receipt_age_seconds < 0


def test_check_receipt_non_string_timestamp_is_corrupt(tmp_path: Path) -> None:
    _seed_receipt(tmp_path, timestamp_utc=12345)
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "corrupt"


def test_check_receipt_invalid_iso_timestamp_is_corrupt(tmp_path: Path) -> None:
    _seed_receipt(tmp_path, timestamp_utc="yesterday")
    result = check_receipt_validity(tmp_path, freshness_window_seconds=3600)
    assert result.reason == "corrupt"


# --- audit-log sanitization (BL-371 v2, PR #76 P1) --------------------------


def test_audit_log_event_swallows_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BL-371 v2 (PR #76 testing-reviewer P2-4): the OSError swallow path
    # must NOT propagate; an audit-log outage cannot block the gate.
    import lp_preflight  # noqa: PLC0415

    def _explode(*_a: object, **_k: object) -> None:
        raise PermissionError("simulated audit-log outage")

    monkeypatch.setattr(Path, "open", _explode)
    # Should NOT raise even though every write attempt explodes.
    _audit_log_event(tmp_path, "x")
    # Reset for the next call so subsequent tests are not affected.
    monkeypatch.undo()
    assert lp_preflight  # silence unused-import linter


def test_writer_command_with_newline_rejected_at_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # BL-371 v2 (PR #76 pattern-finder + security-auditor): a newline
    # in --writer-command must be rejected up-front so the sanitizer
    # never has to handle a smuggling attempt.
    rc = main(
        [
            "--repo-root",
            str(tmp_path),
            "--writer-command",
            "/lp-ship\nFORGED",
            "--read-receipt",
        ]
    )
    assert rc == 2
    assert "newline" in capsys.readouterr().err


def test_audit_log_writer_command_with_control_chars_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # BL-371 v2 (PR #76 pattern-finder + security-auditor F1): when the
    # receipt-on-disk has tampered writer_command field (control chars
    # bypassing the CLI guard), the sanitizer escapes them before they
    # land in the audit log.
    _seed_checklist(tmp_path)
    _seed_receipt(
        tmp_path,
        writer_command="/lp-build\x1b[31mFORGED\x1b[0m",
    )
    rc = main(
        [
            "--repo-root",
            str(tmp_path),
            "--read-receipt",
            "--writer-command",
            "/lp-ship",
        ]
    )
    assert rc == 0
    audit = (tmp_path / AUDIT_LOG_PATH).read_text(encoding="utf-8")
    # Escape sequences must be percent-escaped, not rendered literally.
    assert "\x1b" not in audit
    assert "\\x1b" in audit


# --- receipt write determinism / scope round-trip ---------------------------


def test_write_receipt_round_trips_section_path(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    _seed_checklist(tmp_path)
    target = write_receipt(
        tmp_path,
        exit_code=0,
        section_path="docs/tasks/sections/hero.md",
        writer_command="/lp-build",
        freshness_window_seconds=DEFAULT_FRESHNESS_WINDOW_SECONDS,
    )
    assert target is not None
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["section_path"] == "docs/tasks/sections/hero.md"
