# Skills Catalog

Curated pointers to validated, high-quality skills ready to port into any project
created from LaunchPad.

Skills are **not stored locally** — they live at their upstream sources. This folder
contains a catalog file listing recommended skills with links and descriptions, so
you can browse what's available and port what you need.

## How It Works

1. Browse [CATALOG.md](CATALOG.md) to find skills worth porting
2. Run the port command listed for that skill
3. The `/lp-port-skill` workflow handles everything: fetching, adapting to project
   conventions, validating against 16 quality criteria, generating eval scenarios,
   and registering in CLAUDE.md and AGENTS.md

## Harness Skills vs Catalog Skills

**Harness skills** (15 skills in `.claude/skills/`) auto-load in every project and power
the LaunchPad workflow:

1. `brainstorming` — structured brainstorming sessions
2. `commit` — stage, quality-gate, and commit workflow
3. `compound-docs` — structured problem documentation
4. `creating-agents` — agent creation and skill-to-agent conversion
5. `creating-skills` — 7-phase Meta-Skill Forge methodology
6. `document-review` — brainstorm/plan document review
7. `frontend-design` — distinctive, production-grade frontend interfaces
8. `imgup` — lightweight image hosting for quick sharing
9. `prd` — Product Requirements Document generation
10. `rclone` — cloud file management
11. `react-best-practices` — 70 rules across 9 categories
12. `responsive-design` — responsive-first spec injection
13. `stripe-best-practices` — Stripe integration patterns
14. `tasks` — PRD-to-JSON task conversion
15. `web-design-guidelines` — 100+ accessibility/performance/UX rules

**Catalog skills** (listed in CATALOG.md) are recommendations — curated pointers to
external skills worth porting. They stay inert until explicitly ported into a project
with `/lp-port-skill`.
