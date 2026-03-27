# Recommended Skills

Curated list of high-quality skills ready to port into any project created from LaunchPad.
Use `/port-skill` to bring any of these into your project.

## How to Port

```
/port-skill based on <source-url-or-path>
```

---

## Frontend & Design

| Skill                 | Description                                                                                                                                                                                                   | Source                                                                                     | Port Command                                                                                 |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| frontend-design       | Distinctive, production-grade frontend interfaces that avoid generic AI aesthetics. Enforces a Design Brief before coding, bans generic fonts and cliched color schemes, requires named aesthetic directions. | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/frontend-design` |
| impeccable            | Extends frontend-design with 17 commands: /polish, /audit, typography, color, layout, motion. The "upgrade" to frontend-design.                                                                               | [pbakaus/impeccable](https://github.com/pbakaus/impeccable)                                | `/port-skill based on https://github.com/pbakaus/impeccable`                                 |
| web-design-guidelines | 100+ rules for accessibility, performance, and UX compliance auditing.                                                                                                                                        | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)                    | `/port-skill based on https://github.com/vercel-labs/agent-skills`                           |
| react-best-practices  | 40+ optimization rules across 8 categories: waterfalls, bundle size, server/client performance.                                                                                                               | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)                    | `/port-skill based on https://github.com/vercel-labs/agent-skills`                           |
| composition-patterns  | React architectural patterns: compound components, state lifting, boolean prop elimination.                                                                                                                   | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)                    | `/port-skill based on https://github.com/vercel-labs/agent-skills`                           |
| theme-factory         | Design system and theme generation.                                                                                                                                                                           | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/theme-factory)   | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/theme-factory`   |

---

## Development Workflow & Code Quality

| Skill             | Description                                                                                                                                       | Source                                                                                      | Port Command                                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| superpowers       | Complete dev methodology: brainstorming, git worktrees, plan writing, strict TDD (RED-GREEN-REFACTOR). 20+ skills in the suite. Port selectively. | [obra/superpowers](https://github.com/obra/superpowers)                                     | `/port-skill based on https://github.com/obra/superpowers`                   |
| code-review       | Automated PR review with multiple specialized agents.                                                                                             | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |
| pr-review-toolkit | PR review agents for comments, tests, types, and code quality.                                                                                    | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |
| feature-dev       | 7-phase feature development workflow.                                                                                                             | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |
| code-simplifier   | Code simplification tools for reducing complexity.                                                                                                | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |

---

## Testing & Quality Assurance

| Skill          | Description                                                                                                  | Source                                                                                      | Port Command                                                                                |
| -------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| webapp-testing | Web application testing workflows.                                                                           | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/webapp-testing)   | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/webapp-testing` |
| playwright     | Browser automation and E2E testing.                                                                          | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official`                |
| shannon        | Autonomous white-box pentester. 96% exploit success rate. Finds injection, auth bypass, XSS, SSRF. ~$50/run. | [KeygraphHQ/shannon](https://github.com/KeygraphHQ/shannon)                                 | `/port-skill based on https://github.com/KeygraphHQ/shannon`                                |

---

## Document & Content Generation

| Skill           | Description                                                  | Source                                                                                     | Port Command                                                                                 |
| --------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| docx            | Create, read, and edit Word documents.                       | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/docx)            | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/docx`            |
| pdf             | PDF handling and form filling.                               | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/pdf)             | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/pdf`             |
| pptx            | PowerPoint creation.                                         | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/pptx)            | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/pptx`            |
| xlsx            | Excel spreadsheet manipulation.                              | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/xlsx)            | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/xlsx`            |
| doc-coauthoring | Structured co-authoring for docs, proposals, and tech specs. | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring) | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring` |

---

## DevOps & Deployment

| Skill                   | Description                                                                                | Source                                                                                      | Port Command                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| vercel-deploy-claimable | Framework-agnostic Vercel deployment with transferable ownership. Supports 40+ frameworks. | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)                     | `/port-skill based on https://github.com/vercel-labs/agent-skills`           |
| commit-commands         | Git workflow automation: commit, push, PR creation.                                        | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |

---

## Meta / Skill Creation

| Skill         | Description                                                                                                                       | Source                                                                                      | Port Command                                                                               |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| skill-creator | Interactive skill creation — asks about workflow, generates SKILL.md. Compare with LaunchPad's built-in `/create-skill` for gaps. | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/skill-creator)    | `/port-skill based on https://github.com/anthropics/skills/tree/main/skills/skill-creator` |
| plugin-dev    | Comprehensive toolkit for developing Claude Code plugins.                                                                         | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official`               |
| hookify       | Create custom hooks to prevent unwanted behaviors.                                                                                | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official`               |

---

## Integrations & External Services

| Skill    | Description                            | Source                                                                                      | Port Command                                                                 |
| -------- | -------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| supabase | Supabase backend integration.          | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |
| stripe   | Stripe payment processing.             | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |
| linear   | Linear issue tracking integration.     | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |
| slack    | Slack messaging integration.           | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |
| firebase | Firebase and Google Cloud integration. | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | `/port-skill based on https://github.com/anthropics/claude-plugins-official` |

---

## Mobile Development

| Skill                   | Description                                                                            | Source                                                                  | Port Command                                                       |
| ----------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ |
| react-native-guidelines | 16 rules across 7 sections: performance, layout, animations, images, state management. | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | `/port-skill based on https://github.com/vercel-labs/agent-skills` |

---

## Discovery Resources

Curated lists for finding additional skills beyond this catalog:

| Resource                   | Description                                 | URL                                                                                         |
| -------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------- |
| awesome-claude-code        | Major curated list of Claude Code resources | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)     |
| awesome-agent-skills       | 500+ agent skills catalog                   | [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)         |
| antigravity-awesome-skills | 1,234+ skills collection                    | [sickn33/antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) |
| awesome-claude-skills      | Growing curated skills list                 | [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills)         |

---

## Contributing

To add a skill to this catalog:

1. Port it into at least one project using `/port-skill` and confirm it passes all 16 quality gates
2. Add a row to the appropriate category table above
3. Include a clear description and the upstream source link
