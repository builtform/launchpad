"""Post-dispatch workspace enumeration for /lp-scaffold-stack.

Per docs/plans/launchpad_plans/2026-05-08-v2.1.0-completion-plan.md §3.3.

Trust boundary: adapter output is treated as untrusted. Symlink-escape,
oversized walks, and out-of-tree paths are filtered or rejected, never
silently included. The post-dispatch walk produces the
`materialized_files` list consumed by `wire_cross_cutting` and the
scaffold-receipt's downstream surface.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from plugin_stack_adapters.contracts import ScaffoldStepFailedError

if TYPE_CHECKING:  # pragma: no cover
    from plugin_stack_adapters.composition import CompositionResult


# Cycle-2 fold per v2.1.0 completion plan §3.3: reduced to v2.1-relevant
# dirs only. Build-dir entries (`.next`, `target`, `vendor`, `dist`,
# `.venv`, `__pycache__`) deferred to v2.2 alongside adapters that
# install dependencies. Security-credential dotdirs added as
# defense-in-depth (cycle-1 SEC-1 hardening intent).
_DISPATCH_EXCLUDE_DIRS: frozenset[str] = frozenset({
    ".launchpad", ".lp-tmp",          # plugin-managed
    "node_modules",                   # universal JS dep dir (kept for safety)
    ".ssh", ".aws", ".gnupg",         # credential dotdirs
    ".config", ".docker", ".kube",    # config dotdirs
})

_MAX_ENUMERATED_FILES = 50_000


def enumerate_files(
    cwd: Path,
    dispatch_result: "CompositionResult | Path",
) -> list[str]:
    """Walk the post-dispatch workspace and return cwd-relative file paths.

    Security order (DO NOT REORDER — load-bearing):
      1. is_symlink() check FIRST — must precede is_file() because
         is_file() follows symlinks by default. Reordering would let a
         symlink-to-regular-file pass the file check and bypass symlink
         rejection.
      2. is_file() — skips directories, sockets, fifos, devices.
      3. resolve(strict=False) + is_relative_to(cwd_resolved) — defeats
         relative-path escapes and resolves any ancestor symlinks.
      4. Path-component exclusion via `_DISPATCH_EXCLUDE_DIRS` + .git*
         check (component-level, not just first-component).
      5. Bounded output via `_MAX_ENUMERATED_FILES` (raises
         ScaffoldStepFailedError(reason="dispatch_walk_too_large")).

    `repr()` escapes \\n/\\r/ANSI in the dropped-path stderr WARN to
    neutralize log-injection. Do not switch to plain str() interpolation.
    """
    from plugin_stack_adapters.composition import CompositionResult  # noqa: PLC0415

    roots: list[Path] = []
    if isinstance(dispatch_result, Path):
        roots.append(dispatch_result)
    elif isinstance(dispatch_result, CompositionResult):
        roots.extend(dispatch_result.placed_paths)
    else:  # pragma: no cover - defense in depth
        raise TypeError(
            f"enumerate_files: unsupported dispatch_result type "
            f"{type(dispatch_result).__name__}"
        )

    out: list[str] = []
    seen: set[str] = set()
    dropped_out_of_tree: list[str] = []
    cwd_resolved = cwd.resolve()
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            # Order is load-bearing — see docstring step 1/2.
            if p.is_symlink():
                continue
            if not p.is_file():
                continue
            try:
                resolved = p.resolve(strict=False)
            except OSError:
                continue
            if not resolved.is_relative_to(cwd_resolved):
                # Cycle-2 SEC-fold: log cwd-relative `p`, NEVER the
                # resolved escape target (PII / sensitive-path disclosure).
                try:
                    dropped_out_of_tree.append(str(p.relative_to(cwd)))
                except ValueError:
                    dropped_out_of_tree.append(p.name)
                continue
            try:
                rel = p.relative_to(cwd)
            except ValueError:
                continue
            parts = rel.parts
            if any(
                part.startswith(".git") or part in _DISPATCH_EXCLUDE_DIRS
                for part in parts
            ):
                continue
            rel_str = str(rel)
            if rel_str not in seen:
                seen.add(rel_str)
                out.append(rel_str)
            if len(out) > _MAX_ENUMERATED_FILES:
                raise ScaffoldStepFailedError(
                    reason="dispatch_walk_too_large",
                    path=root,
                    remediation=(
                        f"adapter dispatch produced >{_MAX_ENUMERATED_FILES} "
                        f"files; refusing to enumerate. Likely a runaway "
                        f"adapter or unexpected dependency install."
                    ),
                )
    if dropped_out_of_tree:
        print(
            f"[v2.1 dispatch] WARN: {len(dropped_out_of_tree)} "
            f"adapter-emitted path(s) escaped cwd containment and were "
            f"dropped from enumeration (security): "
            f"first={dropped_out_of_tree[0]!r}",
            file=sys.stderr,
        )
    return sorted(out)


__all__ = [
    "_DISPATCH_EXCLUDE_DIRS",
    "_MAX_ENUMERATED_FILES",
    "enumerate_files",
]
