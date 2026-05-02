"""Polyglot composer.

NOT a peer adapter. When the detector reports multiple stacks (e.g.
TS + Python + Next.js), this module runs each concrete adapter and merges
their AdapterOutput objects per the documented rules:

  - arrays concat (dedup-preserving order)
  - dicts merge by key with precedence: ts_monorepo > python_django > go_cli
    for conflicting scalar fields
  - describe_*() prose results concatenate with one-line section dividers
  - CommandsConfig lists concat (polyglot test suites run serially)
  - PipelineOverrides take the OR of restrictive flags (if any adapter says
    frontend_docs_enabled=False, the composite respects that — safer default)

Concrete adapters never call into this module; detection → composer orchestration
happens at the /lp-define layer.
"""
from __future__ import annotations

from . import (
    astro_adapter,
    eleventy_adapter,
    expo_adapter,
    fastapi_adapter,
    generic,
    go_cli,
    hugo_adapter,
    python_django,
    rails_adapter,
    ts_monorepo,
)
from .contracts import (
    AdapterOutput,
    AppFlowInfo,
    BackendInfo,
    CommandsConfig,
    FrontendInfo,
    PipelineOverrides,
    ProductContextInfo,
    StackId,
    TechStackInfo,
)

# Precedence order for conflicting scalar values. Earlier wins. v2.0 ordering:
# (1) full-stack TypeScript (ts_monorepo) wins on shared scalars; (2) framework
# fullstack/orchestrate stacks next (next, rails, django); (3) framework
# orchestrate single-purpose (astro, hono, hugo, expo, fastapi, eleventy);
# (4) the legacy go_cli + generic baselines absorb anything unmatched. The
# precedence drives which adapter "owns" conflicting scalar values like
# `commands.dev` when the user composes a polyglot project.
STACK_PRECEDENCE: tuple[StackId, ...] = (
    "ts_monorepo",
    "next",          # aliases to ts_monorepo
    "python_django",
    "django",        # aliases to python_django
    "rails",
    "astro",
    "hugo",
    "expo",
    "fastapi",
    "eleventy",
    "hono",          # aliases to generic until a hono-specific adapter ships
    "supabase",      # aliases to generic until a supabase-specific adapter ships
    "go_cli",
    "generic",
)

ADAPTERS = {
    "ts_monorepo": ts_monorepo,
    "python_django": python_django,
    "go_cli": go_cli,
    "generic": generic,
    "astro": astro_adapter,
    "fastapi": fastapi_adapter,
    "rails": rails_adapter,
    "hugo": hugo_adapter,
    "eleventy": eleventy_adapter,
    "expo": expo_adapter,
    # v2.0 catalog aliases — wire the canonical catalog stack IDs to the
    # appropriate adapter so receipt-driven dispatch (PR #41 cycle 3 #1)
    # never silently falls back to generic for a real catalog stack.
    "next": ts_monorepo,
    "django": python_django,
    "hono": generic,
    "supabase": generic,
}


def _dedup_concat(*lists: list[str]) -> list[str]:
    """Concat lists preserving first-seen order; drop duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        for item in lst:
            if item not in seen:
                seen.add(item)
                out.append(item)
    return out


def _merge_tech_stack(outputs: list[AdapterOutput]) -> TechStackInfo:
    """Merge TechStackInfo across adapters. Language/runtime list becomes
    multi-valued (e.g. 'TypeScript + Python')."""
    primary = outputs[0]["tech_stack"]
    languages = _dedup_concat(*[[o["tech_stack"]["language"]] for o in outputs])
    runtimes = _dedup_concat(*[[o["tech_stack"]["runtime"]] for o in outputs if o["tech_stack"]["runtime"]])
    pkgs = _dedup_concat(*[[o["tech_stack"]["package_manager"]] for o in outputs if o["tech_stack"]["package_manager"]])
    frameworks = _dedup_concat(*[o["tech_stack"]["frameworks"] for o in outputs])

    # Database: first non-None by precedence
    database = next((o["tech_stack"]["database"] for o in outputs if o["tech_stack"]["database"]), None)
    ci = next((o["tech_stack"]["ci"] for o in outputs if o["tech_stack"]["ci"]), None)

    return TechStackInfo(
        language=" + ".join(languages),
        runtime=" / ".join(runtimes) if runtimes else "",
        package_manager=" + ".join(pkgs) if pkgs else "",
        frameworks=frameworks,
        database=database,
        ci=ci,
    )


def _merge_backend(outputs: list[AdapterOutput]) -> BackendInfo:
    """Backend takes the highest-precedence adapter's fields. Polyglot projects
    typically have one clear primary backend; composer picks it.

    This is a deliberate simplification for v1 — dual-backend (e.g. TS API +
    Python worker) is v1.1 territory.
    """
    primary = outputs[0]["backend"]
    return primary


def _merge_frontend(outputs: list[AdapterOutput]) -> FrontendInfo | None:
    """First non-None frontend wins (respects precedence order)."""
    for o in outputs:
        if o["frontend"] is not None:
            return o["frontend"]
    return None


def _merge_app_flow(outputs: list[AdapterOutput]) -> AppFlowInfo | None:
    for o in outputs:
        if o["app_flow"] is not None:
            return o["app_flow"]
    return None


def _merge_product_context(outputs: list[AdapterOutput]) -> ProductContextInfo:
    summaries = [o["product_context"]["stack_summary"] for o in outputs]
    deployment = next(
        (o["product_context"]["deployment_target"] for o in outputs
         if o["product_context"]["deployment_target"]),
        None,
    )
    return ProductContextInfo(
        stack_summary=" + ".join(summaries),
        deployment_target=deployment,
    )


def _merge_commands(outputs: list[AdapterOutput]) -> CommandsConfig:
    """Concatenate commands across adapters, preserving order.

    Polyglot test suites run serially — e.g. ['pnpm test', 'pytest']
    for a TS + Python repo.
    """
    def merge_field(name: str) -> list[str]:
        return _dedup_concat(*[o["commands"][name] for o in outputs])

    return CommandsConfig(
        test=merge_field("test"),
        typecheck=merge_field("typecheck"),
        lint=merge_field("lint"),
        format=merge_field("format"),
        build=merge_field("build"),
    )


def _merge_pipeline_overrides(outputs: list[AdapterOutput]) -> PipelineOverrides:
    """Two-policy merge for pipeline-override flags:

    1. design_enabled / test_browser_enabled — ENABLED-WINS.
       In a TS+Python polyglot, the TS adapter provides a frontend that
       design-review and browser tests should still cover, even though the
       Python (Django) adapter marks them False on its own. These two
       flags represent CI workflow gates whose presence in the polyglot
       composite tracks the union of capabilities, not the intersection.

       Implementation: leave the flag unset on the composite if ANY
       adapter has it True / unset (default-True), meaning downstream
       consumers see the default-True. Only set False when EVERY adapter
       explicitly says False.

    2. frontend_docs_enabled — RESTRICTIVE-WINS (legacy contract).
       This flag controls whether the canonical-doc generator emits
       frontend-shaped sections in TECH_STACK.md and BACKEND_STRUCTURE.md
       prose. Backend-heavy adapters intentionally restrict it to avoid
       contradictory doc shape; the existing test contract enforces this.
    """
    result: PipelineOverrides = PipelineOverrides()

    # Enabled-wins for the two CI workflow flags.
    for key in ("design_enabled", "test_browser_enabled"):
        any_enabled = False
        all_false = True
        for o in outputs:
            ov = o["pipeline_overrides"]
            if key not in ov:
                any_enabled = True
                all_false = False
                continue
            if ov[key] is not False:
                any_enabled = True
                all_false = False
        if any_enabled:
            continue
        if all_false:
            result[key] = False  # type: ignore[literal-required]

    # Restrictive-wins for frontend_docs_enabled.
    for o in outputs:
        if o["pipeline_overrides"].get("frontend_docs_enabled") is False:
            result["frontend_docs_enabled"] = False
            break

    return result


def compose(stack_ids: list[StackId]) -> AdapterOutput:
    """Orchestrate adapter runs + merge according to composer rules.

    Raises ValueError if stack_ids is empty.
    """
    if not stack_ids:
        raise ValueError("stack_ids must contain at least one stack")

    # Sort per precedence (ts > python > go > generic), keeping only requested
    ordered = [s for s in STACK_PRECEDENCE if s in stack_ids]
    if not ordered:
        ordered = ["generic"]

    outputs = [ADAPTERS[s].run() for s in ordered]

    if len(outputs) == 1:
        # Single-stack fast path: no merging needed, return as-is
        return outputs[0]

    # Multi-stack: merge
    return AdapterOutput(
        stack_id=ordered[0],  # Primary stack for record-keeping
        tech_stack=_merge_tech_stack(outputs),
        backend=_merge_backend(outputs),
        frontend=_merge_frontend(outputs),
        app_flow=_merge_app_flow(outputs),
        product_context=_merge_product_context(outputs),
        commands=_merge_commands(outputs),
        pipeline_overrides=_merge_pipeline_overrides(outputs),
    )


# Roles that legitimately own the BackendInfo slot in /lp-define-rendered
# architecture docs. Layered in priority order — fullstack wins over backend
# wins over backend-managed (managed = Supabase/Firebase, present alongside a
# regular backend in some categories).
_BACKEND_ROLES = ("fullstack", "backend", "backend-managed")
# Roles that legitimately own the FrontendInfo slot. frontend-main wins over
# frontend (default) wins over frontend-dashboard (the secondary surface in
# multi-frontend categories).
_FRONTEND_ROLES = ("frontend-main", "frontend", "frontend-dashboard")


def _select_by_role(
    layer_outputs: list[tuple[dict, AdapterOutput]],
    priority_roles: tuple[str, ...],
) -> AdapterOutput | None:
    """Return the first (layer, adapter_out) pair whose role is in
    priority_roles, walking priorities first then layer order."""
    for role in priority_roles:
        for layer, out in layer_outputs:
            if str(layer.get("role", "")) == role:
                return out
    return None


def compose_with_layers(layers: list[dict]) -> AdapterOutput:
    """Role-aware multi-stack composer (PR #41 cycle 11 #1 closure — Codex
    P1).

    Same merge semantics as `compose()` for the stack-precedence-driven
    fields (tech stack, commands, pipeline overrides), but the
    role-bearing fields are sourced from the role-matched layer:

    - `backend`: layer with role ∈ (`fullstack`, `backend`, `backend-managed`)
    - `frontend`: layer with role ∈ (`frontend-main`, `frontend`, `frontend-dashboard`)
    - `app_flow`: same priority as frontend (frontend layer's app flow)

    Falls back to the precedence-based selection from `compose()` if no
    role-matched layer is present (e.g., legacy receipts without `role`
    field, or all-backend / all-frontend topologies).

    Each layer is also responsible for path-rewriting via the
    `_rewrite_adapter_paths` post-processor in plugin-doc-generator.py;
    this composer doesn't do path rewrites itself (the caller is the
    receipt loader, which has the cwd context).

    `layers` entries must have `stack` (str). `role` and `path` are
    optional — when absent, falls back to precedence-based selection.
    """
    if not layers:
        raise ValueError("layers must contain at least one entry")

    stack_ids: list[StackId] = []
    for layer in layers:
        sid = str(layer.get("stack", ""))
        if sid:
            stack_ids.append(sid)  # type: ignore[arg-type]

    # Run each adapter once; layer_outputs preserves the receipt's original
    # layer ordering so role lookups can disambiguate primary/secondary.
    layer_outputs: list[tuple[dict, AdapterOutput]] = [
        (layer, ADAPTERS.get(str(layer.get("stack", "")), generic).run())
        for layer in layers
    ]

    # Stack-precedence-driven merges still operate on a deduplicated, sorted
    # set so the existing _merge_* helpers behave identically.
    ordered_unique = [s for s in STACK_PRECEDENCE if s in stack_ids]
    if not ordered_unique:
        ordered_unique = ["generic"]
    precedence_outputs = [ADAPTERS[s].run() for s in ordered_unique]

    if len(layer_outputs) == 1:
        return layer_outputs[0][1]

    backend_out = _select_by_role(layer_outputs, _BACKEND_ROLES)
    frontend_out = _select_by_role(layer_outputs, _FRONTEND_ROLES)

    backend = backend_out["backend"] if backend_out else _merge_backend(precedence_outputs)
    frontend = (
        frontend_out["frontend"]
        if frontend_out and frontend_out["frontend"] is not None
        else _merge_frontend(precedence_outputs)
    )
    app_flow = (
        frontend_out["app_flow"]
        if frontend_out and frontend_out["app_flow"] is not None
        else _merge_app_flow(precedence_outputs)
    )

    return AdapterOutput(
        stack_id=ordered_unique[0],
        tech_stack=_merge_tech_stack(precedence_outputs),
        backend=backend,
        frontend=frontend,
        app_flow=app_flow,
        product_context=_merge_product_context(precedence_outputs),
        commands=_merge_commands(precedence_outputs),
        pipeline_overrides=_merge_pipeline_overrides(precedence_outputs),
    )
