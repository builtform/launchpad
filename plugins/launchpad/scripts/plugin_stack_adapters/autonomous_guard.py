"""Autonomous-build integrity checks.

The v1 trust model treats `.launchpad/autonomous-ack.md` as a *social / review
signal* — any contributor with commit access can add it. That's intentional
for v1 scope. But it leaves one narrow attack surface:

    A hostile PR that adds BOTH a new section spec (to SECTION_REGISTRY.md
    and docs/tasks/sections/) AND the autonomous-ack.md file — if the
    reviewer doesn't notice the ack file, the section becomes autonomously
    buildable on first merge. The hostile PR can split this across multiple
    commits to lower visual prominence: commit A adds the ack quietly,
    commit B adds the section.

This module supplies the belt-and-suspenders check: `/lp-plan` refuses to
auto-approve a plan for a section when EITHER

  (a) the section's introduction commit also touched autonomous-ack.md
      (same-commit attack), OR
  (b) autonomous-ack.md was first added in the current branch — i.e., the
      ack does not predate the branch's merge-base with the default branch
      (cross-commit attack).

Human plan approval is still the authoritative gate; this just makes the
fast-path refuse.

Contract:
  - section_added_with_ack(repo_root, section_name) -> bool
    Returns True if either condition above holds.
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


def _git_rc(repo_root: Path, *args: str) -> int | None:
    """Run git; return exit code (used when 1 is meaningful, e.g. is-ancestor)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result.returncode


def _find_section_introduction_commit(repo_root: Path, section_name: str) -> str | None:
    """Return the commit SHA that first added the section's `### <name>` heading
    to SECTION_REGISTRY.md. Returns None if not found.

    Uses git's pickaxe (`-S`) without `--diff-filter=A` so MODIFY commits to
    an already-existing registry are inspected — closing the bypass where a
    new section line was added to a pre-existing file.
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
    shas = [line.strip() for line in out.splitlines() if line.strip()]
    return shas[-1] if shas else None


def _commit_touched_ack(repo_root: Path, commit_sha: str) -> bool:
    """Returns True if the commit modified .launchpad/autonomous-ack.md."""
    out = _git(repo_root, "show", "--name-only", "--pretty=format:", commit_sha)
    if out is None:
        return False
    files = {line.strip() for line in out.splitlines() if line.strip()}
    return ".launchpad/autonomous-ack.md" in files


def _detect_default_branch(repo_root: Path) -> str | None:
    """Return a ref pointing at the repo's default branch, or None.

    Tries (in order): origin/HEAD symref, origin/main, origin/master, main,
    master. Returns the first that exists. Returns None if none resolve —
    in which case the cross-commit check skips (best-effort, do not block).
    """
    out = _git(repo_root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if out:
        ref = out.strip()
        if ref:
            return ref
    for candidate in ("origin/main", "origin/master", "main", "master"):
        rc = _git_rc(repo_root, "rev-parse", "--verify", "--quiet", candidate)
        if rc == 0:
            return candidate
    return None


def _ack_creation_commit(repo_root: Path) -> str | None:
    """Return the SHA of the commit that first added .launchpad/autonomous-ack.md.

    Uses --diff-filter=A here (correctly): we want the file-creation commit,
    not modifications. Returns None if the file was never added in repo
    history.
    """
    out = _git(
        repo_root,
        "log",
        "--diff-filter=A",
        "--pretty=format:%H",
        "--",
        ".launchpad/autonomous-ack.md",
    )
    if not out:
        return None
    shas = [line.strip() for line in out.splitlines() if line.strip()]
    return shas[-1] if shas else None  # earliest = chronologically first


def _ack_added_in_current_branch(repo_root: Path) -> bool:
    """Return True if autonomous-ack.md was first created in the current
    branch (i.e., AFTER its merge-base with the repo's default branch).

    Logic:
      - If the ack creation commit is reachable from the default branch,
        the ack predates the current branch — legitimate prior opt-in. OK.
      - If the ack creation commit is NOT reachable from the default branch,
        it was introduced in this branch's commits — refuse.
      - If we cannot determine the default branch (no remote, no main/master),
        return False (best-effort; same-commit check still applies).
    """
    base = _detect_default_branch(repo_root)
    if base is None:
        return False

    ack_intro = _ack_creation_commit(repo_root)
    if ack_intro is None:
        return False  # ack was never added — nothing to block on this axis

    # `merge-base --is-ancestor X Y` returns 0 if X is reachable from Y, 1 otherwise.
    rc = _git_rc(repo_root, "merge-base", "--is-ancestor", ack_intro, base)
    if rc is None:
        return False  # git error — best-effort, don't block
    if rc == 0:
        return False  # ack predates branch — legitimate prior opt-in
    return True  # ack introduced in current branch — refuse


def section_added_with_ack(repo_root: Path, section_name: str) -> bool:
    """Return True if the named section's plan should be refused for
    autonomous-build fast-path approval.

    Two conditions trigger refusal:
      1. The section's introduction commit also touched
         `.launchpad/autonomous-ack.md` (same-commit attack).
      2. `.launchpad/autonomous-ack.md` was first created in the current
         branch — i.e., it does not predate the branch's merge-base with
         the default branch (cross-commit attack: ack quietly added in one
         commit, section added in a later commit on the same branch).

    Best-effort — returns False on any git failure (detached HEAD, shallow
    clone, no git binary, no default branch, section not in registry, etc.)
    so legitimate users aren't blocked by git-state edge cases.
    """
    intro_commit = _find_section_introduction_commit(repo_root, section_name)
    if intro_commit is None:
        return False

    # Check 1: same-commit attack
    if _commit_touched_ack(repo_root, intro_commit):
        return True

    # Check 2: cross-commit attack — ack added elsewhere in this branch
    if _ack_added_in_current_branch(repo_root):
        return True

    return False
