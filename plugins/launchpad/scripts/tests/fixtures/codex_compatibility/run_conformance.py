"""Run disposable Section 1 Codex and Claude host-conformance probes."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path(__file__).resolve().parent
MARKETPLACE = "launchpad-section1-fixture"
PLUGIN = "lp-section1-probe"


def run(
    command: list[str],
    *,
    env: dict[str, str],
    check: bool = True,
    cwd: Path = FIXTURE_ROOT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def record(
    results: list[dict[str, Any]],
    check_id: str,
    status: str,
    detail: str,
) -> None:
    results.append({"id": check_id, "status": status, "detail": detail})


def schema_text(schema_dir: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(schema_dir.rglob("*.json"))
    )


def set_plugin_version(marketplace_root: Path, version: str) -> None:
    plugin_root = marketplace_root / "plugins" / PLUGIN
    for manifest in (
        plugin_root / "plugin.json",
        plugin_root / ".codex-plugin/plugin.json",
    ):
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["version"] = version
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--claude-bin", default="claude")
    return parser.parse_args()


def claude_direct_probe(
    claude_bin: str,
    env: dict[str, str],
    component: str,
) -> dict[str, Any]:
    claude_fixture = FIXTURE_ROOT / "claude-plugin"
    completed = run(
        [
            claude_bin,
            "--bare",
            "--plugin-dir",
            str(claude_fixture),
            "--no-session-persistence",
            "--permission-mode",
            "dontAsk",
            "--max-turns",
            "1",
            "--output-format",
            "json",
            "-p",
            f"/{component}",
        ],
        env=env,
        check=False,
    )
    if not completed.stdout.strip():
        raise RuntimeError(f"Claude returned no JSON for {component}")
    return json.loads(completed.stdout)


def main() -> int:
    args = parse_args()
    codex_home = args.codex_home.resolve()
    user_codex_home = Path.home() / ".codex"
    if codex_home == user_codex_home or user_codex_home in codex_home.parents:
        raise SystemExit(
            "--codex-home must not be inside the user's normal Codex state"
        )

    codex_home.mkdir(parents=True, exist_ok=True)
    isolated_home = codex_home / "host-home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "CODEX_HOME": str(codex_home),
            "HOME": str(isolated_home),
            "NO_COLOR": "1",
        }
    )
    results: list[dict[str, Any]] = []
    selector = f"{PLUGIN}@{MARKETPLACE}"
    marketplace_copy = codex_home / "marketplace"
    shutil.copytree(FIXTURE_ROOT, marketplace_copy)

    try:
        codex_version = run([args.codex_bin, "--version"], env=env).stdout.strip()
        claude_version = run([args.claude_bin, "--version"], env=env).stdout.strip()
        record(results, "host-versions", "PASS", f"{codex_version}; {claude_version}")

        run(
            [
                args.codex_bin,
                "plugin",
                "marketplace",
                "add",
                str(marketplace_copy),
                "--json",
            ],
            env=env,
        )
        run([args.codex_bin, "plugin", "add", selector, "--json"], env=env)
        listing = run([args.codex_bin, "plugin", "list", "--json"], env=env).stdout
        if PLUGIN not in listing or MARKETPLACE not in listing:
            raise RuntimeError("installed plugin is missing from codex plugin list")
        record(results, "codex-plugin-install-list", "PASS", selector)

        cache_root = codex_home / "plugins" / "cache"
        helpers = list(cache_root.rglob("scripts/read_sibling.py"))
        if len(helpers) != 1:
            raise RuntimeError(f"expected one cached helper, found {len(helpers)}")
        installed_root = helpers[0].parents[1]
        for relative in (
            "plugin.json",
            ".codex-plugin/plugin.json",
            "skills/lp/SKILL.md",
            "canonical/lp-probe.md",
        ):
            if not (installed_root / relative).is_file():
                raise RuntimeError(f"cached plugin is missing {relative}")
        marker = run([sys.executable, str(helpers[0])], env=env).stdout.strip()
        if marker != "LP_SECTION1_INSTALLED_ROOT_OK":
            raise RuntimeError("installed-root helper returned the wrong marker")
        record(
            results,
            "installed-root-and-dual-manifest",
            "PASS",
            str(installed_root),
        )

        if (installed_root / "agents/openai.yaml").exists():
            raise RuntimeError("fixture unexpectedly contains agents/openai.yaml")
        record(results, "openai-yaml-omission", "PASS", "file absent by design")

        collision_project = codex_home / "collision-project"
        shutil.copytree(
            FIXTURE_ROOT / "collisions" / "repo",
            collision_project,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            FIXTURE_ROOT / "collisions" / "user",
            isolated_home,
            dirs_exist_ok=True,
        )
        prompt_input = run(
            [args.codex_bin, "debug", "prompt-input", "$lp"],
            env=env,
            cwd=collision_project,
        ).stdout
        collision_markers = (
            "Test-only repository collision candidate.",
            "Test-only user collision candidate.",
            "lp-section1-probe:lp",
        )
        if any(marker not in prompt_input for marker in collision_markers):
            raise RuntimeError("Codex did not discover every collision candidate")
        record(
            results,
            "duplicate-skill-resolution",
            "BLOCKED",
            "repository and user skills share lp with no precedence; the installed "
            "skill is marketplace-namespaced",
        )

        set_plugin_version(marketplace_copy, "0.1.1")
        update_payload = json.loads(
            run(
                [args.codex_bin, "plugin", "add", selector, "--json"],
                env=env,
            ).stdout
        )
        if update_payload.get("version") != "0.1.1":
            raise RuntimeError("local plugin update did not install version 0.1.1")

        config_path = codex_home / "config.toml"
        config = config_path.read_text(encoding="utf-8")
        if "enabled = true" not in config:
            raise RuntimeError("installed plugin has no enabled configuration")
        config_path.write_text(
            config.replace("enabled = true", "enabled = false", 1),
            encoding="utf-8",
        )
        disabled = json.loads(
            run([args.codex_bin, "plugin", "list", "--json"], env=env).stdout
        )
        if disabled["installed"][0].get("enabled") is not False:
            raise RuntimeError("plugin disable state was not honored")
        config_path.write_text(config, encoding="utf-8")
        record(
            results,
            "codex-plugin-update-disable",
            "PASS",
            "plugin add updated 0.1.0 to 0.1.1; enabled=false disabled it",
        )

        schema_dir = codex_home / "app-server-schema"
        run(
            [
                args.codex_bin,
                "app-server",
                "generate-json-schema",
                "--experimental",
                "--out",
                str(schema_dir),
            ],
            env=env,
        )
        schema = schema_text(schema_dir)
        if "SkillUserInput" not in schema or '"skill"' not in schema:
            raise RuntimeError("app-server schema has no typed skill input")
        record(
            results,
            "typed-skill-input",
            "PASS",
            "SkillUserInput is present in the generated protocol schema",
        )
        if '"AttestationGenerateParams"' not in schema:
            raise RuntimeError("app-server schema has no attestation request type")
        record(
            results,
            "enforcement-boundaries",
            "BLOCKED",
            "typed input and opaque attestation are host protocol data, not "
            "authenticated plugin enforcement APIs",
        )

        claude_fixture = FIXTURE_ROOT / "claude-plugin"
        validation = run(
            [args.claude_bin, "plugin", "validate", str(claude_fixture)],
            env=env,
            check=False,
        )
        detail = (validation.stdout + validation.stderr).strip()
        status = "PASS" if validation.returncode == 0 else "BLOCKED"
        record(results, "claude-current-validation", status, detail)

        strict_validation = run(
            [
                args.claude_bin,
                "plugin",
                "validate",
                "--strict",
                str(claude_fixture),
            ],
            env=env,
            check=False,
        )
        strict_detail = (strict_validation.stdout + strict_validation.stderr).strip()
        strict_status = "PASS" if strict_validation.returncode == 0 else "BLOCKED"
        record(
            results, "claude-current-strict-validation", strict_status, strict_detail
        )

        namespace = "lp-section1-claude-probe"
        missing = claude_direct_probe(
            args.claude_bin, env, f"{namespace}:lp-probe-missing"
        )
        explicit_false = claude_direct_probe(
            args.claude_bin, env, f"{namespace}:lp-probe-false"
        )
        explicit_true = claude_direct_probe(
            args.claude_bin, env, f"{namespace}:lp-probe-true"
        )
        if "Not logged in" not in missing.get("result", ""):
            raise RuntimeError("omitted user-invocable did not attempt invocation")
        if explicit_false.get("result") != "" or explicit_false.get("num_turns") != 0:
            raise RuntimeError("user-invocable false was not suppressed")
        if "Not logged in" not in explicit_true.get("result", ""):
            raise RuntimeError("user-invocable true did not attempt invocation")
        record(
            results,
            "claude-user-invocable-runtime-discovery",
            "PASS",
            "omitted and true invoke; false is recognized and suppressed",
        )
    finally:
        remove_plugin = run(
            [args.codex_bin, "plugin", "remove", selector, "--json"],
            env=env,
            check=False,
        )
        remove_marketplace = run(
            [
                args.codex_bin,
                "plugin",
                "marketplace",
                "remove",
                MARKETPLACE,
                "--json",
            ],
            env=env,
            check=False,
        )
        cleanup_ok = (
            remove_plugin.returncode == 0 and remove_marketplace.returncode == 0
        )
        record(
            results,
            "codex-plugin-cleanup",
            "PASS" if cleanup_ok else "BLOCKED",
            "temporary plugin and marketplace removal",
        )

    output = {
        "overall": "BLOCKED",
        "fixture": str(FIXTURE_ROOT),
        "codex_home": str(codex_home),
        "results": results,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
