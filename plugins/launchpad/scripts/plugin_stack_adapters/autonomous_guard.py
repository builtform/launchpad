"""Autonomous-build integrity checks (BL-356 generalised at v2.1.6).

The v1 trust model treats `.launchpad/autonomous-ack.md` as a *social / review
signal* — any contributor with commit access can add it. That's intentional
for v1 scope. But it leaves one narrow attack surface:

    A hostile PR that adds BOTH a new section spec (to SECTION_REGISTRY.md
    and docs/tasks/sections/) AND the autonomous-ack.md file — if the
    reviewer doesn't notice the ack file, the section becomes autonomously
    buildable on first merge. The hostile PR can split this across multiple
    commits to lower visual prominence: commit A adds the ack quietly,
    commit B adds the section.

This module supplies the belt-and-suspenders check: `/lp-plan` and `/lp-build`
refuse to auto-approve a plan for a section when EITHER

  (a) the section's introduction commit also touched autonomous-ack.md
      (same-commit attack), OR
  (b) autonomous-ack.md was first added in the current branch — i.e., the
      ack does not predate the branch's merge-base with the default branch
      (cross-commit attack).

Human plan approval is still the authoritative gate; this just makes the
fast-path refuse.

**BL-356 — gate generalised across autonomous-write commands.** Prior to
v2.1.6 the ack-file-must-exist gate lived only in `/lp-build` Step 0.1 as
inline markdown logic, even though `/lp-build` is a meta-orchestrator that
chains `/lp-inf`, `/lp-resolve-todo-parallel`, and `/lp-ship`. Each of
those wrapped commands performs autonomous code mutation; calling any of
them directly bypassed the ack gate. v2.1.6 lifts the gate into a shared
helper (`assert_autonomous_ack`) and wires every direct-invocation command
to call it. The refuse-message also gains a copy-pasteable starter template
so first-time users hitting the refuse don't have to read HOW_IT_WORKS.md
to understand what the file is for.

Contract:
  - section_added_with_ack(repo_root, section_name) -> bool
    Returns True if either same-commit or cross-commit attack pattern holds.
  - assert_ack_not_same_commit_as(repo_root, section_name) -> None
    Raises `AutonomousAckSameCommitError` if `section_added_with_ack` is True.
    Exception message is the canonical refuse-text used by `/lp-build` 0.3
    and `/lp-plan` 0.3.
  - assert_autonomous_ack(repo_root) -> None
    Raises `AutonomousAckMissingError` if `.launchpad/autonomous-ack.md`
    does not exist. Exception message is the canonical refuse-text — short
    description of what the file is + the copy-pasteable starter template
    (`AUTONOMOUS_ACK_TEMPLATE`).
  - Missing files or repo in detached-head / shallow-clone state → returns
    False (don't block legitimate users with edge-case git state).

Single-source-of-truth invariant (BL-356 test 5): the gate logic for both
checks lives in exactly one module — this one. Command markdown files MUST
reference these helpers by name (`assert_autonomous_ack`,
`assert_ack_not_same_commit_as`) rather than re-implementing the refuse
logic inline. The test harness greps for inline `.launchpad/autonomous-ack.md`
absence-checks in command markdown and fails if it finds any that are not
references to this module.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# UX constants — single source of truth for refuse-message text.
# ---------------------------------------------------------------------------
#
# Every site that surfaces the ack requirement (refuse-messages on the four
# wrapped commands AND the `/lp-plan` final transition message) MUST
# reference these constants rather than copy-pasting the text inline. The
# BL-356 test 6 (UX surface test) greps for the canonical sentinel
# `# Autonomous Execution Acknowledgment` in command markdown to verify
# every surface reflects the shared template.

AUTONOMOUS_ACK_SENTINEL = "# Autonomous Execution Acknowledgment"
"""Canonical first-line sentinel for the starter template.

Used by BL-356 test 6 to verify every surface site references the same
template. The string MUST appear verbatim in `AUTONOMOUS_ACK_TEMPLATE`
and in the refuse-message text of every wrapped command markdown file.
"""

AUTONOMOUS_ACK_DESCRIPTION = (
    "`.launchpad/autonomous-ack.md` is a visible, git-tracked acknowledgment "
    "that the team has consciously authorized autonomous code execution in "
    "this repository. It is a social / review signal, not a cryptographic "
    "gate — but its presence in git history makes the authorization visible "
    "in PR diffs and `git blame`."
)
"""Short description of what `autonomous-ack.md` is.

Surfaces in the refuse-message of every wrapped command + the `/lp-plan`
final transition message. Lets a first-time user hitting the refuse
understand the file's purpose without reading HOW_IT_WORKS.md.
"""

AUTONOMOUS_ACK_TEMPLATE = """\
# Autonomous Execution Acknowledgment

I, <Your Name>, acknowledge that running `/lp-build`, `/lp-inf`,
`/lp-resolve-todo-parallel`, or `/lp-ship` in this repository will cause
LaunchPad to:

- Write and modify source files autonomously based on planned section specs
- Run tests, linters, type checkers, and build commands
- Open pull requests, push commits, and merge branches (depending on
  `.launchpad/config.yml`)

I accept these risks and authorize autonomous code execution in this
repository.

**Authorized by:** <Your Name> <your-email@example.com>
**Authorized on:** <YYYY-MM-DD>
**Scope:** <optional — e.g., "all sections" or "only sections under docs/marketing/">
"""
"""Copy-pasteable starter template for `.launchpad/autonomous-ack.md`.

The refuse-message reproduces this verbatim so the user can copy-edit-commit
without leaving the terminal. The template names every autonomous-write
command the gate covers (`/lp-build`, `/lp-inf`,
`/lp-resolve-todo-parallel`, `/lp-ship`) so the author can confirm scope.
"""


def _refuse_message_missing_ack() -> str:
    """Canonical refuse-text for `assert_autonomous_ack` failure.

    Composed from `AUTONOMOUS_ACK_DESCRIPTION` + `AUTONOMOUS_ACK_TEMPLATE`
    so every refuse surface stays byte-identical even if the template
    changes. The body is also reflected verbatim in `/lp-plan`'s final
    transition message (Step 5 success branch) so the same content reaches
    the user at the moment they're told they need the file, not only at
    refuse-time.
    """
    return (
        "Autonomous execution requires `.launchpad/autonomous-ack.md` to exist.\n"
        "\n"
        f"{AUTONOMOUS_ACK_DESCRIPTION}\n"
        "\n"
        "Create the file at `.launchpad/autonomous-ack.md` using the "
        "starter template below, edit it with your name / email / date, "
        "commit it, then re-run the command.\n"
        "\n"
        "Starter template (copy-paste, then edit):\n"
        "\n"
        "```markdown\n"
        f"{AUTONOMOUS_ACK_TEMPLATE}"
        "```\n"
    )


def _refuse_message_untracked_ack() -> str:
    """Canonical refuse-text when `.launchpad/autonomous-ack.md` exists on
    disk but is not tracked by git (v2.1.6 round-3 review fix, Codex P1
    #1).

    The threat model treats the ack as a `team-visible authorization
    signal` (HOW_IT_WORKS.md:363 — `having the file tracked in git blame
    makes autonomous-execution authorization visible`). An untracked
    local file satisfies file-existence but bypasses the team-visibility
    intent: a hostile contributor could drop an ack file into their
    local working tree and run autonomous commands without leaving any
    committed evidence. Requiring the file to be tracked (and ideally
    present in HEAD) closes that gap.
    """
    return (
        "Autonomous execution requires `.launchpad/autonomous-ack.md` to be "
        "**tracked by git** (not just present in the working tree).\n"
        "\n"
        f"{AUTONOMOUS_ACK_DESCRIPTION}\n"
        "\n"
        "The file currently exists at `.launchpad/autonomous-ack.md` but "
        "git is not tracking it — that defeats the team-visibility intent "
        "of the gate (the ack must appear in git blame / PR diffs for the "
        "authorization to count). Stage and commit the file, then re-run "
        "the command:\n"
        "\n"
        "```\n"
        "git add .launchpad/autonomous-ack.md\n"
        "git commit -m 'chore: acknowledge autonomous execution'\n"
        "```\n"
    )


_REFUSE_SAME_COMMIT = (
    "This section was added to the registry in the same commit that "
    "introduced `.launchpad/autonomous-ack.md`. That's the exact pattern "
    "a hostile PR would use to bypass review. Refusing autonomous build. "
    "Verify the section spec is legitimate and have the ack file predate "
    "the section, then retry."
)
"""Canonical refuse-text for `assert_ack_not_same_commit_as` failure.

Identical to the prior inline markdown text in `/lp-build` 0.3 — verbatim
reuse so v2.1.6 is a no-op refactor on the user-visible refuse surface for
this branch (only the missing-ack refuse gets the new UX content).
"""


# ---------------------------------------------------------------------------
# Custom exceptions.
# ---------------------------------------------------------------------------


class AutonomousAckError(Exception):
    """Base class for autonomous-ack gate refusals.

    Catching this base type lets command runners surface ANY ack-gate
    failure with a generic "autonomous execution refused" wrapper while
    still rendering the specific refuse-message via `str(exc)`.
    """


class AutonomousAckMissingError(AutonomousAckError):
    """Raised by `assert_autonomous_ack` when the ack file is absent.

    `str(exc)` returns `_refuse_message_missing_ack()` — the canonical
    refuse-message containing the description and the copy-pasteable
    template.
    """


class AutonomousAckUntrackedError(AutonomousAckError):
    """Raised by `assert_autonomous_ack` when the ack file exists on
    disk but is not tracked by git (v2.1.6 round-3 review fix, Codex P1
    #1).

    `str(exc)` returns `_refuse_message_untracked_ack()` — the canonical
    refuse-message instructing the user to `git add` + `git commit`.
    Subclass of `AutonomousAckError` so generic `except
    AutonomousAckError:` handlers still catch it.
    """


class AutonomousAckSameCommitError(AutonomousAckError):
    """Raised by `assert_ack_not_same_commit_as` when the same-commit or
    cross-commit pattern fires.

    `str(exc)` returns `_REFUSE_SAME_COMMIT` — preserves the v2.1.5 refuse
    text byte-for-byte.
    """


# ---------------------------------------------------------------------------
# Git plumbing helpers (carried forward from v2.1.5).
# ---------------------------------------------------------------------------


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
        "-S",
        pickaxe,
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


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


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


def _ack_tracked(repo_root: Path) -> bool:
    """Return True if `.launchpad/autonomous-ack.md` is tracked by git.

    Detection order (v2.1.6 round-3 fix, Codex P1 #1):
      1. If HEAD exists, require the file to be present in HEAD
         (`git ls-tree HEAD -- .launchpad/autonomous-ack.md`). This is
         the strict interpretation matching HOW_IT_WORKS.md's `commit,
         then re-run` guidance — the file must appear in a commit, not
         merely be staged.
      2. If HEAD does NOT exist (pre-first-commit repos: greenfield
         scaffolds where no commit has landed yet), fall back to
         tracked-by-git (`git ls-files --error-unmatch ...`). This
         covers the legitimate flow where /lp-bootstrap stages the
         ack file and a fresh user is about to make their first commit
         that includes both the scaffold AND the ack — blocking that
         flow would require committing twice.
      3. If git is unavailable (not installed) or `repo_root` is not a
         git repository at all, return False — fail-closed. The gate
         is for autonomous-write LaunchPad commands operating on git
         repos; running outside a git repo is undefined and should be
         refused.
    """
    head_rc = _git_rc(repo_root, "rev-parse", "--verify", "--quiet", "HEAD")
    if head_rc is None:
        # git not installed OR not a git repo — fail-closed.
        return False
    if head_rc == 0:
        # HEAD exists; require the ack to be in HEAD.
        rc = _git_rc(
            repo_root,
            "cat-file",
            "-e",
            "HEAD:.launchpad/autonomous-ack.md",
        )
        return rc == 0
    # HEAD does not exist (pre-first-commit). Allow staged-only ack.
    rc = _git_rc(
        repo_root,
        "ls-files",
        "--error-unmatch",
        ".launchpad/autonomous-ack.md",
    )
    return rc == 0


def assert_autonomous_ack(repo_root: Path) -> None:
    """Raise `AutonomousAckMissingError` if `.launchpad/autonomous-ack.md`
    does not exist under `repo_root`, or `AutonomousAckUntrackedError`
    if it exists but is not tracked by git (v2.1.6 round-3 review fix,
    Codex P1 #1).

    Tracked-file enforcement closes the threat-model gap where an
    untracked local file satisfied the gate: HOW_IT_WORKS.md:363
    describes the ack as a `tracked file` whose visibility in git blame
    is the authorization signal, so an untracked file bypasses the
    team-visibility intent. Detection logic lives in `_ack_tracked`;
    see its docstring for the HEAD-vs-pre-first-commit fallback.

    Exception `str(exc)` is the canonical refuse-message — includes the
    short description of the file's purpose plus the copy-pasteable starter
    template (`AUTONOMOUS_ACK_TEMPLATE`). Wire every autonomous-write
    command's gate to call this and surface `str(exc)` verbatim on failure.
    """
    ack_path = repo_root / ".launchpad" / "autonomous-ack.md"
    if not ack_path.is_file():
        raise AutonomousAckMissingError(_refuse_message_missing_ack())
    if not _ack_tracked(repo_root):
        raise AutonomousAckUntrackedError(_refuse_message_untracked_ack())


def assert_ack_not_same_commit_as(repo_root: Path, section_name: str) -> None:
    """Raise `AutonomousAckSameCommitError` if the named section's plan
    should be refused for autonomous-build fast-path approval.

    Wraps `section_added_with_ack` with raising behavior so callers (the
    `/lp-build` 0.3 and `/lp-plan` 0.3 gates) can share an identical
    refuse-message via `str(exc)` without re-implementing the logic.
    """
    if section_added_with_ack(repo_root, section_name):
        raise AutonomousAckSameCommitError(_REFUSE_SAME_COMMIT)
