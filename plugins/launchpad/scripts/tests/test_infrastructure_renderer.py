"""Tests for the v2.1 infrastructure renderer (V3 plan section 17.1 Phase 3 / Slice B).

The infrastructure renderer ships the 30-path overlay rendered by
`/lp-bootstrap` at greenfield + brownfield-auto + refresh time. Tests
cover:

  * All 30 paths emit; output sha256s stable across calls.
  * Identity injection into templates that reference identity fields.
  * `FILE_MODES` allowlist: 11 paths -> 0o755; 19 paths -> 0o644.
  * `chmod` after `os.replace` (harden B8): the post-replace mode matches
    `FILE_MODES[target_relpath]` even when the target previously had a
    different mode.
  * `.gitignore` allowlist scan with unknown-entry warning.
  * `only_paths` filtering: subset of 30 emitted; non-inventory rejection.
  * Singleton renderer pattern: a freshly-constructed renderer + a cached
    one render byte-identical output for the same identity.
  * `render_target` returns bytes for the engine fast-path; raises
    `TEMPLATE_NOT_FOUND` for unknown targets.
  * `_validate_gitignore_content` allowlist regex matrix.
  * Autoescape posture: identity values containing `{{ 7*7 }}` render as
    literal string, not as 49 (SSTI defense).
  * StrictUndefined: missing identity field raises at render time.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap import (  # noqa: E402
    BootstrapErrorCode,
    FILE_MODES,
    INFRASTRUCTURE_FILES,
    INFRASTRUCTURE_TARGETS,
)
from plugin_default_generators.infrastructure_renderer import (  # noqa: E402
    InfrastructureRenderError,
    InfrastructureRenderer,
    _validate_gitignore_content,
)


def _identity(**overrides):
    base = {
        "pii_opt_in": True,
        "project_name": "demo",
        "email": "demo@example.com",
        "copyright_holder": "@demo-team",
        "repo_url": "https://github.com/demo/demo",
        "license": "MIT",
        "license_other_body": "",
    }
    base.update(overrides)
    return base


# --- 30-path enumeration --------------------------------------------------

def test_renders_all_30_paths(tmp_path):
    # v2.1 Codex PR #50 P1.A: count is 31 after restamp-history-hook entry.
    from lp_bootstrap import INFRASTRUCTURE_FILES
    r = InfrastructureRenderer()
    out = r.render_all(tmp_path, _identity())
    assert len(out) == len(INFRASTRUCTURE_FILES)
    assert {p.relative_to(tmp_path).as_posix() for p, _ in out} == INFRASTRUCTURE_TARGETS


def test_render_outputs_are_stable(tmp_path):
    """Same identity -> byte-identical render across calls."""
    r = InfrastructureRenderer()
    out1 = r.render_all(tmp_path / "a", _identity())
    out2 = r.render_all(tmp_path / "b", _identity())
    shas1 = [sha for _, sha in out1]
    shas2 = [sha for _, sha in out2]
    assert shas1 == shas2


def test_only_paths_subset_renders_only_those(tmp_path):
    r = InfrastructureRenderer()
    subset = [".gitignore", "scripts/compound/build.sh"]
    out = r.render_all(tmp_path, _identity(), only_paths=subset)
    rendered_targets = [p.relative_to(tmp_path).as_posix() for p, _ in out]
    assert rendered_targets == subset


def test_only_paths_unknown_rejected(tmp_path):
    r = InfrastructureRenderer()
    with pytest.raises(InfrastructureRenderError) as excinfo:
        r.render_all(tmp_path, _identity(), only_paths=["nonexistent.txt"])
    assert excinfo.value.reason == BootstrapErrorCode.UNKNOWN_REFRESH_PATH


# --- File mode allowlist (harden B8) --------------------------------------

def test_file_modes_inventory_split():
    """v2.1 Codex PR #50 P1.A (D1): 12 paths 0o755 (was 11; restamp-history-hook
    added) + 19 paths 0o644 per harden B8."""
    exe = sum(1 for m in FILE_MODES.values() if m == 0o755)
    non_exe = sum(1 for m in FILE_MODES.values() if m == 0o644)
    assert exe == 12
    assert non_exe == 19


def test_file_modes_set_post_atomic_write(tmp_path):
    """Harden B8: chmod AFTER os.replace; final mode matches FILE_MODES."""
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity())
    for _template, target_relpath, _policy, mode in INFRASTRUCTURE_FILES:
        actual = (tmp_path / target_relpath).stat().st_mode & 0o777
        assert actual == mode, f"{target_relpath}: expected 0o{mode:o}, got 0o{actual:o}"


def test_chmod_after_replace_overrides_existing_mode(tmp_path):
    """If target existed with different mode, post-replace chmod fixes it."""
    target = tmp_path / "scripts" / "compound" / "build.sh"
    target.parent.mkdir(parents=True)
    target.write_text("# old\n")
    target.chmod(0o600)
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity())
    assert target.stat().st_mode & 0o777 == 0o755


# --- Identity injection ---------------------------------------------------

def test_identity_injected_into_greptile(tmp_path):
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity(project_name="acme-saas"))
    payload = json.loads((tmp_path / ".greptile.json").read_text())
    assert "acme-saas" in payload["instructions"]


def test_identity_injected_into_codeowners(tmp_path):
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity(copyright_holder="@platform-team", project_name="acme"))
    text = (tmp_path / ".github" / "CODEOWNERS").read_text()
    assert "acme" in text
    assert "@platform-team" in text


def test_identity_injected_into_harness_local_md(tmp_path):
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity(project_name="my-project"))
    text = (tmp_path / ".harness" / "harness.local.md").read_text()
    assert "my-project" in text


def test_identity_injected_into_secret_patterns(tmp_path):
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity(project_name="my-proj"))
    text = (tmp_path / ".launchpad" / "secret-patterns.txt").read_text()
    assert "my-proj" in text


def test_identity_injected_into_ci_workflow(tmp_path):
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity(project_name="acme"))
    text = (tmp_path / ".github" / "workflows" / "ci.yml").read_text()
    assert "acme" in text
    assert "${{ github.ref }}" in text  # raw-block preserved GHA syntax


def test_strict_undefined_raises_on_missing_field():
    """StrictUndefined: a template that references a missing identity field
    raises at render time rather than emitting an empty string."""
    r = InfrastructureRenderer()
    bad_identity = {"pii_opt_in": True}  # no project_name, etc.
    with pytest.raises(InfrastructureRenderError) as excinfo:
        r.render_target(".greptile.json", bad_identity)
    assert excinfo.value.reason == BootstrapErrorCode.TEMPLATE_RENDER_FAILED


# --- Autoescape / SSTI defense -------------------------------------------

def test_identity_value_with_jinja_syntax_is_not_re_evaluated(tmp_path):
    """SSTI defense: hostile project_name value renders as literal."""
    r = InfrastructureRenderer()
    r.render_all(tmp_path, _identity(project_name="{{ 7*7 }}"))
    text = (tmp_path / ".harness" / "harness.local.md").read_text()
    assert "{{ 7*7 }}" in text
    assert "49" not in text


# --- render_target single-file rendering ---------------------------------

def test_render_target_returns_bytes():
    r = InfrastructureRenderer()
    bytes_ = r.render_target(".gitignore", _identity())
    assert isinstance(bytes_, bytes)
    assert b".launchpad/" in bytes_


def test_render_target_unknown_path_rejected():
    r = InfrastructureRenderer()
    with pytest.raises(InfrastructureRenderError) as excinfo:
        r.render_target("nonexistent/foo.txt", _identity())
    assert excinfo.value.reason == BootstrapErrorCode.UNKNOWN_REFRESH_PATH


# --- .gitignore allowlist scan (harden A12) ------------------------------

def test_validate_gitignore_content_allowlist_matches_known_entries():
    text = ".launchpad/\nnode_modules/\n*.log\n.env.local\ncoverage/\n"
    warnings = _validate_gitignore_content(text)
    assert warnings == []


def test_validate_gitignore_content_warns_on_unknown_entry():
    text = ".launchpad/\nbizarre-unknown-pattern-xyz/\n"
    warnings = _validate_gitignore_content(text)
    assert len(warnings) == 1
    assert "bizarre-unknown-pattern-xyz" in warnings[0]


def test_validate_gitignore_skips_blanks_and_comments():
    text = "# comment\n\n.launchpad/\n# another comment\n"
    assert _validate_gitignore_content(text) == []


def test_gitignore_warnings_helper_runs_clean_against_default_template():
    """The default v2.1 .gitignore template is in-allowlist."""
    r = InfrastructureRenderer()
    warnings = r.gitignore_warnings(_identity())
    # The default template SHOULD pass; if a future template change adds
    # an unknown entry without updating the allowlist, this test surfaces it.
    assert warnings == [], f"unexpected gitignore warnings: {warnings}"


# --- Singleton-friendly: renderer reuse produces same output --------------

def test_two_renderer_instances_produce_identical_output(tmp_path):
    """Pin that no per-instance state diverges (the engine constructs
    `_RENDERER` once and reuses across calls)."""
    a = InfrastructureRenderer()
    b = InfrastructureRenderer()
    out_a = a.render_all(tmp_path / "a", _identity())
    out_b = b.render_all(tmp_path / "b", _identity())
    assert [sha for _, sha in out_a] == [sha for _, sha in out_b]


def test_renderer_jinja_env_is_constructed_once_per_instance():
    """Each instance owns one Jinja Environment; multiple render calls do
    not re-construct it."""
    r = InfrastructureRenderer()
    env1 = r.env
    _ = r.render_target(".gitignore", _identity())
    _ = r.render_target("scripts/compound/build.sh", _identity())
    env2 = r.env
    assert env1 is env2
