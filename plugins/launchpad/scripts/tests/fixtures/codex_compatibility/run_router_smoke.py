"""Run the Section 6 router package smoke in disposable Codex state."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
PLUGIN_ROOT = SCRIPT_PATH.parents[4]
SCRIPTS = PLUGIN_ROOT / "scripts"
MANIFEST_PATH = SCRIPTS / "plugin-codex-manifest.py"
SUPPORT_PATH = SCRIPTS / "plugin-codex-support.py"
MARKETPLACE = "launchpad-section6-smoke"
PLUGIN = "launchpad"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(
    argv: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
        timeout=90,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--codex-bin", default="codex")
    return parser


def main() -> int:
    args = _parser().parse_args()
    codex_home = args.codex_home.resolve()
    normal_codex_home = Path.home().resolve() / ".codex"
    if codex_home == normal_codex_home or normal_codex_home in codex_home.parents:
        raise SystemExit("--codex-home must not use the normal Codex state")
    if codex_home.exists() and any(codex_home.iterdir()):
        raise SystemExit("--codex-home must be absent or empty")
    codex_home.mkdir(parents=True, exist_ok=True)
    host_home = codex_home / "host-home"
    host_home.mkdir()
    source_stage = codex_home / "source-stage"
    shutil.copytree(
        PLUGIN_ROOT,
        source_stage,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
    )
    package = codex_home / "marketplace" / "plugins" / PLUGIN
    package.mkdir(parents=True)

    manifest = _load("launchpad_section6_smoke_manifest", MANIFEST_PATH)
    support = _load("launchpad_section6_smoke_support", SUPPORT_PATH)
    manifest.sync_manifest(PLUGIN_ROOT, source_stage, write=True)
    candidate = support.build_test_candidate(source_stage)
    packaged_paths = manifest.project_package(
        candidate,
        source_stage,
        package,
        include_generated=False,
    )
    marketplace_root = package.parents[1]
    marketplace_manifest = marketplace_root / ".agents" / "plugins"
    marketplace_manifest.mkdir(parents=True)
    (marketplace_manifest / "marketplace.json").write_text(
        json.dumps(
            {
                "name": MARKETPLACE,
                "owner": {"name": "LaunchPad test fixture"},
                "metadata": {
                    "description": "Disposable Section 6 router smoke fixture."
                },
                "plugins": [
                    {
                        "name": PLUGIN,
                        "description": "Disposable LaunchPad router smoke fixture.",
                        "source": f"./plugins/{PLUGIN}",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env.update(
        {
            "CODEX_HOME": str(codex_home),
            "HOME": str(host_home),
            "NO_COLOR": "1",
        }
    )
    selector = f"{PLUGIN}@{MARKETPLACE}"
    installed = False
    marketplace_added = False
    results: list[dict[str, object]] = []
    try:
        version = _run([args.codex_bin, "--version"], env=env, cwd=host_home)
        results.append(
            {"probe": "codex-version", "result": "PASS", "detail": version.stdout.strip()}
        )
        _run(
            [
                args.codex_bin,
                "plugin",
                "marketplace",
                "add",
                str(marketplace_root),
                "--json",
            ],
            env=env,
            cwd=host_home,
        )
        marketplace_added = True
        _run(
            [args.codex_bin, "plugin", "add", selector, "--json"],
            env=env,
            cwd=host_home,
        )
        installed = True
        listing = _run(
            [args.codex_bin, "plugin", "list", "--json"],
            env=env,
            cwd=host_home,
        ).stdout
        if PLUGIN not in listing or MARKETPLACE not in listing:
            raise RuntimeError("installed plugin is missing from the isolated listing")

        cached_routers = list(
            (codex_home / "plugins" / "cache").rglob("scripts/plugin-codex-router.py")
        )
        if len(cached_routers) != 1:
            raise RuntimeError("isolated cache does not contain exactly one router")
        installed_root = cached_routers[0].parents[1]
        required = (
            ".codex-plugin/plugin.json",
            "codex/adapter-protocol.json",
            "codex/skills/lp/SKILL.md",
            "scripts/plugin-codex-router.py",
        )
        if any(not (installed_root / relative).is_file() for relative in required):
            raise RuntimeError("installed package is missing a router surface")
        if list((installed_root / "codex" / "skills").glob("*/SKILL.md")) != [
            installed_root / "codex" / "skills" / "lp" / "SKILL.md"
        ]:
            raise RuntimeError("installed package exposes more than the lp skill")
        results.append(
            {
                "probe": "sealed-install",
                "result": "PASS",
                "detail": f"{len(packaged_paths)} exact runtime files",
            }
        )

        prompt = _run(
            [args.codex_bin, "debug", "prompt-input", "$lp help"],
            env=env,
            cwd=host_home,
        ).stdout
        if (
            "launchpad:lp" not in prompt
            or "Route an explicit LaunchPad request" not in prompt
            or "$lp help" not in prompt
        ):
            raise RuntimeError("Codex did not advertise the isolated router skill")
        results.append(
            {
                "probe": "host-discovery",
                "result": "PASS",
                "detail": "launchpad:lp advertised from the sealed package",
            }
        )
        results.append(
            {
                "probe": "bare-lp-authenticated-routing",
                "result": "BLOCKED",
                "detail": (
                    "host exposes a namespaced skill and no authenticated argument-tail "
                    "binding to packaged router code"
                ),
            }
        )
    finally:
        if installed:
            _run(
                [args.codex_bin, "plugin", "remove", selector, "--json"],
                env=env,
                cwd=host_home,
                check=False,
            )
        if marketplace_added:
            _run(
                [
                    args.codex_bin,
                    "plugin",
                    "marketplace",
                    "remove",
                    MARKETPLACE,
                    "--json",
                ],
                env=env,
                cwd=host_home,
                check=False,
            )
    print(json.dumps({"codex_home": str(codex_home), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
