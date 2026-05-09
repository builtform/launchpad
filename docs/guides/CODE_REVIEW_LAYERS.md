# Code Review Layers

LaunchPad v2.1.1 ships a three-layer code-review architecture. Each layer closes a different review-failure mode that the others can't reach. This guide explains what each layer does, when it fires, and how to override it when necessary.

## Audience

This guide has two audiences with overlapping needs:

- **Running LaunchPad in your project (downstream users)** — you invoke `/lp-commit`, `/lp-ship`, `/lp-review` against your own diffs. The relevant content for you is which gates fire on your commits, how the dual-pass works, and how to bypass it on hotfixes.
- **Contributing to LaunchPad (maintainers)** — you also care about which Layer 3 tools run against the plugin's own scripts, how `commands.{lint,test,typecheck}` arrays in `.launchpad/config.yml` route through `plugin-build-runner.py`, and how to add new Layer 3 tools without breaking downstream lefthook adopters.

Examples in each layer hit both audiences where relevant.

## Why three layers

Each layer addresses a distinct failure mode:

- **Layer 1 (Mandatory wiring)** — closes the "review was optional and got skipped" gap. Phase 3 sibling violated Hard Rule 6 by skipping `/lp-review`'s parallel `Task` dispatch step. Mandatory wiring at `/lp-commit` Step 2.5 + `/lp-ship` Step 4.6 forces both passes to run on every standard commit + ship.
- **Layer 2 (Two-pass with `--no-context`)** — closes plan-bias. Specialist agents read the PR intent + `.harness/harness.local.md` + per-agent specialty framing; that context primes them to find what the plan asks them to find. The blind pass sees the diff alone and surfaces what the specialists' priors hid.
- **Layer 3 (Static analysis)** — closes structural-invariant gaps. Lint catches style; security scanners catch obvious vulnerabilities; semgrep catches cross-cutting invariants no human reviewer can hold in working memory; types catch wrong-shape data; unit tests catch behavioral regressions.

What v2.1.1 explicitly does NOT close: pattern recognition for novel bug classes (forward reference: BL-297, v2.1.2 Codex/Greptile corpus-trained reviewer). Codex + Greptile remain the production reviewers; the new layers ADD to, not REPLACE, third-party review.

## Layer 1 — Mandatory wiring

`/lp-commit` Step 2.5 and `/lp-ship` Step 4.6 dispatch `/lp-review` automatically on every standard commit + ship. There is no longer a "review? y/n" prompt to skip past.

How both passes fire:

```bash
# Inside /lp-commit Step 2.5 (sketch — actual flow runs both as parallel Bash tool calls):
/lp-review --headless                  # specialist pass (full context)
/lp-review --headless --no-context     # blind pass
```

Each pass dispatches its full agent roster as parallel `Task` invocations. Both passes write findings to `.harness/todos/`. The user triages once via `/lp-triage`.

**Hotfix bypass.** When you genuinely need to skip review (production fire, no time for full dispatch), pass `--skip-review`. The flag is TTY-guarded — it requires you to type `BYPASS REVIEW` interactively to confirm. The bypass appends an audit-trail trailer to the commit message recording who skipped, when, and why. Hotfix branches typed naming convention (`fix/*`, `hotfix/*`) is the expected use case.

Don't use `--skip-review` to "save time" on routine commits. The dual-pass is cheap relative to the bug-class it catches; saving 30s in the inner loop is not worth re-litigating Hard Rule 6.

## Layer 2 — Two-pass mechanism

`/lp-review --no-context` strips three things from the specialist invocation:

1. PR intent / commit message
2. `.harness/harness.local.md` project-specific review context
3. Per-agent specialty framing (the agent file's "you are an expert in X" preamble)

The specialist pass keeps all three. The blind pass keeps none.

**Why two passes are complementary, not redundant.** Specialist passes are biased toward "find what the PR claims to do." If the PR description says "fix the auth race condition," the security auditor will look for race conditions in auth — and might miss the SQL injection two files over. The blind pass has no PR context; it just reads the diff and reports what stands out structurally.

**Why `--no-context` is not Codex replacement.** Codex catches local logic bugs at line-level. Greptile catches cross-file convention drift via codebase indexing. The Layer 2 blind pass catches plan-bias-blindspots in our own agent roster — a different failure mode. All three remain valuable; running all three gives the broadest coverage.

Findings from both passes write to the same `.harness/todos/` queue. `/lp-triage` walks the unified list once.

## Layer 3 — Static analysis

Layer 3 enforces structural invariants no agent can hold in working memory: lint, security scan, semantic patterns, types, unit tests.

The architecture is universal-lefthook + per-stack truth: `lefthook.yml` routes `lint` / `typecheck` / `test` through `plugin-build-runner.py`, which reads `commands.{lint,test,typecheck}` arrays from `.launchpad/config.yml` and runs whatever the project's stack declares. Empty arrays skip silently. This means:

- **Downstream users** — your `.launchpad/config.yml` declares your stack's commands. `pnpm lint` for TypeScript, `cargo clippy` for Rust, etc. The lefthook entries fire only on globs that match your changes.
- **LaunchPad maintainers** — the plugin's own `commands.{lint,test,typecheck}` arrays drive the self-host Layer 3 pass. Plus seven Python-specific gates wire directly to lefthook for the plugin scripts surface (bypass build-runner since they apply to a known fixed Python tree): pre-commit `bandit` + `ruff-check` + `ruff-format-check` + `semgrep-general`; pre-push `pytest` + `pyright` + `semgrep-launchpad-internal`.

**Concrete v2.1.1 self-host tools (subject to swap; current as of v2.1.1):**

- `ruff` — Python lint + format-check
- `bandit` — Python security scanner (low-or-higher severity blocks)
- `semgrep` — semantic patterns (general rules + LaunchPad-internal cross-cutting invariants)
- `pyright` — Python types (strict on 3 security-boundary modules; standard mode elsewhere)
- `pytest` — unit tests

See [`docs/architecture/CI_CD.md`](../architecture/CI_CD.md) §v2.1.1 local gate inventory for the full table of priorities, globs, excludes, and source commands.

**`nodeenv` supply-chain caveat.** Pyright transitively pulls `nodeenv`, which downloads a Node.js binary at install time. That download is OUTSIDE pip's hash protection — `pip-compile --generate-hashes` only hashes the Python distribution. Tracked as BL-299 for v2.1.3 remediation (replace pyright with mypy OR pin node binary checksum). Operators in regulated environments should pin/verify the node binary out-of-band.

## When to override

Sometimes a finding is wrong, or the cost of fixing it exceeds the cost of documenting why it's intentional. The escape hatches:

- `--skip-review` on `/lp-commit` / `/lp-ship` — hotfix-only; TTY confirmation required; audit-trail trailer recorded in commit message.
- `# nosec` (bandit) — comment annotation; pair with a BL/HANDSHAKE/plan cross-reference triple so future readers can validate.
- `# type: ignore[<rule>]` (pyright) — narrow ignore; specify the rule, not bare `# type: ignore`.
- `# noqa: <rule>` (ruff) — narrow ignore; same pattern.
- semgrep `# nosemgrep` per-line OR allowlist in the config — prefer the allowlist for known-safe patterns (BL-306 tracks allowlist-vs-handshake-lint convergence).

**Document the override rationale in the commit message.** Future readers will hit the override and need to know why. "Disabled bandit on this line because <specific reason + cross-reference>" is the minimum useful comment.

## What v2.1.1 explicitly does NOT cover

- **Pattern recognition for novel bug classes.** A reviewer that recognizes "this looks like the bug class we hit in PR #234 that took 3 days to debug" is the v2.1.2 work (BL-297 Codex/Greptile corpus-trained reviewer). v2.1.1's three layers can't pattern-match against past incidents — they enforce documented rules + dispatch our agent roster.
- **Replacement for Codex / Greptile.** Both remain advisory PR reviewers. Layer 1 + Layer 2 add LOCAL pre-push coverage; Layer 3 adds structural-invariant pre-commit / pre-push. None of the three remove the value of Codex's narrow line-level review or Greptile's wide codebase-indexed review.
- **Coverage on doc-only diffs.** Static analysis gates are glob-filtered; doc-only commits skip lint/typecheck/test/bandit/ruff/semgrep entirely. The Layer 1 + 2 dual-pass still fires on doc commits — but the agent roster largely surfaces P3 findings (which is correct: docs aren't code).

The new layers compose with third-party review; they don't replace it.
