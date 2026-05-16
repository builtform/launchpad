"""v2.1.6 BL-349 Codex P2 #4 regression: polyglot `_merge_backend` must
prefer a `static_capable=False` backend over a higher-precedence
`static_capable=True` one.

Pre-v2.1.6 behavior: `_merge_backend` returned the first output in
precedence order. Astro (precedence #6, `static_capable=True`) outranks
FastAPI (precedence #9, `static_capable=False`) in `STACK_PRECEDENCE`,
so a polyglot Astro + FastAPI composition silently hid the FastAPI
backend behind Astro's "static site — no backend" framing in the
rendered BACKEND_STRUCTURE.md.

Post-v2.1.6: when ANY adapter contributes `static_capable=False`, the
composer picks that one (first such in precedence order); all-static
compositions fall back to the original first-wins behavior.
"""
from __future__ import annotations

from plugin_stack_adapters import polyglot
from plugin_stack_adapters.contracts import AdapterOutput, BackendInfo


def _make_output(stack_id: str, *, static_capable: bool, framework: str) -> AdapterOutput:
    """Minimal AdapterOutput fixture with only the fields `_merge_backend`
    inspects."""
    backend: BackendInfo = {
        "framework": framework,
        "runtime": "n/a",
        "port": None,
        "routes": [],
        "data_models": [],
        "auth_strategy": None,
        "external_services": [],
        "static_capable": static_capable,
    }
    return AdapterOutput(
        stack_id=stack_id,  # pyright: ignore[reportArgumentType]
        tech_stack={"frameworks": [], "runtimes": [], "databases": [], "infra": []},
        backend=backend,
        frontend=None,
        app_flow=None,
        product_context={"stack_summary": stack_id, "deployment_target": None},
        commands={
            "dev": [],
            "build": [],
            "test": [],
            "lint": [],
            "format": [],
            "typecheck": [],
            "migrate": [],
        },
        pipeline_overrides={},
    )


def test_merge_backend_prefers_static_capable_false_over_higher_precedence_true():
    """The headline Codex P2 #4 case: Astro outranks FastAPI in
    precedence, but FastAPI is the real backend. The merger must pick
    FastAPI."""
    astro = _make_output("astro", static_capable=True, framework="Astro")
    fastapi = _make_output("fastapi", static_capable=False, framework="FastAPI")
    merged = polyglot._merge_backend([astro, fastapi])
    assert merged["static_capable"] is False
    assert merged["framework"] == "FastAPI"


def test_merge_backend_all_static_falls_back_to_first_wins():
    """All-static compositions (e.g., Astro + Hugo) have no
    `static_capable=False` to prefer; the merger correctly falls back to
    the original first-wins rule."""
    astro = _make_output("astro", static_capable=True, framework="Astro")
    hugo = _make_output("hugo", static_capable=True, framework="Hugo")
    merged = polyglot._merge_backend([astro, hugo])
    assert merged["static_capable"] is True
    assert merged["framework"] == "Astro"


def test_merge_backend_first_static_capable_false_wins_among_multiple():
    """When MULTIPLE adapters contribute `static_capable=False`, the
    merger picks the first one in precedence order (the caller has
    already ordered inputs by `STACK_PRECEDENCE`)."""
    fastapi = _make_output("fastapi", static_capable=False, framework="FastAPI")
    rails = _make_output("rails", static_capable=False, framework="Rails")
    merged = polyglot._merge_backend([fastapi, rails])
    assert merged["framework"] == "FastAPI"


def test_compose_astro_plus_fastapi_renders_fastapi_backend():
    """End-to-end via `compose()`: an Astro + FastAPI composition must
    surface FastAPI in `output.backend`, NOT Astro's static-site stub.
    This is the integration-level expression of the Codex P2 #4 fix."""
    out = polyglot.compose(["astro", "fastapi"])  # pyright: ignore[reportArgumentType]
    assert out["backend"]["static_capable"] is False
    assert "FastAPI" in out["backend"]["framework"] or "fastapi" in out["backend"]["framework"].lower()


# ---------------------------------------------------------------------------
# v2.1.6 BL-345 round-2 review fix (Codex P1 #1): nextjs_standalone and
# python_generic must route to the `generic` adapter, NOT to ts_monorepo
# or python_django. ts_monorepo renders Turborepo + Prisma + Hono +
# apps/web framing; python_django renders Django ORM + collectstatic
# commands — both actively wrong for standalone-Next / non-Django Python
# projects. Routing to generic produces Unknown-framework placeholders
# (honest framing) until dedicated adapters ship.
# ---------------------------------------------------------------------------


def test_nextjs_standalone_routes_to_generic_adapter():
    """`polyglot.ADAPTERS["nextjs_standalone"]` resolves to the `generic`
    module, not `ts_monorepo`. Pre round-2 it was `ts_monorepo`, which
    rendered Turborepo + Prisma docs for single-app Next.js projects."""
    from plugin_stack_adapters import generic as generic_mod
    assert polyglot.ADAPTERS["nextjs_standalone"] is generic_mod


def test_python_generic_routes_to_generic_adapter():
    """`polyglot.ADAPTERS["python_generic"]` resolves to the `generic`
    module, not `python_django`. Pre round-2 it was `python_django`,
    which rendered Django ORM + collectstatic docs for FastAPI / Flask /
    plain Python projects."""
    from plugin_stack_adapters import generic as generic_mod
    assert polyglot.ADAPTERS["python_generic"] is generic_mod


def test_compose_nextjs_standalone_solo_produces_unknown_framework():
    """A standalone-Next composition (single stack id `nextjs_standalone`)
    must produce Unknown-framework framing, NOT ts_monorepo's
    Next+Tailwind+Turborepo framing."""
    out = polyglot.compose(["nextjs_standalone"])  # pyright: ignore[reportArgumentType]
    # `generic.describe_backend()` returns framework="Unknown"; we accept
    # that exact string or any non-"Next.js" framing as proof the route
    # no longer falls through to ts_monorepo.
    assert out["backend"]["framework"] != "Next.js"
    assert out["backend"]["framework"] != "Hono"  # ts_monorepo's backend framework
    assert out["tech_stack"]["language"] == "Unknown"


def test_compose_python_generic_solo_produces_unknown_framework():
    """A non-Django Python composition (single stack id `python_generic`)
    must produce Unknown-framework framing, NOT python_django's Django
    + Postgres framing."""
    out = polyglot.compose(["python_generic"])  # pyright: ignore[reportArgumentType]
    assert out["backend"]["framework"] != "Django"
    assert out["tech_stack"]["language"] == "Unknown"


def test_compose_generic_static_capable_is_false():
    """v2.1.6 BL-349 round-2 review fix (Greptile P1): the `generic`
    adapter contributes `static_capable=False`, NOT True. This restores
    server-side placeholder framing in BACKEND_STRUCTURE.md for projects
    routed through `generic` (hono / supabase aliases, unknown stacks,
    and post-round-2 nextjs_standalone / python_generic)."""
    out = polyglot.compose(["generic"])  # pyright: ignore[reportArgumentType]
    assert out["backend"]["static_capable"] is False
