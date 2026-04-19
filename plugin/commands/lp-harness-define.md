---
name: lp-harness-define
description: Meta-orchestrator for product definition. Chains /lp-define-product → /lp-define-design → /lp-define-architecture → /lp-shape-section.
---
# /lp-harness-define

Meta-orchestrator for the definition phase. Runs definition commands in sequence, detecting existing artifacts for update mode.

## Usage

```
/lp-harness-define                → full sequence (product → design → architecture → shape)
/lp-harness-define product        → only /lp-define-product
/lp-harness-define design         → only /lp-define-design
/lp-harness-define architecture   → only /lp-define-architecture
```

**Arguments:** `$ARGUMENTS` (parse for optional target: `product`, `design`, `architecture`)

---

## Step 1: Resolve Target

- IF `$ARGUMENTS` specifies a target (`product`, `design`, `architecture`): run only that step
- IF no target: run full sequence (Steps 2-5)

## Step 2: /lp-define-product

- Check if `docs/architecture/PRD.md` exists
  - IF exists: run `/lp-define-product` in **update mode** (preserve existing content, add/modify sections)
  - IF not: run `/lp-define-product` in **fresh mode**

## Step 3: /lp-define-design

- Check if `docs/architecture/DESIGN_SYSTEM.md` exists
  - IF exists: run `/lp-define-design` in **update mode**
  - IF not: run `/lp-define-design` in **fresh mode**

## Step 4: /lp-define-architecture

- Check if `docs/architecture/BACKEND_STRUCTURE.md` exists
  - IF exists: run `/lp-define-architecture` in **update mode**
  - IF not: run `/lp-define-architecture` in **fresh mode**

## Step 5: Shape Sections

- Ask user which sections to shape (cap 3 per session to avoid fatigue)
- For each selected section: run `/lp-shape-section` internally
- Each shaped section gets status `shaped` in its spec file frontmatter

## Step 6: Transition

"Run `/lp-harness-plan [section]` to start planning."
