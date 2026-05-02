#!/usr/bin/env python3
"""Canonical-doc generator for /lp-define.

Pipeline:
  1. Detect stacks (plugin-stack-detector.py → JSON)
  2. Compose adapter outputs (single stack → adapter.run(); polyglot → composer)
  3. Render 5 canonical docs + config.yml through Jinja2 templates
  4. Secret-scan every rendered artifact BEFORE writing
  5. Apply overwrite policy per artifact (skip / prompt / force / [a]ll-overwrite)
  6. Write to disk

Security gates:
  - Stack detector's manifest allowlist: detector only opens 6 known files
  - Manifest stripping: scripts.*, [tool.*], registry tokens, embedded
    credentials are replaced with <redacted> BEFORE reaching templates
  - Autoescape=True on all templates: interpolated strings can't smuggle
    Jinja metacharacters
  - Post-render secret scan: every generated doc is scanned against
    .launchpad/secret-patterns.txt before write
  - .launchpad/config.yml and .launchpad/agents.yml NEVER overwritten via
    [a]ll-overwrite — always individual prompt with mandatory diff

Usage:
  plugin-doc-generator.py [--repo-root PATH] [--dry-run] [--force]
                          [--only FILE,FILE,...]

Exit 0 on success; 1 on any blocking failure (secret found, user declined,
etc.).
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR = SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import jinja2  # noqa: E402

from plugin_stack_adapters import (  # noqa: E402
    astro_adapter,
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

# manifest_stripper is intentionally NOT imported here. The stripper exists
# as a defense-in-depth layer for a flow that does not currently happen:
# the templates render manifest PATHS, never parsed manifest CONTENT, so
# there is no field for the stripper to scrub before rendering. If a future
# template ever interpolates a value lifted from a parsed manifest, wire
# manifest_stripper at that boundary; until then importing it would
# misleadingly imply work that is not done. Secret scanning of the rendered
# output continues via secret_scanner before write — that is the active
# gate today.
from plugin_stack_adapters.contracts import AdapterOutput  # noqa: E402


# --- Detector wrapper ---

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


# --- Jinja2 environment ---

def make_jinja_env() -> jinja2.Environment:
    """Build the Jinja2 Environment for canonical-doc generation.

    Autoescape policy: HTML-extension-only via `select_autoescape`. Canonical
    docs are .md and .yml — globally forcing autoescape=True (the previous
    config) escapes normal text characters like `&`, `<`, `>` even when they
    appear in user-facing strings, producing artifacts like `R&amp;D` in
    rendered PRD.md prose. The actual injection threat (a hostile value in
    detected manifests being re-evaluated as Jinja) is already prevented by
    Jinja's template model: variable values render as strings, never re-parsed
    as syntax. The HTML autoescape on .md / .yml output therefore has no
    security upside while it does measurably corrupt benign text.

    Templates that ARE HTML (none today, but the door is open for v1.1) get
    autoescape automatically via the extension match.

    YAML templates use `tojson` or explicit yaml-safe quoting in the template
    bodies for any field where a string might collide with YAML syntax — that
    pattern is the right tool for YAML escaping, not HTML autoescape.

    StrictUndefined stays on so missing variables fail loudly at render time
    rather than silently emitting empty strings.
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(SCRIPT_DIR / "plugin-default-generators")),
        autoescape=jinja2.select_autoescape(
            enabled_extensions=("html", "htm", "xml"),
            default=False,
        ),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )


# --- Canonical doc inventory ---
# (template, output_relpath, friendly_name, is_launchpad_yml)
DOCS = [
    ("PRD.md.j2",                "docs/architecture/PRD.md",                "PRD",                 False),
    ("TECH_STACK.md.j2",         "docs/architecture/TECH_STACK.md",         "TECH_STACK",          False),
    ("BACKEND_STRUCTURE.md.j2",  "docs/architecture/BACKEND_STRUCTURE.md",  "BACKEND_STRUCTURE",   False),
    ("APP_FLOW.md.j2",           "docs/architecture/APP_FLOW.md",           "APP_FLOW",            False),
    ("SECTION_REGISTRY.md.j2",   "docs/tasks/SECTION_REGISTRY.md",          "SECTION_REGISTRY",    False),
    ("config.yml.j2",            ".launchpad/config.yml",                   "config.yml",          True),
    ("agents.yml.j2",            ".launchpad/agents.yml",                   "agents.yml",          True),
]


def compose_adapter_output(stacks: list[str]) -> AdapterOutput:
    """Run adapters for the detected stacks. Single stack → direct run.
    Multiple stacks → composer."""
    if not stacks:
        return generic.run()
    if len(stacks) == 1:
        return _single_adapter(stacks[0]).run()
    return polyglot.compose(stacks)


def _single_adapter(stack_id: str):
    mapping = {
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
        # v2.0 catalog aliases (PR #41 cycle 3 #2 — closes the receipt-
        # dispatch silent-fallback gap for `next`, `django`, `hono`,
        # `supabase` which were missing from the legacy adapter mapping).
        "next": ts_monorepo,
        "django": python_django,
        "hono": generic,
        "supabase": generic,
    }
    return mapping.get(stack_id, generic)


# --- Rendering ---

def render_docs(adapter_out: AdapterOutput, detector_report: dict[str, Any], product_name: str) -> dict[str, str]:
    """Render all canonical docs. Returns {output_relpath: rendered_content}."""
    env = make_jinja_env()

    # Build the template context. Explicit keys — no surprises.
    # Manifests come back as absolute paths from the detector; rewrite to
    # repo-relative so docs don't leak the user's home dir / /tmp paths.
    repo_root = Path(detector_report.get("manifests", [""])[0]).parent if detector_report.get("manifests") else None
    # Better: use the actual repo_root the generator was invoked with.
    # We stash it in detector_report under '_repo_root' (populated by generate()).
    actual_root = Path(detector_report.get("_repo_root", "."))
    relative_manifests = []
    for m in detector_report.get("manifests", []):
        try:
            relative_manifests.append(str(Path(m).resolve().relative_to(actual_root.resolve())))
        except (ValueError, OSError):
            relative_manifests.append(Path(m).name)  # fallback to basename

    ctx = {
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
        "pipeline_design_enabled": adapter_out["pipeline_overrides"].get("design_enabled", True),
        "pipeline_test_browser_enabled": adapter_out["pipeline_overrides"].get("test_browser_enabled", True),
    }

    rendered: dict[str, str] = {}
    for template, out_path, friendly, _ in DOCS:
        try:
            tmpl = env.get_template(template)
        except jinja2.TemplateNotFound:
            raise RuntimeError(f"template missing: {template}")
        rendered[out_path] = tmpl.render(**ctx)
    return rendered


# --- Secret scanning ---

def scan_all(rendered: dict[str, str], repo_root: Path) -> dict[str, list]:
    """Run secret-pattern scan on every rendered doc. Returns {out_path: [matches]}."""
    patterns_file = repo_root / ".launchpad" / "secret-patterns.txt"
    patterns = secret_scanner.load_patterns(patterns_file if patterns_file.is_file() else None)

    findings: dict[str, list] = {}
    for out_path, content in rendered.items():
        matches = secret_scanner.scan(content, patterns=patterns)
        if matches:
            findings[out_path] = matches
    return findings


# --- Overwrite menu ---

def prompt_overwrite(out_path: str, existing: str, new: str, all_mode: bool, is_launchpad_yml: bool) -> str:
    """Interactive menu. Returns one of: 'overwrite', 'keep', 'all', 'skip-all'.

    Contract:
      - .launchpad/*.yml files NEVER accept 'all' — always individual prompt
        with mandatory diff, regardless of previous [a]ll-overwrite
      - TTY required; non-interactive caller must supply --force via the
        config.yml overwrite: force top-level key instead
    """
    if all_mode and not is_launchpad_yml:
        return "overwrite"

    # Build diff preview
    diff = list(difflib.unified_diff(
        existing.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{out_path}",
        tofile=f"b/{out_path}",
        n=3,
    ))
    diff_text = "".join(diff[:60])

    if is_launchpad_yml:
        print(f"\n{out_path} exists (user-tuned — [a]ll-overwrite does NOT apply to this file).", file=sys.stderr)
    else:
        print(f"\n{out_path} exists.", file=sys.stderr)
    print("Choose: [k]eep (default) / [o]verwrite / [d]iff / [a]ll-overwrite / [s]kip-all", file=sys.stderr)

    # Non-interactive safety: if stdin isn't a TTY, default to keep.
    if not sys.stdin.isatty():
        print("(non-interactive — defaulting to keep)", file=sys.stderr)
        return "keep"

    choice = input("> ").strip().lower()
    if choice == "o":
        return "overwrite"
    if choice == "d":
        print("\n" + diff_text, file=sys.stderr)
        return prompt_overwrite(out_path, existing, new, all_mode, is_launchpad_yml)
    if choice == "a":
        if is_launchpad_yml:
            print("[a]ll-overwrite excludes .launchpad/*.yml — still prompting for this file.", file=sys.stderr)
            return prompt_overwrite(out_path, existing, new, all_mode, is_launchpad_yml)
        return "all"
    if choice == "s":
        return "skip-all"
    return "keep"


# --- Main ---

def _read_config_overwrite(repo_root: Path) -> str:
    """Read the existing .launchpad/config.yml and return the configured
    overwrite policy ('skip' | 'prompt' | 'force').

    Returns 'prompt' when:
      - config.yml does not exist (fresh /lp-define run)
      - the file is unreadable or malformed
      - the field is absent or has an unrecognized value
    """
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


def generate(repo_root: Path, *, dry_run: bool = False, force: bool = False, only: set[str] | None = None, product_name: str = "Your Product") -> int:
    # 1. Detect (manifest-based; the brownfield path)
    report = run_detector(repo_root)
    report["_repo_root"] = str(repo_root)  # passed through to render_docs for path-relativizing

    # 2. Compose. The greenfield path: prefer scaffold-receipt.json's
    # `layers_materialized[].stack` over manifest detection. This is required
    # for curate-mode stacks (eleventy/fastapi/django) which write only a
    # README.scaffold.md and produce no detectable manifests, so manifest-
    # detection alone would route them to `generic` (per Codex review #1 on
    # PR #41 cycle 3 — receipt-based dispatch contract gap closure).
    receipt_path = repo_root / ".launchpad" / "scaffold-receipt.json"
    receipt_stacks: list[str] = []
    if receipt_path.is_file():
        try:
            from plugin_scaffold_receipt_loader import load_receipt  # type: ignore[import-not-found]
        except ImportError:
            # Receipt loader is a sibling script; import via runpy-style fallback.
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
                receipt_stacks = [
                    str(layer["stack"])
                    for layer in receipt.get("layers_materialized", [])
                    if isinstance(layer, dict) and "stack" in layer
                ]
            except Exception:
                # Receipt malformed/expired: fall back to manifest detection.
                receipt_stacks = []
    stacks = receipt_stacks or report.get("stacks", ["generic"])
    adapter_out = compose_adapter_output(stacks)

    # 3. Render
    rendered = render_docs(adapter_out, report, product_name)
    if only:
        rendered = {k: v for k, v in rendered.items() if Path(k).name in only}

    # 4. Secret scan
    findings = scan_all(rendered, repo_root)
    if findings:
        print("Secret-scan findings:", file=sys.stderr)
        for out_path, matches in findings.items():
            print(f"  {out_path}:", file=sys.stderr)
            print("    " + secret_scanner.format_matches(matches).replace("\n", "\n    "), file=sys.stderr)
        print("\nRefusing to write. Redact the offending values (or adjust "
              ".launchpad/secret-patterns.txt if false positive) and re-run.",
              file=sys.stderr)
        return 1

    # 5. Resolve overwrite policy.
    # Precedence: CLI --force > config.yml `overwrite:` field > prompt (default).
    # Config policies:
    #   force  — overwrite without asking (CLI --force equivalent)
    #   skip   — never overwrite (treat all existing files as kept)
    #   prompt — interactive per-file menu
    config_policy = _read_config_overwrite(repo_root)
    effective_force = force or (config_policy == "force")
    skip_existing = (not force) and (config_policy == "skip")

    # 6. Write with overwrite policy
    all_mode = effective_force
    summary = {"written": [], "kept": [], "skipped": [], "skipped_after_skip_all": []}
    skip_remaining = False

    for template, out_rel, friendly, is_lp_yml in DOCS:
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
                # config.yml says `overwrite: skip` — never overwrite. The
                # .launchpad/*.yml exclusion still applies (those files
                # are user-tuned and never auto-overwritten regardless).
                summary["kept"].append(out_rel + " (config: skip)")
                continue

            if effective_force:
                decision = "overwrite" if not is_lp_yml else prompt_overwrite(out_rel, existing, new_content, all_mode, is_lp_yml)
            else:
                decision = prompt_overwrite(out_rel, existing, new_content, all_mode, is_lp_yml)

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

        # Ensure parent dir exists
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        out_abs.write_text(new_content, encoding="utf-8")
        summary["written"].append(out_rel)

    # Post-write helpers must NOT run during --dry-run: they mutate
    # .gitignore and create paths.sections_dir on disk, which would violate
    # dry-run's contract of zero filesystem side effects.
    if not dry_run:
        # 6. Post-write: ensure .launchpad/audit.log is gitignored when audit.committed=false
        #    Only runs after a successful write (any new/changed artifacts). The audit-log doc
        #    is a per-user debug log; committing it leaks developer-activity timelines in public
        #    repos and creates merge conflicts on multi-contributor ones.
        ensure_audit_gitignore(repo_root, summary)

        # 7. Post-write: scaffold paths.sections_dir. /lp-shape-section writes
        #    to this directory and fails cleanly if absent. Creating it here saves
        #    the user one "directory not found" error on their first section shape.
        ensure_sections_dir(repo_root, summary)

    # 8. Report
    print(json.dumps({"detected_stacks": stacks, "summary": summary}, indent=2))
    return 0


def ensure_sections_dir(repo_root: Path, summary: dict) -> None:
    """Create paths.sections_dir (default docs/tasks/sections) if missing.

    Reads the just-rendered config.yml to honor user-customized paths.
    Failures are non-fatal — log to stderr but do not fail the generator."""
    config_path = repo_root / ".launchpad" / "config.yml"
    if not config_path.is_file():
        return

    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        sections_dir = ((cfg.get("paths") or {}).get("sections_dir")) or "docs/tasks/sections"
    except Exception:
        sections_dir = "docs/tasks/sections"

    # Realpath confinement: must stay inside repo_root.
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
            # Directory is empty — nothing to note.
            summary.setdefault("dirs_created", []).append(sections_dir)
    except OSError as exc:
        print(
            f"warning: could not create {sections_dir} ({exc}). "
            f"/lp-shape-section will fail until you create it manually.",
            file=sys.stderr,
        )


def ensure_audit_gitignore(repo_root: Path, summary: dict) -> None:
    """Append `.launchpad/audit.log` to the repo's .gitignore if not already
    present and the rendered config.yml says audit.committed is false (default).

    Idempotent: running twice produces no duplicate lines. Silent on success;
    failures (permission, filesystem) are non-fatal — log to stderr but do not
    fail the whole generator run (user can add the line manually)."""
    config_path = repo_root / ".launchpad" / "config.yml"
    if not config_path.is_file():
        return  # no config → /lp-define failed earlier or wasn't invoked

    # Parse committed flag. Default false per the canonical template.
    # Keep this dependency-light; we already have the vendored yaml loader available.
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        committed = bool((cfg.get("audit") or {}).get("committed", False))
    except Exception:
        committed = False  # conservative — treat as "should gitignore"

    if committed:
        return  # user explicitly opted in to committing; do not gitignore

    gitignore_path = repo_root / ".gitignore"
    target_line = ".launchpad/audit.log"

    existing = ""
    if gitignore_path.is_file():
        existing = gitignore_path.read_text(encoding="utf-8")
        # Idempotent check — accept common variants
        for line in existing.splitlines():
            stripped = line.strip()
            if stripped in (target_line, "/" + target_line, "audit.log"):
                return  # already gitignored

    # Append (or create) with a clear marker comment
    marker = "\n# Added by LaunchPad /lp-define — audit log is per-user debug state\n"
    append_block = marker + target_line + "\n"

    try:
        if gitignore_path.is_file():
            # Ensure a trailing newline before appending
            if existing and not existing.endswith("\n"):
                append_block = "\n" + append_block
            with gitignore_path.open("a", encoding="utf-8") as fh:
                fh.write(append_block)
        else:
            gitignore_path.write_text(append_block.lstrip("\n"), encoding="utf-8")
        summary.setdefault("gitignore_updated", []).append(".gitignore (audit.log entry)")
    except OSError as exc:
        print(f"warning: could not update .gitignore ({exc}). "
              f"Add '{target_line}' manually.", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=os.environ.get("LP_REPO_ROOT", os.getcwd()))
    ap.add_argument("--dry-run", action="store_true", help="render + secret-scan but don't write")
    ap.add_argument("--force", action="store_true", help="skip per-file prompts except for .launchpad/*.yml")
    ap.add_argument("--only", default="", help="comma-separated list of filenames to render (e.g. 'PRD.md,config.yml')")
    ap.add_argument("--product-name", default="Your Product", help="Name for PRD scaffold")
    args = ap.parse_args()

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
        )
    except Exception as e:
        print(f"generator error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
