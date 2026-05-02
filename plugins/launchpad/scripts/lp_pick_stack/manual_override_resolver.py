"""Manual-override layer resolver (Phase 2 §4.1 Step 4).

When the user picks `[m]anual override` (or the matcher returns zero
candidates and the user opts into manual selection), this module validates
each user-supplied `(stack, role, path, options)` triple against:

  - `lp_pick_stack.VALID_COMBINATIONS` (Phase -1 deliverable; HANDSHAKE §12 +
    pick-stack plan §3.4 — the 7-tuple manual-override matrix)
  - `path_validator.validate_relative_path()` (HANDSHAKE §6 — the path
    string-shape + filesystem-realpath checks)

On success, returns a list of normalized layer dicts ready to embed in the
scaffold-decision.json `layers` array. The matched_category_id is set by the
engine to `manual-override` (HANDSHAKE §4 rule 4 reserved id).

Cross-layer rules from pick-stack plan §3.4 (single-role-per-layer,
fullstack-precludes-split, mobile-standalone, polyglot-allowed,
multi-frontend-allowed, backend-managed-pairing, path-uniqueness) compose
ON TOP OF the per-tuple base check. The base helper (`is_valid_combination`)
is gating the single-stack tuples; the cross-layer rules are gated here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from lp_pick_stack import VALID_COMBINATIONS, is_valid_combination

# Roles allowed in a v2.0 scaffold-decision.json layer.role field
# (HANDSHAKE §4 schema enum). Manual-override accepts the same superset; the
# (stack, role) tuple is then constrained to VALID_COMBINATIONS (a subset).
ALLOWED_ROLES = frozenset({
    "frontend",
    "backend",
    "frontend-main",
    "frontend-dashboard",
    "fullstack",
    "mobile",
    "backend-managed",
    "desktop",
})


class ManualOverrideError(ValueError):
    """Raised when a manual-override layer set fails validation.

    Mirrors PathValidationError pattern: domain-specific exception subclass +
    `field_name` attribute for telemetry routing.
    """

    def __init__(self, message: str, field_name: str = "layers"):
        super().__init__(f"{field_name}: {message}")
        self.field_name = field_name


def _normalize_layer(raw: Mapping[str, Any], index: int, cwd: Path) -> dict:
    """Validate one layer triple; return a normalized dict.

    Per-layer checks: required keys present, types right, role in
    ALLOWED_ROLES, path passes string-shape + filesystem-realpath validator,
    options is a dict (may be empty).
    """
    field = f"layers[{index}]"
    if not isinstance(raw, Mapping):
        raise ManualOverrideError(
            f"expected mapping, got {type(raw).__name__}", field
        )
    for key in ("stack", "role", "path"):
        if key not in raw:
            raise ManualOverrideError(f"missing required key {key!r}", field)
        if not isinstance(raw[key], str) or not raw[key]:
            raise ManualOverrideError(
                f"{key} must be non-empty str", f"{field}.{key}"
            )

    stack = raw["stack"]
    role = raw["role"]
    path_str = raw["path"]
    options = raw.get("options", {})
    if not isinstance(options, Mapping):
        raise ManualOverrideError(
            f"options must be mapping, got {type(options).__name__}",
            f"{field}.options",
        )

    if role not in ALLOWED_ROLES:
        raise ManualOverrideError(
            f"role {role!r} not in ALLOWED_ROLES enum", f"{field}.role"
        )

    # path_validator runs the string-shape AND filesystem-realpath checks.
    # Caller is responsible for ensuring `cwd` exists (HANDSHAKE §6 caller
    # contract); the validator raises PathValidationError on failure which
    # propagates to the engine as a structured rejection.
    from path_validator import validate_relative_path

    validate_relative_path(path_str, cwd, field_name=f"{field}.path")

    # The per-tuple base check from VALID_COMBINATIONS. Multi-stack
    # combinations (polyglot, multi-frontend, backend-managed-pairing) are
    # validated cross-layer in resolve_manual; here we only check the base
    # (stack, role) tuple.
    if not is_valid_combination(stack, role):
        raise ManualOverrideError(
            f"(stack={stack!r}, role={role!r}) not in VALID_COMBINATIONS",
            f"{field}.stack-role",
        )

    return {
        "stack": stack,
        "role": role,
        "path": path_str,
        "options": dict(options),
    }


def resolve_manual(
    layer_specs: Sequence[Mapping[str, Any]],
    cwd: Path,
) -> list[dict]:
    """Validate a manual-override layer set; return normalized layers.

    Per-layer checks via `_normalize_layer`; then cross-layer rules:

    - **Path uniqueness**: each layer has a distinct `path`
    - **Fullstack precludes split**: `fullstack` role at any path is the only
      layer in the set
    - **Mobile standalone**: `mobile` role is the only layer in the set
    - **Backend-managed pairing**: `backend-managed` only paired with
      `frontend` or `frontend-main`/`frontend-dashboard` (NOT another backend)

    Empty layer list → ManualOverrideError. Cross-layer-rule violations →
    ManualOverrideError with `field_name` describing the failing rule.
    """
    if not layer_specs:
        raise ManualOverrideError("layer set is empty")

    layers = [_normalize_layer(s, i, cwd) for i, s in enumerate(layer_specs)]

    # Normalize trailing slashes before uniqueness check so `apps/web` and
    # `apps/web/` are caught as duplicates (PR #41 cycle 10 #2 closure —
    # Codex P1). Catalog entries like `supabase/` must round-trip safely
    # against `supabase` from a sibling layer.
    def _norm(p: str) -> str:
        return p.rstrip("/") if p != "/" else p
    paths = [layer["path"] for layer in layers]
    norm_paths = [_norm(p) for p in paths]
    if len(norm_paths) != len(set(norm_paths)):
        raise ManualOverrideError(
            f"path uniqueness violated (normalized): {paths}",
            "layers.path-uniqueness",
        )

    roles = [layer["role"] for layer in layers]

    if "fullstack" in roles and len(layers) > 1:
        raise ManualOverrideError(
            "fullstack role precludes split — must be sole layer",
            "layers.fullstack-precludes-split",
        )

    if "mobile" in roles and len(layers) > 1:
        raise ManualOverrideError(
            "mobile role is standalone — must be sole layer",
            "layers.mobile-standalone",
        )

    if "backend-managed" in roles:
        # Allowed peers: frontend, frontend-main, frontend-dashboard
        # (NOT backend or fullstack — would mean two backends)
        allowed_peers = frozenset({
            "backend-managed",
            "frontend",
            "frontend-main",
            "frontend-dashboard",
        })
        for r in roles:
            if r not in allowed_peers:
                raise ManualOverrideError(
                    f"backend-managed cannot pair with role {r!r}",
                    "layers.backend-managed-pairing",
                )

    return layers


__all__ = [
    "ALLOWED_ROLES",
    "ManualOverrideError",
    "resolve_manual",
]
