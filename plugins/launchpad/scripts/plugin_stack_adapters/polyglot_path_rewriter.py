"""Polyglot adapter path rewriter (v2.1 Phase 8.5 Slice B).

Standalone home for the post-composition path-rewrite step that aligns
adapter `backend.routes_dir`, `backend.models_dir`, and
`frontend.component_dir` fields with the actual on-disk locations recorded
in `.launchpad/scaffold-receipt.json` (`layers_materialized[].path`).

Moved verbatim from the legacy `plugin-doc-generator.py:159-247` module
during the Phase 8.5 decommission of plugin-doc-generator. The standalone
module preserves the SRP separation locked by Phase 8.5 plan section 3.5
(arch P2-1 + scope-guardian P3 + simplicity #6): `composition.py` owns
adapter merge semantics, `polyglot_path_rewriter.py` owns path rewrites.

Pure functions: input AdapterOutput + layer paths -> rewritten
AdapterOutput. No globals, no I/O, no side effects.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contracts import AdapterOutput


# Default-path prefixes the per-adapter contract uses for path fields. When
# a layer materializes at a different `path` (e.g., `.` for static-blog
# greenfield), these prefixes are rewritten in the AdapterOutput so the
# rendered architecture docs reference the actual scaffolded location
# (PR #41 cycle 10 #1 closure -- Codex P1).
_ADAPTER_DEFAULT_PATH_PREFIXES = {
    "astro": "apps/web",
    "next": "apps/web",
    "ts_monorepo": "apps/web",
    "fastapi": "apps/api",
    "expo": "apps/mobile",
    "hugo": "",       # hugo defaults to project-root paths (content/, layouts/)
    "eleventy": "",   # eleventy defaults to project-root paths (src/)
    "rails": "",      # rails defaults to project-root paths (app/, config/)
    "python_django": "",
    "go_cli": "",
    "generic": "",
    "hono": "apps/api",
    "django": "",
    "supabase": "supabase",
}


def _rewrite_path(value: str | None, old_prefix: str, new_prefix: str) -> str | None:
    """Replace a leading `old_prefix/` with `new_prefix/` (or strip if new is `.`).

    Returns the original value unchanged when:
      - value is None / empty
      - old_prefix is empty (adapter doesn't use a fixed prefix)
      - value doesn't start with `old_prefix/` (already-customized path)
    """
    if not value or not old_prefix:
        return value
    needle = old_prefix.rstrip("/") + "/"
    if not value.startswith(needle):
        return value
    suffix = value[len(needle):]
    new = new_prefix.rstrip("/")
    if new in ("", "."):
        return suffix
    return f"{new}/{suffix}"


def _rewrite_adapter_paths(
    adapter_out: "AdapterOutput",
    layer_paths: dict[str, str],
    stacks: list[str],
) -> "AdapterOutput":
    """Rewrite path-bearing fields in AdapterOutput to match the layer paths
    actually used by the scaffolder (read from the receipt's
    `layers_materialized[].path`).

    For both single-stack AND multi-stack scaffolds: walks every layer's
    stack->path mapping and rewrites that stack's documented default prefix
    in the merged AdapterOutput's backend/frontend fields. The rewrite is
    conservative -- it only swaps the adapter's documented default prefix;
    user-customized paths (anything not starting with the default prefix)
    pass through unchanged.

    Multi-stack handling (PR #41 cycle 11 #1 closure -- Codex P1): without
    this loop, polyglot composers picked the first STACK_PRECEDENCE adapter
    for backend/frontend output, but the actual scaffolded paths could be
    elsewhere (e.g., polyglot-next-fastapi puts FastAPI at `services/api`
    while next is at `apps/web`). The composer-side `compose_with_layers()`
    selects the correct adapter by role; this rewriter ensures its path
    fields point at the correct on-disk location.
    """
    if not stacks or not layer_paths:
        return adapter_out
    backend = dict(adapter_out["backend"])
    front = adapter_out.get("frontend")
    if isinstance(front, dict):
        front = dict(front)
    for stack_id, actual_path in layer_paths.items():
        if not actual_path:
            continue
        default_prefix = _ADAPTER_DEFAULT_PATH_PREFIXES.get(stack_id, "")
        if not default_prefix or default_prefix == actual_path.rstrip("/"):
            continue
        backend["routes_dir"] = _rewrite_path(
            backend.get("routes_dir"), default_prefix, actual_path,
        )
        backend["models_dir"] = _rewrite_path(
            backend.get("models_dir"), default_prefix, actual_path,
        )
        if isinstance(front, dict):
            front["component_dir"] = _rewrite_path(
                front.get("component_dir"), default_prefix, actual_path,
            )
    rewritten = dict(adapter_out)
    rewritten["backend"] = backend
    if front is not None:
        rewritten["frontend"] = front
    return rewritten  # type: ignore[return-value]


__all__ = [
    "_ADAPTER_DEFAULT_PATH_PREFIXES",
    "_rewrite_adapter_paths",
    "_rewrite_path",
]
