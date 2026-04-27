# LaunchPad Skills Index

A user-facing reference for all 17 installed skills in LaunchPad. Each skill is a reusable workflow that Claude Code executes when triggered by a slash command, agent, or natural language.

---

## Quick Reference

### Process Skills

Skills loaded by workflow commands during planning, execution, and shipping.

| #   | Skill                              | Category | Description                                                                                                                   | Loaded By                                                             |
| --- | ---------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 1   | **brainstorming**                  | Process  | Structured brainstorming sessions with progressive questioning                                                                | `/lp-brainstorm`, `/lp-kickoff`                                       |
| 2   | **commit**                         | Process  | Commit workflow with quality gates, staging, and optional PR creation                                                         | `/lp-commit`, `/lp-ship`                                              |
| 3   | **compound-docs**                  | Process  | Structured problem documentation (14 categories, YAML schema)                                                                 | `/lp-learn`                                                           |
| 4   | **creating-agents**                | Process  | Agent creation methodology (8-section body, 5-tier tool assignment)                                                           | `/lp-create-agent`, natural language                                  |
| 5   | **creating-skills**                | Process  | Skill creation methodology (7-phase Meta-Skill Forge)                                                                         | `/lp-create-skill`, `/lp-update-skill`, `/lp-port-skill`              |
| 6   | **document-review**                | Process  | Plan document review (6-step assessment, 4 criteria, 2-pass)                                                                  | `/lp-brainstorm`, `/lp-harden-plan`                                   |
| 7   | **prd**                            | Process  | Product Requirements Document generation from feature descriptions                                                            | `/lp-define-product`                                                  |
| 8   | **step-zero**                      | Process  | Shared prerequisite-and-capability check (Full + Lite modes); composed by every harness and L2 command before main logic runs | `/lp-kickoff`, `/lp-define`, `/lp-plan`, `/lp-build`, all L2 commands |
| 9   | **tasks**                          | Process  | PRD markdown to `prd.json` conversion for compound execution loop                                                             | `/lp-pnf`, `/lp-inf`                                                  |
| 10  | **verification-before-completion** | Process  | Evidence-before-claims enforcement; refuses completion claims without fresh test/typecheck/lint output                        | auto-trigger on completion-claim phrasing across commands             |

### Design Skills

Skills loaded by design workflow commands to enforce visual quality and responsiveness.

| #   | Skill                     | Category | Description                                                            | Loaded By                                           |
| --- | ------------------------- | -------- | ---------------------------------------------------------------------- | --------------------------------------------------- |
| 11  | **frontend-design**       | Design   | Creative direction, anti-AI-slop, bold aesthetic (+ 7 reference files) | `/lp-inf`, design agents                            |
| 12  | **web-design-guidelines** | Design   | Engineering compliance checklist (MUST/SHOULD/NEVER rules)             | `/lp-inf`, design agents                            |
| 13  | **responsive-design**     | Design   | Spec-layer responsive thinking (3 modes: A/B/C)                        | `/lp-shape-section`, `/lp-define-design`, `/lp-pnf` |

### Methodology Skills

Domain-specific best-practice rulesets loaded conditionally by planning and implementation commands.

| #   | Skill                     | Category    | Description                                                          | Loaded By                          |
| --- | ------------------------- | ----------- | -------------------------------------------------------------------- | ---------------------------------- |
| 14  | **react-best-practices**  | Methodology | React/Next.js patterns (70 rules, 9 categories, + 9 reference files) | `/lp-pnf`, `/lp-inf` (conditional) |
| 15  | **stripe-best-practices** | Methodology | Stripe integration patterns (+ 3 reference files + 1 eval)           | `/lp-pnf`, `/lp-inf` (conditional) |

### Utility Skills

Standalone tools loaded by specific commands for file management and media workflows.

| #   | Skill      | Category | Description                                      | Loaded By           |
| --- | ---------- | -------- | ------------------------------------------------ | ------------------- |
| 16  | **rclone** | Utility  | Cloud file management (S3, R2, B2, GDrive, etc.) | `/lp-feature-video` |
| 17  | **imgup**  | Utility  | Lightweight image hosting for quick sharing      | `/lp-feature-video` |

---

## Detailed Descriptions

### Process Skills

#### 1. brainstorming

Guides collaborative idea exploration through progressive questioning, approach comparison, and design document capture. Supports both interactive dialogue and structured output modes.

- **Key Outputs:** Design documents, approach comparisons
- **Loaded By:** `/lp-brainstorm`, `/lp-kickoff`
- **Interconnections:** Feeds into `/lp-define` pipeline. Output reviewed by `document-review` skill.

#### 2. commit

Runs the full commit pipeline: branch validation, staging, parallel quality gates (tests, linting, type checks, pre-commit hooks), conventional commit message generation, and optional PR creation with CI monitoring.

- **Key Outputs:** Git commits, optional GitHub PRs
- **Loaded By:** `/lp-commit`, `/lp-ship`
- **Interconnections:** Standalone workflow. Enforces quality gates before any commit.

#### 3. compound-docs

Structured problem documentation with a 14-category taxonomy, YAML schema, and resolution templates. Captures learnings from resolved problems into `docs/solutions/` for future reference.

- **Key Outputs:** `docs/solutions/<category>/<topic>.md`
- **Loaded By:** `/lp-learn`
- **Interconnections:** Uses 5-agent parallel research pipeline. Output indexed for future retrieval by `docs-locator` agent.

#### 4. creating-agents

Creates new Claude Code agents or converts existing skills into agents. Produces production-grade agent definitions with 8-section body structure, least-privilege tool assignment via 5-tier system, and registration in CLAUDE.md/AGENTS.md.

- **Key Outputs:** `.claude/agents/[namespace/]<name>.md`, updates to `CLAUDE.md` and `AGENTS.md`
- **Loaded By:** `/lp-create-agent` (wrapper command that detects mode and delegates)
- **Interconnections:** Uses `pattern-finder` sub-agent. Companion to `creating-skills` -- skills orchestrate, agents execute.

#### 5. creating-skills

Creates new Claude Code skills using the 7-phase Meta-Skill Forge methodology. Includes research waves, targeted extraction rounds, contrarian analysis, architecture decisions, writing, quality validation, and shipping.

- **Key Outputs:** `.claude/skills/<name>/SKILL.md`, reference files in `references/`, eval scenarios in `evals/`
- **Loaded By:** `/lp-create-skill`, `/lp-update-skill`, `/lp-port-skill`
- **Interconnections:** Uses `pattern-finder`, `docs-locator`, `file-locator`, `code-analyzer`, `docs-analyzer`, `web-researcher`, and `skill-evaluator` sub-agents.

#### 6. document-review

Reviews and refines brainstorm or plan documents through a 6-step assessment with 4 quality criteria and a 2-pass recommendation system. Ensures documents meet quality bar before advancing in the pipeline.

- **Key Outputs:** Review findings, improvement recommendations
- **Loaded By:** `/lp-brainstorm`, `/lp-harden-plan`
- **Interconnections:** Consumes output from `brainstorming` and `prd` skills. Gates advancement to planning phase.

#### 7. prd

Generates Product Requirements Documents from a feature description. Supports interactive (MCQ questions) and autonomous (piped input) modes. Includes codebase research, self-clarification, and structured PRD output.

- **Key Outputs:** `docs/tasks/prd-[feature-name].md`
- **Loaded By:** `/lp-define-product`
- **Interconnections:** Feeds into the `tasks` skill for JSON conversion. Uses `file-locator`, `pattern-finder`, `docs-locator`, `docs-analyzer` sub-agents.

#### 8. step-zero

Shared prerequisite-and-capability check used by every LaunchPad harness command and L2 command that depends on canonical state. Routes all Step 0 logic through a single shell helper (`${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh`) to prevent drift between command-specific implementations. Exposes two modes: **Full** (harness-level — detect, classify, present, scaffold) and **Lite** (L2-level — verify required state files exist, refuse with a `/lp-define` pointer if missing).

- **Key Outputs:** Pass/refuse signal; harness mode may scaffold canonical state files; Lite mode never writes
- **Loaded By:** `/lp-kickoff`, `/lp-define`, `/lp-plan`, `/lp-build` (Full mode); all L2 commands like `/lp-commit`, `/lp-review`, `/lp-ship`, `/lp-harden-plan` (Lite mode with explicit `--require` list)
- **Interconnections:** Enforces the "Lite ⊆ Full" contract mechanically. Never inlined in command prose — keeps the check in one place.

#### 9. tasks

Converts PRD markdown documents into `prd.json` format for the compound execution loop. Explodes high-level tasks into granular, machine-verifiable sub-tasks ordered by dependencies.

- **Key Outputs:** `prd.json` at specified location
- **Loaded By:** `/lp-pnf`, `/lp-inf`
- **Interconnections:** Consumes output from `prd` skill. Output is consumed by `build.sh` and `loop.sh` execution pipeline.

#### 10. verification-before-completion

Enforcement-style skill that mandates fresh verification evidence (test/typecheck/lint/build output) before any agent claims work is done, fixed, or passing. Auto-triggers on completion-claim phrasing across commands and refuses claims that lack attached command output. Maps each kind of claim ("tests pass", "build green", "PR ready", "Definition of Done met") to the verification command that proves it.

- **Key Outputs:** Verification evidence (command output) attached to every completion claim
- **Loaded By:** auto-trigger on completion-claim phrasing across commands; effective in any command that issues completion claims (notably `/lp-commit`, `/lp-ship`, `/lp-build`)
- **Interconnections:** Closes the most common agentic failure mode where work is declared done without running checks. Adapted from [obra/superpowers](https://github.com/obra/superpowers) (MIT).

### Design Skills

#### 11. frontend-design

Creative direction skill that enforces bold, distinctive aesthetics and fights generic AI-generated UI. Includes 7 reference files covering typography, color, layout, animation, and component patterns.

- **Key Outputs:** Design-quality frontend code, creative direction decisions
- **Loaded By:** `/lp-inf`, design agents
- **Interconnections:** Works alongside `web-design-guidelines` and `responsive-design` for complete design coverage.

#### 12. web-design-guidelines

Engineering compliance checklist organized as MUST/SHOULD/NEVER rules. Covers accessibility, keyboard navigation, focus management, forms, animation, typography, images, performance, dark mode, i18n, and hydration.

- **Key Outputs:** Compliance-validated UI code
- **Loaded By:** `/lp-inf`, design agents
- **Interconnections:** Complements `frontend-design` (aesthetic) with engineering correctness.

#### 13. responsive-design

Injects responsive-first thinking into section specs and design definitions. Operates in 3 modes: A (full spec enrichment), B (component-level breakpoint audit), C (quick mobile-first check).

- **Key Outputs:** Responsive annotations on section specs, breakpoint behavior definitions
- **Loaded By:** `/lp-shape-section`, `/lp-define-design`, `/lp-pnf`
- **Interconnections:** Enriches specs consumed by `frontend-design` during implementation.

### Methodology Skills

#### 14. react-best-practices

70 rules across 9 categories for React and Next.js development, prioritized by impact (CRITICAL > HIGH > MEDIUM > LOW). Covers async patterns, bundle optimization, server-side performance, client-side dynamics, and composition. Includes 9 reference files.

- **Key Outputs:** Pattern-compliant React/Next.js code
- **Loaded By:** `/lp-pnf`, `/lp-inf` (loaded conditionally when project uses React/Next.js)
- **Interconnections:** Enforced during implementation and reviewed during `/lp-review`.

#### 15. stripe-best-practices

Stripe integration patterns enforcing Checkout Sessions over raw PaymentIntents, modern API usage, webhook security with Hono, Prisma-backed subscription state, and Connect platform best practices. Includes 3 reference files and 1 eval.

- **Key Outputs:** Pattern-compliant Stripe integration code
- **Loaded By:** `/lp-pnf`, `/lp-inf` (loaded conditionally when task involves Stripe)
- **Interconnections:** Enforced during implementation and reviewed during `/lp-review`.

### Utility Skills

#### 16. rclone

Cloud file management using rclone. Covers setup checking, installation, remote configuration (S3, R2, B2, GDrive, Dropbox), common operations (copy, sync, ls, move), large file handling, and verification.

- **Key Outputs:** Uploaded/synced files on cloud storage
- **Loaded By:** `/lp-feature-video`
- **Interconnections:** Used by `feature-video` command for uploading recorded video assets.

#### 17. imgup

Lightweight image hosting for quick sharing. Uploads screenshots and small files to public hosting services (pixhost, catbox, imagebin, beeimg) without cloud provider setup. Returns public URLs for embedding in markdown.

- **Key Outputs:** Public image URLs
- **Loaded By:** `/lp-feature-video`
- **Interconnections:** Alternative to `rclone` for quick image sharing without cloud provider configuration.

---

## Skill Relationship Map

```
/lp-kickoff ──→ brainstorming ──→ document-review
                                          │
/lp-define ──→ /lp-define-product ──→ prd
                    /lp-shape-section ──→ responsive-design
                                          │
/lp-plan ──→ /lp-pnf ──→ tasks + react-best-practices* + stripe-best-practices*
                    │
                    └──→ /lp-harden-plan ──→ document-review
                                          │
/lp-build ──→ /lp-inf ──→ frontend-design + web-design-guidelines
                    │         + react-best-practices* + stripe-best-practices*
                    │
                    └──→ /lp-review ──→ /lp-commit ──→ commit ──→ /lp-ship
                                                              │
/lp-feature-video ──→ rclone + imgup                            │
                                                              ▼
/lp-learn ──→ compound-docs                                   PR + CI

/lp-create-skill ──→ creating-skills
/lp-create-agent ──→ creating-agents

* = loaded conditionally based on project stack
```

---

## Adding New Skills

To add a new skill to this project:

1. Run `/lp-create-skill <topic>` to generate a skill using the Meta-Skill Forge
2. Run `/lp-port-skill based on <source>` to port an external skill from the catalog
3. Browse available external skills in [CATALOG.md](CATALOG.md)

After adding a skill, update this index with the new entry.
