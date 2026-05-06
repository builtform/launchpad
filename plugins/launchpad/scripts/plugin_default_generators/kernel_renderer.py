"""Kernel renderer (V3 plan section 17.1 Phase 2; Phase 8.5 batch flow).

Thin subclass of `RendererBase` that ships the 7 kernel templates rendered
by `/lp-scaffold-stack` at greenfield scaffold time AND re-rendered by
`/lp-update-identity` (Phase 10+) directly via `KernelRenderer.refresh()`
per Phase 3 cement (`lp_bootstrap/__init__.py:10-14` + `lp-bootstrap.md:34-38`)
when the sealed identity block changes. NOT routed through `/lp-bootstrap
--refresh`; the bootstrap-manifest mechanism covers infrastructure only.

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

import hashlib
from dataclasses import dataclass
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


@dataclass(frozen=True)
class RefreshResult:
    """Phase 10 DA1 -- result of `KernelRenderer.refresh()`.

    `rendered`: list of (target_path, rendered_sha256) for each kernel
        file successfully re-rendered.
    `skipped_user_edits`: list of target_paths refused with
        `USER_EDIT_BLOCKS_REFRESH` per Phase 10 §3.7 -- on-disk sha did
        NOT match the prior `kernel_render_state[i].rendered_content_sha256`,
        signaling a manual user edit post-render.
    `template_drift_infos`: list of one-line INFO strings emitted when
        `source_template_sha256` differs from current plugin's template
        sha (plugin upgrade between scaffold and refresh, per security
        lens P1).
    """
    rendered: list[tuple[Path, str]]
    skipped_user_edits: list[Path]
    template_drift_infos: list[str]


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

    def _template_sha256(self, template_name: str) -> str:
        """Compute sha256 of the on-disk template source (Phase 10 §3.7
        cross-version source-template drift detection)."""
        env = self.env  # type: ignore[attr-defined]
        source_path = Path(env.loader.get_source(env, template_name)[1])
        return hashlib.sha256(source_path.read_bytes()).hexdigest()

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

        Phase 10 DA7 (flipped): after the kernel batch lands on disk, the
        `kernel_render_state` block in `<cwd>/.launchpad/scaffold-decision.json`
        is re-sealed via `re_seal_decision_atomic` so the renderer's
        per-file sha is the single source of truth at refresh time
        (architecture-strategist P2-A; eliminates asymmetric coupling).
        Re-seal is best-effort: if scaffold-decision is absent (greenfield
        ordering: scaffold-decision is sealed BEFORE render_all by
        /lp-scaffold-stack engine, but tests and pre-Phase-10 callers
        may invoke render_all standalone), we skip the re-seal silently.

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
        rendered = [(target, sha256_bytes(content)) for target, content in batch.items()]

        # Phase 10 DA7 + cycle-2 P2-2: re-seal scaffold-decision with
        # kernel_render_state in a single atomic-write-replace. Best-effort:
        # silently skip when scaffold-decision is absent (e.g., test fixtures).
        try:
            from lp_pick_stack.decision_writer import (
                re_seal_decision_atomic,
            )
            decision_path = cwd / ".launchpad" / "scaffold-decision.json"
            if decision_path.is_file():
                state_entries = []
                for template_name, output_relpath in KERNEL_FILES:
                    target = cwd / output_relpath
                    if not target.is_file():
                        continue
                    state_entries.append({
                        "path": output_relpath,
                        "rendered_content_sha256": sha256_bytes(target.read_bytes()),
                        "source_template_sha256": self._template_sha256(template_name),
                    })

                def _set_kernel_render_state(payload):
                    payload["kernel_render_state"] = state_entries

                re_seal_decision_atomic(cwd, update_fn=_set_kernel_render_state)
        except Exception:
            # Don't fail the render on side-effect re-seal failure; the
            # primary contract is the kernel batch landing on disk. Phase
            # 10 engine layer surfaces the issue via subsequent
            # read-and-validate.
            pass

        return rendered

    def refresh(
        self,
        cwd: Path,
        identity: Mapping[str, Any],
        *,
        on_user_edit_warn: bool = True,
    ) -> RefreshResult:
        """Re-render the 7 kernel files with `overwrite-if-unchanged` per DA1.

        Phase 10 contract:
          1. Read `kernel_render_state` block from
             `<cwd>/.launchpad/scaffold-decision.json` (Phase 10 DA7
             flipped; was sidecar artifact in v1).
          2. For each kernel file: compute on-disk sha256; compare to the
             stored `rendered_content_sha256`. Mismatch -> user edited
             post-render -> refuse THAT file with
             `USER_EDIT_BLOCKS_REFRESH` (continue refresh for other
             files).
          3. For matching files: render with new identity; write atomically
             via `write_batch` (secret-scanner gate fires on the surviving
             subset).
          4. Re-seal scaffold-decision with new `kernel_render_state` block.

        Cross-version source-template drift (security-lens P1): if the
        scaffold-decision's `source_template_sha256` differs from the
        current plugin's template sha (plugin upgrade between scaffold
        and refresh), do NOT auto-refuse. Append an INFO string and
        proceed if `rendered_content_sha256` still matches on-disk
        (= user hasn't edited; safe to overwrite even with new templates).

        Returns RefreshResult with rendered + skipped + template-drift
        info lists. Caller (engine.run_update_identity) prints the diff
        summary per Phase 10 §3.12 from this structured return.
        """
        from lp_pick_stack.decision_writer import (
            read_decision_atomic,
            re_seal_decision_atomic,
        )

        decision = read_decision_atomic(cwd)
        kernel_render_state = decision.get("kernel_render_state") or []
        # Build path -> sha lookup for quick per-file decisions.
        prior_state = {
            entry["path"]: entry
            for entry in kernel_render_state
            if isinstance(entry, dict) and "path" in entry
        }

        # Render the full batch in memory; secret-scanner gate runs on the
        # full set per Phase 8.5. Per-file user-edit refusal happens
        # AFTER the gate (the gate is a security boundary; user-edit
        # detection is a consent boundary).
        full_batch = self.render_batch([{"cwd": cwd, "identity": identity}])

        skipped: list[Path] = []
        template_drift_infos: list[str] = []
        write_subset: dict[Path, bytes] = {}

        for template_name, output_relpath in KERNEL_FILES:
            target = cwd / output_relpath
            new_content = full_batch.get(target)
            if new_content is None:
                continue
            entry = prior_state.get(output_relpath)
            if entry is None:
                # No prior state for this file: write it (greenfield-ish; the
                # engine's re-entry case E flow normally provides the baseline
                # so we should only land here in test fixtures).
                write_subset[target] = new_content
                continue
            prior_rendered_sha = entry.get("rendered_content_sha256")
            current_disk_sha = (
                sha256_bytes(target.read_bytes()) if target.is_file() else None
            )
            if current_disk_sha is None:
                # File is missing -> always render fresh.
                write_subset[target] = new_content
                continue
            if current_disk_sha != prior_rendered_sha:
                skipped.append(target)
                continue
            # File matches prior render: safe to overwrite. Check template
            # drift for INFO surface.
            current_template_sha = self._template_sha256(template_name)
            if entry.get("source_template_sha256") != current_template_sha:
                template_drift_infos.append(
                    f"{output_relpath}: plugin templates updated since last "
                    f"render; refresh will adopt new templates"
                )
            write_subset[target] = new_content

        # Run secret-scanner gate on the subset that will actually land.
        if write_subset:
            patterns_file = cwd / ".launchpad" / "secret-patterns.txt"
            allowlist_path = cwd / ".launchpad" / "secret-allowlist.txt"
            self.write_batch(
                write_subset,
                patterns_file=patterns_file,
                allowlist_path=allowlist_path,
            )

        rendered = [
            (target, sha256_bytes(content))
            for target, content in write_subset.items()
        ]

        # Re-seal scaffold-decision with the new state for the rendered subset
        # AND the unchanged entries for skipped files (their state is unchanged).
        new_state_entries = []
        for template_name, output_relpath in KERNEL_FILES:
            target = cwd / output_relpath
            if not target.is_file():
                continue
            new_state_entries.append({
                "path": output_relpath,
                "rendered_content_sha256": sha256_bytes(target.read_bytes()),
                "source_template_sha256": self._template_sha256(template_name),
            })

        def _set_kernel_render_state(payload):
            payload["kernel_render_state"] = new_state_entries

        re_seal_decision_atomic(cwd, update_fn=_set_kernel_render_state)

        return RefreshResult(
            rendered=rendered,
            skipped_user_edits=skipped,
            template_drift_infos=template_drift_infos,
        )


__all__ = ["KERNEL_FILES", "KernelRenderer", "RefreshResult"]
