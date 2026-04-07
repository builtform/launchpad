# CE v2.61.0 Update — Impact Analysis on LaunchPad Porting Plan

**Date:** 2026-04-07
**CE Version Analyzed:** 2.61.0 (was 2.35.2 at time of original analysis, March 28)
**LaunchPad Plan Status:** Phases 0-11 + 8.5 + Finale all planned (v1-v8), none implemented except Phase 11 Part A (2 skills ported)
**BuiltForm Status:** 12 agents, 18 skills, 25 commands. No Phase 0-10 components implemented yet.
**Architecture Decision:** Keep three-tier model (commands / agents / skills). CE's commands-into-skills merge is NOT adopted.
**Sources:** All 14 phase plan files, both repos' current state, CE GitHub repo, Trevin Chow article (3/31/2026)

---

## Table of Contents

1. [What Actually Changed in CE](#what-actually-changed-in-ce)
2. [Big Impact Changes — What Moves the Needle](#big-impact-changes)
3. [Phase-by-Phase Impact Assessment](#phase-by-phase-impact-assessment)
4. [What We Should NOT Port](#what-we-should-not-port)
5. [Recommended Priority Order](#recommended-priority-order)

---

## What Actually Changed in CE

Between v2.35.2 (our March 28 baseline) and v2.61.0:

| Metric                               | March 28 | Now | Delta                    |
| ------------------------------------ | -------- | --- | ------------------------ |
| Agents                               | 29       | 49  | +20                      |
| Skills (including absorbed commands) | 19       | 41  | +22                      |
| Commands                             | 22       | 1   | -21 (migrated to skills) |
| Total components                     | 70       | 91  | +21 net                  |

**Structural change:** All 22 commands migrated into skills (v2.39.0). `deepen-plan` absorbed into `ce:plan`. We are NOT adopting this — our three-tier model stays.

**New agent categories:**

- `document-review/` — 7 entirely new agents (adversarial, coherence, design-lens, feasibility, product-lens, scope-guardian, security-lens)
- 13 new `review/` agents (adversarial, api-contract, cli-readiness, correctness, data-migrations, maintainability, performance-reviewer, previous-comments, project-standards, reliability, security-reviewer, testing-reviewer)
- 1 new `research/` agent (issue-intelligence-analyst)

**Major feature additions:**

- Review confidence rubric (6-tier, 0.60 threshold, ~49% FP reduction)
- Mandatory review across entire pipeline
- Headless mode for programmatic review invocation
- Bare prompts in ce:work (auto complexity assessment)
- "Testing addressed" replaces binary "tests pass"
- Interactive deepening in ce:plan
- Conditional visual aids (Mermaid/ASCII)
- Feedback clustering in PR resolution
- Track-based compound schema (bug vs knowledge tracks)

---

## Big Impact Changes

These are the changes that would **significantly move the needle** for our pipeline quality. Not cosmetic. Not nice-to-have. These are the ones that change outcomes.

### 1. Review Confidence Rubric — HIGH IMPACT

**What it is:** Every review finding gets scored 0.00-1.00 on a 6-tier confidence scale. Findings below 0.60 are suppressed. Six specific false-positive categories are targeted: pre-existing issues, style nitpicks, intentional patterns, handled-elsewhere cases, code restatement, and generic advice. Multi-persona agreement (2+ agents flagging same issue) boosts confidence by 0.10.

**Why it matters for us:** Our Phase 0 `/review` dispatches up to 10+ agents in parallel. Without confidence scoring, that's a firehose of findings including noise. CE reports ~49% FP reduction. The difference between a review system developers use vs one they ignore is noise level.

**Where it fits:** Phase 0 — `/review` command's synthesis step (Step 5 in our plan). The rubric runs AFTER agents return findings, BEFORE writing to `.harness/todos/`. This is a post-processing layer in the orchestrator, not a change to individual agents.

**Implementation scope:** Medium. Add a confidence scoring section to `/review`'s synthesis step. Define the 6 FP categories. Add the 0.60 threshold. Add multi-agent agreement boost logic. Add intent verification against PR context.

### 2. Mandatory Review Enforcement — HIGH IMPACT

**What it is:** Review is no longer optional anywhere in CE's pipeline. ce:work, ce:brainstorm, ce:plan all enforce review as a non-negotiable checkpoint. Full review is the default; limited review requires justification.

**Why it matters for us:** Our Phase 0 already makes review mandatory in `/harness:build` (Step 2). But `/commit` (Phase 7) makes review optional (Step 2.5 asks "Run code review?"). CE's insight is correct — mandate first, reduce noise second. If review is optional, developers skip it. If it's mandatory but noisy, they resent it. The confidence rubric (Impact #1) makes mandatory review viable.

**Where it fits:** Phase 7 — Change `/commit` Step 2.5 from optional to default-on. User can still skip with justification, but the default flips. This only works AFTER the confidence rubric is implemented (Impact #1), otherwise we're mandating noise.

**Implementation scope:** Small. One-line change in `/commit` step 2.5 logic.

### 3. Headless Review Mode — HIGH IMPACT

**What it is:** Reviews can be invoked programmatically by other skills/commands without interactive prompts or git ceremony. This is what enabled CE to make review mandatory everywhere — other pipeline steps can call review as a subroutine.

**Why it matters for us:** Our `/review` command is designed for standalone invocation with interactive elements (reporting, user prompts). If `/harden-plan` or `/brainstorm` want to run a quick review, they can't easily call `/review` without triggering all the ceremony. A headless mode would let any command invoke review as a silent quality gate.

**Where it fits:** Phase 0 — Add a `--headless` flag to `/review` that suppresses interactive output, skips the report step, and returns findings as structured data. Used by `/harden-plan` (Phase 3), `/commit` Step 2.5 (Phase 7), and potentially `/brainstorm` (Phase 3).

**Implementation scope:** Medium. Add flag parsing to `/review`, conditional output path for headless mode.

### 4. Document-Review Agent Fleet (7 agents) — HIGH IMPACT

**What it is:** An entirely new category of agents that review documents (plans, specs, brainstorm outputs) with multiple lenses: adversarial, coherence, design, feasibility, product, scope, security. This is the same multi-agent scrutiny CE applies to code, now applied to plans.

**Why it matters for us:** Our `/harden-plan` (Phase 3) dispatches code-focused review agents against plan documents. But reviewing a plan for security vulnerabilities is different from reviewing it for scope creep or feasibility. CE created dedicated document-review agents because the lens matters. Our pipeline produces many documents (brainstorm → spec → plan → approved plan) — each benefits from multi-lens document review.

**Where it fits:** New addition to Phase 3. The document-review agents would be dispatched by `/harden-plan` in a new step, and by the `document-review` skill. They complement (not replace) the existing code-focused review agents. Applicable agents for our stack:

- `adversarial-document-reviewer` — challenges assumptions (always applicable)
- `coherence-reviewer` — checks consistency (always applicable)
- `feasibility-reviewer` — assesses technical feasibility (always applicable)
- `scope-guardian-reviewer` — guards against scope creep (always applicable)
- `product-lens-reviewer` — product strategy (domain-agnostic, applicable)
- `security-lens-reviewer` — security implications (applicable)
- `design-lens-reviewer` — design/UX review (applicable when design-bearing)

All 7 are language-agnostic and directly applicable.

**Implementation scope:** HIGH. 7 new agent files + wiring into `/harden-plan` + wiring into `document-review` skill + `.launchpad/agents.yml` new key (`harden_document_agents`).

### 5. "Testing Addressed" Paradigm — MEDIUM-HIGH IMPACT

**What it is:** Replaces the binary "tests pass" checklist with deliberation about whether a behavioral change needs a test. The testing-reviewer agent got a new 5th check that flags behavioral code changes (new branches, state mutations, API changes) with zero corresponding test additions.

**Why it matters for us:** Our Phase 1 `kieran-foad-ts-reviewer` checks test quality but doesn't specifically enforce "did you write tests for new behavior?" This is a common gap — existing tests still pass, but new behavior is untested. CE's approach makes test coverage intentional rather than incidental.

**Where it fits:** Phase 1 — Add a testing-awareness criterion to the TypeScript reviewer or create a dedicated `testing-reviewer` agent. The criterion: "For each behavioral change (new branch, state mutation, API endpoint, error path), verify a corresponding test exists or document why testing is deferred."

**Implementation scope:** Small-medium. Either add a section to `kieran-foad-ts-reviewer` or create a new lightweight agent.

### 6. Previous-Comments-Reviewer Agent — MEDIUM IMPACT

**What it is:** A review agent that checks whether a PR addresses feedback from previous review cycles. Closes the review feedback loop — prevents the pattern where reviewer says "fix X", developer pushes, but X isn't actually fixed.

**Why it matters for us:** Our Phase 4 `/resolve-pr-comments` resolves PR comments, but there's no verification that the resolution actually addressed the feedback. This agent closes that gap.

**Where it fits:** Phase 4 — Wire as a post-resolution verification step. After `/resolve-pr-comments` runs, dispatch `previous-comments-reviewer` to verify the resolutions actually addressed the original feedback.

**Implementation scope:** Small. 1 new agent file + wiring into `/resolve-pr-comments` post-resolution step.

### 7. Feedback Clustering in PR Resolution — MEDIUM IMPACT

**What it is:** Detects when you're playing whack-a-mole with PR feedback by clustering similar comments by concern category and spatial proximity. After 2 fix-verify cycles, remaining issues surface as "recurring patterns" instead of individual tickets. Actionability filter strips approvals, badges, emoji reactions.

**Why it matters for us:** Our Phase 4 `/resolve-pr-comments` treats each comment independently. If a reviewer flags the same concern in 5 places, we spawn 5 agents. Clustering would identify "this is one systemic issue" and address it holistically.

**Where it fits:** Phase 4 — Add clustering logic to `/resolve-pr-comments` Step 2 (Group by File), expanding it to "Group by File + Cluster by Concern." Add actionability filter to Step 1 (Fetch Threads) to skip non-actionable comments.

**Implementation scope:** Medium. Clustering logic in the command, actionability filter.

### 8. Track-Based Compound Schema — MEDIUM IMPACT

**What it is:** Learnings now split into two tracks: bug-track docs (build errors, test failures, runtime errors) keep the full diagnostic fields, while knowledge-track docs (best practices, workflow issues, DX gaps) get a lighter template.

**Why it matters for us:** Our Phase 6 `/learn` command uses a single template for all learnings. Bug fixes and best practices are structurally different — a bug has steps to reproduce, stack traces, root cause; a best practice has context, rationale, examples. Using the right template produces more useful documents.

**Where it fits:** Phase 6 — Split the `compound-docs` skill's resolution template into two variants. Add track detection to `/learn` Phase 2 (Assembly) based on the Category Classifier's output.

**Implementation scope:** Small. Two template variants + conditional selection logic.

---

## Phase-by-Phase Impact Assessment

### Phase 0: Review Agent Config & Pipeline Restructure

**Plan version:** v8 | **Status:** Not implemented

| CE Change                              | Impact                                      | Action Required                                                                                                    |
| -------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Confidence rubric                      | **HIGH**                                    | Add scoring/suppression to `/review` Step 5 (synthesis). Define 6 FP categories, 0.60 threshold, multi-agent boost |
| Headless review mode                   | **HIGH**                                    | Add `--headless` flag to `/review`. Suppresses interactive output, returns structured findings                     |
| Mandatory review                       | LOW (already mandatory in `/harness:build`) | No change needed for Phase 0                                                                                       |
| Pipe-delimited table output            | LOW                                         | Already using structured output in our agent definitions                                                           |
| resolve-base.sh hardening              | N/A                                         | We don't have resolve-base.sh                                                                                      |
| Intent verification against PR context | MEDIUM                                      | Add to `/review` synthesis: read PR title/body/linked issue, suppress contradicting findings                       |

**Net assessment:** Phase 0 plan needs **two significant additions** (confidence rubric + headless mode) and one minor addition (intent verification). The core architecture (commands, agents.yml, scripts, directory structure) is unchanged.

### Phase 1: Review Agent Fleet

**Plan version:** v6 | **Status:** Not implemented

| CE Change                   | Impact          | Action Required                                                               |
| --------------------------- | --------------- | ----------------------------------------------------------------------------- |
| 13 new review agents        | MEDIUM          | Evaluate each for applicability. Language-agnostic ones are directly relevant |
| Testing-addressed paradigm  | **MEDIUM-HIGH** | Add testing awareness to TS reviewer or create dedicated agent                |
| Agent count (15 → 28 in CE) | INFORMATIONAL   | We don't need to match count — our 8+1 covers our stack                       |

**Applicable new agents to consider adding:**

| CE Agent                       | Applicable?             | Recommendation                                                              |
| ------------------------------ | ----------------------- | --------------------------------------------------------------------------- |
| `adversarial-reviewer`         | Yes (language-agnostic) | Consider for Phase 1. Tries to break code — different lens from correctness |
| `api-contract-reviewer`        | Yes (we have Hono API)  | Consider. Reviews API contracts, breaking changes                           |
| `correctness-reviewer`         | Yes (language-agnostic) | Consider. Logical correctness, edge cases                                   |
| `maintainability-reviewer`     | Yes (language-agnostic) | Low priority — overlaps with simplicity + architecture                      |
| `previous-comments-reviewer`   | Yes                     | Add to Phase 4 (PR resolution), not Phase 1                                 |
| `project-standards-reviewer`   | Yes (language-agnostic) | Low priority — overlaps with pattern-recognition                            |
| `reliability-reviewer`         | Yes (language-agnostic) | Consider. Error handling, resilience                                        |
| `testing-reviewer`             | Yes                     | **Recommend adding.** New behavioral-change test check is valuable          |
| `performance-reviewer`         | Redundant               | We already have `performance-auditor`                                       |
| `security-reviewer`            | Redundant               | We already have `security-auditor`                                          |
| `data-migrations-reviewer`     | Redundant               | We already have Phase 2 DB chain                                            |
| `cli-readiness-reviewer`       | No                      | CE-specific (CLI agent product)                                             |
| `cli-agent-readiness-reviewer` | No                      | CE-specific                                                                 |

**Net assessment:** Consider adding **3-4 agents** from CE's new fleet: `testing-reviewer`, `adversarial-reviewer`, `api-contract-reviewer`, and possibly `correctness-reviewer`. The rest are either redundant with our existing agents or CE-specific. This expands Phase 1 from 8 agents to 11-12.

### Phase 2: Database Agent Chain

**Plan version:** v4 | **Status:** Not implemented

| CE Change                                       | Impact | Action Required                                                                                                                                |
| ----------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `data-migrations-reviewer` (new separate agent) | LOW    | We already have `data-migration-auditor` which covers this scope. CE split their DB review into more granular agents — we don't need to follow |

**Net assessment:** No changes needed. Our 3-agent chain (drift → migration + integrity in parallel) is well-designed and covers the scope.

### Phase 3: Workflow Layers

**Plan version:** v6 | **Status:** Not implemented

| CE Change                         | Impact   | Action Required                                                                                                                                                                      |
| --------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 7 document-review agents          | **HIGH** | New agent category. Add to `/harden-plan` dispatch. Create new `agents.yml` key                                                                                                      |
| Interactive deepening             | MEDIUM   | Add interactive mode to `/harden-plan` where user can accept/reject each agent's findings before integration                                                                         |
| deepen-plan absorbed into ce:plan | LOW      | We already decided to keep `/harden-plan` separate. No change                                                                                                                        |
| Verification rigor in brainstorm  | MEDIUM   | Add verification permission to `/brainstorm`: agents can read schemas/routes/configs to verify claims, but not make implementation decisions. Label unverified claims as assumptions |
| Mandatory document-review         | MEDIUM   | Make document-review skill invocation non-optional in `/harden-plan` (not just Step 2 pre-check). Already largely covered by our plan                                                |
| Conditional visual aids           | LOW      | Nice-to-have. Auto-generate Mermaid diagrams when complexity thresholds are met. Not a needle-mover                                                                                  |
| Blank test scenario flagging      | LOW      | Add to spec-flow-analyzer: flag feature-bearing plan units with blank test scenarios                                                                                                 |
| ce:plan decision matrix           | LOW      | Visual aid for flag combinations. Not a needle-mover                                                                                                                                 |

**Net assessment:** Phase 3 needs **one major addition** (7 document-review agents wired into `/harden-plan`) and two minor improvements (interactive deepening, brainstorm verification rigor). The document-review agents are the single biggest new capability CE added that we didn't account for.

### Phase 4: PR Comment Resolution

**Plan version:** v3.2 | **Status:** Not implemented

| CE Change                         | Impact     | Action Required                                                                                                                         |
| --------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Feedback clustering               | **MEDIUM** | Add concern clustering + spatial proximity grouping to Step 2. Surface "recurring patterns" after 2 cycles                              |
| Actionability filter              | MEDIUM     | Strip approvals, badges, emoji, wrapper text before dispatching agents                                                                  |
| Previous-comments-reviewer        | MEDIUM     | Add post-resolution verification step                                                                                                   |
| Cross-invocation cluster analysis | LOW        | Detects systemic issues across multiple `/resolve-pr-comments` invocations. Nice-to-have, not a needle-mover for initial implementation |

**Net assessment:** Two medium additions (feedback clustering + previous-comments-reviewer) and one small addition (actionability filter).

### Phase 5: Browser Testing

**Plan version:** v4.2 | **Status:** Not implemented

No CE changes affect this phase. CE's `test-browser` and `bug-reproduction-validator` were not mentioned in the update article, and the repo analysis showed no modifications.

**Net assessment:** No changes needed.

### Phase 6: Compound Learning

**Plan version:** v4.2 | **Status:** Not implemented

| CE Change             | Impact     | Action Required                                                                                                  |
| --------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| Track-based schema    | **MEDIUM** | Split template: bug-track (full diagnostics) vs knowledge-track (lighter). Add track detection based on category |
| Discoverability check | SMALL      | Verify `docs/solutions/` is referenced in CLAUDE.md. One-time check, easy to add                                 |
| ce-compound-refresh   | LOW        | Ability to refresh existing learnings. Not in our plan, low priority                                             |

**Net assessment:** One medium improvement (track-based schema). The rest are minor.

### Phase 7: Manual Commit Workflow

**Plan version:** v3 | **Status:** Not implemented

| CE Change                | Impact | Action Required                                                                                       |
| ------------------------ | ------ | ----------------------------------------------------------------------------------------------------- |
| Mandatory review default | MEDIUM | Flip `/commit` Step 2.5 from opt-in to default-on (only viable after confidence rubric from Phase 0)  |
| git-commit-push-pr skill | LOW    | CE created a separate skill for commit+push+PR. We already have `/commit` + `/ship` which covers this |

**Net assessment:** One small change (flip default) contingent on Phase 0's confidence rubric.

### Phase 8: Backlog System

**Plan version:** v4 | **Status:** Not implemented

No CE changes affect this phase. The backlog system is a LaunchPad-original concept.

**Net assessment:** No changes needed.

### Phase 8.5: Structure Drift Detection

**Plan version:** v4 | **Status:** Not implemented

No CE changes affect this phase. This is a LaunchPad-original concept.

**Net assessment:** No changes needed.

### Phase 9: Git Worktree

**Plan version:** v1 | **Status:** Not implemented

No CE changes affect this phase. CE's worktree skill was unchanged. Our plan already correctly identified that Claude Code's native worktree support supersedes CE's custom scripts.

**Net assessment:** No changes needed.

### Phase 10: Design Workflow

**Plan version:** v3 | **Status:** Not implemented

No CE design agents were modified in the update. The `design-implementation-reviewer`, `design-iterator`, and `figma-design-sync` agents are unchanged.

**Net assessment:** No changes needed.

### Phase 11: Skill Porting

**Plan version:** v2 | **Status:** Partially implemented (Part A: 2 skills ported)

No CE changes affect this phase. The skill porting work is about wiring existing BuiltForm skills into LaunchPad commands, not about CE agent changes.

**Net assessment:** No changes needed.

### Phase Finale: Documentation Refresh

**Plan version:** v1 | **Status:** Not implemented

Any changes from CE that get incorporated into Phases 0-6 will naturally flow into the Finale documentation refresh. No separate action needed.

**Net assessment:** No changes needed — this phase inherently captures all upstream changes.

---

## What We Should NOT Port

| CE Change                                                 | Why Skip                                                                                      |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Commands-into-skills merge                                | Architectural preference. Our three-tier model works. This is file organization, not feature. |
| 10 platform converters (Codex, Copilot, Droid, etc.)      | CE-specific product feature. Not relevant to LaunchPad.                                       |
| `cli-readiness-reviewer` / `cli-agent-readiness-reviewer` | CE-specific (their product is a CLI agent platform).                                          |
| `coding-tutor` plugin                                     | Separate product. Not relevant.                                                               |
| `ce-ideate` skill                                         | Unclear purpose. We have `/brainstorm` which covers ideation. Wait for more info.             |
| `ce-work-beta`                                            | Experimental. Wait for it to stabilize.                                                       |
| `ce-compound-refresh`                                     | Low priority. Focus on getting `/learn` working first.                                        |
| `claude-permissions-optimizer`                            | CE-specific utility.                                                                          |
| `onboarding` skill                                        | CE-specific project onboarding. We have `/Hydrate`.                                           |
| `proof` skill                                             | Unclear purpose. No documentation on what this does.                                          |
| `git-clean-gone-branches`                                 | Utility script. Not pipeline-critical. Can add later trivially.                               |
| Conditional visual aids                                   | Nice-to-have cosmetic improvement. Not a quality gate.                                        |
| Argument-hint cleanup                                     | CE-specific syntax change.                                                                    |
| Model field normalization                                 | CE converter infrastructure. Not relevant.                                                    |

---

## Recommended Priority Order

Based on impact analysis, here's what to incorporate and when:

### Must-Have (incorporate into existing phase plans before implementation)

| Priority | Change                                                   | Phase   | Effort |
| -------- | -------------------------------------------------------- | ------- | ------ |
| 1        | **Confidence rubric** in `/review` synthesis             | Phase 0 | Medium |
| 2        | **Headless review mode** (`--headless` flag)             | Phase 0 | Medium |
| 3        | **7 document-review agents** + `/harden-plan` wiring     | Phase 3 | High   |
| 4        | **Testing-reviewer agent** (behavioral change detection) | Phase 1 | Small  |

### Should-Have (incorporate if scope allows)

| Priority | Change                                                            | Phase   | Effort |
| -------- | ----------------------------------------------------------------- | ------- | ------ |
| 5        | **Feedback clustering** in `/resolve-pr-comments`                 | Phase 4 | Medium |
| 6        | **Previous-comments-reviewer** agent                              | Phase 4 | Small  |
| 7        | **Track-based compound schema** (bug vs knowledge)                | Phase 6 | Small  |
| 8        | **Intent verification** against PR context in `/review`           | Phase 0 | Small  |
| 9        | **Brainstorm verification rigor** (read schemas to verify claims) | Phase 3 | Small  |
| 10       | **Interactive deepening** in `/harden-plan`                       | Phase 3 | Medium |

### Consider (evaluate during implementation)

| Priority | Change                                | Phase   | Effort |
| -------- | ------------------------------------- | ------- | ------ |
| 11       | `adversarial-reviewer` agent          | Phase 1 | Small  |
| 12       | `api-contract-reviewer` agent         | Phase 1 | Small  |
| 13       | `correctness-reviewer` agent          | Phase 1 | Small  |
| 14       | Mandatory review default in `/commit` | Phase 7 | Tiny   |
| 15       | Actionability filter in PR resolution | Phase 4 | Small  |

---

## Summary

**4 must-haves** that significantly move the needle:

1. Confidence rubric (~49% FP reduction makes review viable at scale)
2. Headless review mode (enables other commands to invoke review programmatically)
3. 7 document-review agents (plans get the same scrutiny as code)
4. Testing-reviewer agent (catches untested behavioral changes)

**6 should-haves** that improve quality:
5-10: Feedback clustering, previous-comments verification, track-based compound, intent verification, brainstorm verification, interactive deepening

**5 consider items** for evaluation during implementation.

**No structural changes to the porting plan are needed.** The three-tier architecture holds. The phase order holds. The additions are enhancements WITHIN existing phases, not new phases. The biggest new scope is the 7 document-review agents in Phase 3, which adds ~7 agent files and wiring changes to `/harden-plan`.
