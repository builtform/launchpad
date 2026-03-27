# LaunchPad Skills Index

A user-facing reference for all installed skills in LaunchPad. Each skill is a reusable workflow that Claude Code executes when triggered by a slash command or natural language.

---

## How Skill Tracking Works

- **Installation:** Skills are added via `/create-skill` or `/port-skill` and registered in this index, `CLAUDE.md`, `AGENTS.md`, and `skills-usage.json`.
- **Usage tracking:** `scripts/hooks/track-skill-usage.sh` fires after every skill invocation and records the date in `skills-usage.json`.
- **Staleness audit:** `scripts/hooks/audit-skills.sh` fires at session end. If 2+ weeks have passed since the last audit, it reports which skills are stale or unused.

---

## Quick Reference

### Build Pipeline

| #   | Skill     | What It Does                                                          | Trigger           |
| --- | --------- | --------------------------------------------------------------------- | ----------------- |
| 1   | **prd**   | Generates Product Requirements Documents from a feature description   | `/define-product` |
| 2   | **tasks** | Converts PRD markdown into `prd.json` for the compound execution loop | `/pnf`, `/inf`    |

### Quality & Workflow

| #   | Skill      | What It Does                                                                   | Trigger   |
| --- | ---------- | ------------------------------------------------------------------------------ | --------- |
| 3   | **commit** | Runs full commit pipeline: staging, quality gates, commit message, optional PR | `/commit` |

### Meta (Skill Management)

| #   | Skill               | What It Does                                                      | Trigger                                         |
| --- | ------------------- | ----------------------------------------------------------------- | ----------------------------------------------- |
| 4   | **creating-skills** | Creates new skills using the 7-phase Meta-Skill Forge methodology | `/create-skill`, `/update-skill`, `/port-skill` |

---

## Detailed Descriptions

### Build Pipeline

#### 1. prd

Generates Product Requirements Documents from a feature description. Supports interactive (MCQ questions) and autonomous (piped input) modes. Includes codebase research, self-clarification, and structured PRD output.

- **Key Outputs:** `docs/tasks/prd-[feature-name].md`
- **Related Commands:** `/define-product`
- **Interconnections:** Feeds into the `tasks` skill for JSON conversion. Uses `codebase-locator`, `codebase-pattern-finder`, `docs-locator`, `docs-analyzer` sub-agents.

#### 2. tasks

Converts PRD markdown documents into `prd.json` format for the compound execution loop. Explodes high-level tasks into granular, machine-verifiable sub-tasks ordered by dependencies.

- **Key Outputs:** `prd.json` at specified location
- **Related Commands:** `/pnf`, `/inf`
- **Interconnections:** Consumes output from `prd` skill. Output is consumed by `auto-compound.sh` and `loop.sh` execution pipeline.

### Quality & Workflow

#### 3. commit

Runs the full commit pipeline: branch validation, staging, parallel quality gates (tests, linting, type checks, pre-commit hooks), conventional commit message generation, and optional PR creation with CI monitoring.

- **Key Outputs:** Git commits, optional GitHub PRs
- **Related Commands:** `/commit`
- **Interconnections:** Standalone workflow. Enforces quality gates before any commit.

### Meta (Skill Management)

#### 4. creating-skills

Creates new Claude Code skills using the 7-phase Meta-Skill Forge methodology. Includes research waves, targeted extraction rounds, contrarian analysis, architecture decisions, writing, quality validation, and shipping.

- **Key Outputs:** `.claude/skills/<name>/SKILL.md`, reference files in `references/`, eval scenarios in `evals/`, updates to `CLAUDE.md` and `AGENTS.md`
- **Related Commands:** `/create-skill`, `/update-skill`, `/port-skill`
- **Interconnections:** Uses `codebase-pattern-finder`, `docs-locator`, `codebase-locator`, `codebase-analyzer`, `docs-analyzer`, `web-search-researcher`, and `skill-evaluator` sub-agents.

---

## Skill Relationship Map

```
/define-product ──→ prd ──→ tasks ──→ auto-compound.sh / loop.sh
                                         │
                                         ▼
                                      commit (quality gates → git → PR)

/create-skill ──→ creating-skills (7-phase forge → new skill registered)
/port-skill   ──→ creating-skills (porting workflow → adapted skill)
/update-skill ──→ creating-skills (iteration workflow → updated skill)
```

---

## Adding New Skills

To add a new skill to this project:

1. Run `/create-skill <topic>` to generate a skill using the Meta-Skill Forge
2. Run `/port-skill based on <source>` to port an external skill from the catalog
3. Browse available external skills in [CATALOG.md](CATALOG.md)

After adding a skill, it will automatically appear in usage tracking on first invocation.
