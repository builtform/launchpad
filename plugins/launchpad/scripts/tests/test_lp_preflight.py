"""Tests for the BL-364 external-infrastructure preflight gate.

Covers the 12-case BL-364 test plan plus the round-1 review fix-pass
expansions (vercel / netlify / dns probe coverage, github-secrets
failure branches, PreflightConfigError variants, parse_checklist
tolerance, first-tick stamping, _render_check_block exhaustiveness,
B-probe URL-path injection, _http_get scheme-rejection, _is_stale
corruption surfacing). All network/CLI calls go through the
ProbeClients seam so tests are hermetic; the only exception is
test_cli_exit_zero_on_pass which invokes real `git` for a CLI smoke.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import lp_preflight
from lp_preflight import (
    CheckConfirmation,
    CommandResult,
    HttpResponse,
    PreflightConfigError,
    PreflightFailedError,
    ProbeClients,
    _is_stale,
    assert_preflight_ok,
    load_preflight_config,
    parse_checklist,
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


def _recent_iso() -> str:
    """Return an ISO-8601 UTC timestamp 1 day before now.

    Tests that need a "recent enough" Last-confirmed value use this so
    the assertion never goes stale as wall-clock time advances. Hardcoded
    timestamps would silently fail tests after the configured stale
    window elapses (Codex round-2 P2: hardcoded `2026-05-16` values
    were 60+ days fresh at PR creation but would drift to stale on
    later CI runs).
    """
    return (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def test_load_profile_malformed_yaml_raises_with_path_hint(tmp_path: Path):
    """Malformed YAML in a profile file surfaces as PreflightConfigError
    with the profile path embedded in the message, so the user can find
    and fix the bad file.

    Regression for the narrowed `except yaml.YAMLError` clause in
    `load_profile`: an `AttributeError` or other genuine bug from a
    future refactor must NOT be swallowed as "parse failure". Only
    PyYAML's documented YAMLError hierarchy should be rewrapped.
    """
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    bad_profile = profile_dir / "broken.yaml"
    # Unclosed flow mapping → yaml.scanner.ScannerError (YAMLError subclass).
    bad_profile.write_text("checks: { unclosed: brace\n", encoding="utf-8")
    from lp_preflight import load_profile

    with pytest.raises(PreflightConfigError) as exc_info:
        load_profile(bad_profile)
    msg = str(exc_info.value)
    assert "failed to parse" in msg
    assert str(bad_profile) in msg


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
                body=json.dumps({"success": True, "result": {"status": "active"}}),
            ),
            "https://api.cloudflare.com/client/v4/accounts/acct123/pages/projects/myproj": HttpResponse(
                status=200, body=json.dumps({"success": True})
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
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.api-token-valid"]
    assert res.status == "fail"
    assert "401" in res.message


def test_cloudflare_token_network_error_surfaces_clearly(tmp_path: Path, monkeypatch):
    """When the Cloudflare API call fails at the transport layer (URLError /
    TimeoutError / OSError), ``default_clients()._http_get`` returns
    ``HttpResponse(status=0, body="network error: ...")``. The B probe must
    surface the network-error body directly rather than leaking the synthetic
    "HTTP 0" status, so users see "network error talking to Cloudflare:
    connection refused" instead of the confusing "Cloudflare token verify
    failed: HTTP 0"."""
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "valid-looking-token")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "myproj")
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/client/v4/user/tokens/verify": HttpResponse(
                status=0, body="network error: connection refused"
            ),
            "https://api.cloudflare.com/client/v4/accounts/acct123/pages/projects/myproj": HttpResponse(
                status=0, body="network error: connection refused"
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
    res = by_id["cloudflare-pages.api-token-valid"]
    assert res.status == "fail"
    # The clearer message surfaces "network" and the provider name; the old
    # "HTTP 0" wording would have been confusing and is now explicitly absent.
    assert "network" in res.message.lower()
    assert "cloudflare" in res.message.lower()
    assert "HTTP 0" not in res.message
    # And the underlying transport-layer detail is preserved (the prefix
    # "network error: " gets stripped so we don't double-prefix).
    assert "connection refused" in res.message


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
        f"  Last confirmed: {_recent_iso()}\n",
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
        f"  Last confirmed: {_recent_iso()}\n",
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
        f"  Last confirmed: {_recent_iso()}\n",
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


def test_first_tick_with_no_timestamp_is_stamped_at_run_time(tmp_path: Path):
    """First-tick UX: when the user ticks a previously-unticked box and the
    prior checklist had no timestamp (`Last confirmed: never`), the next
    `run_preflight` invocation must treat the current run as the
    confirmation event and stamp `last_confirmed = now`. Without this
    branch (lp_preflight.py:1146-1153), the very first tick + re-run
    would be flagged stale immediately because `_is_stale` treats
    `last_confirmed is None` as stale-by-default. This test pins the
    behavior to a fixed `now` so the stamped timestamp appears verbatim
    in the rendered checklist."""
    repo = _make_repo(tmp_path, ["cloudflare-pages"])
    # Pre-write a checklist where the user ticked the box but no
    # timestamp was ever recorded (the first-tick case).
    (repo / ".launchpad" / "preflight-checklist.md").write_text(
        "- [x] Cloudflare account (id: cloudflare-pages.account-exists)\n"
        "  Last confirmed: never\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        http_responses={
            "https://api.cloudflare.com/": HttpResponse(401, "{}"),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    fixed_now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    report = run_preflight(
        repo,
        clients=clients,
        profile_dir=PROFILE_DIR,
        write_checklist=True,
        now=fixed_now,
    )
    by_id = {r.item_id: r for r in report.results}
    # The stamping turned a None-timestamp tick into a fresh confirmation,
    # so the C2 check passes rather than being flagged stale.
    assert by_id["cloudflare-pages.account-exists"].status == "pass"
    # The re-rendered checklist must record the stamped timestamp so the
    # stale-window timer starts from this run.
    rendered = (repo / ".launchpad" / "preflight-checklist.md").read_text(
        encoding="utf-8"
    )
    assert "Last confirmed: 2026-05-17T12:00:00Z" in rendered


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
    old_ts = (datetime.now(UTC) - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
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
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
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
    (sections / "hero.md").write_text("---\nstatus: shaped\n---\n", encoding="utf-8")
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
    report = assert_preflight_ok(tmp_path, clients=clients, profile_dir=PROFILE_DIR)
    assert report.ok
    assert not report.failures
    assert not report.needs_confirmation


# ---------------------------------------------------------------------------
# _is_stale: ISO-with-Z parsing + corrupt-timestamp surfacing.
# ---------------------------------------------------------------------------


def test_is_stale_iso_with_z_suffix_parses_natively():
    """py311 `datetime.fromisoformat` parses the `Z` suffix natively, so a
    recent timestamp ending in `Z` is NOT stale within the configured window."""
    recent_ts = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conf = CheckConfirmation(
        item_id="example.item",
        confirmed=True,
        last_confirmed=recent_ts,
    )
    assert _is_stale(conf, 30) is False


def test_is_stale_unparseable_timestamp_returns_true_and_warns(capsys):
    """A corrupt last_confirmed value must NOT silently mask the corruption:
    return True (safe-by-default) AND emit a stderr warning naming the item."""
    conf = CheckConfirmation(
        item_id="example.item",
        confirmed=True,
        last_confirmed="not-a-valid-timestamp",
    )
    assert _is_stale(conf, 30) is True
    captured = capsys.readouterr()
    assert "corrupt last_confirmed timestamp" in captured.err
    assert "example.item" in captured.err


# ---------------------------------------------------------------------------
# DNS probe: defense-in-depth against leading-dash domain injection.
# ---------------------------------------------------------------------------


def test_dns_probe_rejects_leading_dash_domain(tmp_path: Path):
    """Both DNS probes must pass `--` before the domain so that `dig` cannot
    consume an attacker-controlled leading-dash token (e.g. `-fsome/path`,
    `-x 1.2.3.4`) as an option flag. The argv must contain the end-of-options
    sentinel immediately before the domain argument."""
    captured_argv: list[list[str]] = []

    def _run(args: list[str]) -> CommandResult:
        captured_argv.append(list(args))
        # Return an empty answer so the probe terminates deterministically;
        # we only care about the argv shape, not the outcome.
        return CommandResult(0, "", "")

    def _http(url: str, headers: dict[str, str]) -> HttpResponse:
        raise AssertionError(f"unexpected http_get url: {url}")

    clients = ProbeClients(http_get=_http, run_command=_run)
    hostile = "-fsome/path"

    cname_check = lp_preflight.CheckDefinition(
        item_id="namecheap-dns.dns-cname",
        category="C1",
        title="DNS CNAME probe",
        setup_hint="",
        stale_window_days=30,
        probe="dns-resolves-via-cname",
        args={"domain": hostile, "expected_suffix": ".pages.dev"},
    )
    cf_check = lp_preflight.CheckDefinition(
        item_id="cloudflare-pages.dns-cloudflare",
        category="C1",
        title="DNS Cloudflare probe",
        setup_hint="",
        stale_window_days=30,
        probe="dns-resolves-to-cloudflare",
        args={"domain": hostile},
    )

    cname_probe = lp_preflight._PROBE_REGISTRY["dns-resolves-via-cname"]
    cloudflare_probe = lp_preflight._PROBE_REGISTRY["dns-resolves-to-cloudflare"]
    cname_probe(tmp_path, cname_check, clients)
    cloudflare_probe(tmp_path, cf_check, clients)

    assert len(captured_argv) == 2
    for argv in captured_argv:
        assert argv[0] == "dig"
        assert "--" in argv, f"missing end-of-options sentinel in argv: {argv}"
        dash_dash_idx = argv.index("--")
        # The hostile domain must appear immediately after `--`, so `dig`
        # treats it as a positional argument rather than a flag.
        assert argv[dash_dash_idx + 1] == hostile
        # And `--` must come after the `+short` query option.
        assert "+short" in argv[:dash_dash_idx]


# ---------------------------------------------------------------------------
# _http_get: case-insensitive https scheme enforcement (P2 regression guard).
# ---------------------------------------------------------------------------


def test_http_get_refuses_uppercase_https():
    """URI schemes are case-insensitive per RFC 3986; the scheme check must
    reject `HTTPS://...` (and other case variants) without making a network
    call so the bandit B310 nosec rationale stays accurate."""
    clients = lp_preflight.default_clients()
    resp = clients.http_get("HTTPS://api.cloudflare.com/", {})
    assert resp.status == 0
    assert "refused non-https URL" in resp.body


def test_http_get_refuses_file_scheme():
    """file://, http://, and other non-https schemes must be refused before
    urlopen is called, returning HttpResponse(status=0, body=refused...)."""
    clients = lp_preflight.default_clients()

    file_resp = clients.http_get("file:///etc/passwd", {})
    assert file_resp.status == 0
    assert "refused non-https URL" in file_resp.body

    http_resp = clients.http_get("http://api.cloudflare.com/", {})
    assert http_resp.status == 0
    assert "refused non-https URL" in http_resp.body


# ---------------------------------------------------------------------------
# B-probe URL-path injection defense (P2 regression guard).
#
# Env-supplied identifiers (account / slug / project / site) are
# interpolated into provider API URLs via f-strings. A value containing
# `/`, `?`, `#`, `..`, or whitespace would rewrite the URL path or query.
# Each probe must reject inputs outside the documented `[A-Za-z0-9_-]+`
# charset BEFORE issuing the request, with a clear error rather than a
# silent 404 from the provider.
# ---------------------------------------------------------------------------


def _no_http_clients() -> ProbeClients:
    """ProbeClients seam that raises on any HTTP call: proves the probe
    refused to construct a request URL when the input segment is rejected."""

    def _http(url: str, headers: dict[str, str]) -> HttpResponse:
        raise AssertionError(
            f"probe must not issue HTTP request for invalid segment: {url}"
        )

    def _run(args: list[str]) -> CommandResult:
        raise AssertionError(f"unexpected run_command: {args}")

    return ProbeClients(http_get=_http, run_command=_run)


def test_cloudflare_pages_rejects_slug_with_slash(tmp_path: Path, monkeypatch):
    """A slug containing `/` (e.g., `../etc`) must be refused before
    constructing the Cloudflare Pages URL; otherwise the f-string would
    rewrite the path to `/accounts/acct/pages/projects/../etc`."""
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "../etc")
    chk = lp_preflight.CheckDefinition(
        item_id="cloudflare-pages.project-exists",
        category="C1",
        title="Cloudflare Pages project exists",
        setup_hint="",
        stale_window_days=90,
        probe="cloudflare-pages-project-exists",
        args={},
    )
    probe = lp_preflight._PROBE_REGISTRY["cloudflare-pages-project-exists"]
    result = probe(tmp_path, chk, _no_http_clients())
    assert result.status == "fail"
    assert "CLOUDFLARE_PAGES_PROJECT_SLUG" in result.message
    assert "[A-Za-z0-9_-]+" in result.message


def test_vercel_rejects_project_with_query_char(tmp_path: Path, monkeypatch):
    """A project ID containing `?` (e.g., `abc?inject=1`) must be refused
    before constructing the Vercel projects URL; otherwise the f-string
    would append a query string that overrides path semantics."""
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "abc?inject=1")
    chk = lp_preflight.CheckDefinition(
        item_id="vercel.project-exists",
        category="C1",
        title="Vercel project exists",
        setup_hint="",
        stale_window_days=90,
        probe="vercel-project-exists",
        args={},
    )
    probe = lp_preflight._PROBE_REGISTRY["vercel-project-exists"]
    result = probe(tmp_path, chk, _no_http_clients())
    assert result.status == "fail"
    assert "VERCEL_PROJECT_ID" in result.message
    assert "[A-Za-z0-9_-]+" in result.message


def test_netlify_rejects_site_with_whitespace(tmp_path: Path, monkeypatch):
    """A site ID containing internal whitespace must be refused before
    constructing the Netlify sites URL; whitespace inside the env value
    survives `_resolve_env`'s edge-strip and would corrupt the path."""
    monkeypatch.setenv("NETLIFY_AUTH_TOKEN", "tok")
    monkeypatch.setenv("NETLIFY_SITE_ID", "site with space")
    chk = lp_preflight.CheckDefinition(
        item_id="netlify.site-exists",
        category="C1",
        title="Netlify site exists",
        setup_hint="",
        stale_window_days=90,
        probe="netlify-site-exists",
        args={},
    )
    probe = lp_preflight._PROBE_REGISTRY["netlify-site-exists"]
    result = probe(tmp_path, chk, _no_http_clients())
    assert result.status == "fail"
    assert "NETLIFY_SITE_ID" in result.message
    assert "[A-Za-z0-9_-]+" in result.message


# ---------------------------------------------------------------------------
# parse_checklist whitespace tolerance (P2 regression guard).
#
# Real-world user edits in the generated checklist file commonly introduce
# leading whitespace variants (4-space indent, tab characters) that the
# original strict regex silently dropped. The tolerant regex must accept
# these without losing confirmation state.
# ---------------------------------------------------------------------------


def test_parse_checklist_tolerates_4space_indent(tmp_path: Path):
    """A user-edited checklist with 4-space indented item lines and a
    4-space indented `Last confirmed:` attribution line must still parse
    correctly."""
    checklist = tmp_path / "preflight-checklist.md"
    checklist.write_text(
        "    - [x] Foo (id: spec.foo)\n    Last confirmed: 2026-05-17T00:00:00Z\n",
        encoding="utf-8",
    )
    result = parse_checklist(checklist)
    assert result == {
        "spec.foo": CheckConfirmation(
            item_id="spec.foo",
            confirmed=True,
            last_confirmed="2026-05-17T00:00:00Z",
        )
    }


def test_parse_checklist_tolerates_tab_indent(tmp_path: Path):
    """A user-edited checklist with tab-indented item lines and a
    tab-indented `Last confirmed:` attribution line must still parse
    correctly."""
    checklist = tmp_path / "preflight-checklist.md"
    checklist.write_text(
        "\t- [x] Foo (id: spec.foo)\n\tLast confirmed: 2026-05-17T00:00:00Z\n",
        encoding="utf-8",
    )
    result = parse_checklist(checklist)
    assert result == {
        "spec.foo": CheckConfirmation(
            item_id="spec.foo",
            confirmed=True,
            last_confirmed="2026-05-17T00:00:00Z",
        )
    }


# ---------------------------------------------------------------------------
# _render_check_block status-exhaustiveness guard (P2 readability).
#
# The box-state branch is an explicit if/elif chain over the closed status
# set {"pass", "needs-confirmation", "fail"} with an `else: raise` arm so
# that any future addition to CheckResult.status surfaces as a loud error
# rather than silently rendering with fail semantics.
# ---------------------------------------------------------------------------


def test_render_check_block_raises_on_unknown_status():
    """An unknown CheckResult.status must raise ValueError rather than
    silently falling through to a fail-shaped render."""
    chk = lp_preflight.CheckDefinition(
        item_id="spec.future",
        category="C1",
        title="Future check",
        setup_hint="",
        stale_window_days=90,
        probe=None,
        args={},
    )
    confirmation = CheckConfirmation(
        item_id="spec.future",
        confirmed=False,
        last_confirmed=None,
    )
    result = lp_preflight.CheckResult(
        item_id="spec.future",
        category="C1",
        status="hypothetical-future-status",
        message="",
        setup_hint="",
    )
    with pytest.raises(ValueError, match="unknown status"):
        lp_preflight._render_check_block(chk, confirmation, result)


def test_render_check_block_c1_confirmed_but_failed_keeps_tick():
    """A C1 check whose user confirmation is in place but whose probe
    failed must render as ticked (preserving the prior confirmation)
    plus an explicit FAIL status line."""
    chk = lp_preflight.CheckDefinition(
        item_id="spec.c1",
        category="C1",
        title="C1 check",
        setup_hint="",
        stale_window_days=90,
        probe="some-probe",
        args={},
    )
    confirmation = CheckConfirmation(
        item_id="spec.c1",
        confirmed=True,
        last_confirmed="2026-05-17T00:00:00Z",
    )
    result = lp_preflight.CheckResult(
        item_id="spec.c1",
        category="C1",
        status="fail",
        message="probe failed",
        setup_hint="",
    )
    rendered = lp_preflight._render_check_block(chk, confirmation, result)
    assert rendered.startswith("- [x] C1 check (id: spec.c1)")
    assert "Status: FAIL: probe failed" in rendered


# ---------------------------------------------------------------------------
# Category B coverage gap: Vercel + Netlify token / project / site probes.
#
# The cloudflare-pages probes (above) have full token-invalid + project-404
# coverage; vercel and netlify ship with the same probe shape but had ZERO
# direct tests until BL-364 todo 02 closed the gap. These four tests mirror
# `test_category_b_cloudflare_token_invalid` and the C1 project-404 test,
# substituting the provider-specific URLs + env vars.
# ---------------------------------------------------------------------------


def test_category_b_vercel_token_invalid(tmp_path: Path, monkeypatch):
    """Stub HTTP 401 against the Vercel token-verify URL; the vercel
    api-token-valid B-probe must surface a fail status whose message names
    the 401 status so the user knows the token (not the network) is the
    problem."""
    _make_repo(tmp_path, ["vercel"])
    monkeypatch.setenv("VERCEL_TOKEN", "test-token-revoked")
    monkeypatch.setenv("VERCEL_ORG_ID", "org123")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "proj123")
    clients = _make_clients(
        http_responses={
            "https://api.vercel.com/v2/user": HttpResponse(
                status=401, body='{"error": {"code": "forbidden"}}'
            ),
            "https://api.vercel.com/v9/projects/": HttpResponse(status=401, body="{}"),
        },
        command_responses={
            ("gh", "secret", "list", "--json", "name"): CommandResult(0, "[]", ""),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["vercel.api-token-valid"]
    assert res.status == "fail"
    assert "401" in res.message


def test_category_b_vercel_project_404(tmp_path: Path, monkeypatch):
    """Stub a valid 200 for token verify but a 404 for the project lookup;
    the vercel project-exists probe must fail with a message naming the
    HTTP 404 so the user knows the project id (not the token) is wrong."""
    _make_repo(tmp_path, ["vercel"])
    monkeypatch.setenv("VERCEL_TOKEN", "valid-token")
    monkeypatch.setenv("VERCEL_ORG_ID", "org123")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "missing-proj")
    # Pre-tick the C1 project-exists box so the probe actually runs (rather
    # than short-circuiting to needs-confirmation).
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Vercel project (id: vercel.project-exists)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        http_responses={
            "https://api.vercel.com/v2/user": HttpResponse(status=200, body="{}"),
            "https://api.vercel.com/v9/projects/missing-proj": HttpResponse(
                status=404, body="{}"
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
    res = by_id["vercel.project-exists"]
    assert res.status == "fail"
    assert "404" in res.message


def test_category_b_netlify_token_invalid(tmp_path: Path, monkeypatch):
    """Stub HTTP 401 against the Netlify user URL; the netlify
    api-token-valid B-probe must surface fail + 401 in the message."""
    _make_repo(tmp_path, ["netlify"])
    monkeypatch.setenv("NETLIFY_AUTH_TOKEN", "test-token-revoked")
    monkeypatch.setenv("NETLIFY_SITE_ID", "site-uuid")
    clients = _make_clients(
        http_responses={
            "https://api.netlify.com/api/v1/user": HttpResponse(
                status=401, body='{"code": 401, "message": "Unauthorized"}'
            ),
            "https://api.netlify.com/api/v1/sites/": HttpResponse(
                status=401, body="{}"
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
    res = by_id["netlify.api-token-valid"]
    assert res.status == "fail"
    assert "401" in res.message


def test_category_b_netlify_site_404(tmp_path: Path, monkeypatch):
    """Stub a valid 200 for token verify but a 404 for the site lookup;
    the netlify site-exists C1 probe must fail with 404 in the message
    after the C1 confirmation box is pre-ticked."""
    _make_repo(tmp_path, ["netlify"])
    monkeypatch.setenv("NETLIFY_AUTH_TOKEN", "valid-token")
    monkeypatch.setenv("NETLIFY_SITE_ID", "missing-site")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Netlify site (id: netlify.site-exists)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        http_responses={
            "https://api.netlify.com/api/v1/user": HttpResponse(status=200, body="{}"),
            "https://api.netlify.com/api/v1/sites/missing-site": HttpResponse(
                status=404, body="{}"
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
    res = by_id["netlify.site-exists"]
    assert res.status == "fail"
    assert "404" in res.message


# ---------------------------------------------------------------------------
# DNS probe coverage gap: most parse-heavy probes had ZERO direct tests
# until BL-364 todo 02 closed the gap.
#
# Cloudflare DNS tests run end-to-end through `run_preflight` with the
# cloudflare-dns profile + a pre-ticked checklist so the C1 probe actually
# fires. The CNAME-suffix test calls the probe directly through
# `_PROBE_REGISTRY` because the namecheap-dns profile does not bind
# `expected_suffix` in its default args (it is set per-project, and
# `overrides:` only merges `stale_window_days`, not args), so the direct-
# probe invocation pattern (already used by `test_dns_probe_rejects_
# leading_dash_domain`) is the cleanest hermetic path.
# ---------------------------------------------------------------------------


def test_dns_resolves_to_cloudflare_matches_104_prefix(tmp_path: Path, monkeypatch):
    """Stub `dig +short example.com` returning `104.16.1.1`; the
    dns-resolves-to-cloudflare probe must pass because the answer matches
    Cloudflare's 104.16.* edge prefix."""
    _make_repo(tmp_path, ["cloudflare-dns"])
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.com")
    # Pre-tick the C1 apex-resolves-to-cloudflare box so the probe runs.
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Custom domain resolves to Cloudflare "
        "(id: cloudflare-dns.apex-resolves-to-cloudflare)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.com"): CommandResult(
                0, "104.16.1.1\n", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-dns.apex-resolves-to-cloudflare"]
    assert res.status == "pass"
    assert "104.16.1.1" in res.message


def test_dns_resolves_to_cloudflare_rejects_third_party_ip(tmp_path: Path, monkeypatch):
    """Stub `dig +short example.com` returning `8.8.8.8` (Google DNS, not
    Cloudflare); the dns-resolves-to-cloudflare probe must fail with a
    message that names the unexpected answer + cites that it did not match
    the Cloudflare edge ranges."""
    _make_repo(tmp_path, ["cloudflare-dns"])
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.com")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Custom domain resolves to Cloudflare "
        "(id: cloudflare-dns.apex-resolves-to-cloudflare)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.com"): CommandResult(0, "8.8.8.8\n", ""),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-dns.apex-resolves-to-cloudflare"]
    assert res.status == "fail"
    assert "8.8.8.8" in res.message
    assert "Cloudflare" in res.message


def test_dns_resolves_via_cname_matches_pages_dev_suffix(tmp_path: Path, monkeypatch):
    """Stub `dig +short example.com` returning `myapp.pages.dev`; the
    dns-resolves-via-cname probe must pass when given `expected_suffix:
    .pages.dev` because the answer ends with the configured suffix.

    Invokes the probe directly through `_PROBE_REGISTRY` (rather than the
    full namecheap-dns profile pipeline) because `expected_suffix` is set
    per-project in profile args and `overrides:` only merges
    `stale_window_days`, not args. The direct-probe pattern mirrors
    `test_dns_probe_rejects_leading_dash_domain` above.
    """
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.com")
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.com"): CommandResult(
                0, "myapp.pages.dev.\n", ""
            ),
        }
    )
    chk = lp_preflight.CheckDefinition(
        item_id="namecheap-dns.apex-resolves-via-cname",
        category="C1",
        title="Custom domain resolves through CNAME target",
        setup_hint="",
        stale_window_days=365,
        probe="dns-resolves-via-cname",
        args={"domain_env": "PREFLIGHT_DOMAIN", "expected_suffix": ".pages.dev"},
    )
    probe = lp_preflight._PROBE_REGISTRY["dns-resolves-via-cname"]
    result = probe(tmp_path, chk, clients)
    assert result.status == "pass"
    assert "myapp.pages.dev" in result.message


def test_dns_resolves_fails_when_dig_missing(tmp_path: Path, monkeypatch):
    """Stub `clients.run_command` returning CommandResult(returncode=127,
    ...) to simulate `dig` not being installed on PATH; the
    dns-resolves-to-cloudflare probe must fail with an install hint
    naming BIND tools so the user knows how to remediate."""
    _make_repo(tmp_path, ["cloudflare-dns"])
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.com")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Custom domain resolves to Cloudflare "
        "(id: cloudflare-dns.apex-resolves-to-cloudflare)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.com"): CommandResult(
                127, "", "dig: command not found"
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-dns.apex-resolves-to-cloudflare"]
    assert res.status == "fail"
    assert "dig" in res.message
    assert "BIND" in res.message


# ---------------------------------------------------------------------------
# github-secrets-populated probe: failure-branch coverage.
#
# The probe at lp_preflight.py:933 has three failure branches that were
# previously untested (only the success/empty-secrets branch was exercised
# via the C2-confirmation tests above). Per todo 03 these cover:
#   1. missing-required-secrets: regression guard for the set-difference
#      logic at `missing = [s for s in required if s not in present]`.
#   2. gh-CLI-not-installed (returncode 127): the install-hint branch.
# ---------------------------------------------------------------------------


def test_github_secrets_missing_fails(tmp_path: Path, monkeypatch):
    """Pre-tick the github-secrets-populated C1 confirmation box and stub
    `gh secret list` to return ONLY CLOUDFLARE_API_TOKEN. The probe must
    fail and name the missing CLOUDFLARE_ACCOUNT_ID secret so the user
    knows exactly which one to add."""
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "slug")
    # Pre-tick the github-secrets-populated confirmation so the probe runs
    # (it is category C1; needs-confirmation otherwise).
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] GitHub Secrets populated "
        "(id: cloudflare-pages.github-secrets-populated)\n"
        f"  Last confirmed: {_recent_iso()}\n",
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
            # _derive_gh_repo_slug runs first; stub the git remote call
            # so the probe pins --repo to the derived slug.
            (
                "git",
                "-C",
                str(tmp_path),
                "remote",
                "get-url",
                "origin",
            ): CommandResult(0, "https://github.com/test-org/test-repo.git\n", ""),
            (
                "gh",
                "secret",
                "list",
                "--json",
                "name",
                "--repo",
                "test-org/test-repo",
            ): CommandResult(
                0,
                json.dumps([{"name": "CLOUDFLARE_API_TOKEN"}]),
                "",
            ),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.github-secrets-populated"]
    assert res.status == "fail"
    assert "CLOUDFLARE_ACCOUNT_ID" in res.message
    assert "missing" in res.message.lower()


def test_github_secrets_gh_not_installed(tmp_path: Path, monkeypatch):
    """Pre-tick the github-secrets-populated C1 confirmation and stub
    `gh secret list` to return returncode=127 (gh CLI not on PATH). The
    probe must fail with a friendly install hint that names "GitHub CLI"
    and links to cli.github.com so the user can remediate."""
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "slug")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] GitHub Secrets populated "
        "(id: cloudflare-pages.github-secrets-populated)\n"
        f"  Last confirmed: {_recent_iso()}\n",
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
            (
                "git",
                "-C",
                str(tmp_path),
                "remote",
                "get-url",
                "origin",
            ): CommandResult(0, "https://github.com/test-org/test-repo.git\n", ""),
            (
                "gh",
                "secret",
                "list",
                "--json",
                "name",
                "--repo",
                "test-org/test-repo",
            ): CommandResult(returncode=127, stdout="", stderr="FileNotFoundError"),
        },
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.github-secrets-populated"]
    assert res.status == "fail"
    assert "GitHub CLI" in res.message
    assert "cli.github.com" in res.message


# ---------------------------------------------------------------------------
# PreflightConfigError variant coverage (BL todo 14).
#
# Six distinct validation branches share one happy-path test today. The
# following tests exercise the remaining branches so a future profile
# typo (e.g., `categry:` instead of `category:`) cannot ship silently.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config_text,expected_match",
    [
        # 1. providers not a list of strings.
        ("providers: not-a-list\n", "list of profile-name strings"),
        # 2. overrides not a mapping (with otherwise-valid providers).
        (
            "providers:\n  - spec-completeness\noverrides: not-a-mapping\n",
            "mapping of item-id",
        ),
        # 3. config root not a mapping (top-level list).
        ("- providers\n- spec-completeness\n", "root must be a mapping"),
    ],
)
def test_load_preflight_config_validation_errors(
    tmp_path: Path, config_text: str, expected_match: str
):
    """Each malformed `.launchpad/preflight.config.yaml` shape must surface
    as PreflightConfigError with a message naming the offending field, so
    the user can fix the file without spelunking through the loader."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(config_text, encoding="utf-8")
    with pytest.raises(PreflightConfigError, match=expected_match):
        load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)


def test_load_preflight_config_duplicate_item_id_across_profiles(tmp_path: Path):
    """When two profiles each define a check with the same item_id, the
    loader must refuse with a `duplicate check id` message. Checklist
    parsing is item_id-keyed; duplicates would collide silently."""
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    profile_body = (
        "checks:\n"
        "  - id: shared.item\n"
        "    category: A\n"
        "    title: Shared item\n"
        "    setup_hint: |\n"
        "      Resolve the duplicate.\n"
    )
    (profile_dir / "profile-a.yaml").write_text(profile_body, encoding="utf-8")
    (profile_dir / "profile-b.yaml").write_text(profile_body, encoding="utf-8")
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - profile-a\n  - profile-b\n", encoding="utf-8")
    with pytest.raises(PreflightConfigError, match="duplicate check id"):
        load_preflight_config(tmp_path, profile_dir=profile_dir)


def test_load_preflight_config_invalid_category_enum(tmp_path: Path):
    """A profile with `category: D` (outside the {A, B, C1, C2} enum)
    must be refused at load time so a typo can never reach the dispatch
    switch."""
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "bad-category.yaml").write_text(
        "checks:\n"
        "  - id: bad-category.item\n"
        "    category: D\n"
        "    title: Bad category\n"
        "    setup_hint: |\n"
        "      Pick A, B, C1, or C2.\n",
        encoding="utf-8",
    )
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - bad-category\n", encoding="utf-8")
    with pytest.raises(PreflightConfigError, match="category 'D' not in"):
        load_preflight_config(tmp_path, profile_dir=profile_dir)


def test_load_preflight_config_check_missing_required_field(tmp_path: Path):
    """A profile check that omits a required field (`id`, `category`,
    `title`, or `setup_hint`) must be refused at load time with a message
    that names the missing field."""
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "missing-id.yaml").write_text(
        "checks:\n"
        "  - category: A\n"
        "    title: Missing id field\n"
        "    setup_hint: |\n"
        "      Add an `id:` field.\n",
        encoding="utf-8",
    )
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - missing-id\n", encoding="utf-8")
    with pytest.raises(PreflightConfigError, match="missing required field 'id'"):
        load_preflight_config(tmp_path, profile_dir=profile_dir)


# ---------------------------------------------------------------------------
# parse_checklist tolerance contract (todo-18, P2).
#
# `parse_checklist` advertises (lp_preflight.py:442-444) that missing files
# yield `{}`, malformed lines are skipped silently, and `Last confirmed:
# never` maps to `None`. These three tests lock that contract so a
# corrupted user-edited checklist can never crash `run_preflight`.
# ---------------------------------------------------------------------------


def test_parse_checklist_missing_file_returns_empty_dict(tmp_path: Path):
    """A path that does not exist must return an empty dict rather than
    raising. The engine then treats every check as unconfirmed, which is
    the safe-by-default behaviour."""
    result = parse_checklist(tmp_path / "no-such-file.md")
    assert result == {}


def test_parse_checklist_treats_never_as_none(tmp_path: Path):
    """When a checklist item carries `Last confirmed: never`, the parser
    must coerce the timestamp to `None` so the staleness check treats the
    item as never-confirmed rather than parsing 'never' as an ISO date."""
    checklist = tmp_path / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Foo (id: spec.foo)\n  Last confirmed: never\n",
        encoding="utf-8",
    )
    result = parse_checklist(checklist)
    assert result["spec.foo"].last_confirmed is None


def test_parse_checklist_skips_malformed_lines(tmp_path: Path):
    """A checklist with leading garbage, a non-checkbox dash line, and
    trailing garbage interleaved with a single valid checkbox line must
    still parse the valid item correctly. Malformed lines are skipped
    silently per the documented tolerance contract."""
    checklist = tmp_path / "preflight-checklist.md"
    checklist.write_text(
        "garbage line\n"
        "- not-a-checkbox\n"
        "- [x] Valid (id: spec.valid)\n"
        "  Last confirmed: 2026-05-17T00:00:00Z\n"
        "trailing garbage\n",
        encoding="utf-8",
    )
    result = parse_checklist(checklist)
    assert result["spec.valid"].confirmed is True
    assert result["spec.valid"].last_confirmed == "2026-05-17T00:00:00Z"


# ---------------------------------------------------------------------------
# Round-2 Codex review fixes: empty-providers refusal, override.args merge,
# gh --repo pin, malformed-override raise.
# ---------------------------------------------------------------------------


def test_empty_providers_list_refuses(tmp_path: Path):
    """Refuse `providers: []` at config-load time. An empty providers list
    would vacuously pass the gate with zero checks; the user almost
    certainly does NOT want that (they either declare profiles or delete
    the config file entirely). Codex round-2 P1."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers: []\n", encoding="utf-8")
    with pytest.raises(PreflightConfigError, match="empty"):
        load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)


def test_missing_providers_key_refuses(tmp_path: Path):
    """Refuse a config file with NO `providers:` key at all. Distinct
    failure mode from empty-list (a missing key is a typo or template
    fragment; an empty list is intentional)."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("overrides: {}\n", encoding="utf-8")
    with pytest.raises(PreflightConfigError, match="required"):
        load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)


def test_override_args_merge_with_profile_args(tmp_path: Path):
    """`overrides.<item>.args` MUST merge into the CheckDefinition.args
    map. Multiple profiles document this contract (namecheap-dns.yaml
    `apex-resolves-via-cname`, cloudflare-dns.yaml `apex-resolves-...`,
    spec-completeness.yaml `changelog-has-version-entry`). Codex round-2 P1."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "providers:\n"
        "  - namecheap-dns\n"
        "overrides:\n"
        "  namecheap-dns.apex-resolves-via-cname:\n"
        "    args:\n"
        "      domain: example.test\n"
        "      expected_suffix: .pages.dev\n",
        encoding="utf-8",
    )
    checks, _ = load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)
    by_id = {c.item_id: c for c in checks}
    check = by_id["namecheap-dns.apex-resolves-via-cname"]
    # Profile's domain_env arg should survive...
    assert check.args.get("domain_env") == "PREFLIGHT_DOMAIN"
    # ...AND the override's args should be merged in.
    assert check.args.get("domain") == "example.test"
    assert check.args.get("expected_suffix") == ".pages.dev"


def test_malformed_override_value_raises(tmp_path: Path):
    """A non-mapping override value (e.g., a string or a list) MUST raise
    PreflightConfigError rather than be silently dropped. Codex round-2 P2."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "providers:\n  - spec-completeness\n"
        "overrides:\n"
        '  spec-completeness.changelog-has-version-entry: "not-a-dict"\n',
        encoding="utf-8",
    )
    with pytest.raises(PreflightConfigError, match="must be a mapping"):
        load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)


def test_github_secrets_pins_repo_from_origin(tmp_path: Path, monkeypatch):
    """The github-secrets probe MUST derive the repo slug from
    `git remote get-url origin` (rooted in --repo-root, not cwd) and pass
    `--repo <slug>` to `gh secret list`. Codex round-2 P1."""
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "slug")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] GitHub Secrets (id: cloudflare-pages.github-secrets-populated)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    captured_commands: list[list[str]] = []

    def _capture_run(args: list[str]) -> CommandResult:
        captured_commands.append(args)
        if args[:4] == ["git", "-C", str(tmp_path), "remote"]:
            return CommandResult(0, "git@github.com:org-via-ssh/repo-via-ssh.git\n", "")
        if args[:3] == ["gh", "secret", "list"]:
            return CommandResult(
                0,
                json.dumps(
                    [
                        {"name": "CLOUDFLARE_API_TOKEN"},
                        {"name": "CLOUDFLARE_ACCOUNT_ID"},
                    ]
                ),
                "",
            )
        raise AssertionError(f"unexpected run_command: {args}")

    clients = ProbeClients(
        http_get=lambda url, headers: HttpResponse(
            200, json.dumps({"success": True, "result": {"status": "active"}})
        ),
        run_command=_capture_run,
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    assert by_id["cloudflare-pages.github-secrets-populated"].status == "pass"
    # Find the gh call and verify --repo is pinned to the SSH-form slug.
    gh_calls = [c for c in captured_commands if c[:3] == ["gh", "secret", "list"]]
    assert len(gh_calls) == 1
    assert "--repo" in gh_calls[0]
    repo_idx = gh_calls[0].index("--repo")
    assert gh_calls[0][repo_idx + 1] == "org-via-ssh/repo-via-ssh"


# ---------------------------------------------------------------------------
# Round-2 Codex / Greptile review fixes: section-spec lifecycle, gh
# fail-closed, Vercel teamId, malformed check guard, regex error catch,
# Cloudflare IP range completeness.
# ---------------------------------------------------------------------------


def test_section_specs_accepts_reviewed_and_built_statuses(tmp_path: Path):
    """Sections in the lifecycle ahead of `approved` (reviewed, built)
    MUST count as ship-ready. The probe previously required EXACTLY
    `approved`, which would block /lp-ship recovery-path invocations
    after a successful /lp-build advance to `reviewed` or `built`.
    Codex round-2 P1."""
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [v1.0.0]\n", encoding="utf-8")
    sections = tmp_path / "docs" / "tasks" / "sections"
    sections.mkdir(parents=True)
    (sections / "hero.md").write_text("---\nstatus: reviewed\n---\n", encoding="utf-8")
    (sections / "pricing.md").write_text("---\nstatus: built\n---\n", encoding="utf-8")
    (sections / "faq.md").write_text("---\nstatus: approved\n---\n", encoding="utf-8")
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
    assert by_id["spec-completeness.section-specs-approved"].status == "pass"


def test_section_specs_rejects_pre_approval_statuses(tmp_path: Path):
    """Statuses before `approved` (shaped, designed, planned, hardened)
    are NOT ship-ready and must fail. Locks the closed-enum invariant."""
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
    (sections / "draft.md").write_text("---\nstatus: planned\n---\n", encoding="utf-8")
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
    assert "planned" in res.message


def test_github_secrets_fails_closed_when_slug_not_derivable(
    tmp_path: Path, monkeypatch
):
    """When the git remote is missing OR not a github.com URL, the probe
    MUST fail-closed rather than fall back to gh's ambient cwd inference.
    Codex round-2 P1."""
    _make_repo(tmp_path, ["cloudflare-pages"])
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "slug")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] GitHub Secrets (id: cloudflare-pages.github-secrets-populated)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )

    def _run(args: list[str]) -> CommandResult:
        if args[:4] == ["git", "-C", str(tmp_path), "remote"]:
            # Simulate "no origin remote" via non-zero exit
            return CommandResult(128, "", "fatal: No such remote 'origin'\n")
        raise AssertionError(f"gh secret list should not run; got {args}")

    clients = ProbeClients(
        http_get=lambda url, headers: HttpResponse(
            200, json.dumps({"success": True, "result": {"status": "active"}})
        ),
        run_command=_run,
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-pages.github-secrets-populated"]
    assert res.status == "fail"
    assert "cannot derive" in res.message
    assert "args.repo" in res.message


def test_github_secrets_honors_args_repo_override(tmp_path: Path, monkeypatch):
    """When `args.repo: <owner>/<name>` is set in overrides, the probe
    skips slug derivation and uses the explicit override. Documented
    fail-closed escape hatch."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        "providers:\n  - cloudflare-pages\n"
        "overrides:\n"
        "  cloudflare-pages.github-secrets-populated:\n"
        "    args:\n"
        "      repo: explicit-org/explicit-repo\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "ok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_PAGES_PROJECT_SLUG", "slug")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] GitHub Secrets (id: cloudflare-pages.github-secrets-populated)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    captured: list[list[str]] = []

    def _run(args: list[str]) -> CommandResult:
        captured.append(args)
        if args[:3] == ["gh", "secret", "list"]:
            return CommandResult(
                0,
                json.dumps(
                    [
                        {"name": "CLOUDFLARE_API_TOKEN"},
                        {"name": "CLOUDFLARE_ACCOUNT_ID"},
                    ]
                ),
                "",
            )
        raise AssertionError(f"unexpected run_command: {args}")

    clients = ProbeClients(
        http_get=lambda url, headers: HttpResponse(
            200, json.dumps({"success": True, "result": {"status": "active"}})
        ),
        run_command=_run,
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    assert by_id["cloudflare-pages.github-secrets-populated"].status == "pass"
    gh_calls = [c for c in captured if c[:3] == ["gh", "secret", "list"]]
    assert len(gh_calls) == 1
    idx = gh_calls[0].index("--repo")
    assert gh_calls[0][idx + 1] == "explicit-org/explicit-repo"
    # The git remote get-url should NOT have been called when args.repo
    # is explicit (avoids spurious subprocess).
    assert not any(c[:2] == ["git", "-C"] for c in captured)


def test_vercel_project_pins_teamid_when_org_env_set(tmp_path: Path, monkeypatch):
    """When VERCEL_ORG_ID is exported, the project-exists probe MUST
    append `?teamId=<org>` so team-owned projects verify correctly.
    Codex round-2 P2."""
    _make_repo(tmp_path, ["vercel"])
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    monkeypatch.setenv("VERCEL_PROJECT_ID", "prj_abc")
    monkeypatch.setenv("VERCEL_ORG_ID", "team_xyz")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Project (id: vercel.project-exists)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    captured_urls: list[str] = []

    def _http(url: str, headers: dict[str, str]) -> HttpResponse:
        captured_urls.append(url)
        return HttpResponse(200, "{}")

    clients = ProbeClients(
        http_get=_http,
        run_command=lambda args: CommandResult(0, "[]", ""),
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    assert by_id["vercel.project-exists"].status == "pass"
    project_urls = [u for u in captured_urls if "/v9/projects/" in u]
    assert len(project_urls) == 1
    assert "teamId=team_xyz" in project_urls[0]


def test_malformed_check_entry_raises_config_error(tmp_path: Path):
    """A profile with `checks: [1]` or `checks: ["foo"]` (non-mapping
    entries) MUST raise PreflightConfigError at load time instead of
    propagating an unhandled TypeError. Codex round-2 P2."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - bad-profile\n", encoding="utf-8")
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "bad-profile.yaml").write_text(
        "name: bad-profile\nchecks:\n  - 1\n  - non-dict-string\n",
        encoding="utf-8",
    )
    with pytest.raises(PreflightConfigError, match="must be a mapping"):
        load_preflight_config(tmp_path, profile_dir=profile_dir)


def test_file_contains_catches_invalid_regex(tmp_path: Path):
    """The file-contains probe MUST catch re.error from a malformed
    regex pattern and return a clean _fail message rather than raising.
    Greptile round-2 P2."""
    target = tmp_path / "sample.txt"
    target.write_text("hello world\n", encoding="utf-8")
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - bad-regex\n", encoding="utf-8")
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "bad-regex.yaml").write_text(
        "name: bad-regex\n"
        "checks:\n"
        "  - id: bad-regex.invalid-pattern\n"
        "    category: A\n"
        "    title: Smoke check with bad regex\n"
        "    setup_hint: |\n"
        "      not used\n"
        "    probe: file-contains\n"
        "    args:\n"
        "      path: sample.txt\n"
        "      pattern: '[unclosed'\n",
        encoding="utf-8",
    )
    clients = _make_clients()
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=profile_dir, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["bad-regex.invalid-pattern"]
    assert res.status == "fail"
    assert "invalid regex pattern" in res.message


def test_dns_cloudflare_accepts_full_104_block(tmp_path: Path, monkeypatch):
    """The cloudflare-DNS probe MUST cover 104.16.0.0/12 in full
    (104.16.* through 104.31.*), not just 3 prefixes. Greptile round-2
    P2: previous heuristic false-negatived on 104.19.* through
    104.31.*."""
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.test")
    chk = lp_preflight.CheckDefinition(
        item_id="test.dns-104-25",
        category="C1",
        title="DNS",
        setup_hint="",
        stale_window_days=30,
        probe="dns-resolves-to-cloudflare",
        args={"domain_env": "PREFLIGHT_DOMAIN"},
    )
    # Test 104.25.x.y (inside the /12 but outside the 3-prefix subset
    # the old heuristic covered).
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.test"): CommandResult(
                0, "104.25.42.7\n", ""
            ),
        }
    )
    res = lp_preflight._PROBE_REGISTRY["dns-resolves-to-cloudflare"](
        tmp_path, chk, clients
    )
    assert res.status == "pass"
    assert "104.25.42.7" in res.message


def test_dns_cloudflare_accepts_full_172_block(tmp_path: Path, monkeypatch):
    """Mirror of the /12 test for 172.64.0.0/13 (172.64.* through
    172.71.*). Pre-fix heuristic only covered 172.64.* and 172.67.*."""
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.test")
    chk = lp_preflight.CheckDefinition(
        item_id="test.dns-172-70",
        category="C1",
        title="DNS",
        setup_hint="",
        stale_window_days=30,
        probe="dns-resolves-to-cloudflare",
        args={"domain_env": "PREFLIGHT_DOMAIN"},
    )
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.test"): CommandResult(
                0, "172.70.5.5\n", ""
            ),
        }
    )
    res = lp_preflight._PROBE_REGISTRY["dns-resolves-to-cloudflare"](
        tmp_path, chk, clients
    )
    assert res.status == "pass"
    assert "172.70" in res.message


# ---------------------------------------------------------------------------
# Codex round-3 review fixes: plan-file glob exclusion, stale-retick clear,
# stale_window_days validation, path-traversal guard, provider name regex,
# expected_prefixes shape validation.
# ---------------------------------------------------------------------------


def test_section_specs_excludes_plan_md_files(tmp_path: Path):
    """`docs/tasks/sections/*-plan.md` files lack section-status frontmatter
    and must be excluded from the section-specs-approved scan. Codex
    round-3 P1: previously they false-failed as 'no status field'."""
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [v1.0.0]\n", encoding="utf-8")
    sections = tmp_path / "docs" / "tasks" / "sections"
    sections.mkdir(parents=True)
    (sections / "hero.md").write_text("---\nstatus: approved\n---\n", encoding="utf-8")
    # Plan file with NO status frontmatter; should be ignored by the probe.
    (sections / "hero-plan.md").write_text(
        "# Implementation plan for hero\n\nNo status frontmatter here.\n",
        encoding="utf-8",
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
    assert by_id["spec-completeness.section-specs-approved"].status == "pass"


def test_stale_render_clears_timestamp_so_retick_stamps_fresh(tmp_path: Path):
    """Round-trip: render a stale check (un-tick + last=`never`); user
    re-ticks; next run stamps fresh timestamp. Codex round-3 P1."""
    _make_repo(tmp_path, ["cloudflare-pages"])
    old_ts = (datetime.now(UTC) - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    # First run: stale -> render unticked + last="never"
    run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=True
    )
    rendered = checklist.read_text(encoding="utf-8")
    assert "Last confirmed: never" in rendered, (
        "stale render must clear the timestamp so re-tick is treated as "
        "a fresh confirmation event by the first-tick stamping branch"
    )


def test_malformed_stale_window_days_raises_config_error(tmp_path: Path):
    """`stale_window_days: soon` MUST raise PreflightConfigError (exit
    code 2) instead of propagating raw ValueError from int(). Codex
    round-3 P1."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - bad-window\n", encoding="utf-8")
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "bad-window.yaml").write_text(
        "name: bad-window\n"
        "checks:\n"
        "  - id: bad-window.invalid-stale\n"
        "    category: A\n"
        "    title: Bad window\n"
        "    setup_hint: |\n"
        "      irrelevant\n"
        "    stale_window_days: soon\n"
        "    probe: file-exists\n"
        "    args:\n"
        "      path: nope.md\n",
        encoding="utf-8",
    )
    with pytest.raises(PreflightConfigError, match="stale_window_days"):
        load_preflight_config(tmp_path, profile_dir=profile_dir)


def test_negative_stale_window_days_raises_config_error(tmp_path: Path):
    """Numeric but negative `stale_window_days: -5` also fails. Symmetric
    with the non-numeric branch."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - neg-window\n", encoding="utf-8")
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "neg-window.yaml").write_text(
        "name: neg-window\n"
        "checks:\n"
        "  - id: neg-window.invalid-stale\n"
        "    category: A\n"
        "    title: Bad window\n"
        "    setup_hint: |\n"
        "      irrelevant\n"
        "    stale_window_days: -5\n"
        "    probe: file-exists\n"
        "    args:\n"
        "      path: nope.md\n",
        encoding="utf-8",
    )
    with pytest.raises(PreflightConfigError, match="non-negative"):
        load_preflight_config(tmp_path, profile_dir=profile_dir)


def test_file_probe_path_traversal_refused(tmp_path: Path):
    """`args.path: ../../etc/passwd` MUST be refused by file-based probes
    via _resolve_under_root. Codex round-3 P2."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - escape\n", encoding="utf-8")
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    (profile_dir / "escape.yaml").write_text(
        "name: escape\n"
        "checks:\n"
        "  - id: escape.try-traversal\n"
        "    category: A\n"
        "    title: Try traversal\n"
        "    setup_hint: |\n"
        "      irrelevant\n"
        "    probe: file-exists\n"
        "    args:\n"
        "      path: ../../etc/passwd\n",
        encoding="utf-8",
    )
    clients = _make_clients()
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=profile_dir, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["escape.try-traversal"]
    assert res.status == "fail"
    assert "escapes repo root" in res.message


def test_provider_name_with_path_traversal_refused(tmp_path: Path):
    """Provider names with `../` must be refused before any file open.
    Codex round-3 P2."""
    cfg = tmp_path / ".launchpad" / "preflight.config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("providers:\n  - ../../etc/passwd\n", encoding="utf-8")
    with pytest.raises(PreflightConfigError, match=r"provider name"):
        load_preflight_config(tmp_path, profile_dir=PROFILE_DIR)


def test_expected_prefixes_string_refused(tmp_path: Path, monkeypatch):
    """A scalar string for `expected_prefixes` (instead of a list) MUST
    fail with an actionable message rather than iterate character-by-
    character. Codex round-3 P2."""
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.test")
    chk = lp_preflight.CheckDefinition(
        item_id="test.bad-prefixes",
        category="C1",
        title="DNS",
        setup_hint="",
        stale_window_days=30,
        probe="dns-resolves-via-cname",
        args={
            "domain_env": "PREFLIGHT_DOMAIN",
            "expected_prefixes": "104.16.",  # WRONG: should be a list
        },
    )
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.test"): CommandResult(0, "1.2.3.4\n", ""),
        }
    )
    res = lp_preflight._PROBE_REGISTRY["dns-resolves-via-cname"](tmp_path, chk, clients)
    assert res.status == "fail"
    assert "list of strings" in res.message


# ---------------------------------------------------------------------------
# Codex round-4 review fixes: section_glob validation, required_secrets
# list shape, args.repo owner/repo regex.
# ---------------------------------------------------------------------------


def test_section_glob_absolute_path_refused(tmp_path: Path, monkeypatch):
    """Absolute glob paths raise NotImplementedError from Path.glob. The
    probe must validate and return a clean fail. Codex round-4 P1."""
    chk = lp_preflight.CheckDefinition(
        item_id="test.absolute-glob",
        category="A",
        title="abs glob",
        setup_hint="",
        stale_window_days=30,
        probe="section-specs-approved",
        args={"section_glob": "/etc/*.md"},
    )
    res = lp_preflight._PROBE_REGISTRY["section-specs-approved"](
        tmp_path, chk, _make_clients()
    )
    assert res.status == "fail"
    assert "repo-root-relative" in res.message


def test_section_glob_traversal_refused(tmp_path: Path, monkeypatch):
    """`../` segments in section_glob must be refused before globbing."""
    chk = lp_preflight.CheckDefinition(
        item_id="test.traversal-glob",
        category="A",
        title="traversal",
        setup_hint="",
        stale_window_days=30,
        probe="section-specs-approved",
        args={"section_glob": "../../etc/*.md"},
    )
    res = lp_preflight._PROBE_REGISTRY["section-specs-approved"](
        tmp_path, chk, _make_clients()
    )
    assert res.status == "fail"
    assert "repo-root-relative" in res.message


def test_required_secrets_string_refused(tmp_path: Path, monkeypatch):
    """`required_secrets: VERCEL_TOKEN` (scalar instead of list) must be
    refused rather than iterated char-by-char. Codex round-4 P2."""
    chk = lp_preflight.CheckDefinition(
        item_id="test.bad-required-secrets",
        category="C1",
        title="bad shape",
        setup_hint="",
        stale_window_days=30,
        probe="github-secrets-populated",
        args={"required_secrets": "VERCEL_TOKEN"},
    )
    res = lp_preflight._PROBE_REGISTRY["github-secrets-populated"](
        tmp_path, chk, _make_clients()
    )
    assert res.status == "fail"
    assert "list of secret-name strings" in res.message


def test_args_repo_with_invalid_shape_refused(tmp_path: Path, monkeypatch):
    """`args.repo: just-the-name` (missing `/`) must be refused before
    being passed to gh, so the cwd-ambient fallback can't sneak through.
    Codex round-4 P2."""
    chk = lp_preflight.CheckDefinition(
        item_id="test.bad-args-repo",
        category="C1",
        title="bad args.repo",
        setup_hint="",
        stale_window_days=30,
        probe="github-secrets-populated",
        args={
            "required_secrets": ["FOO"],
            "repo": "just-the-name-no-slash",
        },
    )
    res = lp_preflight._PROBE_REGISTRY["github-secrets-populated"](
        tmp_path, chk, _make_clients()
    )
    assert res.status == "fail"
    assert "<owner>/<repo>" in res.message


# ---------------------------------------------------------------------------
# Codex round-5 P1-A: target-scoped section-specs-approved via --section.
# ---------------------------------------------------------------------------


def test_target_section_scopes_check_to_one_file_passing(tmp_path: Path):
    """When `run_preflight` is called with `target_section=<path>`, the
    section-specs-approved probe must inspect ONLY that file. A second
    section spec at status=shaped must NOT cause a fail.

    This is the Codex round-5 P1-A acceptance test: /lp-build <approved>
    must not be false-blocked by unrelated in-flight sections.
    """
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [v1.0.0]\n", encoding="utf-8")
    sections = tmp_path / "docs" / "tasks" / "sections"
    sections.mkdir(parents=True)
    (sections / "approved-target.md").write_text(
        "---\nstatus: approved\n---\n", encoding="utf-8"
    )
    # In-flight work on a different section. Without --section scoping this
    # would fail the gate.
    (sections / "in-flight.md").write_text(
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
        tmp_path,
        clients=clients,
        profile_dir=PROFILE_DIR,
        write_checklist=False,
        target_section="docs/tasks/sections/approved-target.md",
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["spec-completeness.section-specs-approved"]
    assert res.status == "pass"


def test_target_section_fails_when_target_itself_not_approved(tmp_path: Path):
    """If the targeted section is itself not ship-ready, the probe must
    fail even when other unrelated sections are approved."""
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [v1.0.0]\n", encoding="utf-8")
    sections = tmp_path / "docs" / "tasks" / "sections"
    sections.mkdir(parents=True)
    (sections / "approved-sibling.md").write_text(
        "---\nstatus: approved\n---\n", encoding="utf-8"
    )
    (sections / "not-ready-target.md").write_text(
        "---\nstatus: planned\n---\n", encoding="utf-8"
    )
    clients = _make_clients(
        command_responses={
            ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                0, "", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path,
        clients=clients,
        profile_dir=PROFILE_DIR,
        write_checklist=False,
        target_section="docs/tasks/sections/not-ready-target.md",
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["spec-completeness.section-specs-approved"]
    assert res.status == "fail"
    assert "planned" in res.message


def test_target_section_rejects_traversal_path(tmp_path: Path):
    """`target_section` pointing outside repo_root must be refused."""
    chk = lp_preflight.CheckDefinition(
        item_id="test.target-traversal",
        category="A",
        title="traversal",
        setup_hint="",
        stale_window_days=30,
        probe="section-specs-approved",
        args={"section_path": "../../etc/passwd"},
    )
    res = lp_preflight._PROBE_REGISTRY["section-specs-approved"](
        tmp_path, chk, _make_clients()
    )
    assert res.status == "fail"
    assert "does not resolve under" in res.message


def test_target_section_rejects_non_file_path(tmp_path: Path):
    """`target_section` pointing at a directory or missing file must fail."""
    (tmp_path / "docs" / "tasks" / "sections").mkdir(parents=True)
    chk = lp_preflight.CheckDefinition(
        item_id="test.target-not-file",
        category="A",
        title="not file",
        setup_hint="",
        stale_window_days=30,
        probe="section-specs-approved",
        args={"section_path": "docs/tasks/sections"},
    )
    res = lp_preflight._PROBE_REGISTRY["section-specs-approved"](
        tmp_path, chk, _make_clients()
    )
    assert res.status == "fail"
    assert "is not a file" in res.message


def test_cli_section_flag_threads_through_to_probe(
    tmp_path: Path, monkeypatch, capsys
):
    """Smoke-test the --section CLI flag: invoking `main(['--repo-root',
    tmp, '--section', 'docs/tasks/sections/target.md'])` must succeed when
    the target is approved even if a sibling is `shaped`.
    """
    _make_repo(tmp_path, ["spec-completeness"])
    (tmp_path / ".launchpad" / "autonomous-ack.md").write_text(
        "ack\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "architecture" / "PRD.md").write_text(
        "# PRD\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("## [v1.0.0]\n", encoding="utf-8")
    sections = tmp_path / "docs" / "tasks" / "sections"
    sections.mkdir(parents=True)
    (sections / "target.md").write_text(
        "---\nstatus: approved\n---\n", encoding="utf-8"
    )
    (sections / "sibling.md").write_text(
        "---\nstatus: shaped\n---\n", encoding="utf-8"
    )

    # Patch default_clients so the CLI invocation uses a hermetic stub
    # rather than touching the real shell. The smoke test verifies the
    # flag plumbs; the section-specs-approved probe is the only one that
    # reads it.
    def _fake_default_clients() -> lp_preflight.ProbeClients:
        return _make_clients(
            command_responses={
                ("git", "-C", str(tmp_path), "status", "--porcelain"): CommandResult(
                    0, "", ""
                ),
            }
        )

    monkeypatch.setattr(lp_preflight, "default_clients", _fake_default_clients)
    exit_code = lp_preflight.main(
        [
            "--repo-root",
            str(tmp_path),
            "--no-write-checklist",
            "--section",
            "docs/tasks/sections/target.md",
        ]
    )
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Codex round-5 P2: ipaddress.ip_address() prevents CNAME false-positives.
# ---------------------------------------------------------------------------


def test_dns_cloudflare_rejects_numeric_prefix_cname(tmp_path: Path, monkeypatch):
    """A CNAME hostname literally starting with `104.16.` (e.g.,
    `104.16.cdn.example.com.`) must NOT pass the Cloudflare edge-range
    check, because raw-string `startswith` would false-positive here.
    The `ipaddress.IPv4Address` parser rejects it as not an IPv4, so
    only the suffix list is consulted, and the hostname does not end
    with `.cloudflare.com` or `.pages.dev`.
    """
    _make_repo(tmp_path, ["cloudflare-dns"])
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.com")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Custom domain resolves to Cloudflare "
        "(id: cloudflare-dns.apex-resolves-to-cloudflare)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.com"): CommandResult(
                0, "104.16.cdn.example.com.\n", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-dns.apex-resolves-to-cloudflare"]
    assert res.status == "fail"
    assert "104.16.cdn.example.com" in res.message


def test_dns_cloudflare_accepts_172_64_through_172_71(
    tmp_path: Path, monkeypatch
):
    """Confirm the full /13 block (172.64.0.0 to 172.71.255.255) parses
    via ipaddress.IPv4Network. 172.71.255.255 is the last address in the
    /13 and must pass."""
    _make_repo(tmp_path, ["cloudflare-dns"])
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.com")
    checklist = tmp_path / ".launchpad" / "preflight-checklist.md"
    checklist.write_text(
        "- [x] Custom domain resolves to Cloudflare "
        "(id: cloudflare-dns.apex-resolves-to-cloudflare)\n"
        f"  Last confirmed: {_recent_iso()}\n",
        encoding="utf-8",
    )
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.com"): CommandResult(
                0, "172.71.255.255\n", ""
            ),
        }
    )
    report = run_preflight(
        tmp_path, clients=clients, profile_dir=PROFILE_DIR, write_checklist=False
    )
    by_id = {r.item_id: r for r in report.results}
    res = by_id["cloudflare-dns.apex-resolves-to-cloudflare"]
    assert res.status == "pass"
    assert "172.71.255.255" in res.message


def test_dns_cname_probe_does_not_treat_hostname_as_ip_prefix(
    tmp_path: Path, monkeypatch
):
    """The generic dns-resolves-via-cname probe must not match a CNAME
    hostname against `expected_prefixes` (which are IP-prefix strings).
    A hostname starting with `104.16.` must FAIL when the only
    configured matcher is the IP prefix, because hostnames cannot be
    classified as IP addresses.
    """
    monkeypatch.setenv("PREFLIGHT_DOMAIN", "example.com")
    clients = _make_clients(
        command_responses={
            ("dig", "+short", "--", "example.com"): CommandResult(
                0, "104.16.evil.attacker.example.\n", ""
            ),
        }
    )
    chk = lp_preflight.CheckDefinition(
        item_id="test.cname-numeric-prefix",
        category="C1",
        title="cname numeric prefix",
        setup_hint="",
        stale_window_days=365,
        probe="dns-resolves-via-cname",
        args={
            "domain_env": "PREFLIGHT_DOMAIN",
            "expected_prefixes": ["104.16."],
        },
    )
    probe = lp_preflight._PROBE_REGISTRY["dns-resolves-via-cname"]
    result = probe(tmp_path, chk, clients)
    assert result.status == "fail"
    assert "104.16.evil.attacker.example" in result.message
