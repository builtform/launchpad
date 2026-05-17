"""Detect deploy-target signals and propose a preflight config (BL-370).

Closes the v2.1.7 invisibility gap: greenfield consumers never see the
external-infrastructure preflight gate fire because nothing in the
workflow creates ``.launchpad/preflight.config.yaml`` for them. After a
successful ``/lp-bootstrap`` run, this module is invoked as a post-bootstrap
follow-up step that scans for deploy-target signals and (when the user
agrees) writes the config so subsequent ``/lp-build`` and ``/lp-ship``
invocations actually probe Cloudflare / DNS / secrets before deploy time.

The brief at BL-370 originally suggested
``plugin_stack_adapters/deploy_target_detector.py``; the module lives
inside ``lp_bootstrap/`` instead because the work is bootstrap-flow logic
(not stack-adapter logic) and the ``atomic_write_replace`` allowlist plus
the ``/lp_bootstrap/`` CODEOWNERS rule both already cover this directory.

Public API
==========

``detect_deploy_providers(repo_root) -> list[str]``
    Pure scan for deploy-target signals. Returns a sorted list of
    provider-profile names known to ``preflight-profiles/``. Empty on no
    signals.

``proposed_profiles(detected) -> list[str]``
    Maps detected providers to the full profile set the config should
    cover. Always includes ``spec-completeness``; auto-adds
    ``cloudflare-dns`` when ``cloudflare-pages`` is detected.

``preflight_config_path(repo_root)`` / ``skipped_marker_path(repo_root)``
    Canonical artifact locations.

``config_present(repo_root)`` / ``skipped_marker_present(repo_root)``
    Existence checks.

``write_preflight_config(repo_root, providers)``
    Atomic write of the proposed YAML via ``atomic_write_replace``.
    Refuses to overwrite an existing config (caller must remove first).

``write_skipped_marker(repo_root)``
    Writes the opt-out sentinel so future bootstrap runs do not re-prompt.

CLI
===

``python -m lp_bootstrap.preflight_proposer --json [--cwd <p>]``
    Prints a JSON summary (detected, proposed_profiles, config_present,
    skipped_marker_present) for ``/lp-bootstrap`` to consume.

``python -m lp_bootstrap.preflight_proposer --write-config \\
    --providers cloudflare-pages,cloudflare-dns,spec-completeness [--cwd <p>]``
    Writes the config.

``python -m lp_bootstrap.preflight_proposer --write-skipped [--cwd <p>]``
    Writes the skipped marker.

Scope (v2.1.8): detects ``cloudflare-pages``, ``vercel``, ``netlify``.
Other providers join when their profile lands in ``preflight-profiles/``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import atomic_write_replace  # noqa: E402

# Known provider-profile names. Detection MUST stay a subset of profiles
# that actually exist under ``plugins/launchpad/preflight-profiles/``;
# otherwise the generated config fails to load at /lp-preflight time.
KNOWN_PROFILES: frozenset[str] = frozenset(
    {
        "build-time-api-auth",
        "cloudflare-dns",
        "cloudflare-pages",
        "namecheap-dns",
        "netlify",
        "spec-completeness",
        "vercel",
    }
)

_LAUNCHPAD_DIR = ".launchpad"
_PREFLIGHT_CONFIG_NAME = "preflight.config.yaml"
_SKIPPED_MARKER_NAME = "preflight.config.skipped"


def preflight_config_path(repo_root: Path) -> Path:
    return repo_root / _LAUNCHPAD_DIR / _PREFLIGHT_CONFIG_NAME


def skipped_marker_path(repo_root: Path) -> Path:
    return repo_root / _LAUNCHPAD_DIR / _SKIPPED_MARKER_NAME


def config_present(repo_root: Path) -> bool:
    return preflight_config_path(repo_root).exists()


def skipped_marker_present(repo_root: Path) -> bool:
    return skipped_marker_path(repo_root).exists()


# BL-370 v2 (PR #76 security-auditor F2): hard cap on per-file size for
# any reader that can hit attacker-influenceable files in the workflows
# scanner. A workflow file symlinked at `/dev/zero` or a 5 GB log would
# otherwise hang the post-bootstrap step.
_MAX_WORKFLOW_BYTES = 1_000_000

# BL-370 v2 (PR #76 Codex P2): wrangler.* is shared by Cloudflare Pages
# AND Cloudflare Workers. Pages-specific markers narrow detection so a
# Workers-only project does not silently propose a Pages preflight
# config. Any of these key substrings inside wrangler config (case-
# insensitive) is sufficient to classify as Pages.
_WRANGLER_PAGES_MARKERS = (
    "pages_build_output_dir",
    "[pages]",
    '"pages":',
    "[[pages",
    '"pages_build_output_dir"',
)


def _read_text_capped(path: Path, *, limit: int = _MAX_WORKFLOW_BYTES) -> str | None:
    """Read text from ``path``; reject symlinks and any file over ``limit`` bytes.

    Returns ``None`` on rejection or read failure so callers can treat
    the file as absent. Symlink rejection prevents a deploy-target
    scanner from walking onto `/dev/zero` or `/proc/self/mem`; the
    size cap prevents a multi-gigabyte log from blocking bootstrap.
    """
    try:
        if path.is_symlink() or not path.is_file():
            return None
        if path.stat().st_size > limit:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _wrangler_signals_pages(repo_root: Path) -> bool:
    """Return True iff a present `wrangler.*` config has Pages markers."""
    for name in ("wrangler.jsonc", "wrangler.toml", "wrangler.json"):
        text = _read_text_capped(repo_root / name)
        if text is None:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in _WRANGLER_PAGES_MARKERS):
            return True
    return False


def _detect_cloudflare(repo_root: Path) -> str | None:
    # Only classify as cloudflare-pages when a wrangler config is present
    # AND contains a Pages-specific marker. Wrangler-without-marker is a
    # Workers project and gets no Pages profile (avoids generating a
    # Pages preflight config for a non-Pages deploy target).
    if _wrangler_signals_pages(repo_root):
        return "cloudflare-pages"
    return None


def _detect_vercel(repo_root: Path) -> str | None:
    if (repo_root / "vercel.json").is_file():
        return "vercel"
    if (repo_root / ".vercel" / "project.json").is_file():
        return "vercel"
    return None


def _detect_netlify(repo_root: Path) -> str | None:
    if (repo_root / "netlify.toml").is_file():
        return "netlify"
    return None


def _detect_from_workflows(repo_root: Path) -> set[str]:
    workflows_dir = repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return set()
    # Mirror the Pages-vs-Workers narrowing on workflow refs: only the
    # `cloudflare/pages-action` invocation classifies as Pages.
    # `cloudflare/wrangler-action` is shared by Pages and Workers and
    # is dropped here (BL-370 v2 PR #76 Codex P2). If a future profile
    # for Workers lands, this set extends rather than re-classifies.
    pages_actions = {"cloudflare/pages-action"}
    found: set[str] = set()
    for entry in sorted(workflows_dir.iterdir()):
        if entry.is_symlink() or not entry.is_file():
            continue
        if entry.suffix.lower() not in {".yml", ".yaml"}:
            continue
        text = _read_text_capped(entry)
        if text is None:
            continue
        for action in pages_actions:
            if action in text:
                found.add("cloudflare-pages")
    return found


def detect_deploy_providers(repo_root: Path) -> list[str]:
    """Scan ``repo_root`` for deploy-target signals.

    Returns a sorted list of provider-profile names. Empty on no signals.
    """
    found: set[str] = set()
    for picker in (_detect_cloudflare, _detect_vercel, _detect_netlify):
        provider = picker(repo_root)
        if provider:
            found.add(provider)
    found.update(_detect_from_workflows(repo_root))
    # Guard against drift: detected providers MUST be in KNOWN_PROFILES.
    found &= KNOWN_PROFILES
    return sorted(found)


def proposed_profiles(detected: list[str]) -> list[str]:
    """Map ``detected`` providers to the full profile set the config covers.

    Always includes ``spec-completeness``. Auto-adds ``cloudflare-dns``
    when ``cloudflare-pages`` is detected (most Pages projects use a
    custom domain; user can remove the line if not). Auto-adds
    ``build-time-api-auth`` (BL-373) when ANY deploy target is detected
    so the probe is opt-in-by-default for new projects; the probe is
    a no-op for projects that do not call rate-limited APIs at build
    time (PASS-with-skip-message), so the default-on posture is safe.
    """
    profiles: set[str] = {"spec-completeness", *detected}
    if "cloudflare-pages" in detected:
        profiles.add("cloudflare-dns")
    if detected:
        profiles.add("build-time-api-auth")
    return sorted(profiles & KNOWN_PROFILES)


def _render_yaml(providers: list[str]) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    # PR #76 Codex P3: the prior comment claimed `.launchpad/ files are
    # gitignored by default`, but this config file is NOT in either
    # LaunchPad's root `.gitignore` or the plugin's shipped gitignore
    # template (the runtime artifacts `audit.log`, `preflight-checklist.md`,
    # `preflight-receipt.json`, and the opt-out markers ARE; the config
    # is meant to be either committed or gitignored at the team's
    # discretion). State that explicitly so a reader does not assume
    # the file is gitignored when it is not.
    lines = [
        f"# Generated by /lp-bootstrap on {timestamp}",
        "# Commit or gitignore at your team's discretion; see",
        "# `plugins/launchpad/scripts/plugin_default_generators/infrastructure/gitignore.j2`",
        "# for the LaunchPad-shipped `.launchpad/` ignore entries.",
        "",
        "providers:",
    ]
    for provider in providers:
        comment = ""
        if provider == "cloudflare-dns":
            comment = "  # remove if no custom domain"
        elif provider == "build-time-api-auth":
            comment = "  # BL-373: detect missing GITHUB_TOKEN / GITLAB_TOKEN"
        lines.append(f"  - {provider}{comment}")
    lines.append("")
    return "\n".join(lines)


def write_preflight_config(repo_root: Path, providers: list[str]) -> Path:
    """Atomically write ``.launchpad/preflight.config.yaml``.

    Validates every provider against ``KNOWN_PROFILES``. Refuses to
    overwrite an existing config (caller must remove it first).
    """
    if not providers:
        raise ValueError("providers list is empty")
    unknown = sorted(set(providers) - KNOWN_PROFILES)
    if unknown:
        raise ValueError(f"unknown provider(s): {unknown}")
    target = preflight_config_path(repo_root)
    if target.exists():
        raise FileExistsError(str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    body = _render_yaml(sorted(set(providers))).encode("utf-8")
    atomic_write_replace(target, body, trusted_root=repo_root)
    return target


def write_skipped_marker(repo_root: Path) -> Path:
    """Write the opt-out sentinel so future bootstrap runs do not re-prompt."""
    target = skipped_marker_path(repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (
        b"# User opted out of preflight config at /lp-bootstrap.\n"
        b"# Delete this file to be re-prompted on the next /lp-bootstrap run.\n"
    )
    atomic_write_replace(target, body, trusted_root=repo_root)
    return target


def summarize(repo_root: Path) -> dict[str, object]:
    """Structured-output entry point for the slash command."""
    detected = detect_deploy_providers(repo_root)
    return {
        "detected": detected,
        "proposed_profiles": proposed_profiles(detected),
        "config_present": config_present(repo_root),
        "skipped_marker_present": skipped_marker_present(repo_root),
    }


def _parse_providers(raw: str) -> list[str]:
    return [piece.strip() for piece in raw.split(",") if piece.strip()]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lp_bootstrap.preflight_proposer",
        description=(
            "Detect deploy-target signals and propose a preflight config. "
            "Invoked by /lp-bootstrap; see BL-370."
        ),
    )
    # BL-370 v2 (PR #76 review, pattern-finder P2): match the rest of the
    # LaunchPad CLI surface (`lp_preflight`, `lp_define_runner`,
    # `plugin-build-runner`, `plugin-config-loader`, `plugin-audit-log`,
    # `plugin-config-hash`) by using `--repo-root` with an `LP_REPO_ROOT`
    # env-var fallback. `--cwd` remains as a hidden compatibility alias
    # so out-of-tree callers do not break mid-cycle.
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(os.environ.get("LP_REPO_ROOT", os.getcwd())),
        help=("Project root (default: $LP_REPO_ROOT or current working directory)."),
    )
    p.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON summary of detection state.",
    )
    group.add_argument(
        "--write-config",
        action="store_true",
        help="Write .launchpad/preflight.config.yaml from --providers.",
    )
    group.add_argument(
        "--write-skipped",
        action="store_true",
        help="Write the skipped marker so future runs do not re-prompt.",
    )
    p.add_argument(
        "--providers",
        type=str,
        default="",
        help="Comma-separated provider list (required with --write-config).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # `--cwd` (compat alias) wins over `--repo-root` only when explicitly
    # passed by an out-of-tree caller; the new canonical flag is
    # `--repo-root` (matches the rest of the LaunchPad CLI surface).
    raw_root = args.cwd if args.cwd is not None else args.repo_root
    repo_root: Path = raw_root.resolve()

    if args.write_config:
        providers = _parse_providers(args.providers)
        if not providers:
            print("error: --write-config requires --providers", file=sys.stderr)
            return 64
        try:
            target = write_preflight_config(repo_root, providers)
        except FileExistsError as exc:
            print(
                f"error: refusing to overwrite existing config: {exc}", file=sys.stderr
            )
            return 65
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 64
        print(str(target))
        return 0

    if args.write_skipped:
        target = write_skipped_marker(repo_root)
        print(str(target))
        return 0

    if args.json:
        json.dump(summarize(repo_root), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    detected = detect_deploy_providers(repo_root)
    if not detected:
        print("No deploy-target signals detected.")
        return 0
    profiles = proposed_profiles(detected)
    print(f"Detected: {', '.join(detected)}")
    print(f"Proposed preflight profiles: {', '.join(profiles)}")
    if config_present(repo_root):
        print("Preflight config already present; no action needed.")
    elif skipped_marker_present(repo_root):
        print("Preflight config previously declined; no action needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
