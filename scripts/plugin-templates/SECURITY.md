# LaunchPad Plugin — Security Notes

## Trust boundary

Installing this plugin grants it:

- **SessionStart hook execution** (on startup + `/clear`)
- **PreToolUse hook execution on every `Bash` tool call**
- **PostToolUse hook execution on every `Skill` tool call**
- ~11 shell scripts under `plugin/bin/` invokable by the plugin's commands

These execute with the same privileges as your Claude session. Review the hook scripts under `plugin/bin/` before installing.

## Hook behavior

| Hook         | Fires on                | Script                            | Blast radius                                                   |
| ------------ | ----------------------- | --------------------------------- | -------------------------------------------------------------- |
| SessionStart | session open, `/clear`  | `plugin/bin/hydrate.sh`           | Read-only — prints backlog + session card                      |
| PreToolUse   | every `Bash` tool call  | `plugin/bin/block-merges.sh`      | Blocks destructive git commands; otherwise pass-through        |
| PostToolUse  | every `Skill` tool call | `plugin/bin/track-skill-usage.sh` | Appends usage stamp to `docs/skills-catalog/skills-usage.json` |

## Hook dependencies

- `jq` is a hard dependency — install via `brew install jq` (macOS) or `apt install jq` (Linux) before installing the plugin. Without it, `block-merges.sh` exits 2 with an install hint.
- `python3` is required by the build pipeline but NOT by any runtime hook (was removed from `track-skill-usage.sh` in Phase 2).

## Secret-scan posture

Plugin ships with a **curated generic baseline** at `plugin/data/secret-patterns.txt` (AWS, GitHub, Stripe, Slack, JWT, private-key headers). LaunchPad-internal vendor patterns are NOT shipped. The build pipeline grep-scans `plugin/data/*.yml` against the baseline and refuses to ship on any match.

Projects that need stronger or project-specific scanning should keep their own `.launchpad/secret-patterns.txt` — the plugin's baseline is a floor, not a ceiling.

## Integrity

`plugin/SHA256SUMS` is generated on every build. To verify:

```bash
cd /path/to/LaunchPad/plugin
shasum -a 256 -c SHA256SUMS
```

Tampering with any plugin file after publication will be detected by re-running the checksum verification.

No release-tag signing in v0.1. Planned for v0.2.

## Nothing written to user files

The plugin never writes to:

- Your project's `CLAUDE.md`
- Any file outside `.harness/`, `.launchpad/`, or `docs/skills-catalog/` in your project root
- Any file outside its own `plugin/` directory

When Priority A commands seed `.launchpad/agents.yml` (Pattern B), they copy from `plugin/data/` into your project's `.launchpad/`. You can edit or delete the seeded file freely — the plugin re-seeds only if missing.

## Uninstall

No cleanup command needed. Stop passing `--plugin-dir` (or remove from `.claude/settings.local.json`). Your `.harness/` and `.launchpad/` directories remain; they contain your project's runtime state and config, owned by you. Delete them manually with `rm -rf .harness .launchpad` if you want a clean slate.

## Reporting vulnerabilities

Email the LaunchPad repo owner (see `plugin/.claude-plugin/plugin.json` `author.url`). Do not file public GitHub issues for security-sensitive reports.
