# Pull Launchpad Updates

Pull the latest upstream LaunchPad changes into this project using delta patching. Only shows what changed in LaunchPad since the last sync — downstream customizations are preserved.

## Usage

- `/pull-launchpad` — fetch, classify, and interactively apply upstream changes

## Execution

### Step 1: Run the pull script

```bash
bash scripts/setup/pull-upstream.launchpad.sh
```

Relay all output to the user.

**Exit codes:**

- **0**: Success — no conflicts, script handled everything. Summarize what was applied and stop.
- **1**: Error — dirty tree, missing anchor, missing remote, etc. Relay the error message and stop.
- **2**: Conflicts exist — the script applied what it could but some files have conflicts. Continue to Step 2.

If the `launchpad` remote is not configured, help the user set it up:

```bash
git remote add launchpad https://github.com/thinkinghand/launchpad.git
```

Then re-run the pull script.

### Step 2: Analyze conflicts (only if exit code 2)

The script outputs a `CONFLICTS:` line listing the conflicting files and `OLD_SHA`/`NEW_SHA` values.

For each conflicting file, read three versions to understand the conflict:

```bash
git show $OLD_SHA:$file   # what upstream looked like when this project last synced
git show $NEW_SHA:$file   # what upstream looks like now
cat $file                  # what this project has (with downstream customizations)
```

For each conflict, explain to the user:

- What the downstream project customized in this file and why
- What upstream changed and how it interacts with the customizations
- Recommend one of: apply (and resolve conflict markers), skip (will reappear next sync), or manually merge specific sections

### Step 3: Apply user-selected conflicts

For conflicts the user wants to apply:

```bash
git diff $OLD_SHA $NEW_SHA -- $file | git apply -3
```

This creates conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) where the patches overlap. Tell the user to resolve the markers, then review with `git diff --cached` and commit.

For conflicts the user skips: note that they will reappear on the next `/pull-launchpad` run (the anchor only advances when all files are resolved).

## Key Concepts

- **Anchor file:** `.launchpad/upstream-commit` stores the LaunchPad commit SHA this project was last synced from. The delta is computed from this anchor to current `launchpad/main`.
- **Categories:** NEW (safe to add), CLEAN (patch applies cleanly), CONFLICT (needs resolution), DELETED (upstream removed).
- **Anchor policy:** The anchor advances only when all files in the delta are resolved. Partial syncs leave the anchor unchanged — skipped files reappear next time.
- **Rollback:** If anything goes wrong: `git checkout -- .` restores the pre-sync state.
