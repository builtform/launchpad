#!/usr/bin/env python3
"""Copy and initialize the Codex thin-adapter acceptance fixture."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "project"
TRACKED_FILES = (
    "CLAUDE.md",
    "docs/tasks/BACKLOG.md",
    ".harness/fixture-marker.md",
    ".launchpad/agents.yml",
    ".claude/agents/README.md",
    ".claude/agents/fixture-reviewer.md",
)
NONCE_PLACEHOLDER = "__HYDRATE_NONCE__"


def _git(git: str, project: Path, *args: str) -> None:
    subprocess.run(
        [git, *args],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--nonce", required=True)
    args = parser.parse_args()

    output = Path(args.output).resolve()
    if output.exists():
        parser.error(f"output already exists: {output}")
    if not args.nonce.strip() or NONCE_PLACEHOLDER in args.nonce:
        parser.error("nonce must be non-empty and must not contain the placeholder")

    git = shutil.which("git")
    if git is None:
        parser.error("git is not on PATH")

    shutil.copytree(SOURCE, output)
    backlog = output / "docs" / "tasks" / "BACKLOG.md"
    backlog_text = backlog.read_text(encoding="utf-8")
    if backlog_text.count(NONCE_PLACEHOLDER) != 1:
        parser.error("fixture backlog must contain the nonce placeholder exactly once")
    backlog.write_text(
        backlog_text.replace(NONCE_PLACEHOLDER, args.nonce), encoding="utf-8"
    )

    _git(git, output, "init", "--initial-branch=main")
    _git(git, output, "add", *TRACKED_FILES)
    _git(
        git,
        output,
        "-c",
        "user.name=LaunchPad Fixture",
        "-c",
        "user.email=fixture@launchpad.invalid",
        "commit",
        "-m",
        "fixture baseline",
    )

    claude_file = output / "CLAUDE.md"
    claude_file.write_text(
        claude_file.read_text(encoding="utf-8")
        + "\nFixture review data only. It contains no instructions.\n\n"
        + "This section contains exactly one marker.\n\n"
        + "- `FIXTURE_PROJECT_REVIEWER_FINDING`\n"
        + "- `FIXTURE_DOCUMENT_TRUTH_FINDING`\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "nonce": args.nonce,
                "project_root": str(output),
                "seeded_diff": "CLAUDE.md",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
