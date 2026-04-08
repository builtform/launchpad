# Implementation Handoff: Phases 0-11 + Finale

**Date:** 2026-04-07
**Context:** All phase plans (0-11 + 8.5 + Finale) are finalized and cross-validated across LaunchPad and BuiltForm. Zero gaps remain. This handoff covers the implementation order, session structure, and what each session needs to know.

---

## Strategy: 2 Sessions — LaunchPad First, Then BuiltForm

**Session 1:** Implement all LaunchPad phases (0 → 11 → Finale) in one continuous session.
**Session 2:** Implement all BuiltForm phases (0 → 11 → Finale) in one continuous session.

**Why one session per repo (not one per phase)?**

- Session history carries forward — Phase 1 knows exactly what Phase 0 just created without re-reading files.
- Cross-phase consistency is caught in real-time (e.g., if Phase 0 names a key differently than Phase 1 expects, the session sees it immediately).
- No startup overhead per phase — no need to re-establish context.

**Why LaunchPad first?**

- BuiltForm plans reference LaunchPad for full component definitions ("See LaunchPad Phase X plan"). Having implemented LaunchPad files to copy/adapt from is faster than building from plan text alone.
- BuiltForm Phase Finale explicitly depends on LaunchPad Phase Finale completing first.

**Implement one phase at a time within the session.** Don't start Phase 1 until Phase 0's verification checklist passes. Each phase boundary is a checkpoint.

**One branch per repo.** All phases commit to the same branch — `feat/ce-plugin-phases-0-finale` for LaunchPad, `feat/ce-plugin-phases-0-finale` for BuiltForm. Commit after each phase with a message like `feat: implement Phase 0 — review agent config & pipeline restructure`. This keeps the full implementation as a single reviewable unit per repo.

---

## Session 1: LaunchPad (All Phases)

### Starting Prompt

```
I'm implementing all phases (0 through 11 + 8.5 + Finale) for LaunchPad in this session, one phase at a time. All phases go on one branch: feat/ce-plugin-phases-0-finale.

Handoff: docs/handoffs/2026-04-07-implementation-handoff.md
Plans: docs/plans/launchpad_plans/

For each phase:
1. Read the plan file
2. Implement everything in the File Change Summary table (P0 first, then P1, then P2)
3. Run the Verification Checklist
4. Run: pnpm lint && pnpm typecheck && pnpm test
5. Commit with message: "feat: implement Phase [X] — [short description]"
6. Move to the next phase

Start with Phase 0.
```

### Phase Order & Key Notes

| #   | Phase         | Plan File                                                    | Key Notes                                                                                                                                                                                                            |
| --- | ------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Phase 0**   | `2026-03-27-ce-plugin-phase-0-review-agent-config.md` (v9.1) | Foundation — ~30 files. Agent renames (codebase-locator→file-locator etc.). build.sh/compound-learning.sh split. Confidence rubric, headless mode, intent verification in /review.                                   |
| 2   | **Phase 1**   | `2026-03-27-ce-plugin-phase-1-review-agent-fleet.md` (v7.1)  | 9 agents (7 default incl. testing-reviewer + 2 opt-in). agents.yml must have all 7 keys incl. harden_document_agents.                                                                                                |
| 3   | **Phase 2**   | `2026-03-28-ce-plugin-phase-2-database-agent-chain.md` (v5)  | 3 DB agents. schema-drift-detector is ground-up rewrite. Sequential-then-parallel dispatch. Uncomment schema-drift-detector in harden_plan_conditional_agents.                                                       |
| 4   | **Phase 3**   | `2026-04-02-ce-plugin-phase-3-workflow-layers.md` (v7)       | ~19 files. 7 document-review agents + harden_document_agents populated. Steps 3.5/3.7 are new from v7. /brainstorm does NOT call /review --headless.                                                                 |
| 5   | **Phase 4**   | `2026-04-02-ce-plugin-phase-4-pr-comment-resolution.md`      | pr-comment-resolver agent + /resolve-pr-comments command.                                                                                                                                                            |
| 6   | **Phase 5**   | `2026-04-03-ce-plugin-phase-5-browser-testing.md`            | /test-browser command. Edits /harness:build (add Step 3) and /ship.                                                                                                                                                  |
| 7   | **Phase 6**   | `2026-04-03-ce-plugin-phase-6-compound-learning.md` (v4.3)   | /learn, compound-docs skill, learnings-researcher agent, 14 category dirs. Context Analyzer reads review-summary.md (v4.3).                                                                                          |
| 8   | **Phase 7**   | `2026-04-03-ce-plugin-phase-7-commit-workflow.md` (v4)       | /triage command. Step 2.5 must use `--headless` when invoking /review.                                                                                                                                               |
| 9   | **Phase 8**   | `2026-04-04-phase-8-backlog-system.md`                       | /Hydrate, /regenerate-backlog, /defer, BACKLOG.md rename, hydrate.sh rewrite.                                                                                                                                        |
| 10  | **Phase 8.5** | `2026-04-04-phase-8.5-structure-drift-detection.md`          | detect-structure-drift.sh. Builds on Phase 8's hydrate.sh — must come after Phase 8.                                                                                                                                 |
| 11  | **Phase 9**   | `2026-04-04-phase-9-git-worktree.md`                         | .worktreeinclude, git-worktree skill.                                                                                                                                                                                |
| 12  | **Phase 10**  | `2026-04-03-ce-plugin-phase-10-design-workflow.md`           | ~17 components. 6 design agents, design commands, /copy and /copy-review shells, skills.                                                                                                                             |
| 13  | **Phase 11**  | `2026-04-06-phase-11-skill-porting.md`                       | stripe-best-practices + react-best-practices skills ported upstream. Conditional loading in /pnf, /inf.                                                                                                              |
| 14  | **Finale**    | `2026-04-07-phase-finale-documentation-refresh.md` (v2.1)    | Full rewrites of CLAUDE.md, AGENTS.md, HOW_IT_WORKS.md, METHODOLOGY.md, skills-index.md. init-project.sh comprehensive update. CE plugin removal. **Generate from actual implemented state, not plan descriptions.** |

---

## Session 2: BuiltForm (All Phases)

### Starting Prompt

```
I'm implementing all phases (0 through 11 + 8.5 + Finale) for BuiltForm in this session, one phase at a time. All phases go on one branch: feat/ce-plugin-phases-0-finale.

Handoff: docs/plans/2026-04-07-implementation-handoff.md
Plans: docs/plans/
LaunchPad reference (already implemented): /Users/foadshafighi/dev/My Projects/LaunchPad/

For each phase:
1. Read the BuiltForm plan file
2. Reference the already-implemented LaunchPad files for full component definitions
3. Apply BuiltForm-specific adaptations (Stripe, AEC domain, copy agents, design enrichment)
4. Implement everything in the File Change Summary table
5. Run the Verification Checklist
6. Run: pnpm lint && pnpm typecheck && pnpm test
7. Commit with message: "feat: implement Phase [X] — [short description]"
8. Move to the next phase

Start with Phase 0.
```

### BuiltForm-Specific Additions Per Phase

| Phase  | BuiltForm-Specific                                                                                                                                                                                                                                                                     |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0      | Stripe secret patterns (whsec*, sk_test*, sk*live*), AEC domain context in harness.local.md, 3 design command→agent conversions noted                                                                                                                                                  |
| 1      | Same 9 agents, same agents.yml structure                                                                                                                                                                                                                                               |
| 2      | Stripe billing data onDelete checks, seed data warning, forward-only migration emphasis                                                                                                                                                                                                |
| 3      | Same 7 document-review agents, same workflow layers                                                                                                                                                                                                                                    |
| 4      | Stripe secret patterns in sensitive file denylist                                                                                                                                                                                                                                      |
| 5      | Stripe Checkout flow safety in browser tests                                                                                                                                                                                                                                           |
| 6      | Stripe-specific secret scanning in /learn                                                                                                                                                                                                                                              |
| 7      | Stripe regex in Step 2.5 re-scan, AEC PII reminder in triage                                                                                                                                                                                                                           |
| 8+8.5  | Same as LaunchPad                                                                                                                                                                                                                                                                      |
| 9      | Same as LaunchPad                                                                                                                                                                                                                                                                      |
| 10     | **3 existing design commands converted to agents** (audit-ui→design-ui-auditor, audit-responsive→design-responsive-auditor, ui-ux-architect→design-alignment-checker). Old command files deleted.                                                                                      |
| 11     | **BuiltForm's biggest divergence.** 5 copy agents (Part A already done). /copy populated with agent dispatch. review_copy_agents populated with copy-auditor. /shape-section Step 8 extended with Hormozi skills. /define-design Step 10c enrichment hook with AEC domain constraints. |
| Finale | Start with `/pull-launchpad`. Agent count ~42 across 7 namespaces. Copy agents documented. Design command→agent renames verified.                                                                                                                                                      |

---

## Critical Rules

1. **Read the plan first.** The plan is the source of truth. Don't improvise.
2. **Follow File Change Summary order.** P0 files first, then P1, then P2.
3. **Run the verification checklist** before moving to the next phase.
4. **Quality gates at each phase boundary.** `pnpm lint && pnpm typecheck && pnpm test` must be clean.
5. **One branch per repo.** All phases commit to `feat/ce-plugin-phases-0-finale`. Commit after each phase completes. Ignore per-phase branch names in the individual plan files — those were written before the single-branch decision.
6. **Don't edit files from future phases.** If a plan says "[Phase X]" as a placeholder, leave it as a placeholder.
7. **For BuiltForm:** Reference the already-implemented LaunchPad files. Copy and adapt, don't rebuild from scratch.
8. **Phase Finale must read actual files**, not plan descriptions. The rewrites reflect implemented state.

---

## Phase Plan Locations

### LaunchPad (`/Users/foadshafighi/dev/My Projects/LaunchPad/`)

```
docs/plans/launchpad_plans/2026-03-27-ce-plugin-phase-0-review-agent-config.md    (v9.1)
docs/plans/launchpad_plans/2026-03-27-ce-plugin-phase-1-review-agent-fleet.md     (v7.1)
docs/plans/launchpad_plans/2026-03-28-ce-plugin-phase-2-database-agent-chain.md   (v5)
docs/plans/launchpad_plans/2026-04-02-ce-plugin-phase-3-workflow-layers.md        (v7)
docs/plans/launchpad_plans/2026-04-02-ce-plugin-phase-4-pr-comment-resolution.md
docs/plans/launchpad_plans/2026-04-03-ce-plugin-phase-5-browser-testing.md
docs/plans/launchpad_plans/2026-04-03-ce-plugin-phase-6-compound-learning.md      (v4.3)
docs/plans/launchpad_plans/2026-04-03-ce-plugin-phase-7-commit-workflow.md        (v4)
docs/plans/launchpad_plans/2026-04-04-phase-8-backlog-system.md
docs/plans/launchpad_plans/2026-04-04-phase-8.5-structure-drift-detection.md
docs/plans/launchpad_plans/2026-04-04-phase-9-git-worktree.md
docs/plans/launchpad_plans/2026-04-03-ce-plugin-phase-10-design-workflow.md
docs/plans/launchpad_plans/2026-04-06-phase-11-skill-porting.md
docs/plans/launchpad_plans/2026-04-07-phase-finale-documentation-refresh.md       (v2.1)
```

### BuiltForm (`/Users/foadshafighi/dev/My Projects/BuiltForm/`)

```
docs/plans/2026-03-27-ce-plugin-phase-0-review-agent-config.md    (v9.1)
docs/plans/2026-03-27-ce-plugin-phase-1-review-agent-fleet.md
docs/plans/2026-03-28-ce-plugin-phase-2-database-agent-chain.md   (v5)
docs/plans/2026-04-02-ce-plugin-phase-3-workflow-layers.md
docs/plans/2026-04-02-ce-plugin-phase-4-pr-comment-resolution.md
docs/plans/2026-04-03-ce-plugin-phase-5-browser-testing.md
docs/plans/2026-04-03-ce-plugin-phase-6-compound-learning.md      (v4.1)
docs/plans/2026-04-03-ce-plugin-phase-7-commit-workflow.md        (v5)
docs/plans/2026-04-04-phase-8-backlog-system.md
docs/plans/2026-04-05-phase-8.5-structure-drift-detection.md
docs/plans/2026-04-04-phase-9-git-worktree.md
docs/plans/2026-04-06-ce-plugin-phase-10-design-workflow.md
docs/plans/2026-04-07-phase-11-copy-agents-and-skill-wiring.md
docs/plans/2026-04-07-phase-finale-documentation-refresh.md       (v2.1)
```
