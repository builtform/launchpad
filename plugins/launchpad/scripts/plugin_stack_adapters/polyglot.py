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
    "python_django",
    "rails",
    "astro",
    "hugo",
    "expo",
    "fastapi",
    "eleventy",
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
