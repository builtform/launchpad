---
stack: generic
pillar: Bring-your-own-framework
type: curate
last_validated: 2026-05-14
scaffolder_command: (curate — no scaffolder; user fills the workspace by hand)
scaffolder_command_pinned_version: n/a
---

# Generic — Knowledge Anchor (v2.1.4 BL-331)

## Purpose

The `generic` stack is a barebones LaunchPad workspace shell. There is no
upstream template fetch, no `npm create`, and no `git clone` — just the
LaunchPad cross-cutting wiring (lefthook hooks, `agents.yml`, `config.yml`,
CI workflows) over an empty workspace tree. The user brings their own
framework on top.

Use cases:

- A third-party Astro theme (or any other framework starter) the user has
  already curated, where LaunchPad's pinned upstream is the wrong choice.
- A framework not yet shipped with a stack-aware adapter
  (`StackIdV22Candidate` ids without an active `Adapter` Protocol
  implementation — e.g., SvelteKit, Remix, Solid, Phoenix-LiveView).
- A custom starter the user maintains internally (private monorepo
  template, company-internal scaffold, prototype that hasn't earned a
  full adapter yet).
- Power-user "pin everything yourself" workflows where LaunchPad's role
  is the cross-cutting wiring layer only.

This is distinct from the v2.2-candidate fallback path (passing
`--accept-v22-fallback` against a candidate id like `python_generic`),
which signals "you asked for X but X isn't ready yet." Picking
`generic` directly is an explicit positive intent, not a fallback.

## Idiomatic 2026 pattern

There is no idiomatic "generic" framework — the user picks any tooling
they want. LaunchPad provides the shell:

- `lefthook.yml` with the v2.1.1 hardened pre-commit + pre-push hook
  set (lint / typecheck / test / secret-scan / format-check).
- `.launchpad/config.yml` with the project's identity sealed (project
  name, license, repo URL, copyright holder, email) per the
  `/lp-pick-stack` Step 1.5 capture.
- `.harness/agents.yml` populated with the project-default review-agent
  roster.
- `.github/workflows/ci.yml` with the universal Python + JS gates
  matching the local lefthook configuration.

The user's own scaffolder (whichever they pick) goes in OVER this shell,
either before invoking `/lp-scaffold-stack` (manual prep) or after (then
running `/lp-define` to register the new stack with the harness). Either
ordering works; LaunchPad does not assume one.

## When to choose `generic` vs a stack-aware adapter

Choose **`generic`** when:

- You already have a starter you trust and don't want LaunchPad to fetch
  an upstream template.
- The framework you want isn't in the v2.1 supported list AND you don't
  want to wait for the v2.2 stack-aware adapter.
- You want LaunchPad's pipeline (review agents, lefthook, harness
  observations) over an existing minimal workspace.

Choose a **stack-aware adapter** (e.g., `astro`, `next`, `nextjs_fastapi`)
when:

- You want LaunchPad to fetch the canonical upstream template at a
  reproducible SHA.
- You want stack-aware defaults for `commands` (test / typecheck / lint
  / format / build) baked into `config.yml`.
- You want the cross-cutting wiring tuned to the framework's own
  conventions (e.g., `pnpm-workspace.yaml` for a Next monorepo).

## Cross-layer composition

`generic` composes with the three real v2.1 adapters (`astro`,
`nextjs_standalone`, `nextjs_fastapi`) per the
`plugin_stack_adapters/generic.py:_COMPOSES_WITH` map. It does NOT
compose with `ts_monorepo` (would create two top-level workspace
managers) and does NOT compose with itself (no-op pairing).

A canonical polyglot use case: `astro` (frontend) + `generic` (backend).
The user wants LaunchPad to scaffold the Astro side from the pinned
upstream but plans to bring their own backend (e.g., a Rust API server,
a Phoenix LiveView app, a Java Spring Boot service, a custom AWS Lambda
handler set). Picking `(astro, frontend)` + `(generic, backend)` in the
manual-override branch produces this shape.

## What `/lp-scaffold-stack` does for `generic`

- **No upstream fetch.** No `template_cache.fetch()` call. No git clone.
  No `npm create`. The adapter's `scaffold_into(tempdir)` is a one-line
  no-op that just creates the empty tempdir.
- **No `apply_overlay`.** The generic adapter has no overlay map.
- **Cross-cutting wiring still runs.** `lefthook.yml`, `agents.yml`,
  `config.yml`, and the CI workflows are written into the workspace
  per the universal v2.1 pipeline. This is the entire value proposition
  of choosing `generic`.
- **Receipt records the dispatch normally.** `scaffold-receipt.json`
  has `layers_materialized` populated with the `generic` entry, but
  with empty `materialized_files` for the layer (since the generic
  adapter never wrote any). The cross-cutting files (lefthook.yml,
  agents.yml, config.yml, etc.) appear in the receipt's separate
  `cross_cutting_files` array.
- **No `adapter_dispatch_meta.fallback_ids`.** That field is reserved
  for v2.2-candidate routing; picking `generic` directly does not
  populate it.

## Telemetry + audit notes

- `matched_category_id = "manual-override"` per HANDSHAKE §4 rule 4
  (the only path to `generic` as a primary stack at v2.1.4 is the
  manual-override branch — there is no category-pattern entry for
  generic in `category-patterns.yml` because there is no idiomatic
  pattern to match against).
- Ledger nonce is consumed normally. `decision_sha256` chains to the
  receipt as usual.
- The `generic` adapter's `assert_adapter_protocol_conformance()` at
  module load time guards against `Adapter` Protocol drift, same as
  every other adapter.
