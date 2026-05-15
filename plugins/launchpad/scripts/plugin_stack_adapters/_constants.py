"""Centralized version constants for stack tooling (BL-353 + BL-354).

Single source of truth for pinned tool versions referenced across the
LaunchPad rendering pipeline. Bumping a constant here propagates to every
rendered file that consumes it (e.g., `.nvmrc`, `.github/workflows/ci.yml`).

Per BL-353 + BL-354 v2.1.5: the `pnpm/action-setup` and `actions/setup-node`
steps in the rendered CI workflow require a version source. Without one,
the Build job aborts at the setup step and every downstream step is
skipped — failing CI red on the very first push of a freshly-scaffolded
project. These constants close that gap.

Update cadence: bump on a quarterly schedule or when the upstream tool
ships a security advisory. The BL-355 self-consistency assertion catches
the related class of "workflow references file the manifest doesn't
render" — but version drift inside this file is a separate concern.
"""

from __future__ import annotations

# pnpm v10 stable; consumed by `version:` on `pnpm/action-setup` in the
# rendered CI workflow (BL-353). When BL-345 (v2.1.6) lands the full
# stack-aware CI refactor, this constant becomes the single source of
# truth for both the workflow input AND the optional `packageManager`
# field in package.json.
DEFAULT_PNPM_VERSION = "10.30.1"

# Node 22 LTS; consumed by the rendered `.nvmrc` file (BL-354). The CI
# workflow's `actions/setup-node` step reads `.nvmrc` via the
# `node-version-file:` input. Adapters whose `package.json` ships an
# `engines.node` declaration MUST satisfy this version (>= the major
# version baked into DEFAULT_NODE_VERSION).
DEFAULT_NODE_VERSION = "22.12.0"


__all__ = [
    "DEFAULT_NODE_VERSION",
    "DEFAULT_PNPM_VERSION",
]
