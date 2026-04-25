---
name: lp-compound-docs
description: "Process skill for structured problem documentation. Defines 14-category taxonomy, YAML schema, and resolution templates for docs/solutions/. Loaded by /lp-learn."
---

# Compound Docs Skill

Process methodology for capturing resolved problems into structured, searchable solution documents.

## 14 Categories

| Category            | Description                                                     |
| ------------------- | --------------------------------------------------------------- |
| `api_issue`         | API endpoint bugs, request/response issues, middleware problems |
| `auth_issue`        | Authentication, authorization, session management               |
| `build_issue`       | Build failures, compilation errors, bundling problems           |
| `config_issue`      | Configuration errors, environment variable issues               |
| `data_issue`        | Data corruption, migration failures, query issues               |
| `deployment_issue`  | Deploy failures, infrastructure, hosting issues                 |
| `design_pattern`    | UI/UX patterns, component architecture, design system           |
| `frontend_issue`    | React, Next.js, CSS, client-side rendering issues               |
| `integration_issue` | Third-party service, API integration, webhook issues            |
| `performance_issue` | Slow queries, memory leaks, bundle size, rendering perf         |
| `pipeline_issue`    | CI/CD, build pipeline, automation workflow issues               |
| `security_issue`    | Vulnerabilities, secrets exposure, auth bypass                  |
| `test_issue`        | Test failures, flaky tests, test infrastructure                 |
| `type_issue`        | TypeScript type errors, inference failures, generics            |

## 16 Components

`nextjs_app_router`, `nextjs_api_routes`, `nextjs_middleware`, `hono_api`, `prisma_schema`, `prisma_migrations`, `prisma_client`, `react_components`, `tailwind_styles`, `typescript_config`, `eslint_config`, `turborepo_pipeline`, `pnpm_workspace`, `vercel_deployment`, `ci_cd_pipeline`, `design_system`

## Resolution Document Structure

See `references/yaml-schema.md` for the full YAML frontmatter schema.
See `assets/resolution-template.md` for the document template.

### Required Sections

1. **Problem** — What went wrong, error messages, reproduction steps
2. **Root Cause Analysis** — Why it happened, what was misunderstood
3. **Solution** — What fixed it, code changes, configuration changes
4. **What Failed First** — Approaches tried that didn't work and why
5. **Prevention Strategy** — How to prevent recurrence (tests, tooling, docs, patterns)
6. **Related Documentation** — Links to related solution docs, external references

## Quality Gate

YAML frontmatter MUST validate against `references/yaml-schema.md` before writing:

- `category` must be one of 14 valid values
- `component` must be one of 16 valid values
- `root_cause` must be one of 17 valid values
- `resolution_type` must be one of 10 valid values
- `severity` must be critical, high, medium, or low
- `tags` must be a non-empty array
- `date` must be YYYY-MM-DD format

If validation fails, report the specific field and value that failed — do not write the file.

## Secret Scanning

Before writing, scan the assembled document for:

- API keys (sk-, rk*live*, ghp\_, AKIA patterns)
- Tokens and passwords (password=, token=, secret=)
- Connection strings (://user:pass@host)
- Internal URLs and IP addresses

Replace any matches with `[REDACTED]`.
