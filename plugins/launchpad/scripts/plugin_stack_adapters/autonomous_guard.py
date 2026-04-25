"""Autonomous-build integrity checks.

The v1 trust model treats `.launchpad/autonomous-ack.md` as a *social / review
signal* — any contributor with commit access can add it. That's intentional
for v1 scope. But it leaves one narrow attack surface:

    A hostile PR that adds BOTH a new section spec (to SECTION_REGISTRY.md
    and docs/tasks/sections/) AND the autonomous-ack.md file in the same
    commit — if the reviewer doesn't notice the ack file, the section becomes
    autonomously buildable on first merge.

This module supplies the belt-and-suspenders check: `/lp-plan` refuses to
auto-approve a plan for a section that was added to the registry in the same
commit as (or later than) the current `autonomous-ack.md`. Human plan approval
is still the authoritative gate; this just makes the fast-path refuse.

Contract:
  - section_added_with_ack(repo_root, section_name) -> bool
    Returns True if the section was introduced to SECTION_REGISTRY.md in a
    commit that also touched .launchpad/autonomous-ack.md.
  - Missing files or repo in detached-head / shallow-clone state → returns
    False (don't block legitimate users with edge-case git state).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo_root: Path, *args: str) -> str | None:
    """Run git; return stdout on success, None on any failure (including not-a-repo)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        # git not installed — don't block. The check is best-effort.
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _find_section_introduction_commit(repo_root: Path, section_name: str) -> str | None:
    """Return the commit SHA that first added the section's `### <name>` heading
    to SECTION_REGISTRY.md. Returns None if not found.

    Uses git's pickaxe (`-S`) to find commits whose diff changed the count of
    lines containing the heading string. The previous implementation also
    passed `--diff-filter=A`, which filtered to commits where the whole
    SECTION_REGISTRY.md file was added — meaning in any normal repo where
    the registry already exists, modifications that added a new section to
    an existing file were silently dropped from the result. A hostile PR
    that committed a new section line and `.launchpad/autonomous-ack.md`
    in the same commit would then bypass the guard entirely. Removing the
    file-level diff-filter so MODIFY commits are also inspected closes the
    bypass; the pickaxe `-S` is the right primitive for "added this
    string", whether the file was new or already present.
    """
    registry_rel = "docs/tasks/SECTION_REGISTRY.md"

    pickaxe = f"### {section_name}"
    out = _git(
        repo_root,
        "log",
        "--follow",
        "-S", pickaxe,
        "--pretty=format:%H",
        "--",
        registry_rel,
    )
    if not out:
        return None
    # Most recent commit introducing the string — take the last line (chronologically first)
    shas = [line.strip() for line in out.splitlines() if line.strip()]
    return shas[-1] if shas else None


def _commit_touched_ack(repo_root: Path, commit_sha: str) -> bool:
    """Returns True if the commit modified .launchpad/autonomous-ack.md."""
    out = _git(repo_root, "show", "--name-only", "--pretty=format:", commit_sha)
    if out is None:
        return False
    files = {line.strip() for line in out.splitlines() if line.strip()}
    return ".launchpad/autonomous-ack.md" in files


def section_added_with_ack(repo_root: Path, section_name: str) -> bool:
    """Return True if the named section was added to SECTION_REGISTRY.md in the
    SAME commit that touched `.launchpad/autonomous-ack.md`.

    Best-effort — returns False on any git failure (detached HEAD, shallow
    clone, no git binary, section not in registry, etc.) so legitimate users
    aren't blocked by git-state edge cases.
    """
    intro_commit = _find_section_introduction_commit(repo_root, section_name)
    if intro_commit is None:
        return False
    return _commit_touched_ack(repo_root, intro_commit)
