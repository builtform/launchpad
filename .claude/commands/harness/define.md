---
name: harness:define
description: Meta-orchestrator for product definition. Chains /define-product → /define-design → /define-architecture → /shape-section.
---

# /harness:define

Meta-orchestrator for the definition phase. Runs definition commands in sequence, detecting existing artifacts for update mode.

## Usage

```
/harness:define                → full sequence (product → design → architecture → shape)
/harness:define product        → only /define-product
/harness:define design         → only /define-design
/harness:define architecture   → only /define-architecture
```

**Arguments:** `$ARGUMENTS` (parse for optional target: `product`, `design`, `architecture`)

---

## Step 1: Resolve Target

- IF `$ARGUMENTS` specifies a target (`product`, `design`, `architecture`): run only that step
- IF no target: run full sequence (Steps 2-5)

## Step 2: /define-product

- Check if `docs/architecture/PRD.md` exists
  - IF exists: run `/define-product` in **update mode** (preserve existing content, add/modify sections)
  - IF not: run `/define-product` in **fresh mode**

## Step 3: /define-design

- Check if `docs/architecture/DESIGN_SYSTEM.md` exists
  - IF exists: run `/define-design` in **update mode**
  - IF not: run `/define-design` in **fresh mode**

## Step 4: /define-architecture

- Check if `docs/architecture/BACKEND_STRUCTURE.md` exists
  - IF exists: run `/define-architecture` in **update mode**
  - IF not: run `/define-architecture` in **fresh mode**

## Step 5: Shape Sections

- Ask user which sections to shape (cap 3 per session to avoid fatigue)
- For each selected section: run `/shape-section` internally
- Each shaped section gets status `shaped` in its spec file frontmatter

## Step 6: Transition

"Run `/harness:plan [section]` to start planning."
