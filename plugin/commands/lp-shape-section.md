---
name: lp-shape-section
description: "Deep-dive into a specific product section with guided questions"
---
# Shape Section

You are guiding the user through a deep-dive into a specific product section. This command creates a detailed section spec in `docs/tasks/sections/[section-name].md` and updates the section registry in `docs/architecture/PRD.md`.

Shaping is the bridge between high-level product definition and implementation planning. After a section is shaped, it has enough detail for `/lp-pnf` to create a concrete implementation plan.

Every question uses the **guided format**: context explaining WHY the question matters, a dynamically generated options table with "Best When" guidance and examples, a context-aware recommendation based on prior answers, and a TBD escape hatch.

---

## Step 1: Prerequisite Check

Read these files to load project context:

- `docs/architecture/PRD.md` — **required** (needs section registry and data shape)
- `docs/architecture/TECH_STACK.md` — optional but useful
- `docs/architecture/DESIGN_SYSTEM.md` — optional but useful for UI pattern suggestions
- `docs/architecture/APP_FLOW.md` — optional but useful for navigation context

**If PRD.md is still a stub or has no Product Sections table**, tell the user:

```
Section shaping requires a section registry in PRD.md. Please run /define-product first
to define your product sections, then come back to /shape-section.
```

Then STOP.

---

## Step 2: Identify Target Section

**If `$ARGUMENTS` is provided:**

1. Normalize the argument to **kebab-case** (e.g., "User Auth" → `user-auth`, "Dashboard Settings" → `dashboard-settings`)
2. Look up the normalized name in the PRD.md Product Sections table
3. If found, use it. If NOT found, ask:

```
"[argument]" is not in the section registry. Would you like to:
A) Add it as a new section (I'll ask if it's MVP or Post-MVP)
B) Pick from existing sections
```

If the user chooses A, ask whether the new section is MVP or Post-MVP, then add it to the PRD.md registry with status `defined` before proceeding.

**If no arguments provided:**

1. Read the Product Sections table from PRD.md
2. Show sections that are still `defined` (not yet shaped):

```
These sections haven't been shaped yet:

| Section | MVP | Status |
|---------|-----|--------|
| auth    | Yes | defined |
| dashboard | Yes | defined |
| settings | Yes | defined |

Which section would you like to shape? (You can also name a new section to add.)
```

---

## Step 3: Detect Mode

Check if `docs/tasks/sections/[section-name].md` already exists.

- If it does NOT exist — **create mode**.
- If it exists with real content — **update mode**. Show current content summary and ask what to update.
- If the section's status in PRD.md is `planned` or `built`, warn the user: "This section is currently [status]. Re-shaping it will reset its status to `shaped`, which means any existing implementation plan may become stale." Ask them to confirm before proceeding.

---

## Step 4: Load Section Context

Before asking questions, extract relevant context from the loaded files:

- **From PRD.md:** What this section was described as, which data entities are relevant, MVP status
- **From DESIGN_SYSTEM.md:** Available component library, design philosophy, color palette
- **From APP_FLOW.md:** Any routes or navigation related to this section
- **From TECH_STACK.md:** Frontend/backend framework (affects UI pattern suggestions)

Present this context briefly:

```
Shaping section: [section-name]

Context from your specs:
- MVP: [Yes/No]
- Related entities: [list from Data Shape]
- Design: [philosophy + component library]
- Routes: [any matching routes from APP_FLOW]

I'll ask 9 questions to fully define this section: purpose, actions, displayed info,
user flows, UI patterns, data requirements, scope, edge cases, and an open-ended
catch-all for anything we missed.
```

---

## Step 5: Gather Section Information

Ask these questions **one at a time**. Wait for the user's answer before asking the next question. Accept "TBD" for any question.

**IMPORTANT — Guided Format:** For every question, dynamically generate:

1. A brief explanation of WHY this question matters
2. The question itself
3. An options table with columns: Option | Best When | Example
4. A **Recommended** pick with reasoning referencing prior answers AND section context
5. A note: **If unsure:** Answer "TBD" — you can fill this in later with `/lp-update-spec`.

The options tables below are starting points. **Heavily adapt them based on the specific section being shaped.** An "auth" section gets very different suggestions than a "dashboard" section.

---

### S-1: Primary Purpose

WHY: A clear purpose statement prevents feature creep within this section and helps AI agents understand what belongs here vs elsewhere.

```
What is the primary purpose of the [section-name] section?

Describe in 1-3 sentences what this section exists to accomplish.
```

| Option                   | Best When                                     | Example                                                           |
| ------------------------ | --------------------------------------------- | ----------------------------------------------------------------- |
| CRUD management          | Section manages a resource                    | "Manage projects: create, view, edit, archive"                    |
| Data visualization       | Section displays analytics/metrics            | "Show real-time dashboard of key business metrics"                |
| Workflow orchestration   | Section guides a multi-step process           | "Guide users through onboarding with progress tracking"           |
| Configuration / Settings | Section lets users customize behavior         | "Allow users to configure notifications, theme, and integrations" |
| Communication            | Section handles messaging/collaboration       | "Enable team chat with channels, DMs, and threads"                |
| Content consumption      | Section displays content for reading/browsing | "Browse and search the knowledge base articles"                   |

**Recommended:** Generate based on section name and PRD context.

---

### S-2: User Actions

WHY: Listing concrete actions defines the scope of what this section needs to support. Actions map directly to UI elements, API endpoints, and permissions.

```
What can the user DO in this section?

List every action as a verb phrase. Be specific — "create project" not just "manage projects".
```

| Option             | Best When           | Example                                                       |
| ------------------ | ------------------- | ------------------------------------------------------------- |
| CRUD actions       | Resource management | "Create task, view task list, edit task details, delete task" |
| Filter/sort/search | Data browsing       | "Filter by status, sort by date, search by name"              |
| Bulk operations    | Managing many items | "Select multiple, bulk archive, bulk assign"                  |
| Import/export      | Data transfer       | "Import from CSV, export to PDF"                              |
| Configure/toggle   | Settings            | "Toggle notifications, change theme, update email"            |
| Trigger workflows  | Process initiation  | "Start review, approve request, escalate issue"               |

**Recommended:** Generate based on S-1 purpose and section type. Present a pre-populated list based on common patterns for this section type, then ask the user to confirm, add, or remove.

---

### S-3: Displayed Information

WHY: Knowing what data the user needs to SEE determines the UI layout, which entities to fetch, and what API responses look like.

```
What information does the user SEE in this section?

List the key data points, metrics, or content displayed. Reference entities from your
Data Shape where applicable.
```

| Option                | Best When          | Example                                                              |
| --------------------- | ------------------ | -------------------------------------------------------------------- |
| List/table of records | Browsing resources | "Table: name, status, assignee, due date, priority"                  |
| Summary metrics       | Dashboard/overview | "Total count, completion rate, overdue items, recent activity"       |
| Detail view fields    | Single-record view | "Title, description, status badge, assignee avatar, comments thread" |
| Form fields           | Create/edit flows  | "Name input, description textarea, status dropdown, date picker"     |
| Timeline/feed         | Activity tracking  | "Chronological list: timestamp, actor, action, details"              |
| Nested/hierarchical   | Tree structures    | "Folder tree with expand/collapse, breadcrumb path"                  |

**Recommended:** Generate based on S-1, S-2, and the data entities from PRD.md. Map each entity's fields to what should be visible in this section.

---

### S-4: User Flows

WHY: Step-by-step flows reveal the exact UI interactions needed. They expose decision points, error paths, and state transitions that are invisible in a feature list.

```
Walk through the main user flows in this section step by step.

For each flow, describe:
1. Entry point (how does the user get here?)
2. Steps (what do they click/type/see at each step?)
3. Decision points (any branches or conditional paths?)
4. Success state (what does "done" look like?)
5. Error state (what can go wrong and how is it handled?)
```

Do NOT provide an options table for this question — it requires a narrative answer unique to each section. Instead, provide a **worked example** relevant to the section type:

**Example for an auth section:**

```
Flow: Sign Up
1. Entry: User clicks "Sign Up" on landing page
2. Enters email, password, confirms password
3. Decision: Email already exists? → Show error "Account exists, try logging in"
4. Success: Account created → redirect to onboarding
5. Error: Weak password → inline validation message
```

**Example for a dashboard section:**

```
Flow: View Dashboard
1. Entry: User logs in → redirected to /dashboard
2. Sees summary metrics (loaded from API)
3. Decision: Loading slow? → Show skeleton, then real data
4. Success: All widgets populated with current data
5. Error: API fails → Show error state with retry button
```

Generate a relevant example based on the section being shaped.

---

### S-5: UI Patterns

WHY: Choosing UI patterns early ensures consistency with your design system and prevents reinventing layouts for each section.

```
What UI patterns should this section use?

Pick the patterns that best fit the actions and information you described.
```

| Option                     | Best When                              | Example                                                |
| -------------------------- | -------------------------------------- | ------------------------------------------------------ |
| Data table                 | List of records with sorting/filtering | "Sortable table with pagination, row actions dropdown" |
| Card grid                  | Visual browsing, image-heavy content   | "3-column card grid with cover image, title, metadata" |
| Kanban board               | Status-based workflow                  | "Columns: To Do, In Progress, Done — drag to move"     |
| Form (single page)         | Simple create/edit                     | "Single form with sections, validation, submit button" |
| Form (multi-step wizard)   | Complex creation with many fields      | "3-step wizard: basics → details → review & confirm"   |
| Split view (list + detail) | Browse + inspect pattern               | "Left: list of items, Right: selected item detail"     |
| Modal / Dialog             | Quick actions without leaving context  | "Delete confirmation, quick edit, preview"             |
| Tabs                       | Multiple views of the same data        | "Tabs: Overview, Activity, Settings within a project"  |
| Empty state                | First-time or no-data experience       | "Illustration + 'Create your first [thing]' CTA"       |

**Recommended:** Generate based on S-2 (actions), S-3 (displayed info), and DESIGN_SYSTEM.md (component library, philosophy). If the user chose shadcn/ui, suggest its specific component names.

---

### S-6: Data Requirements

WHY: Mapping this section to the data model clarifies which API endpoints are needed, what permissions to check, and how entities are created/modified.

```
What entities from the Data Shape does this section read and write?

For each entity, specify:
- Read (R), Create (C), Update (U), Delete (D) — which operations?
- Any filters or scopes? (e.g., "only tasks assigned to current user")
```

Pre-populate from PRD.md data shape. Present the known entities and ask the user to assign CRUD operations:

```
Based on your Data Shape, these entities seem relevant to [section-name]:

| Entity | Read | Create | Update | Delete | Scope/Filter |
|--------|------|--------|--------|--------|-------------|
| [entity] | ? | ? | ? | ? | ? |
| [entity] | ? | ? | ? | ? | ? |

Confirm or adjust, and add any entities I missed.
```

---

### S-7: Scope Boundaries

WHY: Explicit scope prevents this section from growing into "the everything page." Clear boundaries make implementation faster.

```
What is explicitly OUT of scope for this section?

List things that might seem related but should NOT be built here.
```

| Option                     | Best When           | Example                                                         |
| -------------------------- | ------------------- | --------------------------------------------------------------- |
| Advanced feature exclusion | Keeping MVP simple  | "No bulk import — users add items one at a time for v1"         |
| Cross-section boundary     | Preventing overlap  | "User management is in Settings, not here"                      |
| Integration exclusion      | Avoiding complexity | "No third-party calendar sync — manual date entry only"         |
| Permission boundary        | Simplifying auth    | "No role-based views — all users see the same data for v1"      |
| Mobile exclusion           | Platform focus      | "No mobile-specific layouts — responsive but desktop-optimized" |

**Recommended:** Generate based on R-3 (non-goals from PRD) and section context. If the PRD says "no real-time collaboration", reinforce that as a scope boundary for relevant sections.

---

### S-8: Edge Cases

WHY: Edge cases are where bugs live. Thinking about them during shaping (not during coding) prevents costly rework.

```
What edge cases should this section handle?

Think about: empty states, error conditions, permission boundaries, data limits,
and concurrent access.
```

| Category              | Example Edge Cases                                                                        |
| --------------------- | ----------------------------------------------------------------------------------------- |
| Empty states          | First-time user with no data, search with no results, filtered view with nothing matching |
| Error conditions      | API timeout, validation failure, file too large, duplicate name                           |
| Permission boundaries | Unauthorized access attempt, expired session, role change mid-session                     |
| Data limits           | Very long text, thousands of items, deeply nested structures                              |
| Concurrency           | Two users editing same item, stale data after long idle, optimistic update conflict       |
| Input edge cases      | Special characters in names, unicode, very long strings, empty required fields            |

For each edge case the user identifies, ask for the **expected behavior** and any **fallback**:

```
For each edge case, how should the app respond?

| Scenario | Expected Behavior | Fallback |
|----------|-------------------|----------|
| [case] | [behavior] | [fallback if primary fails] |
```

---

### Open-Ended Catch-All

#### OE-1: Anything Else?

After all guided questions are complete, ask:

```
Is there anything about the [section-name] section that we haven't covered?
Any constraints, dependencies on other sections, or implementation preferences?

If not, just say "No, we're good" and I'll generate the section spec.
```

**No options table** for this question.

**CRITICAL behavior:** If the user provides additional information, parse it and integrate it into the appropriate sections of the section spec. Do NOT create a separate "Other Notes" section.

---

## Step 6: Write Section Spec

Create the directory if it doesn't exist, then write `docs/tasks/sections/[section-name].md`:

```markdown
# Section Spec: [Display Name]

**Last Updated**: [YYYY-MM-DD]
**Status**: shaped
**Priority**: [MVP/Post-MVP from registry]

## Purpose

[S-1 answer]

## User Actions

[S-2 answer as a bulleted list of verb phrases]

## Displayed Information

[S-3 answer — data points, metrics, fields by view]

## User Flows

[S-4 answer — each flow as a numbered sequence with entry, steps, decisions, success, error]

## UI Patterns

[S-5 answer — chosen patterns with notes on why]

## Data Requirements

| Entity   | Read  | Create | Update | Delete | Scope/Filter |
| -------- | ----- | ------ | ------ | ------ | ------------ |
| [entity] | [Y/N] | [Y/N]  | [Y/N]  | [Y/N]  | [scope]      |

## Scope Boundaries

[S-7 answer as a bulleted list]

## Edge Cases

| Scenario | Expected Behavior | Fallback   |
| -------- | ----------------- | ---------- |
| [case]   | [behavior]        | [fallback] |
```

**In update mode:** Only modify sections the user chose to update. Preserve everything else.

---

## Step 7: Update Section Registry

After writing the section spec, update `docs/architecture/PRD.md`:

1. Find the section in the Product Sections table
2. Update its status from `defined` to `shaped`
3. Add the spec link: `[spec](../../docs/tasks/sections/[section-name].md)`

If this was a newly added section (not previously in the registry), insert a new row.

---

## Step 8: Web Copy (Public-Facing Pages Only)

After writing the section spec, determine if this section is a **public-facing page** — a page that visitors (not logged-in users) see. This includes: landing pages, pricing pages, about pages, feature pages, product pages, homepages, and contact/demo pages.

**If the section IS a public-facing page:**

Present to the user:

```
This is a public-facing page. Good copy is critical for conversion.

Would you like to create the page copy now?
- Yes — I'll load available copy skills and produce a copy brief + full copy document
- No — I'll note that copy is needed and you can run it later
```

If the user says **yes**:

**Step 8a: Strategic Context Loading (conditional)**

Before producing copy, conditionally load strategic methodology skills that provide business context:

- IF section involves pricing, offer design, or value proposition:
  - Load offer methodology skill (if available in `.claude/skills/` — e.g., `hormozi-offer`)
- IF section involves lead generation, signup flows, or lead magnets:
  - Load lead strategy skill (if available in `.claude/skills/` — e.g., `hormozi-leads`)
- IF section involves pricing page architecture, billing, or tiers:
  - Load monetization methodology skill (if available in `.claude/skills/` — e.g., `hormozi-moneymodel`)

Strategic skills produce blueprints that feed into web copy as Phase 1 context. Skip silently if no strategic skills are installed.

**Step 8b: Copy Production**

- Load `web-copy` skill (if available in `.claude/skills/`)
- Execute the copy workflow using the section spec + any strategic blueprints as input context
- Skip silently if no `web-copy` skill is installed — add a note to the section spec instead:

```markdown
## Copy Status

**Status:** Not yet created (no web-copy skill installed)
**Action:** Install a web-copy skill or write copy manually before implementation
```

If the user says **no**: Add a note to the section spec under a new `## Copy Status` section:

```markdown
## Copy Status

**Status:** Not yet created
**Action:** Run web-copy skill for this section before implementation
```

**If the section is NOT a public-facing page** (e.g., admin dashboard, settings, internal tools): Skip this step entirely.

---

## Step 9: Summary and Next Step

```
Done. Section "[section-name]" has been shaped.

**docs/tasks/sections/[section-name].md**
- Purpose: [1-line summary]
- [N] user actions defined
- [N] user flows documented
- [N] UI patterns chosen
- [N] edge cases identified
- Copy: [created / pending / not applicable]

**docs/architecture/PRD.md** registry updated: [section-name] → shaped

Remaining unshaped sections: [list any with status "defined"]

Next steps:
- Shape another section: /shape-section [next-section]
- Fill in any TBDs: /update-spec
- When all MVP sections are shaped, plan implementation: /pnf [section-name]
```

---

## Behavioral Rules

1. **Ask one question at a time.** Never batch multiple questions into a single message.
2. **Wait for an answer before proceeding.** Do not assume or fill in answers.
3. **Accept "TBD" gracefully.** Write it literally into the docs. Do not push for decisions.
4. **In update mode, show current values.** Let the user confirm or change each field.
5. **Do not invent information.** Only write what the user explicitly told you.
6. **Use exact answers provided.** Do not rephrase or editorialize unless asked.
7. **Generate guided format dynamically.** Options MUST be tailored to the specific section being shaped — an auth section gets different suggestions than a dashboard section.
8. **Pre-populate from existing specs.** Use data entities, routes, and design choices from other architecture docs to provide context-rich suggestions.
9. **Normalize section names to kebab-case.** Always use kebab-case for filenames and registry entries.
10. **Integrate open-ended answers.** Parse the catch-all response and place information in the appropriate spec sections.
