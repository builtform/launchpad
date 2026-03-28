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
