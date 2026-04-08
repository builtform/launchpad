# Implement Next Feature

Build-only pipeline: reads the latest report or section spec, creates a feature branch, generates a PRD, implements tasks, and runs quality gates. Does NOT push, create PRs, or extract learnings — those are handled by `/ship` and `compound-learning.sh`.

## Usage

- `/inf` — run the full build pipeline
- `/inf --dry-run` — preview the priority pick without making changes
- `/inf --plan path/to/plan.md` — explicit plan path, skips registry check

## Section Registry Check

If `--plan` flag is provided, skip this section entirely and pass the plan directly to `build.sh`.

Otherwise, read `docs/architecture/PRD.md` and look for the section registry. If a section registry exists:

1. Look for sections with status `planned` (NOT `shaped`). If exactly one is found, auto-select it. If multiple are found, present the list and ask the user which one to implement.
2. If only `shaped` sections exist, suggest to the user: "Section [name] is shaped but not planned yet. Run `/pnf [name]` first."
3. If no section registry exists, fall through to the standard report analysis logic below.

## Conditional Skill Loading

Before execution, conditionally load methodology skills that guide code quality:

**React / Frontend gate:**

- IF current task touches files in `apps/web/` or `packages/ui/`, OR task title/description mentions React, component, page, layout:
  - Load skill: `react-best-practices`
  - 70 rules enforced during code writing — CRITICAL rules block, HIGH rules require justification to skip

**Stripe / Billing gate:**

- IF current task title/description mentions Stripe, payment, billing, checkout, subscription, webhook, or pricing:
  - Load skill: `stripe-best-practices`
  - Checkout Sessions enforced, banned APIs rejected, webhook patterns applied, Prisma billing models used

Skills are loaded silently if present. Skip silently if the skill directory does not exist in `.claude/skills/`.

---

## Execution

Run the build script and relay all output:

```bash
./scripts/compound/build.sh $ARGUMENTS [SECTION_SPEC_PATH]
```

Where `$ARGUMENTS` is whatever the user passed (e.g., `--dry-run`, `--plan path/to/plan.md`, `--ambition`, `--evaluator`, `--contract`).

**If you auto-selected a section from the registry above**, append the section spec path to the command:

```bash
./scripts/compound/build.sh $ARGUMENTS docs/tasks/sections/<section-name>.md
```

This tells the pipeline to use the section spec as primary context, bypassing report analysis.

If the script exits with an error, report the failure clearly and suggest next steps.
If the script completes successfully, report the completion status.

**Note:** The pipeline prints `[CHECKPOINT]` messages at key stages for observability. These are informational only — the pipeline continues autonomously.
