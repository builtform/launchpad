# Methodology

> **Structure for AI coding. Best practices, pre-configured.**

AI coding tools are powerful. Without structure, they're a trap.

You prompt an agent to build a feature. It generates code that looks right -- until you discover it hallucinated an API, ignored your existing patterns, or duplicated a utility that already exists. You fix it, start a new session, and the agent has forgotten everything. No specs. No guardrails. No memory. Just vibes.

The best practices exist. Spec-driven development. Compound loops with fresh context. Structure enforcement. Automated quality gates. Context engineering via CLAUDE.md. They're scattered across blog posts, repos, and conference talks. You know you should set them up. You haven't had time.

Launchpad is a monorepo template where all of it is already wired in and working. Clone it, define your product, and start building with an AI workflow that has specs, guardrails, autonomous execution loops, pre-commit hooks, CI pipelines, and automated code review -- from the first commit.

This document explains the philosophy and principles behind each layer. For implementation details, see [How It Works](docs/guides/HOW_IT_WORKS.md).

---

## The Seven Layers

| Layer                                                        | What It Does                                                                                                   | Key Files                                                               |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| 1. [Opinionated Scaffold](#layer-1-opinionated-scaffold)     | Monorepo with enforced structure, whitelisted root files, and a decision tree for file placement               | `REPOSITORY_STRUCTURE.md`, `check-repo-structure.sh`, `init-project.sh` |
| 2. [Spec-Driven Definition](#layer-2-spec-driven-definition) | Interactive wizards that produce 6 canonical architecture docs, giving AI agents full project context          | `/define-product`, `/define-architecture`, `/create_plan`               |
| 3. [Compound Execution](#layer-3-compound-execution)         | Report --> analysis --> PRD --> tasks --> autonomous loop --> PR. Fresh-context iterations with a Kanban board | `auto-compound.sh`, `loop.sh`, `iteration-claude.md`, `/inf`            |
| 4. [Quality Gates](#layer-4-quality-gates)                   | Pre-commit hooks, CI pipeline, and AI-powered code review with P0--P3 severity classification                  | `lefthook.yml`, `ci.yml`, `codex-review.yml`                            |
| 5. [Commit-to-Merge](#layer-5-commit-to-merge)               | Branch guard --> quality gates --> PR creation --> 3-gate monitoring loop. Never auto-merges                   | `/commit`, `auto-compound.sh` Steps 7a--7c                              |
| 6. [Compound Learning](#layer-6-compound-learning)           | Structured knowledge extraction, learnings catalog, pattern promotion, and cross-run memory                    | `docs/solutions/`, `progress.txt`, `promoted-patterns.md`               |
| 7. [Skill Creation](#layer-7-skill-creation)                 | Encode domain expertise as reusable AI skills with quality-validated reasoning patterns                        | `/create-skill`, `/update-skill`, `skill-evaluator`                     |

No single competitor offers all seven layers. SpecKit has Layer 2. Design OS has Layer 2. Ralph has Layer 3. Compound Product has Layers 3 and 6. Nobody has Layers 1, 4, 5, or 7.

---

## Layer 1: Opinionated Scaffold

The scaffold is a closed-loop system with three components: a **specification** that defines where every file belongs, a **bash enforcement script** that validates the repo against that specification, and **wiring** (Lefthook + CI) that triggers enforcement on every commit. A fourth component, the **initialization wizard**, transforms the template into a new project.

The system answers one question: _"Where does this file go?"_ -- and enforces the answer automatically.

> Implementation details in [How It Works](docs/guides/HOW_IT_WORKS.md).

---

## Layer 2: Spec-Driven Definition

Before any code is written, the project needs specs. This layer produces six canonical architecture documents that give AI agents full context about what they're building, why, and how.

There are two paths into this layer: an **interactive path** (human-guided slash commands) and an **autonomous path** (AI-generated from reports via the compound pipeline). Both produce the same artifacts.

Both paths use **6 sub-agents** organized in a two-wave orchestration pattern. Wave 1 (Discovery) runs 4 locators in parallel -- codebase locator, docs locator, pattern finder, and web researcher -- using only fast tools (Grep, Glob, LS) to find relevant files without reading them. Wave 2 (Analysis) waits for Wave 1 to complete, then runs 2 analyzers in parallel -- codebase analyzer and docs analyzer -- targeting only the paths Wave 1 found. This ensures expensive Read operations are focused precisely where they'll yield useful context, preventing wasted tokens on irrelevant files.

The PRD creation workflow (via the `/prd` skill or Step 4 of `auto-compound.sh`) extends this layer with several enhancements:

- **Interactive MCQ mode:** When invoked interactively, the PRD skill asks 3-5 multiple-choice clarifying questions before generation. In autonomous mode (piped from the compound pipeline), it self-clarifies without user input.
- **P0/P1/P2 priority tiers:** Every functional requirement is classified as P0 (must-have), P1 (should-have), or P2 (nice-to-have). P0 requirements must have corresponding tasks.
- **"Files NOT to Modify" section:** Every PRD includes an explicit list of files and directories that must not be touched during implementation, preventing agents from "improving" adjacent code.
- **Separated auto/manual verification:** Task acceptance criteria are split into machine-verifiable checks (run by the agent) and manual verification steps (logged for human follow-up).
- **4 research agents:** Before generating a PRD, the skill spawns `codebase-locator`, `codebase-pattern-finder`, `docs-locator`, and `docs-analyzer` in parallel to gather codebase context, existing patterns, prior decisions, and documentation constraints.

### The Philosophy

Spec-driven development is the practice of specifying before building. The idea comes from the broader SDD movement (Thoughtworks, GitHub SpecKit, AWS Kiro), but our implementation is different:

- **SpecKit** produces per-feature specs that are consumed and discarded
- **Launchpad** produces project-level canonical documents that persist and evolve

The six architecture docs are living documents. They grow as the project grows. Every AI agent session reads them for context. Every compound pipeline iteration checks them for constraints.

> Implementation details in [How It Works](docs/guides/HOW_IT_WORKS.md).

---

## Layer 3: Compound Execution

This layer implements the autonomous execution loop: give it a report describing what needs to be done, and it produces a PR with the work complete, quality gates passing, and a Kanban board showing progress.

The pipeline emits `[CHECKPOINT]` messages at key boundaries (after report analysis, PRD generation, task decomposition, and loop completion). These are informational only -- the pipeline continues autonomously -- but they make the autonomous process observable for developers watching the terminal.

The methodology is adapted from [Compound Product](https://github.com/snarktank/compound-product) by Ryan Carson (itself built on [Kieran Klaassen's compound engineering](https://github.com/EveryInc/compound-engineering-plugin) and [Geoffrey Huntley's Ralph pattern](https://github.com/geoffreyhuntley/ralph)). We've modified it significantly -- see [Differences from Upstream](#differences-from-upstream) for details.

> Implementation details in [How It Works](docs/guides/HOW_IT_WORKS.md).

---

## Layer 4: Quality Gates

Quality is enforced at three stages: **locally before commit** (pre-commit hooks), **remotely on every PR** (CI pipeline), and **via AI review after PR creation** (Codex code review). Each stage is a safety net for the previous one.

> Implementation details in [How It Works](docs/guides/HOW_IT_WORKS.md).

---

## Layer 5: Commit-to-Merge

This layer governs everything from the moment code is ready to commit through PR creation and monitoring. It exists in two modes: **interactive** (the `/commit` slash command) and **autonomous** (Steps 7a--7c of `auto-compound.sh`).

Both modes share the same three-gate architecture but differ in human involvement.

### 10 Hard Rules

1. Never commit on `main`/`master`
2. Never use `--no-verify`
3. Never auto-merge
4. Never skip quality gates
5. Fix root causes, never work around
6. Always use HEREDOC for commit messages
7. Always include `Co-Authored-By` trailer
8. Keep subject under 72 characters
9. Use imperative mood
10. If any step fails, stop and fix before continuing

> Implementation details in [How It Works](docs/guides/HOW_IT_WORKS.md).

---

## Layer 6: Compound Learning

The compound philosophy is that **each unit of work should make future work easier -- not harder**. This layer captures learnings from every compound run and feeds them back into the system, so the same mistake is never made twice and the same pattern is never rediscovered.

This is a synthesis of two systems: the knowledge management from [Compound Product](https://github.com/snarktank/compound-product) and the structured learning capture from the [Compound Engineering Plugin](https://github.com/EveryInc/compound-engineering-plugin) by Every.

**The feedback loop is now fully closed.** Earlier versions could only _write_ knowledge (extracting learnings into `docs/solutions/` and `promoted-patterns.md`). Now, dedicated docs agents (`docs-locator` and `docs-analyzer`) can _read_ that accumulated knowledge back during `/research_codebase` and `/create_plan`. This means prior decisions, rejected approaches, constraints, and promoted patterns are surfaced during planning -- not just stored for future manual discovery. On fresh projects where `docs/` contains only stubs, the docs agents are skipped gracefully.

### The Feedback Loop

```
Build --> Test --> Find Issue --> Fix --> Document --> Validate --> Deploy
  ^                                                                 |
  +------------ learnings feed back into next cycle ----------------+
```

1. **First occurrence:** A problem takes 30 minutes to research and solve
2. **Document:** `auto-compound.sh` Step 8 extracts the learnings (automatic, ~2 minutes)
3. **Next occurrence:** The AI reads `progress.txt` and `docs/solutions/` and recognizes the pattern (seconds)
4. **Pattern promotion:** If it recurs 3+ times, it's staged in `promoted-patterns.md` and eventually promoted to CLAUDE.md
5. **Permanent knowledge:** All future sessions start with the pattern pre-loaded -- the problem is prevented, not just fixed faster

> Implementation details in [How It Works](docs/guides/HOW_IT_WORKS.md).

---

## Layer 7: Skill Creation

AI skills are reusable instruction sets that change how Claude reasons about specific problem domains. Without skills, every session starts from baseline — Claude applies generic reasoning to every task. With skills, Claude applies domain-specific decision frameworks, anti-patterns, and verification gates that produce structurally different output.

Layer 7 provides the **infrastructure to create these skills**, not pre-built skills for specific domains. Every project derived from Launchpad inherits this infrastructure and can create domain-specific skills from day one.

### The Meta-Skill Forge

Skills are created through a 7-phase methodology called the Meta-Skill Forge:

1. **Context Ingestion** — Two-wave sub-agent research (Discovery → Analysis) gathers codebase patterns, documentation, and external best practices
2. **Targeted Extraction** — 4 collaborative rounds extract the user's domain expertise (or distill source material for book/article-based skills)
3. **Contrarian Analysis** — Write out the generic/baseline version first, then engineer away from every predictable pattern
4. **Architecture Decision** — Adaptive complexity routing: Simple (single file), Moderate (1-3 references), or Full (multiple files + templates)
5. **Write the Skill** — Produce SKILL.md orchestrator + reference files following progressive disclosure
6. **Quality Validation** — Recursive evaluation loop (max 3 cycles) against 14 criteria across 3 passes
7. **Ship It** — Generate eval scenarios, register in CLAUDE.md, present to user

### Three Layers Every Skill Needs

| Layer                     | What It Does                                | What "Bad" Looks Like                             |
| ------------------------- | ------------------------------------------- | ------------------------------------------------- |
| **Trigger System**        | Defines WHEN and WHY the skill activates    | "Helps with writing" — too vague to be useful     |
| **Thinking Architecture** | "How to THINK about this class of problems" | "Step 1, step 2, deliver" — recipe, not reasoning |
| **Verification Gate**     | "Does this look like baseline LLM output?"  | No self-check — generates and ships               |

### The Compounding Effect

Skills feed directly into the compound pipeline. When `/inf` or `auto-compound.sh` runs the autonomous execution loop, every skill in `.claude/skills/` shapes how it approaches tasks. A "writing API routes" skill means the compound loop produces better API routes. A "testing React components" skill means better tests. The autonomous capabilities of the project grow with each skill added.

### Key Design Decisions

- **Infrastructure, not content** — Launchpad ships the skill creation workflow, not pre-built domain skills. Pre-built skills would be "running someone else's brain on your problems."
- **Interactive, not autonomous** — Skill creation requires human domain expertise. It lives in Phase A (human-guided), not Phase B (agent-driven).
- **Contrarian frame** — Every skill must demonstrate it produces structurally different output from baseline Claude. Formatting changes don't count.
- **Recursive evaluation** — Skills are validated against 14 criteria across 3 passes (first-principles, baseline detection, Anthropic checklist) before shipping.

> Implementation details in the skill itself: `.claude/skills/creating-skills/SKILL.md`

---

## Credits and Inspirations

Launchpad is built on the shoulders of three frameworks. We credit them here and throughout the codebase.

### Compound Product

**By:** Ryan Carson ([snarktank/compound-product](https://github.com/snarktank/compound-product))

The core pipeline: report --> analysis --> PRD --> tasks --> autonomous loop --> PR. We adapted this into `scripts/compound/` with significant modifications (see below).

### Compound Engineering Plugin

**By:** Kieran Klaassen / Every ([EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin))

The compounding philosophy and structured learning capture system. The `docs/solutions/` pattern, the learnings extraction pipeline, and the WRONG/CORRECT anti-pattern format are inspired by their approach. The plugin itself is an optional external dependency -- not installed by default, but recommended.

### Ralph Pattern

**By:** Geoffrey Huntley

The autonomous execution loop concept -- fresh context per iteration, git as memory. Merged into `loop.sh`.

### Spec-Driven Development

**Inspired by:** Thoughtworks Technology Radar, GitHub SpecKit, AWS Kiro

The philosophy of "specify before building." Our implementation (`/define-product`, `/define-architecture`) is our own -- different from SpecKit's per-feature specs. Ours produce project-level canonical documents that persist and evolve.

---

## Differences from Upstream

Launchpad is not a fork of Compound Product. It's a custom implementation that shares the pipeline architecture but diverges significantly in capabilities.

| Aspect                    | Compound Product (Upstream) | Launchpad                                                                                                   |
| ------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **AI tool dispatch**      | Claude Code only            | Configurable via `config.json` (`claude`, `codex`, or `gemini`) with `ai_run()` abstraction                 |
| **Prompt files**          | Separate per tool           | Single `iteration-claude.md` piped to all tools via stdin                                                   |
| **Task status**           | `passes: true/false` only   | Full `status` field (pending/in_progress/done/failed) with `startedAt`/`completedAt` timestamps             |
| **Visualization**         | None                        | `board.sh` with 3 modes (ASCII, Markdown, Summary), rendered after every iteration, embedded in PR body     |
| **Archive**               | `cp` (copy)                 | `mv` (move) with date-prefixed folders                                                                      |
| **Report analysis**       | Basic, single-provider      | `analyze-report.sh` with 5-provider LLM support, model aliases, recent-PRD deduplication                    |
| **Quality gates**         | Basic test run in config    | 3-attempt auto-fix loop with lefthook + AI-assisted fixing (Step 7a)                                        |
| **PR monitoring**         | None                        | 3-gate loop: CI checks, Codex P0/P1 parsing, merge conflict resolution (Step 7c)                            |
| **Learnings extraction**  | Agent updates AGENTS.md     | Structured extraction to `docs/solutions/` with YAML frontmatter, template, and promotion pipeline (Step 8) |
| **Definition layer**      | None                        | `/define-product` and `/define-architecture` producing 6 architecture docs                                  |
| **Manual execution path** | None                        | `/create_plan` + `/implement_plan` as human-supervised alternative                                          |
| **Commit workflow**       | None                        | `/commit` with branch guards, parallel quality gates, interactive Codex review                              |
| **Structure enforcement** | None                        | `check-repo-structure.sh` + `REPOSITORY_STRUCTURE.md` + Lefthook + CI                                       |
| **Knowledge pipeline**    | AGENTS.md updates only      | progress.txt --> learnings --> promoted-patterns --> CLAUDE.md feedback loop                                |
| **Skill creation**        | None                        | 7-phase Meta-Skill Forge with contrarian analysis, recursive evaluation, and progressive disclosure         |
