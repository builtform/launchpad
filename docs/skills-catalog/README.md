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

**Harness skills** (16 skills shipped under `plugins/launchpad/skills/`, installed
to `${CLAUDE_PLUGIN_ROOT}/skills/` after `/plugin install launchpad@builtform`)
auto-load in every project and power the LaunchPad workflow:

1. `lp-brainstorming` — structured brainstorming sessions
2. `lp-commit` — stage, quality-gate, and commit workflow
3. `lp-compound-docs` — structured problem documentation
4. `lp-creating-agents` — agent creation and skill-to-agent conversion
5. `lp-creating-skills` — 7-phase Meta-Skill Forge methodology
6. `lp-document-review` — brainstorm/plan document review
7. `lp-frontend-design` — distinctive, production-grade frontend interfaces
8. `lp-imgup` — lightweight image hosting for quick sharing
9. `lp-prd` — Product Requirements Document generation
10. `lp-rclone` — cloud file management
11. `lp-react-best-practices` — 70 rules across 9 categories
12. `lp-responsive-design` — responsive-first spec injection
13. `lp-step-zero` — shared lite-mode prereq check the L2 commands compose with
14. `lp-stripe-best-practices` — Stripe integration patterns
15. `lp-tasks` — PRD-to-JSON task conversion
16. `lp-web-design-guidelines` — 100+ accessibility/performance/UX rules

**Catalog skills** (listed in CATALOG.md) are recommendations — curated pointers to
external skills worth porting. They stay inert until explicitly ported into a project
with `/lp-port-skill`.
