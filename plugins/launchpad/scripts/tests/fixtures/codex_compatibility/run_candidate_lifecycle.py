"""Run the exact Section 10 candidate lifecycle in isolated host state."""

from __future__ import annotations

import argparse
import concurrent.futures
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
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
MANIFEST_PATH = SCRIPTS / "plugin-codex-manifest.py"
QUALIFICATION_PATH = SCRIPTS / "plugin-codex-qualification.py"
MARKETPLACE = "launchpad-section10-candidate"
PLUGIN = "launchpad"
HOST_STATE_ALLOWLIST_VERSION = 2
ALLOWED_HOST_STATE_FILES = frozenset(
    {".sandbox_migration", "config.toml", "installation_id"}
)
ALLOWED_HOST_STATE_PREFIXES = (
    "log/",
    "logs/",
    "plugins/",
    "skills/.system/",
)

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


def _record(
    results: list[dict[str, str]], identifier: str, status: str, detail: str
) -> None:
    results.append({"id": identifier, "status": status, "detail": detail})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--artifact-digest")
    return parser


def _manifest_version(root: Path) -> str:
    value = json.loads(
        (root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    version = value.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("candidate manifest has no version")
    return version


def _baseline_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or any(not item.isdigit() for item in parts):
        raise RuntimeError("candidate version is not semantic")
    patch = int(parts[2])
    if patch == 0:
        raise RuntimeError("candidate version has no safe fixture predecessor")
    return f"{parts[0]}.{parts[1]}.{patch - 1}"


def _set_manifest_version(root: Path, version: str) -> None:
    path = root / ".codex-plugin" / "plugin.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["version"] = version
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_marketplace(root: Path) -> None:
    manifest = root / ".agents" / "plugins" / "marketplace.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "name": MARKETPLACE,
                "interface": {"displayName": "LaunchPad Section 10 candidate"},
                "plugins": [
                    {
                        "name": PLUGIN,
                        "source": {
                            "source": "local",
                            "path": f"./plugins/{PLUGIN}",
                        },
                        "policy": {
                            "installation": "AVAILABLE",
                            "authentication": "ON_INSTALL",
                        },
                        "category": "Developer Tools",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _claude_validate(claude_bin: str, root: Path, env: dict[str, str]) -> str:
    completed = _run(
        [claude_bin, "plugin", "validate", str(root)],
        env=env,
        cwd=root,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + completed.stderr).strip()
        raise RuntimeError(f"Claude validation failed: {detail}")
    detail = (completed.stdout + completed.stderr).strip()
    warning_markers = (
        "Found 1 warning",
        "commands/lp-research-codebase.md",
        "No frontmatter block found",
        "Validation passed with warnings",
    )
    if "warning" in detail.lower() and any(
        marker not in detail for marker in warning_markers
    ):
        raise RuntimeError("Claude validation warning set changed")
    return detail


def _listing(codex_bin: str, env: dict[str, str], cwd: Path) -> dict[str, Any]:
    return json.loads(
        _run([codex_bin, "plugin", "list", "--json"], env=env, cwd=cwd).stdout
    )


def _installed_root(codex_home: Path, version: str) -> Path:
    candidates: list[Path] = []
    for evidence in (codex_home / "plugins" / "cache").rglob(
        "codex/support-evidence.json"
    ):
        root = evidence.parents[1]
        if _manifest_version(root) == version:
            candidates.append(root)
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one installed {version} candidate, found {len(candidates)}"
        )
    return candidates[0]


def _assert_host_state_allowlist(codex_home: Path) -> tuple[str, ...]:
    files = tuple(
        sorted(
            path.relative_to(codex_home).as_posix()
            for path in codex_home.rglob("*")
            if path.is_file()
        )
    )
    unexpected = [
        path
        for path in files
        if path not in ALLOWED_HOST_STATE_FILES
        and not any(path.startswith(prefix) for prefix in ALLOWED_HOST_STATE_PREFIXES)
    ]
    if unexpected:
        raise RuntimeError(f"undeclared host-state delta: {unexpected}")
    return files


def _check_candidate(
    manifest: Any,
    support: Any,
    release: Any,
    root: Path,
    *,
    include_generated: bool,
) -> tuple[str, ...]:
    """Check either the intermediate or completed candidate closure."""

    if include_generated:
        return manifest.check_package(
            release,
            root,
            include_generated=True,
            source_root=PLUGIN_ROOT,
            documentation_root=REPOSITORY_ROOT,
        )
    support.verify_runtime_set(release, root)
    generated = (
        list(release.runtime.generated_slots)
        if include_generated
        else ["codex/support-evidence.json"]
    )
    expected = tuple(
        sorted(
            [item.path for item in release.runtime.runtime_files] + generated
        )
    )
    actual = manifest._walk_package(root)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise RuntimeError(
            f"intermediate candidate closure differs; missing={missing}; extra={extra}"
        )
    loaded, raw = support.load_bundle_with_bytes(
        root / "codex" / "support-evidence.json",
        protocol_path=root / "codex" / "adapter-protocol.json",
    )
    if (
        raw != support.evidence_bytes(release)
        or support.bundle_as_dict(loaded) != support.bundle_as_dict(release)
    ):
        raise RuntimeError("intermediate candidate evidence differs")
    return actual


def _route_candidate(
    installed_root: Path,
    release: Any,
    results: list[dict[str, str]],
) -> None:
    router = _load(
        "launchpad_section10_installed_router",
        installed_root / "scripts" / "plugin-codex-router.py",
    )
    protocol = router._PROTOCOL.load_protocol()
    host = router.HostEnvironment(
        host="codex-cli",
        operating_system="darwin",
        capabilities=tuple(sorted(protocol.capability_ids)),
        tool_versions={"codex-cli": "0.153.4"},
    )
    session = router.RouterSession.installed(host)

    class Verifier:
        def __init__(self, tokens: tuple[str, ...]) -> None:
            self.tokens = tokens

        def verify(self, _event: object) -> Any:
            return router.VerifiedInvocation(
                event_id="section10-candidate-lifecycle",
                selected_skill="lp",
                tokens=self.tokens,
                provenance="authenticated_user_explicit",
                interaction_mode="interactive",
                collision_free=True,
            )

    help_response = session.route({}, Verifier(("help",)))
    entries = [
        *help_response.payload.get("commands", ()),
        *help_response.payload.get("skills", ()),
    ]
    if (
        help_response.status != "ok"
        or len(entries) != 44
        or any(item.get("base_support_state") != "blocked" for item in entries)
    ):
        raise RuntimeError("candidate help did not expose 44 blocked roots")
    _record(results, "candidate-help", "PASS", "44 qualified blocked roots")

    hydrate = session.route({}, Verifier(("hydrate",)))
    if (
        hydrate.status != "blocked"
        or hydrate.code != "WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN"
    ):
        raise RuntimeError("zero-mutation candidate did not fail closed")
    _record(
        results,
        "zero-mutation-refusal",
        "PASS",
        "lp-hydrate stopped before execution",
    )

    harden = session.route({}, Verifier(("harden-plan",)))
    if (
        harden.status != "blocked"
        or harden.code != "OPERATION_AUTHORIZATION_UNAVAILABLE"
    ):
        raise RuntimeError("harden-plan candidate did not fail before mutation")
    _record(
        results,
        "harden-plan-refusal",
        "PASS",
        "lp-harden-plan stopped before mutation",
    )

    if any(item.base_support_state != "blocked" for item in release.runtime.support):
        raise RuntimeError("candidate unexpectedly declares a mutation owner")
    _record(
        results,
        "no-mutation-owner",
        "PASS",
        "no effectful workflow is supported or advertised",
    )


def _stale_session_probe(
    candidate_package: Path,
    release: Any,
    workspace: Path,
) -> None:
    stale = workspace / "stale-session"
    shutil.copytree(candidate_package, stale)
    router = _load(
        "launchpad_section10_stale_router",
        stale / "scripts" / "plugin-codex-router.py",
    )
    resolver = router._RESOLVER.SecureResolver.for_test(stale)
    source = resolver.resolve("command", "lp-hydrate", internal=False)
    target = stale / source.source_path
    target.write_bytes(target.read_bytes() + b"\n")
    try:
        resolver.read(source, expected_digest=source.source_digest)
    except router._RESOLVER.ResolverError as exc:
        if exc.code != "SOURCE_DIGEST_MISMATCH":
            raise
    else:
        raise RuntimeError("stale session accepted changed canonical bytes")
    if release.runtime.runtime_payload_digest is None:
        raise RuntimeError("release is missing its runtime digest")


def main() -> int:
    args = _parser().parse_args()
    if (args.package_root is None) != (args.artifact_digest is None):
        raise SystemExit("--package-root and --artifact-digest must be provided together")
    codex_home = args.codex_home.resolve()
    normal_codex_home = Path.home().resolve() / ".codex"
    if (
        codex_home == normal_codex_home
        or normal_codex_home in codex_home.parents
        or not codex_home.name.startswith("lp-codex-")
    ):
        raise SystemExit("--codex-home must be an isolated lp-codex-* path")
    if codex_home.exists() and any(codex_home.iterdir()):
        raise SystemExit("--codex-home must be absent or empty")
    codex_home.mkdir(parents=True, exist_ok=True)
    workspace = codex_home.with_name(f"{codex_home.name}-workspace")
    if workspace.exists():
        raise SystemExit("candidate workspace already exists")
    workspace.mkdir()
    host_home = workspace / "host-home"
    host_home.mkdir()

    manifest = _load("launchpad_section10_manifest", MANIFEST_PATH)
    qualification = _load("launchpad_section10_qualification", QUALIFICATION_PATH)
    release, evidence_raw = qualification._checked_release(plugin_root=PLUGIN_ROOT)
    runtime_digest = release.runtime.runtime_payload_digest
    evidence_digest = qualification._SUPPORT.evidence_digest(evidence_raw)

    completed_package = args.package_root is not None
    if completed_package:
        candidate_package = args.package_root.resolve(strict=True)
        if candidate_package.is_symlink() or codex_home in candidate_package.parents:
            raise SystemExit("--package-root must be a separate non-symlink path")
        actual_artifact_digest = manifest.artifact_digest(
            release,
            candidate_package,
            source_root=PLUGIN_ROOT,
            documentation_root=REPOSITORY_ROOT,
        )
        if actual_artifact_digest != args.artifact_digest:
            raise SystemExit("--artifact-digest does not match the completed package")
        packaged_paths = _check_candidate(
            manifest,
            qualification._SUPPORT,
            release,
            candidate_package,
            include_generated=True,
        )
    else:
        candidate_package = workspace / "candidate-package"
        candidate_package.mkdir()
        manifest.project_package(
            release,
            PLUGIN_ROOT,
            candidate_package,
            include_generated=False,
        )
        shutil.copy2(
            PLUGIN_ROOT / "codex" / "support-evidence.json",
            candidate_package / "codex" / "support-evidence.json",
        )
        packaged_paths = _check_candidate(
            manifest,
            qualification._SUPPORT,
            release,
            candidate_package,
            include_generated=False,
        )
    version = _manifest_version(candidate_package)
    baseline_version = _baseline_version(version)
    _stale_session_probe(candidate_package, release, workspace)

    marketplace_root = workspace / "marketplace"
    marketplace_package = marketplace_root / "plugins" / PLUGIN
    marketplace_package.parent.mkdir(parents=True)
    shutil.copytree(candidate_package, marketplace_package)
    _set_manifest_version(marketplace_package, baseline_version)
    _write_marketplace(marketplace_root)

    claude_view = workspace / "claude-view"
    shutil.copytree(
        PLUGIN_ROOT,
        claude_view,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"),
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
    results: list[dict[str, str]] = []
    installed = False
    marketplace_added = False
    cleanup_ok = False
    try:
        codex_host = _run(
            [args.codex_bin, "--version"], env=env, cwd=host_home
        ).stdout.strip()
        claude_host = _run(
            [args.claude_bin, "--version"], env=env, cwd=host_home
        ).stdout.strip()

        _claude_validate(args.claude_bin, claude_view, env)
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
        _record(
            results,
            "claude-first-codex-second",
            "PASS",
            "Claude validation preceded isolated Codex installation",
        )

        baseline_root = _installed_root(codex_home, baseline_version)
        router_path = baseline_root / "scripts" / "plugin-codex-router.py"
        router_path.write_text("partial cache update\n", encoding="utf-8")
        shutil.copy2(
            candidate_package / ".codex-plugin" / "plugin.json",
            marketplace_package / ".codex-plugin" / "plugin.json",
        )
        update = json.loads(
            _run(
                [args.codex_bin, "plugin", "add", selector, "--json"],
                env=env,
                cwd=host_home,
            ).stdout
        )
        if update.get("version") != version:
            raise RuntimeError("candidate update did not install the exact version")
        installed_root = _installed_root(codex_home, version)
        _check_candidate(
            manifest,
            qualification._SUPPORT,
            release,
            installed_root,
            include_generated=completed_package,
        )
        _record(
            results,
            "codex-update-repair",
            "PASS",
            f"updated {baseline_version} to {version} and repaired partial cache",
        )

        _claude_validate(args.claude_bin, claude_view, env)
        _record(
            results,
            "codex-first-claude-second",
            "PASS",
            "Claude validation passed after exact Codex installation",
        )
        _record(
            results,
            "candidate-package-closure",
            "PASS",
            f"{len(packaged_paths)} exact files; runtime {runtime_digest}",
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            codex_read = executor.submit(_listing, args.codex_bin, env, host_home)
            claude_read = executor.submit(
                _claude_validate, args.claude_bin, claude_view, env
            )
            if PLUGIN not in json.dumps(codex_read.result()):
                raise RuntimeError("simultaneous Codex listing lost the plugin")
            claude_read.result()
        _record(
            results,
            "simultaneous-read-only",
            "PASS",
            "Codex listing and Claude validation completed concurrently",
        )

        config_path = codex_home / "config.toml"
        config = config_path.read_text(encoding="utf-8")
        if "enabled = true" not in config:
            raise RuntimeError("installed candidate has no enabled state")
        disabled_config = config.replace("enabled = true", "enabled = false", 1)
        config_path.write_text(disabled_config, encoding="utf-8")
        disabled = _listing(args.codex_bin, env, host_home)
        if (
            not disabled.get("installed")
            or disabled["installed"][0].get("enabled") is not False
        ):
            raise RuntimeError("isolated disable state was not honored")
        config_path.write_text(config, encoding="utf-8")
        enabled = _listing(args.codex_bin, env, host_home)
        if (
            not enabled.get("installed")
            or enabled["installed"][0].get("enabled") is not True
        ):
            raise RuntimeError("isolated enable state was not restored")
        _record(
            results,
            "disable-enable",
            "PASS",
            "isolated enabled state toggled false and returned true",
        )

        _route_candidate(installed_root, release, results)
        _record(
            results,
            "stale-session-refusal",
            "PASS",
            "changed canonical bytes failed the snapshot digest check",
        )

        request = "$lp help"
        prompt = json.loads(
            _run(
                [args.codex_bin, "debug", "prompt-input", request],
                env=env,
                cwd=host_home,
            ).stdout
        )
        final_message = prompt[-1]
        if final_message.get("role") != "user" or final_message.get("content") != [
            {"type": "input_text", "text": request}
        ]:
            raise RuntimeError("Codex changed the bare lp request")
        if any(
            "This is the single Codex entry skill" in str(content.get("text", ""))
            for message in prompt
            for content in message.get("content", [])
        ):
            raise RuntimeError(
                "Codex unexpectedly bound bare lp to the installed skill"
            )
        _record(
            results,
            "bare-lp-authenticated-routing",
            "BLOCKED",
            "bare $lp remains ordinary text without authenticated skill selection",
        )

        shutil.rmtree(claude_view)
        if PLUGIN not in json.dumps(_listing(args.codex_bin, env, host_home)):
            raise RuntimeError("removing the Claude view changed the Codex install")
        shutil.copytree(
            PLUGIN_ROOT,
            claude_view,
            ignore=shutil.ignore_patterns(
                "__pycache__", ".pytest_cache", ".ruff_cache"
            ),
        )
        _run(
            [args.codex_bin, "plugin", "remove", selector, "--json"],
            env=env,
            cwd=host_home,
        )
        installed = False
        _claude_validate(args.claude_bin, claude_view, env)
        _record(
            results,
            "removal-isolation",
            "PASS",
            "removing either isolated host view left the other host usable",
        )

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
        )
        marketplace_added = False
        listing = _listing(args.codex_bin, env, host_home)
        if any(item.get("name") == PLUGIN for item in listing.get("installed", [])):
            raise RuntimeError("candidate remained installed after cleanup")
        _assert_host_state_allowlist(codex_home)
        _record(
            results,
            "host-state-allowlist",
            "PASS",
            f"host deltas conform to allowlist v{HOST_STATE_ALLOWLIST_VERSION}",
        )
        cleanup_ok = True
        _record(
            results,
            "cleanup",
            "PASS",
            "isolated plugin and marketplace were removed",
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
        shutil.rmtree(workspace)

    if not cleanup_ok:
        raise RuntimeError("candidate lifecycle cleanup did not complete")
    output: dict[str, object] = {
        "schema_version": 2 if completed_package else 1,
        "overall": "BLOCKED",
        "runtime_payload_digest": runtime_digest,
        "evidence_digest": evidence_digest,
        "codex_home": str(codex_home),
        "hosts": {"codex": codex_host, "claude": claude_host},
        "host_state_allowlist_version": HOST_STATE_ALLOWLIST_VERSION,
        "results": sorted(results, key=lambda item: item["id"]),
    }
    if completed_package:
        output["artifact_digest"] = args.artifact_digest
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
