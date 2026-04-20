# Porting Guide

> **Loaded when:** `/lp-port-skill` is invoked. Governs all 4 phases of the skill porting workflow.

**A ported skill must be indistinguishable from a native project skill. No shortcuts,
no verbatim imports. Every file must pass the same 16-criteria quality gates as /lp-create-skill.**

---

## The 4-Phase Port Workflow

```
Phase 1: Ingest     → Parse source skill, produce inventory
Phase 2: Adapt      → Resolve dependencies + reformat to project conventions
Phase 3: Validate   → lp-skill-evaluator sub-agent, 3-pass quality gates, max 3 cycles
Phase 4: Register   → Eval scenarios, CLAUDE.md, AGENTS.md, user summary
```

---

## Phase 1: Ingest

### 1a. Read All Source Files

Read every file in the source skill directory:

- `SKILL.md` (required — if absent, abort and report: "No SKILL.md found at [path]. Aborting.")
- All files in `rules/` if present
- All files in `references/` if present
- All files in `scripts/` if present
- `metadata.json` if present

Do NOT summarize, skip, or truncate any file at this stage. Read all content before proceeding.

### 1b. Parse the Source SKILL.md

Extract and report:

- `name` from frontmatter
- `description` from frontmatter
- Trigger phrases (if declared)
- Number of files (SKILL.md + supporting files)
- Architecture: single-file or multi-file
- Any `dependencies`, `compatibility`, or `metadata` frontmatter fields

### 1c. Produce Ingestion Inventory

Emit this structured summary before proceeding to Phase 2:

```
## Ingestion Inventory

Source: [path]
Skill name: [name from frontmatter]
Description: [first 100 chars]
Files found: [count] ([list of files])
Architecture: [single-file / multi-file]

### Frontmatter Fields
[list all fields found, flag any unknown to the project]

### Dependencies Detected
[list each dependency with type — see Phase 2 decision tree]

### Initial Assessment
[1-2 sentences on porting complexity: straightforward / moderate / requires user decisions]
```

---

## Phase 2: Adapt

Phase 2 has two tracks that run in order: **Dependency Resolution** (2A) first, then **Format Adaptation** (2B).

---

### 2A: Dependency Resolution

For each dependency type detected in Phase 1, apply the decision tree below. Escalated items (marked USER DECISION REQUIRED) must be resolved before proceeding to format adaptation.

---

**Shell Scripts**

First, classify portability:

- **Portable:** Script uses only standard POSIX tools, relative paths, and no environment-specific assumptions. → Adapt and port. Place adapted script in `.claude/skills/<name>/scripts/`. Update SKILL.md references accordingly.
- **Environment-specific:** Script contains hardcoded absolute paths, source-environment credentials, or platform-specific tooling that cannot be generalized. → Strip from skill. Document in the skill's Verification section as a manual prerequisite: "Script `[name]` was removed during porting — requires manual setup: [description of what it did]."

---

**Runtime URL Fetches**

Skill body fetches content from an external URL at runtime (e.g., fetches a remote markdown spec, API definition, or ruleset).

→ Inline the content now. Use WebFetch to retrieve the URL content. Embed it directly into the appropriate reference file. Add an HTML comment:

```html
<!-- Inlined from: [original URL] on [YYYY-MM-DD]. Refresh manually if upstream changes. -->
```

---

**Build Pipelines**

Two sub-cases:

- **Artifact-producing:** Pipeline compiles or bundles output (e.g., `npm run build`, `cargo build`). → Run the build now and port the compiled output. Do not port the build configuration itself.
- **Workflow instructions:** Pipeline steps are procedural instructions embedded in the skill (e.g., "run tests before deploying"). → Adapt the instructions to the project's workflow conventions. Rewrite as imperative steps in the SKILL.md body.

---

**External CLI Tools**

The skill requires a CLI tool to be installed (e.g., `gh`, `docker`, `wrangler`, `jq`, `vercel`).

→ Add a "Prerequisites" section to SKILL.md:

```markdown
## Prerequisites

This skill requires the following tools to be installed:

- `[tool-name]` — [what it's used for] | Install: [install command or URL]
```

In Phase 3 (Validate), the lp-skill-evaluator checks that prerequisites are documented. Availability on the current machine is NOT checked — this is the user's responsibility.

---

**External APIs**

The skill calls an external API (e.g., Stripe, GitHub API, Linear, Clerk, Slack, OpenRouter).

→ **Step 1:** Identify the required environment variable(s) from the skill source.

→ **Step 2:** Check `.env.local` in the project root. Parse for each required env var name.

- **If the env var IS present in `.env.local`:** Continue porting. Add the var to the skill's Prerequisites section for documentation only. No user interruption needed.
- **If the env var is NOT present in `.env.local`:** PAUSE the port workflow. Surface to the user:

```
⚠️  API Dependency Required

This skill requires access to an external API:
  Service: [API name]
  Required env var: [VAR_NAME]
  Purpose: [what the skill uses this API for]
  Without it: This skill will be completely non-functional.

Options:
  A) Add [VAR_NAME] to .env.local now, then continue porting
  B) Skip this skill — do not port it
  C) Port it anyway and add the prerequisite manually later

Choose A, B, or C:
```

If A: wait for user to add the var, verify it now appears in `.env.local`, then continue.
If B: abort the port. Report: "Port skipped — [VAR_NAME] not configured."
If C: continue. Add a prominent warning to SKILL.md:

```markdown
⚠️ **PREREQUISITE MISSING:** This skill requires `[VAR_NAME]` in `.env.local`.
Without it, the skill is non-functional. Add the variable before using this skill.
```

---

**MCP Servers**

The skill declares an MCP server dependency (e.g., in frontmatter `dependencies.tools` with `type: mcp`, or references an MCP server by name in its body).

→ **Step 1:** Check if the MCP server is already configured in the project (look for MCP configuration in `.claude/settings.json`, `CLAUDE.md`, or `AGENTS.md`).

- **If already configured:** Translate the MCP reference to the project's configuration format. Continue porting.
- **If NOT configured:** PAUSE. Same escalation protocol as External APIs — present options A/B/C, same handling.

---

**Language Packages (npm / pip / cargo / etc.)**

The skill assumes certain packages are installed (e.g., references React, Next.js, FastAPI, PyTorch).

→ Add to "Prerequisites" section in SKILL.md:

```markdown
## Prerequisites

- **[Package ecosystem]:** [package-name] ([version if specified]) | Install: `[install command]`
```

No user interruption. Document and continue.

---

**Platform / Environment Requirements**

The skill specifies OS, runtime version, or tool requirements (e.g., "requires Node.js 20+", "Linux only", "requires Docker").

→ Translate to frontmatter `compatibility` field if supported. Add to Prerequisites section. Flag to user in the Phase 4 summary if the requirement conflicts with the known target environment. No interruption during Phase 2.

---

**Hardcoded Local File System Paths**

The skill contains absolute paths from the source environment (e.g., `/Users/alice/dev/project/scripts/run.sh`).

→ Replace with relative paths where the intent is clear. For paths where the correct relative path is ambiguous or irrecoverable: flag in the skill's Verification section as a manual fixup:

```markdown
- [ ] Replace hardcoded path `[original path]` with the correct path in this environment
```

---

### 2B: Format Adaptation

After dependencies are resolved, adapt the skill to the project's format. Apply every item below to SKILL.md and all supporting files.

---

**Frontmatter Field Mapping**

| Source Field        | Project Treatment                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| `name`              | Keep. Ensure kebab-case, max 64 chars. Rename directory to match.                                         |
| `description`       | Rewrite in third person. Ensure max 1024 chars. Add `Triggers on: phrase1, phrase2, phrase3.` at the end. |
| `license`           | Strip from frontmatter. Optionally add to provenance comment block.                                       |
| `metadata.author`   | Strip from frontmatter. Add to provenance comment block.                                                  |
| `metadata.version`  | Strip from frontmatter. Add to provenance comment block.                                                  |
| `metadata.internal` | Strip.                                                                                                    |
| `argument-hint`     | Convert the value into a trigger example under the `## Trigger` section.                                  |
| `dependencies`      | Strip from frontmatter. Content is handled by Phase 2A.                                                   |
| `compatibility`     | Keep if present.                                                                                          |
| Any other field     | Strip.                                                                                                    |

**Provenance Comment Block**

Add immediately after frontmatter closing `---`, before any content:

```markdown
<!-- ported-from: [original source path or URL]
     original-author: [author name if known, else "unknown"]
     port-date: [YYYY-MM-DD]
     upstream-version: [version if known, else "unversioned"] -->
```

---

**Structural Transformation: `rules/` → `references/`**

If the source skill has a `rules/` directory:

1. Keep all rule files exactly as-is — do not summarize, consolidate, or split them.
2. Move all files from `rules/` into `references/` (the project's flat structure).
3. Reformat each rule file to be independently loadable (no cross-rule dependencies if present).
4. Update all references in SKILL.md from `rules/[file]` to `references/[file]`.
5. Add explicit loading triggers in SKILL.md for each reference: `Read [references/file.md](mdc:references/file.md) before proceeding to [next section].`

---

**Project Convention Checklist**

Apply to SKILL.md (and all reference files where applicable):

- [ ] **Recency-bias bookending:** Add the critical constraint as a bold single line at the very top of SKILL.md body. Repeat the same line verbatim at the very bottom.
- [ ] **No hedge language:** Search for and remove: "try to", "consider", "you might want to", "it's generally a good idea", "it may be worth", "potentially", "could possibly". Replace with direct imperatives.
- [ ] **Verification gate:** If missing, add a `## Verification` section with 4-7 pass/fail checkboxes. Every criterion must be objectively testable — no subjective criteria.
- [ ] **Negative boundaries:** If missing, add a `## What This Skill Does NOT Handle` section. Include 2-4 explicit exclusions with reasons.
- [ ] **Trigger section:** If missing, add a `## Trigger` section with positive activation conditions and 2-3 example invocations.
- [ ] **Visible outputs per phase:** Each numbered step in `## The Job` must produce a named artifact or visible decision. Steps like "Understand the requirements" are not valid steps.
- [ ] **Progressive disclosure:** Reference files are loaded at the point of use, not at the top of SKILL.md.
- [ ] **Line count:** SKILL.md must be under 500 lines. If adaptation brings it over 500 lines, move the excess to a new reference file.

---

## Phase 3: Validate

Spawn a `lp-skill-evaluator` sub-agent (Sonnet) with read-only access to the adapted skill files.

Run the standard 3-pass evaluation:

1. First-principles (3 checks — necessity, minimality, independent loadability)
2. Baseline detection (3 checks — structural differentiation from no-skill Claude)
3. Anthropic checklist (10 criteria)

Max 3 improvement cycles. If gates still fail after 3 cycles, present remaining failures to the user with options: ship as-is, provide guidance, or abort.

**Output:** Evaluation report (PASS / FAIL with diagnostics).

---

## Phase 4: Register

### 4a. Generate Eval Scenarios

Read `.claude/skills/creating-skills/references/EVAL-TEMPLATE.md` before writing scenarios.

Create at least 3 scenarios in `.claude/skills/<name>/evals/eval-scenarios.md`:

1. Happy path — standard invocation with typical inputs
2. Edge case — minimal, ambiguous, or tricky input
3. Negative boundary — input that looks related but is out of scope

Each scenario includes: invocation, expected output, and baseline comparison (what Claude produces WITHOUT this skill).

### 4b. Update CLAUDE.md

Add the skill to the Progressive Disclosure table and Available Sub-Agents section. Follow the existing table format exactly.

### 4c. Update AGENTS.md

Add the skill to the Progressive Disclosure table and Available Sub-Agents section. Follow the existing entry format exactly.

### 4d. Update Skills Catalog

1. **`docs/skills-catalog/skills-usage.json`** -- Add `"<skill-name>": "YYYY-MM-DD"` to the `skills` object (use today's date). Create the file with initial structure if it doesn't exist.
2. **`docs/skills-catalog/skills-index.md`** -- Add the skill to the correct group in both the Quick Reference table and Detailed Descriptions section. Canonical groups (in order): Design & UI, Frontend Engineering, Backend Engineering, Data & Database, Testing & QA, DevOps & Infrastructure, Security & Auth, API & Integrations, Billing & Payments, Build Pipeline, Quality & Workflow, Documentation, Meta (Skill Management), Other. Assign the next sequential number. Place the skill in the best-fit group. Use "Other" only if no canonical group fits.

### 4e. Present Summary

```
## Skill Ported: <name>

### Source
[original path]

### File Tree
.claude/skills/<name>/
  SKILL.md (XXX lines)
  references/
    [list of reference files, if any]
  evals/
    eval-scenarios.md

### Provenance
Ported from: [source]
Port date: [date]

### Dependencies Resolved
[list of dependency decisions made in Phase 2A]

### Evaluation
[PASS / FAIL] — [1-sentence summary]

### CLAUDE.md / AGENTS.md
Updated with trigger phrases: [list triggers]

### Next Steps
- Use /lp-update-skill <name> to iterate on this skill
- Run eval scenarios to verify real-world behavior
```

Ask: "Commit these files, or adjust something first?"

---

## Verification Gate

Before delivering to user, confirm every item:

- [ ] All skill files saved to `.claude/skills/<name>/`
- [ ] SKILL.md under 500 lines
- [ ] Provenance comment block present
- [ ] All reference files independently loadable
- [ ] No hedge language in any file
- [ ] Verification gate present with pass/fail criteria
- [ ] Negative boundaries section present
- [ ] Recency-bias bookending applied (constraint at top AND bottom)
- [ ] Evaluation report shows PASS
- [ ] CLAUDE.md updated
- [ ] AGENTS.md updated
- [ ] `docs/skills-catalog/skills-usage.json` updated with ported skill
- [ ] `docs/skills-catalog/skills-index.md` updated with ported skill entry
- [ ] At least 3 eval scenarios created
- [ ] All Phase 2A dependency decisions documented in skill or summary
- [ ] Output structurally different from what Claude produces without this skill

---

**A ported skill must be indistinguishable from a native project skill.**
