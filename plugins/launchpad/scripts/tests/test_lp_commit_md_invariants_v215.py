"""v2.1.5 round-3 review fix C11 (testing-reviewer): static-validation
guard for the BL-338 initial-scaffold mode section of
`commands/lp-commit.md`.

Slash-command markdown changes have no other compile-time check.
A future edit that accidentally drops the BL-338 invariant strings
(`HAS_HEAD == no` precondition, `Initial-Scaffold: true` trailer,
emergency-hotfix exclusion line, post-review reject-when-HEAD-exists
hardening) would silently regress.

This test grep-asserts the literal invariant strings so the gate
fires on first re-render.
"""

from __future__ import annotations

from pathlib import Path

_COMMANDS_DIR = Path(__file__).resolve().parents[2] / "commands"
_LP_COMMIT_MD = _COMMANDS_DIR / "lp-commit.md"


def _md() -> str:
    return _LP_COMMIT_MD.read_text(encoding="utf-8")


def test_lp_commit_md_exists() -> None:
    assert _LP_COMMIT_MD.is_file(), (
        f"lp-commit.md not found at {_LP_COMMIT_MD}; the markdown invariant "
        "lints rely on the file being at the canonical path."
    )


def test_bl338_has_head_no_precondition() -> None:
    """The initial-scaffold mode MUST be gated on `HAS_HEAD == no`
    (NOT a flag-only bypass; the auto-detect IS the safety against
    accidental scope expansion of `--initial-scaffold`).

    v2.1.5 round-4 fix (Codex P2-1): the HAS_HEAD assignment must use
    `>/dev/null 2>&1` (redirect both streams) so the captured value is
    `yes` or `no` only, NOT `<sha>\\nyes`. The broken `2>/dev/null` shape
    would silently make the `== no` gate at Step 1.A always-false."""
    text = _md()
    assert "HAS_HEAD" in text, (
        "BL-338 invariant: lp-commit.md must reference the `HAS_HEAD` "
        "precondition variable. The auto-detection is the safety against "
        "`--initial-scaffold` being misused as a review-bypass."
    )
    # Codex P2-1: correct shell shape (full redirection).
    assert "git rev-parse --verify HEAD >/dev/null 2>&1" in text, (
        "Codex P2-1 regression: HAS_HEAD assignment must redirect both "
        "stdout (commit SHA) AND stderr (error msg) so the captured "
        "value is exactly `yes` or `no`."
    )
    # Negative: broken shape must NOT be present.
    assert "git rev-parse --verify HEAD 2>/dev/null && echo yes" not in text


def test_bl338_initial_scaffold_trailer_literal() -> None:
    """The trailer literal `Initial-Scaffold: true` MUST appear in the
    spec. It is the public signal in the commit message that the commit
    skipped Step 2.5 mandatory review."""
    text = _md()
    assert "Initial-Scaffold: true" in text


def test_bl338_emergency_hotfix_exclusion() -> None:
    """The initial-scaffold mode MUST be documented as distinct from
    the `Mandatory-Review-Skipped: emergency-hotfix` flow. They are NOT
    aliases; the round-3 review explicitly hardened the boundary."""
    text = _md()
    # Either the doc explicitly contrasts the two flows OR pins the
    # emergency-hotfix trailer string with a note that initial-scaffold
    # uses its own trailer.
    assert "emergency-hotfix" in text


def test_bl338_reject_when_head_exists() -> None:
    """v2.1.5 round-3 review fix BL-338 hardening: --initial-scaffold
    MUST be rejected when HEAD already exists (otherwise it becomes
    an easier review-bypass path than --skip-review).

    The doc must reference the rejection — either by name (`reject`,
    `refuse`, `error`) OR by the canonical `HAS_HEAD == yes` shape
    that the engine asserts."""
    text = _md()
    has_reject_language = any(
        kw in text.lower() for kw in ("reject", "refuse", "error", "must not")
    )
    has_head_yes_check = "HAS_HEAD == yes" in text or "HAS_HEAD=yes" in text
    assert has_reject_language or has_head_yes_check, (
        "BL-338 hardening invariant: lp-commit.md must document that "
        "`--initial-scaffold` is rejected when HEAD already exists. "
        "Without this, the flag is a review-bypass path."
    )
