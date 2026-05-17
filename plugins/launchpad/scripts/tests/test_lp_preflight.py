"""Tests for the BL-364 external-infrastructure preflight gate.

12 cases covering the BL-364 test plan: profile loading, A/B/C1/C2
dispatch, stale-window enforcement, slash-command integration spec-text,
provider-profile extensibility, uncommitted-changes warn-only, and the
spec-completeness probe set. All network/CLI calls go through the
ProbeClients seam so tests are hermetic.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import lp_preflight
from lp_preflight import (
    CommandResult,
    HttpResponse,
    PreflightConfigError,
    PreflightFailedError,
    ProbeClients,
    assert_preflight_ok,
    load_preflight_config,
    run_preflight,
)

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def _make_repo(tmp_path: Path, providers: list[str]) -> Path:
    """Create a minimal repo dir with a preflight.config.yaml."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        "providers:\n" + "".join(f"  - {p}\n" for p in providers),
        encoding="utf-8",
    )
    return tmp_path


def _make_clients(
    http_responses: dict[str, HttpResponse] | None = None,
    command_responses: dict[tuple, CommandResult] | None = None,
) -> ProbeClients:
    """Build a stub ProbeClients. URL-keyed for http_get; tuple-of-args
    keyed for run_command. Missing entries raise to make test gaps loud."""
    http_responses = http_responses or {}
    command_responses = command_responses or {}

    def _http(url: str, headers: dict[str, str]) -> HttpResponse:
        for prefix, resp in http_responses.items():
            if url.startswith(prefix):
                return resp
        raise AssertionError(f"unexpected http_get url: {url}")

    def _run(args: list[str]) -> CommandResult:
        key = tuple(args)
        if key in command_responses:
            return command_responses[key]
        for k, resp in command_responses.items():
            if len(args) >= len(k) and tuple(args[: len(k)]) == k:
                return resp
        raise AssertionError(f"unexpected run_command: {args}")

    return ProbeClients(http_get=_http, run_command=_run)


PROFILE_DIR = REPO_ROOT / "plugins" / "launchpad" / "preflight-profiles"


# ---------------------------------------------------------------------------
# Test 1: profile loader assembles checks across profiles + applies overrides.
# ---------------------------------------------------------------------------


def test_profile_loader_merges_and_applies_overrides(tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "providers:\n"
        "  - cloudflare-pages\n"
        "  - spec-completeness\n"
        "overrides:\n"
        "  cloudflare-pages.api-token-valid:\n"
        "    stale_window_days: 7\n",
        encoding="utf-8",
    )
    checks, providers = load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)
    assert providers == ["cloudflare-pages", "spec-completeness"]
    by_id = {c.item_id: c for c in checks}
    # Both profiles contributed.
    assert "cloudflare-pages.api-token-valid" in by_id
    assert "spec-completeness.prd-no-tbd-markers" in by_id
    # Override applied.
    assert by_id["cloudflare-pages.api-token-valid"].stale_window_days == 7
    # Profile default preserved where no override.
    assert by_id["cloudflare-pages.project-exists"].stale_window_days == 90


def test_profile_loader_refuses_missing_config(tmp_path: Path):
    with pytest.raises(PreflightConfigError, match="preflight.config.yaml"):
        load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)


def test_profile_loader_refuses_unknown_profile(tmp_path: Path):
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - does-not-exist\n", encoding="utf-8")
    with pytest.raises(PreflightConfigError, match="profile file not found"):
        load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)


# ---------------------------------------------------------------------------
# Test 2: Category A — file-exists probe.
# ---------------------------------------------------------------------------


def test_category_a_file_present_passes(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    ack = tmp_path / ".launchpad" / "autonomous-ack.md"
    ack.write_text("ack\n", encoding="utf-8")
    # Provide the minimum surface so the OTHER spec-completeness checks
    # don't all fail and obscure this assertion.
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "## [Unreleased]\n", encoding="utf-8"
    )
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    assert by_id["spec-completeness.autonomous-ack-exists"].status == "pass"


def test_category_a_file_missing_fails(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [Unreleased]\n", encoding="utf-8")
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["spec-completeness.autonomous-ack-exists"]
    assert res.status == "fail"
    assert "autonomous-ack.md" in res.message


# ---------------------------------------------------------------------------
# Test 3: Category B — mocked Cloudflare API token verify.
# ---------------------------------------------------------------------------


def test_category_b_cloudflare_token_valid(tmp_path: Path, monkeypatch):
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token-active")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "myproj")
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/client/v4/user/tokens/verify": HttpResponse(
                status=200,
                body=json.dumps(
                    {"success": True, "result": {"status": "active"}}
                ),
            ),
            "https://api.cloudflare.com/client/v4/accounts/acct123/pages/projects/myproj": HttpResponse(
                status=200, body=json.dumps({"success": True})
            ),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(
                0, "[]", ""
            ),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    assert by_id["cloudflare-pages.api-token-valid"].status == "pass"


def test_category_b_cloudflare_token_invalid(tmp_path: Path, monkeypatch):
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token-revoked")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "myproj")
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/client/v4/user/tokens/verify": HttpResponse(
                status=401, body='{"success": false, "errors": [{"code": 1000}]}'
            ),
            "https://api.cloudflare.com/client/v4/accounts/": HttpResponse(
                status=401, body="{}"
            ),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(
                0, "[]", ""
            ),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.api-token-valid"]
    assert res.status == "fail"
    assert "401" in res.message


# ---------------------------------------------------------------------------
# Test 4: Category C1 — confirmation + probe sequencing.
# ---------------------------------------------------------------------------


def test_category_c1_unconfirmed_blocks_before_probe(tmp_path: Path, monkeypatch):
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "slug")
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/client/v4/user/tokens/verify": HttpResponse(
                200, json.dumps({"success": True, "result": {"status": "active"}})
            ),
            "https://api.cloudflare.com/client/v4/accounts/acct/pages/projects/slug": HttpResponse(
                200, "{}"
            ),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    # project-exists is C1 — unticked box means needs-confirmation, not pass
    # (even though the probe WOULD succeed if we ran it).
    assert by_id["cloudflare-pages.project-exists"].status == "needs-confirmation"


def test_category_c1_confirmed_and_probe_runs(tmp_path: Path, monkeypatch):
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "slug")
    # Pre-tick the box for project-exists.
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Cloudflare Pages project exists "
        "(id: cloudflare-pages.project-exists)\n"
        "  Last confirmed: 2026-05-16T00:00:00Z\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/client/v4/user/tokens/verify": HttpResponse(
                200, json.dumps({"success": True, "result": {"status": "active"}})
            ),
            "https://api.cloudflare.com/client/v4/accounts/acct/pages/projects/slug": HttpResponse(
                200, "{}"
            ),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    assert by_id["cloudflare-pages.project-exists"].status == "pass"


def test_category_c1_confirmed_but_probe_fails_blocks(tmp_path: Path, monkeypatch):
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "missing-slug")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Cloudflare Pages project (id: cloudflare-pages.project-exists)\n"
        "  Last confirmed: 2026-05-16T00:00:00Z\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/client/v4/user/tokens/verify": HttpResponse(
                200, json.dumps({"success": True, "result": {"status": "active"}})
            ),
            "https://api.cloudflare.com/client/v4/accounts/acct/pages/projects/missing-slug": HttpResponse(
                404, "{}"
            ),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.project-exists"]
    assert res.status == "fail"
    assert "404" in res.message


# ---------------------------------------------------------------------------
# Test 5: Category C2 — trust-only.
# ---------------------------------------------------------------------------


def test_category_c2_confirmed_passes_trusted(tmp_path: Path):
    _make_repo(tmp_path, ["cloudflare-pages"])
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Cloudflare account (id: cloudflare-pages.account-exists)\n"
        "  Last confirmed: 2026-05-16T00:00:00Z\n",
        encoding="utf-8",
    )
    # Need all envs set so other checks don't blow up the run; we only
    # assert on the C2 item.
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/": HttpResponse(401, "{}"),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.account-exists"]
    assert res.status == "pass"
    assert "trusted" in res.message.lower()


def test_category_c2_unconfirmed_needs_confirmation(tmp_path: Path):
    _make_repo(tmp_path, ["cloudflare-pages"])
    clients = _make_clients(
        http_responses={"https://api.cloudflare.com/": HttpResponse(401, "{}")},
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    assert by_id["cloudflare-pages.account-exists"].status == "needs-confirmation"


# ---------------------------------------------------------------------------
# Test 6: Stale-window enforcement.
# ---------------------------------------------------------------------------


def test_stale_window_reflags_expired_confirmation(tmp_path: Path):
    _make_repo(tmp_path, ["cloudflare-pages"])
    # Account-exists has a 365-day stale window. A timestamp from 400 days
    # ago triggers re-confirmation.
    old_ts = (datetime.now(UTC) - timedelta(days=400)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Cloudflare account (id: cloudflare-pages.account-exists)\n"
        f"  Last confirmed: {old_ts}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        http_responses={"https://api.cloudflare.com/": HttpResponse(401, "{}")},
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.account-exists"]
    assert res.status == "needs-confirmation"
    assert "stale" in res.message.lower() or "expired" in res.message.lower()


# ---------------------------------------------------------------------------
# Test 7: /lp-ship Step 0.6 spec-text integration.
# ---------------------------------------------------------------------------


def test_lp_ship_step_06_references_preflight_module():
    ship_md = REPO_ROOT / "plugins" / "launchpad" / "commands" / "lp-ship.md"
    text = ship_md.read_text(encoding="utf-8")
    assert "Step 0.6" in text
    assert "lp_preflight.py" in text
    # Gate must be positioned AFTER the BL-356 ack gate (Step 0.5).
    assert text.index("Step 0.5") < text.index("Step 0.6")
    # Must come before Step 1 (Branch Guard).
    assert text.index("Step 0.6") < text.index("Step 1: Branch Guard")


# ---------------------------------------------------------------------------
# Test 8: /lp-build Step 0.6 spec-text integration.
# ---------------------------------------------------------------------------


def test_lp_build_step_06_references_preflight_module_before_inf():
    build_md = REPO_ROOT / "plugins" / "launchpad" / "commands" / "lp-build.md"
    text = build_md.read_text(encoding="utf-8")
    assert "0.6" in text
    assert "lp_preflight.py" in text
    # Gate must precede /lp-inf dispatch.
    preflight_pos = text.index("0.6")
    inf_pos = text.index("Step 1: /lp-inf")
    assert preflight_pos < inf_pos, (
        "preflight gate must precede /lp-inf so it fails-fast before "
        "autonomous implementation"
    )


# ---------------------------------------------------------------------------
# Test 9: Standalone /lp-preflight CLI exit codes.
# ---------------------------------------------------------------------------


def test_cli_exit_one_on_failure(tmp_path: Path, monkeypatch, capsys):
    _make_repo(tmp_path, ["spec-completeness"])
    # Don't create PRD / CHANGELOG / ack — should fail.
    # The CLI uses default_clients(); to avoid real subprocess calls in
    # git-uncommitted-changes-warn, point at a dir with no .git so git
    # status returns non-zero (probe handles gracefully by passing).
    monkeypatch.chdir(tmp_path)
    rc = lp_preflight.main(["--repo-root", str(tmp_path)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "External-infrastructure preflight failed" in out


def test_cli_exit_zero_on_pass(tmp_path: Path, monkeypatch, capsys):
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\nNo placeholders here.\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n## [Unreleased]\n", encoding="utf-8"
    )
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    # Init a clean git repo so the uncommitted-changes warn-probe sees a
    # clean tree (note: even a dirty tree wouldn't fail — it's warn-only —
    # but we keep the smoke clean).
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"], check=True
    )
    monkeypatch.chdir(tmp_path)
    rc = lp_preflight.main(["--repo-root", str(tmp_path)])
    assert rc == 0


# ---------------------------------------------------------------------------
# Test 10: Provider profile extensibility.
# ---------------------------------------------------------------------------


def test_dropping_in_new_profile_yaml_extends_check_list(tmp_path: Path):
    # User's repo cfg references a custom profile name.
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - my-custom\n", encoding="utf-8")
    # Custom profile lives in a dir we control for this test.
    custom_dir = tmp_path / "custom-profiles"
    custom_dir.mkdir()
    (custom_dir / "my-custom.yaml").write_text(
        "name: my-custom\n"
        "checks:\n"
        "  - id: my-custom.always-passes\n"
        "    category: A\n"
        "    title: Smoke check\n"
        "    setup_hint: nothing to do\n"
        "    probe: file-exists\n"
        "    args:\n"
        "      path: README.md\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# README\n", encoding="utf-8")
    checks, providers = load_preflight_config(tmp_path, profile_dir=custom_dir)
    assert providers == ["my-custom"]
    assert len(checks) == 1
    assert checks[0].item_id == "my-custom.always-passes"


# ---------------------------------------------------------------------------
# Test 11: Uncommitted changes — warn-only, do not block.
# ---------------------------------------------------------------------------


def test_uncommitted_changes_warn_only(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [Unreleased]\n", encoding="utf-8")
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    # Inject a stub that reports a dirty tree.
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, " M file1.txt\n?? file2.txt\n", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["spec-completeness.working-tree-clean-warn"]
    # Per BL-364 locked design decision 1: dirty tree warns, does NOT
    # fail. Status is `pass` with a warning message naming the count.
    assert res.status == "pass"
    assert "WARNING" in res.message
    assert "uncommitted" in res.message.lower()


# ---------------------------------------------------------------------------
# Test 12: Spec-completeness profile end-to-end.
# ---------------------------------------------------------------------------


def test_spec_completeness_full_pass(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# Product Requirements\n\nNo placeholders.\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n## [v0.1.0]\n- Initial release\n", encoding="utf-8"
    )
    sections = tmp_path / "docs" / "tasks" / "sections"
    sections.mkdir(parents=True)
    (sections / "hero.md").write_text(
        "---\nname: hero\nstatus: approved\n---\n", encoding="utf-8"
    )
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    failures = [r for r in report.results if r.status == "fail"]
    assert failures == [], f"unexpected failures: {failures}"


def test_spec_completeness_tbd_marker_fails(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text("ack\n", encoding="utf-8")
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n\nAudience: [TBD]\n\nMore content here.\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [Unreleased]\n", encoding="utf-8")
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["spec-completeness.prd-no-tbd-markers"]
    assert res.status == "fail"
    assert "[TBD]" in res.message or "TBD" in res.message


def test_spec_completeness_section_not_approved_fails(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [Unreleased]\n", encoding="utf-8")
    sections = tmp_path / "docs" / "tasks" / "sections"
    sections.mkdir(parents=True)
    (sections / "hero.md").write_text(
        "---\nstatus: shaped\n---\n", encoding="utf-8"
    )
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["spec-completeness.section-specs-approved"]
    assert res.status == "fail"
    assert "shaped" in res.message


# ---------------------------------------------------------------------------
# Bonus: assert_preflight_ok raises with the canonical refuse message.
# ---------------------------------------------------------------------------


def test_assert_preflight_ok_raises_with_refuse_message(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    with pytest.raises(PreflightFailedError) as excinfo:
        assert_preflight_ok(tmp_path, clients=clients, profile_dir=PROFILE_DIR)
    msg = str(excinfo.value)
    assert "External-infrastructure preflight failed" in msg
    assert ".launchpad/preflight-checklist.md" in msg


def test_assert_preflight_ok_returns_report_on_pass(tmp_path: Path):
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [v1.0.0]\n", encoding="utf-8")
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    report = assert_preflight_ok(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR
    )
    assert report.ok
    assert not report.failures
    assert not report.needs_confirmation
