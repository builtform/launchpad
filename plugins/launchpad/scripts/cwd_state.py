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
    "refuse_if_not_greenfield",
]


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
