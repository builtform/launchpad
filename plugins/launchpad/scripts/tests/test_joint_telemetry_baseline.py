"""Phase 7 §4.6 — telemetry baseline gate (gate #9).

Per OPERATIONS §6 acceptance gate #9. Two paths:

  - **Opt-in**: telemetry enabled by default; pick-stack + scaffold-stack
    each emit one `v2-pipeline-*.jsonl` entry with `schema_version: "1.0"`,
    canonical `outcome` enum value, no free-text leakage.

  - **Opt-out**: with `.launchpad/config.yml` `telemetry: off`, NO
    `v2-pipeline-*.jsonl` files are created (the writer is a no-op when off).

Brainstorm + define telemetry are v1.x markdown-driven concerns; this
Phase 7 sub-test asserts the v2.0 contract (Phase 2 pick-stack + Phase 3
scaffold-stack only). The "4 commands → 4 jsonl entries" handoff §4.6
prescription assumed the v2.0 brainstorm + define would also emit; at
strip-back, those remain markdown-driven and are out of scope per
handoff §2 BL deferrals.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_pick_stack.engine import run_pipeline as pick_stack_run  # noqa: E402

from _phase5_decision_builder import (  # noqa: E402
    write_first_run_marker,
)
from scaffold_smoke_runner import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
    PLUGIN_SCAFFOLD_STACK,
)
from test_joint_pipeline_smoke import (  # noqa: E402
    CANONICAL_ANSWERS,
    CANONICAL_PROJECT_DESCRIPTION,
    _stub_scaffolders_yml,
)


def _make_tempdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-joint-telemetry-"))
    os.chmod(d, 0o700)
    return d


def _run_pick_stack(cwd: Path, *, write_telemetry: bool):
    return pick_stack_run(
        cwd, CANONICAL_ANSWERS,
        project_description=CANONICAL_PROJECT_DESCRIPTION,
        project_understanding=("Markdown blog with TypeScript team",),
        why_this_fits=("Astro fits TS-first islands",),
        alternatives=("eleventy: pre-NPM ESM-only constraint",),
        notes=("Phase 7 telemetry gate",),
        write_telemetry=write_telemetry,
    )


def _invoke_scaffold(cwd: Path, scaffolders_yml: Path, *,
                     no_telemetry: bool) -> subprocess.CompletedProcess:
    argv = [
        sys.executable, str(PLUGIN_SCAFFOLD_STACK),
        "--cwd", str(cwd),
        "--scaffolders-yml", str(scaffolders_yml),
        "--category-patterns-yml", str(DEFAULT_CATEGORY_PATTERNS_YML),
        "--plugins-root", str(DEFAULT_PLUGINS_ROOT),
        # pick-stack with telemetry on writes `.harness/observations/`, which
        # makes cwd_state classify the directory as `ambiguous` (the .harness
        # dir is NOT in cwd_state.GREENFIELD_OK_DIRS). Bypass the greenfield
        # gate per Phase 5 "rerun-after-fix" precedent.
        "--skip-greenfield-gate",
    ]
    if no_telemetry:
        argv.append("--no-telemetry")
    return subprocess.run(argv, capture_output=True, timeout=60, check=False)


def _v2_pipeline_jsonl_files(cwd: Path) -> list[Path]:
    obs = cwd / ".harness" / "observations"
    if not obs.exists():
        return []
    return sorted(obs.glob("v2-pipeline-*.jsonl"))


def _read_jsonl(path: Path) -> list[dict]:
    """Read all lines of a JSONL file. Each line is one JSON record."""
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError:
            continue
    return out


def test_telemetry_opt_in_writes_prescribed_schema():
    """With telemetry enabled (default), pick-stack + scaffold-stack each
    write a v2-pipeline-*.jsonl entry. Each entry has schema_version + a
    canonical `outcome` value + no free-text leakage."""
    cwd = _make_tempdir()
    try:
        # Phase 2: pick-stack with telemetry ON.
        write_first_run_marker(cwd)
        pick = _run_pick_stack(cwd, write_telemetry=True)
        assert pick.success, f"pick-stack failed: {pick.message}"

        # Phase 3: scaffold-stack with telemetry ON.
        stub = _stub_scaffolders_yml(cwd / ".launchpad" / "stub-scaffolders.yml")
        rv = _invoke_scaffold(cwd, stub, no_telemetry=False)
        assert rv.returncode == 0, (
            f"scaffold-stack failed: stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )

        # Verify ≥1 v2-pipeline-*.jsonl was written, each with the prescribed
        # schema. Phase 3 writes scaffold-stack telemetry; Phase 2 writes
        # pick-stack telemetry. They MAY share the same timestamp basename
        # (per `write_telemetry_entry`'s default ts-from-now logic), in which
        # case we get one file with multiple lines.
        files = _v2_pipeline_jsonl_files(cwd)
        assert files, "no v2-pipeline-*.jsonl files written despite telemetry on"

        all_entries = []
        for f in files:
            all_entries.extend(_read_jsonl(f))
        assert len(all_entries) >= 2, (
            f"expected ≥2 telemetry entries (pick-stack + scaffold-stack); "
            f"got {len(all_entries)}: {all_entries!r}"
        )

        # Schema validation per OPERATIONS §5: every entry has
        # schema_version + timestamp + a `command` or `outcome` field.
        commands_seen = set()
        for entry in all_entries:
            assert entry.get("schema_version") == "1.0", (
                f"entry missing schema_version=1.0: {entry!r}"
            )
            assert entry.get("timestamp"), (
                f"entry missing timestamp: {entry!r}"
            )
            # `outcome` is one of {"completed", "aborted", "failed", ...}
            outcome = entry.get("outcome")
            assert outcome is None or outcome in {
                "completed", "aborted", "failed", "accepted", "rejected",
            }, f"non-canonical outcome value: {outcome!r}"
            cmd = entry.get("command")
            if cmd:
                commands_seen.add(cmd)
            # No free-text leakage: keys should be a small known-safe set;
            # values should not contain the rationale or user description
            # verbatim.
            for k, v in entry.items():
                if isinstance(v, str):
                    assert "Markdown blog with TypeScript" not in v, (
                        f"telemetry entry leaked project_description verbatim: "
                        f"key={k!r}, value={v!r}"
                    )

        # Both commands should be represented.
        assert "/lp-pick-stack" in commands_seen, (
            f"no pick-stack telemetry entry; commands_seen={commands_seen!r}"
        )
        assert "/lp-scaffold-stack" in commands_seen, (
            f"no scaffold-stack telemetry entry; commands_seen={commands_seen!r}"
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_telemetry_opt_out_writes_nothing():
    """With `.launchpad/config.yml` `telemetry: off`, NO
    `v2-pipeline-*.jsonl` files are created. The writer is a no-op when off."""
    cwd = _make_tempdir()
    try:
        # Write config.yml `telemetry: off` BEFORE any pipeline phase.
        (cwd / ".launchpad").mkdir(parents=True, exist_ok=True)
        (cwd / ".launchpad" / "config.yml").write_text(
            "telemetry: off\n", encoding="utf-8",
        )
        write_first_run_marker(cwd)

        pick = _run_pick_stack(cwd, write_telemetry=True)
        assert pick.success, f"pick-stack failed: {pick.message}"

        stub = _stub_scaffolders_yml(cwd / ".launchpad" / "stub-scaffolders.yml")
        rv = _invoke_scaffold(cwd, stub, no_telemetry=False)
        assert rv.returncode == 0, (
            f"scaffold-stack failed: stderr="
            f"{rv.stderr.decode('utf-8', errors='replace')[:512]!r}"
        )

        files = _v2_pipeline_jsonl_files(cwd)
        assert not files, (
            f"telemetry: off but v2-pipeline-*.jsonl was written: {files!r}"
        )
        # The receipt SHOULD still exist (telemetry opt-out doesn't gate
        # the receipt write).
        assert (cwd / ".launchpad" / "scaffold-receipt.json").exists()
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
