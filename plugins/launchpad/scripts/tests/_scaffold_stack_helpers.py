"""Shared helpers for Phase 3 gate + closure tests.

Builds a complete `.launchpad/` directory tree under a tmp_path: rationale.md,
scaffold-decision.json (sealed with canonical_hash), and a fake `scaffolders.yml`
+ `category-patterns.yml` matching the layer's stack.

Test code imports `make_decision_dir(tmp_path, layers=...)` and gets back a
`(repo_root, decision_path)` tuple ready for `engine.run_pipeline()`.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash  # noqa: E402

DEFAULT_RATIONALE = (
    "## project-understanding\n- A static blog\n\n"
    "## matched-category\n- static-blog-astro\n\n"
    "## stack\n- astro as frontend\n\n"
    "## why-this-fits\n- TS-first islands match user preference\n\n"
    "## alternatives\n- eleventy: TypeScript was preferred over ESM-only JS\n\n"
    "## notes\n- Six-month freshness review per BL-105\n"
)

DEFAULT_SUMMARY = [
    {"section": "project-understanding", "bullets": ["A static blog"]},
    {"section": "matched-category", "bullets": ["static-blog-astro"]},
    {"section": "stack", "bullets": ["astro as frontend"]},
    {"section": "why-this-fits", "bullets": ["TS-first islands match"]},
    {"section": "alternatives",
     "bullets": ["eleventy: TypeScript was preferred over ESM-only JS"]},
    {"section": "notes", "bullets": ["BL-105 freshness review"]},
]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bound_cwd_for(cwd: Path) -> dict:
    real = os.path.realpath(str(cwd))
    st = os.stat(real)
    return {"realpath": real, "st_dev": int(st.st_dev), "st_ino": int(st.st_ino)}


def write_rationale(cwd: Path, body: str = DEFAULT_RATIONALE) -> tuple[Path, str]:
    target = cwd / ".launchpad" / "rationale.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target, hashlib.sha256(body.encode("utf-8")).hexdigest()


def make_decision(
    cwd: Path,
    *,
    layers: Sequence[Mapping[str, Any]] | None = None,
    matched_category_id: str = "static-blog-astro",
    monorepo: bool | None = None,
    nonce: str | None = None,
    rationale_body: str = DEFAULT_RATIONALE,
    rationale_summary: Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
    version: str = "1.0",
    write_to_disk: bool = True,
    skip_rationale: bool = False,
) -> tuple[Path, dict]:
    """Build a sealed scaffold-decision.json + write rationale.md.

    Returns (decision_path, sealed_payload). Defaults to a single-layer
    Astro frontend at `.`.
    """
    if layers is None:
        layers = [{"stack": "astro", "role": "frontend", "path": ".",
                   "options": {"template": "blog"}}]
    if monorepo is None:
        monorepo = len(layers) > 1
    if rationale_summary is None:
        rationale_summary = DEFAULT_SUMMARY

    if skip_rationale:
        rsha = hashlib.sha256(b"").hexdigest()
        rationale_path = None
    else:
        rationale_path, rsha = write_rationale(cwd, rationale_body)

    payload = {
        "version": version,
        "layers": [dict(layer) for layer in layers],
        "monorepo": bool(monorepo),
        "matched_category_id": matched_category_id,
        "rationale_path": ".launchpad/rationale.md",
        "rationale_sha256": rsha,
        "rationale_summary": [dict(s) for s in rationale_summary],
        "generated_by": "/lp-pick-stack",
        "generated_at": generated_at or _utc_iso(),
        "nonce": nonce or uuid.uuid4().hex,
        "bound_cwd": _bound_cwd_for(cwd),
    }
    payload["sha256"] = canonical_hash({k: v for k, v in payload.items() if k != "sha256"})

    decision_path = cwd / ".launchpad" / "scaffold-decision.json"
    if write_to_disk:
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False),
            encoding="utf-8",
        )
    return decision_path, payload


def write_minimal_scaffolders_yml(target: Path) -> None:
    """Write a small scaffolders.yml that covers the test stacks."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """schema_version: "1.0"
stacks:
  astro:
    pillar: "Frontend Content/Performance"
    type: "orchestrate"
    flavor: "pure-headless"
    command: "npm create astro@latest"
    headless_flags: ["--", "--yes"]
    knowledge_anchor: "plugins/launchpad/scaffolders/astro-pattern.md"
    knowledge_anchor_sha256: "0000"
    options_schema:
      template: "string"
    last_validated: "2026-04-30"
  fastapi:
    pillar: "Backend Python"
    type: "curate"
    flavor: "n/a"
    knowledge_anchor: "plugins/launchpad/scaffolders/fastapi-pattern.md"
    knowledge_anchor_sha256: "0000"
    options_schema:
      database: "string"
    last_validated: "2026-04-30"
  next:
    pillar: "Frontend App"
    type: "orchestrate"
    flavor: "pure-headless"
    command: "npx create-next-app@latest"
    headless_flags: ["--yes"]
    knowledge_anchor: "plugins/launchpad/scaffolders/next-pattern.md"
    knowledge_anchor_sha256: "0000"
    options_schema:
      src_dir: "boolean"
    last_validated: "2026-04-30"
""",
        encoding="utf-8",
    )


def write_minimal_categories_yml(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        """schema_version: "1.0"
ambiguity_clusters: []
categories:
  - id: "static-blog-astro"
    name: "Static blog (Astro)"
    fits_when: "Q1=static-site-or-blog"
    canonical_stack:
      - stack: "astro"
        role: "frontend"
        path: "."
    explanation: "test"
    last_validated: "2026-04-30"
  - id: "polyglot-next-fastapi"
    name: "Polyglot"
    fits_when: "Q1=web-app"
    canonical_stack:
      - stack: "next"
        role: "frontend"
        path: "apps/web"
      - stack: "fastapi"
        role: "backend"
        path: "services/api"
    explanation: "test"
    last_validated: "2026-04-30"
""",
        encoding="utf-8",
    )


def fake_run_invoker_creating(out_files: dict[str, list[str]]):
    """Build a run_invoker that creates a list of files PER stack-id.

    Lookup key: the first argv element (e.g., "npm" → out_files["npm"]).
    Fallback: the union of all values when no key matches.

    Accepts arbitrary kwargs (e.g., `timeout=`) to mirror `safe_run`'s
    signature without exercising them in tests.
    """
    import subprocess

    def _invoker(argv, cwd, **_kwargs):
        files = out_files.get(argv[0], [])
        if not files:
            for v in out_files.values():
                files.extend(v)
        for f in files:
            target = cwd / f
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("created", encoding="utf-8")
        return subprocess.CompletedProcess(args=list(argv), returncode=0,
                                           stdout=b"", stderr=b"")
    return _invoker


def fake_run_invoker_failing_at(failure_layer_index: int):
    """Build a run_invoker that succeeds for first N layers and fails on the
    (N+1)th. Counts via a closure-state list. Accepts arbitrary kwargs to
    mirror `safe_run`'s signature."""
    import subprocess

    state = {"calls": 0}

    def _invoker(argv, cwd, **_kwargs):
        state["calls"] += 1
        if state["calls"] - 1 == failure_layer_index:
            raise subprocess.CalledProcessError(
                returncode=1, cmd=list(argv), output=b"", stderr=b"sim-fail",
            )
        # Success: drop a marker file so layer materialization tracks it.
        marker = cwd / "marker.scaffolded"
        marker.write_text("created", encoding="utf-8")
        return subprocess.CompletedProcess(args=list(argv), returncode=0,
                                           stdout=b"", stderr=b"")
    return _invoker


__all__ = [
    "DEFAULT_RATIONALE",
    "DEFAULT_SUMMARY",
    "fake_run_invoker_creating",
    "fake_run_invoker_failing_at",
    "make_decision",
    "write_minimal_categories_yml",
    "write_minimal_scaffolders_yml",
    "write_rationale",
]
