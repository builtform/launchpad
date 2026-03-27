# Upstream Pull Mechanism Rewrite: Delta Patching

**Date:** 2026-03-27
**Branch:** `feat/pull-launchpad-rewrite`
**Status:** Plan — final (v3, post-review fixes)

---

## Overview

The current `pull-upstream.launchpad.sh` has two fundamental problems:

1. **Incomplete coverage.** It only syncs 4 hardcoded directories (`.claude/commands`, `.claude/skills`, `scripts/compound`, `.github/workflows`), missing upstream-managed files like `CLAUDE.md`, `AGENTS.md`, `docs/guides/`, `scripts/setup/`, and `scripts/maintenance/`.
2. **Destructive application.** It runs `git checkout launchpad/main -- <dir>` which wholesale replaces files, clobbering any downstream customizations (e.g., BuiltForm's custom sub-agents table in `CLAUDE.md`).

**New approach: Upstream Delta Patching.** Instead of diffing upstream vs downstream (which surfaces intentional customizations as noise), diff **upstream-old vs upstream-new** to isolate only what changed in LaunchPad. Then try to apply each change and let `git apply -3` determine whether it succeeds or conflicts — no prediction logic needed.

The mechanism relies on `.launchpad/upstream-commit` — a file containing the LaunchPad commit SHA the project was initialized from (or last synced from). This is the anchor point for computing the upstream delta.

---

## Review History

**v1 reviewed by:** code-simplicity-reviewer, performance-oracle (2026-03-27)

**Key changes in v2:**

- Collapsed 7 classification categories to 4 (CLEAN absorbs COMPATIBLE; CONFLICT absorbs DIVERGED)
- Replaced `git archive` + `diff -ruN` with `git diff` + `git show` (O(delta) not O(repo), no temp dirs)
- Replaced line-range overlap prediction with try-and-report via `git apply -3`
- Simplified two-pass JSON protocol to single-pass script with conflict handoff
- Simplified sub-agent dispatch: inline analysis for ≤3 conflicts, batched agents for >3
- Removed YAGNI items: binary file detection, move-tracking heuristic, 40% divergence threshold

**v2 re-reviewed by:** code-simplicity-reviewer, performance-oracle (2026-03-27)

**Key changes in v3:**

- **Bug fix:** Replaced `echo | while read` (subshell loses variables) with `while read <<<` (here-string, current shell)
- **Design fix:** Anchor only advances when ALL files are resolved (applied or explicitly skipped), not on partial application — prevents permanently losing skipped files from future deltas
- **Simplification:** Dropped `pull-launchpad.md` move to `.launchpad/` — the command stays in `.claude/commands/` and the delta patching mechanism handles updates naturally. Eliminated Steps 1b/1c.
- **Performance:** Added optimistic fast-path — try applying the full patch first; only fall back to per-file classification if it fails. Zero-conflict syncs are O(1) instead of O(N).
- **UX:** Added category-level selection (`[n]ew`, `[c]lean`, `[a]ll`) for large syncs
- **Simplification:** Always analyze conflicts inline (Claude reads files directly). Removed sub-agent batching threshold — unnecessary orchestration for a rare scenario.
- **Simplification:** Removed `git apply --reject` fallback — skip failed files and log error instead
- **Cleanup:** Deferred `--numstat` to presentation step (lazy computation, not upfront)

---

## Files to Modify

| File                                        | Action      | What Changes                                                                  |
| ------------------------------------------- | ----------- | ----------------------------------------------------------------------------- |
| `scripts/setup/pull-upstream.launchpad.sh`  | **Rewrite** | Replace 40-line naive script with 6-step delta patching pipeline (~200 lines) |
| `scripts/setup/init-project.sh`             | **Modify**  | Write `.launchpad/upstream-commit` during init                                |
| `.claude/commands/pull-launchpad.md`        | **Modify**  | Update to run script, analyze conflicts inline, handle user selection         |
| `docs/guides/HOW_IT_WORKS.md`               | **Modify**  | Document the new pull mechanism                                               |
| `docs/architecture/REPOSITORY_STRUCTURE.md` | **Modify**  | Add `upstream-commit` to `.launchpad/` section                                |

**New files created during `init-project.sh` (in downstream projects):**

| File                         | Purpose                                                      |
| ---------------------------- | ------------------------------------------------------------ |
| `.launchpad/upstream-commit` | Stores the LaunchPad commit SHA the project was created from |

---

## Implementation Steps

### Step 1: Update `init-project.sh`

**Write upstream commit anchor.**

After the existing `.launchpad/version` write (line 346), add:

```bash
# Write upstream commit SHA for delta patching during pull-upstream
UPSTREAM_SHA="$(git rev-parse HEAD)"
echo "$UPSTREAM_SHA" > .launchpad/upstream-commit
info "Created .launchpad/upstream-commit ($UPSTREAM_SHA)"
```

This captures the exact LaunchPad commit the downstream project was created from. All future `pull-upstream` runs diff from this anchor forward.

No changes to `pull-launchpad.md` — it stays in `.claude/commands/` and receives updates via the delta patching mechanism like any other upstream file.

---

### Step 2: Rewrite `scripts/setup/pull-upstream.launchpad.sh`

The new script implements a 6-step pipeline. It runs as a single pass. The script handles everything for the common case (no conflicts). When conflicts exist, it outputs a conflict list and exits with code 2 so the Claude Code command can enrich with analysis.

---

#### Script Step 1: Clean Working Tree Guard

```bash
if [ -n "$(git status --porcelain)" ]; then
  error "Working tree is dirty. Commit or stash your changes, then re-run."
  error "  /commit — to commit your current work"
  error "  git stash — to temporarily shelve changes"
  exit 1
fi
```

Hard gate. No "continue anyway?" option. A dirty working tree makes rollback impossible and conflict markers unmanageable. This guard also makes the Ctrl+C trap handler (`git checkout -- .`) safe — there are no pre-existing changes to lose.

---

#### Script Step 2: Read Anchor and Fetch

```bash
ANCHOR_FILE=".launchpad/upstream-commit"

if [ ! -f "$ANCHOR_FILE" ]; then
  error "No .launchpad/upstream-commit file found."
  error "This project was likely created before the delta patching rewrite."
  error "To fix: create the file manually with the LaunchPad commit SHA your project was initialized from."
  error "  echo '<sha>' > .launchpad/upstream-commit"
  error "If unsure, use the earliest LaunchPad commit in your git log:"
  error "  git log --oneline --all | tail -1"
  exit 1
fi

OLD_SHA="$(cat "$ANCHOR_FILE")"

if ! git remote get-url launchpad >/dev/null 2>&1; then
  error "No 'launchpad' remote found."
  error "Add it with: git remote add launchpad https://github.com/thinkinghand/launchpad.git"
  exit 1
fi

git fetch launchpad
NEW_SHA="$(git rev-parse launchpad/main)"

if [ "$OLD_SHA" = "$NEW_SHA" ]; then
  info "Already up to date (anchor: ${OLD_SHA:0:7})."
  exit 0
fi

echo "Upstream delta: ${OLD_SHA:0:7} -> ${NEW_SHA:0:7}"
```

---

#### Script Step 3: Compute Upstream Delta Using Git

Use `git diff` directly against the object store — no temp directories, no file extraction, O(delta) not O(repo).

```bash
# Get the list of changed files with change type
CHANGED_FILES=$(git diff --name-status "$OLD_SHA" "$NEW_SHA")
```

This gives us `A` (added), `M` (modified), `D` (deleted) per file. Line stats (`--numstat`) are computed lazily during the presentation step, only for files that will be displayed.

For any specific file's content at either version:

```bash
git show "$OLD_SHA:$file"   # old upstream version
git show "$NEW_SHA:$file"   # new upstream version
```

No temp dirs. No `diff -ruN`. No monolithic patch file.

---

#### Script Step 4: Classify (Try-and-Report)

Instead of predicting conflicts with line-range analysis, **try the patch and let git report the result.**

**4 classification categories:**

| Category     | Condition                                                          | How Determined                                            |
| ------------ | ------------------------------------------------------------------ | --------------------------------------------------------- |
| **NEW**      | File added upstream, doesn't exist downstream                      | `git diff --name-status` shows `A` + file missing locally |
| **CLEAN**    | File modified upstream, patch applies cleanly                      | `git apply -3 --check` succeeds                           |
| **CONFLICT** | File modified upstream, patch fails (downstream edited same lines) | `git apply -3 --check` fails                              |
| **DELETED**  | File deleted upstream                                              | `git diff --name-status` shows `D`                        |

An additional informational note for files that don't exist downstream (upstream modified a file the downstream project removed) — logged as "skipped" in the output, not a separate category.

**Optimistic fast-path:** Try applying the full patch for all modified files at once. If it succeeds, all modified files are CLEAN — skip per-file classification entirely (O(1) instead of O(N)). Fall back to per-file only when the full patch fails.

```bash
CLEAN_FILES=()
CONFLICTED=()
NEW_FILES=()
DELETED_FILES=()
SKIPPED=()

# Collect files by type
MODIFIED_FILES=()
while IFS=$'\t' read -r status file; do
  case "$status" in
    A)
      if [ ! -f "$file" ]; then
        NEW_FILES+=("$file")
      fi
      ;;
    D)
      if [ -f "$file" ]; then
        DELETED_FILES+=("$file")
      fi
      ;;
    M)
      if [ ! -f "$file" ]; then
        SKIPPED+=("$file")
      else
        MODIFIED_FILES+=("$file")
      fi
      ;;
  esac
done <<< "$CHANGED_FILES"

# Optimistic fast-path: try all modified files at once
if [ ${#MODIFIED_FILES[@]} -gt 0 ]; then
  FULL_PATCH=$(git diff "$OLD_SHA" "$NEW_SHA" -- "${MODIFIED_FILES[@]}")
  if echo "$FULL_PATCH" | git apply -3 --check 2>/dev/null; then
    # Everything applies cleanly
    CLEAN_FILES=("${MODIFIED_FILES[@]}")
  else
    # Fall back to per-file classification
    for file in "${MODIFIED_FILES[@]}"; do
      PATCH=$(git diff "$OLD_SHA" "$NEW_SHA" -- "$file")
      if echo "$PATCH" | git apply -3 --check 2>/dev/null; then
        CLEAN_FILES+=("$file")
      else
        CONFLICTED+=("$file")
      fi
    done
  fi
fi
```

Key: `git apply -3 --check` does a dry run — no files are modified. All classification happens before any changes are applied. The here-string `<<< "$CHANGED_FILES"` avoids the subshell variable loss bug that piping into `while` would cause.

---

#### Script Step 5: Interactive Presentation

Compute line stats lazily for display:

```bash
FILE_STATS=$(git diff --numstat "$OLD_SHA" "$NEW_SHA")
```

Present results grouped by category, with category-level selection shortcuts:

```
LaunchPad upstream changes (b6a7eb1 -> 4f03dde):

NEW (safe to add):
  [1] scripts/compound/evaluate.sh          (+104 lines)
  [2] scripts/compound/grading-criteria.md   (+50 lines)
  [3] scripts/hooks/audit-skills.sh          (+45 lines)

CLEAN (applies cleanly, local edits preserved):
  [4] .claude/commands/create-skill.md       (+2 lines)
  [5] .claude/commands/commit.md             (+66 lines)

CONFLICT (needs manual resolution):
  [6] CLAUDE.md                              (+8/-3 lines, patch cannot apply cleanly)
  [7] AGENTS.md                              (+5/-2 lines, patch cannot apply cleanly)

DELETED upstream:
  [8] .claude/commands/old-command.md

Skipped (you removed these files locally):
  - docs/guides/METHODOLOGY.md (moved to .launchpad/ during init)

Apply which? [a]ll, [n]ew, [c]lean, comma-separated numbers, or [q]uit:
```

Category shortcuts: `n` applies all NEW, `c` applies all CLEAN, `a` applies all. These can be combined: `n,c` applies all NEW and CLEAN. Individual numbers work for fine-grained control.

When invoked via the Claude Code command (not raw bash), Claude presents the results with enriched analysis for CONFLICT files.

---

#### Script Step 6: Apply and Update Anchor

**Before any changes:** create a backup tag for rollback (skip if user selected zero files).

```bash
if [ ${#SELECTED[@]} -eq 0 ]; then
  echo "No changes selected."
  exit 0
fi

git tag _pre-upstream-sync
```

**Apply by category:**

| Category     | Application Method                                                       |
| ------------ | ------------------------------------------------------------------------ |
| **NEW**      | `mkdir -p $(dirname "$file")` then `git show "$NEW_SHA:$file" > "$file"` |
| **CLEAN**    | `git diff "$OLD_SHA" "$NEW_SHA" -- "$file" \| git apply -3`              |
| **CONFLICT** | Same as CLEAN — creates conflict markers where patches overlap           |
| **DELETED**  | `rm "$file"`                                                             |

If `git apply -3` fails during actual application (not just `--check`), log the error and skip the file. The user can manually retrieve the content with `git show $NEW_SHA:$file`.

**Anchor update policy:** The anchor advances to `NEW_SHA` only when **all files in the delta have been resolved** — either applied or explicitly skipped by the user. If the user selects a subset and quits, the anchor does NOT advance. This ensures skipped files reappear in the next sync's delta.

```bash
# Check if all files were resolved
TOTAL_FILES=$(( ${#NEW_FILES[@]} + ${#CLEAN_FILES[@]} + ${#CONFLICTED[@]} + ${#DELETED_FILES[@]} ))
RESOLVED_FILES=${#SELECTED[@]}

if [ "$RESOLVED_FILES" -eq "$TOTAL_FILES" ]; then
  echo "$NEW_SHA" > .launchpad/upstream-commit
  echo "Anchor updated to ${NEW_SHA:0:7} (all files resolved)."
else
  echo "Anchor NOT updated (${RESOLVED_FILES}/${TOTAL_FILES} files resolved)."
  echo "Skipped files will reappear on next sync. To advance the anchor manually:"
  echo "  echo '$NEW_SHA' > .launchpad/upstream-commit"
fi

# Stage only the files we touched (not git add -A)
for file in "${SELECTED[@]}"; do
  git add "$file"
done
if [ -f .launchpad/upstream-commit ] && git diff --cached --quiet -- .launchpad/upstream-commit 2>/dev/null; then
  : # anchor unchanged, don't stage
else
  git add .launchpad/upstream-commit
fi

echo ""
echo "Upstream changes applied. Review with 'git diff --cached', then commit."
echo "If something went wrong: git checkout -- . && git tag -d _pre-upstream-sync"
```

After the user commits successfully, the backup tag can be deleted:

```bash
git tag -d _pre-upstream-sync 2>/dev/null || true
```

---

### Step 3: Update `/pull-launchpad` command

Update `.claude/commands/pull-launchpad.md` to orchestrate the full flow. The command uses a **single-pass with conflict handoff** — the bash script handles everything for non-conflict cases; Claude only activates when conflicts need semantic analysis.

```
Step 1: Run the bash script
  - bash scripts/setup/pull-upstream.launchpad.sh
  - If exit code 0: no conflicts, script handled everything. Relay output and stop.
  - If exit code 1: error (dirty tree, no anchor, etc). Relay message and stop.
  - If exit code 2: conflicts exist. Script printed the list. Continue to Step 2.

Step 2: Analyze conflicts inline
  - Read the conflict list from script output
  - For each conflicting file, read three versions:
      git show $OLD_SHA:$file  (old upstream)
      git show $NEW_SHA:$file  (new upstream)
      cat $file                (downstream)
  - Explain what downstream customized and how upstream changes interact
  - Recommend: apply (and resolve conflicts), skip, or apply manually

Step 3: Present enriched results
  - Show CONFLICT files with analysis inline
  - Ask user which to apply
  - For selected conflicts: apply the patch (creates conflict markers)
  - Remind user to resolve markers, review with git diff, and commit
```

All conflict analysis is done inline by Claude reading the files directly — no sub-agent dispatch. This is simpler and sufficient since conflicts should be rare and few.

---

### Step 4: Update documentation

**`docs/guides/HOW_IT_WORKS.md`:**

- Document the upstream delta patching mechanism
- Explain the `.launchpad/upstream-commit` anchor file
- Describe the 4 classification categories (NEW, CLEAN, CONFLICT, DELETED)
- Explain the anchor update policy (advances only when all files resolved)
- Document the clean working tree requirement

**`docs/architecture/REPOSITORY_STRUCTURE.md`:**

- Add `upstream-commit` to the `.launchpad/` section with description: "LaunchPad commit SHA this project was initialized/last synced from. Used by pull-upstream for delta computation."

---

## Edge Cases

| Edge Case                                                             | Handling                                                                                                                                                                                  |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Pre-rewrite downstream project** (no `.launchpad/upstream-commit`)  | Hard error with instructions to manually create the file. Suggest using the LaunchPad commit closest to their init date.                                                                  |
| **LaunchPad remote not configured**                                   | Error with the `git remote add` command to run.                                                                                                                                           |
| **Network failure during fetch**                                      | `set -e` catches it. User re-runs after fixing connectivity.                                                                                                                              |
| **`git apply -3` fails during application**                           | Log the error, skip the file. User can retrieve content with `git show $NEW_SHA:$file`.                                                                                                   |
| **User cancels mid-application** (Ctrl+C)                             | Trap handler runs `git checkout -- .`. Safe because clean-tree guard ensures no pre-existing changes exist. Anchor is NOT updated, so re-running picks up where it left off.              |
| **Files moved during init** (e.g., `METHODOLOGY.md` to `.launchpad/`) | Classified as "skipped" — file doesn't exist at original path. Logged informatively. To get upstream changes, compare manually with `git show launchpad/main:docs/guides/METHODOLOGY.md`. |
| **Empty upstream delta** (OLD_SHA == NEW_SHA)                         | Already handled in Step 2: "Already up to date" and exit.                                                                                                                                 |
| **User selects zero files**                                           | Skip backup tag creation, skip anchor update, exit cleanly.                                                                                                                               |
| **Partial application** (user applies some, skips others)             | Anchor does NOT advance. Skipped files reappear in next sync. User can manually advance anchor when ready.                                                                                |

---

## Rollback Strategy

1. **Before applying:** `git tag _pre-upstream-sync` (only if files were selected)
2. **If anything goes wrong:** `git checkout -- .` (safe due to clean-tree guard)
3. **After successful commit:** `git tag -d _pre-upstream-sync`

The anchor file is only updated when all files are resolved. If the user rolls back, the anchor stays at the old SHA, and re-running picks up the same delta.

---

## Testing Strategy

Test with BuiltForm as the real downstream project.

| Test                                      | Expected Result                                           |
| ----------------------------------------- | --------------------------------------------------------- |
| New files from upstream                   | Added to downstream, no conflicts                         |
| Clean files (no downstream edits)         | Patched in place cleanly                                  |
| Conflict files (overlapping edits)        | Reported as CONFLICT, user decides                        |
| Deleted files upstream                    | Removed when user selects them                            |
| Skipped files (downstream removed)        | Logged informatively, not applied                         |
| Dirty working tree                        | Hard stop, no changes made                                |
| Missing anchor file                       | Clear error with remediation instructions                 |
| Rollback after partial application        | `git checkout -- .` restores pre-sync state               |
| Re-run after rollback                     | Picks up same delta (anchor was not updated)              |
| Zero files selected                       | No backup tag, no anchor update, clean exit               |
| Partial apply (some files, not all)       | Anchor does NOT advance, skipped files reappear next sync |
| Full apply (all files resolved)           | Anchor advances to NEW_SHA                                |
| Zero-conflict sync (optimistic fast-path) | All modified files classified in O(1), no per-file loop   |
| Category-level selection (`n`, `c`, `a`)  | Applies all files in the selected category                |

---

## Out of Scope

- **Automatic conflict resolution.** User resolves manually; analysis provides recommendations but does not auto-edit.
- **Bi-directional sync.** Downstream changes never flow back to LaunchPad.
- **Template variable re-rendering.** LaunchPad uses `{{PLACEHOLDER}}` replacement during init. If upstream adds new placeholders, they appear as-is and the user replaces them manually.
- **Cherry-picking individual upstream commits.** The delta is always computed as a single range (old anchor to current `launchpad/main`). Partial syncs are handled by selecting which files to apply, not which commits.
- **Binary file special handling.** `git diff` detects binary files natively and reports them as such. They are treated as NEW-or-replace without line-level analysis.
