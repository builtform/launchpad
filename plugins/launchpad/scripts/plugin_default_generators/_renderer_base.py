"""Shared rendering primitives for the v2.1 renderer split (V3 plan section 13.6).

Subclasses bind to a `TEMPLATE_SUBDIR` (e.g., `"kernel"`, `"infrastructure"`)
or set it to `"."` to load templates directly from `GENERATORS_ROOT` (used
by the v2.1 /lp-define orchestrator for the canonical PRD/TECH_STACK/
APP_FLOW/BACKEND_STRUCTURE/SECTION_REGISTRY/config.yml/agents.yml render).

Three single-purpose renderers (kernel_renderer, infrastructure_renderer,
lp_define orchestrator) share:

  * Jinja Environment with HTML-extension-only autoescape via
    `select_autoescape` (StrictUndefined; keep_trailing_newline). The
    test_renderer_base_jinja_autoescape regression contract pins this
    posture so a future change cannot silently introduce SSTI or
    HTML-escape Markdown text.
  * StrictUndefined plus keep_trailing_newline so missing identity fields
    fail loudly at render time and trailing newlines round-trip cleanly.
  * Buffered-batch flow per Phase 8.5 plan section 3.11 (DA1' = a2):
    `render_batch(contexts) -> dict[Path, bytes]` (in-memory only),
    `scan_batch(batch) -> list[SecretMatch]` (full-batch secret-scanner
    over rendered content; allowlist-aware), `write_batch(batch) -> None`
    (atomic write-all-or-none after scan_batch returns no findings).
    Subclasses implement `render_targets(context)` and never call
    `atomic_write_replace` directly. The handshake-lint enforces this
    via an ALLOWLIST-based rule restricted to
    `_renderer_base.py + lp_bootstrap/policy.py + atomic_io.py`.
  * `sha256_file()` / `sha256_bytes()` utilities for manifest tracking.
  * `identity_inject()` helper that takes the sealed identity dict from
    scaffold-decision.json and produces the Jinja context every kernel
    template can rely on (project_name, copyright_holder, email, repo_url,
    license, license_other_body, plus a derived current_year).
  * Filters: `shell_quote` (shlex.quote for bash contexts), `tojson` and
    `to_yaml_safe` (already part of Jinja stdlib for `tojson`; we add
    `to_yaml_safe` via PyYAML's safe_dump for YAML value injection).

Phase 8.5 plan section 3.11 also forbids subclasses from overriding
`render_to_path` / `render_batch` / `scan_batch` / `write_batch`. The
v2.1 /lp-define orchestrator (`lp_define_runner.py`) supersedes
`plugin-doc-generator.py` (deleted in Phase 8.5 Slice E) and is the only
public entry point that builds an in-memory render batch outside the
kernel + infrastructure renderers.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import shlex
import sys
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

import jinja2

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import (  # noqa: E402
    atomic_write_replace_batch,
)

# Generators root. Subdirectories at `kernel/`, `infrastructure/`, and
# `workflow-config/` each carry their own .j2 templates. The base class
# accepts a subdirectory name so each subclass binds to its template root;
# `"."` selects GENERATORS_ROOT directly (used by the /lp-define
# orchestrator in Phase 8.5).
GENERATORS_ROOT = Path(__file__).resolve().parent

# Phase 4 v2.1 (Slice F): per-adapter fragment root for stack-aware
# rendering. Outer templates live at `plugin_default_generators/stack_aware/`
# and `{% include %}` per-adapter fragments at
# `plugin_stack_adapters/<adapter>/templates/<name>.j2.fragment`.
STACK_FRAGMENTS_ROOT = _SCRIPTS_DIR / "plugin_stack_adapters"

# v2.1 active stack id closed enum. Stack-aware renderers MUST validate the
# incoming stack_id against this set BEFORE building the Environment so a
# bad value raises StackIdInvalidError instead of silently rendering a
# missing-fragment template error or, worse, looking up an
# attacker-controlled path traversal.
#
# Phase 6 v2.1: `rails` added as detector groundwork. No Rails-specific
# reviewer ships in v2.1; framework-axis wire-through + Rails reviewers
# arrive in v2.2 BL.
#
# Phase 7 v2.1 (DA5): reconciled to V3 §8.1
# `frozenset(StackIdActive) | frozenset(StackIdV22Candidate)` (10 ids). The
# renderer accepts the union; adapter dispatch routes ids without an
# active `Adapter` Protocol implementation via `generic` per the existing
# v2.0 catalog-alias pattern. The reconciliation+partition invariant is
# guarded by `tests/test_stack_coupling_refactors.py::
# test_stack_id_active_enum_partition_invariant` (drift OR silent
# active↔candidate reclassification → fail).
STACK_ID_ACTIVE_ENUM: frozenset[str] = frozenset(
    {
        # StackIdActive (v2.1 active dispatch)
        "ts_monorepo",
        "nextjs_standalone",
        "nextjs_fastapi",
        "astro",
        "generic",
        # StackIdV22Candidate (detector may emit; adapter dispatch routes via
        # `generic` for ids without an active Adapter Protocol implementation)
        "python_django",
        "python_generic",
        "nextjs_hono_cloudflare",
        "nextjs_trpc_prisma",
        "rails",
    }
)


class StackIdInvalidError(ValueError):
    """Raised when a stack_id outside `STACK_ID_ACTIVE_ENUM` reaches the
    stack-aware renderer. Phase 4 plan section 3.11 closed-enum guarantee."""


class SecretScannerViolation(RuntimeError):
    """Raised by `write_batch` when `scan_batch` returns at least one
    finding. Carries the structured findings list + the count of refused
    writes for caller-side reporting (Phase 8.5 plan section 3.11)."""

    def __init__(
        self,
        findings: list,
        refused_count: int,
        message: str,
    ) -> None:
        super().__init__(message)
        self.findings = findings
        self.refused_count = refused_count


def validate_stack_id(stack_id: str) -> str:
    """Phase 4 plan section 3.11 closed-enum gate. Raise on miss.

    Returns the stack_id unchanged on accept so callers can use this as a
    pass-through validator inline.
    """
    if stack_id not in STACK_ID_ACTIVE_ENUM:
        raise StackIdInvalidError(
            f"stack_id {stack_id!r} not in v2.1 active enum "
            f"{sorted(STACK_ID_ACTIVE_ENUM)!r}"
        )
    return stack_id


def make_jinja_env(template_subdir: str) -> jinja2.Environment:
    """Build the Jinja2 Environment for a renderer subdirectory.

    `template_subdir == "."` loads templates directly from
    `GENERATORS_ROOT` (used by the v2.1 /lp-define orchestrator).

    Autoescape policy: HTML-extension-only via `select_autoescape`.
    Templates that ARE HTML (none today, but reserved) get autoescape
    automatically via the extension match. Markdown and YAML templates
    do NOT get autoescape because globally forcing it escapes normal text
    characters like `&`, `<`, `>` even when they appear in user-facing
    strings, producing artifacts like `R&amp;D` in rendered prose. The
    actual injection threat (a hostile value in detected manifests being
    re-evaluated as Jinja) is already prevented by Jinja's template
    model: variable values render as strings, never re-parsed as syntax.

    YAML templates use `tojson` or explicit yaml-safe quoting for any
    field where a string might collide with YAML syntax -- that pattern
    is the right tool for YAML escaping, not HTML autoescape.

    StrictUndefined fails loudly on missing variables at render time
    rather than silently emitting empty strings.

    Filter additions:
      - `shell_quote(value)`: shlex.quote-based escaping for bash contexts.
      - `to_yaml_safe(value)`: PyYAML safe_dump for YAML value injection.
    """
    if template_subdir in ("", "."):
        template_root = GENERATORS_ROOT
    else:
        template_root = GENERATORS_ROOT / template_subdir
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_root)),
        autoescape=jinja2.select_autoescape(
            enabled_extensions=("html", "htm", "xml"),
            default_for_string=False,
            default=False,
        ),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["shell_quote"] = lambda v: shlex.quote(str(v))
    env.filters["to_yaml_safe"] = _to_yaml_safe
    env.filters["markdown_safe"] = _markdown_safe
    return env


# Phase 4 v2.1 (Slice F) singleton stack-aware renderer environment. Reused
# across renders so id(env) is stable; tests assert this. The loader scope
# spans both `plugin_default_generators/stack_aware/` (outer templates) and
# `plugin_stack_adapters/` (fragment templates) so `{% include %}` directives
# can reach across via relative paths.
_STACK_AWARE_ENV: jinja2.Environment | None = None


def make_stack_aware_jinja_env() -> jinja2.Environment:
    """Singleton-cached Jinja Environment for stack-aware renders."""
    global _STACK_AWARE_ENV
    if _STACK_AWARE_ENV is not None:
        return _STACK_AWARE_ENV

    outer_root = GENERATORS_ROOT / "stack_aware"
    fragments_root = STACK_FRAGMENTS_ROOT
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [
                jinja2.FileSystemLoader(str(outer_root)),
                jinja2.FileSystemLoader(str(fragments_root)),
            ]
        ),
        autoescape=jinja2.select_autoescape(
            enabled_extensions=("html", "htm", "xml"),
            default_for_string=False,
            default=False,
        ),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["shell_quote"] = lambda v: shlex.quote(str(v))
    env.filters["to_yaml_safe"] = _to_yaml_safe
    env.filters["markdown_safe"] = _markdown_safe
    _STACK_AWARE_ENV = env
    return env


def make_sandboxed_jinja_env() -> jinja2.SandboxedEnvironment:
    """SandboxedEnvironment factory for `.sh.j2` templates.

    Phase 4 plan section 3.11: shell-script templates run under
    SandboxedEnvironment so a hostile identity value cannot reach
    process-control attributes during render. Filter parity with
    `make_jinja_env` (shell_quote / to_yaml_safe / tojson) so callers can
    swap envs without code changes.
    """
    from jinja2.sandbox import SandboxedEnvironment

    env = SandboxedEnvironment(
        autoescape=jinja2.select_autoescape(
            enabled_extensions=("html", "htm", "xml"),
            default_for_string=False,
            default=False,
        ),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["shell_quote"] = lambda v: shlex.quote(str(v))
    env.filters["to_yaml_safe"] = _to_yaml_safe
    env.filters["markdown_safe"] = _markdown_safe
    return env


def _to_yaml_safe(value: Any) -> str:
    """PyYAML safe_dump filter for YAML value injection.

    Used in YAML templates where a string field might contain characters
    that collide with YAML syntax (colons, quotes, leading dashes).
    Emits a double-quoted YAML scalar with proper escaping.
    """
    import yaml  # type: ignore[import-not-found]

    return yaml.safe_dump(
        value,
        default_style='"',
        default_flow_style=False,
        allow_unicode=True,
    ).rstrip("\n")


# Phase 1+2 retroactive amendment A6: 13 CommonMark active characters that
# corrupt downstream Markdown rendering and enable `[link](javascript:...)`
# style injection in GitHub UI when an identity value lands inside a
# Markdown template body. Escape with backslash-prefix per CommonMark.
# Backslash is escaped FIRST so subsequent backslash-prefixed escapes are
# not themselves escaped a second time.
_MARKDOWN_SAFE_CHARS = (
    "\\",
    "*",
    "_",
    "[",
    "]",
    "(",
    ")",
    "<",
    ">",
    "`",
    "!",
    "#",
    "|",
)


def _markdown_safe(value: Any) -> str:
    """Escape CommonMark active characters with backslash-prefix.

    Idempotent on already-escaped input only at the per-character level:
    a string `\\*` (backslash + asterisk) becomes `\\\\\\*` (escape the
    backslash + escape the asterisk) on a second pass. Templates apply
    this filter exactly once at the boundary; downstream rendering does
    not re-apply.
    """
    text = "" if value is None else str(value)
    for ch in _MARKDOWN_SAFE_CHARS:
        text = text.replace(ch, "\\" + ch)
    return text


def sha256_file(path: Path) -> str:
    """Compute the sha256 of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute the sha256 of an in-memory bytes value (rendered content)."""
    return hashlib.sha256(data).hexdigest()


def identity_inject(identity: Mapping[str, Any]) -> dict[str, Any]:
    """Build the Jinja context for kernel/infrastructure templates.

    v2.1.5 BL-353 + BL-354: `default_pnpm_version` and `default_node_version`
    are surfaced from `plugin_stack_adapters._constants` so the rendered
    `.github/workflows/ci.yml` (pnpm/action-setup `version:` input) and
    `.nvmrc` (Node version pin consumed by `actions/setup-node` via
    `node-version-file:`) both resolve at render time. Single source of
    truth — bumping a tool version touches one file.
    """
    from plugin_stack_adapters._constants import (
        DEFAULT_NODE_VERSION,
        DEFAULT_PNPM_VERSION,
    )

    license_value = identity.get("license", "Other")
    license_url = (
        f"https://choosealicense.com/licenses/{license_value.lower()}/"
        if license_value != "Other"
        else None
    )
    return {
        "identity": dict(identity),
        "current_year": datetime.datetime.now(datetime.UTC).year,
        "license_url": license_url,
        "default_pnpm_version": DEFAULT_PNPM_VERSION,
        "default_node_version": DEFAULT_NODE_VERSION,
    }


class RendererBase:
    """Abstract base for the v2.1 renderer split.

    Subclasses bind to their template subdirectory by setting `TEMPLATE_SUBDIR`
    and implement `render_targets(context)` to yield `(target_absolute_path,
    rendered_text)` pairs. Public batch flow:

      * `render_batch(contexts) -> dict[Path, bytes]`: in-memory only;
        does NOT touch disk.
      * `scan_batch(batch, *, patterns_file=None, allowlist_path=None,
        template_sources=None) -> list[SecretMatch]`: secret scanner over
        the full batch; returns ALL findings.
      * `write_batch(batch, *, file_modes=None, ...) -> None`: atomic
        write-all-or-none after scan_batch returns no findings.

    Phase 8.5 plan section 3.11 forbids subclasses from overriding any of
    these protected methods OR `render_to_path` (so the secret-scanner
    gate cannot be bypassed at any caller layer). The handshake-lint test
    asserts.
    """

    TEMPLATE_SUBDIR: str = ""  # subclasses override (e.g., "kernel"; "." for root)

    # Phase 8.5 plan section 3.11 closed-set of protected method names.
    # `test_no_renderer_subclass_overrides_protected_methods` enforces.
    PROTECTED_METHODS: frozenset[str] = frozenset(
        {
            "render_batch",
            "scan_batch",
            "write_batch",
            "render_to_path",
        }
    )

    def __init__(self) -> None:
        if not self.TEMPLATE_SUBDIR:
            raise ValueError(f"{type(self).__name__}.TEMPLATE_SUBDIR must be set")
        self.env = make_jinja_env(self.TEMPLATE_SUBDIR)
        if self.TEMPLATE_SUBDIR in ("", "."):
            self.template_root = GENERATORS_ROOT
        else:
            self.template_root = GENERATORS_ROOT / self.TEMPLATE_SUBDIR

    # ------------------------------------------------------------------
    # Read-only render primitives (kept for backward compat)
    # ------------------------------------------------------------------

    def render_to_string(
        self,
        template_name: str,
        identity: Mapping[str, Any],
        extra_context: Mapping[str, Any] | None = None,
    ) -> str:
        """Render a template with the identity context plus optional extras."""
        ctx = identity_inject(identity)
        if extra_context:
            ctx.update(extra_context)
        template = self.env.get_template(template_name)
        return template.render(**ctx)

    def render_to_path(
        self,
        template_name: str,
        target: Path,
        identity: Mapping[str, Any],
        extra_context: Mapping[str, Any] | None = None,
        *,
        cwd: Path,
    ) -> tuple[str, str]:
        """Render and atomically write to `target` via the buffered-batch
        gate. Backwards-compat wrapper: callers that previously rendered
        a single file now also get the secret-scanner gate, just operating
        on a 1-item batch.

        Returns (rendered_text, rendered_sha256).

        Phase 8.5 plan section 3.11: render_to_path is a thin wrapper
        over `render_batch + write_batch` so the gate fires here too.
        v2.1.0 atomic_io symlink-rejection plan §3.3: `cwd` is the
        engine-boundary `trusted_root` propagated to atomic_io.
        """
        rendered = self.render_to_string(template_name, identity, extra_context)
        encoded = rendered.encode("utf-8")
        batch = {target: encoded}
        self.write_batch(batch, cwd=cwd)
        return rendered, sha256_bytes(encoded)

    # ------------------------------------------------------------------
    # Buffered-batch flow (Phase 8.5 plan section 3.11; DA1' = a2)
    # ------------------------------------------------------------------

    def render_targets(self, context: Mapping[str, Any]) -> Iterator[tuple[Path, str]]:
        """Subclass-overridable: yield `(absolute_target_path, rendered_text)`
        pairs for the given context. Called by `render_batch`.

        Default implementation raises NotImplementedError; subclasses that
        use `render_batch` MUST override.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.render_targets must be overridden "
            "before render_batch can be called"
        )

    def render_batch(self, contexts: Iterable[Mapping[str, Any]]) -> dict[Path, bytes]:
        """Render every target across every context to an in-memory dict.
        Does NOT touch disk -- the Phase 8.5 plan section 3.11 invariant
        (DA1' = a2 buffered batch + refuse-all on any finding).
        """
        rendered: dict[Path, bytes] = {}
        for context in contexts:
            for target_path, content_str in self.render_targets(context):
                rendered[Path(target_path)] = content_str.encode("utf-8")
        return rendered

    def scan_batch(
        self,
        batch: Mapping[Path, bytes],
        *,
        patterns_file: Path | None = None,
        allowlist_path: Path | None = None,
        template_sources: Mapping[Path, str] | None = None,
    ) -> list:
        """Run the secret scanner over the full rendered batch; return all
        findings across all files. Allowlist mechanisms (Phase 8.5 plan
        section 3.9 DA4) are consulted before findings are returned.
        """
        # Sibling imports stay inside the method so the renderer module
        # itself does not pull the scanner at import time.
        from plugin_stack_adapters.secret_scanner import (
            load_patterns,
            scan,
        )

        from plugin_default_generators.secret_allowlist import (
            filter_allowlisted,
        )

        if patterns_file is None:
            # Phase 8.5 DA5: relative-path lookup is the caller's job.
            # Without a hint we fall through to bundled patterns.
            patterns = load_patterns(None)
        else:
            patterns = load_patterns(patterns_file)

        all_findings: list = []
        for target_path, content_bytes in batch.items():
            text = content_bytes.decode("utf-8", errors="replace")
            raw = scan(text, patterns=patterns, source=str(target_path))
            template_source = (
                template_sources.get(target_path)
                if template_sources is not None
                else None
            )
            kept = filter_allowlisted(
                raw,
                target_path,
                text,
                template_source=template_source,
                allowlist_path=allowlist_path,
            )
            all_findings.extend(kept)
        return all_findings

    def write_batch(
        self,
        batch: Mapping[Path, bytes],
        *,
        cwd: Path,
        file_modes: Mapping[Path, int] | None = None,
        chmod_after_replace: bool = False,
        patterns_file: Path | None = None,
        allowlist_path: Path | None = None,
        template_sources: Mapping[Path, str] | None = None,
    ) -> None:
        """Two-phase atomic write of `batch`.

        Phase 0 — secret-scan gate (Phase 8.5 DA1' = a2):
          Run `scan_batch`; on any finding, NO files are written and
          `SecretScannerViolation` is raised with the full findings list.

        Phase 1 — stage (atomic — partial failure leaves all targets untouched):
          For each (target, content) pair, write `content` to a sibling
          `.<basename>.<random>.tmp` file in the target's parent dir,
          fsync the tempfile, set the per-file mode. If ANY stage fails,
          unlink ALL staged tempfiles and raise — original target files
          on disk are byte-for-byte unchanged.

        Phase 2 — rename (best-effort — same-FS atomic renames make full-batch
        failure rare but not impossible):
          Atomic-rename each staged tempfile to its final target path.
          If a rename fails mid-batch (rare; same-FS guaranteed by the
          tempfile-in-target-parent layout), the failed-rename file
          remains as `.tmp` on disk and any prior renames remain at
          final paths. Caller surface: this post-condition is exposed
          via the underlying `OSError` propagation; the operator
          recovers by either completing the rename manually or running
          /lp-bootstrap --recover.

        v2.1 Codex PR #50 post-review P1: this two-phase shape replaces
        the previous sequential `atomic_write_replace` loop, which
        committed each write immediately and could leave the batch in a
        partial state when a later write failed.

        `file_modes`: optional per-target file mode (e.g.,
        infrastructure_renderer's per-file POSIX modes). When provided,
        the staged tempfile is fchmod'd to that mode before rename and
        (with chmod_after_replace true) os.chmod fires after rename as
        belt-and-braces.
        """
        findings = self.scan_batch(
            batch,
            patterns_file=patterns_file,
            allowlist_path=allowlist_path,
            template_sources=template_sources,
        )
        if findings:
            sources = {getattr(f, "source", None) for f in findings}
            sources.discard(None)
            raise SecretScannerViolation(
                findings=findings,
                refused_count=len(batch),
                message=(
                    f"Secret scanner found {len(findings)} match(es) "
                    f"across {len(sources) or len(batch)} file(s); "
                    f"refused all {len(batch)} writes."
                ),
            )

        modes = file_modes or {}
        # Two-phase atomic write: stage all targets first, then rename.
        # See `atomic_write_replace_batch` in atomic_io.py for the
        # phase-1 (atomic) / phase-2 (best-effort) contract.
        # v2.1.0 atomic_io symlink-rejection: thread `cwd` as
        # `trusted_root` so any symlinked ancestor on the write path
        # raises OSError before tempfiles are staged.
        atomic_write_replace_batch(batch, modes=modes, trusted_root=cwd)
        if chmod_after_replace:
            for target_path in batch.keys():
                mode = modes.get(target_path)
                if mode is None:
                    continue
                try:
                    os.chmod(target_path, mode)
                except OSError:
                    pass


__all__ = [
    "GENERATORS_ROOT",
    "STACK_FRAGMENTS_ROOT",
    "STACK_ID_ACTIVE_ENUM",
    "RendererBase",
    "SecretScannerViolation",
    "StackIdInvalidError",
    "identity_inject",
    "make_jinja_env",
    "make_sandboxed_jinja_env",
    "make_stack_aware_jinja_env",
    "sha256_bytes",
    "sha256_file",
    "validate_stack_id",
]
