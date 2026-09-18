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


def test_codex_round5_p1_b_no_remote_branch_split() -> None:
    """v2.1.5 round-5 fix (Codex P1-B): Step 1.A originally conflated
    `HAS_HEAD == no` with `HAS_REMOTE == no` and applied the same scope
    (untracked + staged-tracked) to both. But for `HAS_HEAD == yes` AND
    `HAS_REMOTE == no` (existing-history, local-only or unfetched fork),
    that scope OMITS unstaged modifications to tracked files — exactly
    what the user wants reviewed locally.

    The fix splits Step 1.A into two explicit cases. This test pins
    the split."""
    text = _md()
    step1a_idx = text.find("Step 1.A: Pre-first-commit fallback")
    step1_5_idx = text.find("## Step 1.5")
    assert step1a_idx > 0 and step1_5_idx > step1a_idx
    step1a_body = text[step1a_idx:step1_5_idx]

    # Both cases must be explicitly documented.
    assert "Case 1: `HAS_HEAD == no`" in step1a_body, (
        "Codex round-5 P1-B regression: Case 1 (no-HEAD) branch must "
        "be explicitly distinguished from Case 2 (existing-history, "
        "no-remote)."
    )
    assert "Case 2: `HAS_HEAD == yes` AND `HAS_REMOTE == no`" in step1a_body, (
        "Codex round-5 P1-B regression: Case 2 (existing-history, "
        "no-remote) must have its own scope description that includes "
        "unstaged modifications via `git diff --name-only HEAD`."
    )
    # Case 2 MUST include `git diff --name-only HEAD` (the omitted shape).
    assert "git diff --name-only HEAD" in step1a_body, (
        "Codex round-5 P1-B: Case 2's scope must include "
        "`git diff --name-only HEAD` so unstaged tracked-file edits "
        "reach review."
    )
    # Distinct banners for each case (operator-visible signal that the
    # right branch fired).
    assert "[pre-first-commit]" in step1a_body
    assert "[no-remote-base]" in step1a_body


def test_document_agent_roster_is_loaded_and_dispatched_without_stack_filter() -> None:
    """Recipient-output review is opt-in and independent of code stack."""
    text = _md()
    step0_idx = text.find("## Step 0: Read Configuration")
    step1_idx = text.find("## Step 1: Determine Diff Scope")
    step46_idx = text.find("## Step 4.6: Conditional Document Truth Agents")
    step5_idx = text.find("## Step 5: Confidence Scoring & Synthesis")

    assert step0_idx >= 0 and step1_idx > step0_idx
    assert "review_document_agents" in text[step0_idx:step1_idx]
    assert "review_document_artifacts" in text[step0_idx:step1_idx]
    assert step46_idx >= 0 and step5_idx > step46_idx
    step46_body = text[step46_idx:step5_idx]
    assert "dispatch all `resolved_review_document_agents` in parallel" in step46_body
    assert "document_artifact_inventory" in step46_body
    assert "repository-relative glob patterns" in step46_body
    assert "emit a P1 configuration finding" in step46_body
    assert "Do NOT apply the stack pre-filter" in step46_body
    assert "IF the list is empty: skip silently" in step46_body


def test_claims_auditor_receives_pr_intent_in_contextual_mode() -> None:
    """The default claims reviewer must receive the PR body it advertises."""
    text = _md()
    step3_idx = text.find("## Step 3: Dispatch Review Agents")
    step4_idx = text.find("## Step 4: Conditional DB Agent Dispatch")
    assert step3_idx >= 0 and step4_idx > step3_idx
    step3_body = text[step3_idx:step4_idx]

    assert "For `lp-claims-auditor`" in step3_body
    assert "pass `intent_context` from Step 1.5 verbatim" in step3_body
    assert "PR title, body, labels, and linked issue context" in step3_body
    assert "`--no-context` mode: pass no PR intent by design" in step3_body


def test_pr_intent_fetches_closing_issue_context() -> None:
    """Step 1.5 must fetch the issue context promised to the claims auditor."""
    text = _md()
    step15_idx = text.find("## Step 1.5: Read PR Intent Context")
    step2_idx = text.find("## Step 2: Pre-dispatch Secret Scan")
    assert step15_idx >= 0 and step2_idx > step15_idx
    step15_body = text[step15_idx:step2_idx]

    assert "title,body,labels,closingIssuesReferences" in step15_body
    assert "each closing issue's canonical URL" in step15_body
    assert "gh issue view <url> --json number,title,body,labels,state,url" in step15_body
    assert "Never fetch a closing reference by bare issue number" in step15_body
    assert "add the returned issue context to `intent_context`" in step15_body
    assert "record that issue as unavailable" in step15_body


def test_agent_p0_is_normalized_before_pipeline_serialization() -> None:
    """The P1/P2/P3 pipeline must retain but never serialize P0 priority."""
    text = _md()
    step5a_idx = text.find("### Step 5a: Collect raw findings from all agents")
    step5b_idx = text.find("### Step 5b: Deduplicate")
    assert step5a_idx >= 0 and step5b_idx > step5a_idx
    step5a_body = text[step5a_idx:step5b_idx]

    assert "Normalize any agent-reported P0 to pipeline P1" in step5a_body
    assert "Reported severity: P0" in step5a_body
    assert "downstream artifacts continue to use only P1/P2/P3" in step5a_body
    assert "coverage limitations as audit ledger entries, not findings" in step5a_body


def test_prevalidated_project_agents_survive_stack_filter() -> None:
    """Project-local agents resolved in Step 0 must reach Step 3 dispatch."""
    text = _md()
    step0_idx = text.find("## Step 0: Read Configuration")
    step1_idx = text.find("## Step 1: Determine Diff Scope")
    step3_idx = text.find("## Step 3: Dispatch Review Agents")
    step4_idx = text.find("## Step 4: Conditional DB Agent Dispatch")
    assert step0_idx >= 0 and step1_idx > step0_idx
    assert step3_idx >= 0 and step4_idx > step3_idx

    assert "prevalidated_project_agent_names" in text[step0_idx:step1_idx]
    assert "prevalidated_passthrough_names=" in text[step3_idx:step4_idx]
    assert "prevalidated_project_agent_names" in text[step3_idx:step4_idx]


def test_all_conditional_dispatches_use_resolved_rosters() -> None:
    """Missing optional agents must be skipped before any dispatch path."""
    text = _md()
    step0_idx = text.find("## Step 0: Read Configuration")
    step1_idx = text.find("## Step 1: Determine Diff Scope")
    step4_idx = text.find("## Step 4: Conditional DB Agent Dispatch")
    step5_idx = text.find("## Step 5: Confidence Scoring & Synthesis")
    assert step0_idx >= 0 and step1_idx > step0_idx
    assert step4_idx >= 0 and step5_idx > step4_idx

    step0_body = text[step0_idx:step1_idx]
    conditional_body = text[step4_idx:step5_idx]
    for roster in (
        "resolved_review_db_agents",
        "resolved_review_design_agents",
        "resolved_review_copy_agents",
        "resolved_review_document_agents",
    ):
        assert roster in step0_body
        assert roster in conditional_body

    assert "every later dispatch step MUST consume these resolved lists" in step0_body


def test_all_stack_mismatch_halts_without_full_roster_fallback() -> None:
    """A fully incompatible roster must fail visibly and stay filtered."""
    text = _md()
    step3_idx = text.find("## Step 3: Dispatch Review Agents")
    step4_idx = text.find("## Step 4: Conditional DB Agent Dispatch")
    assert step3_idx >= 0 and step4_idx > step3_idx
    step3_body = text[step3_idx:step4_idx]

    mismatch_idx = step3_body.find("**All-stack-mismatch refusal:**")
    fallback_idx = step3_body.find("**Pass-through fallback**")
    assert 0 <= mismatch_idx < fallback_idx
    assert "NoMatchingAgentsError" in step3_body
    assert "raise_on_no_match=True" in step3_body
    assert "emit a P1 configuration finding" in step3_body
    assert "Do NOT dispatch the full roster" in step3_body


def test_coverage_limitations_are_always_persisted_in_summary() -> None:
    """Headless callers must see checks skipped for environment reasons."""
    text = _md()
    step6_idx = text.find("## Step 6: Write Outputs")
    step7_idx = text.find("## Step 7: Report")
    assert step6_idx >= 0 and step7_idx > step6_idx
    step6_body = text[step6_idx:step7_idx]

    assert "## Coverage Limitations ({K})" in step6_body
    assert "Persist coverage limitations from every evidence reviewer" in step6_body
    assert "include the same subsection inside the appended blind findings section" in step6_body
    assert "Never create todo files for coverage limitations" in step6_body
    assert '"Clean review: no actionable findings"' in step6_body


def test_claims_findings_are_exempt_from_intent_suppression() -> None:
    """Disproving a PR assertion must not suppress the resulting finding."""
    text = _md()
    step5c_idx = text.find("### Step 5c: Confidence Scoring")
    step5d_idx = text.find("### Step 5d: Filter")
    assert step5c_idx >= 0 and step5d_idx > step5c_idx
    step5c_body = text[step5c_idx:step5d_idx]

    assert "Distinguish normative intent" in step5c_body
    assert "from factual assertions" in step5c_body
    assert "NEVER suppress an evidence-backed `lp-claims-auditor` finding" in step5c_body
    assert "that contradiction is the finding's proof" in step5c_body
