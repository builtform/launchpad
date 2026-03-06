# Implement Next Feature

Fully autonomous pipeline: reads the latest report, picks the top priority, creates a feature branch, generates a PRD, implements tasks, runs quality gates, creates a PR, and monitors CI until green.

## Usage

- `/inf` — run the full pipeline
- `/inf --dry-run` — preview the priority pick without making changes

## Execution

Run the pipeline script and relay all output:

```bash
./scripts/compound/auto-compound.sh $ARGUMENTS
```

Where `$ARGUMENTS` is whatever the user passed (e.g., `--dry-run`).

If the script exits with an error, report the failure clearly and suggest next steps.
If the script completes successfully, report the PR URL from the output.

**Note:** The pipeline prints `[CHECKPOINT]` messages at key stages (report analysis, PRD creation, task conversion, execution loop completion) for observability. These are informational only — the pipeline continues autonomously. A developer watching the terminal can Ctrl+C at a checkpoint to pause and review artifacts before they are consumed by later steps.
