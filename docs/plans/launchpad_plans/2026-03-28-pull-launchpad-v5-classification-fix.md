# Fix: Pull-LaunchPad Script v5 — Dual Hash Comparison + Manifest-Based Exclusion

**Date:** 2026-03-28
**Branch:** `fix/pull-launchpad-classification`
**Status:** Plan — final (incorporates all reviewer feedback)
**Fixes:** v4 classification accuracy — false CONFLICTs, missing NEW upstream comparison, template files in report
**Builds on:** v4 (direct comparison, no patching) which is already implemented and working

---

## Problem

Real-world testing of v4 on BuiltForm (anchor `534e808` → `7d83de0`) revealed classification accuracy issues:

1. **Missing NEW upstream comparison.** The script only compares downstream against OLD upstream to decide CLEAN vs CONFLICT. It never checks if downstream already matches NEW upstream. Result: 11+ files that were manually copied from LaunchPad and are identical to the NEW upstream show as CONFLICT instead of being silently skipped.

2. **No exclusion list.** Template files (`*.template.md`), `init-project.sh`, and project-identity files (`CLAUDE.md`, `AGENTS.md`, `README.md`, etc.) that diverge by design after initialization appear in the report. These files "have their own life" after init and should never appear in sync results.

3. **Inflated report.** The combination of (1) and (2) produced a report with 42 items + 20 skips when the actionable list should be ~10-15 items.

### Evidence from BuiltForm test run (2026-03-28)

| Category | Count | Accurate?                                                                                              |
| -------- | ----- | ------------------------------------------------------------------------------------------------------ |
| NEW      | 11    | Mostly — but includes files that should be excluded (DESIGN_SYSTEM.md, METHODOLOGY.md created by init) |
| CLEAN    | 13    | Accurate                                                                                               |
| CONFLICT | 17    | ~11 are false — match NEW upstream (manually copied from LaunchPad)                                    |
| DELETED  | 1     | Accurate                                                                                               |
| SKIPPED  | 20    | Inflated — includes template files and project-identity files that should be excluded entirely         |

---

## Solution

Three changes across two scripts:

### Fix 1: Dual Hash Comparison (in `pull-upstream.launchpad.sh`)

Add a NEW upstream hash check as the **first comparison** in classification:

```
For each changed file:
  1. Is file excluded? → skip entirely (not even SKIPPED)  [only for A and M status]
  2. Does downstream match NEW upstream? → silently skip (already up to date)
  3. (Only if doesn't match NEW) Does downstream match OLD upstream? → CLEAN
  4. (Matches neither) → CONFLICT
```

### Fix 2: Manifest-Based Exclusion (in `init-project.sh` + `pull-upstream.launchpad.sh`)

Instead of a hardcoded exclusion list in the pull script, `init-project.sh` generates `.launchpad/init-touched-files` — a manifest of every file it customizes. The pull script reads this manifest at runtime. Only 2 glob patterns remain hardcoded (`*.template.md`, `*.template`) since template source files are deleted during init and can't be in any manifest.

**Exclusions apply only to `A` (added) and `M` (modified) statuses, NOT to `D` (deleted).** If upstream explicitly deletes a file, downstream should see it even if the file is in the exclusion list.

### Fix 3: Auto-Present Conflict Diffs (in `pull-launchpad.md`)

Update the command file so Claude automatically presents diffs for all CONFLICT files — no extra step for the user to request them.

---

## Files to Modify

| File                                       | Action                                                                     |
| ------------------------------------------ | -------------------------------------------------------------------------- |
| `scripts/setup/init-project.sh`            | **Add** manifest generation (`.launchpad/init-touched-files`) near the end |
| `scripts/setup/pull-upstream.launchpad.sh` | **Rewrite** Step 4 classification + add manifest reading                   |
| `.claude/commands/pull-launchpad.md`       | **Update** conflict handling — auto-present diffs                          |

---

## Implementation

### Change 1: Manifest Generation in `init-project.sh`

Insert after the upstream-commit write (line 352) and before "Step 2/3 — Swapping template files":

```bash
# Write init-touched manifest for upstream sync exclusion.
# pull-upstream.launchpad.sh reads this to know which files were customized
# during init and should be excluded from sync results.
cat > .launchpad/init-touched-files << 'MANIFEST'
# Files customized, created, or moved by init-project.sh.
# pull-upstream.launchpad.sh excludes these from sync (A/M status only).
# One file path per line. Lines starting with # are comments.
#
# --- Project identity (placeholder-injected) ---
README.md
LICENSE
CODE_OF_CONDUCT.md
CHANGELOG.md
CONTRIBUTING.md
CLAUDE.md
AGENTS.md
package.json
# --- App source (project metadata injected) ---
apps/web/src/app/layout.tsx
# --- Commands/skills (project name injected) ---
.claude/commands/define-product.md
.claude/skills/tasks/SKILL.md
scripts/agent_hydration/hydrate.sh
docs/architecture/CI_CD.md
# --- Structure files (template refs removed by init) ---
docs/architecture/REPOSITORY_STRUCTURE.md
scripts/maintenance/check-repo-structure.sh
# --- Files created fresh by init ---
.claude/settings.json
docs/skills-catalog/skills-usage.json
docs/skills-catalog/skills-index.md
docs/architecture/DESIGN_SYSTEM.md
docs/tasks/sections/.gitkeep
# --- Files moved/deleted by init (original paths) ---
scripts/setup/init-project.sh
docs/guides/METHODOLOGY.md
docs/guides/HOW_IT_WORKS.md
MANIFEST

# Conditional entries based on init choices
if [ "$REPO_VISIBILITY" = "public" ]; then
  echo "SECURITY.md" >> .launchpad/init-touched-files
fi

info "Created .launchpad/init-touched-files (upstream sync exclusion manifest)"
```

Then at line 460 (where `docs/guides/.gitkeep` is conditionally created), append:

```bash
if [ ! "$(ls -A docs/guides/ 2>/dev/null)" ]; then
  touch docs/guides/.gitkeep
  echo "docs/guides/.gitkeep" >> .launchpad/init-touched-files  # <-- ADD THIS
  info "Created docs/guides/.gitkeep"
fi
```

**Why a static heredoc + conditional appends instead of dynamic tracking:** The list of files init touches is known and stable. A single heredoc block is easier to read, audit, and maintain than 30+ `track_init()` calls scattered across 900 lines. The 2 conditional entries (SECURITY.md for public repos, .gitkeep if created) are appended separately.

**When to update this block:** Only when `init-project.sh` is modified to customize, create, or move a NEW file that didn't exist before. Adding a new `replace_in_file` call on an already-listed file doesn't require changes.

### Change 2: Manifest-Based Exclusion in `pull-upstream.launchpad.sh`

Replace the current hardcoded exclusion logic with manifest reading. Insert between Step 3 and Step 4:

```bash
# ---------------------------------------------------------------------------
# Step 3.5: Load Exclusion Manifest
# ---------------------------------------------------------------------------
# init-project.sh writes .launchpad/init-touched-files listing every file it
# customized. These files diverge by design and should not appear in sync
# results. Exclusions apply to A (added) and M (modified) only — upstream
# deletions (D) are always shown.

EXCLUDED_PATHS=()
EXCLUDED_MANIFEST=".launchpad/init-touched-files"
if [ -f "$EXCLUDED_MANIFEST" ]; then
  while IFS= read -r line; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" == \#* ]] && continue
    EXCLUDED_PATHS+=("$line")
  done < "$EXCLUDED_MANIFEST"
fi

is_excluded() {
  local file="$1"
  # Glob patterns for template source files (deleted by init, never in manifest)
  case "${file##*/}" in
    *.template.md|*.template) return 0 ;;
  esac
  # Check exact paths from manifest
  local p
  for p in "${EXCLUDED_PATHS[@]}"; do
    [ "$file" = "$p" ] && return 0
  done
  return 1
}
```

### Change 3: Classification Rewrite (Step 4)

Replace the current classification loop:

```bash
# ---------------------------------------------------------------------------
# Step 4: Classify via Dual Hash Comparison (OLD + NEW upstream)
# ---------------------------------------------------------------------------
CLEAN_FILES=()
CONFLICTED=()
NEW_FILES=()
DELETED_FILES=()
SKIPPED=()

while IFS=$'\t' read -r status file; do
  # Exclusions apply to A and M only — deletions always shown
  if [ "$status" != "D" ] && is_excluded "$file"; then
    continue
  fi

  case "$status" in
    A)
      if [ ! -f "$file" ]; then
        # Upstream added, downstream doesn't have it
        NEW_FILES+=("$file")
      else
        # Upstream added, downstream already has it — compare against NEW upstream
        NEW_HASH=$(git rev-parse "$NEW_SHA:$file" 2>/dev/null || echo "none")
        CURRENT_HASH=$(git hash-object "$file" 2>/dev/null || echo "none")
        if [ "$NEW_HASH" = "$CURRENT_HASH" ]; then
          # Already matches new upstream — silently skip
          continue
        else
          # Different from new upstream — conflict
          CONFLICTED+=("$file")
        fi
      fi
      ;;
    D)
      if [ -f "$file" ]; then
        DELETED_FILES+=("$file")
      fi
      ;;
    M)
      if [ ! -f "$file" ]; then
        # Upstream modified, downstream removed it
        SKIPPED+=("$file")
      else
        # Step A: Does downstream already match NEW upstream?
        NEW_HASH=$(git rev-parse "$NEW_SHA:$file" 2>/dev/null || echo "none")
        CURRENT_HASH=$(git hash-object "$file" 2>/dev/null || echo "none")
        if [ "$NEW_HASH" = "$CURRENT_HASH" ]; then
          # Already up to date — silently skip
          continue
        fi

        # Step B: Does downstream match OLD upstream? (never modified)
        OLD_HASH=$(git rev-parse "$OLD_SHA:$file" 2>/dev/null || echo "none")
        if [ "$OLD_HASH" = "$CURRENT_HASH" ]; then
          # Downstream never modified this file — safe to update
          CLEAN_FILES+=("$file")
        else
          # Downstream modified AND doesn't match new upstream — conflict
          CONFLICTED+=("$file")
        fi
      fi
      ;;
    *)
      warn "Unknown git status '$status' for $file — skipping"
      ;;
  esac
done <<< "$CHANGED_FILES"
```

**Key changes from v4:**

1. `is_excluded()` reads from `.launchpad/init-touched-files` manifest — no hardcoded list
2. Exclusions only apply to A/M status, not D
3. Uses `git hash-object "$file"` (working tree) instead of `git rev-parse "HEAD:$file"` (committed) — correctly handles untracked files
4. For `A` files with collision: compare against NEW upstream. If match → silent `continue`
5. For `M` files: check NEW upstream FIRST, then fall back to OLD upstream for CLEAN vs CONFLICT
6. Catch-all `*` case warns on unexpected git status codes (T, C, U)

### Change 4: Zero-Items Message Update

```bash
if [ "$TOTAL_ITEMS" -eq 0 ]; then
  info "No applicable changes (upstream changes are to excluded or already-synced files)."
  echo "$NEW_SHA" > "$ANCHOR_FILE"
  exit 0
fi
```

### Change 5: Update `pull-launchpad.md` — Auto-Present Conflict Diffs

Replace the current "After the script completes" section:

```markdown
## After the script completes

### If CONFLICT files exist — automatically present diffs

Do NOT wait for the user to ask. For each CONFLICT file, immediately:

1. Run `git diff $OLD_SHA $NEW_SHA -- $file` to get what upstream changed
2. Read the current downstream file to understand local customizations
3. Present each conflict to the user:
   - **File:** `path/to/file`
   - **What upstream changed:** summarize the upstream diff
   - **What you customized:** summarize what differs from the original LaunchPad version
   - **Recommendation:** accept upstream, keep local, or merge specific sections
4. If the user wants to merge, help them edit the file to incorporate upstream changes
   while preserving their customizations

### After conflicts are resolved (or if none exist)

- Remind the user to review staged changes with `git diff --cached` and commit
- If anchor didn't advance (conflicts existed), note that re-running `/pull-launchpad`
  after resolving conflicts will advance it
```

---

## What Changes from v4

| v4 Behavior                               | v5 Behavior                                         | Why                                               |
| ----------------------------------------- | --------------------------------------------------- | ------------------------------------------------- |
| Hardcoded exclusion list (none)           | Reads `.launchpad/init-touched-files` manifest      | Self-maintaining — init generates the list        |
| Only compares downstream vs OLD upstream  | Compares downstream vs NEW upstream FIRST, then OLD | Catches files already up-to-date                  |
| Uses `git rev-parse "HEAD:$file"`         | Uses `git hash-object "$file"`                      | Correctly handles untracked files                 |
| Template files appear as SKIPPED          | Excluded entirely (glob patterns)                   | Diverge by design, never actionable               |
| Project identity files appear as CONFLICT | Excluded entirely (manifest)                        | "Have their own life" after init                  |
| Files matching NEW upstream → CONFLICT    | Silently skipped via `continue`                     | Already up-to-date, no action needed              |
| Conflict diffs shown on user request      | Auto-presented immediately by Claude                | Saves a step for every conflict                   |
| No manifest generated by init             | init writes `.launchpad/init-touched-files`         | Pull script stays in sync with init automatically |

---

## Expected BuiltForm Report After Fix

```
════════════════════════════════════════════════════
  LaunchPad Upstream Changes
  534e808 → 7d83de0
════════════════════════════════════════════════════

── NEW (upstream added, you don't have) ───────────
  [1]  docs/plans/2026-03-27-pull-launchpad-rewrite.md  +446 lines
  [2]  docs/reports/2026-03-13-harness-...               +172 lines
  [3]  docs/reports/2026-03-25-anthropic-...             +155 lines
  [4]  docs/reports/2026-03-25-evaluator-simplified-...  +524 lines
  [5]  docs/reports/2026-03-25-evaluator-...             +758 lines
  [6]  docs/reports/2026-03-26-compound-...              +707 lines
  [7]  docs/skills-catalog/CATALOG.md                    +119 lines
  [8]  docs/skills-catalog/README.md                     +25 lines

── CLEAN (upstream updated, you haven't modified) ─
  [9]   .claude/commands/commit.md                +57/-7 lines
  [10]  .claude/commands/create-skill.md          +2 lines
  [11]  .claude/commands/define-architecture.md   +227/-164 lines
  [12]  .claude/commands/inf.md                   +17/-1 lines
  [13]  .claude/commands/port-skill.md            +8/-7 lines
  [14]  .claude/commands/update-skill.md          +12 lines
  [15]  .claude/skills/creating-skills/SKILL.md   +7/-2 lines
  [16]  .claude/skills/creating-skills/references/METHODOLOGY.md  +1/-1 lines
  [17]  .claude/skills/creating-skills/references/PORTING-GUIDE.md +20/-13 lines
  [18]  .claude/skills/prd/SKILL.md               +3/-3 lines
  [19]  scripts/compound/analyze-report.sh        +1/-1 lines
  [20]  scripts/compound/auto-compound.sh         +198/-33 lines
  [21]  scripts/compound/config.json              +7/-1 lines

── CONFLICT (both sides changed) ──────────────────
  [22]  docs/plans/2026-03-27-ce-plugin-phase-0-review-agent-config.md
  [23]  docs/plans/2026-03-27-ce-plugin-phase-1-review-agent-fleet.md
       ℹ View upstream:  git show 7d83de0:<file>
       ℹ View old:       git show 534e808:<file>

── DELETED (upstream removed) ─────────────────────
  [24]  .claude/commands/create_plan.md

════════════════════════════════════════════════════
  8 NEW · 13 CLEAN · 2 CONFLICT · 1 DELETED · 0 SKIPPED
════════════════════════════════════════════════════
```

Then Claude automatically presents diffs for the 2 CONFLICT files before the user has to ask.

---

## Edge Cases

| Edge Case                                     | Handling                                                                                                                                    |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | --- | --------- |
| Excluded file receives upstream fix           | User won't see A/M changes. But upstream deletions (D) ARE shown. Manifest is visible in `.launchpad/init-touched-files` for manual review. |
| New file added to init-project.sh             | Add the path to the manifest heredoc in init-project.sh. Existing downstream projects create the manifest manually.                         |
| `.launchpad/init-touched-files` doesn't exist | `EXCLUDED_PATHS` stays empty — no exclusions applied. Script works as v4 (everything shown). Graceful fallback.                             |
| Downstream file matches NEW upstream          | Silently skipped — already up to date                                                                                                       |
| Downstream file matches OLD upstream          | CLEAN — presented for user approval                                                                                                         |
| Downstream file matches neither               | CONFLICT — Claude auto-presents diff                                                                                                        |
| Upstream deletes an excluded file             | Deletion IS shown (exclusions only for A/M)                                                                                                 |
| Untracked file exists, upstream adds same     | `git hash-object` correctly hashes it (v4 bug fix)                                                                                          |
| `package.json`                                | Excluded via manifest — init customizes name field. Dependency updates require manual review of upstream package.json.                      |
| Manifest has comments or blank lines          | Skipped by `while read` loop (`[[ -z                                                                                                        |     | \#\* ]]`) |

---

## Testing

| Test                                  | Expected                                              |
| ------------------------------------- | ----------------------------------------------------- |
| File matching NEW upstream (A status) | Silently skipped                                      |
| File matching NEW upstream (M status) | Silently skipped                                      |
| File matching OLD upstream (M status) | CLEAN — user approves                                 |
| File matching neither (M status)      | CONFLICT — diff auto-presented                        |
| File in manifest (A or M status)      | Excluded — not in report                              |
| File in manifest (D status)           | SHOWN in DELETED                                      |
| Template file (glob match)            | Excluded                                              |
| No manifest file exists               | No exclusions — graceful fallback                     |
| `package.json`                        | Excluded via manifest                                 |
| Zero actionable items                 | "No applicable changes", anchor advances              |
| BuiltForm full sync                   | ~24 items (8 NEW + 13 CLEAN + 2 CONFLICT + 1 DELETED) |
| Unknown git status (T, C, U)          | Warning logged, file skipped                          |

---

## Review History

**v4 (2026-03-27):** critical reviewer, performance-oracle, code-simplicity-reviewer

- Replaced `git apply` with hash comparison + direct file copy

**v5 (2026-03-28):** critical reviewer, code-simplicity-reviewer, performance-oracle

- Dual hash comparison (NEW + OLD upstream)
- Manifest-based exclusion (`.launchpad/init-touched-files`) instead of hardcoded list
- `git hash-object` for working tree hash (handles untracked files)
- Exclusions only for A/M, not D (upstream deletions always visible)
- Auto-present conflict diffs in `pull-launchpad.md`
- `package.json` excluded via manifest (init customizes name field)
- Hardcoded glob patterns in `case` statement (not via variable — bash `case` doesn't expand `|` from variables)
- Catch-all `*` case for unknown git status codes
- Simplified `is_excluded()` — 2 inline globs + manifest loop
- Removed `EXCLUDED_COUNT` display from summary (YAGNI)
- Fixed BuiltForm rollback to use `git clean -fd` instead of fragile `rm -f` list
- Performance: no bottlenecks found, all concerns NEGLIGIBLE
