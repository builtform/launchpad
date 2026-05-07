"""Tests for lp_bootstrap.policy (v2.1 Phase 3 Slice A).

Coverage matrix (section 5 + plan section 2.2):
  * 3 active policies plus `--refresh`-mode `overwrite-with-backup`.
  * Lefthook merge-keys additive-only contract: 4 cases per harden A13.
    - add new top-level key
    - user wins on value-type conflict (warning logged)
    - never deletes user keys
    - appends to user pre_commit.commands without deletion
  * `gitignore_append_failed` fail-closed (harden A14).
  * Symlink rejection per overwrite-if-unchanged + append-only + merge-keys
    + overwrite-with-backup.
  * Backup directory naming: `<ts>-<PID>-<rand4>` (harden C1).
  * Backup contents byte-equal to pre-edit.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap import BootstrapErrorCode  # noqa: E402
from lp_bootstrap.policy import (  # noqa: E402
    BootstrapPolicyError,
    PolicyAction,
    apply_append_only,
    apply_merge_keys,
    apply_overwrite_if_unchanged,
    ensure_backups_in_gitignore,
    make_backup_dir,
    merge_keys_additive,
    record_warnings,
    write_backup_then_overwrite,
)


# --- overwrite-if-unchanged (section 3.2 row 1) ---------------------------

def test_overwrite_if_unchanged_writes_when_target_absent(tmp_path):
    target = tmp_path / "build.sh"
    body = b"#!/bin/bash\necho hello\n"
    result = apply_overwrite_if_unchanged(
        target=target,
        rendered_bytes=body,
        manifest_rendered_sha=None,
        mode=0o755,
        cwd=tmp_path,
    )
    assert result.action == PolicyAction.WRITE
    assert target.read_bytes() == body
    # mode set after replace per harden B8
    assert target.stat().st_mode & 0o777 == 0o755


def test_overwrite_if_unchanged_skips_when_on_disk_matches_rendered(tmp_path):
    target = tmp_path / "lib.sh"
    body = b"echo same\n"
    target.write_bytes(body)
    import hashlib
    on_disk_sha = hashlib.sha256(body).hexdigest()
    result = apply_overwrite_if_unchanged(
        target=target,
        rendered_bytes=body,
        manifest_rendered_sha=on_disk_sha,
        mode=0o644,
        cwd=tmp_path,
    )
    assert result.action == PolicyAction.SKIP_UNCHANGED


def test_overwrite_if_unchanged_keeps_user_edits(tmp_path):
    target = tmp_path / "build.sh"
    target.write_bytes(b"# user edited content\n")
    rendered = b"#!/bin/bash\necho plugin\n"
    result = apply_overwrite_if_unchanged(
        target=target,
        rendered_bytes=rendered,
        manifest_rendered_sha="0" * 64,  # manifest says rendered was 0000...
        mode=0o755,
        cwd=tmp_path,
    )
    assert result.action == PolicyAction.KEPT_USER_EDITS
    assert target.read_bytes() == b"# user edited content\n"


def test_overwrite_if_unchanged_writes_when_template_changed(tmp_path):
    """Plugin updated; on-disk matches manifest sha; rendered differs -> write."""
    import hashlib
    target = tmp_path / "build.sh"
    old_body = b"echo v1\n"
    target.write_bytes(old_body)
    old_sha = hashlib.sha256(old_body).hexdigest()
    new_body = b"echo v2\n"
    result = apply_overwrite_if_unchanged(
        target=target,
        rendered_bytes=new_body,
        manifest_rendered_sha=old_sha,
        mode=0o755,
        cwd=tmp_path,
    )
    assert result.action == PolicyAction.WRITE
    assert target.read_bytes() == new_body


def test_overwrite_if_unchanged_rejects_symlink(tmp_path):
    real = tmp_path / "real.sh"
    real.write_bytes(b"echo real\n")
    target = tmp_path / "link.sh"
    target.symlink_to(real)
    with pytest.raises(BootstrapPolicyError) as excinfo:
        apply_overwrite_if_unchanged(
            target=target,
            rendered_bytes=b"x",
            manifest_rendered_sha=None,
            mode=0o755,
            cwd=tmp_path,
        )
    assert excinfo.value.reason == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


# --- append-only (section 3.2 row 3 + harden A14) -------------------------

def test_append_only_creates_new_file(tmp_path):
    target = tmp_path / ".gitignore"
    rendered = b".launchpad/\nnode_modules/\n"
    result = apply_append_only(target=target, rendered_bytes=rendered, mode=0o644, cwd=tmp_path)
    assert result.action == PolicyAction.APPENDED
    text = target.read_text(encoding="utf-8")
    assert ".launchpad/" in text
    assert "node_modules/" in text


def test_append_only_appends_only_missing_entries(tmp_path):
    target = tmp_path / ".gitignore"
    target.write_text("node_modules/\n.env\n", encoding="utf-8")
    rendered = b".launchpad/\nnode_modules/\ndist/\n"
    result = apply_append_only(target=target, rendered_bytes=rendered, mode=0o644, cwd=tmp_path)
    assert result.action == PolicyAction.APPENDED
    text = target.read_text(encoding="utf-8")
    # User's .env preserved
    assert ".env" in text
    # Original node_modules/ NOT duplicated
    assert text.count("node_modules/") == 1
    # Plugin's new entries appended
    assert ".launchpad/" in text
    assert "dist/" in text


def test_append_only_no_op_when_all_present(tmp_path):
    target = tmp_path / ".gitignore"
    target.write_text(".launchpad/\nnode_modules/\n", encoding="utf-8")
    rendered = b".launchpad/\nnode_modules/\n"
    result = apply_append_only(target=target, rendered_bytes=rendered, mode=0o644, cwd=tmp_path)
    assert result.action == PolicyAction.SKIP_UNCHANGED


def test_append_only_rejects_symlink(tmp_path):
    real = tmp_path / "real_gitignore"
    real.write_text("# fake\n", encoding="utf-8")
    target = tmp_path / ".gitignore"
    target.symlink_to(real)
    with pytest.raises(BootstrapPolicyError) as excinfo:
        apply_append_only(target=target, rendered_bytes=b".launchpad/\n", mode=0o644, cwd=tmp_path)
    assert excinfo.value.reason == BootstrapErrorCode.GITIGNORE_APPEND_FAILED


def test_ensure_backups_in_gitignore_creates_when_absent(tmp_path):
    ensure_backups_in_gitignore(tmp_path)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".launchpad/backups/" in text


def test_ensure_backups_in_gitignore_idempotent(tmp_path):
    (tmp_path / ".gitignore").write_text(".launchpad/backups/\nnode_modules/\n", encoding="utf-8")
    ensure_backups_in_gitignore(tmp_path)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert text.count(".launchpad/backups/") == 1


# --- merge-keys (section 3.2 row 2 + harden A13) --------------------------

def test_merge_keys_adds_new_top_level_key():
    user = {"existing": True}
    plugin = {"new_key": "value", "existing": True}
    merged, warnings = merge_keys_additive(user=user, plugin=plugin)
    assert merged == {"existing": True, "new_key": "value"}
    assert warnings == []


def test_merge_keys_user_wins_on_value_conflict():
    user = {"key": "user_value"}
    plugin = {"key": "plugin_value"}
    merged, warnings = merge_keys_additive(user=user, plugin=plugin)
    assert merged["key"] == "user_value"
    assert any("key" in w for w in warnings)


def test_merge_keys_user_wins_on_value_type_conflict():
    user = {"key": "scalar"}
    plugin = {"key": ["a", "b"]}
    merged, warnings = merge_keys_additive(user=user, plugin=plugin)
    assert merged["key"] == "scalar"
    assert any("value-type conflict" in w for w in warnings)


def test_merge_keys_never_deletes_user_keys():
    user = {"keep_me": "always", "shared": "user"}
    plugin = {"shared": "plugin"}
    merged, _ = merge_keys_additive(user=user, plugin=plugin)
    assert "keep_me" in merged
    assert merged["keep_me"] == "always"


def test_merge_keys_appends_to_user_pre_commit_commands_without_deletion():
    user = {
        "pre-commit": {
            "commands": [{"name": "user-cmd-1", "run": "echo a"}],
        },
    }
    plugin = {
        "pre-commit": {
            "commands": [{"name": "plugin-cmd-1", "run": "echo b"}],
        },
    }
    merged, warnings = merge_keys_additive(user=user, plugin=plugin)
    cmds = merged["pre-commit"]["commands"]
    names = {c["name"] for c in cmds}
    assert "user-cmd-1" in names
    assert "plugin-cmd-1" in names
    assert len(cmds) == 2


def test_merge_keys_does_not_duplicate_existing_list_items():
    user = {"list": [{"a": 1}, {"b": 2}]}
    plugin = {"list": [{"a": 1}, {"c": 3}]}
    merged, _ = merge_keys_additive(user=user, plugin=plugin)
    assert merged["list"] == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_apply_merge_keys_json_round_trip(tmp_path):
    target = tmp_path / "config.json"
    target.write_text('{"user_key": "value"}\n', encoding="utf-8")
    rendered = b'{"plugin_key": 42, "user_key": "value"}'
    result = apply_merge_keys(
        target=target, rendered_bytes=rendered, mode=0o644, cwd=tmp_path, serializer="json",
    )
    assert result.action == PolicyAction.MERGED
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["user_key"] == "value"
    assert payload["plugin_key"] == 42


def test_apply_merge_keys_rejects_symlink(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    target = tmp_path / "config.json"
    target.symlink_to(real)
    with pytest.raises(BootstrapPolicyError) as excinfo:
        apply_merge_keys(
            target=target, rendered_bytes=b"{}", mode=0o644, cwd=tmp_path, serializer="json",
        )
    assert excinfo.value.reason == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


def test_apply_merge_keys_codeowners_uses_append_only(tmp_path):
    target = tmp_path / "CODEOWNERS"
    target.write_text("docs/ @user\n", encoding="utf-8")
    rendered = b"plugins/ @plugin-team\ndocs/ @user\n"
    result = apply_merge_keys(
        target=target, rendered_bytes=rendered, mode=0o644, cwd=tmp_path, serializer="codeowners",
    )
    assert result.action == PolicyAction.APPENDED
    text = target.read_text(encoding="utf-8")
    assert "docs/ @user" in text
    assert "plugins/ @plugin-team" in text


# --- overwrite-with-backup + backup-dir helper (section 3.2 + harden C1) --

def test_make_backup_dir_naming_pattern(tmp_path):
    backup = make_backup_dir(tmp_path, command_pid=12345)
    name = backup.name
    parts = name.split("-")
    assert len(parts) == 3
    assert parts[1] == "12345"
    assert len(parts[2]) == 4  # 4 hex chars
    assert backup.parent.name == "backups"
    assert backup.parent.parent.name == ".launchpad"


def test_make_backup_dir_collision_resilience(tmp_path):
    """Same PID in same second -> different rand4 -> different paths."""
    a = make_backup_dir(tmp_path, command_pid=1)
    b = make_backup_dir(tmp_path, command_pid=1)
    assert a != b


def test_write_backup_then_overwrite_round_trip(tmp_path):
    target = tmp_path / "scripts" / "build.sh"
    target.parent.mkdir(parents=True)
    pre_edit = b"#!/bin/bash\n# user-edited\n"
    target.write_bytes(pre_edit)
    backup_dir = make_backup_dir(tmp_path)
    new_body = b"#!/bin/bash\n# fresh from plugin\n"

    result = write_backup_then_overwrite(
        target=target,
        new_bytes=new_body,
        backup_dir=backup_dir,
        target_relpath="scripts/build.sh",
        mode=0o755,
        cwd=tmp_path,
    )

    assert result.action == PolicyAction.OVERWROTE_WITH_BACKUP
    assert target.read_bytes() == new_body
    assert (backup_dir / "scripts" / "build.sh").read_bytes() == pre_edit
    assert target.stat().st_mode & 0o777 == 0o755


def test_write_backup_then_overwrite_rejects_symlink(tmp_path):
    real = tmp_path / "real.sh"
    real.write_bytes(b"echo real\n")
    target = tmp_path / "link.sh"
    target.symlink_to(real)
    backup_dir = make_backup_dir(tmp_path)
    with pytest.raises(BootstrapPolicyError) as excinfo:
        write_backup_then_overwrite(
            target=target,
            new_bytes=b"x",
            backup_dir=backup_dir,
            target_relpath="link.sh",
            mode=0o755,
            cwd=tmp_path,
        )
    assert excinfo.value.reason == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


def test_record_warnings_appends_to_existing(tmp_path):
    (tmp_path / ".launchpad").mkdir()
    record_warnings(tmp_path, ["first warning"])
    record_warnings(tmp_path, ["second warning", "third warning"])
    payload = json.loads(
        (tmp_path / ".launchpad" / "bootstrap-warnings.json").read_text(encoding="utf-8")
    )
    assert payload["warnings"] == ["first warning", "second warning", "third warning"]
