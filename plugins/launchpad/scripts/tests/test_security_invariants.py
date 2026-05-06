"""Phase 6 v2.1 Slice G -- security posture invariants.

Three concrete tests covering Phase 6 §3.0 defenses:
  1. CODEOWNERS file content includes `plugins/launchpad/agents/** @builtform/core`
     (cycle-3 spec-flow P1-4 reframing: T1 defense is the file content,
     NOT runtime behavior).
  2. Symlink agent file is skipped at load time (`_safe_candidate` rejection).
  3. Malformed `stack_scope` value (embedded space) rejected by regex.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"
SCRIPTS = Path(__file__).resolve().parent.parent
FILTER_PATH = SCRIPTS / "plugin-agent-scope-filter.py"


def _load_filter_module():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    sys.modules.pop("plugin_agent_scope_filter", None)
    spec = importlib.util.spec_from_file_location(
        "plugin_agent_scope_filter", FILTER_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_codeowners_pre_merge_gate_for_plugin_agents():
    """T1 defense (cycle-3 spec-flow P1-4): malicious upstream PR rewriting
    `stack_scope` to disable security review must trip the CODEOWNERS gate
    on `plugins/launchpad/agents/**`."""
    assert CODEOWNERS.is_file(), f"CODEOWNERS not found at {CODEOWNERS}"
    text = CODEOWNERS.read_text(encoding="utf-8")
    # Match the rule loosely (whitespace tolerance) but strictly require
    # the path glob + the @builtform/core handle.
    found = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("/plugins/launchpad/agents/**") and "@builtform/core" in stripped:
            found = True
            break
    assert found, (
        "CODEOWNERS missing rule "
        "'plugins/launchpad/agents/** @builtform/core' "
        "(Phase 6 §3.0 T1 defense)."
    )


def test_symlink_agent_file_skipped_at_load(tmp_path: Path, monkeypatch):
    """`_safe_candidate` rejection: a symlinked .md in the agents tree is
    skipped at load time (no frontmatter parse, no inclusion in index)."""
    # Skip on Windows where symlink semantics differ.
    if os.name != "posix":
        pytest.skip("symlink test is POSIX-only")

    # Build a fake agent tree under tmp_path mirroring the plugin layout.
    fake_root = tmp_path / "plugins" / "launchpad" / "agents"
    (fake_root / "research").mkdir(parents=True)
    (fake_root / "research" / "lp-fake-real.md").write_text(
        "---\nname: lp-fake-real\ndescription: stub\nstack_scope: core_pipeline\n---\n",
        encoding="utf-8",
    )
    # Create a symlink that should be rejected.
    target_outside = tmp_path / "smuggled.md"
    target_outside.write_text(
        "---\nname: lp-smuggled\ndescription: smuggled\nstack_scope: core_pipeline\n---\n",
        encoding="utf-8",
    )
    symlink = fake_root / "research" / "lp-smuggled.md"
    symlink.symlink_to(target_outside)

    # Re-bind the module's _PLUGIN_AGENTS_ROOT to the fake tree, then
    # exercise the loader.
    mod = _load_filter_module()
    mod._load_agent_index.cache_clear()
    monkeypatch.setattr(mod, "_PLUGIN_AGENTS_ROOT", fake_root.resolve())
    idx = mod._load_agent_index()
    assert "lp-fake-real" in idx
    assert "lp-smuggled" not in idx, "symlinked agent file was not rejected"


def test_malformed_stack_scope_rejected_by_regex():
    """Cycle-3 security P1-NEW-A bound check: `STACK_SCOPE_REGEX` rejects
    embedded-space + over-32-char-suffix values, defeating common
    smuggling shapes."""
    mod = _load_filter_module()
    bad_values = (
        "stack:foo bar",
        "stack:foo\tbar",
        "stack:" + "a" * 33,        # 33 chars exceeds {1,32} bound
        "stack:foo;DROP TABLE",
        "core_pipeline ",            # trailing space
        " stack:any",                # leading space
        "stack:..\n",                # newline injection
        "STACK:ANY",                 # uppercase rejected
    )
    for value in bad_values:
        assert not mod.STACK_SCOPE_REGEX.fullmatch(value), (
            f"regex accepted malformed value {value!r}"
        )
