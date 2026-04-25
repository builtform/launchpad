---
name: lp-plan
description: Meta-orchestrator for interactive planning pipeline. Chains design → /lp-pnf → /lp-harden-plan → human approval based on section registry status.
---

# /lp-plan

Interactive planning pipeline orchestrator. Resolves target from section registry status and chains through design → plan → harden → approval.

**Arguments:** `$ARGUMENTS` (optional section name or free-text description)

---

## Step 0: Prerequisite & Capability Check

Before resolving targets, validate the state this command depends on.

### 0.1 — Load config and registry

Load `.launchpad/config.yml` via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-config-loader.py`. Extract:

- `pipeline.plan.design_review` — if `skipped`, Step 2 (design) is skipped entirely
- `pipeline.plan.pnf` / `pipeline.plan.harden` — both default to `enabled`

Load section registry via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin_stack_adapters/section_registry.py`.
It reads `docs/tasks/SECTION_REGISTRY.md` first; if absent, falls back to parsing PRD.md and emits a one-line deprecation warning to stderr suggesting the user re-run `/lp-define`. The back-compat shim is removed in v1.1.

**IF neither SECTION_REGISTRY.md NOR PRD.md exists:** exit with

> "No section registry found. Run `/lp-define` to scaffold canonical docs first, then `/lp-shape-section <name>` to add your first section."

### 0.2 — Resolve section target

Using `$ARGUMENTS`:

- **Named section** (e.g. `/lp-plan auth-redesign`): look up in registry. If missing:
  > "Section `auth-redesign` not found in registry. Existing sections: [list]. Run `/lp-shape-section auth-redesign` to add it."
- **No argument**: list shaped/designed/planned sections from the registry and prompt the user to pick.
- **Free-text**: preserve existing CASE B behavior below.

### 0.3 — Autonomous-build integrity check

If the user is planning to auto-approve through to `/lp-build` (CASE A path ending at approval), run `section_added_with_ack(repo_root, section_name)` from `autonomous_guard.py`.

IF **True** (section spec and `.launchpad/autonomous-ack.md` were introduced in the same commit): refuse the auto-approval fast-path with:

> "This section was added to the registry in the same commit that introduced `.launchpad/autonomous-ack.md`. That's the exact pattern a hostile PR would use to bypass review. Human plan approval is still available (Step 5) but auto-approval is blocked. Verify the section spec is legitimate before proceeding."

Human plan approval in Step 5 is still the authoritative gate; this is belt-and-suspenders.

### 0.4 — Pipeline skip integration

If `pipeline.plan.design_review: skipped`:

- Skip Step 2 entirely
- Set status to `"design:skipped"`
- Proceed to Step 3 (`/lp-pnf`)

This means backend-only projects never see the design workflow, without `/lp-plan` needing to re-detect the stack.

---

## Guard: Status Check

1. Read section spec file's YAML frontmatter `status:` field
2. Validate registry integrity (see below)
3. IF status is `approved` or beyond → **REFUSE:** "Already approved. Run /lp-build"

### Registry Integrity Validation

Before proceeding, validate expected artifacts exist for current status:

| Status     | Expected Artifacts                                                                         |
| ---------- | ------------------------------------------------------------------------------------------ |
| `designed` | Design artifacts in `.harness/design-artifacts/` (or `"design:skipped"` with no artifacts) |
| `planned`  | Plan file exists                                                                           |
| `hardened` | Hardening notes section exists in plan                                                     |
| `approved` | `approved_at` field present + plan file exists                                             |

**Plan file path:** resolves from `paths.plans_file_pattern` in `.launchpad/config.yml` (default `docs/tasks/sections/{section_name}-plan.md`). Expand `{section_name}` with the section name to get the concrete path. Same convention used by `/lp-pnf` (writes) and `/lp-build` (reads).

Refuse with descriptive error if inconsistent (e.g., "Status is 'approved' but approved_at field missing. Re-run /lp-plan for human approval.").

---

## Step 1: Resolve Target

### CASE A: Named target or no argument → registry lookup

Look up section in `docs/tasks/sections/{section-name}.md`:

| Current Status                   | Route To                     |
| -------------------------------- | ---------------------------- |
| `hardened`                       | Step 5 (approval)            |
| `planned`                        | Step 4 (harden)              |
| `designed` or `"design:skipped"` | Step 3 (plan)                |
| `shaped`                         | Step 2 (design)              |
| `defined` or no status           | "Not shaped. Run /lp-define" |
| No section found                 | → CASE B                     |

### CASE B: Free-text → Step 2

If no matching section or free-text provided, start from Step 2 (design check).

---

## Step 2: Design Step

> **Skip gate:** if Step 0.4 set status to `"design:skipped"` (config.yml's `pipeline.plan.design_review: skipped`), jump directly to Step 3. The UI-detection logic below only runs when the pipeline is configured for design review — backend-only projects skip this entire step by configuration, not by ad-hoc keyword detection.

Design runs before `/lp-pnf` so the plan incorporates concrete design decisions.

### UI Detection

Parse the section spec for UI indicators:

**UI keyword list:** component, page, layout, hero, section, card, modal, dialog, form, input, button, nav, sidebar, header, footer, table, list, grid, dashboard, chart, graph, onboarding, wizard, stepper, carousel, accordion, tab, panel, dropdown, tooltip, popover, badge, avatar, banner, toast, notification, empty state, loading, skeleton, spinner

**File reference check:** any path containing `apps/web/` or `packages/ui/`

**Decision:**

- IF (keyword count >= 2) OR (file reference found): "This section involves UI work. Run design workflow? (yes/skip)"
- ELSE: "No UI work detected. Planning UI work anyway? (yes/skip)"
- IF user says "skip": write status `"design:skipped"` → jump to Step 3

### Step 2a: Autonomous First Draft

**Load context:**

1. `docs/architecture/DESIGN_SYSTEM.md` (design tokens, palette, typography)
2. `docs/architecture/APP_FLOW.md` (navigation, user journeys)
3. `docs/architecture/FRONTEND_GUIDELINES.md` (component patterns, file structure)
4. Section spec file (what to build)
5. `.harness/design-artifacts/` (existing approved designs for visual consistency)

**Load skills:** `frontend-design`, `web-design-guidelines`, `responsive-design`

**Load copy:** Run `/lp-copy` (reads copy brief from section spec if exists)

**Build:**

- Build UI components (write TSX/CSS following design system tokens)
- Open browser (agent-browser primary, Playwright MCP fallback)
  - Requires dev server running (detect, don't start)
- Screenshot → self-evaluate → adjust → screenshot (3-5 auto-cycles via `design-iterator`)
- Offer `/lp-design-onboard` if section involves onboarding/empty states
- Present first draft to user with live localhost URL

### Step 2b: Interactive Refinement

Guide the user through iterative design improvement:

- User gives feedback → dispatch `design-iterator` (ONE change per iteration)
- User requests Figma sync → dispatch `figma-design-sync` (requires Figma URL)
- User requests systematic polish → run `/lp-design-polish`
- Skills stay loaded: `frontend-design`, `web-design-guidelines`, `responsive-design`

Session guides user: "Give feedback / Run /lp-design-polish / Provide Figma URL / Say 'looks good'"

### Step 2c: Design Review & Audit

1. Run `/lp-design-review` first (sequential — comprehensive 8 design + 4 tech dimensions, AI slop detection)
2. Then in parallel:
   - `design-ui-auditor` (5 quick checks)
   - `design-responsive-auditor` (6 responsive checks)
   - `design-alignment-checker` (14-dimension audit)
   - `design-implementation-reviewer` (Figma comparison — IF Figma URL was provided during session)
   - `/lp-copy-review` (dispatches `review_copy_agents` if configured)
3. Present findings
4. IF issues → back to 2b (iterate/fix → re-audit)
5. **Re-audit cap:** 3 cycles maximum. After 3 re-audit passes, if findings remain, present to user: "N findings remain after 3 review cycles. Approve with known issues / Continue iterating / Revise approach?"
6. WHEN clean → save approved screenshots to `.harness/design-artifacts/[section]-approved.png`
7. Set registry status → `designed` → proceed to Step 2d

### Step 2d: Design Walkthrough Recording (optional)

- `/lp-feature-video` (optional — record design walkthrough)
- Captures screenshots of approved design → MP4+GIF
- Uploads via rclone (if configured) or imgup
- Useful for sharing design decisions with team
- Proceed to Step 3

---

## Step 3: /lp-pnf [target]

- Run `/lp-pnf` with the section target
- Produces implementation plan
- Set registry status → `planned`

---

## Step 4: /lp-harden-plan [plan-path] --auto

- Determine intensity:
  - CASE A (section build): `--full` (8 agents when available)
  - CASE B (standalone feature): `--lightweight` (4 agents when available)
- Pass `--auto` for automatic application (no user prompt)
- `/lp-harden-plan` is idempotent: skips if "## Hardening Notes" already exists
- Set registry status → `hardened`

---

## Step 5: Human Approval Gate

Present plan summary to user:

- Plan content (key sections)
- Hardening notes
- Design status (`designed` or `"design:skipped"`)

Ask: **"Approve and start build? (yes / revise design / revise plan / revise both)"**

### IF yes:

- Set registry status → `approved`
- Write `approved_at: <ISO-8601 timestamp>` to section spec frontmatter
- Write `plan_hash: <short hash of plan file at approval time>` to section spec frontmatter
- Print transition: "Plan approved. Run `/lp-build` to execute autonomously (requires `.launchpad/autonomous-ack.md`), or `/lp-implement-plan` for step-by-step execution."
- Proceed to `/lp-build`

### IF revise design:

- Reset status to `shaped`
- Clear `.harness/design-artifacts/` (remove approved screenshots)
- Re-enter Step 2 (full design cycle restarts)

### IF revise plan:

- Reset status to `designed` or `"design:skipped"` (whichever was set)
- Re-enter Step 3 (`/lp-pnf`). Design artifacts preserved. Plan regenerated.

### IF revise both:

- Reset status to `shaped`
- Clear `.harness/design-artifacts/` (remove approved screenshots)
- Re-enter Step 2. Everything regenerated.
