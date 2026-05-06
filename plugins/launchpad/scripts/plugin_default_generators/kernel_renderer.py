"""Kernel renderer (V3 plan section 17.1 Phase 2; Phase 8.5 batch flow).

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

Phase 8.5 plan section 3.11 (DA1' = a2): render_all routes through
`render_batch + write_batch` so the secret-scanner gate fires on the
full kernel output before any single file lands on disk.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from ._renderer_base import RendererBase, sha256_bytes


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

    def render_targets(
        self, context: Mapping[str, Any]
    ) -> Iterator[tuple[Path, str]]:
        """Yield `(absolute_target_path, rendered_text)` for each kernel
        template. Context must carry `cwd: Path` and `identity: Mapping`.
        """
        cwd: Path = context["cwd"]
        identity: Mapping[str, Any] = context["identity"]
        for template_name, output_relpath in KERNEL_FILES:
            text = self.render_to_string(template_name, identity)
            yield cwd / output_relpath, text

    def render_all(
        self,
        cwd: Path,
        identity: Mapping[str, Any],
    ) -> list[tuple[Path, str]]:
        """Render all 7 kernel files into `cwd` via the buffered-batch flow.

        Returns a list of `(target_path, rendered_sha256)` tuples for each
        file written. The sha256 values feed the bootstrap manifest's
        `rendered_content_sha256` field (Phase 3+).

        Phase 8.5 plan section 3.11: secret-scanner gate fires on the full
        7-file batch before any single file lands on disk.

        `cwd` is the project root, NOT a layer subpath.
        """
        patterns_file = cwd / ".launchpad" / "secret-patterns.txt"
        allowlist_path = cwd / ".launchpad" / "secret-allowlist.txt"
        batch = self.render_batch(
            [{"cwd": cwd, "identity": identity}],
        )
        self.write_batch(
            batch,
            patterns_file=patterns_file,
            allowlist_path=allowlist_path,
        )
        return [(target, sha256_bytes(content)) for target, content in batch.items()]


__all__ = ["KERNEL_FILES", "KernelRenderer"]
