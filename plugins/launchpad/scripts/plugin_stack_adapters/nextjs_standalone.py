"""nextjs_standalone adapter: wrap-and-overlay over vercel/next-forge.

Phase 4 plan section 2.1 + section 3.3 + section 3.5. Adapter pins the
upstream commit SHA in pin_registry.py (CODEOWNERS-protected) and applies an
OverlayConfig that swaps Clerk for Auth.js v5 and removes the optional
apps/storybook workspace before composition placement.

Wrap-and-overlay flow (single-adapter mode):
  1. scaffold_into(tempdir): template_cache.fetch returns the cached upstream
     tree; we copy it into tempdir.
  2. apply_overlay(tempdir): rewrite Clerk imports / config to Auth.js v5;
     remove apps/storybook subtree.

Nested-Turborepo unwrap is the composition wrapper's responsibility (Slice E)
since unwrap is a cross-adapter concern; the adapter only declares the
strategy via `unwrap_strategy="nested_turborepo"`.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType

from .contracts import (
    _EMPTY_WORKSPACE_MAP,
    Adapter,
    AdapterScaffoldError,
    CompositionRule,
    OverlayConfig,
    StackIdActive,
    UnwrapStrategy,
    UpstreamTemplate,
)
from .pin_registry import get_pin

_REPO_URL = "https://github.com/vercel/next-forge"

_OVERLAY: OverlayConfig = {
    "add": [],
    "replace": [
        "apps/app/lib/auth.ts",
        "apps/app/middleware.ts",
    ],
    "remove": [
        "apps/storybook",
    ],
    "conflict_policy": {
        "package.json": "merge-keys",
        "turbo.json": "merge-keys",
        ".gitignore": "append-only",
        "lefthook.yml": "merge-keys",
    },
}

# Compose-with declarations (Phase 4 plan section 3.4 pair table). Each rule
# names the OTHER adapter's workspace + the conflict policy slice that this
# adapter owns. ts_monorepo + nextjs_standalone is collapsed at the
# composition layer via the ts_monorepo + * catch-all rejection.
_COMPOSES_WITH: dict[StackIdActive, CompositionRule] = {
    "astro": {
        "workspace_name": "content",
        "conflict_policy": {
            "lefthook.yml": "merge-keys",
            "package.json": "merge-keys",
            "turbo.json": "merge-keys",
        },
    },
    "nextjs_fastapi": {
        # Both adapters claim "app"; collision suffix in composition.py
        # renames the first occurrence "app-fe" with the §3.12 INFO log.
        "workspace_name": "app",
        "conflict_policy": {
            "lefthook.yml": "merge-keys",
            "package.json": "merge-keys",
            "turbo.json": "merge-keys",
            "pnpm-workspace.yaml": "merge-keys",
        },
    },
    "generic": {
        "workspace_name": "extra",
        "conflict_policy": {
            "package.json": "merge-keys",
        },
    },
}

_CLERK_IMPORT_RE = re.compile(
    r"^import\s+\{[^}]*\}\s+from\s+['\"]@clerk/[^'\"]+['\"];?\s*\n",
    re.MULTILINE,
)
_CLERK_PROVIDER_RE = re.compile(r"<ClerkProvider[\s\S]*?</ClerkProvider>", re.MULTILINE)


class NextjsStandaloneAdapter:
    """Adapter Protocol implementation for vercel/next-forge."""

    stack_id: StackIdActive = "nextjs_standalone"
    upstream: UpstreamTemplate | None = {
        "adapter_id": "nextjs_standalone",
        "sub_template_id": None,
    }
    manifest_schema_version: str = "1.0"
    workspace_name: str | None = "app"
    unwrap_strategy: UnwrapStrategy = "nested_turborepo"
    composes_with: dict[StackIdActive, CompositionRule] = _COMPOSES_WITH
    # Per Codex P1-B harden D3/D4:
    #  - single-mode: empty map preserves "fork next-forge as project root"
    #    (next-forge IS a Turborepo with its own apps/ + packages/);
    #  - composition-mode: lift the upstream-nested `apps/app` to
    #    `composition_root/apps/app`, and lift `packages/` to top-level
    #    sibling so `pnpm-workspace.yaml` globs resolve.
    workspace_source_map_single: Mapping[str, str] = _EMPTY_WORKSPACE_MAP
    workspace_source_map_composition: Mapping[str, str] = MappingProxyType(
        {
            "app": "apps/app",
        }
    )
    package_workspace_paths: tuple[str, ...] = ("packages",)

    def __init__(self, *, fetcher: Callable[[Path], None] | None = None) -> None:
        self._fetcher_override = fetcher

    def _resolve_pin(self) -> dict:
        pin = get_pin("nextjs_standalone")
        if pin["repo_url"] != _REPO_URL:
            raise AdapterScaffoldError(
                reason="pin_registry_repo_mismatch",
                path=None,
                remediation=(
                    f"pin_registry repo {pin['repo_url']} does not match "
                    f"adapter constant {_REPO_URL}"
                ),
            )
        return pin

    def scaffold_into(self, tempdir: Path) -> None:
        pin = self._resolve_pin()
        from template_cache import fetch

        try:
            cached = fetch(pin["repo_url"], pin["sha"], fetcher=self._fetcher_override)
        except Exception as exc:
            raise AdapterScaffoldError(
                reason="template_cache_fetch_failed",
                path=tempdir,
                remediation=(
                    f"failed to fetch {pin['repo_url']}@{pin['sha'][:8]} into "
                    f"the template cache: {exc}"
                ),
            ) from exc

        tempdir.mkdir(parents=True, exist_ok=True)
        for child in cached.iterdir():
            if child.name in {".ready", ".fetched_at", ".expected_files.json"}:
                continue
            dst = tempdir / child.name
            if child.is_dir():
                shutil.copytree(child, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(child, dst)

    def apply_overlay(self, tempdir: Path) -> None:
        for rel in _OVERLAY["remove"]:
            target = tempdir / rel
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()

        for path in tempdir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".mjs"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "@clerk/" not in text:
                continue
            new_text = _CLERK_IMPORT_RE.sub("", text)
            new_text = _CLERK_PROVIDER_RE.sub("{children}", new_text)
            if not new_text.lstrip().startswith("import { auth }"):
                new_text = 'import { auth } from "@/lib/auth";\n' + new_text
            new_text = new_text.replace("@clerk/nextjs", "@/lib/auth")
            new_text = new_text.replace("@clerk/clerk-react", "@/lib/auth")
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")


ADAPTER = NextjsStandaloneAdapter()


def assert_adapter_protocol_conformance() -> None:
    """Hard-fail import-time check that the singleton implements `Adapter`."""
    if not isinstance(ADAPTER, Adapter):
        raise AdapterScaffoldError(
            reason="adapter_protocol_drift",
            path=None,
            remediation=(
                "NextjsStandaloneAdapter no longer satisfies the `Adapter` "
                "Protocol; check contracts.py for shape changes."
            ),
        )


assert_adapter_protocol_conformance()
