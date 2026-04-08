---
name: update-spec
description: "Scan all spec files for gaps, TBDs, and inconsistencies — then fix them"
---

# Update Spec

You are scanning all specification files for completeness gaps, TBD placeholders, and cross-file inconsistencies. This command helps users fill in missing details and keep their spec layer consistent without re-running entire definition commands.

---

## Step 1: Scan All Spec Files

Read all of these files (skip any that don't exist):

- `docs/architecture/PRD.md`
- `docs/architecture/TECH_STACK.md`
- `docs/architecture/DESIGN_SYSTEM.md`
- `docs/architecture/APP_FLOW.md`
- `docs/architecture/BACKEND_STRUCTURE.md`
- `docs/architecture/FRONTEND_GUIDELINES.md`
- `docs/architecture/CI_CD.md`
- `docs/tasks/sections/*.md` (all section specs)

---

## Step 2: Detect Gaps

For each file, scan for:

1. **TBD markers** — literal "TBD", "TODO", "tbd", "N/A (not decided)"
2. **Placeholder text** — `{{ }}`, `<!-- -->`, `[fill in]`, `20xx-xx-xx`, `YYYY-MM-DD`, `[Project Name]`
3. **Empty sections** — section headers with no content below them (empty or whitespace only)
4. **Stub files** — files that contain only HTML comments or generic placeholder text with no real project-specific content

Count the total fields and the completed fields per file to calculate a completeness percentage.

---

## Step 3: Cross-File Consistency Check

After scanning for gaps, check for **inconsistencies across files**:

### 3a: Entity Name Consistency

- Extract all entity names from PRD.md Data Shape section
- Check that BACKEND_STRUCTURE.md data models use the same entity names
- Check that section specs in `docs/tasks/sections/` reference entities by the same names
- **Flag:** Any entity that appears with different names across files (e.g., "User" in PRD but "Account" in backend)

### 3b: Section Name Consistency

- Extract all section names from PRD.md Product Sections table
- Check that section spec filenames match (kebab-case of section names)
- Check that APP_FLOW.md routes reference the same sections
- **Flag:** Any section that appears with different names or is missing from expected locations

### 3c: Tech Stack Consistency

- Extract tech choices from TECH_STACK.md
- Check that FRONTEND_GUIDELINES.md references the same framework, styling, and component library
- Check that BACKEND_STRUCTURE.md references the same backend framework and database
- Check that CI_CD.md references the same hosting platform
- **Flag:** Any tech choice that is referenced differently across files

### 3d: Status Consistency

- Check PRD.md section registry statuses match the actual state of section spec files
- A section marked `shaped` should have a corresponding file in `docs/tasks/sections/`
- A section marked `defined` should NOT have a section spec file yet (or the file is a stub)
- **Flag:** Any status mismatch

### 3e: Copy Gap Detection

- For each shaped section spec in `docs/tasks/sections/`, check if the section is a **public-facing page** (landing, pricing, about, feature, product, homepage, contact/demo)
- If it is public-facing, check for a `## Copy Status` section in the spec. If it says "Not yet created" or if no Copy Status section exists, flag it.
- **Flag:** "Section [name] is a public-facing page with no copy document. Run the web-copy skill to create page copy before implementation."

---

## Step 4: Present Completeness Report

Present a summary report to the user:

```
## Spec Completeness Report

| File | Completeness | Gaps | Inconsistencies |
|------|-------------|------|-----------------|
| PRD.md | 85% | 2 TBDs | — |
| TECH_STACK.md | 100% | — | — |
| DESIGN_SYSTEM.md | — | [not created yet] | — |
| APP_FLOW.md | 70% | 3 TBDs, 1 empty section | 1 route mismatch |
| BACKEND_STRUCTURE.md | 90% | 1 TBD | 1 entity name mismatch |
| FRONTEND_GUIDELINES.md | 60% | 4 TBDs | — |
| CI_CD.md | 100% | — | — |
| Section: auth | shaped | — | — |
| Section: dashboard | [not shaped yet] | — | — |

### Gaps Found:

1. [PRD.md] Success Metrics: TBD
2. [PRD.md] Data Shape → Relationships: TBD
3. [APP_FLOW.md] Error Handling → Network Offline: TBD
4. [APP_FLOW.md] Accessibility: empty section
5. [APP_FLOW.md] Error Handling → 500: TBD
6. [BACKEND_STRUCTURE.md] External Services: TBD
7. [FRONTEND_GUIDELINES.md] Responsive Strategy → Minimum Width: TBD
8. [FRONTEND_GUIDELINES.md] Responsive Strategy → Tablet Layouts: TBD
9. [FRONTEND_GUIDELINES.md] State Management → URL State: TBD
10. [FRONTEND_GUIDELINES.md] Component Architecture → Naming Conventions: TBD

### Inconsistencies Found:

1. [CROSS-FILE] Entity "User" in PRD.md is called "Account" in BACKEND_STRUCTURE.md
2. [CROSS-FILE] Route "/projects" in APP_FLOW.md but section is "project-management" in PRD.md

### Missing Files:

- DESIGN_SYSTEM.md — run /define-design to create it
- docs/tasks/sections/dashboard.md — run /shape-section dashboard to create it

Which items would you like to fix? You can:
- Pick by number (e.g., "1, 3, 7")
- Pick by file (e.g., "all APP_FLOW gaps")
- Fix all gaps ("all")
- Fix inconsistencies only ("inconsistencies")
```

---

## Step 5: Fix Selected Items

For each selected item:

### For TBD/Empty Gaps:

Re-ask the original guided question that would have produced this answer. Use the **same guided format** as the original command: WHY context, options table, recommendation based on current project state.

For example, if the user wants to fill in "APP_FLOW.md Error Handling → Network Offline":

```
### Error Handling: Network Offline

WHY: Users on flaky connections need clear feedback when the app loses connectivity.

How should the app handle network connectivity loss?

| Option | Best When | Example |
|--------|-----------|---------|
| Toast notification | Brief interruptions | "Connection lost. Retrying..." with auto-dismiss on reconnect |
| Full-page overlay | Critical operations | Modal blocking interaction until connection restored |
| Offline mode | Progressive web app | Cache recent data, queue actions, sync on reconnect |
| Inline indicators | Per-component feedback | Red dot on components that can't refresh |

**Recommended:** [Based on current app type and users]

**If unsure:** Answer "TBD" to keep it unfilled for now.
```

After the user answers, write ONLY the changed field to the appropriate file. Do not modify other sections.

### For Inconsistencies:

Present the mismatch and ask the user which version is correct:

```
Entity name mismatch:
- PRD.md calls it "User"
- BACKEND_STRUCTURE.md calls it "Account"

Which name should be used everywhere? (or provide a different name)
```

After the user decides, update ALL files that reference the old name to use the new name.

### For Missing Files:

Suggest the appropriate command:

```
DESIGN_SYSTEM.md doesn't exist yet. Run /define-design to create it.
Section spec for "dashboard" doesn't exist. Run /shape-section dashboard to create it.
```

---

## Step 6: Cascade Changes

After fixing items, check if any change needs to cascade to other files:

- **Project name change** → update CLAUDE.md, README.md, all architecture docs
- **Entity rename** → update PRD.md, BACKEND_STRUCTURE.md, all section specs that reference it
- **Section rename** → update PRD.md registry, rename section spec file, update APP_FLOW.md routes
- **Tech stack change** → update TECH_STACK.md, FRONTEND_GUIDELINES.md, BACKEND_STRUCTURE.md, CI_CD.md

Present cascading changes before making them:

```
This change will cascade to:
- BACKEND_STRUCTURE.md: rename "Account" to "User" (3 occurrences)
- docs/tasks/sections/auth.md: rename "Account" to "User" (1 occurrence)

Proceed? (yes/no)
```

---

## Step 7: Summary

After all selected fixes are applied:

```
Done. Updated spec files:

| File | Changes |
|------|---------|
| [file] | [what was changed] |

Remaining gaps: [count] across [files]
Remaining inconsistencies: [count]

Run /update-spec again anytime to check for new gaps.
```

---

## Behavioral Rules

1. **Read ALL spec files first.** Do not present a report until you've scanned everything.
2. **Never invent information.** Only write what the user explicitly tells you.
3. **Use guided format for re-asking.** Every gap-filling question gets the same educational format as the original command.
4. **Show cascading changes before applying.** Let the user confirm cross-file updates.
5. **Preserve existing content.** When fixing a gap, only modify the specific field — do not rewrite surrounding sections.
6. **Accept "TBD" gracefully.** If the user still doesn't have an answer, keep it as TBD.
7. **Track what was changed.** Present a clear summary of all modifications at the end.
