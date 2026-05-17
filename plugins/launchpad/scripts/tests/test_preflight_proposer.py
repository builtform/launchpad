"""Tests for ``lp_bootstrap.preflight_proposer`` (BL-370).

Covers deploy-target detection signals, profile proposal, atomic writes,
overwrite refusal, opt-out marker, and the CLI surface invoked by the
``/lp-bootstrap`` slash command.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap.preflight_proposer import (  # noqa: E402
    KNOWN_PROFILES,
    config_present,
    detect_deploy_providers,
    main,
    preflight_config_path,
    proposed_profiles,
    skipped_marker_path,
    skipped_marker_present,
    summarize,
    write_preflight_config,
    write_skipped_marker,
)

# --- detect_deploy_providers ------------------------------------------------


def test_detect_cloudflare_from_wrangler_jsonc(tmp_path: Path) -> None:
    (tmp_path / "wrangler.jsonc").write_text(
        '{"name": "site", "pages_build_output_dir": "dist"}\n',
        encoding="utf-8",
    )
    assert detect_deploy_providers(tmp_path) == ["cloudflare-pages"]


def test_detect_cloudflare_from_wrangler_toml(tmp_path: Path) -> None:
    (tmp_path / "wrangler.toml").write_text(
        'name = "site"\npages_build_output_dir = "dist"\n',
        encoding="utf-8",
    )
    assert detect_deploy_providers(tmp_path) == ["cloudflare-pages"]


def test_detect_cloudflare_from_github_workflow(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "deploy.yml").write_text(
        "jobs:\n  deploy:\n    steps:\n      - uses: cloudflare/pages-action@v1\n",
        encoding="utf-8",
    )
    assert detect_deploy_providers(tmp_path) == ["cloudflare-pages"]


def test_detect_vercel_from_vercel_json(tmp_path: Path) -> None:
    (tmp_path / "vercel.json").write_text("{}\n", encoding="utf-8")
    assert detect_deploy_providers(tmp_path) == ["vercel"]


def test_detect_vercel_from_dotvercel_project_json(tmp_path: Path) -> None:
    dotvercel = tmp_path / ".vercel"
    dotvercel.mkdir()
    (dotvercel / "project.json").write_text('{"projectId": "abc"}\n', encoding="utf-8")
    assert detect_deploy_providers(tmp_path) == ["vercel"]


def test_detect_netlify_from_netlify_toml(tmp_path: Path) -> None:
    (tmp_path / "netlify.toml").write_text(
        '[build]\ncommand = "build"\n', encoding="utf-8"
    )
    assert detect_deploy_providers(tmp_path) == ["netlify"]


def test_detect_none_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    assert detect_deploy_providers(tmp_path) == []


def test_detect_skips_wrangler_without_pages_marker(tmp_path: Path) -> None:
    # BL-370 v2 (PR #76 Codex P2): a Workers-only wrangler config (no
    # `pages_build_output_dir` key) must NOT be classified as
    # cloudflare-pages. Generating a Pages preflight config for a
    # Workers project would block /lp-build on irrelevant probes.
    (tmp_path / "wrangler.toml").write_text(
        'name = "worker-only"\nmain = "src/index.ts"\n', encoding="utf-8"
    )
    assert detect_deploy_providers(tmp_path) == []


def test_detect_skips_wrangler_action_without_pages_action(tmp_path: Path) -> None:
    # BL-370 v2 (PR #76 Codex P2): `cloudflare/wrangler-action` is shared
    # by Pages and Workers; only `cloudflare/pages-action` classifies
    # as Pages.
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "deploy.yml").write_text(
        "jobs:\n  deploy:\n    steps:\n      - uses: cloudflare/wrangler-action@v3\n",
        encoding="utf-8",
    )
    assert detect_deploy_providers(tmp_path) == []


def test_detect_multi_target_returns_all(tmp_path: Path) -> None:
    (tmp_path / "wrangler.jsonc").write_text(
        '{"name": "site", "pages_build_output_dir": "dist"}\n',
        encoding="utf-8",
    )
    (tmp_path / "vercel.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "netlify.toml").write_text("[build]\n", encoding="utf-8")
    assert detect_deploy_providers(tmp_path) == [
        "cloudflare-pages",
        "netlify",
        "vercel",
    ]


def test_detect_ignores_non_yaml_workflow_files(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    # A README inside the workflows dir mentions the action; must NOT trigger.
    (workflows / "README.md").write_text(
        "We use cloudflare/pages-action.\n", encoding="utf-8"
    )
    assert detect_deploy_providers(tmp_path) == []


def test_detect_uppercase_yaml_workflow_extension(tmp_path: Path) -> None:
    # BL-370 v2 (PR #76 testing-reviewer P2-6): the suffix check uses
    # `.lower()`; pin the case-insensitive contract.
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "deploy.YAML").write_text(
        "jobs:\n  deploy:\n    steps:\n      - uses: cloudflare/pages-action@v1\n",
        encoding="utf-8",
    )
    assert detect_deploy_providers(tmp_path) == ["cloudflare-pages"]


def test_detect_rejects_symlinked_workflow(tmp_path: Path) -> None:
    # BL-370 v2 (PR #76 security-auditor F2): symlinks in the workflows
    # dir are rejected so a symlink to /dev/zero or a multi-GB log
    # cannot hang the bootstrap step.
    import os as _os

    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    real = tmp_path / "real-workflow.yml"
    real.write_text(
        "jobs:\n  deploy:\n    steps:\n      - uses: cloudflare/pages-action@v1\n",
        encoding="utf-8",
    )
    link = workflows / "deploy.yml"
    _os.symlink(real, link)
    # Symlink rejection: the symlinked workflow contents must NOT register.
    assert detect_deploy_providers(tmp_path) == []


def test_detect_skips_oversized_workflow(tmp_path: Path) -> None:
    # BL-370 v2 (PR #76 security-auditor F2): a workflow file larger
    # than the 1 MB cap is skipped to prevent DoS.
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    big = workflows / "deploy.yml"
    # Pad past 1 MB; the marker still appears in the body so we
    # would otherwise classify as Pages without the cap.
    big.write_text(
        "# cloudflare/pages-action\n" + ("# pad\n" * 200_000), encoding="utf-8"
    )
    assert detect_deploy_providers(tmp_path) == []


# --- proposed_profiles ------------------------------------------------------


def test_proposed_profiles_always_includes_spec_completeness() -> None:
    # Empty detection -> no deploy target -> no `build-time-api-auth`
    # (BL-373 is opt-in-by-default ONLY when a deploy target is detected;
    # a fully greenfield project with no signals stays minimal).
    assert proposed_profiles([]) == ["spec-completeness"]


def test_proposed_profiles_auto_adds_cloudflare_dns() -> None:
    assert proposed_profiles(["cloudflare-pages"]) == [
        "build-time-api-auth",
        "cloudflare-dns",
        "cloudflare-pages",
        "spec-completeness",
    ]


def test_proposed_profiles_for_vercel_does_not_add_dns() -> None:
    # Vercel deploy detected -> BL-373 build-time-api-auth auto-adds but
    # cloudflare-dns does NOT (only attached to cloudflare-pages detection).
    assert proposed_profiles(["vercel"]) == [
        "build-time-api-auth",
        "spec-completeness",
        "vercel",
    ]


def test_proposed_profiles_filters_unknown_inputs() -> None:
    # Defensive: if a future caller feeds a profile we do not bundle yet,
    # it must be dropped rather than appearing in the YAML.
    out = proposed_profiles(["cloudflare-pages", "imaginary-cdn"])
    assert "imaginary-cdn" not in out
    assert set(out) <= KNOWN_PROFILES


def test_bl373_proposed_config_includes_build_time_api_auth_when_any_deploy_target_detected() -> None:
    """BL-373: when any deploy target is detected, the proposed starter
    config auto-includes `build-time-api-auth` so the GitHub/GitLab probes
    are opt-in-by-default for new projects. The probe is a no-op for
    projects that do not call rate-limited APIs at build time (returns
    PASS-with-skip-message), so the default-on posture is safe.
    """
    # Each deploy target gets the BL-373 profile auto-added.
    for target in ("cloudflare-pages", "vercel", "netlify"):
        out = proposed_profiles([target])
        assert "build-time-api-auth" in out, (
            f"BL-373 profile must be auto-added when {target!r} is detected; "
            f"got {out!r}"
        )


def test_bl373_not_added_when_no_deploy_target_detected() -> None:
    """The opt-in-by-default trigger is ANY deploy target. A project with
    no signals at all stays minimal (only `spec-completeness`)."""
    assert "build-time-api-auth" not in proposed_profiles([])


# --- write_preflight_config + write_skipped_marker --------------------------


def test_write_preflight_config_creates_yaml(tmp_path: Path) -> None:
    target = write_preflight_config(
        tmp_path, ["spec-completeness", "cloudflare-pages", "cloudflare-dns"]
    )
    assert target == preflight_config_path(tmp_path)
    body = target.read_text(encoding="utf-8")
    assert "providers:" in body
    assert "- cloudflare-pages" in body
    assert "- cloudflare-dns  # remove if no custom domain" in body
    assert body.startswith("# Generated by /lp-bootstrap on ")


def test_write_preflight_config_refuses_overwrite(tmp_path: Path) -> None:
    write_preflight_config(tmp_path, ["spec-completeness", "vercel"])
    with pytest.raises(FileExistsError):
        write_preflight_config(tmp_path, ["spec-completeness", "vercel"])


def test_write_preflight_config_rejects_empty_providers(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="providers list is empty"):
        write_preflight_config(tmp_path, [])


def test_write_preflight_config_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        write_preflight_config(tmp_path, ["spec-completeness", "not-a-profile"])


def test_write_skipped_marker_creates_file(tmp_path: Path) -> None:
    target = write_skipped_marker(tmp_path)
    assert target == skipped_marker_path(tmp_path)
    body = target.read_text(encoding="utf-8")
    assert "opted out" in body
    assert skipped_marker_present(tmp_path) is True


# --- summarize --------------------------------------------------------------


def test_summarize_no_signals(tmp_path: Path) -> None:
    summary = summarize(tmp_path)
    assert summary == {
        "detected": [],
        "proposed_profiles": ["spec-completeness"],
        "config_present": False,
        "skipped_marker_present": False,
    }


def test_summarize_signals_and_existing_config(tmp_path: Path) -> None:
    (tmp_path / "wrangler.jsonc").write_text(
        '{"name": "site", "pages_build_output_dir": "dist"}\n',
        encoding="utf-8",
    )
    write_preflight_config(
        tmp_path, ["spec-completeness", "cloudflare-pages", "cloudflare-dns"]
    )
    summary = summarize(tmp_path)
    assert summary["detected"] == ["cloudflare-pages"]
    assert summary["config_present"] is True
    assert summary["skipped_marker_present"] is False


def test_summarize_signals_and_skipped_marker(tmp_path: Path) -> None:
    (tmp_path / "vercel.json").write_text("{}\n", encoding="utf-8")
    write_skipped_marker(tmp_path)
    summary = summarize(tmp_path)
    assert summary["detected"] == ["vercel"]
    assert summary["config_present"] is False
    assert summary["skipped_marker_present"] is True


# --- CLI --------------------------------------------------------------------


def test_cli_json_emits_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "netlify.toml").write_text("[build]\n", encoding="utf-8")
    rc = main(["--cwd", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["detected"] == ["netlify"]
    assert "spec-completeness" in payload["proposed_profiles"]
    assert payload["config_present"] is False
    assert payload["skipped_marker_present"] is False


def test_cli_write_config_then_present(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(
        [
            "--cwd",
            str(tmp_path),
            "--write-config",
            "--providers",
            "spec-completeness,vercel",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("preflight.config.yaml")
    assert config_present(tmp_path) is True


def test_cli_write_config_requires_providers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--cwd", str(tmp_path), "--write-config"])
    assert rc == 64
    assert "requires --providers" in capsys.readouterr().err


def test_cli_write_config_refuses_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_preflight_config(tmp_path, ["spec-completeness", "vercel"])
    rc = main(
        [
            "--cwd",
            str(tmp_path),
            "--write-config",
            "--providers",
            "spec-completeness,vercel",
        ]
    )
    assert rc == 65
    assert "refusing to overwrite" in capsys.readouterr().err


def test_cli_write_skipped_creates_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--cwd", str(tmp_path), "--write-skipped"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("preflight.config.skipped")
    assert skipped_marker_present(tmp_path) is True


# --- BL-370 v2 (PR #76 pattern-finder P2): --repo-root flag parity ----------


def test_cli_repo_root_flag_matches_repo_convention(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # BL-370 v2 cycle-2 patch: mirror the BL-372 merger test that pins
    # the canonical `--repo-root` flag (consistent with the rest of the
    # LaunchPad CLI surface).
    rc = main(["--repo-root", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["detected"] == []


def test_cli_cwd_alias_still_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Compatibility alias for out-of-tree callers; the existing test
    # suite uses `--cwd` throughout so this also documents the contract
    # explicitly.
    rc = main(["--cwd", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["detected"] == []
