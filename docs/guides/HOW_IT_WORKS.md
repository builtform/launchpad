# How It Works

Launchpad is a 7-layer AI coding harness for structured AI development. This guide walks you through the four-tier workflow. For the full architecture, diagrams, and implementation details, see [Methodology](METHODOLOGY.md).

---

## Tier 0 — Capabilities (seed before you build)

### Step 0: Create or Port Skills

Skills are reusable instruction sets that change how the AI reasons about specific problem domains. Loading skills **before** definition means every subsequent command — from `/define-product` to `/inf` — benefits from domain-specific reasoning instead of generic baseline output.

- `/create-skill [topic]` — create a new skill using the 7-phase Meta-Skill Forge
- `/port-skill [source]` — import an external skill (from Vercel, Anthropic, community repos, or any local file)
- `/update-skill [name]` — iterate on an existing skill after real-world usage

**Where to find skills to port:**

- Browse the [Skills Catalog](../skills-catalog/CATALOG.md) — curated, validated skills ready to port
- Anthropic's [official skills](https://github.com/anthropics/skills) — maintained by the Claude team
- Domain-specific skills for your industry or tech stack

> Deep dive: [Methodology — Layer 7](METHODOLOGY.md#layer-7-skill-creation)

### How Skills Work

Skills live in `.claude/skills/<name>/` and are loaded automatically by the AI when a matching trigger phrase appears. Each skill directory contains:

| File              | Audience | Purpose                                                   |
| ----------------- | -------- | --------------------------------------------------------- |
| `SKILL.md`        | Agent    | The orchestrator — defines phases, triggers, and workflow |
| `references/*.md` | Agent    | Deep knowledge files loaded on demand by SKILL.md         |
| `evals/*.md`      | Agent    | Test scenarios for validating skill quality               |

Skills are **agent-facing** — the AI reads them, not you. As a user, you interact with skills through commands (`/create-skill`, `/port-skill`, `/update-skill`) and through the catalog described below.

### Skill Lifecycle

```
Create or Port          Use              Track             Audit
─────────────── → ─────────────── → ─────────────── → ───────────────
/create-skill     AI auto-loads       PostToolUse hook    Every 2 weeks
/port-skill       on trigger match    updates date in     at session end,
                                      skills-usage.json   reports stale skills
       │                                                        │
       ▼                                                        ▼
  Registered in:                                          User decides:
  • CLAUDE.md (agent)                                     keep, update,
  • AGENTS.md (agent)                                     or archive
  • skills-index.md (you)
  • skills-usage.json (auto)
```

### Skills Catalog (User-Facing)

Two files in `docs/skills-catalog/` give you visibility into what skills are installed and how actively they're used:

| File                | Maintained By                                   | What It Shows                                                                                     |
| ------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `skills-index.md`   | `/create-skill`, `/port-skill`, `/update-skill` | All installed skills with descriptions, outputs, triggers, related commands, and interconnections |
| `skills-usage.json` | PostToolUse hook (automatic)                    | Last-used date per skill + last audit date                                                        |

`skills-index.md` is the file to read when you want to know what skills your project has and what each one does.

### Skill Tracking and Staleness Audit

Two hook scripts in `scripts/hooks/` run automatically — no action needed from you:

1. **`track-skill-usage.sh`** — Fires after every skill invocation. Records the skill name and date in `skills-usage.json`. You never run this manually.

2. **`audit-skills.sh`** — Fires at session end. If 14+ days have passed since the last audit, it scans all installed skills against `skills-usage.json` and reports which skills are stale (never used or unused for 2+ weeks). It does not remove anything — it informs you, and you decide what to do.

These hooks are configured in `.claude/settings.json` (project-level).

### When Skills Get Registered

| Action                 | Adds to Catalog?                                                | Updates Catalog?                                                     |
| ---------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------- |
| `/create-skill`        | Yes — adds new entry to `skills-index.md` + `skills-usage.json` | —                                                                    |
| `/port-skill`          | Yes — adds new entry to both files                              | —                                                                    |
| `/update-skill`        | No — skill must already exist                                   | Yes — updates date and entry if description/outputs/triggers changed |
| Every skill invocation | No                                                              | Yes — hook updates last-used date                                    |

---

## Tier 1 — Definition (run once per project)

### Step 1: Define Your Product

Run `/define-product` in Claude Code. This interactive Q&A produces:

- `docs/architecture/PRD.md` — product requirements, target users, MVP features, section registry
- `docs/architecture/TECH_STACK.md` — framework, database, auth, hosting decisions

> Deep dive: [Methodology — Layer 2](METHODOLOGY.md#layer-2-spec-driven-definition)

### Step 2: Define Your Design (UI/UX)

Run `/define-design`. This produces:

- `docs/architecture/DESIGN_SYSTEM.md` — visual design tokens, component conventions, spacing, typography, color palette (UI)
- `docs/architecture/APP_FLOW.md` — pages, routes, auth flow, navigation (UX)
- `docs/architecture/FRONTEND_GUIDELINES.md` — components, state management, responsive strategy (UI/UX)

### Step 3: Define Your Backend Architecture

Run `/define-architecture`. This produces:

- `docs/architecture/BACKEND_STRUCTURE.md` — data models, API endpoints, auth strategy
- `docs/architecture/CI_CD.md` — CI pipeline, deploy strategy, environments

These seven documents give every AI session full project context.

> Deep dive: [Methodology — Layer 2](METHODOLOGY.md#layer-2-spec-driven-definition)

---

## Tier 2 — Development (per section, ongoing)

### Step 4: Shape Sections

Run `/shape-section [name]` for each product section identified in your PRD. This deep-dive produces:

- `docs/tasks/sections/[name].md` — detailed section spec with user stories, data shapes, edge cases

For **public-facing pages** (landing, pricing, about, feature, product, homepage, contact), `/shape-section` will prompt you to create the page copy using the `web-copy` skill (if installed). This produces a copy brief and full copy document with conversion-optimized headlines, body text, CTAs, trust signals, and A/B variants — all before any design or implementation begins. Copy informs design, not the other way around.

### Step 5: Maintain Spec Quality

Run `/update-spec` periodically. This scans all spec files for gaps, TBDs, and cross-file inconsistencies, then fixes them. It also detects public-facing sections that are missing copy documents and flags them for action.

---

## Tier 3 — Implementation (per section)

### Step 6: Plan a Feature

- **From section spec:** `/pnf [section]` — research-first planning with sub-agents, creates an implementation plan from a shaped section
- **Autonomous:** Write a report in `docs/reports/`, then run `/inf`

> Deep dive: [Methodology — Layer 2](METHODOLOGY.md#layer-2-spec-driven-definition)

### Step 7: Build It

- **Interactive:** `/implement_plan` — execute your plan phase by phase
- **Autonomous:** `/inf` runs the full pipeline: report → PRD → tasks → execution loop → quality sweep → PR

Each iteration runs with fresh AI context. Memory persists through git commits, `prd.json`, and `progress.txt`.

> Deep dive: [Methodology — Layer 3](METHODOLOGY.md#layer-3-compound-execution)

---

## Quality Gates

Every change passes through three stages:

1. **Pre-commit hooks** (Lefthook) — formatting, linting, type checking, structure validation
2. **CI pipeline** (GitHub Actions) — lint, typecheck, test, build, structure check
3. **AI review** (Codex) — P0–P3 severity classification on every PR

> Deep dive: [Methodology — Layer 4](METHODOLOGY.md#layer-4-quality-gates)

---

## Commit and Ship

Run `/commit` for the interactive workflow, or let `/inf` handle it autonomously. Both paths use a 3-gate monitoring loop: CI checks → Codex review → merge conflict resolution.

The system never auto-merges — you decide when to merge.

> Deep dive: [Methodology — Layer 5](METHODOLOGY.md#layer-5-commit-to-merge)

---

## Learn and Improve

After each cycle, learnings are captured at three levels:

1. **`progress.txt`** — per-iteration notes (immediate, ephemeral)
2. **`docs/solutions/`** — structured learnings per feature (persistent)
3. **`CLAUDE.md`** — promoted patterns that influence every future session (permanent)

The system gets smarter with every cycle.

> Deep dive: [Methodology — Layer 6](METHODOLOGY.md#layer-6-compound-learning)

---

## Troubleshooting

**Loop exits early / doesn't complete all tasks.**
The loop exits with code 1 when it reaches `maxIterations` (default 25) without all tasks passing. Check `scripts/compound/progress.txt` for the last iteration's output. Common causes: tasks are too large for a single iteration, quality checks keep failing on committed code, or context overflow causes the agent to lose track. Fix: break large tasks into smaller ones in `prd.json`, reduce scope in the PRD, or increase `maxIterations` in `config.json`.

**Loop exits immediately with "No prd.json found."**
`loop.sh` requires `scripts/compound/prd.json` to exist before entering the loop. This file is created by Step 5 of `auto-compound.sh`. If running `loop.sh` standalone, run the full pipeline with `/inf` or `auto-compound.sh` first.

**Lefthook pre-commit hooks fail and block your commit.**
Lefthook runs 7 checks: Prettier, ESLint (both auto-fix), then typecheck, structure-check, large-file-guard, trailing-whitespace, and end-of-file-newline (all blocking). If an auto-fixer fails, check that `pnpm` dependencies are installed (`pnpm install`). If a read-only check fails, the error message explains the violation. Never use `--no-verify` to bypass -- fix the root cause.

**TypeScript typecheck fails during pre-commit.**
The `typecheck` hook runs `pnpm typecheck`, which Turborepo dispatches across all workspaces in strict mode. Common causes: missing type exports from `@repo/shared`, type errors in generated code, or stale build artifacts. Fix: run `pnpm typecheck` manually to see the full error, then fix the type issue. If types from a dependency are stale, run `pnpm build` in that package first.

**Structure check blocks commit: "Non-whitelisted file at root."**
The `check-repo-structure.sh` enforcer validates every file at the repo root against a whitelist. If you created a file at the root that isn't in the whitelist, the commit is blocked. Fix: move the file to the correct directory using the decision tree in `docs/architecture/REPOSITORY_STRUCTURE.md` Section 7. If the file legitimately belongs at the root, add it to the whitelist arrays in both `check-repo-structure.sh` and `REPOSITORY_STRUCTURE.md`.

**Structure check blocks commit: "Found duplicate files."**
The enforcer detects macOS Finder artifacts (files with ` 2`, ` v2`, or ` copy` in the name). The error message says "MANUAL REVIEW REQUIRED -- DO NOT AUTO-DELETE." Fix: compare both versions with `diff`, keep the better one, delete the other, and rename if needed.

**Report analysis fails: "No LLM provider configured."**
`analyze-report.sh` needs at least one API key. It checks in order: `AI_GATEWAY_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`. Fix: add one of these to `.env.local` at the project root. The script sources `.env.local` automatically via `auto-compound.sh`.

**Report analysis fails: "Could not parse response as JSON."**
The LLM returned a response that isn't valid JSON (often wrapped in markdown code fences). The script tries to extract JSON from the response, but if the LLM adds commentary, parsing fails. Fix: this is usually transient -- rerun the pipeline. If it persists, check that the API key is valid and the model is accessible on your plan.

**`auto-compound.sh` fails: "Config file not found."**
The pipeline requires `scripts/compound/config.json`. Fix: this file is tracked in the repo and should already exist. If missing, restore it with `git checkout HEAD -- scripts/compound/config.json`.

**`auto-compound.sh` fails: "jq is required" / "gh CLI not found" / "lefthook not found."**
The pipeline checks for CLI tools at startup. Fix: install the missing tool with `brew install jq`, `brew install gh`, or `brew install lefthook`.

**`prd.json` parse errors.**
The AI-generated `prd.json` has invalid JSON or is missing required fields. Fix: inspect `scripts/compound/auto-compound-tasks.log` for the raw AI output. Manually fix `prd.json` or delete it and rerun the pipeline. Validate with: `jq . scripts/compound/prd.json`.

**PR creation fails: "gh: not logged in."**
Step 7b uses `gh pr create` which requires GitHub CLI authentication. Fix: run `gh auth login` and verify with `gh auth status`.

**Codex review not running on PRs.**
The `codex-review.yml` workflow requires `OPENAI_API_KEY` in GitHub repository secrets. Fix: go to Settings > Secrets and variables > Actions in your GitHub repo and add `OPENAI_API_KEY`.

**No reports found in `docs/reports/`.**
Step 1 of `auto-compound.sh` looks for `.md` files in `docs/reports/`. If the directory is empty, the pipeline exits. Fix: write a report describing what needs attention, or run `/research_codebase` to generate one.

**Agent can't find slash commands or skills.**
If `/inf`, `/commit`, or other slash commands don't work, the `.claude/commands/` directory may be missing or the command files aren't present. Fix: verify the command files exist in `.claude/commands/`. If you initialized with `init-project.sh`, these should already be in place.

**Large file guard blocks commit.**
The `large-file-guard` hook in `lefthook.yml` rejects staged text-based source files (`.js`, `.ts`, `.json`, `.css`, `.md`, `.yml`, `.yaml`, `.html`, `.sh`, `.mjs`, `.cjs`) over 500KB. Binary files (images, PDFs) are not checked by this guard. Common culprits: lockfiles, bundled assets, or accidentally staged `node_modules` contents. Fix: add the file to `.gitignore` if it shouldn't be tracked, or split it into smaller files. For large reference resources like PDFs, store them in `docs/articles/` where they are automatically gitignored via `docs/**/*.pdf`.

---

## Quick Reference

> This section lists LaunchPad's built-in commands. Downstream projects add their own commands (design quality, billing, etc.) in their own HOW_IT_WORKS.md.

### Skill Management

| Command                 | What It Does                                                                  | When to Use                                                 |
| ----------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `/create-skill [topic]` | Create a new skill using the 7-phase Meta-Skill Forge methodology             | When you need Claude to learn a new domain                  |
| `/port-skill [source]`  | Import an external skill from GitHub repos or local files into project format | When you find a useful community skill and want to adapt it |
| `/update-skill [name]`  | Iterate on an existing skill after real-world usage reveals gaps              | When a skill produces wrong guidance or misses edge cases   |

### Project Definition

| Command                | What It Does                                                                                | When to Use                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `/define-product`      | Interactive Q&A that produces `PRD.md` + `TECH_STACK.md`                                    | At project start — defines what you're building, for whom, and with what                         |
| `/define-design`       | Interactive Q&A that produces `DESIGN_SYSTEM.md` + `APP_FLOW.md` + `FRONTEND_GUIDELINES.md` | After `/define-product` — establishes visual language, navigation, and component conventions     |
| `/define-architecture` | Interactive Q&A that produces `BACKEND_STRUCTURE.md` + `CI_CD.md`                           | After product + design are defined — establishes data models, API structure, and deploy pipeline |

### Spec Development

| Command                 | What It Does                                                                                                                                                                  | When to Use                                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `/shape-section [name]` | Deep-dive Q&A into a product section, produces `docs/tasks/sections/[name].md`. For public-facing pages, prompts to create page copy via the `web-copy` skill (if installed). | Before building any feature — shapes user stories, data shapes, edge cases, and acceptance criteria |
| `/update-spec`          | Scans all spec files for gaps, TBDs, cross-file inconsistencies, and missing copy for public-facing pages                                                                     | Periodically, or after multiple sections have been shaped — keeps specs internally consistent       |

### Implementation

| Command              | What It Does                                                                                                     | When to Use                                                                   |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `/pnf [section]`     | Plan Next Feature: Research-first planning with sub-agents, creates an implementation plan from a shaped section | Before writing any code — turns a section spec into a step-by-step build plan |
| `/inf`               | Implement Next Feature: Full autonomous pipeline: report → PRD → tasks → execution loop → quality sweep → PR     | When you want Claude to build a feature end-to-end with minimal intervention  |
| `/implement_plan`    | Execute an existing plan phase by phase with your oversight                                                      | When you prefer to guide implementation manually rather than using `/inf`     |
| `/research_codebase` | Deep codebase research and analysis using multiple sub-agents                                                    | When you need to understand how something works before changing it            |
| `/review_code`       | Review code for pattern consistency against project conventions                                                  | After implementing a feature — catches deviations from established patterns   |
| `/commit`            | Stage changes, run quality gates (test/typecheck/lint), generate commit message, optionally create PR            | When you're ready to commit — handles the full commit-to-PR workflow          |

### Maintenance

| Command           | What It Does                                                                                                           | When to Use                                                      |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `/pull-launchpad` | Pull upstream LaunchPad changes using delta patching — shows only what changed upstream, preserves your customizations | When LaunchPad has new features or fixes you want to incorporate |
| `/memory-report`  | Save session findings to persistent memory for future conversations                                                    | At the end of a long session to preserve context                 |

### How `/pull-launchpad` Works

The pull mechanism uses **upstream delta patching** — it diffs LaunchPad's old version against LaunchPad's new version to isolate only what changed upstream. Your downstream customizations are invisible to the diff.

**Anchor file:** `.launchpad/upstream-commit` stores the LaunchPad commit SHA your project was last synced from. This is the starting point for computing the delta.

**Classification:** Each upstream change is classified by trying to apply it:

- **NEW** — file added upstream, doesn't exist locally. Safe to add.
- **CLEAN** — file modified upstream, patch applies cleanly. Your local edits (if any) are on different lines.
- **CONFLICT** — file modified upstream, but your local edits overlap with the upstream changes. Needs manual resolution.
- **DELETED** — file deleted upstream.

**Interactive selection:** You choose which changes to apply by category (`n` for all NEW, `c` for all CLEAN, `a` for all) or by individual file numbers.

**Anchor policy:** The anchor advances only when all files in the delta are resolved (applied or skipped). Partial syncs leave the anchor unchanged — skipped files reappear next time.

**Rollback:** If anything goes wrong: `git checkout -- .` restores the pre-sync state.

> For all scripts, sub-agents, configuration, and security, see [Methodology](METHODOLOGY.md).

---

## Related

- [README](../../README.md)
- [Methodology](METHODOLOGY.md) — architecture, diagrams, credits
- [Repository Structure](../architecture/REPOSITORY_STRUCTURE.md)
