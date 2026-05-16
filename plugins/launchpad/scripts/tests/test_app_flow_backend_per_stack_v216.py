"""BL-348 + BL-349 v2.1.6 — APP_FLOW.md placeholder hints + BackendInfo.static_capable.

BL-348: every adapter's `describe_app_flow()` previously emitted concrete
fake routes (`["/", "/about", "/blog"]` for Astro; `["/", "/signin",
"/dashboard"]` for ts_monorepo). Those values rendered into APP_FLOW.md
as if they were detected from the user's project — they weren't. v2.1.6
ships minimal placeholders (`["/"]` plus an explicit "shape via
/lp-shape-section" hint in `primary_journeys`) so APP_FLOW.md is
honestly a stub.

BL-349: every adapter's `describe_backend()` previously assumed a server
backend exists. For static-output stacks (Astro static, Hugo, Eleventy,
Expo mobile, generic) this is wrong. v2.1.6 adds a `static_capable: bool`
field to `BackendInfo`; the renderer reads it and emits "static site,
no backend" framing for static-capable stacks.

Test coverage (numbering matches BL-348 + BL-349 spec):
- (1) Every adapter's `describe_backend()` populates `static_capable`
  (the new field is required, not optional).
- (2) Per-stack expected `static_capable` value matches the table:
  Astro / Hugo / Eleventy / Expo / Generic → True;
  FastAPI / Django / Rails / TS-monorepo / Go-CLI → False.
- (3) Every adapter's `describe_app_flow()` (when non-None) emits
  `entry_routes=["/"]` and a primary_journeys entry containing the
  `[Placeholder` marker.
- (4) Adapters that previously returned `None` (fastapi, generic,
  python_django, go_cli) still return None — backend-only stacks have
  no app-flow surface.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


# Adapter module names (matching `plugin_stack_adapters/<name>.py`) and
# the expected `static_capable` value per stack. Order matches the
# scan-and-edit order used during BL-348/349 implementation.
_BACKEND_EXPECT: dict[str, bool] = {
    "astro": True,
    "eleventy_adapter": True,
    "expo_adapter": True,
    "fastapi_adapter": False,
    # v2.1.6 BL-349 round-2 review fix (Greptile P1): generic adapter
    # flipped to `static_capable=False`. Originally `True` to under-
    # claim backend presence, but `generic` is the dispatch target
    # for `hono`, `supabase`, and unknown stacks — calling those
    # projects "static site — no backend" was actively wrong. `False`
    # restores server-side placeholder framing as the safer default
    # when the adapter doesn't know whether a backend exists.
    "generic": False,
    "go_cli": False,
    "hugo_adapter": True,
    "python_django": False,
    "rails_adapter": False,
    "ts_monorepo": False,
}


def _import_adapter(name: str):  # type: ignore[no-untyped-def]
    """Import an adapter module via the package path so contracts.py
    imports resolve correctly."""
    return importlib.import_module(f"plugin_stack_adapters.{name}")


# ---------------------------------------------------------------------------
# (1) + (2) Every adapter's describe_backend populates static_capable.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adapter_name, expected_static", list(_BACKEND_EXPECT.items()))
def test_describe_backend_has_static_capable_field(
    adapter_name: str, expected_static: bool
) -> None:
    """Every adapter's describe_backend() must return a BackendInfo dict
    with the v2.1.6 BL-349 `static_capable` field populated correctly."""
    mod = _import_adapter(adapter_name)
    info = mod.describe_backend()
    assert "static_capable" in info, (
        f"Adapter `{adapter_name}` describe_backend() missing the "
        f"BL-349 `static_capable` field. Every adapter must populate "
        f"this when the contract was introduced."
    )
    assert info["static_capable"] is expected_static, (
        f"Adapter `{adapter_name}` describe_backend() reports "
        f"`static_capable={info['static_capable']!r}` but BL-349 expects "
        f"`{expected_static}`. If the stack's nature changed, update "
        f"_BACKEND_EXPECT in this test; otherwise fix the adapter."
    )


# ---------------------------------------------------------------------------
# (3) + (4) Every adapter's describe_app_flow placeholder-or-None.
# ---------------------------------------------------------------------------


# Adapters that ship a non-None AppFlowInfo — the BL-348 placeholder
# pattern must apply to all of these. The four explicitly returning
# None are tested separately.
_APPFLOW_EMITTING = (
    "astro",
    "eleventy_adapter",
    "expo_adapter",
    "hugo_adapter",
    "rails_adapter",
    "ts_monorepo",
)

_APPFLOW_NONE = (
    "fastapi_adapter",
    "generic",
    "go_cli",
    "python_django",
)


@pytest.mark.parametrize("adapter_name", _APPFLOW_EMITTING)
def test_describe_app_flow_emits_placeholder_pattern(adapter_name: str) -> None:
    """Every adapter that returns a non-None AppFlowInfo must use the
    BL-348 placeholder pattern: `entry_routes=["/"]` and a primary
    journey that contains the `[Placeholder` marker.
    """
    mod = _import_adapter(adapter_name)
    info = mod.describe_app_flow()
    assert info is not None, (
        f"Adapter `{adapter_name}` previously returned non-None AppFlowInfo; "
        f"if you intentionally moved to None, update _APPFLOW_NONE."
    )
    assert info["entry_routes"] == ["/"], (
        f"Adapter `{adapter_name}` describe_app_flow() should emit a "
        f"minimal placeholder `entry_routes=['/']` per BL-348, got "
        f"{info['entry_routes']!r}. Concrete fake routes mislead users "
        f"into thinking they were detected."
    )
    journeys = info.get("primary_journeys", [])
    assert any("[Placeholder" in j for j in journeys), (
        f"Adapter `{adapter_name}` primary_journeys must contain the "
        f"`[Placeholder` marker per BL-348; got {journeys!r}."
    )


@pytest.mark.parametrize("adapter_name", _APPFLOW_NONE)
def test_describe_app_flow_returns_none_for_backend_only_stacks(
    adapter_name: str,
) -> None:
    """Backend-only stacks (FastAPI, Django, Go-CLI) and the unknown
    `generic` adapter still return None from describe_app_flow() — no
    user-journey surface worth scaffolding. BL-348 doesn't change this
    behaviour."""
    mod = _import_adapter(adapter_name)
    assert mod.describe_app_flow() is None, (
        f"Adapter `{adapter_name}` was expected to return None from "
        f"describe_app_flow() but returned a value. If the stack now "
        f"has a frontend, move it to _APPFLOW_EMITTING."
    )


# ---------------------------------------------------------------------------
# Spec-conformance: every BackendInfo carries all 6 fields (original 5 +
# static_capable). Catches future drift where the contract gains another
# required field but adapters lag.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adapter_name", list(_BACKEND_EXPECT))
def test_describe_backend_carries_full_contract(adapter_name: str) -> None:
    """Every adapter's BackendInfo must populate the full v2.1.6
    contract: framework, api_style, routes_dir, models_dir,
    auth_pattern, static_capable.
    """
    mod = _import_adapter(adapter_name)
    info = mod.describe_backend()
    required = {
        "framework",
        "api_style",
        "routes_dir",
        "models_dir",
        "auth_pattern",
        "static_capable",
    }
    missing = required - set(info)
    assert not missing, (
        f"Adapter `{adapter_name}` BackendInfo missing fields: "
        f"{sorted(missing)}. The v2.1.6 contract requires all 6."
    )
