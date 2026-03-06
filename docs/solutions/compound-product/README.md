# Compound Product Learnings

Structured learnings from autonomous compound product runs. Each feature run produces a learnings file with YAML frontmatter for cataloging.

## How It Works

1. During a compound run, the agent writes learnings to `progress.txt`
2. After the run completes, `auto-compound.sh` extracts learnings into a structured file here
3. Patterns worth promoting are staged in `patterns/promoted-patterns.md`
4. Periodically, promoted patterns are added to the root `CLAUDE.md`

## File Structure

```
compound-product/
  README.md                              # This file
  _template.md                           # Template for learnings files
  patterns/
    promoted-patterns.md                 # Staging area for CLAUDE.md candidates
  [feature-slug]/
    [feature-slug]-YYYY-MM-DD.md         # One file per compound run
```

## YAML Frontmatter Schema

| Field             | Required | Description                                        |
| ----------------- | -------- | -------------------------------------------------- |
| `title`           | Yes      | Human-readable title of the feature                |
| `feature`         | Yes      | Feature slug (kebab-case)                          |
| `date`            | Yes      | ISO date of the run                                |
| `branch`          | Yes      | Git branch name                                    |
| `report_source`   | Yes      | Report file that triggered this run                |
| `problem_type`    | Yes      | Always `compound_product_learning`                 |
| `severity`        | Yes      | `info` / `warning` / `critical`                    |
| `tasks_total`     | Yes      | Total number of tasks                              |
| `tasks_completed` | Yes      | Number of tasks completed                          |
| `iterations_used` | Yes      | How many loop iterations ran                       |
| `max_iterations`  | Yes      | Max iterations from config                         |
| `categories`      | Yes      | Array of categories (e.g., `api`, `ui`, `testing`) |
| `tags`            | No       | Additional tags                                    |
| `modules_touched` | No       | Array of file paths modified                       |
| `pr_url`          | No       | Pull request URL                                   |

## Searching Learnings

Search learnings by YAML frontmatter fields using grep:

```bash
# Find learnings by category
grep -rl 'categories:.*api' docs/solutions/compound-product/

# Find learnings by severity
grep -rl 'severity: critical' docs/solutions/compound-product/

# Find learnings by feature
grep -rl 'feature: auth' docs/solutions/compound-product/
```

The `problem_type: compound_product_learning` field distinguishes these from other solution files.
