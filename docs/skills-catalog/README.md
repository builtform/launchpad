# Skills Catalog

Curated pointers to validated, high-quality skills ready to port into any project
created from LaunchPad.

Skills are **not stored locally** — they live at their upstream sources. This folder
contains a catalog file listing recommended skills with links and descriptions, so
you can browse what's available and port what you need.

## How It Works

1. Browse [CATALOG.md](CATALOG.md) to find skills worth porting
2. Run the port command listed for that skill
3. The `/port-skill` workflow handles everything: fetching, adapting to project
   conventions, validating against 16 quality criteria, generating eval scenarios,
   and registering in CLAUDE.md and AGENTS.md

## Harness Skills vs Catalog Skills

**Harness skills** (in `.claude/skills/`) auto-load in every project and power the
LaunchPad workflow: skill creation, commit workflow, PRD generation, task management.

**Catalog skills** (listed in CATALOG.md) are recommendations — curated pointers to
external skills worth porting. They stay inert until explicitly ported into a project
with `/port-skill`.
