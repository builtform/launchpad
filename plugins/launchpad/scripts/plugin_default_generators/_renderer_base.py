"""Shared rendering primitives for the v2.1 renderer split (V3 plan section 13.6).

Three single-purpose renderers (kernel_renderer, infrastructure_renderer,
workflow_config_renderer) subclass `RendererBase` and share:

  * Jinja Environment matching the existing canonical at
    `plugin-doc-generator.py:97-128` (autoescape posture preserved verbatim
    so the test_jinja2_autoescape regression contract continues to hold).
  * StrictUndefined plus keep_trailing_newline so missing identity fields
    fail loudly at render time and trailing newlines round-trip cleanly.
  * `sha256_file()` utility for manifest tracking (Phase 3+).
  * `atomic_write()` helper that wraps `atomic_io.atomic_write_replace`
    with command-name-aware sentinel files for crash recovery.
  * `identity_inject()` helper that takes the sealed identity dict from
    scaffold-decision.json and produces the Jinja context every kernel
    template can rely on (project_name, copyright_holder, email, repo_url,
    license, license_other_body, plus a derived current_year).
  * Filters: `shell_quote` (shlex.quote for bash contexts), `tojson` and
    `to_yaml_safe` (already part of Jinja stdlib for `tojson`; we add
    `to_yaml_safe` via PyYAML's safe_dump for YAML value injection).

Per Round 2 P1-N4 closure: the regression contract for autoescape lives
at `tests/test_renderer_base_jinja_autoescape.py` (Phase 2; new). The SSTI
gate asserts that an attacker-controlled identity value containing
`{{ 7*7 }}` lands as the literal string `{{ 7*7 }}` in rendered output,
NOT as `49` -- Jinja variable values are always strings, never re-parsed
as syntax, but the test pins the contract so a future autoescape change
cannot silently introduce SSTI.

Phase 8 deletes `plugin-doc-generator.py`; until then BOTH this module and
the legacy script source the autoescape posture from the same canonical
spec (the inline copy here mirrors the legacy source verbatim, with the
same comment explaining why HTML autoescape is not turned on globally).
"""
from __future__ import annotations

import datetime
import hashlib
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping

import jinja2

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import atomic_write_replace  # noqa: E402

# Generators root. Subdirectories at `kernel/`, `infrastructure/`, and
# `workflow-config/` each carry their own .j2 templates. The base class
# accepts a subdirectory name so each subclass binds to its template root.
GENERATORS_ROOT = Path(__file__).resolve().parent

# Phase 4 v2.1 (Slice F): per-adapter fragment root for stack-aware
# rendering. Outer templates live at `plugin_default_generators/stack_aware/`
# and `{% include %}` per-adapter fragments at
# `plugin_stack_adapters/<adapter>/templates/<name>.j2.fragment`.
STACK_FRAGMENTS_ROOT = _SCRIPTS_DIR / "plugin_stack_adapters"

# v2.1 active stack id closed enum (5 values). Stack-aware renderers MUST
# validate the incoming stack_id against this set BEFORE building the
# Environment so a bad value raises StackIdInvalidError instead of silently
# rendering a missing-fragment template error or, worse, looking up an
# attacker-controlled path traversal.
STACK_ID_ACTIVE_ENUM: frozenset[str] = frozenset({
    "ts_monorepo",
    "nextjs_standalone",
    "nextjs_fastapi",
    "astro",
    "generic",
})


class StackIdInvalidError(ValueError):
    """Raised when a stack_id outside `STACK_ID_ACTIVE_ENUM` reaches the
    stack-aware renderer. Phase 4 plan section 3.11 closed-enum guarantee."""


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

    Autoescape policy: HTML-extension-only via `select_autoescape`. Templates
    that ARE HTML (none today, but reserved) get autoescape automatically
    via the extension match. Markdown and YAML templates do NOT get
    autoescape because globally forcing it escapes normal text characters
    like `&`, `<`, `>` even when they appear in user-facing strings,
    producing artifacts like `R&amp;D` in rendered prose. The actual
    injection threat (a hostile value in detected manifests being
    re-evaluated as Jinja) is already prevented by Jinja's template model:
    variable values render as strings, never re-parsed as syntax.

    YAML templates use `tojson` or explicit yaml-safe quoting for any
    field where a string might collide with YAML syntax -- that pattern
    is the right tool for YAML escaping, not HTML autoescape.

    StrictUndefined fails loudly on missing variables at render time
    rather than silently emitting empty strings.

    Filter additions:
      - `shell_quote(value)`: shlex.quote-based escaping for bash contexts.
        Identity values flowing into shell scripts (e.g., `git config
        user.email "{{ identity.email | shell_quote }}"`) MUST use this
        filter. Plain `{{ identity.email }}` is unsafe in shell.
      - `to_yaml_safe(value)`: PyYAML safe_dump for YAML value injection.
    """
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
    return env


# Phase 4 v2.1 (Slice F) singleton stack-aware renderer environment. Reused
# across renders so id(env) is stable; tests assert this. The loader scope
# spans both `plugin_default_generators/stack_aware/` (outer templates) and
# `plugin_stack_adapters/` (fragment templates) so `{% include %}` directives
# can reach across via relative paths.
_STACK_AWARE_ENV: jinja2.Environment | None = None


def make_stack_aware_jinja_env() -> jinja2.Environment:
    """Singleton-cached Jinja Environment for stack-aware renders.

    Filter parity with `make_jinja_env` (shell_quote + to_yaml_safe + tojson)
    plus the `select_autoescape` posture preserved verbatim.
    """
    global _STACK_AWARE_ENV
    if _STACK_AWARE_ENV is not None:
        return _STACK_AWARE_ENV

    outer_root = GENERATORS_ROOT / "stack_aware"
    fragments_root = STACK_FRAGMENTS_ROOT
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader([
            jinja2.FileSystemLoader(str(outer_root)),
            jinja2.FileSystemLoader(str(fragments_root)),
        ]),
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
    return env


def _to_yaml_safe(value: Any) -> str:
    """PyYAML safe_dump filter for YAML value injection.

    Used in YAML templates where a string field might contain characters
    that collide with YAML syntax (colons, quotes, leading dashes).
    Emits a double-quoted YAML scalar with proper escaping.
    """
    import yaml  # type: ignore[import-not-found]
    # Use default_style='"' to force double-quoted output; default_flow_style=False
    # avoids JSON-like flow output for nested structures.
    return yaml.safe_dump(
        value,
        default_style='"',
        default_flow_style=False,
        allow_unicode=True,
    ).rstrip("\n")


def sha256_file(path: Path) -> str:
    """Compute the sha256 of a file's contents.

    Used by the bootstrap-manifest writer (Phase 3+) for the
    `source_template_sha256` and `rendered_content_sha256` fields. Pinning
    here so all renderers agree on the canonical hash function.
    """
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

    Derived helpers added on top of the raw identity dict:
      - `current_year`: integer (UTC) for copyright headers.
      - `license_url`: choosealicense.com URL for the license enum (None
        for "Other"; the license_other_body field carries the actual text).

    Returns a dict that templates render under `{{ identity.project_name }}`
    etc. plus `{{ current_year }}`.
    """
    license_value = identity.get("license", "Other")
    license_url = (
        f"https://choosealicense.com/licenses/{license_value.lower()}/"
        if license_value != "Other"
        else None
    )
    return {
        "identity": dict(identity),
        "current_year": datetime.datetime.now(datetime.timezone.utc).year,
        "license_url": license_url,
    }


class RendererBase:
    """Abstract base for the v2.1 renderer split.

    Subclasses bind to their template subdirectory by setting `TEMPLATE_SUBDIR`
    and then call `self.env.get_template(...)` for each render. Concrete
    renderers (kernel_renderer.KernelRenderer, infrastructure_renderer.
    InfrastructureRenderer, workflow_config_renderer.WorkflowConfigRenderer)
    are thin: they enumerate which templates to render where and pass through
    to the base.
    """

    TEMPLATE_SUBDIR: str = ""  # subclasses override (e.g., "kernel")

    def __init__(self) -> None:
        if not self.TEMPLATE_SUBDIR:
            raise ValueError(
                f"{type(self).__name__}.TEMPLATE_SUBDIR must be set"
            )
        self.env = make_jinja_env(self.TEMPLATE_SUBDIR)
        self.template_root = GENERATORS_ROOT / self.TEMPLATE_SUBDIR

    def render_to_string(
        self,
        template_name: str,
        identity: Mapping[str, Any],
        extra_context: Mapping[str, Any] | None = None,
    ) -> str:
        """Render a template with the identity context plus optional extras.

        `template_name` is relative to the renderer's TEMPLATE_SUBDIR. Extra
        context (passed by stack-aware renderers in Phase 4+) merges over
        the identity-derived defaults; stack-aware values can therefore
        override identity-derived values when they need to (e.g., adapter
        renderers may inject project-specific overrides).
        """
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
    ) -> tuple[str, str]:
        """Render and atomically write to `target`.

        Returns (rendered_text, rendered_sha256). The sha256 is the hash
        of the rendered bytes (after UTF-8 encoding) and feeds the
        `rendered_content_sha256` field of the bootstrap manifest (Phase 3+).
        """
        rendered = self.render_to_string(template_name, identity, extra_context)
        encoded = rendered.encode("utf-8")
        atomic_write_replace(target, encoded)
        return rendered, sha256_bytes(encoded)


__all__ = [
    "GENERATORS_ROOT",
    "STACK_FRAGMENTS_ROOT",
    "STACK_ID_ACTIVE_ENUM",
    "StackIdInvalidError",
    "RendererBase",
    "identity_inject",
    "make_jinja_env",
    "make_sandboxed_jinja_env",
    "make_stack_aware_jinja_env",
    "sha256_bytes",
    "sha256_file",
    "validate_stack_id",
]
