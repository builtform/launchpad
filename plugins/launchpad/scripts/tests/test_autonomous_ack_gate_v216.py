"""BL-356 v2.1.6 — autonomous-ack gate generalised across wrapped commands.

The v2.1.5 gate enforced `.launchpad/autonomous-ack.md` existence only on
`/lp-build` Step 0.1 as inline markdown logic. Calling any of the three
wrapped autonomous-write commands directly (`/lp-inf`,
`/lp-resolve-todo-parallel`, `/lp-ship`) bypassed the gate entirely.
v2.1.6 lifts the gate into a shared helper (`assert_autonomous_ack`) and
wires every direct-invocation command to call it.

Test coverage (numbering matches BL-356 spec test plan):

  (1) Per-command refuse: with `.launchpad/autonomous-ack.md` absent,
      assert each wrapped command's markdown references the shared helper
      and surfaces the canonical refuse-text.
  (2) Per-command pass-through: with the ack file present, the
      `assert_autonomous_ack` helper does not raise.
  (3) Same-commit / cross-commit guard: `assert_ack_not_same_commit_as`
      raises `AutonomousAckSameCommitError` when `section_added_with_ack`
      would return True (covered transitively by the v2.1.5 regression
      tests in `test_autonomous_guard.py` — this file adds the
      raising-API surface).
  (4) Negative scope test: `/lp-review` and `/lp-test-browser` markdown
      MUST NOT reference the ack-gate helper (scope-NOT-included per
      BL-356; deferred to v2.1.7+ if a use case surfaces).
  (5) Source-of-truth: command markdown for every gate site references
      `assert_autonomous_ack` / `assert_ack_not_same_commit_as` by name
      (not an inline `.launchpad/autonomous-ack.md` absence check), proving
      the gate logic is centralised.
  (6) UX surface: every refuse-message AND the `/lp-plan` final transition
      message embed (a) the canonical sentinel `# Autonomous Execution
      Acknowledgment`, AND (b) reference `AUTONOMOUS_ACK_TEMPLATE`. All
      surface sites trace back to the same constant.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Import autonomous_guard by file path (the module lives under
# plugin_stack_adapters/ but importing as `from plugin_stack_adapters import
# autonomous_guard` requires the parent on sys.path; conftest sets that up
# but we keep this file independent of conftest for cross-suite portability).
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
_GUARD_PATH = _SCRIPT_DIR / "plugin_stack_adapters" / "autonomous_guard.py"
_spec = importlib.util.spec_from_file_location("autonomous_guard_v216", _GUARD_PATH)
assert _spec is not None and _spec.loader is not None
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)

assert_autonomous_ack = _guard.assert_autonomous_ack
assert_ack_not_same_commit_as = _guard.assert_ack_not_same_commit_as
AutonomousAckMissingError = _guard.AutonomousAckMissingError
AutonomousAckSameCommitError = _guard.AutonomousAckSameCommitError
AUTONOMOUS_ACK_SENTINEL = _guard.AUTONOMOUS_ACK_SENTINEL
AUTONOMOUS_ACK_TEMPLATE = _guard.AUTONOMOUS_ACK_TEMPLATE
AUTONOMOUS_ACK_DESCRIPTION = _guard.AUTONOMOUS_ACK_DESCRIPTION

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COMMANDS_DIR = _REPO_ROOT / "plugins" / "launchpad" / "commands"

# Direct-invocation autonomous-write commands that BL-356 lifts into the
# shared gate. `/lp-build` and `/lp-plan` already implement their own gate
# variants (build also calls the same-commit check); the per-command shared
# `assert_autonomous_ack` reference MUST appear in every file's gate step.
GATED_COMMANDS = ("lp-build", "lp-inf", "lp-resolve-todo-parallel", "lp-ship")

# Commands explicitly scope-NOT-included per BL-356 fix-shape item 5.
# `/lp-review` writes to `.harness/todos/` but does not mutate source code;
# `/lp-test-browser` is read-only-ish. Both proceed regardless of ack state.
NON_GATED_COMMANDS = ("lp-review", "lp-test-browser")


# ---------------------------------------------------------------------------
# (1) + (2) Python-level helper behaviour.
# ---------------------------------------------------------------------------


def test_assert_autonomous_ack_raises_when_file_missing() -> None:
    """Missing `.launchpad/autonomous-ack.md` → AutonomousAckMissingError."""
    with tempfile.TemporaryDirectory(prefix="lp-ack-missing-") as tmpstr:
        tmp = Path(tmpstr).resolve()
        # Deliberately do NOT create the ack file.
        with pytest.raises(AutonomousAckMissingError) as excinfo:
            assert_autonomous_ack(tmp)
        # Refuse-message must include the description and the template
        # sentinel so first-time users have the full content inline.
        msg = str(excinfo.value)
        assert AUTONOMOUS_ACK_SENTINEL in msg, (
            "refuse-message must embed the canonical template sentinel "
            f"`{AUTONOMOUS_ACK_SENTINEL}`; got: {msg!r}"
        )
        # The description sentence is verbatim from the constant.
        assert AUTONOMOUS_ACK_DESCRIPTION in msg, (
            "refuse-message must embed AUTONOMOUS_ACK_DESCRIPTION verbatim"
        )


def test_assert_autonomous_ack_passes_when_file_present() -> None:
    """With the ack file present, assert_autonomous_ack does not raise."""
    with tempfile.TemporaryDirectory(prefix="lp-ack-present-") as tmpstr:
        tmp = Path(tmpstr).resolve()
        ack = tmp / ".launchpad" / "autonomous-ack.md"
        ack.parent.mkdir(parents=True, exist_ok=True)
        ack.write_text("# Autonomous Execution Acknowledgment\n\nack body\n", encoding="utf-8")
        # Should not raise.
        assert_autonomous_ack(tmp)


def test_assert_autonomous_ack_treats_directory_as_missing() -> None:
    """If `.launchpad/autonomous-ack.md` exists as a directory (corrupt
    state), the helper still raises — `is_file()` is the source of truth,
    not `exists()`."""
    with tempfile.TemporaryDirectory(prefix="lp-ack-dir-") as tmpstr:
        tmp = Path(tmpstr).resolve()
        weird = tmp / ".launchpad" / "autonomous-ack.md"
        weird.mkdir(parents=True, exist_ok=True)
        with pytest.raises(AutonomousAckMissingError):
            assert_autonomous_ack(tmp)


# ---------------------------------------------------------------------------
# (3) Same-commit / cross-commit guard via raising API.
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "Test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(["git", *args], cwd=cwd, check=True, env=env, capture_output=True)


def test_assert_ack_not_same_commit_raises_on_same_commit_attack() -> None:
    """Hostile timeline (section + ack in same commit) raises the
    AutonomousAckSameCommitError variant — the section-level guard reuses
    `section_added_with_ack` internally."""
    with tempfile.TemporaryDirectory(prefix="lp-ack-samecommit-") as tmpstr:
        tmp = Path(tmpstr).resolve()
        _git(tmp, "init", "-q", "-b", "main")
        _git(tmp, "config", "user.email", "test@example.com")
        _git(tmp, "config", "user.name", "Test")

        # Commit 1: registry with benign section.
        registry = tmp / "docs" / "tasks" / "SECTION_REGISTRY.md"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            "# Section Registry\n\n## Registry\n\n### benign-section\n\n- **Status:** shaped\n",
            encoding="utf-8",
        )
        _git(tmp, "add", "docs/tasks/SECTION_REGISTRY.md")
        _git(tmp, "commit", "-q", "-m", "init")

        # Commit 2: hostile shape — section + ack in same commit.
        registry.write_text(
            "# Section Registry\n\n## Registry\n\n"
            "### benign-section\n\n- **Status:** shaped\n\n"
            "### hostile-section\n\n- **Status:** shaped\n",
            encoding="utf-8",
        )
        ack = tmp / ".launchpad" / "autonomous-ack.md"
        ack.parent.mkdir(parents=True, exist_ok=True)
        ack.write_text("ack\n", encoding="utf-8")
        _git(tmp, "add", "docs/tasks/SECTION_REGISTRY.md", ".launchpad/autonomous-ack.md")
        _git(tmp, "commit", "-q", "-m", "hostile")

        with pytest.raises(AutonomousAckSameCommitError) as excinfo:
            assert_ack_not_same_commit_as(tmp, "hostile-section")
        # Refuse-message preserved verbatim from v2.1.5.
        assert "hostile PR would use to bypass review" in str(excinfo.value)

        # Benign section is fine.
        assert_ack_not_same_commit_as(tmp, "benign-section")


# ---------------------------------------------------------------------------
# (5) Source-of-truth: command markdown references the shared helper.
# ---------------------------------------------------------------------------


def _read_command(name: str) -> str:
    path = _COMMANDS_DIR / f"{name}.md"
    assert path.is_file(), f"command markdown not found: {path}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("command", GATED_COMMANDS)
def test_gated_command_references_shared_helper(command: str) -> None:
    """Every direct-invocation autonomous-write command's markdown MUST
    reference `assert_autonomous_ack` by name in its gate step.

    This is the single-source-of-truth invariant — command markdown does
    NOT inline its own `.launchpad/autonomous-ack.md` absence check. If a
    future contributor copy-pastes the v2.1.5 inline refuse-message back
    into a command file, this test fails and points them at
    `autonomous_guard.py`.
    """
    body = _read_command(command)
    assert "assert_autonomous_ack" in body, (
        f"`{command}.md` must reference `assert_autonomous_ack` from "
        f"`plugin_stack_adapters/autonomous_guard.py` in its Step 0 gate. "
        f"BL-356 invariant: ack-gate logic lives in exactly one place."
    )


@pytest.mark.parametrize("command", GATED_COMMANDS)
def test_gated_command_does_not_inline_absence_check(command: str) -> None:
    """Negative side of the SoT invariant: command markdown MUST NOT
    contain an inline `IF .launchpad/autonomous-ack.md does NOT exist`
    pattern. The only acceptable form is the
    `assert_autonomous_ack(repo_root)` reference covered above.
    """
    body = _read_command(command)
    # Strip the inline form's signature pattern across whitespace variants.
    forbidden = re.compile(
        r"IF\s+`?\.launchpad/autonomous-ack\.md`?\s+does\s+NOT\s+exist",
        re.IGNORECASE,
    )
    match = forbidden.search(body)
    assert match is None, (
        f"`{command}.md` contains an inline absence-check pattern at "
        f"position {match.start() if match else -1}: "
        f"{match.group(0) if match else ''!r}. Replace with a call to "
        f"`assert_autonomous_ack(repo_root)` from `autonomous_guard.py`."
    )


# ---------------------------------------------------------------------------
# (4) Negative scope: /lp-review and /lp-test-browser are NOT gated.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", NON_GATED_COMMANDS)
def test_non_gated_commands_do_not_reference_helper(command: str) -> None:
    """`/lp-review` and `/lp-test-browser` are explicitly scope-NOT-included
    per BL-356 fix-shape item 5. Adding the gate to them in a future BL
    requires a deliberate BL header + opt-in — this test prevents drift
    by enforcing absence today.
    """
    body = _read_command(command)
    assert "assert_autonomous_ack" not in body, (
        f"`{command}.md` references `assert_autonomous_ack` but BL-356 "
        f"scope-NOT-included list explicitly excludes it. If you intend "
        f"to bring the gate to this command, file a new BL and update "
        f"this test."
    )


# ---------------------------------------------------------------------------
# (6) UX surface: every refuse / transition site embeds the template
# sentinel + the description.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", GATED_COMMANDS)
def test_gated_command_surface_embeds_template_sentinel(command: str) -> None:
    """Every gated command's markdown must embed the canonical template
    sentinel `# Autonomous Execution Acknowledgment` so the rendered
    refuse-message includes the copy-pasteable starter inline. Per BL-356
    UX item 4, first-time users hitting the refuse must not have to read
    HOW_IT_WORKS.md to author the file.
    """
    body = _read_command(command)
    assert AUTONOMOUS_ACK_SENTINEL in body, (
        f"`{command}.md` must embed the canonical template sentinel "
        f"`{AUTONOMOUS_ACK_SENTINEL}` so the rendered refuse-message "
        f"shows the user the starter template inline."
    )


def test_lp_plan_transition_message_embeds_template_sentinel() -> None:
    """`/lp-plan` Step 5 success branch surfaces the ack requirement as
    a transition message (not a refuse). Same UX content applies — user
    is told they need the file before `/lp-build` runs, so the template
    must be inline at the transition site too.
    """
    body = _read_command("lp-plan")
    assert AUTONOMOUS_ACK_SENTINEL in body, (
        "`/lp-plan` must embed the canonical template sentinel "
        f"`{AUTONOMOUS_ACK_SENTINEL}` in its Step 5 transition message "
        "so users learn what `autonomous-ack.md` is before they need it."
    )


def test_refuse_message_includes_full_template_constant() -> None:
    """The Python-level refuse-message returned by AutonomousAckMissingError
    must embed the full `AUTONOMOUS_ACK_TEMPLATE` constant verbatim — not
    a summary or excerpt. This anchors the single-source-of-truth: if the
    template is edited, the refuse-text auto-tracks.
    """
    with tempfile.TemporaryDirectory(prefix="lp-ack-fulltpl-") as tmpstr:
        tmp = Path(tmpstr).resolve()
        with pytest.raises(AutonomousAckMissingError) as excinfo:
            assert_autonomous_ack(tmp)
        msg = str(excinfo.value)
        assert AUTONOMOUS_ACK_TEMPLATE.rstrip() in msg, (
            "Python refuse-message must contain AUTONOMOUS_ACK_TEMPLATE "
            "verbatim (modulo trailing newline) so edits to the constant "
            "auto-propagate to the refuse surface."
        )
