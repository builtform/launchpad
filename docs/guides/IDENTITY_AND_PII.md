# Identity & PII

This guide covers identity management for projects scaffolded via
LaunchPad's v2.1 pipeline. It documents what persists in git history,
when to remove it, and how.

## What persists in git history

When `/lp-pick-stack` and `/lp-update-identity` write the 7 kernel
files (LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, README.md,
SECURITY.md, AGENTS.md, CLAUDE.md), identity values land in those
files and are committed alongside the rest of your project. Even
after `/lp-update-identity` rewrites these files, the OLD values
remain reachable via `git log -p` until git history is rewritten.

Concretely: `LICENSE` carries `copyright_holder` + `project_name` +
license body; `CONTRIBUTING.md` and `SECURITY.md` carry `email`;
`README.md` carries `repo_url`. All of these are committed to the
project's git history.

## When to remove

You may need to scrub identity values from git history when:

- The copyright holder changes (employer change, organization fork,
  legal name correction).
- A real email was committed when PII opt-out was intended.
- A repository URL was committed before the project moved hosts.
- A contributor's PII opt-in is reversed.

`/lp-update-identity` updates the LATEST commit's identity but does
NOT rewrite history. For full removal you need `git filter-repo`.

## How to remove (git filter-repo recipe)

`git filter-repo` is the modern, supported successor to
`git filter-branch`. Install via `brew install git-filter-repo` (macOS),
`apt install git-filter-repo` (Debian/Ubuntu), or `pip install git-filter-repo`.

Example: replace `old@example.com` with `pii-opt-out@example.invalid`
across all history:

```bash
echo 'old@example.com==>pii-opt-out@example.invalid' > replacements.txt
git filter-repo --replace-text replacements.txt
```

Multi-replacement file:

```
old@example.com==>pii-opt-out@example.invalid
Old Name==>Pii Opt Out
https://github.com/old-org/old-repo==>https://github.com/new-org/new-repo
```

After running `git filter-repo` the rewritten history must be
force-pushed (which breaks downstream clones; coordinate with
collaborators).

## `--quiet` flag escape note

The `/lp-update-identity --quiet` flag suppresses the PII WARN print
in the engine's output, but it does NOT remove the persistence in
git history. The WARN is informational only; the actual removal
mechanism is `git filter-repo` per the recipe above.

## Limits

- Force-pushed history breaks downstream clones; collaborators must
  re-clone or rebase.
- GitHub's "ghost" commits (PRs, comments, etc.) outside the main
  refs may retain old identity values; review GitHub's data export
  if comprehensive removal is required.
- Backups (server-side, mirrors, archive sites) may retain old
  history beyond your filter-repo reach.
