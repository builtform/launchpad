# Pairing LaunchPad with MemPalace

[MemPalace](https://github.com/MemPalace/mempalace) is an open-source memory-management tool for AI coding CLIs. It indexes your conversation transcripts and project files into a local vector store and exposes 19 retrieval tools over an MCP server, giving Claude Code (and other CLIs) verbatim recall of what you said three sessions ago.

LaunchPad and MemPalace are independent projects. **LaunchPad does not bundle MemPalace, does not auto-install it, and does not depend on it at runtime.** This guide is a cookbook for users who want to pair them voluntarily — including the LaunchPad maintainer, who uses this exact setup.

## Why pair them

LaunchPad already has a structured knowledge system covering three tiers:

- **Immediate tier** — `.harness/progress.txt` written during `/lp-build`
- **Short-term tier** — `docs/solutions/` written by `/lp-learn` after each build cycle
- **Long-term tier** — `CLAUDE.md` for project-wide principles

What none of those cover is **verbatim transcript recall** — being able to ask "what did we decide about authentication three weeks ago?" and get the actual conversation back. MemPalace fills that gap. Adding MemPalace effectively gives LaunchPad a fourth tier without overlapping any of the existing three.

The combination is also additive in the other direction: MemPalace's `mine` command can ingest LaunchPad's curated `docs/solutions/`, `docs/tasks/sections/`, and `docs/handoffs/` directories, making structured knowledge searchable through MemPalace's same retrieval interface.

## Prerequisites

- **Python 3.9 or later** on your machine. MemPalace is a Python package; LaunchPad is a TypeScript/Node project, so this is a separate runtime requirement.
- **~300 MB of disk per project** for MemPalace's local embedding store
- **Time to read [MemPalace's docs](https://github.com/MemPalace/mempalace)** — this guide assumes you've skimmed their README, particularly the "Scam alert" notice listing official sources

## One-time setup, per machine

```bash
pip install mempalace
```

In Claude Code, install MemPalace as a plugin so the auto-save hooks register:

```
/plugin marketplace add MemPalace/mempalace
/plugin install mempalace@mempalace
```

Restart Claude Code. The Stop and PreCompact hooks now auto-register and will save your session transcripts to MemPalace's local store.

## Per-project setup

For each LaunchPad project where you want MemPalace recall:

```bash
cd <your-launchpad-project>
mempalace init .mempalace
mempalace mine docs/solutions docs/tasks/sections docs/handoffs
echo ".mempalace/" >> .gitignore
```

That's it. The four-line block above is the entire integration.

### Why `.mempalace/` at the project root

LaunchPad already uses three dot-directories for different runtime concerns:

| Directory     | Owner       | Purpose                                                     |
| ------------- | ----------- | ----------------------------------------------------------- |
| `.launchpad/` | LaunchPad   | Harness config (agents.yml, audit.log, secret-patterns.txt) |
| `.harness/`   | LaunchPad   | Runtime artifacts (todos, progress, screenshots)            |
| `.claude/`    | Claude Code | Hooks, settings, project-local prompts                      |
| `.mempalace/` | MemPalace   | Per-project embedding store                                 |

Putting MemPalace's storage at the same level keeps a clean mental model: each tool owns one dot-directory, all of them are gitignored, all of them can be reset independently.

Newly initialized LaunchPad projects (via `init-project.sh`) include `.mempalace/` in the gitignore template by default, so users who choose to install MemPalace later have one less step.

### What to point `mempalace mine` at

LaunchPad maintains structured knowledge in three directories worth indexing:

- **`docs/solutions/`** — frontmatter-tagged solution docs written by `/lp-learn` after each `/lp-build` cycle. Categories, tags, root-causes, and module references make these especially useful through semantic search.
- **`docs/tasks/sections/`** — section specs written by `/lp-shape-section`. Each is a self-contained statement of a feature's intent, scope, and constraints.
- **`docs/handoffs/`** — handoff docs written when work spans multiple sessions or contributors.

Optionally also:

- **`.harness/progress.txt`** — current iteration's running notes (only relevant for active sessions)
- **`docs/architecture/`** — long-lived canonical docs (PRD, TECH_STACK, etc.)

Whether to mine `docs/architecture/` is a judgment call. Those documents are more useful for first-load context than for ad-hoc recall, and they update less frequently — the marginal value of indexing them is lower than for `docs/solutions/`.

## What LaunchPad does NOT use MemPalace for

Some explicit non-uses to avoid confusion:

- **`/lp-learn` does not write to MemPalace.** It writes to `docs/solutions/` as before. MemPalace mines those docs after the fact; the pipeline is unchanged.
- **`/lp-build` does not query MemPalace.** The build loop reads `.launchpad/`, the section spec, and the plan — it does not consult MemPalace's vector store. If you want a build to consider past work, the `learnings-researcher` sub-agent already searches `docs/solutions/` directly.
- **`CLAUDE.md` is not auto-populated from MemPalace.** Long-term principles still live in `CLAUDE.md` and are written by humans (or proposed by AI and reviewed by humans).
- **The three-tier knowledge system is not replaced.** MemPalace adds a _fourth_ tier (verbatim recall); it does not subsume the others.

## Compatibility notes

MemPalace is a fast-moving young project. Some practical caveats:

- **Breaking changes are possible.** MemPalace is currently on the v3.x line and ships frequent releases. If you rely on a specific MemPalace command or output shape, pin a version (`pip install mempalace==3.x.y`).
- **If MemPalace's docs disagree with this guide, trust their docs.** This guide reflects the integration as of LaunchPad v1.0.0; MemPalace's documentation is authoritative for its own API.
- **Gitignore the storage.** A LaunchPad project that accidentally commits `.mempalace/` will balloon by hundreds of megabytes per machine. The default scaffold gitignores it; manually-converted projects need the line added.
- **Privacy.** Everything MemPalace stores is local to the machine that runs `mempalace mine`. It does not transmit transcripts to external services (per their published architecture). If your repository contains sensitive data, the same controls you apply to your `.harness/` and `.launchpad/` directories should apply to `.mempalace/`.

## When NOT to install MemPalace

Some signals that MemPalace is not worth setting up for a particular project:

- The project is short-lived and you don't expect to return to it
- You don't context-switch — your current session always has the relevant history loaded
- You are on a non-Python machine and don't want to install Python tooling
- Disk is tight (each project's embedding store is ~300 MB)

For those cases, LaunchPad's existing three-tier system is sufficient.

## A future helper command

A `/lp-mempalace-setup` slash command is on the post-v1.0.0 roadmap. It will execute the four-line per-project block above as a single command, with a graceful failure if MemPalace is not installed on the machine. Until that ships, the manual setup is the supported path. See [ROADMAP.md](../../ROADMAP.md) for the full roadmap context.
