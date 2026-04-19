---
name: lp-learn
description: "Captures learnings from resolved problems into structured solution docs. 5-agent parallel research pipeline with YAML-validated frontmatter."
---
# /lp-learn

Captures learnings from resolved problems into the structured knowledge base at `docs/solutions/`.

## Usage

```
/lp-learn                              → capture learnings from current session
/lp-learn "fixed the Prisma N+1"      → capture with problem description
```

**Arguments:** `$ARGUMENTS` (optional problem description)

**Auto-invocation:** Triggers on phrases like "that worked", "it's fixed", "the issue was", "root cause was". Suppressed when dispatched by an orchestrator.

---

## Phase 1: Parallel Research (5 inline sub-agents)

Spawn all 5 in parallel. Each returns text only — no file writes.

### 1. Context Analyzer

- Scoped context: problem description + module path
- What module/area is affected?
- What was the original problem?
- What environment/conditions triggered it?
- Optional: reads `.harness/review-summary.md` for suppressed finding patterns
- Returns: module name, problem summary, environment details

### 2. Solution Extractor

- Scoped context: code diff only
- What was tried and failed?
- What ultimately worked?
- What code changes were made? (file paths, diffs)
- Returns: failed approaches, working solution, code changes

### 3. Related Docs Finder

- Scoped context: module name + tags
- Grep `docs/solutions/` by tags/module in frontmatter (pre-filter)
- Read only matching files — do NOT read all files sequentially
- Returns: list of related docs (paths + summaries), duplicate flag

### 4. Prevention Strategist

- Scoped context: root cause + solution summary
- How can this be prevented in the future?
- Suggests: tests, tooling, documentation, pipeline steps, patterns
- Returns: prevention strategies with specificity

### 5. Category Classifier

- Maps to one of 14 categories and assigns component, root_cause, resolution_type
- Returns: category, component, root_cause, resolution_type, severity, tags

## Phase 2: Assemble Document

1. Load `compound-docs` skill for template and taxonomy
2. Merge sub-agent outputs into YAML-frontmatter document
3. **YAML validation gate:** Validate all frontmatter fields against schema. Block write if invalid.
4. **Secret scan:** Before writing, scan for API keys, tokens, passwords, connection strings — redact with `[REDACTED]`
5. Generate filename slug: lowercase, hyphens only, max 50 chars

## Phase 3: Write

- Run `mkdir -p docs/solutions/[category]/` before writing
- Write to `docs/solutions/[category]/YYYY-MM-DD-[slug].md`
- Confirm write with path and summary
- If Related Docs Finder flagged a duplicate: warn and ask to proceed or merge

---

## When Called by /lp-harness-build Step 5

- Reads `${CLAUDE_PLUGIN_ROOT}/bin/compound/progress.txt` + code diff as problem context
- Runs autonomously (no interactive prompts)
- Falls back to `bash ${CLAUDE_PLUGIN_ROOT}/bin/compound/compound-learning.sh` if /lp-learn fails
