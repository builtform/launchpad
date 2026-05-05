"""Kernel renderer (V3 plan section 17.1 Phase 2).

Thin subclass of `RendererBase` that ships the 7 kernel templates rendered
by `/lp-scaffold-stack` at greenfield scaffold time AND re-rendered by
`/lp-bootstrap --refresh` when `/lp-update-identity` (Phase 10+) updates
the sealed identity block.

The 7 kernel files are stack-agnostic and identity-bearing:
  * LICENSE              (license enum + copyright_holder + project_name + current_year)
  * CONTRIBUTING.md      (project_name + email + repo_url)
  * CODE_OF_CONDUCT.md   (project_name + email; Contributor Covenant 2.1)
  * README.md            (project_name + repo_url + license)
  * SECURITY.md          (project_name + email + repo_url)
  * AGENTS.md            (project_name + repo_url + email + license)
  * CLAUDE.md            (project_name; Claude-specific superset of AGENTS.md)

Phase 2 ships full canonical text for the MIT license enum (the default).
Non-MIT licenses render a placeholder pointing at choosealicense.com; the
remaining 5 license bodies (Apache-2.0, GPL-3.0, BSD-3-Clause, ISC,
MPL-2.0) are tracked as a Phase-9 follow-up. The `Other` license enum
uses `identity.license_other_body` verbatim.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from ._renderer_base import RendererBase


# Inventory: (template name relative to TEMPLATE_SUBDIR, output relpath)
# Output relpaths are relative to the project root (cwd at scaffold time).
KERNEL_FILES: Sequence[tuple[str, str]] = (
    ("LICENSE.j2",            "LICENSE"),
    ("CONTRIBUTING.md.j2",    "CONTRIBUTING.md"),
    ("CODE_OF_CONDUCT.md.j2", "CODE_OF_CONDUCT.md"),
    ("README.md.j2",          "README.md"),
    ("SECURITY.md.j2",        "SECURITY.md"),
    ("AGENTS.md.j2",          "AGENTS.md"),
    ("CLAUDE.md.j2",          "CLAUDE.md"),
)


class KernelRenderer(RendererBase):
    """Render the 7 kernel files for a project's identity block."""

    TEMPLATE_SUBDIR = "kernel"

    def render_all(
        self,
        cwd: Path,
        identity: Mapping[str, Any],
    ) -> list[tuple[Path, str]]:
        """Render all 7 kernel files into `cwd`.

        Returns a list of `(target_path, rendered_sha256)` tuples for each
        file written. The sha256 values feed the bootstrap manifest's
        `rendered_content_sha256` field (Phase 3+).

        `cwd` is the project root, NOT a layer subpath. Kernel files live
        at the top of the project tree alongside the user's own README,
        package.json, etc.

        Re-rendering is idempotent: each call writes the same content for
        the same identity input. Per V3 plan section 10.1 conflict policy,
        kernel files are written with `overwrite-if-unchanged` policy at
        Phase 3+ wiring time -- /lp-update-identity will not clobber a
        user's manual edits unless the on-disk hash matches the previously
        rendered hash.
        """
        results: list[tuple[Path, str]] = []
        for template_name, output_relpath in KERNEL_FILES:
            target = cwd / output_relpath
            _, sha256 = self.render_to_path(template_name, target, identity)
            results.append((target, sha256))
        return results


__all__ = ["KERNEL_FILES", "KernelRenderer"]
