---
generated_by: /lp-pick-stack
last_validated: 2026-04-30
purpose: strict markdown template /lp-pick-stack fills to produce .launchpad/rationale.md
---

# Rationale Template

This file is the **strict template** that `/lp-pick-stack` (Phase 2) fills in
to generate `.launchpad/rationale.md`. Section headers are load-bearing: the
Phase -1 `rationale_summary_extractor.py` parses by `## <slug>` headers, so
slugs MUST match the `ALLOWED_SECTIONS` set
(`project-understanding`, `matched-category`, `stack`, `why-this-fits`,
`alternatives`, `notes`).

Bullets MUST satisfy the §9.1 sanitization filter: ≤240 chars per bullet, no
fenced code blocks, no URLs (`http://`, `https://`, `file://`, `data:`,
`javascript:`, `vbscript:`), no `<` or `>` characters, NFKC-normalized
text only, no Unicode `Cf`/`Cc` category characters (zero-width joiners,
format chars).

The frontmatter `matched_category_id` MUST equal an `id` from
`category-patterns.yml`. The frontmatter `generated_at` is ISO 8601 UTC
(matches the `generated_at` format used in `scaffold-decision.json`).

---

## Template body

When Claude fills this template, it produces a file at `.launchpad/rationale.md`
shaped exactly as below, with placeholder bullets replaced by content. Section
headers and frontmatter keys are fixed; bullet counts may vary 1-8 per section.

```markdown
---
generated_by: /lp-pick-stack
generated_at: <ISO 8601 UTC, e.g. 2026-04-30T12:34:56Z>
matched_category_id: <id from category-patterns.yml>
---

# Why this stack?

## project-understanding

- <one-bullet summary of project shape from user's Q1 + description>
- <optional second bullet on key constraint or AI/ML need>

## matched-category

- <category id and one-line description from category-patterns.yml>

## stack

- <bullet per layer in canonical_stack: stack + role + path>

## why-this-fits

- <bullet matching project to fits_when predicate 1>
- <bullet matching project to fits_when predicate 2>
- <optional third bullet on team-language alignment>

## alternatives

- <one or more sibling categories that came close, with one-line "why not">

## notes

- <optional bullet on v2.x candidates, override hints, or constraints>
```

## Section semantics

- **project-understanding** — 1-2 bullets summarizing what the user wants to
  build. Sourced from Q1 (project shape) + project-description free text.
  Free text is ALREADY wrapped in `<untrusted_user_input>` upstream; the
  rationale extractor's NFKC + forbidden-bullet checks defend against
  prompt-injection that bypassed the upstream envelope.

- **matched-category** — exactly 1 bullet naming the matched
  `category-patterns.yml` entry by id + name. Sourced from the engine's
  highest-scoring match.

- **stack** — 1 bullet per layer in `canonical_stack`. Format: `<stack> as
<role> at <path>`. Sourced from the matched category's `canonical_stack`
  array.

- **why-this-fits** — 2-3 bullets explaining why the matched category's
  `fits_when` predicates align with the user's answers + description.
  Pillar-framework.md content may inform this section's framing but MUST NOT
  be quoted verbatim (avoid leaking framework prose into user-visible output).

- **alternatives** — REQUIRED ≥1 entry when `matched_category_id` is in an
  ambiguity_cluster from `category-patterns.yml` (per HANDSHAKE §4 rule 7).
  Otherwise optional. Format: one-line `<alt-category-name>: <why not for
this user>`.

- **notes** — Optional bullet for v2.x candidates (e.g., "if you later need
  Phoenix LiveView, that's tracked at v2.2"), override hints, or
  project-specific constraints worth flagging in the receipt for /lp-define
  to surface in the Tier 1 panel.

## Length budget

Total file ≤ 200 lines or ≤ 8000 bytes, whichever is smaller. The
`rationale_summary_extractor.py` truncates per-section to 8 bullets and
240 chars/bullet; longer files parse but contribute no extra signal.
