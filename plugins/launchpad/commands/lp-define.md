---
name: lp-define
description: Detect the project's stack and scaffold the 4 canonical architecture docs + section registry + .launchpad/config.yml, adapted to what was detected. Honors an interactive overwrite menu and applies secret-scan + manifest-strip guardrails. The biggest lift in the harness pipeline.
---

# /lp-define

The definition phase. Detects your project's stack, scaffolds the canonical
architecture docs adapted to what's actually there, and seeds
`.launchpad/config.yml` so every downstream command has the state it needs.

This command replaces the old thin meta-orchestrator. It now does the work
directly — powered by the plugin's shared infrastructure (stack detector,
stack adapters, Jinja2 generator, secret scanner).

---

## Step 0: Prerequisite & Capability Check

Before generating anything, confirm what we're looking at and what's already
on disk.

### 0.1 — Detect the stack (single confirmation up front)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-stack-detector.py`. Summarize the result for the user
in ONE message (not seven per-doc prompts — prompt fatigue is a real failure
mode):

> "Detected stack: **TypeScript monorepo** (Next.js 15, Hono, Prisma, Turborepo)
> plus **Python** (Django).
>
> I'll scaffold 4 architecture docs, a section registry, and `.launchpad/config.yml`
> adapted to this stack. Overwrite behavior for any existing files: interactive
> per-file prompt with diff preview. Proceed? [Y/n]"

If the user declines, exit cleanly.

If the detector returned `zero_manifest: true`:

> "I didn't find any recognized manifests. I can scaffold a generic skeleton
> you fill in manually, or you can name your stack and I'll use closer
> defaults. What would you like?"

### 0.2 — Check for pre-existing canonical files

The generator handles the overwrite policy itself. Do NOT inline the skip/prompt
logic here — that's exactly the kind of drift the shared-helper rule
forbids.

---

## Step 1: Run the generator

Invoke `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-doc-generator.py`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin-doc-generator.py \
  --repo-root=$PWD \
  --product-name="<user-provided name, or existing PRD H1 if re-running>"
```

The generator does:

1. **Detect** — runs the stack detector (manifest allowlist, 1MB cap, bounded walk)
2. **Compose** — single-stack adapter OR polyglot composer (multi-language path)
3. **Render** — 4 canonical docs + section registry + config.yml through Jinja2
   with `select_autoescape(enabled_extensions=('html','htm','xml'), default=False)`
   so HTML / XML templates autoescape (no template here today, door open for
   v1.1) but Markdown and YAML render variable content verbatim. Variable
   values are strings, never re-parsed as Jinja syntax — the SSTI guard
   was always Jinja's template model, not HTML autoescape, which on
   Markdown only corrupted benign text like `R&D <Pilot>`. YAML safety
   relies on `tojson` / explicit yaml-safe quoting in template bodies.
   `StrictUndefined` is preserved so missing variables fail loudly
4. **Scan** — every rendered doc passed through `.launchpad/secret-patterns.txt`
   (with conservative built-in fallback); any match blocks the write. The
   doc generator does not interpolate parsed manifest CONTENT into template
   output (it renders manifest paths only), so there is no per-field strip
   step here today; a `manifest_stripper` helper exists for the case where
   a future template needs to embed a manifest value, at which point it
   would be wired at that interpolation boundary
5. **Apply overwrite menu** per existing file:
   `[k]eep / [o]verwrite / [d]iff preview / [a]ll-overwrite / [s]kip-all`
   - `.launchpad/config.yml` and `.launchpad/agents.yml` are **never**
     included in `[a]ll-overwrite` — always individual prompt with mandatory
     diff (user-tuned state is too costly to lose)
6. **Write** — writes the new files to disk at their canonical paths

The generator is non-interactive-safe: if stdin isn't a TTY and `--force`
isn't passed, it defaults every existing-file prompt to `keep`. This makes
re-runs in CI safe by default.

## Step 2: Verify + Transition

Check the generator's JSON summary (`written` / `kept` / `skipped` lists).
If everything looks right:

> "Scaffolded the canonical docs adapted to your stack. Review
> `docs/architecture/` and fill in the placeholder sections.
>
> When ready, run `/lp-shape-section <name>` to add the first implementation
> section, then `/lp-plan <name>` to start planning."

If the generator reported secret-scan findings:

> "I found something that looks like a secret in the rendered output. I've
> refused to write. Review the flagged lines, redact the values, and re-run.
> If it's a false positive, add a narrower exception to
> `.launchpad/secret-patterns.txt`."

---

## Step 3: Render the Tier 1 governance reveal panel

Per OPERATIONS §5, after the generator's JSON summary, render the Tier 1
reveal panel so the user sees concrete proof of what governance gates were
installed. The panel variant depends on the cwd state captured by Step 0.1
(greenfield vs. brownfield).

### Greenfield variant

If `cwd_state == "empty"` AND `.launchpad/scaffold-receipt.json` exists,
read the receipt's `tier1_governance_summary` block and render:

```
✓ Tier 1 governance kernel installed:

  • REPOSITORY_STRUCTURE.md whitelists <whitelisted_paths> paths; CI rejects anything else
    → blocks structure-drift PRs before reviewer time is wasted
  • lefthook pre-commit hooks gate: <lefthook_hooks joined with ", ">
    → catches `.env.local` leaks and broken types before push
  • .launchpad/config.yml drives <slash_commands_wired> slash commands across
    your project lifecycle
    → consistent /lp-build, /lp-define, /lp-commit semantics across sessions
  • .harness/ captures run logs, observations, todos for compound
    learning
    → past mistakes inform future review agents automatically
  • docs/architecture/ — <architecture_docs_rendered> living architecture docs, kept current
    by /lp-define re-runs
    → architecture stays in sync with code; no doc rot

Telemetry: local-only (.harness/observations/v2-pipeline-*.jsonl).
Opt out via .launchpad/config.yml: telemetry: off.
CI users: set CI=true + LP_CONFIG_AUTO_REVIEW=1 (with positive CI
filesystem signal) to skip config-review prompts on first invocation.

Run /help to see what slash commands are now available, or
/lp-build when you're ready to ship a feature.
```

Compute the bracketed values:

- `<lefthook_hooks>` and `<architecture_docs_rendered>` come from the
  receipt's `tier1_governance_summary` (these are known at scaffold-stack
  time and sealed into the receipt's sha256).
- `<whitelisted_paths>` is **computed live** at panel-render time by
  reading the just-rendered `docs/architecture/REPOSITORY_STRUCTURE.md` and
  counting entries under its `whitelist:` (or equivalent) section. The
  receipt carries `null` for this field by design — `/lp-scaffold-stack`
  doesn't render REPOSITORY_STRUCTURE.md, `/lp-define` does (PR #41 cycle
  8 #1 closure).
- `<slash_commands_wired>` is **computed live** by counting the number of
  slash commands referenced in `.launchpad/config.yml` (sum of unique
  command names across all `commands.*` arrays). The receipt also carries
  `null` for this field.

If the receipt's `whitelisted_paths` or `slash_commands_wired` is `null`
(expected for v2.0 receipts), fall back to live filesystem counts. If the
receipt is missing OR malformed, fall back to the brownfield variant
rather than inventing numbers.

### Brownfield variant

If `cwd_state != "empty"` OR no scaffold-receipt is available, render with
filesystem-only counts (no chain-of-custody, no receipt SHA cross-check):

```
✓ Tier 1 governance verified — all gates green:

  • REPOSITORY_STRUCTURE.md — <N> paths whitelisted (<M> new this run)
    → structure-drift detector blocks misplaced files before merge
  • lefthook pre-commit hooks — installed/verified: secret-scan,
    structure-drift, typecheck, lint
    → catches secrets and broken types at commit time, not in CI
  • .launchpad/config.yml — <N> slash commands wired
    → consistent automation semantics across sessions
  • .harness/ — <N> observations, <M> todos (last run: <timestamp>)
    → continuity across sessions; review agents read past learnings
  • docs/architecture/ — 4 architecture docs refreshed against
    your current code
    → re-renders pick up changes since last /lp-define run

Telemetry: local-only (.harness/observations/v2-pipeline-*.jsonl).
Opt out via .launchpad/config.yml: telemetry: off.

Run /help to see your slash commands, or /lp-build when you're
ready to ship a feature.
```

### Telemetry-disabled modifier

If `.launchpad/config.yml` has `telemetry: off`, replace the two telemetry
lines (Telemetry / Opt-out) in either variant with the single line:

```
Telemetry: disabled (.launchpad/config.yml: telemetry: off).
```

---

## Acceptance behavior

- **Greenfield (empty repo)**: LaunchPad defaults; 4-doc scaffold + config.yml.
- **Brownfield TS monorepo** (e.g. BuiltForm): detects actual stack; docs reflect reality.
- **Brownfield Django**: detects Python; `pipeline.design = skipped`; APP_FLOW.md
  explicitly notes backend-only shape.
- **Polyglot (TS + Python)**: `commands.test` is `["pnpm test", "pytest"]`;
  TECH_STACK mentions both languages.
- **Re-run on configured repo**: `keep` is the default; no user-authored
  content is silently clobbered.
- **Zero-manifest**: falls through to the `generic` adapter; prompts user
  for language/framework rather than guessing.
- **`--force` mode**: still can't overwrite `.launchpad/config.yml` or
  `.launchpad/agents.yml` without an individual confirm.

---

## Subcommands (legacy — kept for users who want fine control)

- `/lp-define-product` — refine just the PRD (if you want to iterate on it
  separately from the generator's scaffold)
- `/lp-define-design` — refine the design system (v1.1 scope)
- `/lp-define-architecture` — refine BACKEND_STRUCTURE
- `/lp-shape-section` — append a section spec to `docs/tasks/SECTION_REGISTRY.md`

These still exist as commands; `/lp-define` no longer orchestrates them by
default. Invoke them directly when you want targeted refinement after the
initial scaffold.
