#!/usr/bin/env python3
"""v2.1 /lp-define runner -- canonical-doc orchestrator.

Phase 8.5 plan section 3.11 supersession of plugin-doc-generator.py:
routes through `RendererBase.render_batch + scan_batch + write_batch`
(DA1' = a2 buffered batch + refuse-all on any secret-scanner finding).

Pipeline:
  1. Detect stacks (plugin-stack-detector.py -> JSON)
  2. Compose adapter outputs (single-stack -> adapter.run(); polyglot ->
     polyglot.compose / compose_with_layers); apply standalone polyglot
     path rewriter (Phase 8.5 plan section 3.5 DA2)
  3. Render 5 canonical docs + config.yml + agents.yml through
     `LpDefineRenderer` (RendererBase subclass with TEMPLATE_SUBDIR=".")
  4. Secret-scan every rendered artifact via the buffered-batch gate
     BEFORE any write (legacy plugin-doc-generator.py:496-505 contract
     preserved verbatim)
  5. Apply overwrite policy per artifact (skip / prompt / force /
     [a]ll-overwrite); .launchpad/*.yml NEVER accept [a]ll
  6. Atomic write-all-or-none via write_batch on the writeable subset

Trust-model banner (Phase 8.5 plan section 3.12 verbatim) prints to
stderr BEFORE the secret-scanner gate fires so the user sees the gate
being asserted before any disk write.

Usage:
  python3 lp_define_runner.py [--repo-root PATH] [--dry-run] [--force]
                              [--only FILE,FILE,...]

Exit 0 on success; 1 on any blocking failure (secret found, user
declined, etc.).
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR = SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from plugin_default_generators._renderer_base import (  # noqa: E402
    RendererBase,
    SecretScannerViolation,
)
from plugin_stack_adapters import (  # noqa: E402
    astro,
    eleventy_adapter,
    expo_adapter,
    fastapi_adapter,
    generic,
    go_cli,
    hugo_adapter,
    polyglot,
    python_django,
    rails_adapter,
    secret_scanner,
    ts_monorepo,
)
from plugin_stack_adapters.contracts import AdapterOutput  # noqa: E402
from plugin_stack_adapters.polyglot_path_rewriter import (  # noqa: E402
    _rewrite_adapter_paths,
)

# Phase 8.5 plan section 3.12 verbatim.
TRUST_BANNER = (
    "This command will render and atomically write the LaunchPad "
    "infrastructure overlay. All rendered content is scanned against "
    ".launchpad/secret-patterns.txt before any disk write; if any secret "
    "pattern matches, all writes are refused."
)


# Canonical doc inventory: (template, output_relpath, friendly, is_launchpad_yml)
DOCS: tuple[tuple[str, str, str, bool], ...] = (
    ("PRD.md.j2", "docs/architecture/PRD.md", "PRD", False),
    ("TECH_STACK.md.j2", "docs/architecture/TECH_STACK.md", "TECH_STACK", False),
    (
        "BACKEND_STRUCTURE.md.j2",
        "docs/architecture/BACKEND_STRUCTURE.md",
        "BACKEND_STRUCTURE",
        False,
    ),
    ("APP_FLOW.md.j2", "docs/architecture/APP_FLOW.md", "APP_FLOW", False),
    # v2.1.5 BL-336: REPOSITORY_STRUCTURE.md is referenced by
    # scripts/maintenance/check-repo-structure.sh error messages —
    # but was never rendered. Universal-shape v2.1.5 template; v2.1.6
    # BL-347 lands the stack-aware version.
    (
        "REPOSITORY_STRUCTURE.md.j2",
        "docs/architecture/REPOSITORY_STRUCTURE.md",
        "REPOSITORY_STRUCTURE",
        False,
    ),
    (
        "SECTION_REGISTRY.md.j2",
        "docs/tasks/SECTION_REGISTRY.md",
        "SECTION_REGISTRY",
        False,
    ),
    ("config.yml.j2", ".launchpad/config.yml", "config.yml", True),
    ("agents.yml.j2", ".launchpad/agents.yml", "agents.yml", True),
)


# ---------------------------------------------------------------------------
# Detector wrapper (delegates to plugin-stack-detector.py via subprocess)
# ---------------------------------------------------------------------------


def run_detector(repo_root: Path) -> dict[str, Any]:
    detector = SCRIPT_DIR / "plugin-stack-detector.py"
    env = dict(os.environ)
    env["LP_REPO_ROOT"] = str(repo_root)
    result = subprocess.run(
        [sys.executable, str(detector)],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"stack detector failed: {result.stderr}")
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Adapter dispatch
# ---------------------------------------------------------------------------


def _single_adapter(stack_id: str):
    mapping = {
        "ts_monorepo": ts_monorepo,
        "python_django": python_django,
        "go_cli": go_cli,
        "generic": generic,
        "astro": astro,
        "fastapi": fastapi_adapter,
        "rails": rails_adapter,
        "hugo": hugo_adapter,
        "eleventy": eleventy_adapter,
        "expo": expo_adapter,
        # v2.0 catalog aliases
        "next": ts_monorepo,
        "django": python_django,
        "hono": generic,
        "supabase": generic,
    }
    return mapping.get(stack_id, generic)


def compose_adapter_output(stacks: list[str]) -> AdapterOutput:
    """Single-stack -> direct adapter.run(); multi-stack -> polyglot.compose."""
    if not stacks:
        return generic.run()
    if len(stacks) == 1:
        return _single_adapter(stacks[0]).run()
    return polyglot.compose(stacks)


# ---------------------------------------------------------------------------
# LpDefineRenderer subclass + render orchestration
# ---------------------------------------------------------------------------


class LpDefineRenderer(RendererBase):
    """Renderer for the 7 canonical /lp-define docs.

    Templates live at GENERATORS_ROOT (no subdir). render_targets yields
    the (target_path, rendered_text) pairs used by render_batch; the
    secret-scanner gate fires through write_batch per Phase 8.5 plan
    section 3.11 (DA1' = a2).
    """

    TEMPLATE_SUBDIR = "."

    def render_targets(self, context: Mapping[str, Any]) -> Iterator[tuple[Path, str]]:
        repo_root: Path = context["repo_root"]
        ctx: dict[str, Any] = context["jinja_context"]
        only: set[str] | None = context.get("only")
        for template, out_relpath, _friendly, _is_lp_yml in DOCS:
            if only is not None and Path(out_relpath).name not in only:
                continue
            tmpl = self.env.get_template(template)
            yield repo_root / out_relpath, tmpl.render(**ctx)


def read_brainstorm_summary(repo_root: Path) -> dict[str, str]:
    """v2.1.5 BL-333: parse `.launchpad/brainstorm-summary.md` into a
    section-keyed dict for injection into the canonical docs.

    Format: standard Markdown with `## Section Name` headers. The body
    of each section (up to the next `## ` header) becomes the value.
    Section names are slug-normalized: lowercase, spaces → underscores,
    non-alphanumeric stripped. e.g. `## Success Criteria` → `success_criteria`.

    Aliases applied so common brainstorm headings map to the PRD's
    canonical section slugs:
      `problem` / `vision` → `overview`
      `personas` / `audience` → `users`
      `goals` / `success` → `success_criteria`
      `non-goals` / `out_of_scope` → `non_goals`

    Returns `{}` when the file is absent, empty, or malformed —
    callers handle the empty-dict case by falling through to the
    placeholder rendering. Defensive: never raises on read.
    """
    summary_path = repo_root / ".launchpad" / "brainstorm-summary.md"
    if not summary_path.is_file():
        return {}
    try:
        text = summary_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    sections: dict[str, str] = {}
    current_slug: str | None = None
    current_lines: list[str] = []
    for raw in text.splitlines():
        # YAML frontmatter delimiters are ignored — we extract section
        # bodies only. Frontmatter parsing is out of scope for v2.1.5.
        if raw.startswith("## "):
            if current_slug is not None:
                sections[current_slug] = "\n".join(current_lines).strip()
            heading = raw[3:].strip()
            current_slug = _slug_section_name(heading)
            current_lines = []
        elif current_slug is not None:
            current_lines.append(raw)
    if current_slug is not None:
        sections[current_slug] = "\n".join(current_lines).strip()

    # Apply alias map so common brainstorm headings reach canonical
    # PRD/APP_FLOW/BACKEND_STRUCTURE section slugs without forcing the
    # user to match the doc's exact heading.
    #
    # Codex/Greptile review fix on PR #68: two-pass merge where CANONICAL
    # headings overwrite aliases. Prior shape was first-write-wins by
    # document order — if `## Vision` appeared before `## Overview` in
    # the brainstorm, the `vision`-via-alias content landed at
    # `aliased["overview"]` first, and the subsequent `## Overview` body
    # was dropped because the key was already set. The hardened shape:
    # (1) populate aliased entries first, (2) then overwrite with any
    # canonical-named section so canonical always wins. Matches the
    # docstring claim ("canonical name takes precedence").
    _ALIASES = {
        "problem": "overview",
        "vision": "overview",
        "personas": "users",
        "audience": "users",
        "goals": "success_criteria",
        "success": "success_criteria",
        "out_of_scope": "non_goals",
        "non-goals": "non_goals",  # already-correct fallthrough
        "data_models": "data_models",
        "models": "data_models",
    }
    canonical_slugs = set(_ALIASES.values())

    aliased: dict[str, str] = {}
    # Pass 1: populate aliased-to-canonical entries first.
    for slug, body in sections.items():
        if slug in _ALIASES:
            canonical = _ALIASES[slug]
            # First-write-wins WITHIN aliases (e.g., `vision` then `problem`
            # both alias to `overview` — first one wins). Canonical entries
            # overwrite either of these in pass 2.
            if canonical not in aliased:
                aliased[canonical] = body
    # Pass 2: canonical-named sections overwrite any aliased-canonical entry.
    for slug, body in sections.items():
        if slug in canonical_slugs:
            aliased[slug] = body
    # Pass 3: anything else (non-alias, non-canonical sections like
    # `navigation`, `routes`, `error_handling`) lands verbatim.
    for slug, body in sections.items():
        if slug not in aliased and slug not in _ALIASES:
            aliased[slug] = body
    return aliased


def _slug_section_name(heading: str) -> str:
    """Lowercase, replace whitespace with underscore, strip everything
    else, collapse repeated underscores. `Success Criteria` →
    `success_criteria`; `Goals & Metrics!` → `goals_metrics`."""
    import re

    s = heading.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_-]", "", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def _build_jinja_context(
    adapter_out: AdapterOutput,
    detector_report: dict[str, Any],
    product_name: str,
    repo_root: Path,
) -> dict[str, Any]:
    actual_root = Path(detector_report.get("_repo_root", str(repo_root)))
    relative_manifests: list[str] = []
    for m in detector_report.get("manifests", []):
        try:
            relative_manifests.append(
                str(Path(m).resolve().relative_to(actual_root.resolve()))
            )
        except (ValueError, OSError):
            relative_manifests.append(Path(m).name)

    # v2.1.5 BL-333: surface brainstorm-summary content into the Jinja
    # context so PRD / APP_FLOW / BACKEND_STRUCTURE templates can
    # consume `brainstorm.<section_slug>` and replace placeholder text
    # with user-authored content from `/lp-brainstorm`.
    brainstorm = read_brainstorm_summary(repo_root)

    return {
        "product_name": product_name,
        "stack_summary": adapter_out["product_context"]["stack_summary"],
        "deployment_target": adapter_out["product_context"]["deployment_target"],
        "tech_stack": adapter_out["tech_stack"],
        "backend": adapter_out["backend"],
        "frontend": adapter_out["frontend"],
        "app_flow": adapter_out["app_flow"],
        "product_context": adapter_out["product_context"],
        "commands": adapter_out["commands"],
        "manifests": relative_manifests,
        "stacks": detector_report.get("stacks", []),
        "pipeline_design_enabled": adapter_out["pipeline_overrides"].get(
            "design_enabled", True
        ),
        "pipeline_test_browser_enabled": adapter_out["pipeline_overrides"].get(
            "test_browser_enabled", True
        ),
        "brainstorm": brainstorm,
    }


def render_docs(
    adapter_out: AdapterOutput,
    detector_report: dict[str, Any],
    product_name: str,
    repo_root: Path,
    only: set[str] | None = None,
) -> dict[str, str]:
    """Render all canonical docs to in-memory dict.

    Returns `{output_relpath_str: rendered_text}` (relpath strings keep
    parity with the legacy plugin-doc-generator.py:275-316 surface).
    """
    ctx = _build_jinja_context(adapter_out, detector_report, product_name, repo_root)
    renderer = LpDefineRenderer()
    batch = renderer.render_batch(
        [
            {
                "repo_root": repo_root,
                "jinja_context": ctx,
                "only": only,
            }
        ]
    )
    rendered: dict[str, str] = {}
    for abs_path, content_bytes in batch.items():
        rel = abs_path.relative_to(repo_root).as_posix()
        rendered[rel] = content_bytes.decode("utf-8")
    return rendered


# ---------------------------------------------------------------------------
# Secret scan over the full render set (preserves legacy refuse-all-on-any
# contract; Phase 8.5 plan section 3.11)
# ---------------------------------------------------------------------------


def scan_all(rendered: dict[str, str], repo_root: Path) -> dict[str, list]:
    """Run secret-pattern scan WITH ALLOWLIST on every rendered doc.
    Returns `{out_path: [matches]}` (rel-path keyed); empty when clean.

    Routes through `RendererBase.scan_batch()` so `.launchpad/secret-allowlist.txt`
    and template-marker allowlists apply at this early gate. Without this,
    allowlisted false positives would abort the run before the writeable
    subset reached `write_batch()`'s allowlist-aware gate (Codex PR #50 P1).
    """
    patterns_file = repo_root / ".launchpad" / "secret-patterns.txt"
    allowlist_path = repo_root / ".launchpad" / "secret-allowlist.txt"

    batch: dict[Path, bytes] = {
        repo_root / out_path: content.encode("utf-8")
        for out_path, content in rendered.items()
    }

    renderer = LpDefineRenderer()
    findings_list = renderer.scan_batch(
        batch,
        patterns_file=patterns_file if patterns_file.is_file() else None,
        allowlist_path=allowlist_path if allowlist_path.is_file() else None,
    )

    grouped: dict[str, list] = {}
    for finding in findings_list:
        source = getattr(finding, "source", "") or ""
        try:
            rel = Path(source).relative_to(repo_root).as_posix()
        except ValueError:
            rel = source or "<unknown>"
        grouped.setdefault(rel, []).append(finding)
    return grouped


# ---------------------------------------------------------------------------
# Overwrite menu (verbatim port from plugin-doc-generator.py:336-382)
# ---------------------------------------------------------------------------


def prompt_overwrite(
    out_path: str,
    existing: str,
    new: str,
    all_mode: bool,
    is_launchpad_yml: bool,
) -> str:
    """Interactive menu. Returns one of 'overwrite' / 'keep' / 'all' / 'skip-all'.

    Contract:
      - .launchpad/*.yml files NEVER accept 'all' -- always individual prompt
      - TTY required; non-interactive default is keep
    """
    if all_mode and not is_launchpad_yml:
        return "overwrite"

    diff = list(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{out_path}",
            tofile=f"b/{out_path}",
            n=3,
        )
    )
    diff_text = "".join(diff[:60])

    if is_launchpad_yml:
        print(
            f"\n{out_path} exists (user-tuned -- [a]ll-overwrite does NOT apply to this file).",
            file=sys.stderr,
        )
    else:
        print(f"\n{out_path} exists.", file=sys.stderr)
    print(
        "Choose: [k]eep (default) / [o]verwrite / [d]iff / [a]ll-overwrite / [s]kip-all",
        file=sys.stderr,
    )

    if not sys.stdin.isatty():
        print("(non-interactive -- defaulting to keep)", file=sys.stderr)
        return "keep"

    choice = input("> ").strip().lower()
    if choice == "o":
        return "overwrite"
    if choice == "d":
        print("\n" + diff_text, file=sys.stderr)
        return prompt_overwrite(out_path, existing, new, all_mode, is_launchpad_yml)
    if choice == "a":
        if is_launchpad_yml:
            print(
                "[a]ll-overwrite excludes .launchpad/*.yml -- still prompting for this file.",
                file=sys.stderr,
            )
            return prompt_overwrite(out_path, existing, new, all_mode, is_launchpad_yml)
        return "all"
    if choice == "s":
        return "skip-all"
    return "keep"


# ---------------------------------------------------------------------------
# Helpers (in-tree carry-over of the legacy plugin-doc-generator helpers)
# ---------------------------------------------------------------------------


def _read_config_overwrite(repo_root: Path) -> str:
    """Read existing config.yml's `overwrite:` policy. Returns
    'skip' | 'prompt' | 'force'. Defaults to 'prompt' on missing /
    malformed file."""
    config_path = repo_root / ".launchpad" / "config.yml"
    if not config_path.is_file():
        return "prompt"
    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "prompt"
    if not isinstance(cfg, dict):
        return "prompt"
    val = cfg.get("overwrite", "prompt")
    if val in ("skip", "prompt", "force"):
        return val
    return "prompt"


def ensure_sections_dir(repo_root: Path, summary: dict) -> None:
    """Create paths.sections_dir (default docs/tasks/sections) if missing."""
    config_path = repo_root / ".launchpad" / "config.yml"
    if not config_path.is_file():
        return

    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        sections_dir = (
            (cfg.get("paths") or {}).get("sections_dir")
        ) or "docs/tasks/sections"
    except Exception:
        sections_dir = "docs/tasks/sections"

    candidate = (repo_root / sections_dir).resolve()
    repo_resolved = repo_root.resolve()
    try:
        candidate.relative_to(repo_resolved)
    except ValueError:
        print(
            f"warning: paths.sections_dir resolves outside repo_root "
            f"({sections_dir!r}); skipping mkdir.",
            file=sys.stderr,
        )
        return

    try:
        candidate.mkdir(parents=True, exist_ok=True)
        if not any(candidate.iterdir()):
            summary.setdefault("dirs_created", []).append(sections_dir)
    except OSError as exc:
        print(
            f"warning: could not create {sections_dir} ({exc}). "
            f"/lp-shape-section will fail until you create it manually.",
            file=sys.stderr,
        )


def ensure_audit_gitignore(repo_root: Path, summary: dict) -> None:
    """Append `.launchpad/audit.log` to .gitignore when audit.committed is
    false (default) and the entry is missing. Idempotent."""
    config_path = repo_root / ".launchpad" / "config.yml"
    if not config_path.is_file():
        return

    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        committed = bool((cfg.get("audit") or {}).get("committed", False))
    except Exception:
        committed = False

    if committed:
        return

    gitignore_path = repo_root / ".gitignore"
    target_line = ".launchpad/audit.log"

    existing = ""
    if gitignore_path.is_file():
        existing = gitignore_path.read_text(encoding="utf-8")
        for line in existing.splitlines():
            stripped = line.strip()
            if stripped in (target_line, "/" + target_line, "audit.log"):
                return

    marker = "\n# Added by LaunchPad /lp-define -- audit log is per-user debug state\n"
    append_block = marker + target_line + "\n"

    try:
        if gitignore_path.is_file():
            if existing and not existing.endswith("\n"):
                append_block = "\n" + append_block
            with gitignore_path.open("a", encoding="utf-8") as fh:
                fh.write(append_block)
        else:
            gitignore_path.write_text(append_block.lstrip("\n"), encoding="utf-8")
        summary.setdefault("gitignore_updated", []).append(
            ".gitignore (audit.log entry)"
        )
    except OSError as exc:
        print(
            f"warning: could not update .gitignore ({exc}). "
            f"Add '{target_line}' manually.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def _kernel_fallback_render(repo_root: Path) -> None:
    """v2.1.5 BL-341: defense-in-depth fallback for kernel files when
    `/lp-scaffold-stack` was bypassed (or its Phase 4.5 kernel render
    failed). Reads identity from `.launchpad/scaffold-decision.json` and
    invokes `KernelRenderer.render_all` for any missing kernel file.

    BL-327 (v2.1.4) fixed the catalog_load_failed that was forcing the
    bypass under installed-plugin layout, so this code path is mostly
    historical now — but defense-in-depth catches the residual cases
    (hand-crafted scaffold-receipt; partial pipeline runs; debugging).

    Defensive: any read/render error is logged as a warning and silently
    continues so `/lp-define` itself never breaks due to a fallback
    edge case.
    """
    decision_path = repo_root / ".launchpad" / "scaffold-decision.json"
    if not decision_path.is_file():
        return  # no scaffold-decision → not a scaffolded LaunchPad project

    # Check whether any kernel files are missing.
    from plugin_default_generators.kernel_renderer import (
        KERNEL_FILES,
        KernelRenderer,
    )

    missing = [
        output_relpath
        for _template, output_relpath in KERNEL_FILES
        if not (repo_root / output_relpath).is_file()
    ]
    if not missing:
        return  # all kernel files present; nothing to fall back on

    # Read identity from scaffold-decision.json.
    try:
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"warning: BL-341 kernel-fallback skipped — could not read "
            f"scaffold-decision.json ({exc})",
            file=sys.stderr,
        )
        return
    identity = decision.get("identity")
    if not isinstance(identity, dict) or not identity.get("project_name"):
        print(
            "warning: BL-341 kernel-fallback skipped — scaffold-decision.json "
            "lacks an `identity` block",
            file=sys.stderr,
        )
        return

    print(
        f"[BL-341 kernel-fallback] {len(missing)} kernel file(s) missing "
        f"({', '.join(missing)}); rendering via KernelRenderer.",
        file=sys.stderr,
    )
    try:
        renderer = KernelRenderer()
        renderer.render_all(repo_root, identity)
    except Exception as exc:  # noqa: BLE001 — defense-in-depth swallows
        print(
            f"warning: BL-341 kernel-fallback render failed ({exc}); "
            f"proceeding with /lp-define. Re-run `/lp-scaffold-stack` or "
            f"`/lp-update-identity` to recover.",
            file=sys.stderr,
        )


def generate(
    repo_root: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    only: set[str] | None = None,
    product_name: str = "Your Product",
    emit_trust_banner: bool = True,
) -> int:
    """End-to-end /lp-define orchestration. Returns process exit code."""
    if emit_trust_banner:
        # Phase 8.5 plan section 3.12: banner emits BEFORE the gate fires
        # so the user sees the gate being asserted.
        print(TRUST_BANNER, file=sys.stderr)

    # v2.1.5 BL-341: defense-in-depth kernel-file fallback. If kernel
    # files (LICENSE / SECURITY.md / etc.) are missing from a scaffolded
    # project, render them via KernelRenderer before the main pipeline
    # proceeds. No-op when files exist or no scaffold-decision.json.
    if not dry_run:
        _kernel_fallback_render(repo_root)

    # 1. Detect.
    report = run_detector(repo_root)
    report["_repo_root"] = str(repo_root)

    # 2. Compose. Greenfield path prefers scaffold-receipt.json's
    # `layers_materialized[].stack` over manifest detection.
    receipt_path = repo_root / ".launchpad" / "scaffold-receipt.json"
    receipt_stacks: list[str] = []
    receipt_layer_paths: dict[str, str] = {}
    receipt_layers: list[dict] = []
    if receipt_path.is_file():
        try:
            from plugin_scaffold_receipt_loader import (
                load_receipt,  # type: ignore[import-not-found]
            )
        except ImportError:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "plugin_scaffold_receipt_loader",
                SCRIPT_DIR / "plugin-scaffold-receipt-loader.py",
            )
            if spec and spec.loader:
                _mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(_mod)
                load_receipt = _mod.load_receipt  # type: ignore[attr-defined]
            else:
                load_receipt = None  # type: ignore[assignment]
        if load_receipt is not None:
            try:
                receipt = load_receipt(receipt_path)
                for layer in receipt.get("layers_materialized", []):
                    if not isinstance(layer, dict) or "stack" not in layer:
                        continue
                    stack_id = str(layer["stack"])
                    receipt_stacks.append(stack_id)
                    if "path" in layer:
                        receipt_layer_paths[stack_id] = str(layer["path"])
                    receipt_layers.append(
                        {
                            "stack": stack_id,
                            "role": str(layer.get("role", "")),
                            "path": str(layer.get("path", "")),
                        }
                    )
            except Exception:
                receipt_stacks = []
                receipt_layer_paths = {}
                receipt_layers = []

    stacks = receipt_stacks or report.get("stacks", ["generic"])
    has_role_data = bool(receipt_layers) and any(
        layer.get("role") for layer in receipt_layers
    )
    if has_role_data and len(receipt_layers) > 1:
        adapter_out = polyglot.compose_with_layers(receipt_layers)
    else:
        adapter_out = compose_adapter_output(stacks)
    if receipt_layer_paths:
        adapter_out = _rewrite_adapter_paths(adapter_out, receipt_layer_paths, stacks)

    # 3. Render -- overwrite detector's manifest-derived stacks.
    report["stacks"] = list(stacks)
    rendered = render_docs(adapter_out, report, product_name, repo_root, only=only)

    # 4. Secret scan over the full render set (preserves legacy refuse-
    # all-on-any-finding contract; matches plugin-doc-generator.py:496-505).
    findings = scan_all(rendered, repo_root)
    if findings:
        print("Secret-scan findings:", file=sys.stderr)
        for out_path, matches in findings.items():
            print(f"  {out_path}:", file=sys.stderr)
            print(
                "    " + secret_scanner.format_matches(matches).replace("\n", "\n    "),
                file=sys.stderr,
            )
        print(
            "\nRefusing to write. Redact the offending values (or adjust "
            ".launchpad/secret-patterns.txt if false positive) and re-run.",
            file=sys.stderr,
        )
        return 1

    # 5. Resolve overwrite policy.
    config_policy = _read_config_overwrite(repo_root)
    effective_force = force or (config_policy == "force")
    skip_existing = (not force) and (config_policy == "skip")

    # 6. Decide what to write per overwrite policy + interactive prompts.
    all_mode = effective_force
    summary = {"written": [], "kept": [], "skipped": [], "skipped_after_skip_all": []}
    skip_remaining = False
    to_write: dict[Path, bytes] = {}

    for _template, out_rel, _friendly, is_lp_yml in DOCS:
        if out_rel not in rendered:
            continue
        if skip_remaining:
            summary["skipped_after_skip_all"].append(out_rel)
            continue
        out_abs = repo_root / out_rel
        new_content = rendered[out_rel]

        if dry_run:
            summary["written"].append(out_rel + " (dry-run)")
            continue

        if out_abs.exists():
            existing = out_abs.read_text(encoding="utf-8")
            if existing == new_content:
                summary["kept"].append(out_rel + " (unchanged)")
                continue

            if skip_existing:
                summary["kept"].append(out_rel + " (config: skip)")
                continue

            if effective_force:
                decision = (
                    "overwrite"
                    if not is_lp_yml
                    else prompt_overwrite(
                        out_rel, existing, new_content, all_mode, is_lp_yml
                    )
                )
            else:
                decision = prompt_overwrite(
                    out_rel, existing, new_content, all_mode, is_lp_yml
                )

            if decision == "all":
                all_mode = True
                decision = "overwrite"
            elif decision == "skip-all":
                skip_remaining = True
                summary["skipped"].append(out_rel)
                continue

            if decision != "overwrite":
                summary["kept"].append(out_rel)
                continue

        to_write[out_abs] = new_content.encode("utf-8")
        summary["written"].append(out_rel)

    # 7. Atomic write via the gated write_batch (re-scans the writeable
    # subset; cache-fast). Phase 8.5 plan section 3.11 (DA1' = a2).
    if to_write and not dry_run:
        renderer = LpDefineRenderer()
        patterns_file = repo_root / ".launchpad" / "secret-patterns.txt"
        allowlist_path = repo_root / ".launchpad" / "secret-allowlist.txt"
        try:
            renderer.write_batch(
                to_write,
                cwd=repo_root,
                patterns_file=patterns_file,
                allowlist_path=allowlist_path,
            )
        except SecretScannerViolation as exc:
            # Defense-in-depth: scan_all already ran on the full set, but
            # if write_batch surfaces something the user-defined patterns
            # missed earlier (e.g., file mtime changed between calls),
            # honor the gate's refuse-all contract.
            print(f"\nGate refused all writes: {exc}", file=sys.stderr)
            return 1

    # 8. Post-write helpers (skip on dry-run per legacy contract).
    if not dry_run:
        ensure_audit_gitignore(repo_root, summary)
        ensure_sections_dir(repo_root, summary)

    # 9. Report.
    print(json.dumps({"detected_stacks": stacks, "summary": summary}, indent=2))
    return 0


def redetect_stack(repo_root: Path, *, force: bool) -> int:
    """Phase 6 v2.1 DA6: --redetect-stack flag handler.

    Detector runs ONCE per invocation. If the detected stack id matches
    the persisted `stacks:` array, no-op (exit 0). If mismatch and `force`
    is False, abort with exit 65 (`EX_DATAERR` from sysexits.h; chosen to
    distinguish from Phase 8 signpost stubs which use exit 64). If
    mismatch and `force` is True, atomically rewrite the `stacks:` line
    in `.launchpad/config.yml` via `lp_bootstrap.policy.write_config_yaml_atomic`.

    `--force` IS the confirmation token (cycle-3 spec-flow P1-1); no Y/N
    prompt; safe in CI.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "plugin_config_loader", SCRIPT_DIR / "plugin-config-loader.py"
    )
    cfg_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg_mod)  # type: ignore[union-attr]

    persisted = cfg_mod.read_stacks(repo_root)
    report = run_detector(repo_root)
    detected = list(report.get("stacks") or ["generic"])

    if persisted == detected:
        return 0

    if not force:
        print(
            f"detected id {detected!r} differs from persisted {persisted!r}; "
            f"re-run with --force to overwrite",
            file=sys.stderr,
        )
        return 65

    from lp_bootstrap.policy import write_config_yaml_atomic

    config_path = repo_root / ".launchpad" / "config.yml"
    if not config_path.is_file():
        new_text = f"stacks: [{', '.join(detected)}]\n"
        write_config_yaml_atomic(config_path, new_text, cwd=repo_root)
        return 0

    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)
    new_stacks_line = f"stacks: [{', '.join(detected)}]"
    out: list[str] = []
    replaced = False
    for ln in lines:
        if not replaced and ln.lstrip().startswith("stacks:"):
            out.append(new_stacks_line)
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        out.insert(0, new_stacks_line)
        out.insert(1, "")
    new_text = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    write_config_yaml_atomic(config_path, new_text, cwd=repo_root)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    ap.add_argument(
        "--dry-run", action="store_true", help="render + secret-scan but don't write"
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="skip per-file prompts except for .launchpad/*.yml",
    )
    ap.add_argument(
        "--only", default="", help="comma-separated list of filenames to render"
    )
    ap.add_argument(
        "--product-name", default="Your Product", help="Name for PRD scaffold"
    )
    ap.add_argument(
        "--no-trust-banner",
        action="store_true",
        help="suppress the trust-model banner (used by automated tests)",
    )
    ap.add_argument(
        "--redetect-stack",
        action="store_true",
        help=(
            "Re-detect stack id and persist it to .launchpad/config.yml's "
            "top-level `stacks:` array. Bare flag aborts with exit 65 "
            "(EX_DATAERR) if detected id differs from persisted; pair "
            "with --force to overwrite without prompt (safe in CI)."
        ),
    )
    args = ap.parse_args()

    if args.redetect_stack:
        try:
            return redetect_stack(Path(args.repo_root).resolve(), force=args.force)
        except Exception as e:
            print(f"redetect-stack error: {e}", file=sys.stderr)
            return 1

    only_set: set[str] | None = None
    if args.only:
        only_set = {s.strip() for s in args.only.split(",") if s.strip()}

    try:
        return generate(
            Path(args.repo_root).resolve(),
            dry_run=args.dry_run,
            force=args.force,
            only=only_set,
            product_name=args.product_name,
            emit_trust_banner=not args.no_trust_banner,
        )
    except Exception as e:
        print(f"generator error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
