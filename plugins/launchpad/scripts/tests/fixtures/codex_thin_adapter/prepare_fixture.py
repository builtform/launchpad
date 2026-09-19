#!/usr/bin/env python3
"""Copy and initialize the Codex thin-adapter acceptance fixture."""

from __future__ import annotations

import argparse
import json
import re
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
PLUGIN_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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
    parser.add_argument("--output")
    parser.add_argument("--nonce")
    parser.add_argument("--plugin-source")
    parser.add_argument("--plugin-output")
    parser.add_argument("--plugin-name")
    parser.add_argument("--probe-output")
    parser.add_argument("--probe-nonce")
    parser.add_argument("--plan-path")
    args = parser.parse_args()

    if args.plugin_source is not None:
        required = {
            "--plugin-output": args.plugin_output,
            "--plugin-name": args.plugin_name,
            "--probe-output": args.probe_output,
            "--probe-nonce": args.probe_nonce,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            parser.error(f"probe mode requires: {', '.join(missing)}")
        assert args.plugin_output
        assert args.plugin_name
        assert args.probe_output
        assert args.probe_nonce
        if not PLUGIN_NAME_PATTERN.fullmatch(args.plugin_name):
            parser.error("plugin name must use lowercase letters, digits, and hyphens")

        plugin_source = Path(args.plugin_source).resolve(strict=True)
        plugin_output = Path(args.plugin_output).resolve()
        probe_output = Path(args.probe_output).resolve()
        if plugin_output.exists():
            parser.error(f"plugin output already exists: {plugin_output}")
        if plugin_output.parent.name != "plugins":
            parser.error("plugin output must be inside a marketplace plugins directory")

        shutil.copytree(plugin_source, plugin_output)
        for manifest_name in (
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
        ):
            manifest_path = plugin_output / manifest_name
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["name"] = args.plugin_name
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

        command = plugin_output / "commands" / "lp-zzz-probe.md"
        command.write_text(
            "---\n"
            "name: lp-zzz-probe\n"
            "description: Write the supplied acceptance nonce to its probe file\n"
            "---\n\n"
            "# Acceptance probe\n\n"
            f"Accept only the argument `{args.probe_nonce}`. Write that exact argument "
            f"to `{probe_output}`. A trailing newline is allowed. Write no other file.\n",
            encoding="utf-8",
        )

        marketplace_root = plugin_output.parent.parent
        marketplace_name = f"{args.plugin_name}-marketplace"
        marketplace_dir = marketplace_root / ".claude-plugin"
        marketplace_dir.mkdir(parents=True, exist_ok=True)
        marketplace = {
            "name": marketplace_name,
            "owner": {"name": "LaunchPad acceptance fixture"},
            "metadata": {"description": "Disposable probe marketplace"},
            "plugins": [
                {
                    "name": args.plugin_name,
                    "description": "Disposable LaunchPad probe",
                    "source": f"./plugins/{args.plugin_name}",
                }
            ],
        }
        (marketplace_dir / "marketplace.json").write_text(
            json.dumps(marketplace, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "invocation": f"${args.plugin_name}:lp zzz-probe {args.probe_nonce}",
                    "marketplace_name": marketplace_name,
                    "marketplace_root": str(marketplace_root),
                    "plugin_root": str(plugin_output),
                    "probe_output": str(probe_output),
                },
                sort_keys=True,
            )
        )
        return 0

    if args.output is None or args.nonce is None:
        parser.error("project mode requires --output and --nonce")
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

    tracked_files = list(TRACKED_FILES)
    plan_path: Path | None = None
    if args.plan_path is not None:
        plan_relative = Path(args.plan_path)
        if plan_relative.is_absolute() or ".." in plan_relative.parts:
            parser.error("plan path must stay inside the fixture project")
        plan_path = output / plan_relative
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            "---\n"
            "title: Fixture status endpoint\n"
            "status: draft\n"
            "---\n\n"
            "# Fixture plan\n\n"
            "## Goal\n\n"
            "Add a status endpoint that reports whether the service is ready.\n\n"
            "## Scope\n\n"
            "- Add the endpoint.\n"
            "- Return a JSON readiness value.\n\n"
            "## Verification\n\n"
            "- Run the configured tests.\n",
            encoding="utf-8",
        )
        tracked_files.append(str(plan_relative))

    _git(git, output, "init", "--initial-branch=main")
    _git(git, output, "add", *tracked_files)
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

    payload = {
        "nonce": args.nonce,
        "project_root": str(output),
        "seeded_diff": "CLAUDE.md",
    }
    if plan_path is not None:
        payload["plan_path"] = str(plan_path)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
