---
name: lp-brainstorm
description: Collaborative brainstorming with codebase research, structured dialogue, and design document capture. NEVER writes code.
---

# /lp-brainstorm

Collaborative brainstorming command. Explores ideas, generates approaches, and captures design documents.

**Arguments:** `$ARGUMENTS` (optional topic)

---

## Phase 0: Assess Clarity + cwd_state routing

- **cwd_state routing (v2.0 pipeline)** — call `cwd_state.cwd_state(cwd)`
  per `docs/architecture/SCAFFOLD_HANDSHAKE.md` §8 BEFORE the brainstorm
  prompt. The result drives the "Suggested next step" section the
  brainstorm-summary will close with:
  - `empty` (greenfield): suggest `/lp-pick-stack`
  - `brownfield`: suggest `/lp-define` (the brownfield happy path skips
    `/lp-pick-stack` + `/lp-scaffold-stack` entirely)
  - `ambiguous`: prompt the user to confirm intent; default to brownfield
    suggestion on no-answer
- The `cwd_state_when_generated` field in `brainstorm-summary.md`
  frontmatter is the result of THIS classification — recomputed on every
  re-run per HANDSHAKE §7 (never inherited from a prior summary).
- IF requirement is already clear and specific: skip to Phase 2
- IF vague or exploratory: proceed to Phase 1

## Phase 1: Understand the Idea

1. Load brainstorming skill (process knowledge)
2. IF codebase exists (package.json or similar detected):
   - Dispatch `lp-code-analyzer` + `lp-pattern-finder` in parallel (lightweight repo scan)
   - Research agents MAY read schemas, routes, configs to verify infrastructure claims
   - Prevents stating "table X does not exist" without checking
3. Collaborative dialogue:
   - One question at a time (NEVER batch)
   - Start broad, narrow progressively
   - Cover: Purpose, Users, Constraints, Success Criteria, Edge Cases, Existing Patterns
4. Unverified claims MUST be labeled as assumptions:
   "Assumption: no existing payments table" (not "there is no payments table")
5. NEVER write code — explore and document decisions only

## Phase 2: Explore Approaches

- Present 2-3 concrete approaches
- Each: Name, Description, Pros, Cons, "Best When"
- Lead with recommendation
- Apply YAGNI: simplest approach that meets requirements

## Phase 3: Capture Design Document

1. BEFORE writing: scan for unverified absence claims ("does not exist", "no current", "there is no") — verify or relabel as "Assumption: ..."
2. Scan capture for PII and secrets (email, phone, API keys, tokens, connection strings, internal URLs, real customer data) — replace with anonymized placeholders
3. Topic slug: lowercase, hyphens only, strip special characters, max 50 chars
4. Run `mkdir -p docs/brainstorms/` before writing
5. Write to: `docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md`
6. Template sections:
   - What We're Building
   - Why This Approach
   - Key Decisions
   - Open Questions
   - Next Steps
7. **v2.0 pipeline brainstorm-summary** — when the brainstorm is part of
   the v2.0 greenfield pipeline (cwd_state classified at Phase 0), ALSO
   write `.launchpad/brainstorm-summary.md` per `docs/architecture/SCAFFOLD_HANDSHAKE.md`
   §7 with this frontmatter shape:

   ```markdown
   ---
   generated_at: <ISO 8601 UTC sec-precision Z-suffix>
   generated_by: /lp-brainstorm
   greenfield: <true if cwd_state == "empty" else false>
   cwd_state_when_generated: <empty | brownfield | ambiguous>
   ---

   # Project summary

   <2-4 paragraphs of free-form Markdown describing the project intent.>

   # Suggested next step

   Run `/lp-pick-stack` next to choose a stack.

   <!-- Or for brownfield: "Run /lp-define next." -->
   ```

   The body is treated as untrusted-as-data by every later-stage consumer;
   `/lp-pick-stack` re-asks the user for a project description rather than
   parsing the body. Re-running `/lp-brainstorm` overwrites the summary
   with a new `generated_at` and recomputed `cwd_state_when_generated`.

8. **Greenfield first-run marker (v2.0 pipeline; SCAFFOLD_HANDSHAKE.md §4 rule 10 strip-back substitute)**:
   - Compute `cwd_state(.)` via `python3 plugins/launchpad/scripts/cwd_state.py` (or import + call) — ONLY proceed with marker write when state == "empty"
   - For `brownfield` or `ambiguous` cwds: skip the marker write entirely; suggest `/lp-define` (brownfield happy path) and stop
   - For `empty` (greenfield) cwds: `mkdir -p .launchpad/` then create `.launchpad/.first-run-marker` via `os.open(".launchpad/.first-run-marker", O_WRONLY | O_CREAT | O_EXCL, 0o600)` — the `O_EXCL` flag race-detects concurrent `/lp-brainstorm` invocations
   - On `FileExistsError`: refuse with the user-facing hint: **"session in progress; remove `.launchpad/.first-run-marker` if stale OR run `/lp-scaffold-stack` to consume it first"** and exit
   - The marker is an empty positive-presence sentinel — NO JSON envelope, NO sha256, NO bound_cwd, NO `.first-run-marker.lock`. The integrity-bound JSON envelope is BL-235 deferred to v2.2 per `docs/architecture/SCAFFOLD_HANDSHAKE.md` §1.5 strip-back notice
   - The marker tells `/lp-scaffold-stack` that this cwd is mid-pipeline (authorizes the empty-nonce-ledger first-run fast path); after `/lp-scaffold-stack` succeeds it gets renamed to `.first-run-marker.consumed.<iso-sec-ts>`

## Phase 4: Refine + Handoff

1. Load document-review skill
2. Offer refinement pass (max 2 passes, then recommend completion)
3. Handoff options:
   - a) "Review and refine further" (re-enter document-review)
   - b) "Proceed to planning" → "Run /lp-define"
   - c) "Ask more questions" (re-enter Phase 1)
   - d) "Done for now"

---

## Strict Rules

- NEVER write code — brainstorm is about ideas, not implementation
- One question at a time — never dump 5 questions
- Always capture before handoff — no lost brainstorms
- Research agents are optional — skip if no codebase exists
