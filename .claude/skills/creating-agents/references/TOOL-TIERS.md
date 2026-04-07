# Tool Permission Tiers

> **Loaded when:** Phase 4 begins — assigning tools to the agent's frontmatter.

This reference defines the least-privilege tool assignment system. Every agent receives ONLY the tools required for its role. Granting unnecessary tools is the fastest path to unreliable agents.

---

## The Five Tiers

### Tier 1: Search-Only (Locators)

**Tools:** `Grep, Glob, LS`

**Use when:** The agent finds WHERE things are but never reads file contents.

**Examples:** `codebase-locator`, `docs-locator`, `file-locator`

**Why no Read:** Locators are fast and cheap. Adding Read makes them slower, more expensive, and tempted to analyze instead of locate.

---

### Tier 2: Read + Search (Analyzers, Evaluators, Pattern Finders)

**Tools:** `Read, Grep, Glob, LS`

**Use when:** The agent must read and understand file contents to produce its output.

**Examples:** `codebase-analyzer`, `docs-analyzer`, `skill-evaluator`, `codebase-pattern-finder`, `security-reviewer`, `migration-auditor`

**Why no Write/Edit:** These agents observe and report. They never modify files. Adding mutation tools invites scope creep.

---

### Tier 3: Read + Web (Researchers)

**Tools:** `WebSearch, WebFetch, TodoWrite, Read, Grep, Glob, LS`

**Use when:** The agent needs external information from the web to complete its task.

**Examples:** `web-search-researcher`, `web-researcher`

**Why TodoWrite:** Researchers track multiple search threads and need to persist progress across long research sessions.

**Why this is rare:** Most agents work with local codebase or documentation. Web access adds latency and cost. Only grant when the agent's PURPOSE requires external information.

---

### Tier 4: Read + Write (Resolvers, Fixers)

**Tools:** `Read, Edit, Write, Grep, Glob, LS`

**Use when:** The agent must modify files as part of its job (fixing code, resolving issues, applying patches).

**Examples:** `harness-todo-resolver`, `pr-comment-resolver`

**Why Edit+Write but no Bash:** File mutation is scoped — the agent changes specific files. Bash execution is a broader capability that requires additional justification.

**Constraint:** Resolvers must stage only explicitly reported files (`git add <specific-file>`, never `git add -A`). Post-execution scope validation reverts any out-of-scope changes.

---

### Tier 5: Full Execution (Rare, Justified)

**Tools:** `Read, Edit, Write, Bash, Grep, Glob, LS`

**Use when:** The agent must execute commands (run tests, build, deploy) as part of its core function.

**Examples:** Agents that validate by running `pnpm test`, `pnpm typecheck`, or similar commands.

**Why this is dangerous:** Bash can do anything. An agent with Bash access can delete files, push to git, install packages, or make network requests.

**Required justification:** If granting Bash, document in the agent file:

1. What specific commands the agent is allowed to run
2. What commands are explicitly prohibited
3. Consider adding a PreToolUse hook to validate Bash commands

---

## The Hard Rule: No Agent Tool

**NEVER include `Agent` in a subagent's tools field.** Subagents cannot spawn other subagents. This is a hard architectural constraint in Claude Code. It prevents infinite recursion and forces flat delegation architectures.

---

## Decision Tree

Use this tree to assign the correct tier:

```
Does the agent need to READ file contents?
├── NO → Tier 1 (Grep, Glob, LS)
└── YES
    ├── Does it need WEB access?
    │   └── YES → Tier 3 (WebSearch, WebFetch, TodoWrite, Read, Grep, Glob, LS)
    └── NO
        ├── Does it need to MODIFY files?
        │   ├── NO → Tier 2 (Read, Grep, Glob, LS)
        │   └── YES
        │       ├── Does it need to RUN commands?
        │       │   ├── NO → Tier 4 (Read, Edit, Write, Grep, Glob, LS)
        │       │   └── YES → Tier 5 (Read, Edit, Write, Bash, Grep, Glob, LS)
        │       └── (Justify Bash access in the agent file)
        └── NO → Tier 2
```

---

## Role-to-Tier Mapping

| Agent Role     | Typical Tier | Tools                                       | Rationale                               |
| -------------- | ------------ | ------------------------------------------- | --------------------------------------- |
| Locator        | 1            | `Grep, Glob, LS`                            | Finds files, never reads contents       |
| Analyzer       | 2            | `Read, Grep, Glob, LS`                      | Reads and explains code/docs            |
| Pattern Finder | 2            | `Grep, Glob, Read, LS`                      | Reads code to extract reusable patterns |
| Evaluator      | 2            | `Read, Grep, Glob, LS`                      | Reads artifacts to score/grade          |
| Reviewer       | 2            | `Read, Grep, Glob, LS`                      | Reads code to identify issues           |
| Researcher     | 3            | `WebSearch, WebFetch, TodoWrite, Read, ...` | Needs external information              |
| Resolver       | 4            | `Read, Edit, Write, Grep, Glob, LS`         | Fixes code by modifying files           |
| Builder        | 5            | `Read, Edit, Write, Bash, Grep, Glob, LS`   | Runs commands and modifies files        |

---

## Validation Checklist

After assigning tools, verify:

- [ ] Every granted tool is used by at least one step in the agent's Strategy section
- [ ] No tool is granted "just in case" — every tool has a specific justification
- [ ] The `Agent` tool is NOT included
- [ ] If `Bash` is granted, specific allowed/prohibited commands are documented
- [ ] If `Write`/`Edit` is granted, the agent's purpose explicitly requires file modification
- [ ] The tier matches the role-to-tier mapping table (or deviation is justified)
- [ ] `TodoWrite` is only granted to agents that need to track multi-step progress

---

## When the User Wants to Override

If the user requests tools that violate least-privilege:

1. Warn with a specific explanation: "Granting `Write` to a reviewer agent allows it to modify files it's reviewing. This breaks the observer/actor separation."
2. Explain the risk: what could go wrong if the agent has this tool
3. Allow the override if the user confirms — document the justification in the agent file as a comment

Do not block the user. Warn, explain, and respect their decision.
