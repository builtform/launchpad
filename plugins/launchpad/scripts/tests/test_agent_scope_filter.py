"""Phase 6 Slice A + B -- stack_scope corpus invariants + filter behavior.

Slice A invariants (~5): assert the actual on-disk plugin agent corpus
matches the v2.1 §3.1 classification table without any runtime parsing of
the filter module. These tests read the YAML frontmatter directly so they
fail loudly if any agent file gets renamed, demoted, or stripped of its
stack_scope field by a stray edit.

Slice B behavior (~5): import the filter module via importlib (hyphenated
filename) and exercise the public surface (`filter_agents_by_stacks`,
`_load_agent_index`, `STACK_SCOPE_REGEX`).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

_SCRIPTS = Path(__file__).resolve().parent.parent
_AGENTS_ROOT = _SCRIPTS.parent / "agents"
_FILTER_PATH = _SCRIPTS / "plugin-agent-scope-filter.py"


# ---------------------------------------------------------------------------
# Corpus loader (Slice A reads frontmatter directly; module-import-free)
# ---------------------------------------------------------------------------

def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path}: missing leading frontmatter fence")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise AssertionError(f"{path}: missing trailing frontmatter fence")
    body = text[4:end]
    parsed = yaml.safe_load(body)
    if not isinstance(parsed, dict):
        raise AssertionError(f"{path}: frontmatter is not a mapping")
    return parsed


def _all_agent_files() -> list[Path]:
    return sorted(_AGENTS_ROOT.rglob("*.md"))


_STACK_SCOPE_RE = re.compile(
    r"^(core_pipeline|stack:any|stack:[a-z_]{1,32}|design_quality|skill_quality)$"
)


# ---------------------------------------------------------------------------
# Slice A invariants
# ---------------------------------------------------------------------------

def test_every_agent_has_stack_scope_field():
    """DA1: every plugin agent has `stack_scope:` frontmatter."""
    missing = [
        str(f.relative_to(_AGENTS_ROOT))
        for f in _all_agent_files()
        if "stack_scope" not in _read_frontmatter(f)
    ]
    assert not missing, f"agents missing stack_scope: {missing}"


def test_every_agent_name_matches_filename_stem():
    """Slice A invariant: `name:` field == filename stem."""
    mismatches = []
    for f in _all_agent_files():
        fm = _read_frontmatter(f)
        if fm.get("name") != f.stem:
            mismatches.append(
                f"{f.relative_to(_AGENTS_ROOT)}: name={fm.get('name')!r}, stem={f.stem!r}"
            )
    assert not mismatches, "name/stem drift: " + "; ".join(mismatches)


def test_every_stack_scope_matches_regex():
    """DA1: stack_scope value matches STACK_SCOPE_REGEX (bounded {1,32})."""
    bad = []
    for f in _all_agent_files():
        fm = _read_frontmatter(f)
        scope = fm.get("stack_scope", "")
        if not _STACK_SCOPE_RE.fullmatch(str(scope)):
            bad.append(f"{f.relative_to(_AGENTS_ROOT)}: stack_scope={scope!r}")
    assert not bad, "invalid stack_scope values: " + "; ".join(bad)


def test_per_value_count_floors_satisfied():
    """v2.1 §3.1: 4 active scope values each have >= 1 agent.
    Note: stack:<id> count is allowed = 0 in v2.1 per cycle-3 axis-mismatch fix.
    """
    counts: dict[str, int] = {}
    for f in _all_agent_files():
        fm = _read_frontmatter(f)
        scope = fm["stack_scope"]
        # collapse stack:<id> into the family bucket but keep stack:any distinct
        bucket = scope if scope in (
            "core_pipeline", "stack:any", "design_quality", "skill_quality"
        ) else "stack:<id>"
        counts[bucket] = counts.get(bucket, 0) + 1
    for required in ("core_pipeline", "stack:any", "design_quality", "skill_quality"):
        assert counts.get(required, 0) >= 1, (
            f"v2.1 corpus floor violated: {required} count = {counts.get(required, 0)}"
        )


def test_total_agent_count_self_consistent():
    """v2.1 §3.1: 16 + 13 + 6 + 1 = 36; total matches filesystem walk."""
    files = _all_agent_files()
    assert len(files) == 36, f"expected 36 agents on disk; found {len(files)}"
    by_scope: dict[str, int] = {}
    for f in files:
        scope = _read_frontmatter(f)["stack_scope"]
        by_scope[scope] = by_scope.get(scope, 0) + 1
    assert by_scope.get("core_pipeline") == 16, by_scope
    assert by_scope.get("stack:any") == 13, by_scope
    assert by_scope.get("design_quality") == 6, by_scope
    assert by_scope.get("skill_quality") == 1, by_scope
    assert sum(by_scope.values()) == len(files)


# ---------------------------------------------------------------------------
# Filter module loader (Slice B onwards)
# ---------------------------------------------------------------------------

def _load_filter_module():
    """Reload the filter module fresh — clears the lru_cache."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "plugin_agent_scope_filter", _FILTER_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
def filter_mod():
    mod = _load_filter_module()
    # Clear cache to give each test a fresh load.
    mod._load_agent_index.cache_clear()
    return mod


# ---------------------------------------------------------------------------
# Slice B behavior tests
# ---------------------------------------------------------------------------

def test_filter_passes_core_pipeline_and_stack_any_through(filter_mod):
    """DA2: core_pipeline + stack:any survive empty + populated stacks."""
    survivors_empty = filter_mod.filter_agents_by_stacks(
        ["lp-file-locator", "lp-security-auditor"], stacks=[]
    )
    survivors_pop = filter_mod.filter_agents_by_stacks(
        ["lp-file-locator", "lp-security-auditor"], stacks=["ts_monorepo"]
    )
    assert "lp-file-locator" in survivors_empty
    assert "lp-security-auditor" in survivors_empty
    assert "lp-file-locator" in survivors_pop
    assert "lp-security-auditor" in survivors_pop


def test_filter_excludes_design_quality_and_skill_quality(filter_mod):
    """DA2: design_quality + skill_quality NEVER pass; callers pre-filter."""
    out = filter_mod.filter_agents_by_stacks(
        ["lp-design-iterator", "lp-skill-evaluator", "lp-file-locator"],
        stacks=["ts_monorepo"],
    )
    assert "lp-design-iterator" not in out
    assert "lp-skill-evaluator" not in out
    assert "lp-file-locator" in out


def test_filter_validates_stacks_against_active_enum(filter_mod):
    """v2.1 DoD: bogus stack ids are rejected with ValueError."""
    with pytest.raises(ValueError):
        filter_mod.filter_agents_by_stacks(
            ["lp-file-locator"], stacks=["bogus_stack_id"]
        )


def test_filter_warns_and_drops_unknown_names(filter_mod, caplog):
    """Cycle-3 spec-flow P1-2: unknown names dropped + WARN; partial-drop banner ready."""
    import logging
    caplog.set_level(logging.WARNING)
    out = filter_mod.filter_agents_by_stacks(
        ["lp-file-locator", "lp-not-real-agent"], stacks=[]
    )
    assert "lp-not-real-agent" not in out
    assert "lp-file-locator" in out
    dropped = filter_mod.last_dropped_names()
    assert "lp-not-real-agent" in dropped


def test_filter_module_invariants(filter_mod):
    """Cycle-3 perf P1-2 + DA2: module-level STACK_SCOPE_REGEX is bounded;
    loader returns MappingProxyType; EmptyFilterResultError fires when all
    names miss the index (v2.1 trigger path per cycle-4 spec-flow P2-C)."""
    from types import MappingProxyType

    # Module-level regex constant; bounded {1,32}; embedded space rejected.
    assert isinstance(filter_mod.STACK_SCOPE_REGEX, re.Pattern)
    assert filter_mod.STACK_SCOPE_REGEX.fullmatch("core_pipeline")
    assert filter_mod.STACK_SCOPE_REGEX.fullmatch("stack:rails")
    assert not filter_mod.STACK_SCOPE_REGEX.fullmatch("stack:" + "a" * 33)
    assert not filter_mod.STACK_SCOPE_REGEX.fullmatch("stack:foo bar")

    # Loader returns immutable MappingProxyType.
    idx = filter_mod._load_agent_index()
    assert isinstance(idx, MappingProxyType)
    with pytest.raises(TypeError):
        idx["lp-file-locator"] = {"path": "tampered", "stack_scope": "core_pipeline"}

    # EmptyFilterResultError on all-names-missing.
    with pytest.raises(filter_mod.EmptyFilterResultError):
        filter_mod.filter_agents_by_stacks(
            ["lp-not-real-1", "lp-not-real-2"], stacks=[]
        )

    # Empty input returns [] without raising.
    assert filter_mod.filter_agents_by_stacks([], stacks=["ts_monorepo"]) == []
