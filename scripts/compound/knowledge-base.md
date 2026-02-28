# Compound Product - Knowledge Base

This file is updated by agents during compound loops. It accumulates reusable patterns, gotchas, and institutional knowledge that persists across iterations.

## Installation

Compound Product scripts live in `scripts/compound/`. Configuration is in `scripts/compound/config.json`.

## Usage

### Full Pipeline (Report to PR)

```bash
./scripts/compound/auto-compound.sh
```

Pipeline: find latest report -> analyze for #1 priority -> create branch -> generate PRD -> convert to tasks -> run loop -> create PR.

### Dry Run

```bash
./scripts/compound/auto-compound.sh --dry-run
```

Shows what would be done without making changes.

### Execution Loop Only

If you already have `prd.json`:

```bash
./scripts/compound/loop.sh [max_iterations]
```

### Autonomous Agent Loop

For long-running autonomous execution:

```bash
./scripts/compound/loop.sh [max_iterations]
```

### Using Skills

Create a PRD:

```
Load the prd skill. Create a PRD for [feature description]
```

Convert PRD to tasks:

```
Load the tasks skill. Convert [path/to/prd.md] to prd.json
```

## Configuration

`scripts/compound/config.json` fields:

| Field            | Description                          | Default                           |
| ---------------- | ------------------------------------ | --------------------------------- |
| `reportsDir`     | Where to find report markdown files  | `./docs/reports`                  |
| `outputDir`      | Where prd.json and progress.txt live | `./scripts/compound`              |
| `qualityChecks`  | Commands to run after each task      | `["pnpm typecheck", "pnpm test"]` |
| `maxIterations`  | Max loop iterations before stopping  | `25`                              |
| `branchPrefix`   | Prefix for created branches          | `compound/`                       |
| `analyzeCommand` | Custom analysis script (optional)    | `""`                              |

## Codebase Patterns

<!-- Agents: Add discovered patterns here during compound loops -->
