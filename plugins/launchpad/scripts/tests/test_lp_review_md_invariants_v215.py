"""v2.1.5 round-3 review fix C11 (testing-reviewer): static-validation
guard for the BL-337 pre-first-commit fallback section of
`commands/lp-review.md`.

Slash-command markdown changes have no other compile-time check.
A future edit that accidentally drops the BL-337 invariant strings
(pre-first-commit banner, HAS_HEAD detection, --staged fallback,
A3 secret-scan-on-pre-first-commit) would silently regress.

This test grep-asserts the literal invariant strings so the gate
fires on first re-render. Scope is intentionally narrow: it does NOT
parse the markdown structure (the human writer's prose can move
around); it only pins specific load-bearing phrases.
"""

from __future__ import annotations

from pathlib import Path

_COMMANDS_DIR = Path(__file__).resolve().parents[2] / "commands"
_LP_REVIEW_MD = _COMMANDS_DIR / "lp-review.md"


def _md() -> str:
    return _LP_REVIEW_MD.read_text(encoding="utf-8")


def test_lp_review_md_exists() -> None:
    assert _LP_REVIEW_MD.is_file(), (
        f"lp-review.md not found at {_LP_REVIEW_MD}; the markdown invariant "
        "lints rely on the file being at the canonical path."
    )


def test_bl337_pre_first_commit_banner_present() -> None:
    """The `[pre-first-commit]` banner is the user-visible signal that
    the fallback mode fired. Dropping it = silent mode change."""
    text = _md()
    assert "[pre-first-commit]" in text, (
        "BL-337 invariant: lp-review.md must emit the `[pre-first-commit]` "
        "banner when fallback mode fires. The banner string is the public "
        "contract."
    )


def test_bl337_has_head_detection_command() -> None:
    """Detection MUST use `git rev-parse --verify HEAD` (NOT `git status`,
    NOT `git log -1`, NOT a heuristic). The command is the canonical
    no-HEAD detection per `git` docs.

    v2.1.5 round-4 fix (Codex P2-1): the redirection MUST be
    `>/dev/null 2>&1` (suppress both stdout SHA + stderr error msg),
    NOT just `2>/dev/null` (stderr-only, which lets the commit-SHA
    leak into the captured variable, breaking later `== yes` checks)."""
    text = _md()
    assert "git rev-parse --verify HEAD >/dev/null 2>&1" in text, (
        "Codex P2-1 regression: the HAS_HEAD assignment must redirect "
        "BOTH stdout AND stderr (`>/dev/null 2>&1`). Just `2>/dev/null` "
        "lets git's stdout (the commit SHA) leak into the captured "
        "variable, making `$HAS_HEAD == yes` false even when HEAD exists."
    )
    assert "git rev-parse --verify origin/main >/dev/null 2>&1" in text
    # Negative: the broken shape must NOT be present.
    assert "git rev-parse --verify HEAD 2>/dev/null && echo yes" not in text


def test_bl337_staged_fallback_mentioned() -> None:
    """`--staged` is the documented fallback flag for review of staged
    files only. Keep the string in case the command spec drifts away
    from offering it."""
    text = _md()
    assert "--staged" in text


def test_bl337_a3_secret_scan_in_pre_first_commit() -> None:
    """v2.1.5 round-3 review fix A3 mandate: pre-first-commit fallback
    MUST scan full file content. The doc must reference the scan AND
    its source patterns file."""
    text = _md()
    # Either the section explicitly invokes the patterns file OR the
    # narrative mentions running the scan against full content.
    assert ".launchpad/secret-patterns.txt" in text
    # Hardening directive against the prior "Skip Step 2 secret scan" shape.
    assert "Pre-first-commit secret scan" in text or "first-pass secret leak" in text


def test_bl337_section_ordering_before_step_2() -> None:
    """Section 1.A must appear BEFORE Section 2 (Pre-dispatch Secret
    Scan). Reordering would have the user hitting Step 2 before the
    pre-first-commit detection fires."""
    text = _md()
    idx_1a = text.find("Step 1.A: Pre-first-commit fallback")
    idx_step2 = text.find("## Step 2: Pre-dispatch Secret Scan")
    assert idx_1a > 0
    assert idx_step2 > 0
    assert idx_1a < idx_step2, (
        "BL-337 invariant: Section 1.A must precede Section 2. "
        "Reordering changes the execution sequence the doc claims."
    )


def test_codex_p1_b_step2_branches_on_pre_first_commit_mode() -> None:
    """v2.1.5 round-4 fix (Codex P1-B): Step 2 must branch on whether
    Step 1.A's pre-first-commit fallback fired. Without the branch,
    Step 2's `git diff origin/main...HEAD` re-runs the same command
    that triggered the fallback in the first place.

    Locks down the branch shape so a future edit that removes the
    pre-first-commit mode handling from Step 2 trips this test."""
    text = _md()
    # Must explicitly describe the branch.
    assert "Pre-first-commit mode" in text, (
        "Codex P1-B regression: Step 2 must describe the pre-first-commit "
        "branch where it scans full file content instead of running "
        "git diff origin/main...HEAD."
    )
    # Must reference Step 1.A's HAS_HEAD/HAS_REMOTE detection vars.
    assert "HAS_HEAD == no" in text
    assert "HAS_REMOTE == no" in text
    # Must explicitly state that the normal-mode diff command is the
    # one that fails on no-HEAD — this is the load-bearing rationale
    # for the branch.
    assert "git diff origin/main...HEAD" in text
    # The fix should explicitly mention "FULL FILE CONTENT" scanning
    # (the no-diff-base recovery shape).
    assert "FULL FILE CONTENT" in text or "full file content" in text


def test_codex_p1_b_secret_scan_in_pre_first_commit_branch() -> None:
    """The Codex P1-B fix must place the secret-scan in the
    pre-first-commit BRANCH (not skip it). A3 mandated this in round 3
    but the original implementation left a fallthrough that Codex
    round 4 caught."""
    text = _md()
    # Find the pre-first-commit branch description in Step 2.
    step2_idx = text.find("## Step 2: Pre-dispatch Secret Scan")
    step3_idx = text.find("## Step 3: Dispatch Review Agents")
    assert step2_idx > 0 and step3_idx > step2_idx
    step2_body = text[step2_idx:step3_idx]
    # The secret-patterns file must be referenced inside Step 2 body
    # (for both branches; the pre-first-commit branch must also use it).
    assert ".launchpad/secret-patterns.txt" in step2_body
    # The pre-first-commit branch must reference HALT-on-match.
    assert "HALT" in step2_body or "halt" in step2_body
