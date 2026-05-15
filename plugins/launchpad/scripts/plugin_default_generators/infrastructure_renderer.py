"""Infrastructure renderer (V3 plan section 17.1 Phase 3 / Slice B).

Thin subclass of `RendererBase` that ships the 30-path infrastructure
overlay rendered by `/lp-bootstrap` at greenfield scaffold time AND by
brownfield `/lp-define` auto-invocation. Templates live at
`plugin_default_generators/infrastructure/<name>.j2`; the inventory is
pinned in `lp_bootstrap.INFRASTRUCTURE_FILES`.

Behavioural contract (locked in plan section 3.10):

  * `render_template(target_relpath, identity)` returns the rendered bytes
    for a single target; engine fast-path uses this to compute
    `rendered_sha256` before the policy dispatcher decides to write.
  * `render_all(cwd, identity, only_paths=None)` materializes every path
    (or the `only_paths` subset) atomically and returns
    `[(target_path, rendered_sha256), ...]`. Policy is NOT consulted; the
    engine's render loop wraps `render_template` with the per-file policy
    applicator instead. `render_all` is convenient for greenfield-no-manifest
    paths and for tests that want a single-call materialize.
  * `chmod` runs AFTER `os.replace()` (harden B8) belt-and-braces on the
    mode set by `atomic_write_replace` so the final on-disk mode matches
    `FILE_MODES[target_relpath]` regardless of any tempfile-mode race.
  * `_validate_gitignore_content()` runs the allowlist scan (harden A12)
    on the rendered `.gitignore` content; unknown entries are logged to
    `.launchpad/bootstrap-warnings.json` (do NOT block; closed allowlist
    breaks legitimate brownfield additions).
  * `_RENDERER` singleton lives in `lp_bootstrap.engine` (Slice C) per
    harden B4 to share the Jinja environment across `run_bootstrap()`
    calls in a single Python process.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_bootstrap import (  # noqa: E402
    INFRASTRUCTURE_FILES,
    INFRASTRUCTURE_TARGETS,
    BootstrapErrorCode,
)

from ._renderer_base import RendererBase, sha256_bytes  # noqa: E402

# --- Per-module exception (parallel to manifest_writer / policy) -----------


class InfrastructureRenderError(RuntimeError):
    """Render-side failure raised by this module.

    Carries `.reason: BootstrapErrorCode` so the engine wires structured
    `BootstrapError` instances into `BootstrapResult.errors` per section
    3.7.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: BootstrapErrorCode,
        path: Path | None = None,
        remediation: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path
        self.remediation = remediation


# --- Target -> template lookup -------------------------------------------

_TARGET_TO_TEMPLATE: dict[str, str] = {
    target: template for template, target, _policy, _mode in INFRASTRUCTURE_FILES
}


# --- .gitignore allowlist scan (harden A12) ------------------------------

# Initial allowlist. Each entry is a regex compiled below; matches anywhere
# in a stripped line. The pattern set is intentionally permissive: we want
# to flag rendered output that drifts away from the v2.1 design (e.g., a
# template change that adds an unexpected entry), NOT block legitimate
# brownfield additions. `.gitignore` policy is `append-only`; the renderer
# scan ONLY validates the freshly-rendered content, not the post-merge
# disk state.
_GITIGNORE_ALLOWLIST_REGEXES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^\.launchpad(/|$)",
        r"^\.harness(/|$)",
        r"^node_modules(/|$)",
        r"^dist(/|$)",
        r"^\*\.log$",
        r"^\.env(\..+)?$",
        r"^coverage(/|$)",
        # Defaults the .gitignore template ships with that are unambiguously
        # safe for any project type.
        r"^\.cache(/|$)",
        r"^\.next(/|$)",
        r"^\.turbo(/|$)",
        r"^\.pnpm-store(/|$)",
        r"^\.tsbuildinfo$",
        r"^\*\.tsbuildinfo$",
        r"^\*\.pyc$",
        r"^__pycache__(/|$)",
        r"^build(/|$)",
        r"^\.DS_Store$",
        r"^generated_images(/|$)",
        # Per Codex PR #50 P1-B harden P1-ζ: scaffold tempdir parent for
        # composition + single-adapter wrapping.
        r"^\.lp-tmp(/|$)",
        r"^# .*$",  # comments
        r"^$",  # blank lines
    )
)


def _is_allowlisted_gitignore_entry(line: str) -> bool:
    """Return True iff `line` matches any allowlist regex."""
    return any(rx.match(line) for rx in _GITIGNORE_ALLOWLIST_REGEXES)


# --- CI workflow self-consistency assertion (BL-355) ---------------------

# Closed enum of GitHub Actions step inputs that name a file the action
# expects to find at the project root. If a rendered workflow names one of
# these inputs, the named file MUST also be rendered by /lp-bootstrap to
# the same project root — otherwise the action aborts on the first push
# and every downstream step is skipped.
#
# Each entry pairs the action's `uses:` prefix (matched as a substring of
# the full `uses:` value so the sha-pinning suffix doesn't break matching)
# with the input key that references a file.
_WORKFLOW_FILE_REF_INPUTS: tuple[tuple[str, str], ...] = (
    ("actions/setup-node", "node-version-file"),
    ("actions/setup-python", "python-version-file"),
    ("actions/setup-go", "go-version-file"),
    ("ruby/setup-ruby", "ruby-version-file"),
)


def _validate_workflow_self_consistency(
    batch: Mapping[Path, bytes],
    cwd: Path,
) -> list[str]:
    """Walk every rendered `.github/workflows/*.yml` in `batch`; for each
    step, assert any file-referencing input names a file that is also
    in `batch`. Returns a list of human-readable error strings; empty
    when self-consistent.

    BL-355 v2.1.5 — catches the BL-353 + BL-354 class at /lp-bootstrap
    write time: rendered workflow files referencing files /lp-bootstrap
    doesn't render. Without this check, the next workflow-template
    rotation that adds `python-version-file` / `go-version-file` /
    `ruby-version-file` replays the same first-push-CI-red failure
    pattern as BL-353 / BL-354.

    Implementation notes:
      * Uses yaml.safe_load (no construction of arbitrary Python objects)
      * Tolerant of workflow shapes — `on:` triggers may be string / list
        / dict; steps may live under `jobs.<id>.steps` only
      * Substring match on `uses:` so the sha-pin suffix (e.g.,
        `@<sha> # v4.0.0`) doesn't break the action-id match
      * The named file is matched as POSIX path relative to `cwd`
    """
    import yaml  # local import; PyYAML is a hard dep but lazily loaded

    batch_relpaths: set[str] = set()
    for abs_path in batch:
        try:
            batch_relpaths.add(abs_path.relative_to(cwd).as_posix())
        except ValueError:
            continue

    errors: list[str] = []
    for abs_path, content in batch.items():
        try:
            relpath = abs_path.relative_to(cwd).as_posix()
        except ValueError:
            continue
        if not relpath.startswith(".github/workflows/"):
            continue
        if not (relpath.endswith(".yml") or relpath.endswith(".yaml")):
            continue
        try:
            doc = yaml.safe_load(content)
        except yaml.YAMLError:
            # Malformed YAML is not the BL-355 self-consistency concern;
            # the workflow may legitimately contain unquoted `${{ }}`
            # expressions or test fixtures may inject deliberate Jinja
            # markup. The CI-config-lint job (separate gate) catches
            # genuinely-broken workflows. Skip self-consistency here.
            continue
        if not isinstance(doc, dict):
            continue
        jobs = doc.get("jobs", {})
        if not isinstance(jobs, dict):
            continue
        for _job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps", [])
            if not isinstance(steps, list):
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                uses = step.get("uses", "")
                if not isinstance(uses, str) or not uses:
                    continue
                with_block = step.get("with", {})
                if not isinstance(with_block, dict):
                    continue
                for action_prefix, input_key in _WORKFLOW_FILE_REF_INPUTS:
                    if action_prefix not in uses:
                        continue
                    file_ref = with_block.get(input_key)
                    if not isinstance(file_ref, str) or not file_ref:
                        continue
                    # Strip a leading `./` if present (NOT `lstrip("./")` —
                    # that would strip a leading `.` from `.nvmrc`!).
                    normalized = file_ref.removeprefix("./") or file_ref
                    if (
                        normalized not in batch_relpaths
                        and not (cwd / normalized).exists()
                    ):
                        errors.append(
                            f"{relpath}: step `uses: {uses}` references "
                            f"`{input_key}: {file_ref}` but {file_ref!r} is "
                            f"neither in the bootstrap render batch nor on "
                            f"disk; CI will fail on first push. Add the file "
                            f"to INFRASTRUCTURE_FILES or remove the input."
                        )
    return errors


def _validate_gitignore_content(rendered_text: str) -> list[str]:
    """Scan rendered `.gitignore` content; return descriptive warnings.

    The renderer surfaces these warnings up to the engine, which calls
    `lp_bootstrap.policy.record_warnings()` to persist them. Returns an
    empty list when every entry is allowlisted.
    """
    warnings: list[str] = []
    for lineno, raw in enumerate(rendered_text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if _is_allowlisted_gitignore_entry(line):
            continue
        warnings.append(
            f"gitignore: unrecognized entry at line {lineno}: {line!r} "
            f"(allowlist sourced from harden A12)"
        )
    return warnings


# --- Renderer subclass ---------------------------------------------------


class InfrastructureRenderer(RendererBase):
    """Render the 30 infrastructure files for a project's identity block."""

    TEMPLATE_SUBDIR = "infrastructure"

    def template_for_target(self, target_relpath: str) -> str:
        """Resolve `target_relpath` -> its `.j2` template name."""
        try:
            return _TARGET_TO_TEMPLATE[target_relpath]
        except KeyError as exc:
            raise InfrastructureRenderError(
                f"unknown infrastructure target {target_relpath!r}",
                reason=BootstrapErrorCode.UNKNOWN_REFRESH_PATH,
                path=Path(target_relpath),
                remediation=(
                    f"target must be one of the {len(INFRASTRUCTURE_TARGETS)} "
                    f"paths in INFRASTRUCTURE_FILES; see /lp-bootstrap --help"
                ),
            ) from exc

    def render_target(
        self,
        target_relpath: str,
        identity: Mapping[str, Any],
    ) -> bytes:
        """Render a single target's template; return UTF-8 bytes.

        Engine fast-path (harden A16) uses this to compute rendered_sha
        before the policy dispatcher decides to atomic-write. Failure
        (template missing, identity injection error) raises
        `InfrastructureRenderError(TEMPLATE_RENDER_FAILED)`.
        """
        template_name = self.template_for_target(target_relpath)
        try:
            text = self.render_to_string(template_name, identity)
        except FileNotFoundError as exc:
            raise InfrastructureRenderError(
                f"template not found: {template_name}",
                reason=BootstrapErrorCode.TEMPLATE_NOT_FOUND,
                path=Path(template_name),
                remediation=(
                    "reinstall the LaunchPad plugin; the v2.1 plugin ships "
                    "all 30 infrastructure templates"
                ),
            ) from exc
        except Exception as exc:  # noqa: BLE001 -- map jinja errors uniformly
            raise InfrastructureRenderError(
                f"template render failed for {target_relpath}: {exc}",
                reason=BootstrapErrorCode.TEMPLATE_RENDER_FAILED,
                path=Path(target_relpath),
                remediation=(
                    "inspect the template variables; identity values may be "
                    "missing or malformed"
                ),
            ) from exc
        return text.encode("utf-8")

    def render_targets(self, context: Mapping[str, Any]) -> Iterator[tuple[Path, str]]:
        """Yield `(absolute_target_path, rendered_text)` for each
        infrastructure template. Context carries `cwd: Path`,
        `identity: Mapping`, and optional `only_paths: Sequence[str]`.

        Phase 8.5 plan section 3.11 (DA1' = a2): subclass implementation
        of `render_targets` so `render_batch` can buffer the full overlay
        before the secret-scanner gate fires.
        """
        cwd: Path = context["cwd"]
        identity: Mapping[str, Any] = context["identity"]
        only_paths = context.get("only_paths")

        if only_paths is not None:
            allowed = set(only_paths)
        else:
            allowed = None

        for template_relpath, target_relpath, _policy, _mode in INFRASTRUCTURE_FILES:
            if allowed is not None and target_relpath not in allowed:
                continue
            text = self.render_to_string(template_relpath, identity)
            yield cwd / target_relpath, text

    def render_all(
        self,
        cwd: Path,
        identity: Mapping[str, Any],
        only_paths: Sequence[str] | None = None,
    ) -> list[tuple[Path, str]]:
        """Render every path (or the `only_paths` subset) under `cwd` via
        the buffered-batch flow.

        Phase 8.5 plan section 3.11 (DA1' = a2): full overlay renders to
        memory, the secret-scanner gate runs across the whole batch, and
        only on a clean scan does any file land on disk. Per-file POSIX
        modes from `FILE_MODES` flow through `write_batch`'s
        `file_modes` arg; `chmod_after_replace=True` belt-and-braces on
        the tempfile mode (harden B8).

        Returns `[(target_path, rendered_sha256), ...]` in the
        INFRASTRUCTURE_FILES iteration order.

        `only_paths` accepts the canonical target relpaths from
        `INFRASTRUCTURE_TARGETS`. Unknown paths raise
        `InfrastructureRenderError(UNKNOWN_REFRESH_PATH)`.

        Note: the engine never calls this directly during `/lp-bootstrap`
        because the per-file policy dispatcher needs to compare on-disk
        sha and manifest sha before writing. `render_all` is reserved for
        greenfield-no-manifest paths (every file gets written verbatim)
        and for tests.
        """
        if only_paths is not None:
            unknown = [p for p in only_paths if p not in INFRASTRUCTURE_TARGETS]
            if unknown:
                raise InfrastructureRenderError(
                    f"unknown render path(s): {unknown!r}",
                    reason=BootstrapErrorCode.UNKNOWN_REFRESH_PATH,
                    path=Path(unknown[0]),
                    remediation=(
                        "render path must be in INFRASTRUCTURE_FILES; see "
                        "/lp-bootstrap --help for the canonical list"
                    ),
                )

        # Build the file_modes mapping in the same iteration order as
        # INFRASTRUCTURE_FILES so write_batch preserves on-disk modes.
        allowed = set(only_paths) if only_paths is not None else None
        target_to_mode: dict[Path, int] = {}
        for _template, target_relpath, _policy, mode in INFRASTRUCTURE_FILES:
            if allowed is not None and target_relpath not in allowed:
                continue
            target_to_mode[cwd / target_relpath] = mode

        # Render full batch to memory.
        batch = self.render_batch(
            [{"cwd": cwd, "identity": identity, "only_paths": only_paths}]
        )

        # Side-effect: validate gitignore content (warnings only).
        gitignore_target = cwd / ".gitignore"
        if gitignore_target in batch:
            _ = _validate_gitignore_content(
                batch[gitignore_target].decode("utf-8", errors="replace")
            )

        # BL-355 v2.1.5: workflow self-consistency assertion. Refuse the
        # whole batch if any rendered workflow names a `*-version-file`
        # the batch (or cwd) doesn't provide. This catches the
        # BL-353/BL-354 class at write time — before the user pushes,
        # before CI runs, before any failure round-trip.
        consistency_errors = _validate_workflow_self_consistency(batch, cwd)
        if consistency_errors:
            joined = "\n  - ".join(consistency_errors)
            raise InfrastructureRenderError(
                f"workflow self-consistency check failed:\n  - {joined}",
                reason=BootstrapErrorCode.TEMPLATE_RENDER_FAILED,
                path=cwd / ".github" / "workflows",
                remediation=(
                    "every workflow `*-version-file:` input must reference a "
                    "file rendered by /lp-bootstrap. Add the file to "
                    "INFRASTRUCTURE_FILES (with a matching `.j2` template) "
                    "or drop the input from the workflow template."
                ),
            )

        # Atomic write-all-or-none after secret-scanner gate.
        patterns_file = cwd / ".launchpad" / "secret-patterns.txt"
        allowlist_path = cwd / ".launchpad" / "secret-allowlist.txt"
        self.write_batch(
            batch,
            cwd=cwd,
            file_modes=target_to_mode,
            chmod_after_replace=True,
            patterns_file=patterns_file,
            allowlist_path=allowlist_path,
        )

        return [
            (target, sha256_bytes(batch[target]))
            for target in target_to_mode
            if target in batch
        ]

    def gitignore_warnings(self, identity: Mapping[str, Any]) -> list[str]:
        """Return allowlist-scan warnings for the rendered `.gitignore`.

        Engine consumes this during the render loop and forwards the
        warnings to `policy.record_warnings()`. Cheap (single template
        render) so the engine can call it inside its fast-path branch
        without a second-render penalty.
        """
        text = self.render_to_string("gitignore.j2", identity)
        return _validate_gitignore_content(text)


__all__ = [
    "INFRASTRUCTURE_TARGETS",
    "InfrastructureRenderError",
    "InfrastructureRenderer",
    "_validate_gitignore_content",
    "_validate_workflow_self_consistency",
]
