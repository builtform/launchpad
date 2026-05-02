"""C4 (Layer 8/9): scaffold-rejection-<ts>.jsonl inline protocol verification.

Trigger sha256_mismatch; assert:
  - two-part stderr surfacing (Part 1 BEFORE write, Part 2 AFTER)
  - microsec+pid filename
  - no .scaffold-rejection.lock created
  - ENOENT fallback works (set .harness/observations/ unwritable)
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _scaffold_stack_helpers import (
    make_decision,
    write_minimal_categories_yml,
    write_minimal_scaffolders_yml,
)
from lp_scaffold_stack.engine import run_pipeline
from lp_scaffold_stack.rejection_logger import write_rejection


def _trigger_sha256_mismatch(tmp_path: Path, *, stderr=None):
    project = tmp_path / "project"
    project.mkdir()
    decision_path, payload = make_decision(project)
    payload["sha256"] = "0" * 64
    decision_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True),
        encoding="utf-8",
    )
    plugins_root = tmp_path / "plugins-root"
    write_minimal_scaffolders_yml(plugins_root / "scaffolders.yml")
    write_minimal_categories_yml(plugins_root / "data" / "category-patterns.yml")
    return run_pipeline(
        project,
        scaffolders_yml=plugins_root / "scaffolders.yml",
        category_patterns_yml=plugins_root / "data" / "category-patterns.yml",
        plugins_root=plugins_root,
        stderr=stderr,
    )


def test_two_part_stderr_ordering(tmp_path: Path):
    err = io.StringIO()
    result = _trigger_sha256_mismatch(tmp_path, stderr=err)
    assert not result.success
    out = err.getvalue()
    lines = [l for l in out.splitlines() if l.strip()]
    # Part 1 first.
    assert lines[0].startswith("reason: sha256_mismatch")
    # Part 2 second.
    assert any(l.startswith("log written to:") or l.startswith("forensic log") for l in lines[1:])


def test_filename_carries_microsec_and_pid(tmp_path: Path):
    err = io.StringIO()
    result = _trigger_sha256_mismatch(tmp_path, stderr=err)
    assert result.rejection_log_path is not None
    name = result.rejection_log_path.name
    # scaffold-rejection-2026-04-30T19-42-11.583291Z.<pid>.jsonl
    assert re.match(
        r"scaffold-rejection-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.\d+Z\.\d+\.jsonl$",
        name,
    ), f"bad filename shape: {name}"
    assert f".{os.getpid()}.jsonl" in name


def test_no_lock_file_at_rejection_path(tmp_path: Path):
    err = io.StringIO()
    result = _trigger_sha256_mismatch(tmp_path, stderr=err)
    assert result.rejection_log_path is not None
    obs_dir = result.rejection_log_path.parent
    # Layer 8: no .scaffold-rejection.lock at v2.0.
    assert not (obs_dir / ".scaffold-rejection.lock").exists()


def test_enoent_fallback_to_stderr(tmp_path: Path):
    err = io.StringIO()
    project = tmp_path / "project"
    project.mkdir()
    # Pre-create .harness as a FILE so makedirs fails.
    (project / ".harness").write_bytes(b"oops")

    target = write_rejection(project, reason="sha256_mismatch", stderr=err)
    assert target is None  # forensic log unavailable
    out = err.getvalue()
    assert "reason: sha256_mismatch" in out
    assert "JSONL-fallback" in out or "forensic log unavailable" in out
    # Part 2 still surfaces.
    assert "forensic log unavailable" in out
