# Phase 11: Skill Porting & Pipeline Wiring

**Date:** 2026-04-06
**Updated:** 2026-04-07 (v2 — expanded scope: skill wiring into /pnf + /inf, /shape-section copy skill loading pattern, /define-design enrichment hook)
**Prerequisite for:** Phase Finale (Documentation Refresh)
**Depends on:** Phase 3 (Workflow Layers — provides `/pnf`, `/shape-section`, `/harden-plan`), Phase 10 (Design Workflow Import — provides design step context)
**Branch:** `feat/skill-porting`
**Status:** Plan — partially implemented (skill files created, wiring not yet implemented)

---

## Summary

Three workstreams:

1. **Skill Porting** — Port `stripe-best-practices` and `react-best-practices` from BuiltForm to LaunchPad as upstream process skills. **Implemented.**
2. **Skill Wiring** — Wire the ported skills into `/pnf` and `/inf` so they guide planning and code writing. Wire `/shape-section` Step 8 with conditional copy skill loading pattern. **Not yet implemented.**
3. **Design Enrichment Hook** — Add `/define-design` enrichment hook that writes a `## Design Context` section to `harness.local.md`. **Not yet implemented.**

| Component                                  | Count   | Status      |
| ------------------------------------------ | ------- | ----------- |
| Skills ported                              | 2       | Implemented |
| `/pnf` conditional skill loading           | 2 edits | Plan        |
| `/inf` iteration prompt skill loading      | 1 edit  | Plan        |
| `/shape-section` Step 8 copy skill pattern | 1 edit  | Plan        |
| `/define-design` enrichment hook           | 1 edit  | Plan        |

---

## Part A: Skill Porting (Implemented)

### 1. `stripe-best-practices` (5 files)

**Source:** `.claude/skills/stripe-best-practices/` in BuiltForm
**Target:** `.claude/skills/stripe-best-practices/` in LaunchPad

| File                                  | Action  | Changes from BuiltForm                                                                                                                                        |
| ------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SKILL.md`                            | Created | Description generalized ("for SaaS billing" not "for BuiltForm's SaaS billing"). Port comment updated with `port-date: 2026-04-06` and generic monorepo note. |
| `references/integration-guide.md`     | Created | 6 BuiltForm references removed. "BuiltForm is a SaaS product" → "For SaaS products". "BuiltForm's UI" → "the app's UI". Marketplace section generalized.      |
| `references/webhook-patterns.md`      | Created | "BuiltForm's API uses Hono" → "This project's API uses Hono". `@builtform/db` import → `@repo/db`.                                                            |
| `references/prisma-billing-models.md` | Created | Verbatim copy — no BuiltForm references in source.                                                                                                            |
| `evals/eval-scenarios.md`             | Created | "BuiltForm's Pro plan" generalized to "a Pro plan".                                                                                                           |

### 2. `react-best-practices` (11 files)

**Source:** `.claude/skills/react-best-practices/` in BuiltForm
**Target:** `.claude/skills/react-best-practices/` in LaunchPad

| File                                  | Action  | Changes from BuiltForm                                                                                                                                                                                               |
| ------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SKILL.md`                            | Created | Description generalized ("for BuiltForm" removed). "BuiltForm-Specific Notes" → "Tech Stack Notes". Port comment updated. Content unchanged (React 19, Next.js 15, Tailwind v4, Prisma all match LaunchPad's stack). |
| `references/async-patterns.md`        | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/bundle-optimization.md`   | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/server-performance.md`    | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/client-fetching.md`       | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/rerender-optimization.md` | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/rendering-performance.md` | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/composition-patterns.md`  | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/js-performance.md`        | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `references/advanced-patterns.md`     | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |
| `evals/eval-scenarios.md`             | Created | Verbatim — zero BuiltForm references.                                                                                                                                                                                |

### Verification (Part A)

- [x] `stripe-best-practices` SKILL.md + 3 references + 1 eval created
- [x] `react-best-practices` SKILL.md + 9 references + 1 eval created
- [x] Zero BuiltForm/builtform/@builtform references in either skill (grep verified)
- [x] Both skills auto-detected by Claude Code (confirmed in skill list)
- [x] Tech Stack Notes in react-best-practices match LaunchPad's stack (React 19, Next.js 15, Tailwind v4, Prisma)
- [x] Port comments updated with `port-date: 2026-04-06`

---

## Part B: Skill Wiring into `/pnf` and `/inf`

### Problem

No methodology skills are loaded during plan creation (`/pnf`) or code writing (`/inf`). The design skills load during the design step, but when the AI plans implementation or writes code, it has no best-practice guidance. Plans may omit critical steps (e.g., "add Suspense boundaries") and code may violate patterns that would be caught later in review.

### Solution: Conditional Skill Loading

Follow the `responsive-design` Mode C pattern — conditional loading based on section spec content.

### B1. Wire into `/pnf` (Plan Creation — Phase 3)

**File:** `.claude/commands/pnf.md` (created in Phase 3)
**Pattern:** Same as `responsive-design` Mode C — conditional on section spec content.

Add a skill-loading gate after section spec is loaded but before plan generation:

```
Skill Loading Gate:
  - IF section spec references frontend pages/components/UI
    OR task files are in apps/web/ or packages/ui/:
    Load skill: react-best-practices
    (Ensures plan steps include Suspense boundaries, parallel fetching,
     composition patterns, bundle optimization, etc.)

  - IF section spec references payment, billing, checkout, subscription,
    Stripe, pricing, or webhook:
    Load skill: stripe-best-practices
    (Ensures plan steps include Checkout Sessions, webhook idempotency,
     Prisma billing models, dynamic payment methods, etc.)
```

The loaded skills inform the plan — implementation steps will reference specific rules (e.g., "Use `Promise.all()` for the three independent data fetches per `async-parallel` rule").

### B2. Wire into `/inf` Iteration Prompt (Code Writing — Phase 3/7)

**File:** `.claude/commands/inf.md` or the iteration prompt template (created in Phase 3)
**Pattern:** Conditional loading based on `prd.json` task content.

Add a skill-loading gate at the start of each coding iteration:

```
Skill Loading Gate:
  - IF current task touches files in apps/web/ or packages/ui/
    OR task title/description mentions React, component, page, layout:
    Load skill: react-best-practices
    (70 rules enforced during code writing — CRITICAL rules block,
     HIGH rules require justification to skip)

  - IF current task title/description mentions Stripe, payment, billing,
    checkout, subscription, webhook, or pricing:
    Load skill: stripe-best-practices
    (Checkout Sessions enforced, banned APIs rejected, webhook patterns
     applied, Prisma billing models used)
```

### Design Rationale

- **Why `/pnf` + `/inf` and not `/harden-plan` or `/review`:** Skills guide creation (planning and writing), not assessment. Review agents have their own assessment criteria. Loading methodology skills during review would create a new pattern without clear payoff — if the code was written with the skills loaded, violations should be rare.
- **Why conditional and not unconditional:** `stripe-best-practices` is irrelevant for a pure UI task. Loading it unconditionally wastes context and confuses the AI. `react-best-practices` fires on nearly every frontend task but is irrelevant for backend-only API work.
- **Why this parallels `responsive-design` Mode C:** The existing pattern for conditional skill loading in `/pnf` is Mode C of `responsive-design`. We extend the same gate mechanism with two additional conditions.

---

## Part C: `/shape-section` Copy Skill Loading Pattern

### Problem

`/shape-section` Step 8 handles copy for public-facing pages. Currently it offers to load `web-copy` directly. Downstream projects may have additional copy methodology skills (offer architecture, lead generation, monetization) that should be loaded conditionally before `web-copy` to provide strategic context.

### Solution: Conditional Strategic Skill Loading Gate

**File:** `.claude/commands/shape-section.md` (created in Phase 3)

Extend Step 8 with a conditional loading gate before the `web-copy` invocation:

```
Step 8: Web Copy (Public-Facing Pages Only)
  IF section is a public-facing page (landing, pricing, about, feature,
     product, homepage, contact/demo):

    Ask: "Would you like to create the page copy now?"

    IF yes:
      Step 8a: Strategic Context Loading (conditional)
        - IF section involves pricing, offer design, or value proposition:
          Load offer methodology skill (if available in .claude/skills/)
        - IF section involves lead generation, signup flows, or lead magnets:
          Load lead strategy skill (if available in .claude/skills/)
        - IF section involves pricing page architecture, billing, or tiers:
          Load monetization methodology skill (if available in .claude/skills/)

        Strategic skills produce blueprints that feed into web copy as
        Phase 1 context. Skip silently if no strategic skills are installed.

      Step 8b: Copy Production
        Load web-copy skill (if available in .claude/skills/)
        Execute the copy workflow using the section spec + any strategic
        blueprints as input context.
        Skip silently if no web-copy skill is installed.

    IF no:
      Add ## Copy Status: "Not yet created" to the section spec.

  IF NOT public-facing:
    Skip entirely.
```

### Design Rationale

- **LaunchPad provides the pattern, not the skills.** The copy skills (`web-copy`, `hormozi-offer`, etc.) are domain-specific and live in downstream projects. LaunchPad's `/shape-section` defines the conditional loading gates; downstream projects populate with their own skills.
- **"If available" pattern.** Skills are checked for existence before loading. A project without copy skills simply skips Step 8a/8b silently. This matches the `/copy` and `/copy-review` shell command pattern from Phase 10.
- **Strategic → Copy flow.** Offer/lead/monetization methodology produces strategic documents that `web-copy` consumes. This chain is: WHAT to sell → HOW to monetize → HOW to attract → WHAT WORDS to write.

---

## Part D: `/define-design` Enrichment Hook

### Problem

`harness.local.md` has two planned enrichment hooks (`/define-product` → `## Review Context`, `/define-architecture` → appends to `## Review Context`). No design hook exists. Design agents (`design-iterator`, `figma-design-sync`, `design-ui-auditor`, etc.) receive no project-specific design context, causing them to default to generic SaaS patterns.

### Solution: `## Design Context` Section in `harness.local.md`

**File:** `.claude/commands/define-design.md` (exists in downstream projects)

Add an enrichment hook step after the design Q&A completes (after Step 10b — Design Quality Validation, before Step 11 — Summary):

```
Step 10c: Enrich harness.local.md

  Write or update the ## Design Context section in .harness/harness.local.md:

  ## Design Context

  <!-- Enriched by /define-design. -->

  **Brand:** [primary personality] + [secondary personality]. Voice: [attributes].
  **Philosophy:** [chosen design philosophy] — [one-line description].
  **Density:** [data-dense / minimal / balanced] — [context for why].
  **Colors:** [primary hex] primary, [background approach], [dark mode strategy].
  **Typography:** [heading font] / [body font] at [base size].
  **Components:** [library choice] with [customization approach].
  **Responsive:** [strategy] — [critical breakpoints and why].
  **Accessibility:** [WCAG level target] — [chosen patterns].

  ### Domain Design Constraints
  - [Project-specific constraint extracted from Q&A]
  - [Project-specific constraint extracted from Q&A]
  - [Project-specific constraint extracted from Q&A]
```

**Values extracted from:** The Q&A answers in Steps 4-9 (DS-0 through FG-3). The hook condenses 18 Q&A answers into a compact context block that agents can consume quickly.

**Primary consumers:**

- `design-iterator` — project constraints guide improvement priorities
- `figma-design-sync` — project design decisions affect Figma interpretation
- `design-ui-auditor` — brand personality and density expectations inform UI audit
- `design-responsive-auditor` — responsive strategy and breakpoints inform responsive audit
- `design-alignment-checker` — design philosophy informs alignment checks
- `/design-review` — all 8 design dimensions contextualized to the project
- `/design-polish` — brand voice and personality guide polish decisions

### Design Rationale

- **Parallels existing hooks:** Same pattern as `/define-product` Step 6b and `/define-architecture` Step 4b.
- **Separate section header:** `## Design Context` is distinct from `## Review Context` because its consumers are different (design agents vs review agents). Review agents read `## Review Context`; design agents read `## Design Context`.
- **Generic in LaunchPad.** The hook structure and field names are project-agnostic. The `### Domain Design Constraints` section is where downstream projects add their industry-specific context (AEC for BuiltForm, healthcare for a medical app, etc.).
- **Compact format.** Each field is one line. Design agents get the full picture in ~15 lines instead of reading three 200+ line canonical files.

---

## Relationship to BuiltForm Phase 11

| Workstream                              | LaunchPad                                                           | BuiltForm                                                                                             |
| --------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Skill porting**                       | Port `stripe-best-practices` + `react-best-practices` (implemented) | Skills already exist (source)                                                                         |
| **`/pnf` + `/inf` wiring**              | Define conditional loading gates (upstream pattern)                 | Inherits from LaunchPad                                                                               |
| **`/shape-section` copy skill pattern** | Define conditional loading gates (upstream pattern)                 | Populate with `web-copy`, `hormozi-offer`, `hormozi-leads`, `hormozi-moneymodel`                      |
| **`/define-design` enrichment hook**    | Define `## Design Context` section structure (generic)              | Populate with AEC domain constraints                                                                  |
| **Copy agents**                         | N/A (LaunchPad has no copy agents)                                  | 5 agents created (copy-writer, offer-architect, leads-strategist, moneymodel-architect, copy-auditor) |
| **`/copy` + `/copy-review` population** | N/A (shell commands, empty in LaunchPad)                            | Populate with copy agent dispatch                                                                     |
| **`review_copy_agents` population**     | N/A (empty key in agents.yml)                                       | Populate with `copy-auditor`                                                                          |

---

## Deferred to Phase Finale

| Item                                                      | Phase        |
| --------------------------------------------------------- | ------------ |
| Documentation refresh for skills-catalog/skills-index.md  | Phase Finale |
| Update REPOSITORY_STRUCTURE.md with new skill directories | Phase Finale |

---

## Verification

### Part A (Implemented)

- [x] `stripe-best-practices` SKILL.md + 3 references + 1 eval created
- [x] `react-best-practices` SKILL.md + 9 references + 1 eval created
- [x] Zero BuiltForm references in either skill

### Part B (Plan)

- [ ] `/pnf` loads `react-best-practices` conditionally (frontend section specs)
- [ ] `/pnf` loads `stripe-best-practices` conditionally (billing/payment section specs)
- [ ] `/inf` iteration prompt loads `react-best-practices` conditionally (frontend tasks)
- [ ] `/inf` iteration prompt loads `stripe-best-practices` conditionally (billing/payment tasks)

### Part C (Plan)

- [ ] `/shape-section` Step 8 extended with Step 8a (strategic skill loading gate) and Step 8b (copy production)
- [ ] Conditional loading checks for skill file existence before loading
- [ ] Skip silently if no copy skills installed

### Part D (Plan)

- [ ] `/define-design` has Step 10c enrichment hook
- [ ] `## Design Context` section written to `.harness/harness.local.md`
- [ ] Fields extracted from Q&A answers: brand, philosophy, density, colors, typography, components, responsive, accessibility
- [ ] `### Domain Design Constraints` subsection present for project-specific constraints

---

## File Change Summary

| #   | File                                                                       | Action                                                          | Priority | Status      |
| --- | -------------------------------------------------------------------------- | --------------------------------------------------------------- | -------- | ----------- |
| 1   | `.claude/skills/stripe-best-practices/SKILL.md`                            | **Create**                                                      | P0       | Implemented |
| 2   | `.claude/skills/stripe-best-practices/references/integration-guide.md`     | **Create**                                                      | P0       | Implemented |
| 3   | `.claude/skills/stripe-best-practices/references/webhook-patterns.md`      | **Create**                                                      | P0       | Implemented |
| 4   | `.claude/skills/stripe-best-practices/references/prisma-billing-models.md` | **Create**                                                      | P0       | Implemented |
| 5   | `.claude/skills/stripe-best-practices/evals/eval-scenarios.md`             | **Create**                                                      | P0       | Implemented |
| 6   | `.claude/skills/react-best-practices/SKILL.md`                             | **Create**                                                      | P0       | Implemented |
| 7   | `.claude/skills/react-best-practices/references/async-patterns.md`         | **Create**                                                      | P0       | Implemented |
| 8   | `.claude/skills/react-best-practices/references/bundle-optimization.md`    | **Create**                                                      | P0       | Implemented |
| 9   | `.claude/skills/react-best-practices/references/server-performance.md`     | **Create**                                                      | P0       | Implemented |
| 10  | `.claude/skills/react-best-practices/references/client-fetching.md`        | **Create**                                                      | P0       | Implemented |
| 11  | `.claude/skills/react-best-practices/references/rerender-optimization.md`  | **Create**                                                      | P0       | Implemented |
| 12  | `.claude/skills/react-best-practices/references/rendering-performance.md`  | **Create**                                                      | P0       | Implemented |
| 13  | `.claude/skills/react-best-practices/references/composition-patterns.md`   | **Create**                                                      | P0       | Implemented |
| 14  | `.claude/skills/react-best-practices/references/js-performance.md`         | **Create**                                                      | P0       | Implemented |
| 15  | `.claude/skills/react-best-practices/references/advanced-patterns.md`      | **Create**                                                      | P0       | Implemented |
| 16  | `.claude/skills/react-best-practices/evals/eval-scenarios.md`              | **Create**                                                      | P0       | Implemented |
| 17  | `.claude/commands/pnf.md`                                                  | **Edit** (Phase 3) — add conditional skill loading gate         | P0       | Plan        |
| 18  | `.claude/commands/inf.md` (or iteration prompt)                            | **Edit** (Phase 3) — add conditional skill loading gate         | P0       | Plan        |
| 19  | `.claude/commands/shape-section.md`                                        | **Edit** (Phase 3) — extend Step 8 with strategic skill loading | P1       | Plan        |
| 20  | `.claude/commands/define-design.md`                                        | **Edit** (downstream) — add Step 10c enrichment hook            | P1       | Plan        |
