---
name: lp-pull-launchpad
description: "Pull upstream LaunchPad scaffold updates (template-cloned projects only) using delta patching with conflict resolution"
---

# Pull Launchpad Updates

Pull upstream LaunchPad **scaffold** updates (compound scripts, CI workflows, init wizard improvements) using delta patching.

Plugin content — commands, agents, skills — updates separately via `/plugin marketplace update builtform` + uninstall + reinstall. This command does NOT touch the plugin cache.

## Step 0: Audience gate

This command only applies to template-cloned LaunchPad projects. Check for scaffold presence:

1. If `scripts/setup/pull-upstream.launchpad.sh` is missing AND `scripts/compound/build.sh` is missing, refuse with:

   > "`/lp-pull-launchpad` updates the template scaffold (compound scripts, CI workflows, init wizard), which only exists in template-cloned projects. You're on a plugin-only install — plugin content updates via `/plugin marketplace update builtform` followed by uninstall + reinstall. Restart Claude Code after reinstall."

2. Otherwise continue to Execution.

## Execution

Run the pull script and relay all output to the user:

    bash scripts/setup/pull-upstream.launchpad.sh

If the `launchpad` remote is not configured:

    git remote add launchpad https://github.com/builtform/launchpad.git
    git remote set-url --push launchpad DISABLE

Then re-run.

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
- If anchor didn't advance (conflicts existed), note that re-running `/lp-pull-launchpad`
  after resolving conflicts will advance it

## Key Concepts

- Anchor: `.launchpad/upstream-commit` — last synced LaunchPad SHA
- Categories: NEW, CLEAN, CONFLICT, DELETED, SKIPPED
- Anchor advances only when all files resolved and zero conflicts remain
- Rollback: `git checkout -- .` restores pre-sync state
