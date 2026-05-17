"""Tests for ``lp_bootstrap.claude_settings_merger`` (BL-372).

Covers the template-load contract, the merge rules (deep-merge dicts,
permission-list union without broadening, generic-list union, scalar
existing-wins), the ack-gated apply path, and the CLI surface invoked by
``/lp-bootstrap``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap.claude_settings_merger import (  # noqa: E402
    apply_merge,
    autonomous_ack_present,
    claude_settings_path,
    claude_settings_present,
    load_template,
    main,
    plan_merge,
    summarize,
)


def _seed_ack(repo_root: Path) -> None:
    target = repo_root / ".launchpad" / "autonomous-ack.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("acknowledged\n", encoding="utf-8")


def _write_existing_settings(repo_root: Path, payload: dict[str, object]) -> Path:
    target = claude_settings_path(repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


# --- template -----------------------------------------------------------------


def test_load_template_returns_permissions_allow_block() -> None:
    template = load_template()
    assert isinstance(template, dict)
    allow = template["permissions"]["allow"]
    assert "Skill" in allow
    assert "Bash" in allow
    # The template MUST NOT use the per-skill `Skill(...)` syntax (the
    # Context7-fetched docs only support tool-level entries; per-skill
    # granularity is not supported by Claude Code's permission model).
    assert all("Skill(" not in e for e in allow)


# --- plan_merge ---------------------------------------------------------------


def test_plan_merge_inserts_template_when_settings_absent(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    merged, existing, additions = plan_merge(tmp_path)
    assert existing == {}
    assert merged["permissions"]["allow"]
    assert "permissions" in additions  # top-level key added


def test_plan_merge_unions_into_existing_allow_list(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    _write_existing_settings(
        tmp_path,
        {"permissions": {"allow": ["Read", "Bash"]}},
    )
    merged, _, additions = plan_merge(tmp_path)
    allow = merged["permissions"]["allow"]
    # Existing entries preserved
    assert "Read" in allow and "Bash" in allow
    # Template additions appear
    assert "Skill" in allow
    assert "Monitor" in allow
    # Order preserved: existing entries come first
    assert allow.index("Read") < allow.index("Skill")
    # Additions list includes the new entries with dotted-path framing
    assert any("Skill" in entry for entry in additions)


def test_plan_merge_does_not_broaden_pinned_bash(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    _write_existing_settings(
        tmp_path,
        {"permissions": {"allow": ["Bash(git:*)"]}},
    )
    merged, _, _ = plan_merge(tmp_path)
    allow = merged["permissions"]["allow"]
    # User's tightened rule wins: bare "Bash" must NOT be added.
    assert "Bash" not in allow
    assert "Bash(git:*)" in allow
    # But other template entries still join.
    assert "Skill" in allow


def test_plan_merge_preserves_user_scalars(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    _write_existing_settings(
        tmp_path,
        {"model": "claude-sonnet-4-6", "permissions": {"allow": []}},
    )
    merged, _, _ = plan_merge(tmp_path)
    # Existing scalar must NOT be replaced.
    assert merged["model"] == "claude-sonnet-4-6"


def test_plan_merge_preserves_unrelated_user_dicts(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    _write_existing_settings(
        tmp_path,
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}},
    )
    merged, _, _ = plan_merge(tmp_path)
    assert merged["hooks"]["PreToolUse"][0]["matcher"] == "Bash"
    assert "permissions" in merged  # template still applied


def test_plan_merge_idempotent(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    apply_merge(tmp_path)  # first apply
    merged_2, _, additions_2 = plan_merge(tmp_path)
    assert additions_2 == []  # second pass: no changes
    # Re-applying must not duplicate entries.
    allow = merged_2["permissions"]["allow"]
    assert len(allow) == len(set(allow))


def test_plan_merge_rejects_existing_non_dict_root(tmp_path: Path) -> None:
    settings_path = claude_settings_path(tmp_path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text('["not", "a", "dict"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        plan_merge(tmp_path)


def test_plan_merge_rejects_invalid_json(tmp_path: Path) -> None:
    settings_path = claude_settings_path(tmp_path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{ broken json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        plan_merge(tmp_path)


# --- apply_merge --------------------------------------------------------------


def test_apply_merge_refuses_without_ack(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="autonomous-ack"):
        apply_merge(tmp_path)


def test_apply_merge_writes_atomically(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    target = apply_merge(tmp_path)
    assert target == claude_settings_path(tmp_path)
    body = json.loads(target.read_text(encoding="utf-8"))
    assert "Skill" in body["permissions"]["allow"]


def test_apply_merge_preserves_existing_customization(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    _write_existing_settings(
        tmp_path,
        {
            "permissions": {"allow": ["Bash(git:*)", "Read"], "deny": ["WebFetch"]},
            "model": "claude-haiku-4-5-20251001",
        },
    )
    apply_merge(tmp_path)
    body = json.loads(claude_settings_path(tmp_path).read_text(encoding="utf-8"))
    assert body["model"] == "claude-haiku-4-5-20251001"
    assert "Bash(git:*)" in body["permissions"]["allow"]
    assert "Bash" not in body["permissions"]["allow"]  # not broadened
    assert "WebFetch" in body["permissions"]["deny"]


# --- summarize ----------------------------------------------------------------


def test_summarize_no_ack(tmp_path: Path) -> None:
    summary = summarize(tmp_path)
    assert summary["ack_present"] is False
    assert summary["additions"] == []
    assert summary["already_satisfied"] is False


def test_summarize_ack_no_settings(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    summary = summarize(tmp_path)
    assert summary["ack_present"] is True
    assert summary["settings_present"] is False
    assert summary["additions"]  # non-empty: template adds everything


def test_summarize_already_satisfied_after_apply(tmp_path: Path) -> None:
    _seed_ack(tmp_path)
    apply_merge(tmp_path)
    summary = summarize(tmp_path)
    assert summary["already_satisfied"] is True
    assert summary["additions"] == []


# --- CLI ----------------------------------------------------------------------


def test_cli_json_emits_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_ack(tmp_path)
    rc = main(["--cwd", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ack_present"] is True
    assert payload["already_satisfied"] is False


def test_cli_apply_writes_settings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_ack(tmp_path)
    rc = main(["--cwd", str(tmp_path), "--apply"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("settings.json")
    assert claude_settings_present(tmp_path) is True
    assert autonomous_ack_present(tmp_path) is True


def test_cli_apply_refuses_without_ack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--cwd", str(tmp_path), "--apply"])
    assert rc == 65
    assert "autonomous-ack" in capsys.readouterr().err


def test_cli_human_output_when_no_ack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--cwd", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "autonomous-ack absent" in out


# --- BL-372 v2 (PR #76 review) test additions -------------------------------


def test_merger_does_not_contradict_user_deny(tmp_path: Path) -> None:
    # BL-372 v2 (PR #76 Codex P2): if user has `WebFetch` in `deny`,
    # the merger must NOT add `WebFetch` to `allow` from the template.
    from lp_bootstrap.claude_settings_merger import plan_merge as _plan_merge

    _seed_ack(tmp_path)
    _write_existing_settings(tmp_path, {"permissions": {"deny": ["WebFetch"]}})
    merged, _, _ = _plan_merge(tmp_path)
    allow = merged["permissions"]["allow"]
    deny = merged["permissions"]["deny"]
    assert "WebFetch" not in allow
    assert "WebFetch" in deny


def test_merger_honors_scoped_user_deny_against_bare_template_entry(
    tmp_path: Path,
) -> None:
    # Sibling-list cross-check uses bare-name prefix matching so a
    # scoped user rule (WebFetch(read:*)) suppresses the template's
    # bare WebFetch entry.
    from lp_bootstrap.claude_settings_merger import plan_merge as _plan_merge

    _seed_ack(tmp_path)
    _write_existing_settings(tmp_path, {"permissions": {"deny": ["WebFetch(read:*)"]}})
    merged, _, _ = _plan_merge(tmp_path)
    allow = merged["permissions"]["allow"]
    assert "WebFetch" not in allow
    assert "WebFetch(read:*)" in merged["permissions"]["deny"]


def test_permission_scope_rule_exact_match_only(tmp_path: Path) -> None:
    # BL-372 v2 (PR #76 Greptile P2 + testing-reviewer P2-5): the
    # do-not-broaden rule applies ONLY to top-level `permissions.<key>`
    # lists, not to any ancestor key ending in `permissions`. A nested
    # `customPermissions.allow` must merge as a generic list-union.
    from lp_bootstrap.claude_settings_merger import _merge_dicts as _md

    existing = {"customPermissions": {"allow": ["Bash(git:*)"]}}
    template = {"customPermissions": {"allow": ["Bash"]}}
    merged, _ = _md(existing, template)
    # Because `customPermissions` is NOT the canonical `permissions`
    # key, the do-not-broaden rule does NOT fire and the generic
    # exact-match union adds bare Bash.
    assert merged["customPermissions"]["allow"] == ["Bash(git:*)", "Bash"]


# --- BL-372 v2 (PR #76 Greptile P2): write-skipped opt-out marker -----------


def test_write_skipped_marker_creates_file(tmp_path: Path) -> None:
    from lp_bootstrap.claude_settings_merger import (
        skipped_marker_path,
        skipped_marker_present,
        write_skipped_marker,
    )

    target = write_skipped_marker(tmp_path)
    assert target == skipped_marker_path(tmp_path)
    assert skipped_marker_present(tmp_path) is True
    body = target.read_text(encoding="utf-8")
    assert "declined" in body


def test_summarize_short_circuits_on_skipped_marker(tmp_path: Path) -> None:
    from lp_bootstrap.claude_settings_merger import write_skipped_marker

    _seed_ack(tmp_path)
    write_skipped_marker(tmp_path)
    summary = summarize(tmp_path)
    assert summary["skipped_marker_present"] is True
    # When the user has opted out, the merger must NOT compute
    # additions (no re-prompt loop on subsequent /lp-bootstrap runs).
    assert summary["additions"] == []
    assert summary["already_satisfied"] is False


def test_cli_write_skipped_marker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--repo-root", str(tmp_path), "--write-skipped"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("autonomous-settings-merge.skipped")


# --- BL-372 v2 (PR #76 pattern-finder P2): --repo-root flag rename ----------


def test_cli_repo_root_flag_matches_repo_convention(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_ack(tmp_path)
    rc = main(["--repo-root", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ack_present"] is True


def test_cli_cwd_alias_still_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Compatibility alias for out-of-tree callers during the v2.1.8
    # cycle. v2.2 BL candidate to deprecate.
    _seed_ack(tmp_path)
    rc = main(["--cwd", str(tmp_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ack_present"] is True
