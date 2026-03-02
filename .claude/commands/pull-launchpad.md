# Pull Launchpad Updates

Pull the latest updates from the upstream Launchpad repository into safe (non-customized) directories.

## Usage

- `/pull-launchpad` — fetch, diff, and interactively apply upstream changes

## Execution

Run the pull script and relay all output:

```bash
bash scripts/setup/pull-upstream.launchpad.sh
```

If the `launchpad` remote is not configured, help the user set it up:

```bash
git remote add launchpad https://github.com/thinkinghand/launchpad.git
```

Then re-run the pull script.

After applying updates, summarize what changed and suggest the user review with `git diff --cached` before committing.
