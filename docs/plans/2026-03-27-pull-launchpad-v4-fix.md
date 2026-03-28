# Fix: Pull-LaunchPad Script v4 — Direct Comparison, No Patching

**Date:** 2026-03-27
**Branch:** `fix/pull-launchpad-reliability`
**Status:** Plan — final (incorporates all reviewer feedback)
**Fixes:** Unreliable `git apply -3` that corrupts files with conflict markers

---

## Problem

The v3 pull script uses `git apply -3` for classification and application. Real-world testing on BuiltForm revealed three design flaws:

1. **`--check` disagrees with actual apply.** Sequential patch application changes context — files classified CLEAN fail during application.
2. **Added-file collisions can't be three-way merged.** No base version exists for upstream-added files that downstream already has.
3. **`git apply -3` injects conflict markers** (`<<<<<<< ours`) into working files as a side effect of failing — corrupting the codebase before the user can decide.

---

## Solution

**Eliminate `git apply` entirely.** Replace with:

- **Git hash comparison** for classification (compare SHA-1 hashes, not file content — no trailing-newline bugs, no memory concerns, handles binary files)
- **Direct file copy** (`git show > file`) for application of CLEAN and NEW files
- **Print `git show` commands** for CONFLICT files (never touch the user's file — they retrieve and merge manually)
- **Every file requires explicit user approval** — nothing auto-applies

---

## Review History

**v4 reviewed by:** critical reviewer, performance-oracle, code-simplicity-reviewer (2026-03-27)

**Incorporated feedback:**

- Hash comparison instead of string comparison (all three reviewers)
- Merge COLLISION into CONFLICT (simplicity reviewer)
- Drop `.upstream` companion files — just print `git show` commands (simplicity reviewer + user decision)
- Add `chmod +x` propagation for executable files (critical reviewer)
- Anchor does NOT advance when any CONFLICT files exist, even if user selected them (critical reviewer)
- Remove exit code 2 handoff — script is self-contained (simplicity reviewer)
- Drop `.upstream` rollback tracking — no companion files created (simplicity reviewer)

---

## Files to Modify

| File                                       | Action                                                               |
| ------------------------------------------ | -------------------------------------------------------------------- |
| `scripts/setup/pull-upstream.launchpad.sh` | **Rewrite** Steps 4, 5, and 6                                        |
| `.claude/commands/pull-launchpad.md`       | **Simplify** — run script, relay output, help merge conflicts if any |

---

## Implementation

### Classification (Step 4 rewrite)

Replace all `git apply` usage with git hash comparison:

```bash
CLEAN_FILES=()
CONFLICTED=()
NEW_FILES=()
DELETED_FILES=()
SKIPPED=()

while IFS=$'\t' read -r status file; do
  case "$status" in
    A)
      if [ ! -f "$file" ]; then
        # Upstream added, downstream doesn't have it
        NEW_FILES+=("$file")
      else
        # Upstream added, downstream already has it — compare content
        NEW_HASH=$(git rev-parse "$NEW_SHA:$file" 2>/dev/null || echo "none")
        CURRENT_HASH=$(git hash-object "$file" 2>/dev/null || echo "none")
        if [ "$NEW_HASH" = "$CURRENT_HASH" ]; then
          # Identical content — silently skip
          SKIPPED+=("$file")
        else
          # Different content — conflict
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
        # Compare downstream against old upstream via hash
        OLD_HASH=$(git rev-parse "$OLD_SHA:$file" 2>/dev/null || echo "none")
        CURRENT_HASH=$(git hash-object "$file" 2>/dev/null || echo "none")
        if [ "$OLD_HASH" = "$CURRENT_HASH" ]; then
          # Downstream never modified this file
          CLEAN_FILES+=("$file")
        else
          # Downstream has customizations
          CONFLICTED+=("$file")
        fi
      fi
      ;;
  esac
done <<< "$CHANGED_FILES"
```

**5 categories:** NEW, CLEAN, CONFLICT, DELETED, SKIPPED. No COLLISION — merged into CONFLICT with a descriptive message.

No `git apply`, no `--check`, no optimistic fast-path. Classification is 100% deterministic — hash comparison cannot disagree with itself.

### Presentation (Step 5 rewrite)

Structured, organized report output:

```
════════════════════════════════════════════════════
  LaunchPad Upstream Changes
  534e808 → 6c1ebd9
════════════════════════════════════════════════════

── NEW (upstream added, you don't have) ───────────
  [1]  scripts/compound/evaluate.sh           +104 lines
  [2]  scripts/compound/grading-criteria.md    +50 lines

── CLEAN (upstream updated, you haven't modified) ─
  [3]  .claude/commands/commit.md              +57/-7 lines
  [4]  .claude/commands/create-skill.md         +2 lines

── CONFLICT (both sides changed) ──────────────────
  [5]  CLAUDE.md                    you customized · upstream also changed
  [6]  AGENTS.md                    you customized · upstream also changed
       ℹ View upstream:  git show 6c1ebd9:<file>
       ℹ View old:       git show 534e808:<file>

── DELETED (upstream removed) ─────────────────────
  [7]  .claude/commands/create_plan.md

── SKIPPED (upstream updated, you removed locally) ─
   •  docs/guides/HOW_IT_WORKS.md
   •  scripts/setup/init-project.sh

════════════════════════════════════════════════════
  2 NEW · 2 CLEAN · 2 CONFLICT · 1 DELETED · 2 SKIPPED
════════════════════════════════════════════════════
```

**Skipped files have no selection numbers** — they are informational only. The `git show` hint appears once under the CONFLICT header. Line stats are computed lazily via `git diff --numstat` only for displayed files.

### Application (Step 6 rewrite)

**No `git apply` anywhere. No conflict markers ever.**

| Category     | Application                                                                                                                |
| ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **NEW**      | `mkdir -p "$(dirname "$file")" && git show "$NEW_SHA:$file" > "$file"`                                                     |
| **CLEAN**    | `git show "$NEW_SHA:$file" > "$file"` (overwrite — downstream never changed it)                                            |
| **CONFLICT** | **Do not touch the file.** Print: "Skipping CONFLICT file: $file. Retrieve upstream version with: git show $NEW_SHA:$file" |
| **DELETED**  | `rm -f -- "$file"`                                                                                                         |

**Permission propagation** — after writing NEW or CLEAN files:

```bash
if git ls-tree "$NEW_SHA" -- "$file" | grep -q '^100755'; then
  chmod +x "$file"
fi
```

**Anchor policy:** Anchor advances to `NEW_SHA` only when:

- All selectable files were processed (user didn't quit early)
- AND zero CONFLICT files exist in the delta

If any CONFLICT files exist (whether the user selected them or not), the anchor does NOT advance. The user must resolve conflicts and re-run, or manually advance with `echo '$NEW_SHA' > .launchpad/upstream-commit`.

**Rollback:** Track only NEW files created during the run. On Ctrl+C: `git checkout -- .` restores modified files, loop over created files and `rm` them.

### Command file simplification

Replace the current 69-line `.claude/commands/pull-launchpad.md` with ~25 lines:

```markdown
# Pull Launchpad Updates

Pull upstream LaunchPad changes using delta patching.

## Execution

Run the pull script and relay all output to the user:

    bash scripts/setup/pull-upstream.launchpad.sh

If the `launchpad` remote is not configured:

    git remote add launchpad https://github.com/thinkinghand/launchpad.git

Then re-run.

## After the script completes

- If CONFLICT files exist, help the user resolve them:
  - Read the current file and the upstream version (via git show)
  - Explain what the user customized and what upstream changed
  - Help merge the changes or recommend which version to keep
- Remind the user to review staged changes with `git diff --cached` and commit
- If anchor didn't advance (conflicts exist), note that re-running after
  resolving conflicts will advance it

## Key Concepts

- Anchor: `.launchpad/upstream-commit` — last synced LaunchPad SHA
- Categories: NEW, CLEAN, CONFLICT, DELETED, SKIPPED
- Anchor advances only when all files resolved and zero conflicts remain
- Rollback: `git checkout -- .` restores pre-sync state
```

Steps 2 and 3 (conflict analysis, apply user-selected conflicts) are removed. The script handles everything. Claude just helps with conflict resolution after the fact.

---

## What Gets Removed from Current Script

| Removed                                       | Why                                                       |
| --------------------------------------------- | --------------------------------------------------------- |
| `git apply -3 --check` (classification)       | Replaced by git hash comparison                           |
| `git apply -3` (application)                  | Replaced by direct file copy                              |
| Optimistic fast-path                          | Unreliable, unnecessary with hash comparison              |
| `MODIFIED_FILES` array                        | No longer needed — files go directly to CLEAN or CONFLICT |
| `HAS_CONFLICTS` flag                          | No longer needed — conflicts don't produce broken files   |
| Exit code 2 handoff                           | Removed — script is self-contained                        |
| `CONFLICTS:` / `OLD_SHA=` / `NEW_SHA=` output | Removed — no external parsing needed                      |
| `.upstream` companion files                   | Never implemented (dropped before coding)                 |

---

## Edge Cases

| Edge Case                                                              | Handling                                                                                                                                        |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Identical collision (upstream added file, downstream has same content) | Silently skipped — hash comparison detects identical content                                                                                    |
| File permission changes                                                | `chmod +x` propagated for executable files after copy                                                                                           |
| User selects CONFLICT files                                            | Script prints the `git show` command but does NOT modify the file                                                                               |
| Partial application (user quits early)                                 | Anchor does NOT advance                                                                                                                         |
| CONFLICT files exist in delta                                          | Anchor does NOT advance even if user processed all other files                                                                                  |
| Re-run after resolving conflicts                                       | Previously-conflicting files are now CLEAN (content matches new upstream after manual merge) or still CONFLICT — script re-classifies correctly |

---

## Testing

| Test                                          | Expected                                                      |
| --------------------------------------------- | ------------------------------------------------------------- |
| NEW file, doesn't exist downstream            | Copied after user approval                                    |
| CLEAN file, hash matches old upstream         | Overwritten with new upstream after user approval             |
| CONFLICT file, hash differs from old upstream | Not touched. `git show` command printed.                      |
| Identical collision                           | Silently skipped                                              |
| Different collision                           | Classified as CONFLICT                                        |
| DELETED file                                  | Removed after user approval                                   |
| SKIPPED file (downstream removed)             | Logged informatively, no selection number                     |
| Executable file upstream                      | `chmod +x` applied after copy                                 |
| Rollback mid-application                      | NEW files cleaned up, modified files restored                 |
| Anchor with zero conflicts                    | Advances to NEW_SHA                                           |
| Anchor with any conflicts                     | Does NOT advance                                              |
| Re-run after manual conflict resolution       | Previously-conflicting files reclassified correctly           |
| Report format                                 | Clean organized output with headers, categories, summary line |
