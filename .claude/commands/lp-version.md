---
name: lp-version
description: Print the installed LaunchPad plugin version. Reads plugin/.claude-plugin/plugin.json via $CLAUDE_PLUGIN_ROOT.
---

# /lp-version

Trivial introspection command. Prints the currently installed LaunchPad plugin version, author, and a short status summary (agent / skill / command counts).

## Usage

```
/lp-version
```

## Behavior

1. Resolve `PLUGIN_ROOT`:
   - Plugin install: `$CLAUDE_PLUGIN_ROOT` is exported by Claude Code
   - Fallback (dev/source mode): derive from the command's own location

2. Read `$PLUGIN_ROOT/.claude-plugin/plugin.json` and extract `name`, `version`, `author.name`.

3. Count installed surface:
   - Agents: `ls $PLUGIN_ROOT/agents/*.md | wc -l`
   - Skills: `ls -d $PLUGIN_ROOT/skills/*/ | wc -l`
   - Commands: `ls $PLUGIN_ROOT/commands/*.md | wc -l`

4. If `$PLUGIN_ROOT` cannot be resolved (source-mode without the env var), report: "Running from LaunchPad source (not a plugin install). Template version: $(cat VERSION 2>/dev/null || echo unknown)."

5. Print a compact single-block report:

```
LaunchPad v0.1.0 — launchpad plugin by Foad Shafighi
  36 agents, 15 skills, 38 commands
  install: /Users/foadshafighi/.../plugin
  update: cd /path/to/LaunchPad && git pull
```

## Rules

- Never mutate anything
- Never require `.harness/` or `.launchpad/` — this is a pure read command, safe from any state
- If anything fails (file missing, JSON parse error), fall back to a minimal "plugin metadata unavailable" line rather than crashing
