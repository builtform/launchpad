"""Tests for v2.1.2 BL-316 consumer Python-gate propagation.

Verifies the rendered consumer `lefthook.yml` contains the 5 propagated
gates when `nextjs_fastapi` is in `selected_stack_ids`, locks the rendered
shape against silent regressions, and guards the new `_partials/` directory
from being treated as a phantom stack adapter.

Renderer dispatch path: tests invoke `make_stack_aware_jinja_env()` (the
singleton-cached ChoiceLoader-rooted Jinja env at `_renderer_base.py:206`)
and render `lefthook.yml.j2.outer` directly — the same environment + outer
template that `infrastructure_renderer` uses to materialize a consumer's
`lefthook.yml`. The conftest fixture below resets the singleton cache
between tests so partial rewrites don't bleed across.

Implementation path chosen (Phase 1 discovery): SINGLE-PARTIAL. The outer
template at `lefthook.yml.j2.outer` performs pure text concatenation
(NOT YAML merge), so a single partial declaring both `pre-push:` and
`pre-commit:` produces identical rendered output to a split-partial
implementation when the partial is included from a single stack adapter.
The split-partial fallback (per plan Implementation Sequence) was not
needed.

Pre-existing v2.1 composition behavior (NOT BL-316 introduced): the outer
template's text concatenation produces YAML with duplicate top-level keys
when 2+ stack fragments declare the same hook. PyYAML applies last-key-
wins. test #9 below checks substring presence in the raw rendered text
(not parsed YAML) to assert all 5 gate names appear regardless of stack
ordering. Single-stack rendering (test #10 yaml.safe_load) sees no
duplicate-key issue.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from plugin_default_generators import _renderer_base  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_stack_aware_env_singleton():
    """Reset the singleton-cached stack-aware Jinja env between tests so
    partial template rewrites don't bleed across test invocations
    (architecture cycle-2 P2 — singleton cache poisoning guard)."""
    _renderer_base._STACK_AWARE_ENV = None
    yield
    _renderer_base._STACK_AWARE_ENV = None


def _render(selected_stack_ids: list[str]) -> str:
    env = _renderer_base.make_stack_aware_jinja_env()
    tmpl = env.get_template("lefthook.yml.j2.outer")
    return tmpl.render(selected_stack_ids=selected_stack_ids)


_PYTHON_GATE_NAMES = ("bandit", "ruff-check", "ruff-format-check", "pyright", "pytest")


def test_nextjs_fastapi_renders_python_gates() -> None:
    """All 5 propagated gates appear in rendered output for nextjs_fastapi."""
    rendered = _render(["nextjs_fastapi"])
    for gate_name in _PYTHON_GATE_NAMES:
        assert f"{gate_name}:" in rendered, f"missing gate: {gate_name}"


def test_python_gates_have_command_v_preamble() -> None:
    """Each gate emits the fail-loud `command -v <tool>` preamble + GATE
    MISSING error + LEFTHOOK=0 escape hatch + GitHub URL."""
    rendered = _render(["nextjs_fastapi"])
    for tool in ("bandit", "ruff", "pyright", "pytest"):
        assert f"command -v {tool} >/dev/null 2>&1" in rendered
        assert f"GATE MISSING: {tool}" in rendered
    assert "LEFTHOOK=0" in rendered
    assert "https://github.com/builtform/launchpad/" in rendered


@pytest.mark.parametrize(
    "gate_name,hook,priority",
    [
        ("bandit", "pre-commit", 10),
        ("ruff-check", "pre-commit", 11),
        ("ruff-format-check", "pre-commit", 12),
        ("pyright", "pre-push", 10),
        ("pytest", "pre-push", 10),
    ],
)
def test_python_gate_attributes(gate_name: str, hook: str, priority: int) -> None:
    """Each gate has `glob: "**/*.py"`, the right priority, and lives under
    the right top-level hook (pre-commit vs pre-push)."""
    rendered = _render(["nextjs_fastapi"])
    parsed = yaml.safe_load(rendered)
    commands = parsed[hook]["commands"]
    assert gate_name in commands, f"{gate_name} not under {hook}.commands"
    gate = commands[gate_name]
    assert gate["glob"] == "**/*.py"
    assert gate["priority"] == priority


def test_pyright_probes_apps_api_then_api() -> None:
    """Pyright run-line probes apps/api/ (composition layout) BEFORE api/
    (legacy single-stack layout) and silent-skips with exit 0 if neither
    workspace exists — never bare `pyright` cwd-walk."""
    rendered = _render(["nextjs_fastapi"])
    parsed = yaml.safe_load(rendered)
    pyright_run = parsed["pre-push"]["commands"]["pyright"]["run"]
    apps_api_idx = pyright_run.find("if [ -d apps/api ]")
    api_idx = pyright_run.find("elif [ -d api ]")
    assert apps_api_idx >= 0
    assert api_idx > apps_api_idx, "apps/api probe must come before api/ probe"
    assert "exit 0" in pyright_run, "must silent-skip when no workspace"
    assert "pyright apps/api" in pyright_run
    assert "pyright api" in pyright_run


def test_pytest_tolerates_exit_5() -> None:
    """Pytest run-line tolerates exit 5 (no tests collected) and uses
    --tb=short for traceback context."""
    rendered = _render(["nextjs_fastapi"])
    parsed = yaml.safe_load(rendered)
    pytest_run = parsed["pre-push"]["commands"]["pytest"]["run"]
    assert "|| [ $? -eq 5 ]" in pytest_run
    assert "--tb=short" in pytest_run


def test_pytest_probes_apps_api_then_api() -> None:
    """Pytest run-line probes apps/api/ (composition layout) BEFORE api/
    (legacy single-stack layout) and silent-skips with exit 0 if neither
    workspace exists — never bare `pytest` cwd-walk.

    Pytest's default `norecursedirs` does NOT exclude `node_modules/` or
    `.next/`, so a bare `pytest` invocation from the consumer's repo root
    would collect dependency test files. Mirrors pyright's defense.
    """
    rendered = _render(["nextjs_fastapi"])
    parsed = yaml.safe_load(rendered)
    pytest_run = parsed["pre-push"]["commands"]["pytest"]["run"]
    apps_api_idx = pytest_run.find("if [ -d apps/api ]")
    api_idx = pytest_run.find("elif [ -d api ]")
    assert apps_api_idx >= 0
    assert api_idx > apps_api_idx, "apps/api probe must come before api/ probe"
    assert "exit 0" in pytest_run, "must silent-skip when no workspace"
    assert "pytest -x --tb=short apps/api" in pytest_run
    assert "pytest -x --tb=short api" in pytest_run


def test_pre_commit_gates_use_safe_xargs_pipeline() -> None:
    """Each pre-commit gate uses the shell-injection-safe NUL-delimited
    pipeline (BL-316 Slice 4c.6 / closes BL-313): `git diff -z` emits
    NUL-delimited filenames; `xargs -0 -r` execs argv directly with no
    shell re-parse. The unsafe `set -- {staged_files}` pattern is
    REPLACED — this test guards the security regression shield.

    Crucially: `{staged_files}` MUST NOT appear in any rendered run body
    because lefthook substitutes it as raw text into the shell, evaluating
    metacharacters in filenames. See `tests/test_lp_bootstrap_stack_lefthook.py`
    for the malicious-filename regression test that proves the new
    pipeline resists `evil$(touch SHOULD_NOT_EXIST).py` injection.
    """
    rendered = _render(["nextjs_fastapi"])
    parsed = yaml.safe_load(rendered)
    for gate_name, tool in (
        ("bandit", "bandit -ll"),
        ("ruff-check", "ruff check"),
        ("ruff-format-check", "ruff format --check"),
    ):
        run = parsed["pre-commit"]["commands"][gate_name]["run"]
        # New safe pipeline must be present.
        assert "git diff --cached --name-only -z" in run, (
            f"{gate_name} missing NUL-delimited git diff pipeline"
        )
        assert "xargs -0 -r" in run, (
            f"{gate_name} missing safe xargs invocation"
        )
        assert tool in run, f"{gate_name} missing tool invocation: {tool}"
        # The OLD unsafe pattern MUST be gone — security regression shield.
        # Strip comment lines (lines whose first non-whitespace char is `#`)
        # because the safety-narrative comment legitimately mentions
        # `{staged_files}` to explain WHY the pipeline replaces it.
        active_lines = [
            line
            for line in run.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        active_body = "\n".join(active_lines)
        assert "{staged_files}" not in active_body, (
            f"{gate_name} REGRESSED: {{staged_files}} is shell-unsafe; "
            f"BL-313 / Slice 4c.6 closure violated (found in active "
            f"command lines, not just comments)"
        )
        assert "set -- " not in active_body, (
            f"{gate_name} REGRESSED to legacy `set -- {{staged_files}}` "
            f"pattern; security fix lost"
        )


def test_python_gates_dropped_self_host_paths() -> None:
    """Rendered consumer lefthook.yml does NOT reference plugin-internal
    paths from the maintainer's lefthook.yml."""
    rendered = _render(["nextjs_fastapi"])
    forbidden = (
        "plugins/launchpad/scripts",
        "[ -d plugins/launchpad",
        "cd plugins/launchpad",
    )
    for path in forbidden:
        assert path not in rendered, f"forbidden self-host path leaked: {path!r}"


def test_non_python_stacks_do_not_inherit_python_gates() -> None:
    """A non-Python stack (astro) does NOT inherit the propagated Python
    gates by accident. Guards against future copy-paste regression where
    a partial `{% include %}` lands in the wrong adapter."""
    rendered = _render(["astro"])
    for gate_name in _PYTHON_GATE_NAMES:
        assert f"{gate_name}:" not in rendered, (
            f"non-Python stack inherited gate {gate_name!r}"
        )


def test_composition_includes_python_gates_when_nextjs_fastapi_present() -> None:
    """Multi-stack composition: all 5 gate names appear in the rendered
    text regardless of stack ordering. Substring check (not parsed YAML)
    because the outer template's text concatenation produces duplicate
    top-level keys when 2 stacks each declare the same hook (pre-existing
    v2.1 behavior, NOT BL-316 introduced)."""
    for ordering in (
        ["nextjs_fastapi", "astro"],
        ["astro", "nextjs_fastapi"],
    ):
        rendered = _render(ordering)
        for gate_name in _PYTHON_GATE_NAMES:
            assert f"{gate_name}:" in rendered, (
                f"missing {gate_name} in ordering {ordering!r}"
            )


def test_rendered_lefthook_yaml_parses_safely() -> None:
    """Single-stack render parses cleanly via yaml.safe_load.

    NOTE: this proves YAML SYNTAX validity only, NOT lefthook SCHEMA
    validity. Schema validation via `lefthook validate` is queued for a
    v2.2 BL (acknowledgment of cycle-2 adversarial P1 #5).
    """
    rendered = _render(["nextjs_fastapi"])
    parsed = yaml.safe_load(rendered)
    assert isinstance(parsed, dict)
    assert "pre-push" in parsed
    assert "pre-commit" in parsed


def test_partials_not_in_active_stack_enum() -> None:
    """Defends against a future code path that enumerates
    `plugin_stack_adapters/` to discover stack ids from treating the new
    `_partials/` directory as a phantom adapter.

    Two assertions:
      1. `"_partials"` is NOT in the closed-enum `STACK_ID_ACTIVE_ENUM`.
      2. `validate_stack_id("_partials")` raises `StackIdInvalidError`
         (the actual extant gate that protects the renderer from a bad
         stack_id reaching template lookup).

    Note: `_renderer_base.py` does NOT itself perform `iterdir()`-based
    stack discovery (verified during Phase 1 discovery). The cycle-3
    plan acknowledged the cycle-2 architecture P1 concern as forward-
    looking — this test locks the closed-enum gate today against a
    future iterdir-based discovery code path.
    """
    assert "_partials" not in _renderer_base.STACK_ID_ACTIVE_ENUM
    with pytest.raises(_renderer_base.StackIdInvalidError):
        _renderer_base.validate_stack_id("_partials")
