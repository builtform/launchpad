# Phase 3: Workflow Layers

**Date:** 2026-04-02
**Depends on:** Phase 0 (pipeline infrastructure), Phase 1 (review agent fleet), Phase 2 (database agent chain — soft dependency: wiring diagram references schema-drift-detector)
**Branch:** `feat/workflow-layers`
**Status:** Plan — v7 (CE v2.61.0 impact: 7 document-review agents added to `/harden-plan`, interactive deepening mode, brainstorm verification rigor)

---

## Decisions (All Finalized)

| Decision                           | Answer                                                                                                                                                                                                                                    |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Brainstorm command                 | `/brainstorm` → `.claude/commands/brainstorm.md` (flat)                                                                                                                                                                                   |
| Brainstorming skill                | `.claude/skills/brainstorming/SKILL.md` (process skill, not domain)                                                                                                                                                                       |
| Document-review skill              | `.claude/skills/document-review/SKILL.md` (process skill, not domain)                                                                                                                                                                     |
| Skills in LaunchPad                | Process/workflow skills allowed — same category as `creating-skills`                                                                                                                                                                      |
| spec-flow-analyzer agent           | `.claude/agents/review/spec-flow-analyzer.md` (review/ namespace)                                                                                                                                                                         |
| Agent model                        | `model: inherit` (per Phase 0)                                                                                                                                                                                                            |
| Repo research in brainstorm        | Dispatch `code-analyzer` + `pattern-finder` in parallel when codebase exists                                                                                                                                                              |
| Harden-plan agent source           | `agents.yml` keys (per Phase 1 — not hardcoded)                                                                                                                                                                                           |
| CE source: brainstorm              | `workflows/brainstorm.md` (129 lines) — medium adaptation                                                                                                                                                                                 |
| CE source: brainstorming skill     | `skills/brainstorming/SKILL.md` (190 lines) — light adaptation                                                                                                                                                                            |
| CE source: document-review         | `skills/document-review/SKILL.md` (87 lines) — near-direct port                                                                                                                                                                           |
| CE source: spec-flow-analyzer      | `agents/workflow/spec-flow-analyzer.md` (134 lines) — near-direct port                                                                                                                                                                    |
| CE source: deepen-plan             | NOT ported — LaunchPad's /harden-plan uses config-driven dispatch (Phase 0+1), not CE's maximalist dynamic discovery                                                                                                                      |
| Document-review agents (v7)        | 7 new agents in `.claude/agents/document-review/` namespace. Dispatched by `/harden-plan` Step 3.5 (after code-focused agents, before synthesis). All `model: inherit`. From CE v2.61.0 — entirely new category not in original analysis. |
| Document-review agent config key   | `harden_document_agents` in `.launchpad/agents.yml` — separate from `harden_plan_agents` (code-focused)                                                                                                                                   |
| Interactive deepening (v7)         | `/harden-plan --interactive` presents each agent's findings individually for accept/reject/discuss before integration. Default in `/harness:plan` context. `--auto` (unchanged) skips this.                                               |
| Brainstorm verification rigor (v7) | `/brainstorm` Phase 1 agents can read schemas/routes/configs to verify infrastructure claims. Unverified claims labeled as assumptions. Phase 3 finalization catches unverified absence claims.                                           |

---

## Purpose

Fill the two remaining gaps in the pipeline and add document-quality agents:

1. **`/harness:kickoff`** — `/brainstorm` command + `brainstorming` skill give `/harness:kickoff` its implementation
2. **`/harness:plan`** — `spec-flow-analyzer` agent completes `/harden-plan`'s code-focused agent roster; `document-review` skill provides quality checking for plan and brainstorm documents. `/harden-plan` is called by `/harness:plan` (interactive, human-in-the-loop), not `/harness:build` (autonomous).
3. **Document-review agents (v7)** — 7 new agents that give plans and specs the same multi-lens scrutiny that code gets from Phase 1 review agents. Adversarial, coherence, feasibility, scope, product, security, and design lenses. Dispatched by `/harden-plan` Step 3.5 after code-focused agents return.

After Phase 3, the pipeline has four meta-orchestrators with clear interactive/autonomous boundary:

```
/harness:kickoff → /harness:define → /harness:plan → /harness:build
  brainstorm       define+shape       design [P10]    inf → review → fix → test-browser
                                      → pnf → harden     → ship → learn → report
                                      → approve
  ^ Phase 3                           ^ Phase 3 completes harden
```

`/harness:plan` is INTERACTIVE (human-in-the-loop): plan hardening, design review, and human approval all happen here before autonomous build begins. `/harness:build` is AUTONOMOUS: no human input required once a plan is approved.

---

## Architecture: How Phase 3 Components Wire In

### `/brainstorm` Wiring

```
/harness:kickoff
  │
  ├── Step 1: Run /brainstorm (Phase 3)
  │     ├── Load brainstorming skill (Phase 3)
  │     ├── IF codebase exists: dispatch code-analyzer + pattern-finder in parallel
  │     ├── Collaborative dialogue (one question at a time)
  │     ├── Explore 2-3 approaches
  │     ├── Capture → docs/brainstorms/YYYY-MM-DD-[topic]-brainstorm.md
  │     └── Load document-review skill → offer refinement pass (max 2 passes)
  │
  └── Step 2: Handoff
        └── "Brainstorm captured. Run /harness:define to define your product."
```

`/brainstorm` is also available standalone — wired into `/harness:kickoff` but usable independently.

### `spec-flow-analyzer` Wiring

`/harden-plan` is called by `/harness:plan` (Step 4), not `/harness:build`. This places all plan review agents within the interactive orchestrator, where the human can review and approve findings before autonomous build begins.

```
/harness:plan
  │
  ├── Step 2: Design Step [Phase 10]
  │
  ├── Step 3: /pnf (plan next feature)
  │
  └── Step 4: /harden-plan (from Phase 0, updated in Phase 1)
        │
        ├── Read agents.yml → harden_plan_agents, harden_plan_conditional_agents,
        │                      harden_document_agents
        │
        ├── Step 3: Code-focused agents (ALWAYS, lightweight + full):
        │   ├── security-auditor            (Phase 1 — exists)
        │   ├── performance-auditor         (Phase 1 — exists)
        │   ├── pattern-finder              (Phase 0 — exists)
        │   └── spec-flow-analyzer          (Phase 3 — NEW, completes the roster)
        │
        ├── Step 3 CONDITIONAL (full only):
        │   ├── architecture-strategist     (Phase 1 — exists)
        │   ├── code-simplicity-reviewer    (Phase 1 — exists)
        │   ├── frontend-races-reviewer     (Phase 1 — exists)
        │   └── schema-drift-detector       (Phase 2 — exists)
        │
        ├── Step 3.5: Document-review agents (NEW — v7, all in parallel):
        │   ├── adversarial-document-reviewer   (Phase 3 — NEW)
        │   ├── coherence-reviewer              (Phase 3 — NEW)
        │   ├── feasibility-reviewer            (Phase 3 — NEW)
        │   ├── scope-guardian-reviewer         (Phase 3 — NEW)
        │   ├── product-lens-reviewer           (Phase 3 — NEW)
        │   ├── security-lens-reviewer          (Phase 3 — NEW)
        │   └── design-lens-reviewer            (Phase 3 — NEW, conditional on UI)
        │
        └── Step 3.7: Interactive Deepening (NEW — v7)
              IF --interactive (default in /harness:plan):
                Present each agent's findings one-by-one
                User: accept / reject / discuss each
                Rejected findings discarded (not written to plan)
              IF --auto: skip (auto-merge all findings as before)
```

### `document-review` Wiring

Used by two commands:

1. `/brainstorm` — post-capture refinement (Phase 4 in brainstorm flow)
2. `/harden-plan` — plan quality check before agent dispatch (within `/harness:plan`)

`document-review` runs in `/harden-plan`'s document quality pre-check, within `/harness:plan`'s interactive context.

---

## Component Definitions

### 1. `/brainstorm` Command

**File:** `.claude/commands/brainstorm.md`
**CE source:** `workflows/brainstorm.md` (129 lines) — medium adaptation
**Called by:** `/harness:kickoff` Step 1
**Also usable:** standalone

**Adaptations from CE:**

- Replace `repo-research-analyst` → dispatch `code-analyzer` + `pattern-finder` in parallel (Q3 answer)
- Replace `workflows/brainstorm` namespace → flat `/brainstorm`
- Replace `/workflows:plan` handoff → `/harness:define` (canonical handoff; `/define-product` is the first step within `/harness:define`)
- Add codebase existence check before dispatching research agents
- Load `document-review` skill for post-capture refinement
- Output to `docs/brainstorms/` (same as CE)

**Implementation note:** The `/brainstorm` command loads the `brainstorming` skill for process knowledge. The flow below summarizes key behaviors, but the skill is the source of truth for question techniques, approach templates, and anti-patterns. The command should reference the skill, not duplicate its content.

**Flow (4 phases):**

```
Phase 0: Assess Clarity
  - IF requirement is already clear and specific: skip to Phase 2
  - IF vague or exploratory: proceed to Phase 1

Phase 1: Understand the Idea
  - Load brainstorming skill (process knowledge)
  - IF codebase exists (package.json or similar detected):
    Dispatch code-analyzer + pattern-finder in parallel
    (lightweight repo scan — what exists, what patterns are established)
    VERIFICATION RIGOR (v7): Research agents MAY read schemas, routes,
    configs, and existing code to verify infrastructure claims. This
    prevents brainstorm outputs from stating "table X does not exist"
    without anyone checking. Verification of current state is always
    permitted — implementation decisions still defer to planning.
  - Collaborative dialogue:
    One question at a time
    Start broad, narrow progressively
    Cover: Purpose, Users, Constraints, Success Criteria, Edge Cases, Existing Patterns
  - Unverified claims MUST be labeled as assumptions (v7):
    "Assumption: no existing payments table" (not "there is no payments table")
  - NEVER CODE — explore and document decisions only

Phase 2: Explore Approaches
  - Present 2-3 concrete approaches
  - Each: Name, Description, Pros, Cons, "Best When"
  - Lead with recommendation
  - Apply YAGNI: simplest approach that meets requirements

Phase 3: Capture Design Document
  - BEFORE writing: scan for unverified absence claims (v7).
    Phrases like "does not exist", "no current", "there is no" that
    were not verified via code-analyzer/pattern-finder MUST be either
    verified now or relabeled as "Assumption: ..." This prevents
    downstream planning from treating unverified claims as facts.
  - Write to: docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md
  - Topic slug sanitization: lowercase, hyphens only, strip special characters,
    max 50 characters (e.g., "Stripe Billing Flow!" → "stripe-billing-flow")
  - Before writing: scan capture for PII and secrets (including but not
    limited to: email addresses, phone numbers, physical addresses,
    IP addresses, API keys, tokens, connection strings, internal URLs,
    and real customer/user data) and replace with anonymized placeholders
  - Template sections:
    ## What We're Building
    ## Why This Approach
    ## Key Decisions
    ## Open Questions
    ## Next Steps

Phase 4: Refine + Handoff
  - Load document-review skill
  - Offer refinement pass (max 2 passes, then recommend completion)
  - Handoff options:
    a) "Review and refine further" (re-enter document-review)
    b) "Proceed to planning" → "Run /harness:define"
    c) "Ask more questions" (re-enter Phase 1)
    d) "Done for now"
```

**Strict rules:**

- NEVER write code — brainstorm is about ideas, not implementation
- One question at a time — never dump 5 questions
- Always capture before handoff — no lost brainstorms
- Research agents are optional — skip if no codebase exists

**`docs/brainstorms/` commit policy:** Brainstorm documents are committed to git. The PII scrubbing step (Phase 3) ensures sensitive data is anonymized before writing. If the repository is public, consider adding `docs/brainstorms/` to `.gitignore` — brainstorms may contain architectural details about security mechanisms that should stay private.

---

### 2. `brainstorming` Skill

**File:** `.claude/skills/brainstorming/SKILL.md`
**CE source:** `skills/brainstorming/SKILL.md` (190 lines) — light adaptation

**Adaptations from CE:**

- Remove references to `workflows:plan` → replace with `/harness:define` (canonical handoff)
- Keep all process content (question techniques, YAGNI principles, anti-patterns) — framework-agnostic
- Update output path to `docs/brainstorms/` (same as CE)
- Add note about repo research agents (`code-analyzer`, `pattern-finder`) replacing `repo-research-analyst`

**Content structure (preserved from CE):**

```
1. When to Brainstorm vs Skip
   - Clear: explicit acceptance criteria, specific tech requirements → skip
   - Unclear: "make it better", "improve performance", no success criteria → brainstorm

2. Question Techniques
   - One at a time (NEVER batch)
   - Prefer multiple choice over open-ended
   - Start broad, narrow progressively
   - Validate assumptions explicitly
   - Ask about success criteria early
   - Key topics table: Purpose, Users, Constraints, Success, Edge Cases, Existing Patterns

3. Approach Exploration
   - 2-3 approaches, structured: Name, Description, Pros, Cons, "Best When"
   - Lead with recommendation
   - Apply YAGNI

4. Design Document Template
   - What, Why, Decisions, Questions, Next Steps
   - Output: docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md

5. YAGNI Principles
   - Don't design for hypothetical scale
   - Don't add config when one value works
   - Don't abstract before 3 instances
   - Don't build features nobody asked for
   - Don't over-specify implementation details

6. Anti-Patterns Table
   | Anti-Pattern | Better Approach |
   |---|---|
   | Asking 5 questions at once | Ask one at a time |
   | Jumping to solution | Understand the problem first |
   | Ignoring constraints | Ask about budget, timeline, team |
   | Skipping success criteria | Define "done" before starting |
   | Over-engineering brainstorm | It's a brainstorm, not a spec |
   | Not capturing decisions | Write it down before moving on |

7. Integration Note
   - Brainstorm = WHAT (problem space)
   - Plan = HOW (solution space)
   - When brainstorm output exists, /define-product uses it as context
```

---

### 3. `document-review` Skill

**File:** `.claude/skills/document-review/SKILL.md`
**CE source:** `skills/document-review/SKILL.md` (87 lines) — near-direct port

**Adaptations from CE:** Minimal — this skill is framework-agnostic.

- Update any CE-specific command references (if any)
- Keep the 6-step process and 2-pass recommendation intact

**Content structure (preserved from CE):**

```
1. Get the Document
   - Accept path or read from context

2. Assess (5 questions)
   - Is anything unclear or ambiguous?
   - Is anything unnecessary?
   - Is a decision being avoided?
   - Are there unstated assumptions?
   - Is there scope creep?

3. Evaluate (4 criteria)
   - Clarity: Can someone unfamiliar execute on this?
   - Completeness: Are all necessary details present?
   - Specificity: Are requirements concrete enough to implement?
   - YAGNI: Is everything here actually needed for the next step?

4. Identify the Critical Improvement
   - What single change would most improve this document?

5. Make Changes
   - Auto-fix: typos, formatting, minor ambiguities
     Log a brief summary of what was auto-fixed (e.g., "Fixed 3 typos,
     clarified ambiguous pronoun in section 2") so the user can verify
     nothing substantive was silently changed.
   - Ask approval: substantive changes (scope, requirements, approach)

6. Offer Next Action
   - "Refine again" or "Review complete"
   - After 2 passes: recommend completion (diminishing returns)

Simplification Guidance:
  SIMPLIFY when content:
    - Serves hypothetical future needs
    - Repeats information
    - Exceeds what's needed for the next step
    - Adds overhead without adding clarity
  DO NOT SIMPLIFY:
    - Constraints and limitations
    - Rationale for rejected alternatives
    - Unresolved questions
    - Integration requirements

Rules:
  - Don't rewrite the entire document
  - Don't add new sections or requirements
  - Don't over-engineer the review
  - Don't create separate review files
```

---

### 4. `spec-flow-analyzer` Agent

**File:** `.claude/agents/review/spec-flow-analyzer.md`
**CE source:** `agents/workflow/spec-flow-analyzer.md` (134 lines) — near-direct port
**Dispatched by:** `/harden-plan` (always, both intensities) — within `/harness:plan` context

**Adaptations from CE:**

- Change namespace from `workflow/` to `review/` (Phase 0 namespace decision)
- Add `model: inherit` frontmatter (per Phase 0)
- Keep all 4 phases — framework-agnostic analysis
- No Rails/Ruby references to remove (CE version is already stack-neutral)

**Frontmatter:**

```yaml
---
name: spec-flow-analyzer
description: Analyzes specifications and feature descriptions for user flow completeness, gap identification, and requirements validation.
model: inherit
---
```

**4 Analysis Phases:**

```
Phase 1: Deep Flow Analysis
  - Map every user journey end-to-end
  - Identify all decision points and branching paths
  - Document state transitions and their triggers
  - Note entry/exit points for each flow

Phase 2: Permutation Discovery
  - User types: first-time vs returning, roles, permissions
  - Device types: mobile, desktop, tablet
  - Network conditions: offline, slow, interrupted
  - Concurrent actions: multiple tabs, simultaneous edits
  - Partial completion: abandoned flows, back navigation
  - Cancellation paths: mid-flow exits, undo scenarios
  - Error recovery: what happens after each error type

Phase 3: Gap Identification (10 categories)
  1. Error handling — what happens when things fail?
  2. State management — what if state is stale or corrupted?
  3. Accessibility — screen readers, keyboard nav, color contrast
  4. Security — auth edge cases, escalation, session expiry
  5. Rate limiting — abuse scenarios, retry behavior
  6. Data validation — boundary values, empty states, max lengths
  7. Loading states — skeleton screens, spinners, optimistic UI
  8. Empty states — first use, no results, deleted data
  9. Concurrency — race conditions, stale reads, double submits
  10. Rollback — what if a multi-step process fails partway?

Phase 4: Question Formulation
  - Each question: specific, actionable, with impact assessment
  - Priority: Critical / Important / Nice-to-have
  - Include examples of what could go wrong
  - Frame as "What should happen when..." not "Did you consider..."
```

**Output format:**

```markdown
## User Flow Overview

[Visual or textual map of all user journeys]

## Flow Permutations Matrix

[Matrix of user types × device types × scenarios]

## Missing Elements & Gaps

### Critical (P1)

### Important (P2)

### Nice-to-have (P3)

## Critical Questions

[Prioritized, specific, with impact]

## Recommended Next Steps

[Ordered list of actions to close gaps]
```

**Agent reads:** Plan document + project context from `.harness/harness.local.md`. Does NOT read codebase — analyzes the plan/spec only.

**Tool restriction:** Implementation should restrict this agent to the Read tool only, scoped to the plan document path and `.harness/harness.local.md`. Deny Bash, Glob, Grep to enforce the "plan only, not codebase" constraint structurally rather than behaviorally.

---

### 5-11. Document-Review Agents (7 agents — NEW in v7)

**Directory:** `.claude/agents/document-review/`
**CE source:** CE v2.61.0 `agents/document-review/` (entirely new category — not in March 28 baseline)
**Dispatched by:** `/harden-plan` Step 3.5 (after code-focused agents, before synthesis)
**Why added (v7):** CE proved that plans and specs benefit from the same multi-agent scrutiny as code. 7 dedicated lenses catch issues that code-focused agents miss: scope creep, logical incoherence, infeasible timelines, unexamined security implications, missing product context.

**All agents share:**

- `model: inherit`
- Tool restriction: Read only (Bash/Glob/Grep denied) — same as spec-flow-analyzer
- Input: plan document + project context from `.harness/harness.local.md`
- Output: structured findings with P1/P2/P3 severity

#### 5. `adversarial-document-reviewer`

**File:** `.claude/agents/document-review/adversarial-document-reviewer.md`

```yaml
---
name: adversarial-document-reviewer
description: Challenges assumptions, finds logical flaws, and stress-tests claims in plan and specification documents.
model: inherit
---
```

**Role:** The devil's advocate. Actively tries to poke holes in the plan.

**Review protocol:**

1. **Assumption audit** — List every assumption the plan makes (explicit and implicit). For each: Is it verified? What happens if it's wrong?
2. **Logical consistency** — Check that conclusions follow from premises. Flag circular reasoning, false dichotomies, unstated dependencies.
3. **Failure mode analysis** — For each proposed step: What's the worst thing that could happen? Is the fallback plan adequate?
4. **"What if" scenarios** — Generate 3-5 scenarios the plan doesn't account for. Assess impact of each.
5. **Overconfidence detection** — Flag claims stated as facts without evidence ("this will take 2 days", "users will prefer X").

**Output:** Assumptions table (verified/unverified), logical issues, failure modes, scenario gaps.

#### 6. `coherence-reviewer`

**File:** `.claude/agents/document-review/coherence-reviewer.md`

```yaml
---
name: coherence-reviewer
description: Checks document consistency, flow, and internal agreement across sections of plans and specifications.
model: inherit
---
```

**Role:** Ensures the document doesn't contradict itself.

**Review protocol:**

1. **Cross-section consistency** — Check that scope section, requirements, technical approach, and timeline all agree. Flag contradictions.
2. **Terminology consistency** — Flag terms used inconsistently (same concept, different names — or same name, different meanings).
3. **Flow logic** — Steps should follow logically. Dependencies should be satisfied before dependent steps.
4. **Completeness mapping** — Every requirement mentioned in scope should have a corresponding technical approach. Every technical decision should trace to a requirement.
5. **Priority alignment** — If P1 requirements have less detail than P3 requirements, flag the imbalance.

**Output:** Contradiction list, terminology inconsistencies, flow gaps, completeness matrix.

#### 7. `feasibility-reviewer`

**File:** `.claude/agents/document-review/feasibility-reviewer.md`

```yaml
---
name: feasibility-reviewer
description: Assesses technical feasibility of proposed plans against the project's actual stack, constraints, and current state.
model: inherit
---
```

**Role:** Catches plans that sound good but can't actually be built.

**Review protocol:**

1. **Stack compatibility** — Does the plan use technologies that exist in the project? Does it assume APIs/features that don't exist yet?
2. **Dependency feasibility** — Are third-party dependencies available, maintained, and compatible with the project's versions?
3. **Complexity assessment** — Is the proposed approach proportional to the problem? Flag over-engineering and under-engineering.
4. **Constraint satisfaction** — Does the plan satisfy stated constraints (performance, security, budget, timeline)?
5. **Integration points** — Where does the proposed work connect to existing code? Are those integration points stable?

**Output:** Feasibility assessment per major component, risk-rated integration points, alternative approaches for infeasible items.

#### 8. `scope-guardian-reviewer`

**File:** `.claude/agents/document-review/scope-guardian-reviewer.md`

```yaml
---
name: scope-guardian-reviewer
description: Guards against scope creep in requirements and plans by enforcing boundaries between what's needed now and what can wait.
model: inherit
---
```

**Role:** The YAGNI enforcer for documents.

**Review protocol:**

1. **Scope boundary check** — Is everything in the plan necessary for the stated goal? Flag items that are nice-to-have disguised as requirements.
2. **Feature creep detection** — Look for "while we're at it" additions, gold-plating, and premature optimization.
3. **Phase-appropriate scope** — Is the scope appropriate for a single implementation cycle? Flag plans that try to do too much at once.
4. **Deferral recommendations** — For each out-of-scope item, suggest explicit deferral with rationale.
5. **MVP check** — Could this plan be split into a smaller first delivery? What's the minimum that delivers value?

**Output:** In-scope items (confirmed), out-of-scope items (with deferral recommendation), MVP boundary suggestion.

#### 9. `product-lens-reviewer`

**File:** `.claude/agents/document-review/product-lens-reviewer.md`

```yaml
---
name: product-lens-reviewer
description: Reviews plans from a product strategy perspective — user value, market fit, and strategic consequences of technical decisions.
model: inherit
---
```

**Role:** Ensures the plan serves users, not just developers.

**Review protocol:**

1. **User value mapping** — Does every proposed feature/change trace to a user need? Flag technically interesting work with no user benefit.
2. **User journey impact** — How does this plan affect existing user workflows? Are there breaking changes?
3. **Strategic alignment** — Does the plan advance the product's stated goals (from PRD, product context)?
4. **Trade-off visibility** — Are trade-offs made explicit? Does the plan acknowledge what it's giving up?
5. **Success metrics** — Are there measurable success criteria? How will we know if this worked?

**Output:** Value map, user impact assessment, strategic alignment check, missing success criteria.

#### 10. `security-lens-reviewer`

**File:** `.claude/agents/document-review/security-lens-reviewer.md`

```yaml
---
name: security-lens-reviewer
description: Reviews plans and specifications for security implications, threat surface expansion, and missing security requirements.
model: inherit
---
```

**Role:** Catches security implications before code is written (cheaper to fix in the plan than in the PR).

**Review protocol:**

1. **Threat surface assessment** — Does this plan expand the attack surface? New endpoints, new data flows, new user inputs?
2. **Data flow analysis** — Where does sensitive data go? Are there new paths for PII, credentials, or tokens?
3. **Authentication/authorization impact** — Does this change who can access what? Are new permissions needed?
4. **Third-party risk** — Does the plan introduce new external dependencies or API integrations? What's the trust model?
5. **Missing security requirements** — Are there security requirements that should be explicit but aren't? (e.g., "store user data" without specifying encryption)

**Output:** Threat surface delta, data flow concerns, auth impact, missing security requirements.

#### 11. `design-lens-reviewer`

**File:** `.claude/agents/document-review/design-lens-reviewer.md`

```yaml
---
name: design-lens-reviewer
description: Reviews plans from a design/UX perspective — user experience implications, interaction patterns, and visual consistency.
model: inherit
---
```

**Role:** Catches UX issues before they become code.

**Dispatch condition:** Only dispatched when section has UI components (same condition as Phase 10 design step). When section status = `"design:skipped"`, this agent is skipped.

**Review protocol:**

1. **UX flow coherence** — Does the proposed UI flow make sense from a user's perspective? Are there dead ends or confusing transitions?
2. **Interaction pattern consistency** — Are proposed interactions consistent with the design system and existing app patterns?
3. **Accessibility planning** — Does the plan account for keyboard navigation, screen readers, color contrast, focus management?
4. **Responsive implications** — Does the plan address mobile/tablet/desktop? Are there responsive concerns not mentioned?
5. **Missing UI states** — Are loading, error, empty, and success states specified? Are edge cases covered (long text, missing images)?

**Output:** UX flow issues, pattern consistency check, accessibility gaps, responsive concerns, missing states.

---

## Changes to Existing Files

### 1. Update `.launchpad/agents.yml`

Add `spec-flow-analyzer` to `harden_plan_agents` and add new `harden_document_agents` key:

```yaml
harden_plan_agents:
  - pattern-finder
  - security-auditor
  - performance-auditor
  - spec-flow-analyzer # Added in Phase 3

# Document-review agents — dispatched by /harden-plan Step 3.5
# These review the plan DOCUMENT (not code) with multiple lenses
harden_document_agents: # Added in Phase 3 v7
  - adversarial-document-reviewer
  - coherence-reviewer
  - feasibility-reviewer
  - scope-guardian-reviewer
  - product-lens-reviewer
  - security-lens-reviewer
  # - design-lens-reviewer          # Conditional: only when section has UI
```

Note: `spec-flow-analyzer` and the 7 document-review agents are plan review agents, NOT code review agents. They do not go in `review_agents`. The distinction: `harden_plan_agents` analyze the plan for technical gaps (code-focused lens). `harden_document_agents` analyze the plan as a document for quality issues (document-focused lens).

### 2. Update `/harden-plan` command

`/harden-plan` is called by `/harness:plan` Step 4 (interactive orchestrator), not `/harness:build` (autonomous). This is significant for the `document-review` integration: the human is already in the loop during `/harness:plan`, so asking approval for substantive changes is natural rather than disruptive.

Move idempotency check earlier and add three new steps (document quality pre-check, learnings scan, Context7 enrichment):

```
Step 1: Read .launchpad/agents.yml → extract harden_plan_agents, harden_plan_conditional_agents
        Read .harness/harness.local.md (project context)

Step 1.5: Idempotency check — IF "## Hardening Notes" exists → skip
        (Renumbered from Phase 0's Step 2 to make room for new steps.
        Moved before document quality pre-check to avoid wasting a skill
        load + assessment on already-hardened plans.)

Step 2: Document Quality Pre-Check (NEW — Phase 3)
        Load document-review skill
        Fast-path: if initial scan finds no critical clarity issues
        (ambiguity, missing scope, contradictions), skip immediately.
        Only run full 5-question assessment when a red flag is detected.
        IF critical clarity issues found:
          Auto-fix minor issues (log what changed)
          Ask approval for substantive issues
          IF user declines a suggestion: discard silently (do not write
          to observations — document-review suggestions are advisory,
          not findings that need tracking)
          Re-read plan after fixes
        This prevents dispatching 4-8 agents against a plan that has
        fundamental clarity problems — fix the document first.

Step 2.5: Learnings Scan (NEW — Phase 3, dormant until Phase 6)
        [Runs in parallel with Step 2.7 — both feed into Step 3 as
        supplementary context. Neither modifies state the other reads.
        Up to 30s wall-clock savings.]
        Scan docs/solutions/ for past learnings relevant to this plan
        Match by: tags, category, module in YAML frontmatter
        Skip files with malformed or missing frontmatter (do not fail the step)
        IF docs/solutions/ empty or missing: skip silently (no-op until Phase 6)
        IF matches found: pass at most 5 most-recent matches (by file date
        prefix), extracting key insight only (not full document). This bounds
        context growth and prevents overwhelming agent context windows.
        This ensures past mistakes and discoveries inform plan review.

Step 2.7: Context7 Technology Enrichment (NEW — Phase 3)
        [Runs in parallel with Step 2.5 — see note above.]
        Parse plan for technology references (frameworks, libraries, APIs)
        Query Context7 MCP for current documentation — ALL queries run
        IN PARALLEL (not sequential). Each query requires resolve-library-id
        then query-docs; batch all resolve calls concurrently, then batch
        all query-docs calls concurrently.
        Focus on: breaking changes, deprecated APIs, version-specific gotchas
        Collect insights → pass to agents as supplementary context
        IF Context7 MCP unavailable: skip silently (graceful degradation)
        Per-query timeout: 10 seconds. Total step timeout: 30 seconds.
        If any individual query times out, skip that technology and proceed.
        Partial failures do NOT block agent dispatch — use whatever succeeded.
        IMPORTANT: Context7 queries MUST contain only library/framework
        names and version numbers. NEVER include plan content, business
        logic, feature descriptions, or project-specific details in queries.
        Before sending queries, verify each contains only recognized library
        names + version numbers (no natural language sentences, no business
        logic, no feature descriptions).
        Good: "Next.js 15", "Prisma 6.3", "Tailwind CSS v4"
        Bad:  "How to set up Prisma migrations for our billing schema",
              "Next.js authentication middleware for user dashboard"
        This catches outdated API assumptions before they reach implementation.

Step 3: Dispatch code-focused agents in parallel (renumbered from old Step 3)
        Read harden_plan_agents + harden_plan_conditional_agents from agents.yml
        All dispatched in parallel with plan + project context + learnings + Context7 enrichment

Step 3.5: Dispatch document-review agents in parallel (NEW — Phase 3 v7)
        Read harden_document_agents from agents.yml
        All dispatched in parallel with plan document + project context
        design-lens-reviewer: ONLY dispatched when section has UI components
        (same condition as Phase 10 design step — skip when "design:skipped")
        Runs AFTER Step 3 code-focused agents complete, so document reviewers
        can reference code-focused findings in their analysis.

Step 3.7: Interactive Deepening (NEW — Phase 3 v7)
        IF --interactive (default when called from /harness:plan):
          Collect all findings from Step 3 + Step 3.5
          Present each agent's findings one-by-one, grouped by agent
          For each set: "Accept / Reject / Discuss?"
          - Accept: integrate into Hardening Notes
          - Reject: discard (not written anywhere — advisory only)
          - Discuss: open dialogue, then re-present for accept/reject
          This gives the human control over what goes into the plan
          without requiring them to sort through auto-merged output.
        IF --auto: skip interactive deepening, auto-merge all findings

Step 4: Synthesize → append "## Hardening Notes" (renumbered from old Step 4/5)
...rest unchanged...
```

### 3. Update `/harness:kickoff` meta-orchestrator

Currently the Phase 0 spec says:

```
/harness:kickoff
  ├── Load brainstorming skill
  ├── Open-ended dialogue → docs/brainstorms/YYYY-MM-DD-[project].md
  └── "Run /harness:define to define your product."
```

Phase 3 replaces this with:

```
/harness:kickoff
  ├── Step 1: Run /brainstorm
  │     (brainstorm command handles skill loading, research, capture, refinement)
  └── Step 2: Handoff (same as before)
```

`/harness:kickoff` becomes a thin wrapper around `/brainstorm` + handoff message. This is cleaner than inlining brainstorm logic in the orchestrator — `/brainstorm` is independently usable.

Note: This supersedes the `/harness:kickoff` flow in the meta-orchestrators design doc (v4), which described inline brainstorm logic. The design doc has been updated to reflect delegation.

### 4. Update `init-project.sh`

Update the default `.launchpad/agents.yml` template:

- Add `spec-flow-analyzer` to `harden_plan_agents`

Add `docs/brainstorms/` directory scaffold:

- Create `docs/brainstorms/.gitkeep`
- `/brainstorm` command also runs `mkdir -p docs/brainstorms/` before writing (runtime safety net)

### 5. Update `docs/skills-catalog/skills-index.md`

Add entries for `brainstorming` and `document-review` skills with:

- Name, description, loaded-by, category (workflow/process)

### 6. Update `CLAUDE.md`

Add `brainstorming` and `document-review` to any skill reference tables (if they exist in the progressive disclosure table or elsewhere).

---

## What NOT to Port from CE's `deepen-plan`

CE's `deepen-plan` (546 lines) uses maximalist dynamic discovery — scanning ALL agent directories, ALL skill directories, ALL plugin directories, and running 30-40+ agents/skills in parallel against a plan. LaunchPad's `/harden-plan` deliberately uses config-driven dispatch from `agents.yml` keys (decided in Phase 1).

**Specifically NOT ported:**

- Dynamic skill discovery (scanning all `.claude/skills/` directories)
- Dynamic agent discovery (scanning all `.claude/agents/` directories)
- "Run everything, filter nothing" philosophy

**Selectively ported (targeted, not maximalist):**

- Learnings scan from `docs/solutions/` — added as Step 2.5 (dormant until Phase 6 populates the directory)
- Context7 technology enrichment — added as Step 2.7 (queries specific technologies mentioned in plan, not blanket discovery)

**Why:** Config-driven dispatch is more predictable, auditable, and cost-efficient. Users curate their agent roster in `agents.yml` rather than running every agent on every plan. The learnings scan and Context7 enrichment are targeted lookups, not maximalist discovery — they enrich agent context without expanding the agent roster.

---

## Verification Checklist

### Files Created

- [ ] `.claude/commands/brainstorm.md` — loads brainstorming skill, dispatches research agents when codebase exists, captures to `docs/brainstorms/`, loads document-review for refinement
- [ ] `.claude/skills/brainstorming/SKILL.md` — question techniques, YAGNI, anti-patterns, design doc template
- [ ] `.claude/skills/document-review/SKILL.md` — 6-step assessment, 4 criteria, 2-pass recommendation
- [ ] `.claude/agents/review/spec-flow-analyzer.md` — `model: inherit`, 4 phases, 10 gap categories
- [ ] `.claude/agents/document-review/adversarial-document-reviewer.md` — `model: inherit`, assumption audit, failure modes (v7)
- [ ] `.claude/agents/document-review/coherence-reviewer.md` — `model: inherit`, cross-section consistency, terminology (v7)
- [ ] `.claude/agents/document-review/feasibility-reviewer.md` — `model: inherit`, stack compatibility, complexity (v7)
- [ ] `.claude/agents/document-review/scope-guardian-reviewer.md` — `model: inherit`, YAGNI enforcement, MVP check (v7)
- [ ] `.claude/agents/document-review/product-lens-reviewer.md` — `model: inherit`, user value, strategy (v7)
- [ ] `.claude/agents/document-review/security-lens-reviewer.md` — `model: inherit`, threat surface, data flow (v7)
- [ ] `.claude/agents/document-review/design-lens-reviewer.md` — `model: inherit`, UX flow, accessibility (v7, conditional on UI)

### Wiring

- [ ] `/harness:kickoff` calls `/brainstorm` (not inlining brainstorm logic)
- [ ] `/brainstorm` loads `brainstorming` skill
- [ ] `/brainstorm` loads `document-review` skill for post-capture refinement
- [ ] `/brainstorm` dispatches `code-analyzer` + `pattern-finder` when codebase exists
- [ ] `/brainstorm` outputs to `docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md`
- [ ] `/brainstorm` handoff mentions `/harness:define` as canonical next step
- [ ] `/harden-plan` called by `/harness:plan` Step 4 (NOT `/harness:build`)
- [ ] `/harden-plan` loads `document-review` skill as document quality pre-check (within `/harness:plan` interactive context)
- [ ] `spec-flow-analyzer` dispatched by `/harden-plan` (always, both intensities) within `/harness:plan`
- [ ] `spec-flow-analyzer` listed in `agents.yml` `harden_plan_agents` (present and active)
- [ ] All 7 document-review agents listed in `agents.yml` `harden_document_agents` key (v7)
- [ ] `design-lens-reviewer` commented out in `harden_document_agents` (conditional on UI — dispatched dynamically)
- [ ] `/harden-plan` Step 3.5 dispatches document-review agents after code-focused agents return (v7)
- [ ] `/harden-plan` Step 3.5 skips `design-lens-reviewer` when section status = `"design:skipped"` (v7)
- [ ] `/harden-plan` Step 3.7 interactive deepening works: accept/reject/discuss per agent (v7)
- [ ] `/harden-plan --interactive` is default when called from `/harness:plan` (v7)
- [ ] `/harden-plan --auto` skips interactive deepening (unchanged behavior) (v7)
- [ ] No component is exclusively standalone — all wired into pipeline (standalone use additionally supported for `/brainstorm`)

### Agent Behavior

- [ ] `spec-flow-analyzer` produces structured output (flow map, permutations, gaps, questions)
- [ ] `spec-flow-analyzer` covers all 10 gap categories
- [ ] `spec-flow-analyzer` reads plan + project context only (not codebase)
- [ ] `spec-flow-analyzer` restricted to Read tool only (Bash/Glob/Grep denied)
- [ ] `spec-flow-analyzer` does NOT reference Rails, Ruby, ActiveRecord, or CE-specific patterns
- [ ] `spec-flow-analyzer` operates within `/harness:plan` context (findings surface during interactive review, not autonomous build)
- [ ] All 7 document-review agents restricted to Read tool only (same as spec-flow-analyzer) (v7)
- [ ] All 7 document-review agents produce P1/P2/P3 findings with structured output (v7)
- [ ] `adversarial-document-reviewer` lists assumptions as verified/unverified (v7)
- [ ] `coherence-reviewer` produces contradiction list and completeness matrix (v7)
- [ ] `feasibility-reviewer` assesses stack compatibility against actual project (v7)
- [ ] `scope-guardian-reviewer` distinguishes in-scope vs out-of-scope with deferral recommendations (v7)
- [ ] `design-lens-reviewer` only dispatched when section has UI components (v7)
- [ ] All P1/P2/P3 findings are specific and actionable

### Skill Behavior

- [ ] `brainstorming` skill enforces one-question-at-a-time
- [ ] `brainstorming` skill includes YAGNI principles
- [ ] `brainstorming` skill includes anti-patterns table
- [ ] `brainstorming` skill references correct handoff commands
- [ ] `document-review` skill uses 6-step process
- [ ] `document-review` skill recommends completion after 2 passes
- [ ] `document-review` skill distinguishes auto-fix vs ask-approval changes
- [ ] `document-review` skill logs a summary of auto-fixes (audit trail)
- [ ] `document-review` interactive approval naturally fits `/harness:plan`'s human-in-the-loop context
- [ ] `/harden-plan` Step 2 silently discards declined suggestions (not written to observations)

### Command Behavior

- [ ] `/brainstorm` never writes code — brainstorm only
- [ ] `/brainstorm` asks one question at a time
- [ ] `/brainstorm` always captures before handoff
- [ ] `/brainstorm` skips research agents when no codebase exists
- [ ] `/brainstorm` research agents can verify infrastructure claims by reading schemas/routes/configs (v7)
- [ ] `/brainstorm` labels unverified claims as "Assumption: ..." (v7)
- [ ] `/brainstorm` Phase 3 catches unverified absence claims before writing (v7)
- [ ] `/brainstorm` offers 4 handoff options (refine, plan, ask, done)
- [ ] `/brainstorm` scans capture for PII before writing to docs/brainstorms/
- [ ] `/brainstorm` sanitizes topic slug (lowercase, hyphens, no special chars, max 50 chars)
- [ ] `/brainstorm` runs `mkdir -p docs/brainstorms/` before writing
- [ ] `/harden-plan` operates within `/harness:plan` (interactive) — all steps below happen in human-in-the-loop context
- [ ] `/harden-plan` idempotency check (Step 1.5) runs BEFORE document quality pre-check (Step 2)
- [ ] `/harden-plan` Step 2 uses fast-path exit when no critical clarity issues detected
- [ ] `/harden-plan` Step 2 auto-fixes minor issues, asks for substantive ones (natural in `/harness:plan`'s interactive context)
- [ ] `/harden-plan` Step 2.5 scans `docs/solutions/` for relevant learnings
- [ ] `/harden-plan` Step 2.5 skips silently when `docs/solutions/` is empty or missing
- [ ] `/harden-plan` Step 2.5 matches learnings by frontmatter tags/category/module
- [ ] `/harden-plan` Step 2.5 caps at 5 most-recent matches (key insight only, not full docs)
- [ ] `/harden-plan` Step 2.5 skips files with malformed or missing frontmatter
- [ ] `/harden-plan` Step 2.7 queries Context7 for technologies mentioned in plan
- [ ] `/harden-plan` Step 2.7 runs all Context7 queries IN PARALLEL (not sequential)
- [ ] `/harden-plan` Step 2.7 queries contain only library names/versions (no plan content or business logic)
- [ ] `/harden-plan` Step 2.7 skips silently when Context7 MCP unavailable
- [ ] `/harden-plan` Step 2.7 passes enrichment as supplementary context to agents

### Prerequisites (from prior phases)

- [ ] Phase 0: `.claude/commands/harness/kickoff.md` exists
- [ ] Phase 0: `review_code.md` deleted, `/review` exists
- [ ] Phase 0: `.harness/` directory structure exists

### Integration

- [ ] `init-project.sh` updated with `spec-flow-analyzer` added to `agents.yml` template
- [ ] `init-project.sh` creates `docs/brainstorms/.gitkeep`
- [ ] `skills-index.md` updated with 2 new skills
- [ ] CLAUDE.md updated if skill references exist
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test` all pass

---

## What This Does NOT Include

| Deferred To  | What                                                                                                                          |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| Phase 4      | PR comment resolution (`/resolve-pr-comments`)                                                                                |
| Phase 6      | Compound learning system — populates `docs/solutions/` (Step 2.5 wiring exists but is dormant)                                |
| Phase 7      | `/commit` workflow wiring                                                                                                     |
| Phase 10     | Design step in `/harness:plan` (between `shaped` and `planned` statuses — 6 agents + 5 skills + 6 commands + pipeline wiring) |
| Phase Finale | Documentation refresh for all skill/agent tables                                                                              |
| Phase Finale | CE plugin removal                                                                                                             |

---

## File Change Summary

| #   | File                                                              | Change                                                                                                                                                                                                                    | Priority |
| --- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| 1   | `.claude/commands/brainstorm.md`                                  | **Create** (adapted from CE)                                                                                                                                                                                              | P0       |
| 2   | `.claude/skills/brainstorming/SKILL.md`                           | **Create** (light adaptation from CE)                                                                                                                                                                                     | P0       |
| 3   | `.claude/skills/document-review/SKILL.md`                         | **Create** (near-direct port from CE)                                                                                                                                                                                     | P0       |
| 4   | `.claude/agents/review/spec-flow-analyzer.md`                     | **Create** (near-direct port from CE)                                                                                                                                                                                     | P0       |
| 5   | `.claude/agents/document-review/adversarial-document-reviewer.md` | **Create** (v7 — from CE v2.61.0)                                                                                                                                                                                         | P0       |
| 6   | `.claude/agents/document-review/coherence-reviewer.md`            | **Create** (v7)                                                                                                                                                                                                           | P0       |
| 7   | `.claude/agents/document-review/feasibility-reviewer.md`          | **Create** (v7)                                                                                                                                                                                                           | P0       |
| 8   | `.claude/agents/document-review/scope-guardian-reviewer.md`       | **Create** (v7)                                                                                                                                                                                                           | P0       |
| 9   | `.claude/agents/document-review/product-lens-reviewer.md`         | **Create** (v7)                                                                                                                                                                                                           | P0       |
| 10  | `.claude/agents/document-review/security-lens-reviewer.md`        | **Create** (v7)                                                                                                                                                                                                           | P0       |
| 11  | `.claude/agents/document-review/design-lens-reviewer.md`          | **Create** (v7, conditional on UI)                                                                                                                                                                                        | P0       |
| 12  | `.launchpad/agents.yml`                                           | **Edit** — add spec-flow-analyzer to harden_plan_agents + add harden_document_agents key with 7 agents                                                                                                                    | P0       |
| 13  | `.claude/commands/harden-plan.md`                                 | **Edit** — move idempotency earlier, add Steps 2 (document-review), 2.5 (learnings scan), 2.7 (Context7 enrichment), 3.5 (document-review agents), 3.7 (interactive deepening)                                            | P0       |
| 14  | `.claude/commands/brainstorm.md`                                  | **Note** — already created above; v7 adds verification rigor + assumption labeling to Phase 1                                                                                                                             | P0       |
| 15  | `.claude/commands/harness/kickoff.md`                             | **Edit** — delegate to /brainstorm instead of inlining                                                                                                                                                                    | P1       |
| 16  | `scripts/setup/init-project.sh`                                   | **Edit** — update agents.yml template (add harden_document_agents key)                                                                                                                                                    | P1       |
| 17  | `docs/skills-catalog/skills-index.md`                             | **Edit** — add 2 new skills                                                                                                                                                                                               | P1       |
| 18  | `docs/reports/2026-03-30-meta-orchestrators-design.md`            | **Edit** — update /harness:kickoff flow (delegation), /harden-plan flow (new steps including 3.5 + 3.7, now in /harness:plan), 4-orchestrator pipeline diagram, agents.yml example (harden keys + harden_document_agents) | P1       |
| 19  | `CLAUDE.md`                                                       | **Edit** — add skill references + document-review agent namespace                                                                                                                                                         | P2       |
