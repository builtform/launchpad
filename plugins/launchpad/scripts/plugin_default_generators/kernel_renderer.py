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

Phase 1+2 retroactive amendment A7 (DIP cleanup): the renderer is the
LOW-LEVEL primitive. It does NOT depend on `lp_pick_stack.decision_writer`
to seal the kernel_render_state into scaffold-decision.json. Instead,
both `render_all` and `refresh` RETURN the freshly-computed render-state
list to their callers; the higher-level caller (lp_scaffold_stack engine
for greenfield render, lp_update_identity engine for refresh) is
responsible for the atomic re-seal. This keeps the renderer reusable
in test fixtures and brownfield contexts that have no scaffold-decision.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
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
    `kernel_render_state`: list of dicts shaped per HANDSHAKE §4 v1.1
        envelope (`{path, rendered_content_sha256, source_template_sha256}`)
        covering EVERY kernel file currently on disk after refresh
        (rendered + skipped). Phase 1+2 retroactive amendment A7 pushes
        the atomic re-seal of this state into the caller (engine.py),
        so the renderer no longer depends on lp_pick_stack.decision_writer.
    """
    rendered: list[tuple[Path, str]]
    skipped_user_edits: list[Path]
    template_drift_infos: list[str]
    kernel_render_state: list[dict] = field(default_factory=list)


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

    def compute_current_on_disk_state(self, cwd: Path) -> list[dict]:
        """v2.1 Codex PR #50 Greptile #6 (D6): idempotent per-file SHA snapshot.

        Read-only, side-effect-free, returns a fresh list on each call.
        For each kernel file, returns:

            {
                "path": output_relpath,
                "rendered_content_sha256": <on-disk sha or None>,
                "source_template_sha256": <upstream template sha>,
                "missing_on_disk": <bool>,
                "user_has_drift": <bool — true if rendered_sha != template_sha>,
            }

        Used by Case E "y" path in `lp_update_identity` to seal
        kernel_render_state WITHOUT overwriting user edits. The
        consumer-side contract (lock-now, land-BL-267) is documented in
        `docs/architecture/SCAFFOLD_OPERATIONS.md` §12: `--refresh
        --accept-drift` opts into clobber with `.bak` fallback for files
        whose `user_has_drift=true`.
        """
        out: list[dict] = []
        for template_name, output_relpath in KERNEL_FILES:
            target = cwd / output_relpath
            template_sha = self._template_sha256(template_name)
            entry: dict[str, Any]
            if not target.is_file():
                entry = {
                    "path": output_relpath,
                    "rendered_content_sha256": None,
                    "source_template_sha256": template_sha,
                    "missing_on_disk": True,
                    "user_has_drift": False,
                }
            else:
                rendered_sha = sha256_bytes(target.read_bytes())
                entry = {
                    "path": output_relpath,
                    "rendered_content_sha256": rendered_sha,
                    "source_template_sha256": template_sha,
                    "missing_on_disk": False,
                    "user_has_drift": rendered_sha != template_sha,
                }
            out.append(entry)
        return out

    def render_all(
        self,
        cwd: Path,
        identity: Mapping[str, Any],
    ) -> tuple[list[tuple[Path, str]], list[dict]]:
        """Render all 7 kernel files into `cwd` via the buffered-batch flow.

        Returns `(rendered, kernel_render_state)`:

          * `rendered`: list of `(target_path, rendered_sha256)` tuples
            for each file written. Feeds the bootstrap manifest's
            `rendered_content_sha256` field (Phase 3+).
          * `kernel_render_state`: list of dicts shaped per HANDSHAKE §4
            v1.1 envelope (`{path, rendered_content_sha256,
            source_template_sha256}`) covering every kernel file just
            rendered. The CALLER (lp_scaffold_stack engine) is responsible
            for sealing this list into scaffold-decision.json via
            `re_seal_decision_atomic`. Phase 1+2 retroactive amendment A7:
            this DIP cleanup removes the renderer's prior dependency on
            lp_pick_stack.decision_writer.

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
        rendered = [(target, sha256_bytes(content)) for target, content in batch.items()]

        kernel_render_state: list[dict] = []
        for template_name, output_relpath in KERNEL_FILES:
            target = cwd / output_relpath
            if not target.is_file():
                continue
            kernel_render_state.append({
                "path": output_relpath,
                "rendered_content_sha256": sha256_bytes(target.read_bytes()),
                "source_template_sha256": self._template_sha256(template_name),
            })

        return rendered, kernel_render_state

    def refresh(
        self,
        cwd: Path,
        identity: Mapping[str, Any],
        *,
        prior_kernel_render_state: list[dict] | None = None,
    ) -> RefreshResult:
        """Re-render the 7 kernel files with `overwrite-if-unchanged` per DA1.

        Phase 10 contract:
          1. Use `prior_kernel_render_state` (passed by caller; previously
             read from scaffold-decision.json by the renderer itself).
             Phase 1+2 retroactive amendment A7 inverts the dependency:
             the caller passes the prior state and seals the new state.
          2. For each kernel file: compute on-disk sha256; compare to the
             stored `rendered_content_sha256`. Mismatch -> user edited
             post-render -> refuse THAT file with
             `USER_EDIT_BLOCKS_REFRESH` (continue refresh for other
             files).
          3. For matching files: render with new identity; write atomically
             via `write_batch` (secret-scanner gate fires on the surviving
             subset).

        Cross-version source-template drift (security-lens P1): if the
        prior `source_template_sha256` differs from the current plugin's
        template sha (plugin upgrade between scaffold and refresh), do
        NOT auto-refuse. Append an INFO string and proceed if
        `rendered_content_sha256` still matches on-disk (= user hasn't
        edited; safe to overwrite even with new templates).

        Returns RefreshResult with rendered + skipped + template-drift
        info lists + the freshly-computed `kernel_render_state` list.
        Caller (engine.run_update_identity) seals that list into
        scaffold-decision.json via `re_seal_decision_atomic`.
        """
        # Build path -> entry lookup for quick per-file decisions. None or
        # empty list signals brownfield/test-fixture flow with no prior state.
        prior_entries = prior_kernel_render_state or []
        prior_state = {
            entry["path"]: entry
            for entry in prior_entries
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
            # v2.1 Codex PR #50 post-review-2 P1 #2: honor `user_has_drift`
            # sealed by Case E "y" (`compute_current_on_disk_state`). When
            # the prior state's rendered_content_sha256 is the user's edit
            # SHA (not the canonical render SHA), the next on-disk read
            # would observe `current_disk_sha == prior_rendered_sha` and
            # falsely classify the file as "safe to overwrite" — silently
            # destroying the user's edit. The drift flag forces the
            # user-edit-detection branch live regardless of the SHA
            # match. Backward-compat: prior states without the flag fall
            # through to the existing SHA comparison.
            if entry.get("user_has_drift") is True:
                skipped.append(target)
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

        # Compute the new state for the rendered subset AND the unchanged
        # entries for skipped files (their state is unchanged on disk).
        #
        # Phase 11 hardening A2 (data-loss fix): for files in `skipped`
        # (user edited post-render), PRESERVE the prior
        # `rendered_content_sha256` from `prior_state` instead of
        # re-hashing the on-disk bytes. Re-hashing would store the
        # user's edit sha; the next /lp-update-identity invocation would
        # see `current_disk_sha == prior_rendered_sha` (because both are
        # now the user's edit sha), enter the "safe to overwrite" branch
        # at line ~243, and SILENTLY DESTROY the user's edit. Preserving
        # the prior sha keeps the user-edit-detection branch live across
        # invocations until the user explicitly resolves the drift.
        skipped_set = set(skipped)
        new_state_entries: list[dict] = []
        for template_name, output_relpath in KERNEL_FILES:
            target = cwd / output_relpath
            if not target.is_file():
                continue
            if target in skipped_set:
                prior_entry = prior_state.get(output_relpath)
                if (
                    isinstance(prior_entry, dict)
                    and prior_entry.get("rendered_content_sha256")
                    and prior_entry.get("source_template_sha256")
                ):
                    preserved: dict[str, Any] = {
                        "path": output_relpath,
                        "rendered_content_sha256": prior_entry["rendered_content_sha256"],
                        "source_template_sha256": prior_entry["source_template_sha256"],
                    }
                    # v2.1 Codex PR #50 post-review-2 P1 #2: preserve the
                    # `user_has_drift` flag across skipped refreshes so the
                    # consent boundary stays live until the user explicitly
                    # resolves the drift (e.g., via the deferred
                    # `--accept-drift` flag in BL-267).
                    if prior_entry.get("user_has_drift") is True:
                        preserved["user_has_drift"] = True
                    new_state_entries.append(preserved)
                    continue
                # Defensive fallback (should not happen given how `skipped`
                # is populated above): no prior_entry available, so we have
                # no choice but to re-hash. The next refresh's comparison
                # will skip again the moment the user touches the file.
            new_state_entries.append({
                "path": output_relpath,
                "rendered_content_sha256": sha256_bytes(target.read_bytes()),
                "source_template_sha256": self._template_sha256(template_name),
            })

        return RefreshResult(
            rendered=rendered,
            skipped_user_edits=skipped,
            template_drift_infos=template_drift_infos,
            kernel_render_state=new_state_entries,
        )


__all__ = ["KERNEL_FILES", "KernelRenderer", "RefreshResult"]
