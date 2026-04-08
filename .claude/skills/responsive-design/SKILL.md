---
name: responsive-design
description: "Injects responsive-first thinking into section specs and design definitions. Loaded by spec-layer commands (/shape-section, /define-design, /pnf) to ensure every spec includes explicit mobile-first layout decisions, breakpoint behavior per component, container query strategy, touch target requirements, and fluid typography. Triggers on: loaded alongside /shape-section, /define-design, /pnf."
---

# Responsive Design — Spec Layer Skill

**NEVER produce a responsive behavior section that says "make it responsive" or "use responsive breakpoints." Every responsive definition must specify WHAT changes, at WHICH query (viewport or container), and WHY. Vague responsive guidance is worse than none — it creates false confidence that responsiveness was addressed.**

---

## Trigger

This skill activates when loaded alongside spec-layer commands:

- `/shape-section` — adds a "Responsive Behavior" section to every section spec
- `/define-design` — ensures DESIGN_SYSTEM.md includes responsive tokens and FRONTEND_GUIDELINES.md includes responsive strategy
- `/pnf` — ensures implementation plans include responsive requirements per component

This skill does NOT activate for:

- Post-implementation audits (use `design-responsive-auditor` agent)
- Visual design decisions (use `design-alignment-checker` agent)
- General accessibility (only responsive-specific WCAG criteria: 1.4.4, 1.4.10, 2.5.8)
- Performance optimization (CLS is mentioned as responsive-adjacent, not owned)

---

## What This Skill Does NOT Handle

| Request                                                | Use Instead                         |
| ------------------------------------------------------ | ----------------------------------- |
| Audit existing responsive implementation               | `design-responsive-auditor` agent   |
| Visual design, hierarchy, color, typography aesthetics | `design-alignment-checker` agent    |
| General WCAG accessibility compliance                  | Accessibility skill or manual audit |
| Performance optimization (LCP, INP)                    | Performance audit tooling           |
| CSS/Tailwind code generation                           | Build agent during implementation   |

---

## The Job

| Step | Action                        | Visible Output                                                 |
| ---- | ----------------------------- | -------------------------------------------------------------- |
| 0    | Detect calling context        | State which command loaded this skill and what mode applies    |
| 1    | Read responsive foundation    | Report on DESIGN_SYSTEM.md responsive tokens (present/missing) |
| 2    | Inject responsive definitions | Per-component responsive behavior specs added to output        |
| 3    | Validate completeness         | Responsive coverage checklist — all UI elements accounted for  |

---

## Step 0: Detect Calling Context

Identify which command loaded this skill. The injection behavior differs:

**Mode A — `/define-design`:**

- Inject responsive tokens into DESIGN_SYSTEM.md output (breakpoints, container breakpoints, fluid type scale)
- Inject responsive strategy into FRONTEND_GUIDELINES.md output
- Follow the define-design question flow; enhance answers DS-4 (Spacing & Layout) and FG-3 (Responsive Strategy) with responsive-specific depth

**Mode B — `/shape-section`:**

- After the user answers S-5 (UI Patterns), inject a responsive behavior definition for EVERY UI pattern chosen
- Add a "Responsive Behavior" section to the section spec output
- This is the primary mode — most responsive decisions happen here

**Mode C — `/pnf`:**

- For each component in the implementation plan, include responsive requirements
- Reference the section spec's Responsive Behavior section
- Flag any component that lacks a responsive definition

**Output:** State the detected mode: "Responsive design skill loaded in Mode [A/B/C] for [command name]."

---

## Step 1: Read Responsive Foundation

Read `docs/architecture/DESIGN_SYSTEM.md` and `docs/architecture/FRONTEND_GUIDELINES.md`.

Check for these responsive tokens:

| Token Category        | What to Look For                          | If Missing                                          |
| --------------------- | ----------------------------------------- | --------------------------------------------------- |
| Viewport breakpoints  | sm/md/lg/xl/2xl definitions               | Use Tailwind v4 defaults (640/768/1024/1280/1536px) |
| Container breakpoints | @sm/@md/@lg/@xl definitions               | Use Tailwind v4 defaults (384/448/512/576px)        |
| Fluid type scale      | clamp() definitions for headings          | Flag as gap — define during injection               |
| Responsive strategy   | Mobile-first vs desktop-first declaration | Default to mobile-first                             |
| Touch target standard | Minimum size declaration                  | Default to 44x44px (WCAG AAA) with 8px spacing      |
| Container padding     | Per-viewport padding values               | Flag as gap                                         |

**Output:** Report each token category as `[FOUND]` or `[MISSING — using default: X]`.

---

## Step 2: Inject Responsive Definitions

### Mode A: `/define-design` Injection

When the define-design command reaches **DS-4 (Spacing & Layout)**, enhance the question with:

```
RESPONSIVE TOKENS (injected by responsive-design skill):

In addition to your spacing system, define these responsive foundations:

1. Viewport breakpoints — use Tailwind v4 defaults or customize?
2. Container breakpoints — which components will use @container queries?
3. Fluid type scale — clamp() definitions for heading sizes
4. Container padding — padding values per viewport (mobile/tablet/desktop)
5. Touch target minimum — 44x44px (AAA) or 24x24px (AA)?
```

When the define-design command reaches **FG-3 (Responsive Strategy)**, enhance the output to include:

- Viewport query vs container query decision rule
- Mobile-first layout strategy (base = mobile, enhance upward)
- The 3 WCAG responsive criteria as non-negotiable requirements
- Touch target enforcement policy

Write these tokens into the DESIGN_SYSTEM.md and FRONTEND_GUIDELINES.md outputs.

### Mode B: `/shape-section` Injection

After the user answers **S-5 (UI Patterns)**, for EACH chosen UI pattern, generate a responsive behavior definition.

**For each UI pattern, produce this structure:**

```markdown
### [Pattern Name] — Responsive Behavior

**Query type:** [viewport / container] — [1-sentence reason]

| Viewport/Container       | Layout                     | Key Changes                      |
| ------------------------ | -------------------------- | -------------------------------- |
| Base (mobile)            | [exact layout description] | [what is visible/hidden/stacked] |
| @sm / sm (if applicable) | [layout change]            | [what changes]                   |
| @md / md                 | [layout change]            | [what changes]                   |
| @lg / lg                 | [layout change]            | [what changes]                   |
| @xl / xl (if applicable) | [layout change]            | [what changes]                   |

**Touch targets:** [list interactive elements with minimum size]
**Fluid typography:** [heading levels with clamp() values if applicable]
**WCAG notes:** [specific failure modes to prevent for this pattern]
```

Only include breakpoint rows where the layout actually changes. Do not list every breakpoint if nothing changes at that size.

**Decision rule for viewport vs container:**

- Page-level layout (sidebar, navigation, main content grid) = viewport queries
- Component internals (card layout, widget, reusable component) = container queries
- Navigation structure = viewport queries
- Reusable design system components = container queries

### Mode C: `/pnf` Injection

For each component in the implementation plan:

1. Check if the section spec has a Responsive Behavior definition for this component
2. If yes: include it as a requirement in the implementation step
3. If no: flag it — "This component lacks a responsive behavior definition. Define it before implementation or accept default stacking behavior."

Add a responsive verification step at the end of the plan:

```
RESPONSIVE VERIFICATION:
- [ ] Every component renders correctly at 320px width (WCAG 1.4.10)
- [ ] All text scales at 200% browser zoom without overflow (WCAG 1.4.4)
- [ ] All interactive elements meet touch target minimum (WCAG 2.5.8)
- [ ] Container queries used for component internals, viewport queries for layout
- [ ] No horizontal scrollbar at any width from 320px to 2560px
```

---

## Step 3: Validate Completeness

Before the calling command writes its output, run this checklist:

| Check                                        | Pass Condition                                                                             |
| -------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Every UI pattern has a responsive definition | No UI pattern from S-5 lacks a Responsive Behavior section                                 |
| No vague responsive language                 | Zero instances of "make responsive," "add breakpoints," "test on mobile" without specifics |
| Touch targets specified                      | Every interactive element has an explicit minimum size                                     |
| Query type decided per component             | Every component specifies viewport OR container queries with rationale                     |
| Mobile layout defined first                  | Base state in every responsive table is the mobile layout                                  |
| WCAG criteria addressed                      | 1.4.4 (resize text), 1.4.10 (reflow), 2.5.8 (target size) covered                          |
| Fluid typography defined                     | Headings use clamp() or reference the fluid type scale                                     |

**If any check fails:** Fix it before the calling command writes the output. Do not defer responsive definitions to implementation.

---

## Relationship to Other Skills

| Skill                   | Boundary                                                                                                        |
| ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| `frontend-design`       | Creative direction and aesthetic choices. This skill handles structural responsive behavior, not visual design. |
| `web-design-guidelines` | Engineering rules for implementation. This skill operates at the spec level before implementation begins.       |

---

## Verification

Before the calling command completes, confirm:

- [ ] Every UI element has an explicit responsive behavior definition (not "make it responsive")
- [ ] Mobile layout is the base state in every responsive definition
- [ ] Viewport vs container query decision is explicit per component
- [ ] Touch targets: 44x44px minimum, 8px spacing between targets
- [ ] Fluid typography: clamp() for headings, rem for body text
- [ ] WCAG 1.4.4 (resize text), 1.4.10 (reflow at 320px), 2.5.8 (target size) addressed
- [ ] No hedge language ("consider," "you might want to," "perhaps")
- [ ] Zero vague responsive statements

---

**NEVER produce a responsive behavior section that says "make it responsive" or "use responsive breakpoints." Every responsive definition must specify WHAT changes, at WHICH query (viewport or container), and WHY. Vague responsive guidance is worse than none — it creates false confidence that responsiveness was addressed.**
