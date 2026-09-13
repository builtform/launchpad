# Codex Compatibility Documentation PR Handoff

## Status

The local documentation and completed-package phase is complete. The candidate remains qualified for local, unpublished staging only. Codex CLI 0.153.4 does not authenticate bare `$lp` skill selection or bind its argument tail, so no LaunchPad workflow is advertised as supported on Codex.

Do not publish, list, tag, or install this candidate into a maintainer's normal Codex state. Do not install the raw `plugins/launchpad/` source tree. The installable candidate must be produced by the sealed package projector because Codex supplements custom skill paths and migrates root `commands/` content.

## Documentation completion attestation

The first real-document render exposed a temporary implementation-phase lock that still prohibited the repository root. Removing that lock changed the sealed runtime, as required, so the Section 10 entry identity below was invalidated. The corrected renderer was made Prettier-stable, the 166-file runtime was resealed, pinned host receipts were rerun, and release evidence was regenerated before documentation validation resumed.

The raw-byte evidence and independent generated-document validation corrections changed the sealed runtime again. Fresh isolated router and lifecycle receipts were produced with Codex CLI 0.153.4 and Claude Code 2.1.258, the qualification generator consumed those receipts, and the completed-package lifecycle passed with the detached digest below. The host result remains fail-closed.

The PR review metadata correction completed the `lp-plan` dependency graph and declared the browser, MCP, network, mediation, and external-tool requirements used by its design agents. Fresh receipts and attestations were produced because those canonical metadata changes alter the sealed runtime. Public support remains unchanged.

- Final runtime payload digest: `e1233bb51283314d22f2fa5f3167db1b23792de13674a3e27686acf419f791e3`
- Final raw-byte evidence digest: `eec92f1e0f921a982f768e11569cf2037ef9c41f10f178b2754885df8b1dd1ac`
- Final detached artifact digest: `200a3ca3b06e6e036f9e3606d8dd23797114fbafbea13a98b119db1ff74b256c`
- Runtime closure: 166 files
- Completed package closure: 169 files
- Generated package slots: `README.md`, `codex/support-evidence.json`, `docs/guides/HOW_IT_WORKS.md`
- Final package lifecycle: passed for Codex CLI 0.153.4 and Claude Code 2.1.258 in disposable state
- Overall support: blocked
- Supported roots: 0
- Blocked roots: 44
- Advertised capability families: none

The artifact digest is detached from the package and recorded here for branch review in [PR #185](https://github.com/builtform/launchpad/pull/185). No marketplace change, normal Codex installation, tag, or publication was performed.

## Superseded Section 10 entry identity

This identity records the implementation-to-documentation handoff only. Do not use it to verify the completed package.

- Exact implementation commit: `30041ec05d5a61ca9b776d96765c0e0b7a393018`
- Plugin version: `2.1.11`
- Protocol digest: `fdfd8713fc741dc53ce88bd43f90ecd49825d06d11bc1e0bb7a33a8fc1250771`
- Runtime payload digest: `d444890666ad7a587eee92bae68c93fc89ec0ea9315a6c19bf6422c338af9b94`
- Evidence digest: `9d4d8eb967399d6a28e927fb92c2a5e10380256978c01b947bf6bd1856ae82fd`
- Runtime closure: 166 files
- Intermediate candidate closure: 167 files, consisting of the runtime closure plus `codex/support-evidence.json`
- Release stage: `dogfood`
- Beta release acceptance: `blocked`

The documentation PR must reject any runtime payload digest other than the value above. It must not compute or claim a completed-package `artifact_digest` until the generated public documentation slots have been added in that PR.

## Qualification evidence

Qualification ID:

- `qualification-section10-blocked-support`

Bound receipt IDs:

- `section7-safety-coordinator-fixture`
- `section8-harden-plan-fixture`
- `section9-lifecycle-host-blocked`
- `section9-router-host-blocked`
- `section9-whole-corpus-acceptance`

The evidence contains 44 blocked roots and 0 supported roots. Hand editing is rejected by the qualification checker.

## Fixed beta support set

| Required surface     | Fixture result | Real host result | Blocking reason                                                                                        |
| -------------------- | -------------- | ---------------- | ------------------------------------------------------------------------------------------------------ |
| `$lp` and `$lp help` | Pass           | Blocked          | `HOST_NO_AUTHENTICATED_EXPLICIT_INVOCATION_PROVENANCE`, `HOST_NO_LOSSLESS_AUTHENTICATED_ARGUMENT_TAIL` |
| `$lp hydrate`        | Pass           | Blocked          | `WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN`                                                                 |
| `$lp harden-plan`    | Pass           | Blocked          | `WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN`                                                                 |

Every other public command or user-invocable skill is also blocked with `WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN`. The documentation must not describe any Codex workflow as executable, supported, beta-ready, or available through a public command.

## Supported installation surfaces

| Surface                                                      | Status        |
| ------------------------------------------------------------ | ------------- |
| Sealed package projected into a disposable local marketplace | Verified      |
| Isolated `CODEX_HOME` lifecycle testing                      | Verified      |
| Raw `plugins/launchpad/` source tree                         | Unsupported   |
| Normal maintainer Codex installation                         | Not performed |
| Public or unlisted external marketplace entry                | Not created   |
| Tag, visibility change, or release publication               | Not performed |

The sealed package exposes exactly two active Codex discovery surfaces:

- `.codex-plugin/plugin.json`
- `codex/skills/lp/SKILL.md`

Canonical commands, skills, and agents are projected under `codex/canonical/` inside the package. There are no per-command Codex skills or agents.

## Exact tested local procedure

The successful host run used Codex CLI 0.153.4 and Claude Code 2.1.258 with disposable state. The lifecycle harness performs Claude-first and Codex-first checks, local marketplace installation, update repair, disable and enable, concurrent read-only use, stale-session refusal, removal isolation, host-state validation, and cleanup.

```bash
candidate_home="$(mktemp -d /private/tmp/lp-codex-candidate.XXXXXX)"
python plugins/launchpad/scripts/tests/fixtures/codex_compatibility/run_candidate_lifecycle.py \
  --codex-home "${candidate_home}" \
  --codex-bin codex \
  --claude-bin claude \
  > /private/tmp/codex-candidate-lifecycle.json
python plugins/launchpad/scripts/plugin-codex-qualification.py verify-candidate-lifecycle \
  --plugin-root "$(pwd)/plugins/launchpad" \
  --receipt /private/tmp/codex-candidate-lifecycle.json \
  --codex-version 0.153.4 \
  --claude-version 2.1.258
```

The harness internally installs `launchpad@launchpad-section10-candidate` from a disposable local marketplace and removes both the plugin and marketplace before completing. Its only blocked probe is `bare-lp-authenticated-routing`, which is the required fail-closed host result.

## Known limitations and recovery

- Bare `$lp` remains ordinary user text in Codex CLI 0.153.4. The host does not provide authenticated invocation provenance or a lossless authenticated argument tail.
- The host exposes no accepted plugin hook ingress for this router contract.
- The raw repository plugin directory is a projection source, not an installable Codex package. Installing it directly can cause Codex to discover or migrate canonical root content.
- No effectful workflow has a supported mutation owner. `$lp hydrate` and `$lp harden-plan` stop before execution.
- Codex creates its own system-skill and installation markers inside isolated `CODEX_HOME`. Host-state allowlist version 2 permits only the verified Codex-owned paths plus bounded plugin, log, and configuration state.
- Claude validation passes with the existing single warning for legacy `commands/lp-research-codebase.md` frontmatter. This warning is not introduced by the Codex package.

If an isolated update leaves a partial cache, rerunning the exact `codex plugin add` for the same local selector repairs the cache. If validation or a digest check fails, remove the isolated plugin and marketplace, discard the disposable state, regenerate from the frozen implementation commit, and rerun qualification. Never hand edit `support-evidence.json`, reuse a stale session, auto-resume a partial mutation, or alter normal user Codex state as recovery.

## Documentation PR procedure

First verify the frozen evidence:

```bash
python plugins/launchpad/scripts/plugin-codex-qualification.py check \
  --plugin-root "$(pwd)/plugins/launchpad" \
  --evidence "$(pwd)/plugins/launchpad/codex/support-evidence.json"
```

Then render the protocol-owned regions in the real public documents:

```bash
python plugins/launchpad/scripts/plugin-codex-support.py render-docs \
  --write \
  --evidence plugins/launchpad/codex/support-evidence.json \
  --docs-root .
python plugins/launchpad/scripts/plugin-codex-support.py render-docs \
  --check \
  --evidence plugins/launchpad/codex/support-evidence.json \
  --docs-root .
```

The evidence digest is SHA-256 over the exact raw bytes emitted by the deterministic producer. Formatting-only changes to `support-evidence.json` fail qualification. The file is excluded from Prettier so the formatting hook cannot rewrite the attested bytes. Completed-package checks and artifact-digest calculation must receive `plugins/launchpad` and the repository documentation root as authorities independent from the package being checked. The generated README and How It Works digests must be derived from those sources and the protocol renderer.

The documentation PR must preserve Claude instructions, state that all 44 Codex roots are blocked, and run the bounded contradiction audit. After documentation validation, it may add only the protocol-declared generated slots, prove the runtime digest is unchanged, compute the completed-package `artifact_digest`, and run the exact final candidate smoke. Marketplace listing, visibility, tagging, and publication remain prohibited until every later activation gate passes.

## Section 10 validation record

- Focused Codex qualification and closure tests: 210 passed before final source-surface hardening; final acceptance and qualification subset: 70 passed.
- Complete Python suite: 2,343 passed, 4 skipped.
- Pyright: 0 errors, 30 existing warnings.
- Ruff check and format check: passed.
- `pnpm test`, `pnpm typecheck`, and `pnpm lint`: passed.
- Repository structure, workflow SHA pins, and v2 handshake lint: passed. The handshake lint reported existing freshness advisories only.
- Claude plugin validation: passed with the existing single warning noted above.
- Isolated exact candidate lifecycle: all implemented gates passed; bare `$lp` authenticated routing remained blocked as required.
- Public documentation and marketplace authorities were unchanged in the implementation commit.
- The pre-existing imported `.codex/` hook configuration was later reconciled as tracked, portable LaunchPad repository tooling in a separately scoped pre-review commit. It remains outside the sealed plugin package and does not affect the frozen runtime digest.

### Post-review correction validation

- Complete Python suite: 2,392 passed, 5 skipped.
- Workflow-equivalent Codex compatibility subset: 354 passed.
- Pyright: 0 errors, 30 existing warnings.
- Ruff check, Ruff format check, repository structure, workflow SHA pins, exact workflow acceptance, release qualification, and generated-document drift checks: passed.
- Fresh isolated router, lifecycle, and completed-package receipts: passed with Codex CLI 0.153.4 and Claude Code 2.1.258; bare `$lp` support remains blocked as required.

### Greptile metadata correction validation

- Complete Python suite: 2,437 passed, 4 skipped.
- Workflow-equivalent Codex compatibility suite: 398 passed.
- Pyright: 0 errors, 30 existing warnings.
- Ruff check, Ruff format check, repository tests, typecheck, lint, exact workflow acceptance, release qualification, generated-document drift, and completed-package closure: passed.
- Fresh isolated router, coexistence, and completed-package lifecycle receipts: passed with Codex CLI 0.153.4 and Claude Code 2.1.258.
- Support remains fail-closed with 44 blocked roots, 0 supported roots, and no advertised capability families.

This handoff is the Section 10 mandatory stopping point. Do not begin public-document rendering, final artifact assembly, or activation work in the implementation PR.
