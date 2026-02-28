#!/bin/bash
# AI Hydration Script (minimal — preserves context tokens)
# Usage: Run `./scripts/agent_hydration/hydrate.sh` from the repo root
#        or from any directory — it resolves the repo root automatically.
#
# Design: Only loads what every session needs. PRD, tech stack, and app
# READMEs are referenced in CLAUDE.md's Progressive Disclosure table —
# Claude reads them on-demand when the task requires it.

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=============================================="
echo "  PROJECT MONOREPO - AI HYDRATION"
echo "=============================================="
echo ""
echo "You are working on this project's MonoRepo."
echo "Loading minimal session context (repo structure + active tasks)."
echo ""

echo "=============================================="
echo "  1/2: Repository Structure"
echo "=============================================="
cat "$REPO_ROOT/docs/architecture/REPOSITORY_STRUCTURE.md"
echo ""

echo "=============================================="
echo "  2/2: docs/tasks/TODO.md (Pending Tasks)"
echo "=============================================="
cat "$REPO_ROOT/docs/tasks/TODO.md"
echo ""

echo "=============================================="
echo "  HYDRATION COMPLETE"
echo "=============================================="
echo ""
echo "Context loaded: repo structure + active tasks."
echo "PRD, tech stack, and app READMEs are available on-demand"
echo "via CLAUDE.md Progressive Disclosure — no need to preload."
echo ""
echo "Confirm you are hydrated and ask for the next task."
echo "Say it in a funny way - your humor, your choice."
