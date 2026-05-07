"""v2.1 Codex PR #50 Slice E regression: plugin-restamp-redact-wip.py filter.

Tests:
  * Strips wip(slice-a):, wip(slice-b): entries
  * Preserves non-slice wip(experiment): entries
  * Preserves conventional-commit subjects
  * No-op on missing JSONL
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "plugin_restamp_redact_wip",
        _SCRIPTS_DIR / "plugin-restamp-redact-wip.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_strips_wip_slice_entries(tmp_path):
    mod = _load_module()
    obs_dir = tmp_path / ".harness" / "observations"
    obs_dir.mkdir(parents=True)
    jsonl = obs_dir / "restamp-history.jsonl"
    jsonl.write_text(
        "\n".join([
            json.dumps({"subject": "feat: add thing"}),
            json.dumps({"subject": "wip(slice-a): security"}),
            json.dumps({"subject": "wip(slice-b): bootstrap"}),
            json.dumps({"subject": "fix: bug"}),
        ]) + "\n",
        encoding="utf-8",
    )
    rc = mod.main(["--repo-root", str(tmp_path)])
    assert rc == 0
    out_lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(out_lines) == 2
    subjects = [json.loads(line)["subject"] for line in out_lines]
    assert subjects == ["feat: add thing", "fix: bug"]


def test_preserves_non_slice_wip_entries(tmp_path):
    mod = _load_module()
    obs_dir = tmp_path / ".harness" / "observations"
    obs_dir.mkdir(parents=True)
    jsonl = obs_dir / "restamp-history.jsonl"
    jsonl.write_text(
        json.dumps({"subject": "wip(experiment): trying X"}) + "\n",
        encoding="utf-8",
    )
    rc = mod.main(["--repo-root", str(tmp_path)])
    assert rc == 0
    out_lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(out_lines) == 1
    subject = json.loads(out_lines[0])["subject"]
    assert "experiment" in subject


def test_no_op_on_missing_jsonl(tmp_path):
    mod = _load_module()
    rc = mod.main(["--repo-root", str(tmp_path)])
    assert rc == 0


def test_malformed_jsonl_returns_65(tmp_path):
    mod = _load_module()
    obs_dir = tmp_path / ".harness" / "observations"
    obs_dir.mkdir(parents=True)
    jsonl = obs_dir / "restamp-history.jsonl"
    jsonl.write_text("not valid json\n", encoding="utf-8")
    rc = mod.main(["--repo-root", str(tmp_path)])
    assert rc == 65
