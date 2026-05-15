"""Tests for v2.1.5 BL-353 + BL-354 + BL-355 (CI workflow self-consistency).

BL-353: pnpm/action-setup needs a `version:` source. The rendered ci.yml
must include the centralized DEFAULT_PNPM_VERSION pin.

BL-354: actions/setup-node references `.nvmrc` via node-version-file. The
.nvmrc file must be rendered to repo root by /lp-bootstrap with the
centralized DEFAULT_NODE_VERSION pin.

BL-355: /lp-bootstrap must refuse to write if any rendered workflow names
a `*-version-file` input that no other rendered file (or on-disk file)
satisfies. Defense-in-depth that prevents the BL-353/BL-354 regression
class at next workflow-template rotation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plugin_default_generators._renderer_base import identity_inject  # noqa: E402
from plugin_default_generators.infrastructure_renderer import (  # noqa: E402
    InfrastructureRenderError,
    InfrastructureRenderer,
    _validate_workflow_self_consistency,
)
from plugin_stack_adapters._constants import (  # noqa: E402
    DEFAULT_NODE_VERSION,
    DEFAULT_PNPM_VERSION,
)


_TEST_IDENTITY = {
    "project_name": "test-proj",
    "email": "test@example.com",
    "repo_url": "https://github.com/test-org/test-proj",
    "license": "MIT",
    "copyright_holder": "Test Holder",
}


# ---------------------------------------------------------------------------
# BL-353: pnpm version pin in ci.yml
# ---------------------------------------------------------------------------


def test_bl353_ci_yml_renders_pnpm_version_input() -> None:
    """The rendered ci.yml must include `version: '<DEFAULT_PNPM_VERSION>'`
    on the pnpm/action-setup step. Without this, the step bails on every
    greenfield pnpm-stack first push."""
    renderer = InfrastructureRenderer()
    ci = renderer.render_to_string("github/workflows/ci.yml.j2", _TEST_IDENTITY)
    assert "pnpm/action-setup@" in ci, "ci.yml should still reference pnpm/action-setup"
    # The version: input must appear AFTER the pnpm/action-setup `uses:`
    # line; assert it does.
    lines = ci.splitlines()
    setup_idx = next(
        (i for i, ln in enumerate(lines) if "pnpm/action-setup@" in ln), None
    )
    assert setup_idx is not None, "pnpm/action-setup step not found"
    # Look at the next ~5 lines for the `version:` input
    window = "\n".join(lines[setup_idx : setup_idx + 6])
    assert (
        f"version: '{DEFAULT_PNPM_VERSION}'" in window
    ), f"pnpm/action-setup must declare version (got: {window!r})"


def test_bl353_pnpm_version_constant_single_source() -> None:
    """DEFAULT_PNPM_VERSION must be the single source of truth — the
    constant module is the only place the version string appears."""
    from plugin_stack_adapters import _constants

    assert isinstance(DEFAULT_PNPM_VERSION, str)
    assert len(DEFAULT_PNPM_VERSION) >= 5
    # The version follows pnpm's MAJOR.MINOR.PATCH convention.
    parts = DEFAULT_PNPM_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
    # The module exports the constant.
    assert "DEFAULT_PNPM_VERSION" in _constants.__all__


# ---------------------------------------------------------------------------
# BL-354: .nvmrc render
# ---------------------------------------------------------------------------


def test_bl354_nvmrc_renders_with_default_node_version() -> None:
    """The nvmrc.j2 template renders DEFAULT_NODE_VERSION followed by a
    trailing newline."""
    renderer = InfrastructureRenderer()
    nvmrc = renderer.render_to_string("nvmrc.j2", _TEST_IDENTITY)
    assert nvmrc.strip() == DEFAULT_NODE_VERSION
    assert nvmrc.endswith("\n"), ".nvmrc must end with a newline"


def test_bl354_nvmrc_in_infrastructure_files() -> None:
    """The `.nvmrc` target relpath must be in INFRASTRUCTURE_FILES so
    /lp-bootstrap renders it."""
    from lp_bootstrap import INFRASTRUCTURE_FILES, INFRASTRUCTURE_TARGETS

    assert ".nvmrc" in INFRASTRUCTURE_TARGETS
    target_relpaths = [t for _template, t, _policy, _mode in INFRASTRUCTURE_FILES]
    assert ".nvmrc" in target_relpaths
    # The matching template is `nvmrc.j2`
    template_for_nvmrc = next(
        template
        for template, target, _policy, _mode in INFRASTRUCTURE_FILES
        if target == ".nvmrc"
    )
    assert template_for_nvmrc == "nvmrc.j2"


def test_bl354_node_version_constant_format() -> None:
    """DEFAULT_NODE_VERSION must be a Node SemVer string (MAJOR.MINOR.PATCH)
    so .nvmrc's content matches what setup-node expects."""
    parts = DEFAULT_NODE_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


# ---------------------------------------------------------------------------
# BL-355: workflow self-consistency assertion
# ---------------------------------------------------------------------------


def test_bl355_self_consistency_passes_on_current_render(tmp_path: Path) -> None:
    """Rendering the v2.1.5 baseline (with BL-353 + BL-354 in place) must
    pass the self-consistency check with no errors."""
    renderer = InfrastructureRenderer()
    # Render JUST the ci.yml + nvmrc into a batch to test self-consistency
    ci_bytes = renderer.render_to_string(
        "github/workflows/ci.yml.j2", _TEST_IDENTITY
    ).encode("utf-8")
    nvmrc_bytes = renderer.render_to_string("nvmrc.j2", _TEST_IDENTITY).encode("utf-8")
    batch = {
        tmp_path / ".github" / "workflows" / "ci.yml": ci_bytes,
        tmp_path / ".nvmrc": nvmrc_bytes,
    }
    errors = _validate_workflow_self_consistency(batch, tmp_path)
    assert errors == [], f"baseline should be self-consistent (got: {errors!r})"


def test_bl355_refuses_when_referenced_file_missing(tmp_path: Path) -> None:
    """If a workflow references node-version-file but the batch doesn't
    provide the named file (and no on-disk file exists), the self-
    consistency check reports the inconsistency."""
    workflow = """\
name: Build
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v6
        with:
          node-version-file: .nvmrc
"""
    batch = {
        tmp_path / ".github" / "workflows" / "ci.yml": workflow.encode("utf-8"),
    }
    errors = _validate_workflow_self_consistency(batch, tmp_path)
    assert len(errors) == 1
    err = errors[0]
    assert ".nvmrc" in err
    assert "node-version-file" in err
    assert "CI will fail on first push" in err


def test_bl355_accepts_referenced_file_in_batch(tmp_path: Path) -> None:
    """When the referenced file IS in the batch, the check passes."""
    workflow = """\
name: Build
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v6
        with:
          node-version-file: .nvmrc
"""
    batch = {
        tmp_path / ".github" / "workflows" / "ci.yml": workflow.encode("utf-8"),
        tmp_path / ".nvmrc": b"22.12.0\n",
    }
    errors = _validate_workflow_self_consistency(batch, tmp_path)
    assert errors == []


def test_bl355_accepts_referenced_file_on_disk(tmp_path: Path) -> None:
    """When the referenced file exists on disk (not in batch — pre-existing
    project state), the check passes."""
    workflow = """\
name: Build
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v6
        with:
          node-version-file: .nvmrc
"""
    (tmp_path / ".nvmrc").write_text("22.12.0\n")
    batch = {
        tmp_path / ".github" / "workflows" / "ci.yml": workflow.encode("utf-8"),
    }
    errors = _validate_workflow_self_consistency(batch, tmp_path)
    assert errors == []


def test_bl355_render_all_refuses_inconsistent_batch(tmp_path: Path) -> None:
    """`InfrastructureRenderer.render_all` must raise on inconsistent
    state. Use only_paths to render a subset that has the workflow but
    not the .nvmrc."""
    renderer = InfrastructureRenderer()
    # Render only the ci workflow (no .nvmrc) — the check should fire.
    with pytest.raises(InfrastructureRenderError) as exc_info:
        renderer.render_all(
            tmp_path,
            _TEST_IDENTITY,
            only_paths=[".github/workflows/ci.yml"],
        )
    err_str = str(exc_info.value)
    assert "self-consistency" in err_str
    assert ".nvmrc" in err_str


def test_bl355_recognizes_setup_node_input() -> None:
    """The closed enum of file-referencing inputs covers setup-node, the
    only action referenced by v2.1 workflow templates.

    v2.1.5 round-3 review fix B6 (ts-reviewer + simplicity-reviewer):
    `setup-python` / `setup-go` / `setup-ruby` rows were YAGNI scaffolding
    (forward-compat for v2.1.6 BL-345 stack-aware refactor) — no v2.1
    template references them. They will be re-added in v2.1.6 when the
    stack-aware workflows that name those inputs land. Pinned-size
    assertion below guarantees the enum doesn't silently regrow."""
    from plugin_default_generators.infrastructure_renderer import (
        _WORKFLOW_FILE_REF_INPUTS,
    )

    inputs = dict(_WORKFLOW_FILE_REF_INPUTS)
    # The only entry: setup-node + node-version-file.
    assert "actions/setup-node" in inputs
    assert inputs["actions/setup-node"] == "node-version-file"
    # Pinned-size guard so the next person to touch this list updates the
    # documentation/CHANGELOG when they grow it.
    assert len(_WORKFLOW_FILE_REF_INPUTS) == 1, (
        "BL-355 + round-3 B6: _WORKFLOW_FILE_REF_INPUTS is trimmed to "
        "setup-node only at v2.1.5. v2.1.6 BL-345 re-adds rows when "
        "stack-aware workflows reference setup-python/go/ruby."
    )
    # Negative: forward-compat rows must NOT be present at v2.1.
    assert "actions/setup-python" not in inputs
    assert "actions/setup-go" not in inputs
    assert "ruby/setup-ruby" not in inputs


# ---------------------------------------------------------------------------
# Identity-context injection
# ---------------------------------------------------------------------------


def test_identity_inject_surfaces_default_versions() -> None:
    """The Jinja context returned by identity_inject must expose
    DEFAULT_PNPM_VERSION and DEFAULT_NODE_VERSION so templates can
    reference them via {{ default_pnpm_version }} / {{ default_node_version }}."""
    ctx = identity_inject(_TEST_IDENTITY)
    assert ctx["default_pnpm_version"] == DEFAULT_PNPM_VERSION
    assert ctx["default_node_version"] == DEFAULT_NODE_VERSION
