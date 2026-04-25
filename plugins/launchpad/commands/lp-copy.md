---
name: lp-copy
description: "Reads copy brief from section spec and provides copy context for design builds. Shell command — downstream projects extend with copy agents/skills."
---

# /lp-copy

Reads copy brief from the current section spec and returns it as context for the design build agent.

## Usage

```
/lp-copy                    → read copy from current section spec
/lp-copy [section-name]     → read copy from named section spec
```

**Arguments:** `$ARGUMENTS` (optional section name)

---

## Flow

### Step 1: Locate Section Spec

- IF `$ARGUMENTS` provided: look for `docs/tasks/sections/{section-name}.md`
- IF no argument: look for the section currently being worked on (check registry status for `shaped` or `designed`)
- IF no section found: warn and exit

### Step 2: Extract Copy Brief

Read the section spec file and search for copy content under these headings (in order):

1. `## Copy`
2. `## Copy Brief`
3. `## Content`

### Step 3: Return Copy Context

**IF copy found:**

Return the copy text as context for the design build agent. Format:

```
## Copy Brief (from section spec)

[copy content]
```

**IF no copy found:**

Warn:

```
No copy brief found in section spec. Components will use placeholder text.

To create copy:
- Add a "## Copy" section to the section spec during /lp-shape-section
- Or run a copy skill during /lp-define (downstream projects configure copy skills)
```

---

## Downstream Extension

This is a shell command in LaunchPad. Downstream projects extend it with their own copy agents and skills:

- BuiltForm adds `web-copy`, `hormozi-offer`, `hormozi-leads`, `hormozi-moneymodel` skills
- Other projects add their domain-specific copy generation

The extension point is in the section spec's copy section — downstream `/lp-shape-section` commands invoke copy skills to populate it.
