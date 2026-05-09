"""Greenfield/brownfield/ambiguous classifier for the v2.0 pipeline.

Single source of truth (HANDSHAKE §8). Used by /lp-brainstorm (routing) and
/lp-scaffold-stack (idempotency). The shared `BROWNFIELD_MANIFESTS` constant
is also imported by `plugin-stack-detector.py` so the heuristic does not
drift between v1 and v2 surfaces.

The 500-entry iteration cap (HANDSHAKE §8 + Layer 5 performance P3-L5-1)
bounds the slow-path syscall burst when the user accidentally invokes from
/, ~, or a giant monorepo root: those return "ambiguous" without per-entry
stat() calls.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

GREENFIELD_OK_FILES = {".gitignore", "README.md", "LICENSE"}
GREENFIELD_OK_DIRS = {".git", ".launchpad"}

# Single source of truth — also imported by plugin-stack-detector.py.
# Compared case-INsensitively below: macOS (APFS default) and Windows (NTFS
# default) are case-insensitive filesystems where `Package.json` and
# `package.json` resolve to the same file. Linux comparison is also lower-cased
# for cross-platform parity.
BROWNFIELD_MANIFESTS = {
    # Node / TS
    "package.json", "tsconfig.json", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb",
    # Python
    "pyproject.toml", "requirements.txt", "Pipfile", "Pipfile.lock",
    "poetry.lock", ".python-version",
    # Ruby
    "Gemfile", "Gemfile.lock",
    # Elixir
    "mix.exs", "mix.lock",
    # Go
    "go.mod", "go.sum",
    # Dart / Flutter
    "pubspec.yaml", "pubspec.lock",
    # Rust
    "Cargo.toml", "Cargo.lock",
    # PHP
    "composer.json", "composer.lock",
    # Nix
    "flake.nix", "shell.nix", "default.nix",
    # asdf / version managers
    ".tool-versions",
}

_BROWNFIELD_MANIFESTS_LOWER = frozenset(m.lower() for m in BROWNFIELD_MANIFESTS)

_CWD_STATE_MAX_ENTRIES = 500


def cwd_state(cwd: Path) -> Literal["empty", "brownfield", "ambiguous"]:
    if not cwd.exists():
        raise NotADirectoryError(f"cwd_state: path does not exist: {cwd!r}")
    if not cwd.is_dir():
        raise NotADirectoryError(f"cwd_state: path is not a directory: {cwd!r}")
    entries = []
    for i, e in enumerate(cwd.iterdir()):
        if i >= _CWD_STATE_MAX_ENTRIES:
            return "ambiguous"  # too many entries — fail safe without stat()
        entries.append(e)
    names = {e.name for e in entries}
    names_lower = {n.lower() for n in names}
    if names_lower & _BROWNFIELD_MANIFESTS_LOWER:
        return "brownfield"
    extras = names - GREENFIELD_OK_FILES - GREENFIELD_OK_DIRS
    if not extras:
        return "empty"
    if len(extras) == 1 and "README.md" in names:
        # README + 1 extra (e.g., .editorconfig, a stub LICENSE.txt). Per PR
        # #41 cycle 7 #3 closure: the extra file ALSO has to be small —
        # previously only README was sized, so a 50-byte README next to a
        # 100KB stray file would still classify "empty" and let the user
        # accidentally scaffold over it.
        readme = cwd / "README.md"
        extra_name = next(iter(extras))
        extra_path = cwd / extra_name
        readme_ok = readme.stat().st_size < 500
        extra_ok = (
            extra_path.is_file() and extra_path.stat().st_size <= 100
        )
        if readme_ok and extra_ok:
            return "empty"
    # Generic safeguard: any unrecognized file > 100 bytes triggers ambiguous
    # so unknown ecosystems fail safe rather than greenfield-by-omission.
    for name in extras:
        path = cwd / name
        if path.is_file() and path.stat().st_size > 100:
            return "ambiguous"
    return "ambiguous"


def refuse_if_not_greenfield(cwd: Path, command_name: str) -> None:
    """Shared refusal helper. Raises NotADirectoryError or RuntimeError with a
    structured `reason:` field that callers wire into the §4 rejection JSONL.

    Callers: /lp-pick-stack (Step 0.5 pre-question gate), /lp-scaffold-stack
    (idempotency gate). Eliminates two near-identical `if state == "brownfield":`
    branches across commands.
    """
    state = cwd_state(cwd)
    if state == "brownfield":
        raise RuntimeError(
            f"{command_name}: cwd is brownfield; not applicable. "
            f"Use /lp-define instead. reason: cwd_state_brownfield"
        )
    if state == "ambiguous":
        raise RuntimeError(
            f"{command_name}: cwd is ambiguous; refuse to proceed without user "
            f"confirmation. reason: cwd_state_ambiguous"
        )


__all__ = [
    "BROWNFIELD_MANIFESTS",
    "GREENFIELD_OK_FILES",
    "GREENFIELD_OK_DIRS",
    "cwd_state",
    "infrastructure_present",
    "refuse_if_not_greenfield",
]


# --- v2.1 Phase 3 §3.9: 5-state infrastructure classifier ----------------
#
# Folded forward from Phase 6 (V3 §13.4) since Phase 3 owns the
# `infrastructure/` directory contents. Returns a 5-state enum so
# brownfield `/lp-define` can dispatch on richer state than tuple-of-bool.
#
# Path inventory is a module-const computed once at import; the function
# itself is uncached because 30 stat calls (~150us) is faster than any
# cache-invalidation logic per harden B5.

def infrastructure_present(cwd: Path):
    """Classify the `cwd` infrastructure overlay state per Phase 3 §3.9.

    Returns `(state, missing_or_stale_paths)` where `state` is a
    `BootstrapState` enum and `missing_or_stale_paths` is the list of
    target relpaths that drove the non-FULL classification (empty when
    state is FULL or ABSENT-but-no-paths-on-disk).

    Lazy import of `lp_bootstrap` so cwd_state.py stays free of v2.1
    package coupling for v2.0 readers (cwd_state was added in v2.0; the
    v2.1 helper is additive).
    """
    import importlib.util  # noqa: PLC0415

    from lp_bootstrap import (  # noqa: PLC0415
        INFRASTRUCTURE_TARGETS,
        BootstrapState,
    )

    targets: list[str] = sorted(INFRASTRUCTURE_TARGETS)
    present: list[str] = []
    missing: list[str] = []
    for t in targets:
        if (cwd / t).is_file():
            present.append(t)
        else:
            missing.append(t)

    if not present:
        return BootstrapState.ABSENT, missing

    # Read the manifest via the canonical reader; if absent, the paths
    # exist on disk but aren't tracked.
    loader_path = Path(__file__).resolve().parent / "plugin-config-loader.py"
    spec = importlib.util.spec_from_file_location("plugin_config_loader_for_cwdstate", loader_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    manifest = mod.read_bootstrap_manifest(cwd)

    if not manifest.present:
        if missing:
            # Paths partially present, no manifest -> partial-missing
            # (refresh-all on degraded path -> full bootstrap).
            return BootstrapState.PARTIAL_MISSING, missing
        return BootstrapState.PRESENT_UNMANAGED, []

    # Compare on-disk shas to manifest's rendered_content_sha256.
    from plugin_default_generators._renderer_base import sha256_file  # noqa: PLC0415
    by_path: dict[str, str] = {
        e["path"]: e.get("rendered_content_sha256", "")
        for e in manifest.payload.get("files", [])
        if isinstance(e, dict) and "path" in e
    }
    stale: list[str] = []
    for t in targets:
        path = cwd / t
        if not path.is_file():
            continue
        recorded = by_path.get(t)
        if recorded is None:
            continue
        on_disk = sha256_file(path)
        if on_disk != recorded:
            stale.append(t)

    if missing:
        return BootstrapState.PARTIAL_MISSING, missing + stale
    if stale:
        return BootstrapState.PARTIAL_STALE, stale
    return BootstrapState.FULL, []


def _main(argv: list[str] | None = None) -> int:
    """CLI shim: print classification of <cwd> (default: cwd) to stdout.

    Per PR #41 cycle 7 #6 closure: lp-brainstorm.md documents
    `python3 plugins/launchpad/scripts/cwd_state.py` as a way to compute
    cwd_state from a shell. Without this shim the script was importable
    only — running it directly was a no-op. The CLI prints exactly one
    line: `empty`, `brownfield`, or `ambiguous`. Exits 0 on success;
    non-zero on bad input path.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Classify a working directory as empty/brownfield/ambiguous.",
    )
    parser.add_argument(
        "cwd",
        nargs="?",
        default=".",
        help="Path to classify (default: current directory).",
    )
    args = parser.parse_args(argv)
    try:
        state = cwd_state(Path(args.cwd))
    except NotADirectoryError as exc:
        print(f"cwd_state: {exc}", file=sys.stderr)
        return 2
    print(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
