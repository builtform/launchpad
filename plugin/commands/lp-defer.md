---
name: lp-defer
description: "Manually add a task to the project backlog. Creates a deferred observation in .harness/observations/ for the next /lp-regenerate-backlog run."
---
# /lp-defer

Manually add a task to the project backlog.

## Usage

```
/lp-defer "Add pagination to items endpoint" --priority P2 --area api
/lp-defer "Fix login redirect on expired tokens"                        → defaults to P2, area "general"
/lp-defer "Update Stripe webhook handler" --priority P1                 → defaults to area "general"
```

**Arguments:** `$ARGUMENTS` (parse for quoted description, `--priority`, `--area`)

---

## Flow

### Step 0: Ensure runtime state

- `mkdir -p .harness/observations` — ensures the write target exists in brownfield

### Step 1: Parse Arguments

- `description`: required (quoted string). IF missing: ask user for one.
- `--priority`: optional, defaults to `P2`. Must be P1, P2, or P3.
- `--area`: optional, defaults to `"general"`.

### Step 2: Generate Observation File

- ID: timestamp-based — `YYYYMMDD-HHMMSS` (no race conditions)
- Slug: lowercase, hyphens, max 60 chars from description
- Filename: `{YYYYMMDD-HHMMSS}-{slug}.md`

### Step 3: Write File

Write to `.harness/observations/{filename}`:

```yaml
---
status: deferred
priority: P2
agent_source: manual
area: general
deferred_date: YYYY-MM-DD
---
# {description}

Manually deferred via /lp-defer on {date}.
```

### Step 4: Confirm

"Deferred: '{description}' (P{n}, {area}) → .harness/observations/{filename}"

---

## Rules

1. Description is required — prompt if missing
2. Priority defaults to P2
3. Area defaults to "general"
4. Do NOT regenerate BACKLOG.md — happens at next workflow endpoint
