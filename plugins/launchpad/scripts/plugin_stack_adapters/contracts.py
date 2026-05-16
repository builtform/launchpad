"""Contracts for stack adapters.

Every concrete adapter (ts_monorepo, python_django, go_cli, generic) returns
TypedDicts defined here. The composer (polyglot.py) merges adapter outputs
against these same contracts. Unit tests in plugins/launchpad/scripts/tests/ validate every
adapter output against the contracts before the Jinja2 generator consumes it.

Without these contracts, adapters drift and StrictUndefined only catches the
drift at render time (per-stack, in production). The contracts push the check
to the static layer.

v2.1 additions
==============

The v2.1 dispatch surface adds an `Adapter` Protocol (runtime-checkable) and a
narrower `StackIdActive` Literal covering the 5 stacks the v2.1 pick-stack +
scaffold flow understands. The pre-existing TypedDicts model adapter *data*
output (consumed by the Jinja2 generator); the Protocol models adapter
*behavior* (consumed by `lp_scaffold_stack/engine.py` Step 4.5 + the
composition wrapper). They coexist by design: TypedDicts and Protocol have
disjoint concerns, and ABC was rejected to avoid forcing inheritance on
adapters that have no upstream (e.g., `ts_monorepo`).

`_UPSTREAM_SHA` constants for adapter wrap-and-overlay live in
`plugin_stack_adapters/pin_registry.py`. Adapters import via
`pin_registry.get_pin(adapter_id, sub_template_id)` only; per-adapter SHA
constants are forbidden (enforced by `tests/test_no_floating_tag_pins.py`).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Literal, NotRequired, Protocol, TypedDict, runtime_checkable

StackId = Literal[
    "ts_monorepo",
    "python_django",
    "go_cli",
    "generic",
    "astro",
    "fastapi",
    "rails",
    "hugo",
    "eleventy",
    "expo",
    # v2.0 catalog stack IDs (HANDSHAKE §11). next/django alias to the legacy
    # ts_monorepo / python_django adapters; hono and supabase route to
    # generic until dedicated adapters land in v2.1+.
    "next",
    "django",
    "hono",
    "supabase",
]

# v2.1 active dispatch enum: the closed set of stack ids the v2.1 pick-stack +
# scaffold flow understands. `StackId` (above) remains the v2.0 detection
# catalog; `StackIdActive` is a narrower Literal used by `Adapter` and by
# `lp_pick_stack`. Detector v2.2-candidate routing (rails, python_django, etc.)
# falls back to `generic` per Phase 4 plan §3.10 + §3.12.
StackIdActive = Literal[
    "ts_monorepo",
    "nextjs_standalone",
    "nextjs_fastapi",
    "astro",
    "generic",
]

# Phase 7 v2.1 (DA2 LOCKED): forward-reference type for stack ids the detector
# may emit but which lack an active `Adapter` Protocol implementation in v2.1.
# The renderer accepts these via the closed-enum gate at
# `plugin_default_generators/_renderer_base.py:STACK_ID_ACTIVE_ENUM`; adapter
# dispatch routes ids without an active Protocol implementation via `generic`
# per the existing v2.0 catalog-alias pattern (e.g. `polyglot.ADAPTERS["hono"]
# = generic`). v2.2 BL covers Adapter Protocol promotion for `rails_adapter`
# and ships concrete adapters for the remaining candidates.
#
# Intentional `StackId ∩ StackIdV22Candidate` overlap: `python_django` and
# `rails` appear in BOTH the v2.0 14-id `StackId` detection catalog AND this
# v2.1 candidate set. Catalog answers "may detector emit X?"; candidate
# answers "does X have an active Adapter Protocol implementation in v2.1?".
# The type-system surfaces are orthogonal in v2.1; v2.2 BL `StackId`
# narrowing folds catalog membership into the union and resolves the overlap.
# See Phase 7 plan §3.3 + tests/test_stack_coupling_refactors.py for the
# guard against accidental drift.
StackIdV22Candidate = Literal[
    "python_django",
    "python_generic",
    "nextjs_hono_cloudflare",
    "nextjs_trpc_prisma",
    "rails",
    # v2.1.6 BL-345 review fix (Codex P1 #2 + Greptile #2): `go_cli`
    # joins the candidate set. The `go_cli.py` adapter has shipped a
    # module-level `run()` since v2.0; the v2.1.6 stack-aware data
    # modules added `go_cli` coverage, and listing it here keeps the
    # `STACK_ID_ACTIVE_ENUM == StackIdActive | StackIdV22Candidate`
    # partition invariant intact.
    "go_cli",
]

# 4-policy enum (DA7 LOCKED) shared between bootstrap policy resolution and the
# Phase 4 OverlayConfig.conflict_policy field. Values match
# `lp_bootstrap.BootstrapPolicy` exactly; the duplication-by-Literal here keeps
# the contracts module free of an upward import into `lp_bootstrap`.
ConflictPolicy = Literal[
    "overwrite-if-unchanged",
    "merge-keys",
    "append-only",
    "overwrite-with-backup",
]

UnwrapStrategy = Literal["none", "nested_turborepo"]


class UpstreamTemplate(TypedDict):
    """Pointer to a pinned upstream template (resolved via pin_registry)."""

    adapter_id: StackIdActive
    sub_template_id: NotRequired[str | None]


class CompositionRule(TypedDict):
    """How adapter X composes with adapter Y in the composition wrapper.

    `workspace_name` is the directory under `apps/` the secondary adapter
    occupies. `conflict_policy` per top-level path lets adapters override the
    default `overwrite-if-unchanged` for files where merge / append makes
    sense (e.g., lefthook.yml -> merge-keys).
    """

    workspace_name: str
    conflict_policy: dict[str, ConflictPolicy]


class OverlayConfig(TypedDict):
    """Per-Phase-4 plan §3.3. The composition wrapper applies these to the
    upstream-scaffolded tree before workspace placement."""

    add: list[str]
    replace: list[str]
    remove: list[str]
    conflict_policy: dict[str, ConflictPolicy]


# Per-Codex P1-B harden: shared empty defaults for the Adapter Protocol
# placement-mapping fields. `MappingProxyType({})` is hashable + read-only,
# so all 5 adapters can reference the same module-level constant safely.
_EMPTY_WORKSPACE_MAP: Mapping[str, str] = MappingProxyType({})
_EMPTY_PACKAGE_PATHS: tuple[str, ...] = ()


def _validate_workspace_source_relpath(value: str, *, field_name: str) -> None:
    """Reject attacker-controlled path traversal in adapter-declared values.

    Mirrors the verbatim "attacker-controlled path traversal" comment pin from
    `_renderer_base.py:75-79`. Adapter-declared placement values are
    CODEOWNERS-trusted but we still validate at import time so a future drift
    fails closed.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str, got {type(value).__name__!r}")
    if value == "":
        # Empty string means "tempdir IS the workspace"; only valid as a
        # placement value when wrapped in a non-empty map. Reject up front.
        raise ValueError(
            f"{field_name} must not be empty; use an empty map to skip wrapping"
        )
    if value.startswith("/") or value.startswith("\\"):
        raise ValueError(f"{field_name}={value!r} must be a relative POSIX path")
    parts = value.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        raise ValueError(
            f"{field_name}={value!r} contains '..' segment "
            f"(attacker-controlled path traversal forbidden)"
        )
    if any(part == "" for part in parts[:-1]):
        # Disallow `//` and trailing absolute-style empties (POSIX).
        raise ValueError(f"{field_name}={value!r} contains empty path segment")


def _validate_workspace_source_map(m: Mapping[str, str], *, field_name: str) -> None:
    """Per-Codex P1-α: reject path-traversal in adapter-declared values."""
    for key, value in m.items():
        if not isinstance(key, str) or key == "":
            raise ValueError(
                f"{field_name} key {key!r} must be a non-empty workspace name"
            )
        _validate_workspace_source_relpath(value, field_name=f"{field_name}[{key!r}]")


def _validate_package_workspace_paths(
    paths: tuple[str, ...], *, field_name: str
) -> None:
    """Per-Codex P1-α: reject path-traversal in adapter-declared values."""
    if not isinstance(paths, tuple):
        raise TypeError(f"{field_name} must be tuple, got {type(paths).__name__!r}")
    for path in paths:
        _validate_workspace_source_relpath(path, field_name=field_name)


@runtime_checkable
class Adapter(Protocol):
    """v2.1 adapter behavior surface. See Phase 4 plan §3.3.

    Runtime-checkable so `isinstance(obj, Adapter)` works in tests and
    composition. ABC was rejected: ts_monorepo has no upstream and would carry
    abstract-method overrides for empty bodies.

    `workspace_source_map_single` and `workspace_source_map_composition` map
    workspace_name (e.g. "app", "api") to the relative path inside the
    adapter-rendered tempdir whose subtree is moved to
    `<root>/apps/<workspace_name>/`. Both default to empty mapping meaning
    "tempdir IS the workspace" (current behavior for ts_monorepo, generic,
    astro). `package_workspace_paths` lists tempdir-relative subtrees that
    are lifted to top-level siblings (e.g. nextjs_standalone declares
    `("packages",)` so the upstream's nested `packages/` ends up at
    `composition_root/packages/`).
    """

    stack_id: StackIdActive
    upstream: UpstreamTemplate | None
    manifest_schema_version: str
    workspace_name: str | None
    unwrap_strategy: UnwrapStrategy
    composes_with: dict[StackIdActive, CompositionRule]
    workspace_source_map_single: Mapping[str, str]
    workspace_source_map_composition: Mapping[str, str]
    package_workspace_paths: tuple[str, ...]

    def scaffold_into(self, tempdir: Path) -> None: ...
    def apply_overlay(self, tempdir: Path) -> None: ...


# Per-Phase-4 plan §3.11.5(b): per-module error bridging.
class AdapterScaffoldError(RuntimeError):
    """Base class for adapter-level scaffold failures.

    Per-adapter modules subclass for module-specific failure modes; the engine
    bridge in `bridge_to_scaffold_error` preserves `.reason / .path /
    .remediation` while normalizing the exception class to
    `ScaffoldStepFailedError`.
    """

    def __init__(self, *, reason: str, path: Path | None, remediation: str) -> None:
        super().__init__(remediation)
        self.reason = reason
        self.path = path
        self.remediation = remediation


class ScaffoldStepFailedError(RuntimeError):
    """Engine-boundary normalized error used by `lp_scaffold_stack/engine.py`
    Step 4.5 to surface failures from any per-module exception class while
    preserving the structured triple."""

    def __init__(self, *, reason: str, path: Path | None, remediation: str) -> None:
        super().__init__(remediation)
        self.reason = reason
        self.path = path
        self.remediation = remediation


def bridge_to_scaffold_error(exc: BaseException) -> ScaffoldStepFailedError:
    """Bridge any per-module error (Adapter / Composition / TemplateCache) into
    a single engine-boundary exception that preserves the structured triple
    (`reason`, `path`, `remediation`).

    Phase 3 surfaced the need for this pattern when a typed exception raised
    inside a sub-module wasn't caught by the outer `except RuntimeError`
    branch unless the engine bridged it explicitly. See Phase 3 closure record
    `manifest_writer` -> engine bridging fix.
    """
    reason = getattr(exc, "reason", type(exc).__name__)
    path = getattr(exc, "path", None)
    remediation = getattr(exc, "remediation", str(exc) or type(exc).__name__)
    return ScaffoldStepFailedError(reason=reason, path=path, remediation=remediation)


class TechStackInfo(TypedDict):
    """Backing data for docs/architecture/TECH_STACK.md."""

    language: str  # "TypeScript", "Python", "Go", "Unknown"
    runtime: str  # "Node.js 20", "Python 3.12", "Go 1.22", etc.
    package_manager: str  # "pnpm", "poetry", "go mod", ""
    frameworks: list[str]  # ["Next.js 15", "Hono", "Prisma"]
    database: str | None  # "PostgreSQL", None
    ci: str | None  # "GitHub Actions", None


class BackendInfo(TypedDict):
    """Backing data for docs/architecture/BACKEND_STRUCTURE.md.

    v2.1.6 BL-349 added the `static_capable` field as a required attribute.
    Every adapter's `describe_backend()` must populate it.

    `static_capable=True` ⇒ BACKEND_STRUCTURE.md is rendered with
    "static site, no backend" framing — `framework` / `api_style` /
    `routes_dir` describe the static-site equivalent (e.g.,
    "Astro static" / "n/a" / "src/pages/") rather than a server
    framework. Hugo / Eleventy: always True. Astro: True when
    `astro.config.{js,mjs,ts}` does not set `output: 'server'` or
    `'hybrid'`. Next.js: True when `output: 'export'`. Backend-required
    stacks (Django / FastAPI / Hono / Rails): always False.
    """

    framework: str  # "Hono", "Django", "Gin", "Express"
    api_style: str  # "REST", "GraphQL", "tRPC"
    routes_dir: str  # "apps/api/src/routes/", "myapp/urls.py"
    models_dir: str | None  # "packages/db/prisma/", "myapp/models.py", None
    auth_pattern: str | None  # "session", "JWT", "OAuth", None
    static_capable: bool  # v2.1.6 BL-349 — see docstring


class FrontendInfo(TypedDict):
    """Backing data for docs/architecture/FRONTEND_GUIDELINES.md (v1.1) and
    docs/architecture/APP_FLOW.md.

    Returns None from adapters for backend-only stacks.
    """

    framework: str  # "Next.js 15 App Router", "React SPA"
    styling: str  # "Tailwind CSS v4", "CSS Modules"
    component_dir: str  # "apps/web/components/"
    routing: str  # "App Router", "React Router"


class AppFlowInfo(TypedDict):
    """Backing data for docs/architecture/APP_FLOW.md. Returns None for
    backend-only stacks (detector reports no frontend)."""

    entry_routes: list[str]  # ["/", "/signin", "/dashboard"]
    auth_flow: str | None  # "Magic link", "OAuth (GitHub)", None
    primary_journeys: list[str]  # ["Onboarding", "Purchase", "Support"]


class ProductContextInfo(TypedDict):
    """Backing data for docs/architecture/PRD.md framing. Stack-influenced
    but not stack-defined — PRD is mostly product content. This surfaces the
    tech-framing line (e.g., "TypeScript monorepo" vs "Python backend")."""

    stack_summary: str  # One-line tech summary for the PRD intro
    deployment_target: str | None  # "Vercel + Render", "AWS ECS", None


class CommandsConfig(TypedDict):
    """Backing data for config.yml `commands:` section seed.

    Every value is a list (always-array contract). Empty list = skip.
    """

    test: list[str]
    typecheck: list[str]
    lint: list[str]
    format: list[str]
    build: list[str]


class PipelineOverrides(TypedDict, total=False):
    """Stack-specific overrides to config.yml `pipeline:` defaults.

    Only fields the adapter wants to override from defaults need appear.
    Most adapters only override design/frontend-specific toggles.
    """

    design_enabled: NotRequired[bool]  # False for backend-only
    test_browser_enabled: NotRequired[bool]  # False for backend-only
    frontend_docs_enabled: NotRequired[bool]  # False for backend-only


class AdapterOutput(TypedDict):
    """Aggregated output from a single adapter. The composer iterates these
    across multiple adapters when the detector reports polyglot."""

    stack_id: StackId
    tech_stack: TechStackInfo
    backend: BackendInfo
    frontend: FrontendInfo | None
    app_flow: AppFlowInfo | None
    product_context: ProductContextInfo
    commands: CommandsConfig
    pipeline_overrides: PipelineOverrides


# Exported for adapter implementations
__all__ = [
    "StackId",
    "StackIdActive",
    "StackIdV22Candidate",
    "ConflictPolicy",
    "UnwrapStrategy",
    "UpstreamTemplate",
    "CompositionRule",
    "OverlayConfig",
    "Adapter",
    "AdapterScaffoldError",
    "ScaffoldStepFailedError",
    "bridge_to_scaffold_error",
    "TechStackInfo",
    "BackendInfo",
    "FrontendInfo",
    "AppFlowInfo",
    "ProductContextInfo",
    "CommandsConfig",
    "PipelineOverrides",
    "AdapterOutput",
    "_EMPTY_WORKSPACE_MAP",
    "_EMPTY_PACKAGE_PATHS",
    "_validate_workspace_source_map",
    "_validate_package_workspace_paths",
]
