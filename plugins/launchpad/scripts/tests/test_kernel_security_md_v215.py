"""BL-342 v2.1.5: verify SECURITY.md is among the rendered kernel files
and references the project's advisories endpoint.

Status (2026-05-15): research during v2.1.5 scoping revealed SECURITY.md
was already in `KernelRenderer.KERNEL_FILES` from a prior v2.1.x release.
This test confirms the property and locks it down so a future kernel-list
edit can't silently regress."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plugin_default_generators.kernel_renderer import (  # noqa: E402
    KERNEL_FILES,
    KernelRenderer,
)


_TEST_IDENTITY = {
    "project_name": "test-proj",
    "email": "security@example.com",
    "repo_url": "https://github.com/test-org/test-proj",
    "license": "MIT",
    "copyright_holder": "Test Holder",
}


def test_security_md_is_a_kernel_file() -> None:
    """SECURITY.md must appear in KERNEL_FILES so KernelRenderer renders it."""
    target_relpaths = {target for _template, target in KERNEL_FILES}
    assert "SECURITY.md" in target_relpaths
    template_for_security = next(
        template for template, target in KERNEL_FILES if target == "SECURITY.md"
    )
    assert template_for_security == "SECURITY.md.j2"


def test_security_md_renders_with_advisories_endpoint(tmp_path: Path) -> None:
    """Render the full kernel batch; SECURITY.md must reference the
    project's `/security/advisories` endpoint per the public-repo
    setup guide."""
    renderer = KernelRenderer()
    content = renderer.render_to_string("SECURITY.md.j2", _TEST_IDENTITY)
    assert "/security/advisories" in content
    assert _TEST_IDENTITY["email"] in content
    assert _TEST_IDENTITY["project_name"] in content


def test_security_md_in_render_all_output(tmp_path: Path) -> None:
    """End-to-end: `KernelRenderer.render_all` writes SECURITY.md to
    disk alongside the other kernel files."""
    # render_all writes files; need a writable temp tree with .launchpad
    # secret-patterns and allowlist files OR no patterns file (the gate
    # accepts an absent patterns_file).
    renderer = KernelRenderer()
    rendered, render_state = renderer.render_all(tmp_path, _TEST_IDENTITY)
    rendered_paths = {target.name for target, _sha in rendered}
    assert "SECURITY.md" in rendered_paths
    assert (tmp_path / "SECURITY.md").is_file()
    # State entry exists for SECURITY.md
    state_paths = {entry["path"] for entry in render_state}
    assert "SECURITY.md" in state_paths
