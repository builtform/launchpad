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
    no-HEAD detection per `git` docs."""
    text = _md()
    assert "git rev-parse --verify HEAD" in text
    assert "git rev-parse --verify origin/main" in text


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
