# YAML Frontmatter Schema

All solution documents in `docs/solutions/` must have valid YAML frontmatter matching this schema.

## Required Fields

```yaml
---
title: string # Problem title (concise, searchable)
date: YYYY-MM-DD # Date resolved
category: enum # One of 14 categories
component: enum # One of 16 components
root_cause: enum # One of 17 root cause values
resolution_type: enum # One of 10 resolution types
severity: enum # critical | high | medium | low
tags: string[] # Searchable tags (non-empty)
modules_touched: string[] # File paths affected
---
```

## Valid Enum Values

### category (14)

`api_issue`, `auth_issue`, `build_issue`, `config_issue`, `data_issue`, `deployment_issue`, `design_pattern`, `frontend_issue`, `integration_issue`, `performance_issue`, `pipeline_issue`, `security_issue`, `test_issue`, `type_issue`

### component (16)

`nextjs_app_router`, `nextjs_api_routes`, `nextjs_middleware`, `hono_api`, `prisma_schema`, `prisma_migrations`, `prisma_client`, `react_components`, `tailwind_styles`, `typescript_config`, `eslint_config`, `turborepo_pipeline`, `pnpm_workspace`, `vercel_deployment`, `ci_cd_pipeline`, `design_system`

### root_cause (17)

`missing_index`, `wrong_api`, `scope_issue`, `async_timing`, `memory_leak`, `config_error`, `logic_error`, `test_isolation`, `missing_validation`, `missing_permission`, `inadequate_documentation`, `missing_tooling`, `incomplete_setup`, `missing_relation`, `missing_eager_load`, `concurrency_issue`, `missing_pipeline_step`

### resolution_type (10)

`code_fix`, `config_change`, `dependency_update`, `schema_migration`, `test_addition`, `documentation_update`, `pipeline_improvement`, `permission_fix`, `performance_optimization`, `architecture_refactor`
