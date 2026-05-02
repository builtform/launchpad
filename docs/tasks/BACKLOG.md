# BACKLOG

> Central backlog for deferred and active work. Populated by developers and AI agents as the project evolves.

---

## How to Use This File

### Adding a new task

Copy the Standard Task Format below into the correct priority section. Required fields:
`Task ID`, `Priority`, `Status`, `Area`, `Date`, `Location`, `Current Behavior`, `Desired Behavior`.

Task IDs are sequential integers zero-padded to three digits: `BL-001`, `BL-002`, etc.

### Marking a task complete

Remove the task entry from this file and append a one-line summary to `docs/tasks/PROGRESS.md`:

```
COMPLETED BL-XXX - Short title (YYYY-MM-DD)
```

### Priority levels

| Level | Label    | Meaning                                      |
| ----- | -------- | -------------------------------------------- |
| P0    | Critical | Blocks MVP or fixes a live defect — do first |
| P1    | High     | Important for the near-term roadmap          |
| P2    | Medium   | Good to have in the next phase               |
| P3    | Low      | Cleanup, refactor, polish                    |

### Status values

| Value       | Meaning                               |
| ----------- | ------------------------------------- |
| TODO        | Not started                           |
| NEXT        | Candidate for the upcoming sprint     |
| IN_PROGRESS | Currently being worked on             |
| BLOCKED     | Waiting on another task or dependency |

### Referencing related work

Use `Blocked By` for task dependencies. Link PRs, issues, and related files in the `Notes` field.

---

## AI Agent Instructions

At session start, summarize all P0 tasks then all P1 tasks. For each show: Task ID, title, Area, Status. Then ask the user which task (if any) to focus on.

During a session, when a new task emerges that is separate from current work: recognize it, ask the user whether to capture it, add a minimal entry using the format below, then return to the current task.

When implementing a task: always revalidate whether the proposed fix still makes sense before applying it. The codebase may have changed since the task was written.

---

## Legend

**Area** (customize for your project — these are common starting points):

- `Frontend` - Web app (Next.js)
- `Backend` - API service
- `DB` - Database schema, migrations
- `Auth` - Authentication, authorization
- `Infra` - Deployment, CI/CD, infrastructure
- `Testing` - Test infrastructure, QA
- `Docs` - Documentation

---

## Standard Task Format

```markdown
#### BL-XXX - Short, descriptive title

- **Priority**: P0 | P1 | P2 | P3
- **Status**: TODO | NEXT | IN_PROGRESS | BLOCKED
- **Area**: Frontend | Backend | DB | Auth | Infra | Testing | Docs
- **Blocked By**: BL-YYY (only if Status is BLOCKED)

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: file path, module, route, or command where the issue was found
- **Scenario**: Brief description of what was being done when this was discovered

**Current Behavior**

Short description of what is happening right now.

**Desired Behavior**

Short description of what is wanted instead.

**Proposed Fix** (revalidate before implementing)

Outline the fix that seemed correct when this task was created.
Future implementers must verify this is still the best approach.

**Notes**

Extra context, links to PRs, issues, logs, or external docs.
```

---

## Backlog

### P0 - Critical

<!-- EXAMPLE (delete when adding real tasks):
#### BL-001 - Example: Fix authentication middleware crash on expired tokens

- **Priority**: P0
- **Status**: TODO
- **Area**: Auth

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `apps/api/src/middleware/auth.ts`
- **Scenario**: During manual QA, a request with an expired JWT caused a 500 instead of a 401.

**Current Behavior**

Expired JWT throws an unhandled exception and returns HTTP 500.

**Desired Behavior**

Expired JWT is caught, returns HTTP 401 with a clear error message.

**Proposed Fix** (revalidate before implementing)

Wrap the `jwt.verify()` call in a try/catch and return a 401 response on `TokenExpiredError`.

**Notes**

Related issue: #12.
-->

---

### P1 - High

<!-- EXAMPLE (delete when adding real tasks):
#### BL-002 - Example: Add database index on users.email for login performance

- **Priority**: P1
- **Status**: TODO
- **Area**: DB

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `packages/db/prisma/schema.prisma`, `User` model
- **Scenario**: Load testing showed login queries taking 200ms+ on a table with 10k rows.

**Current Behavior**

No index on `users.email`; every login triggers a full table scan.

**Desired Behavior**

Login queries run in under 10ms with a unique index on `users.email`.

**Proposed Fix** (revalidate before implementing)

Add `@@index([email])` (or `@unique`) to the `User` model in `packages/db/prisma/schema.prisma` and generate a migration.

**Notes**

Follow the migration protocol in `docs/operations/PRISMA_MIGRATION_GUIDE.md`.
-->

---

### P2 - Medium

#### BL-100 - v2.2: Restore `cloudflare-workers` to scaffolders.yml + add cf-edge-stack category-pattern

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / scaffolders

**Encountered**

- **Date**: 2026-04-30
- **Location**: `plugins/launchpad/scaffolders.yml`, `plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml`, `plugins/launchpad/scripts/plugin_stack_adapters/` (Layer 5 pattern P3-L5-B + P3-L5-C corrections)
- **Scenario**: v2.0 deferred 5 stacks during the joint cross-plan hardening review (cf-workers, tauri, nestjs, laravel, vite); Layer 3 catalog cut deferred 5 more (sveltekit, elysia, phoenix-liveview, convex, flutter) — total 10 deferrals tracked at BL-212. CF Workers is the highest-priority v2.2 candidate given 2026 edge-native framing. Layer 7 strip-back made v2.1 documentation-only, so stack-catalog restorations land at v2.2 alongside the operational/security infrastructure deferrals.

**Current Behavior**

`scaffolders.yml` ships 10 stacks (Layer 3 catalog cut applied — was 15 in pre-Layer-3 spec); cloudflare-workers is documented as a v2.2 deferred-stacks candidate in [`ROADMAP.md`](../../ROADMAP.md#v22). Users requesting edge-native scaffolds get manual-override only.

**Desired Behavior**

Add `cloudflare-workers` entry to `scaffolders.yml` (orchestrate, pure-headless via `npm create cloudflare@latest`), `cf-edge-stack` category-pattern referencing it (CF Workers backend + Astro frontend, monorepo), and the corresponding `/lp-define` adapter.

**Proposed Fix**

~3-4h. One adapter (~1.5-2h via Wrangler config detection) + one catalog entry (~30 min) + one category-pattern (~30 min) + adapter test fixture (~30 min). Cross-plan integrity (handshake §15) requires the same v2.0 ship sequence: catalog entry, then category-pattern that references it, then adapter.

**Notes**

See [`ROADMAP.md`](../../ROADMAP.md#v22) for the full deferred-stacks list. Telemetry from `/lp-memory-report --v2-pipeline` after v2.0 ship may surface additional demand signal.

#### BL-101 - v2.2: Restore `tauri` to scaffolders.yml + add desktop-tauri category-pattern

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / scaffolders

**Encountered**

- **Date**: 2026-04-30
- **Location**: same as BL-100
- **Scenario**: Tauri is the dominant Electron alternative in 2026; deferred from v2.0 alongside cloudflare-workers/nestjs/laravel/vite.

**Desired Behavior**

Add `tauri` entry (orchestrate, pure-headless via `npm create tauri-app`), `desktop-tauri` category-pattern, and the desktop-pillar `/lp-define` adapter.

**Proposed Fix**

~3-4h. Same pattern as BL-100.

#### BL-102 - v2.2: Restore `nestjs` to scaffolders.yml + add enterprise-saas-ts category-pattern

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / scaffolders

**Encountered**

- **Date**: 2026-04-30
- **Location**: same as BL-100
- **Scenario**: NestJS is a top-3 enterprise-TS backend; v2.0's TS-backend coverage is currently Hono + Elysia (lighter, less enterprise-positioned).

**Desired Behavior**

Add `nestjs` entry (orchestrate, pure-headless), `enterprise-saas-ts` category-pattern (NestJS + Next or Angular), and the corresponding `/lp-define` adapter.

**Proposed Fix**

~3-4h.

#### BL-103 - v2.2: Restore `laravel` to scaffolders.yml + add saas-laravel category-pattern

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / scaffolders

**Encountered**

- **Date**: 2026-04-30
- **Location**: same as BL-100
- **Scenario**: Laravel is the dominant PHP framework; v2.0 has no PHP coverage. Adding it opens the entire PHP user segment.

**Desired Behavior**

Add `laravel` entry (orchestrate, mixed-prompts), `saas-laravel` category-pattern, and the corresponding `/lp-define` adapter.

**Proposed Fix**

~4-5h (mixed-prompts handling is more involved than pure-headless).

#### BL-104 - v2.2: Restore `vite` to scaffolders.yml as generic SPA scaffolder

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / scaffolders

**Encountered**

- **Date**: 2026-04-30
- **Location**: same as BL-100
- **Scenario**: Meta-entrant for non-LaunchPad-catalogued frameworks. Lower priority than BL-100 through BL-103.

**Desired Behavior**

Add `vite` entry (orchestrate, pure-headless) as a generic SPA scaffold path. May not need its own category-pattern; users could reach it via manual-override only.

**Proposed Fix**

~2h. Lower complexity since Vite scaffolding is well-documented and pure-headless.

#### BL-105 - v2.0+6mo: Freshness review of v2.0 catalog

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / scaffolders

**Encountered**

- **Date**: 2026-04-30 (scheduled for 6 months post-v2.0 ship)
- **Location**: All `last_validated:` frontmatter across `plugins/launchpad/scaffolders.yml`, `plugins/launchpad/scaffolders/*.md`, `plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml`, `plugins/launchpad/scripts/lp_pick_stack/data/pillar-framework.md`, `docs/architecture/SCAFFOLD_HANDSHAKE.md`, `docs/architecture/SCAFFOLD_OPERATIONS.md`

**Scenario**

Per OPERATIONS §4 freshness policy, scheduled 6-month review post-v2.0 ship. Re-runs Phase 7.5-style walkthrough; major drift findings drive v2.1 priorities.

**Desired Behavior**

Walkthrough produces drift verdicts for every entry; major-drift entries get refresh PRs.

**Proposed Fix**

~4-8h walkthrough + per-finding refresh PRs as needed.

---

#### BL-200 - v2.0+30d: Telemetry check-in (qualitative review)

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / v2.0 telemetry

**Encountered**

- **Date**: 30 days post-v2.0.0 ship (Layer 2 deploy F-09)
- **Location**: `.harness/observations/v2-pipeline-*.jsonl` from local dev runs + any volunteered downstream cwds

**Scenario**

Local-only telemetry's 4 health signals (acceptance ≥60%, completion ≥80%, time-to-first-200 <90s, post-scaffold engagement ≥50%) are aspirational targets. At single-maintainer scale during the first 30 days post-ship, real-pipeline-runs may be 0-3 — too small for numeric thresholds. This check-in applies the qualitative interpretation rule (OPERATIONS §5: when N<10 distinct runs, signals are qualitative).

**Desired Behavior**

Run `/lp-memory-report --v2-pipeline --since 2026-04-30` (replace date with actual ship date). Capture findings in `.harness/observations/v2-postship-day-30.md` answering:

- Did the pipeline complete without intervention on each run?
- Did anything surprise me (manual edits to `scaffold-decision.json`, unexpected `/lp-define` output, dev server slow)?
- Was the recommendation acceptable for the project shape?

**Proposed Fix**

~30 min check-in. If qualitative review surfaces specific issues, open targeted GitHub issues; do NOT trigger v2.0.x patches solely on numeric threshold misses when N<10.

---

#### BL-201 - v2.0+60d: Telemetry check-in (qualitative + diff)

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / v2.0 telemetry

**Encountered**

- **Date**: 60 days post-v2.0.0 ship (Layer 2 deploy F-09)
- **Location**: same as BL-200

**Scenario**

Same as BL-200, with `--diff-from .harness/observations/v2-postship-day-30.md` to surface trend (improving vs declining) instead of absolute totals.

**Desired Behavior**

Run `/lp-memory-report --v2-pipeline --since <ship-date> --diff-from .harness/observations/v2-postship-day-30.md`. Capture findings in `.harness/observations/v2-postship-day-60.md`. If N has crossed 10 by day 60, numeric thresholds become applicable.

**Proposed Fix**

~30 min check-in.

---

#### BL-202 - v2.0+90d: Telemetry check-in + v2.1 priority signal

- **Priority**: P2
- **Status**: TODO
- **Area**: Plugin / v2.0 telemetry

**Encountered**

- **Date**: 90 days post-v2.0.0 ship (Layer 2 deploy F-09)
- **Location**: same as BL-200

**Scenario**

Final v2.0-driven check-in. Findings drive v2.1 priorities per the OPERATIONS §5 contract ("if missed, drive v2.1's priorities"). If 4 health signals are consistently below thresholds AND N≥10, prioritize v2.1 fixes. If acceptance rate <60% with N≥10, consider revisiting category-patterns.yml ambiguity clusters.

**Desired Behavior**

Run `/lp-memory-report --v2-pipeline --since <ship-date> --diff-from .harness/observations/v2-postship-day-60.md`. Capture findings in `.harness/observations/v2-postship-day-90.md`. Open v2.1 backlog entries for each surfaced gap.

**Proposed Fix**

~1h check-in + v2.1 backlog drafting.

---

<!-- EXAMPLE (delete when adding real tasks):
#### BL-003 - Example: Add pagination to the /api/items list endpoint

- **Priority**: P2
- **Status**: TODO
- **Area**: Backend

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `apps/api/src/routes/items.ts`
- **Scenario**: As the items table grows the endpoint response time increases noticeably.

**Current Behavior**

`GET /api/items` returns all rows with no limit.

**Desired Behavior**

Endpoint accepts `page` and `pageSize` query params; defaults to page 1, size 20.

**Proposed Fix** (revalidate before implementing)

Add Prisma `skip`/`take` and return a `{ data, total, page, pageSize }` envelope.

**Notes**

Frontend will need a corresponding update to consume the paginated response.
-->

---

### P3 - Low

<!-- EXAMPLE (delete when adding real tasks):
#### BL-004 - Example: Standardize error response shape across all API routes

- **Priority**: P3
- **Status**: TODO
- **Area**: Backend

**Encountered**

- **Date**: YYYY-MM-DD
- **Location**: `apps/api/src/` — multiple route files
- **Scenario**: Code review revealed inconsistent error shapes: some return `{ error }`, others return `{ message }`.

**Current Behavior**

Error responses have inconsistent field names across routes.

**Desired Behavior**

All error responses use `{ error: { code, message } }`.

**Proposed Fix** (revalidate before implementing)

Create a shared `errorResponse()` helper in `packages/shared/src/utils/` and replace inline error objects.

**Notes**

Low risk; pure refactor with no functional change.
-->

<!-- Layer 3 + Layer 4 absorption (Paths γ + δ, 2026-04-30) — v2.1 deferred items below -->

#### BL-210 - Remove `_legacy_yaml_canonical_hash` at v2.1.0

**Driver**: Layer 3 data-migration P1-A re-hardening review. The legacy YAML-canonicalization hash function is kept under `DeprecationWarning(stacklevel=2)` for the v2.0.x line to support `LP_CONFIG_REVIEWED` migration UX (HANDSHAKE §3) AND the OPERATIONS §7 rollback path. Removed in v2.1.0.

**Concrete steps at v2.1.0 ship**:

1. Delete `_legacy_yaml_canonical_hash` function from `plugins/launchpad/scripts/plugin-config-hash.py`
2. Delete the soft-warn migration code path from `plugin-config-hash.py` (HANDSHAKE §3 5-branch truth table)
3. Remove `LP_CONFIG_AUTO_REVIEW=1` opt-out (no longer needed once legacy gone)
4. Update HANDSHAKE §3 — strike "kept for one minor cycle" language
5. Update OPERATIONS §7.1 step 4 — remove the `unset LP_CONFIG_REVIEWED && claude /plugin install launchpad@v1.1.0` rollback hint (no longer applicable post-v2.1)
6. CI gate already exists in `plugin-v2-handshake-lint.py --check-_legacy_yaml_canonical_hash-removal` mode; will start passing once removal lands.

**Verification**: `git grep -F '_legacy_yaml_canonical_hash' plugins/launchpad/scripts/` returns empty.

---

#### BL-211 - Forward-compatibility matrix at v2.2.0 (consumer-superset + producer-floor + per-version validation-pipeline-identity)

**Driver**: Layer 3 simplicity P1-D + scope P2-3 + adversarial P1-RT-7 + security-lens P1-S5 + pattern-finder P1-B. **Layer 7 retarget v2.1→v2.2**: v2.1 reframed as documentation-only per Layer 7 strip-back; the schema-bridge policy makes sense alongside other v2.2 manifest-coupled changes. v2.0 ships strict-equality (`EXPECTED_DECISION_VERSION = frozenset({"1.0"})` and `ACCEPTED_RECEIPT_VERSIONS = frozenset({"1.0"})`); the full forward-compat matrix is deferred until v2.2 introduces an actual cross-version need.

**At v2.2 design time**, introduce in HANDSHAKE §10:

1. **Consumer-superset rule**: v2.1 consumer accepts `frozenset({"1.0", "1.1"})` for both decision and receipt
2. **Producer-floor rule** (pattern-finder P1-B): writer at version N MUST NOT write a payload that consumers at version N-1 cannot read OR fail-close on. CI assertion verifies writer-constants and accepted-set are in lockstep on the same commit
3. **Per-version validation-pipeline-identity invariant** (security-lens P1-S5): all accepted versions in `EXPECTED_DECISION_VERSION` MUST share the same validation logic (same field set, same enums, same security checks). Any version that relaxes any check is a major bump (`2.0`), not minor
4. **Receipt-version-≥-decision-version constraint** (architecture P3-5): receipt cannot be older-versioned than the decision it acknowledges
5. **Matrix table** with columns for v2.0.0 / v2.0.x patch / v2.1.0 / v2.1.x patch / v2.2.0; rows for decision file version, scaffold-stack consumer constants, receipt file version, define consumer constants, scaffolders.yml schema_version
6. **CI lint**: `plugin-v2-handshake-lint.py --check-forward-compat` cross-checks all of the above

**Effort estimate**: ~2-3h spec + ~2-3h CI lint extension + ~1-2h tests. Total ~5-8h at v2.1 design time.

---

#### BL-212 - v2.1 stack catalog expansion (10 deferred stacks)

**Driver**: Layer 3 feasibility P1-1 + scope cluster 7. v2.0 ships with 10-entry catalog (handshake §11); v2.1 reintroduces the deferred stacks based on post-v2.0 telemetry signals.

**10 deferred stacks** documented in [`ROADMAP.md` v2.2 section](../../ROADMAP.md#v22):

**Original 5 deferred (pre-Layer-3)**:

1. `tauri` — desktop framework
2. `cloudflare-workers` — edge runtime
3. `nestjs` — backend framework
4. `laravel` — backend framework (PHP)
5. `vite` — build tool

**Layer 3 cut (added to deferred at v2.0)**: 6. `sveltekit` — frontend app variant 7. `elysia` — backend Edge-native TS 8. `phoenix-liveview` — backend realtime (Elixir) 9. `convex` — backend managed (auth-gated) 10. `flutter` — frontend mobile (Dart)

**Effort estimate per stack**: ~5-7h (adapter + scaffolder entry + category-pattern + walkthrough). v2.1 reintroduces 3-5 of these based on telemetry signals (`matched_category_id` requests pointing at deferred stacks, manual override patterns); not all 10 in one v2.1 release.

---

#### BL-213 - Tier freshness windows at v2.1 (if drift surfaces)

**Driver**: Layer 3 simplicity P1-B + scope P2-1. v2.0 ships with single 30-day freshness window for all plugin-shipped catalog/pattern docs + contract docs. Layer 2's tier hierarchy (90d catalog / 30d contract / 14d release notes) is deferred to v2.1 ONLY IF drift problems surface during v2.0.x patches.

**Decision criterion at v2.1 design**: review `.harness/observations/freshness-*.md` reports across v2.0.0 → v2.1.0 lifecycle; if ≥3 reports show "drift-major" verdicts on docs that the 30d window should have caught earlier, introduce tier hierarchy. If 0 such reports, keep the single window (simpler is better).

**At v2.1 design time** (if implemented):

1. Update `plugin-freshness-check.py` to read tier classification from a `tiers:` field in `.launchpad/freshness-config.yml`
2. Update OPERATIONS §4 freshness section
3. Update test fixtures + KAT for tier-aware behavior
4. **Effort estimate**: ~30 min spec + ~1-2h script + ~30 min tests = ~2-3h

**Default decision**: do NOT implement unless evidence demands it. The single window is sufficient for solo-maintainer scale.

---

#### BL-214 - GPG-signed tag infrastructure at v2.1 (if external-contributor threat materializes)

**Driver**: Layer 4 simplicity P3 + scope P2-1 + deployment N1 + security-lens P2-S3 + feasibility P2-4 (multi-lens consensus). v2.0 ships without GPG signing; tag protection rule alone suffices for single-maintainer + low-fork-PR threat model. Reintroduce only if external-contributor / fork-PR volume creates a real tag-impersonation threat.

**At v2.1 design time** (if implemented):

1. Generate maintainer GPG keypair (offline-backed-up master key + revocation cert)
2. Publish fingerprint via `docs/architecture/SIGNING.md` AT LEAST 14 days before any GPG-required tag (bootstrap requirement — downstream verifiers need a stable trust anchor that predates the artifact)
3. Multi-channel publication: GitHub maintainer profile, keys.openpgp.org, signed announcement post in `docs/releases/`
4. Add `git tag -s` mandate to Phase 7.5; add `git verify-tag` (8th check) to verify-v2-ship CI job
5. Add `docs/maintainer/gpg-signing-key.md` runbook covering: rotation cadence (subkey rotation every 1-2 years), key-loss recovery (revocation cert + re-key + signed-tag-history table in SIGNING.md), machine-migration procedure, mid-release expiration recovery

**Decision criterion**: enable when LaunchPad has ≥3 external contributors merging tag-relevant changes, OR when a tag-impersonation incident occurs.

---

#### BL-215 - `restamp-history.jsonl` audit-log hardening at v2.2

**Driver**: Layer 4 schema-drift P1-2 + frontend-races P2 + adversarial P2-RT4-H + security-lens P2 + data-migration P2 (multi-lens consensus). **Layer 5 adversarial P1-A3 + security-lens P3-S2 + data-migration P3-DM5-3 PROMOTED v2.0 baseline** (injection defense, file-mode 0o600, separate `.restamp-audit.lock`, schema_version 1.0 field, pid+pid_start_time forensic identity) into v2.0 ship — see OPERATIONS §4 audit-log subsection. BL-215 now covers ONLY the chain-hashing tamper-evidence + retention policy at v2.2 (retargeted from v2.1 per Layer 7 strip-back: v2.1 is documentation-only).

**v2.0 baseline (NOW shipped, per Layer 5 absorption)**:

- `forensic_writer.write_restamp_audit()` (NOT shell `echo >>`) — eliminates `\n`/`\r\n` injection from commit subjects
- Lefthook commit-msg hook rejects subjects containing `\n` or `\r` BEFORE JSON encoding
- Separate `.restamp-audit.lock` (NOT shared with telemetry lock) — closes DoS coupling
- File mode `0o600` via explicit `os.fchmod()`
- `schema_version: "1.0"` field at v2.0 (registered in HANDSHAKE §10 bump list per Layer 5 P2-SD5-1 — closes v2.0→v2.1 forward-compat trap)
- `pid` + `pid_start_time` minimal forensic identity fields

**At v2.2 design time** (BL-215 remaining work):

1. Add `prev_entry_sha256` chain field to enable tamper-evidence (SHA-256 of prior canonical line)
2. Document retention policy (default 365 days; longer than telemetry's 30d because re-stamp events are rare and forensically valuable)
3. v2.2 readers: verify-chain consumer
4. Depends on BL-223 (forensic_writer.py SRP split) shipping first.

**Default decision**: v2.0 ships baseline injection-defense + integrity-bound writes; v2.2 adds tamper-evidence chain. v2.1 is documentation-only — no audit-log changes ship there.

---

#### BL-216 - `fsync_durable()` shared helper universalization at v2.1

**Driver**: Layer 4 pattern-finder F-3 + performance + testing. v2.0 applies F_FULLFSYNC on macOS only to nonce-ledger writes. Telemetry, receipt, recovery JSON, freshness report, first-run-marker all do plain `os.fsync` without F_FULLFSYNC. Inconsistent macOS durability.

**At v2.1 design time**:

1. Add `fsync_durable(fd)` shared helper to `safe_run.py` (or new `durability.py` module) that wraps `os.fsync(fd)` + conditional `F_FULLFSYNC` on `sys.platform == 'darwin'`
2. Apply consistently in: HANDSHAKE §4 rule 10 (nonce ledger — already has it), §5 receipt write spec, OPERATIONS §5 telemetry pruning, §6 gate #11 recovery JSON write, §4 rule 10 first-run-marker write
3. Effort estimate: ~30 min helper + ~1-2h applying across sites + ~1h tests = ~2-3h

**Default decision**: ship narrow F_FULLFSYNC at v2.0 (nonce ledger is the most security-critical durability path); broaden at v2.1.

---

#### BL-217 - Tier 1 reveal panel `n_docs` constant single-source at v2.1

**Driver**: Layer 4 architecture P3-6. The literal `8` for "architecture docs rendered" appears in HANDSHAKE §5 receipt schema + OPERATIONS §5 greenfield panel + brownfield panel. No shared constant.

**At v2.1 design time**:

1. Define `TIER1_ARCHITECTURE_DOCS = ("PRD.md", "TECH_STACK.md", ...)` constant in shared module
2. Receipt's `architecture_docs_rendered` computed as `len(TIER1_ARCHITECTURE_DOCS)`
3. Panel templates substitute `{n_docs}` rather than hard-coding `8`
4. CI lint: assert `git grep -nE '"?architecture_docs_rendered"?:?\s*[0-9]'` returns ≤1 hit
5. Effort estimate: ~30 min total

**Default decision**: ship hardcoded `8` at v2.0 (3 sites all consistent post-Layer 4 sweep); single-source at v2.1 when Tier 1 evolves.

#### BL-106 - v2.2: Native sub-app workflow (`/lp-add-subapp`) for brownfield monorepos

**Driver**: HANDSHAKE §8 references this BL number for the brownfield sub-app escape hatch. v2.0 documents only the workaround (`cd` to fresh subdir, scaffold, manually copy in). A user wanting to add a new sub-app inside an existing brownfield monorepo has no in-pipeline path in v2.0. Layer 7 strip-back made v2.1 documentation-only; introducing a new command is code work and lands at v2.2 alongside the operational/security infrastructure deferrals and the deferred-stacks restorations (BL-100 through BL-104).

**At v2.2 design time**:

1. New command `/lp-add-subapp <path>` with explicit user attestation ("yes I understand this writes into existing brownfield context")
2. Skips `cwd_state` brownfield check at the named subpath if subpath is empty
3. Validates subpath against §6 path validator; rejects if subpath traverses upward or escapes cwd
4. Re-uses pick-stack + scaffold-stack pipeline scoped to the subpath
5. Re-uses `/lp-define` to update parent monorepo manifests (`pnpm-workspace.yaml`, etc.) to include new sub-app

**Default decision**: defer to v2.2. The "redo pipeline in fresh dir + manual copy" workaround documented in HANDSHAKE §8 is acceptable at v2.0 single-maintainer scale.

#### BL-218 - v2.1: `LP_ALLOW_NONLOCAL_FS=1` env-var override (if downstream demand surfaces)

**Driver**: Layer 5 product-lens P1-PL5-1. Layer 4 hinted at this env var in `.first-run-marker` filesystem-whitelist rejection message, but never specified it. Layer 5 removed the phantom hint; v2.0 ships fail-closed for non-local filesystems (WSL2 9p, tmpfs, overlayfs, FUSE).

**At v2.1 design time** (only if telemetry/issues surface real demand):

1. Define env-var truth table parallel to `LP_CONFIG_AUTO_REVIEW`: `LP_ALLOW_NONLOCAL_FS=1` only honored when `_is_ci_environment()` is true (closes hostile-rcfile pivot)
2. Always-write to security-events.jsonl: `{event: "nonlocal_fs_override_used", fs_type: <detected>, ...}`
3. Document in OPERATIONS §1 as parallel structure to `LP_CONFIG_AUTO_REVIEW`
4. Tier 1 reveal panel mentions both env vars for CI users
5. Empirically test on WSL2 9p, Docker overlayfs, FUSE — confirm fcntl.flock semantics are reliable enough for nonce-replay protection

**Default decision**: drop the v2.0 hint, defer the override. Real CI-runner overlayfs need is addressed by Phase -1 acceptance gate (whitelist add for GHA Ubuntu's actual fstype after empirical check).

#### BL-219 - v2.2: `tests/fixtures/manifest.yml` schema_version evolution path

**Driver**: Layer 5 data-migration P2-DM5-2 (Layer 7 retarget v2.1→v2.2 per L6-λ #8). v2.0 ships `manifest.yml` with `schema_version: "1.0"` (registered in HANDSHAKE §10 lifecycle bump list per Layer 5; absent vs unknown disambiguation pinned at v2.0 per OPERATIONS §4 Layer 7 closure of L6-λ #2). **v2.1 retarget rationale**: v2.1 is documentation-only per Layer 7 strip-back; no v1.1 manifest schema evolution lands at v2.1. The schema-bridge work makes sense alongside other v2.2 manifest-coupled changes (e.g., `target_recovery_op_enum_version` only matters once BL-231 recovery_commands runtime enforcement ships).

**At v2.2 design time**:

1. Define `MANIFEST_SCHEMA_VERSIONS = frozenset({"1.0", "1.1"})` consumer-superset rule
2. Bridge spec for "v1.0 manifest read by v1.1-aware reader" — backfill missing columns with safe defaults
3. CI lint: `--regenerate-fixtures` reads manifest schema_version, refuses unknown (rejection reason already pinned at v2.0: `manifest_schema_unsupported`; absent-field rejection: `manifest_schema_version_missing`)
4. Test fixtures cover both v1.0-shape and v1.1-shape manifests

**Default decision**: defer to v2.2. v2.0 ships v1.0 only with absent-vs-unknown disambiguation pinned; v2.2 introduces v1.1 with the bridge alongside other manifest-coupled v2.2 work.

#### BL-220 - v2.2: `security-events.jsonl` rotation + verify-chain consumer

**Driver**: Layer 5 security-lens P1-S1. **Layer 7 strip-back** retargets from v2.1 → v2.2 because v2.1 is documentation-only AND the underlying `security-events.jsonl` itself is deferred to v2.2 via BL-223 (forensic_writer split). Without forensic_writer at v2.0, there's no producer for the chain consumer to walk.

**At v2.2 design time** (depends on BL-223 forensic_writer landing first):

1. Add `prev_entry_sha256` chain field (was originally a v2.0 baseline, deferred to v2.2 alongside forensic_writer)
2. Add 1MB rollover with 10-bak retention if file growth becomes operationally painful
3. Add `lp-memory-report --security-events --verify-chain` consumer that walks the chain and reports break point on tampering
4. Same atomic-rename protocol as nonce ledger rotation
5. Per-process forensic_writer caching for chain head

**Default decision**: defer. v2.0 ships zero forensic logging surface; v2.2 introduces the full set (forensic_writer + chain + consumer).

#### BL-221 - v2.2: Automated recovery tooling for `recovery_commands` consumer

**Driver**: OPERATIONS §6 gate #11 + Layer 5 spec-flow P1-LF1 + adversarial P1-A2. **Layer 7 strip-back** retargets from v2.1 → v2.2 (v2.1 docs-only). v2.0 ships the structured `recovery_commands` array as a forward-compat hint; humans read `recommended_recovery_action` prose. No v2.0 tool consumes the structured array. Runtime enforcement contract (closed enum + denylist + idempotency + sha256 + .recovery.lock) is in BL-231.

**At v2.2 design time** (depends on BL-223 forensic_writer + BL-231 runtime enforcement contract):

1. New CLI `plugin-recover-from-failed-scaffold.py` reads `.launchpad/scaffold-failed-<ts>.json`
2. Verifies `sha256` self-hash before executing any op (Layer 5 P3-S1)
3. Holds `LOCK_EX` on `.recovery.lock` for entire read+validate+execute cycle (Layer 5 P3-1)
4. Re-validates every `path:` against §6 validator at execute-time (Layer 5 P3-1)
5. Halts on first failure; writes `recovery-partial-<ts>.json` via forensic_writer
6. Honors at-most-one-rerun-per-array invariant
7. Spawns `rerun` op fire-and-forget (does NOT block on exit)

**Default decision**: defer. v2.0's structured array is not load-bearing without the consumer; humans consume the prose.

#### BL-222 - v2.2+: Confirm `forensic_writer.py` split holds after evolution

**Driver**: Layer 5 architecture P2-A2. **Layer 7 strip-back** retargets from v2.1+ → v2.2+ since the split itself is deferred to v2.2 via BL-223. Once `forensic_writer.py` ships at v2.2, this BL becomes a v2.3+ retrospective on whether the boundary held.

**At v2.3+ design time** (after BL-223 has landed at v2.2):

1. Audit any new JSONL/audit-log paths added since BL-223
2. Confirm each routes through the correct writer (analytics vs forensic)
3. Add CI lint asserting `os.write(.harness/observations/...)` calls pass through one of the two helpers
4. Update CODEOWNERS if writers gain co-owners

**Default decision**: defer. Re-audit after BL-223 ships.

<!-- Layer 7 strip-back (2026-04-30) — operational/security infrastructure deferred to v2.2 per user direction.
v2.1 is documentation-focused (METHODOLOGY/HOW_IT_WORKS/governance updates); v2.2 absorbs the heavyweight
operational/security infrastructure that didn't earn its place at v2.0 against the stated threat model
(single-maintainer plugin used by ~3-4 downstream projects). -->

### v2.2 strip-back bundle overview (Layer 8 — closes code-simplicity P3 readability)

The 13 BL entries below (BL-223 through BL-235) collectively form the v2.2 operational/security infrastructure deferral. Quick-reference table:

| BL     | Component                                                             | Reference doc + section                    |
| ------ | --------------------------------------------------------------------- | ------------------------------------------ |
| BL-220 | `security-events.jsonl` rotation + verify-chain consumer              | HANDSHAKE §3 (Layer 5 audit-trail wording) |
| BL-215 | `restamp-history.jsonl` chain hashing (`prev_entry_sha256`)           | OPERATIONS §4                              |
| BL-221 | Automated recovery tooling (`recovery_commands` consumer)             | OPERATIONS §6 gate #11                     |
| BL-222 | `forensic_writer.py` split retrospective                              | HANDSHAKE §12 file table                   |
| BL-223 | `forensic_writer.py` SRP-split module + 4 forensic JSONL paths        | HANDSHAKE §12 + OPERATIONS §5              |
| BL-224 | Multi-signal CI detection (`_has_ci_filesystem_signal`)               | HANDSHAKE §3                               |
| BL-225 | AST `pull_request_target` shape check via PyYAML                      | HANDSHAKE §12 + OPERATIONS §2              |
| BL-226 | Tag protection rule + content verification + watchdog                 | HANDSHAKE §10 + OPERATIONS §2              |
| BL-227 | §7.0 `vX.Y.Z-recalled` rename procedure                               | OPERATIONS §7.0 (audit-trail wording)      |
| BL-228 | §7.3 24h post-tag observation window + decision matrix                | OPERATIONS §7.3 (audit-trail wording)      |
| BL-229 | `rollback-runbook.md` + `branch-protection-token.md` runbooks         | HANDSHAKE §12 file table                   |
| BL-230 | Consolidated `v2-nightly-checks.yml` + 3 separate workflows           | HANDSHAKE §12 + OPERATIONS §2              |
| BL-231 | `recovery_commands` runtime enforcement contract                      | OPERATIONS §6 gate #11                     |
| BL-232 | Exponential-backoff polling for `verify-v2-ship`                      | HANDSHAKE §12 verify-v2-ship row           |
| BL-233 | KAT cross-platform parity (macOS leg)                                 | HANDSHAKE §3                               |
| BL-234 | 90-day PAT lifecycle + token rotation runbook                         | OPERATIONS §2                              |
| BL-235 | `.first-run-marker` integrity binding + `brainstorm_session_id` field | HANDSHAKE §4 rule 10 + rule 12             |

Detailed BL entries below preserve per-item rationale + at-v2.2-design-time steps + decision criteria.

#### BL-223 - v2.2: `forensic_writer.py` SRP-split module + 4 forensic JSONL paths

**Driver**: Layer 5 architecture P2-A2 + security-lens P1-S1 (Layer 7 strip-back deferral). v2.0 ships zero forensic-logging surface — neither `security-events.jsonl` nor `scaffold-rejection-<ts>.jsonl` nor `recovery-partial-<ts>.json` nor chain-hashing on `restamp-history.jsonl`. Threat model concedes "compromised in-process Claude session is out of scope" + "same-UID attacker is out of scope" — forensic primitives without a verifier (BL-220 verify-chain consumer also deferred) are YAGNI at single-maintainer scale.

**At v2.2 design time**:

1. Create `plugins/launchpad/scripts/forensic_writer.py` with `write_security_event()` + `write_scaffold_rejection()` + `write_recovery_partial()` + `write_restamp_audit()` helpers
2. 4 separate locks: `.security-events.lock`, `.scaffold-rejection.lock`, `.recovery.lock`, `.restamp-audit.lock` — closes DoS coupling where a long-held telemetry-prune lock would block forensic writes
3. File mode `0o600` via explicit `os.fchmod()`; atomic single-write ≤4096 bytes; `os.fsync(fd)` + `os.fsync(dirfd)` + `F_FULLFSYNC` on darwin
4. Always-written semantics (NOT gated by `telemetry: off`)
5. Closed event enum for `security-events.jsonl`: `{auto_review_accepted, auto_review_rejected_outside_ci, config_review_skipped_harness_missing, nonlocal_fs_override_used, first_run_marker_corrupt, first_run_marker_replayed, first_run_marker_swapped, recall_tag_squat_attempt, restamp_chain_violation, branch_protection_token_unauthorized, tag_protection_token_unauthorized, first_run_marker_lock_timeout}` — note `first_run_marker_lock_timeout` was missing from the Layer 5 spec; add at write-time
6. CODEOWNERS gate on the module
7. Tests for separate-locks DoS-non-coupling

**v2.0 substitution**: HANDSHAKE §3 "Security event log spec" subsection AND OPERATIONS §5 forensic-writer references are stripped from v2.0 ship. The Layer 5 audit-log baseline injection-defense (json.dumps + reject \r\n + flock + 0o600 + schema_version + pid forensic identity) for `restamp-history.jsonl` ships at v2.0 inline (not via forensic_writer), since the lefthook commit-msg hook is small and self-contained. Other forensic paths simply do not exist at v2.0.

**Default decision**: defer. v2.0 ships zero forensic logging.

#### BL-224 - v2.2: Multi-signal CI detection (`_has_ci_filesystem_signal`)

**Driver**: Layer 4 security-lens P1-S1 + Layer 5 adversarial P1-A4 + security-auditor P2-2 + security-lens P2-2 (Layer 7 strip-back deferral). v2.0 ships `_is_ci_environment()` checking only env-vars (`CI=true` + recognized vendor — `GITHUB_ACTIONS`/`GITLAB_CI`/etc.). Multi-layer signal (filesystem `/.dockerenv` + `RUNNER_TEMP` + `/proc/{ppid}/comm` parent-process check) deferred to v2.2.

**Threat model honesty at v2.0**: `LP_CONFIG_AUTO_REVIEW=1` opt-out is honored on env-var match alone. Hostile rcfile / dependency postinstall can pivot. The load-bearing defenses remain: (a) CODEOWNERS gate on the loader code path (OPERATIONS §2), (b) the soft-warn UX is non-blocking by design — at single-maintainer + ~3-4 downstream-project scale, the env-var-only gate is proportionate.

**At v2.2 design time**:

1. Add `_has_ci_filesystem_signal()` per Layer 5 spec: `/.dockerenv` + `/run/.containerenv` markers; `RUNNER_TEMP`/`RUNNER_TOOL_CACHE`/`GITHUB_WORKSPACE` env vars; `/proc/{ppid}/comm` parent-process name check against `_CI_PARENT_PROCESSES` frozenset
2. Multi-signal `_is_ci_environment()` requires CI=true + vendor env + at least one positive filesystem signal
3. Tests for hostile rcfile + dependency postinstall pivot
4. Documentation update for downstream CI users

**Default decision**: defer. v2.0 ships env-var-only `_is_ci_environment()`.

#### BL-225 - v2.2: AST `pull_request_target` shape check via PyYAML

**Driver**: Layer 4 security-lens P1-S2 + Layer 5 security-auditor P2-4 + security P2-S1 (Layer 7 strip-back deferral). v2.0 ships a grep-based forbidden-pattern check (greps for `${{ github.event.pull_request.head.sha }}` + `head.ref` + `merge_commit_sha` etc. as forbidden tokens in `.github/workflows/*.yml`). The PyYAML AST walk + `safe_load` + version pin + Phase -1 acceptance gate is deferred to v2.2.

**v2.0 grep regex** (lives in `plugin-v2-handshake-lint.py`):

```python
FORBIDDEN_GHA_PATTERNS = [
    r'\$\{\{\s*github\.event\.pull_request\.(head\.sha|head\.ref|head\.repo|merge_commit_sha|body|title|user\.login)',
    r'\$\{\{\s*github\.event\.workflow_run\.(head_sha|head_branch)',
]
```

Trade-off: grep can be bypassed via `fromJSON(toJSON())` / bracket-notation / expression-evaluator obfuscation. At single-maintainer scale and zero current external contributors, this is acceptable.

**At v2.2 design time**:

1. Add YAML AST walk via `yaml.safe_load` (PyYAML pinned via `_vendor/PYYAML_VERSION` constant)
2. Phase -1 acceptance gate against latest CVE list
3. CI lint sub-rule: assert `yaml.load(` does not appear in this script
4. Walk all `${{ … }}` expressions; reject by AST path matches
5. Tests for bracket-notation/`fromJSON(toJSON())` bypass attempts

**Default decision**: defer. v2.0 ships grep.

#### BL-226 - v2.2: Tag protection rule + content verification + watchdog

**Driver**: Layer 3 deployment P1-B + Layer 4 deployment N2 + adversarial P2-RT4-G + Layer 5 adversarial P1-A1 + security-lens P2-S3 (Layer 7 strip-back deferral). v2.0 relies on branch protection on `main` for tag-immutability; no separate GitHub tag-protection rule, no broadened pattern, no content verification.

**Trade-off**: a maintainer with admin rights can `git tag -d v2.0.0 && git push --delete origin v2.0.0` and re-tag. At single-maintainer + admin-sole-actor scale, this is operational discipline (don't do that), not a security gate.

**At v2.2 design time**:

1. Create GitHub tag-protection rule with broadened pattern `v[0-9]+\.[0-9]+\.[0-9]+(-(yanked|recalled|rc[0-9]+|dryrun))?`
2. `gh api repos/:owner/:repo/tags/protection --jq …` content verification: `allow_deletions: false`, no force-push exceptions, admins-only override
3. Phase 7.5 verification battery + nightly watchdog
4. Probe-then-fallback to `repos/:owner/:repo/rulesets` for endpoint-deprecation resilience

**Default decision**: defer. v2.0 ships branch protection only.

#### BL-227 - v2.2: §7.0 `vX.Y.Z-recalled` rename procedure + namespace-squat 404-check

**Driver**: Layer 3 deployment P1-A + spec-flow P1-1 + Layer 4 spec-flow P1-3 + adversarial P1-RT4-B + Layer 5 spec-flow P2-LF5/P1-LF2 + adversarial P1-A1/P2-A2 + security-auditor P2-3 (Layer 7 strip-back deferral). v2.0 rollback procedure is OPERATIONS §7.1 only (compressed 4-step yank + remediate + re-ship as v2.0.1). No `vX.Y.Z-recalled` tag, no namespace-squat 404 check, no per-id workflow-cancel loop, no idempotent `gh release delete`, no local-clone remediation, no user-facing recall communication checklist.

**Trade-off**: at v2.0 single-maintainer scale + ~3-4 downstream projects, a "delete tag + push v2.0.1" recovery path is proportionate. The §7.0 procedure is release-engineering for a 1000-customer SaaS.

**At v2.2 design time**:

1. Restore §7.0 8-step procedure: recall tag rename + 404 namespace-squat pre-condition + yank marketplace pointer first + draft release + asset preservation + per-id workflow-cancel loop + idempotent release-object delete + bump-commit revert + ship next patch
2. Local-clone remediation subsection (`git fetch --tags --force`)
3. User-facing recall communication checklist
4. Pre-existing recall-tag 404-check as new gate in verify-v2-ship

**Default decision**: defer. v2.0 §7.1 is sufficient.

#### BL-228 - v2.2: §7.3 24h post-tag observation window + decision matrix

**Driver**: Layer 5 deployment P1-D2 (Layer 7 strip-back deferral). v2.0 ships no formal observation window. Post-tag, the maintainer manually monitors for installer issues; no decision matrix, no T+1h/6h/24h install-verification protocol, no `verify-v2-ship` re-run on schedule, no CHANGELOG acknowledgment edit.

**At v2.2 design time**:

1. Restore §7.3 monitored signals enumeration (install-blocker label, T+1h/6h/24h manual install verification, 4h verify-v2-ship re-run schedule, CHANGELOG acknowledgment edit)
2. Restore decision matrix: install-blocker confirmed <2h → §7.0 recall; 2h-24h → §7.0 + escalation; >24h → §7.1 yank; verify-v2-ship re-run fails → §7.0
3. Cross-link to BL-229 rollback-runbook

**Default decision**: defer. v2.0 maintainer monitors informally.

#### BL-229 - v2.2: rollback-runbook.md + branch-protection-token.md authored runbooks

**Driver**: Layer 4 + Layer 5 deployment P1-D1 + security-lens P2-S2 (Layer 7 strip-back deferral). v2.0 does NOT author `docs/maintainer/rollback-runbook.md` or `docs/runbooks/branch-protection-token.md` as Phase -1 deliverables. The compressed §7.1 procedure inline in OPERATIONS is sufficient for v2.0 scale; PAT lifecycle is informally documented in the v2.0.0 release notes (rotate annually, regenerate via GitHub UI).

**At v2.2 design time** (depends on BL-226 tag protection landing first):

1. Author `docs/maintainer/rollback-runbook.md`: full 6-step compressed-rollback procedure, §7.0 walkthrough, §7.2 un-yank walkthrough, severity decision tree, "what rollback does NOT undo," 3-patch-14-day escalation rule, 24h post-tag observation window monitored signals, paper rollback drill protocol
2. Author `docs/runbooks/branch-protection-token.md`: PAT lifecycle, rotation cadence (90-day max), secret update procedure, fail-closed contract, compromise detection, revocation, recovery from expired-mid-PR
3. CI lint asserts both runbooks contain the required H2 sections

**Default decision**: defer. v2.0 ships compressed §7.1 inline.

#### BL-230 - v2.2: Consolidated `v2-nightly-checks.yml` workflow (3 jobs)

**Driver**: Layer 5 performance P2-L5-1 + architecture P2-A3 (Layer 7 strip-back deferral). v2.0 ships only `v2-handshake-lint.yml` (PR-triggered) and the basic `v2-release.yml` for tag-emission. No nightly cron workflow, no branch-staleness-check, no separate branch-protection-watchdog, no tag-protection-watchdog (latter blocked on BL-226 anyway).

**At v2.2 design time** (depends on BL-226 tag protection):

1. Create `.github/workflows/v2-nightly-checks.yml` with 3 jobs: `branch-protection`, `tag-protection`, `branch-staleness`
2. `concurrency: { group: v2-nightly-checks, cancel-in-progress: true }` for cron-coalescing
3. Independent failure semantics; one failing does NOT mask another
4. Each job opens a separate GitHub issue on failure

**Default decision**: defer. v2.0 ships PR-triggered lint only.

#### BL-231 - v2.2: `recovery_commands` runtime enforcement contract

**Driver**: Layer 5 spec-flow P1-LF1/LF6/LF8 + adversarial P1-A2 + security P3-1/S1 (Layer 7 strip-back deferral). v2.0 ships the `recovery_commands` structured array as a forward-compat hint (humans read `recommended_recovery_action` prose; no runtime consumer). No closed enum + denylist + idempotency contract + execute-time path re-validation + sha256 self-hash + `.recovery.lock` consumer concurrency lock + at-most-one-rerun rule + closed `command` set for `rerun` op.

**At v2.2 design time** (depends on BL-221 automated recovery tooling + BL-223 forensic_writer):

1. `op` closed enum: `{rmdir_recursive, rm, rerun}`
2. Destructive-path denylist: `{".", "./", "..", "/", "~", ".launchpad", ".git", ".github"}`
3. Idempotency contract per op
4. Execute-time path re-validation against §6 path-validator regex + ancestor-symlink check
5. Recovery JSON sha256 self-hash; consumer verifies before executing
6. `.recovery.lock` LOCK_EX held for entire read+validate+execute cycle
7. At-most-one-rerun rule + `rerun` LAST element + closed `command` set
8. `failed_layer_index: null` for cross-cutting/secret-scan failures

**Default decision**: defer. v2.0's structured array is forward-compat hint; humans consume prose.

#### BL-232 - v2.2: Exponential-backoff polling for `verify-v2-ship`

**Driver**: Layer 5 frontend-races P2-L5-A2 + deployment P2-D1 (Layer 7 strip-back deferral). v2.0's `verify-v2-ship` CI job runs ONCE post-tag with no propagation-race retry. GitHub check-runs API has ≤120s eventual-consistency window between squash-merge and tag-emission; v2.0 accepts the rare false-fail and relies on manual workflow_dispatch re-run.

**At v2.2 design time**:

1. 60-90s exponential-backoff polling loop before the check-runs predicate
2. Explicit non-empty assertion: `length >= 1 || fail "no check-runs found (propagation race?)"`
3. Tightening of `${{ github.run_id }}` self-loop break — switch from JQ filter on `databaseId != github.run_id` (which is semantically wrong: `run_id` is workflow-run-id, not check-run-id namespace) to `name != "verify-v2-ship"` filter

**Default decision**: defer. v2.0 verify-v2-ship runs once; manual re-run on transient failure.

#### BL-233 - v2.2: KAT cross-platform parity matrix (macOS + Windows)

**Driver**: Layer 2 P2-4 + Layer 3 simplicity P1-A (Layer 7 strip-back deferral). v2.0 KAT runs Linux-only on the v2-handshake-lint workflow. macOS CI matrix leg + the cross-platform parity assertion (Linux CI and macOS CI produce identical new hashes for the same fixture) deferred to v2.2.

**At v2.2 design time**:

1. Add `runs-on: macos-latest` job to `v2-handshake-lint.yml`
2. Cross-platform parity KAT: `_legacy_yaml_canonical_hash(fixture) != canonical_hash(fixture)` AND Linux/macOS produce identical new hashes
3. Phase 7.5 acceptance gate: both matrix legs pass before tag-emission
4. Windows support is separately deferred (POSIX-only at v2.0; v2.1+ via BL-existing platform_unsupported_v2_0)

**Default decision**: defer. v2.0 ships Linux-only KAT; manual macOS spot-check before tag-emission.

#### BL-234 - v2.2: 90-day PAT lifecycle ceremony + token rotation runbook

**Driver**: Layer 2 F-03 + Layer 3 security-lens P2-S2 + adversarial P1-RT-3 (Layer 7 strip-back deferral). v2.0 uses a long-lived `BRANCH_PROTECTION_READ_TOKEN` PAT with informal annual-rotation note in v2.0.0 release notes. No 90-day max-lifetime mandate, no formal rotation log in `docs/releases/`, no `branch-protection-token.md` runbook (covered by BL-229).

**At v2.2 design time** (lands with BL-229 runbook):

1. 90-day max PAT lifetime
2. Rotation logged in `docs/releases/`
3. Workflow MUST mask token: `echo "::add-mask::${{ secrets.BRANCH_PROTECTION_READ_TOKEN }}"`
4. Restrict consumption to non-fork PRs only via `if: github.event.pull_request.head.repo.full_name == github.repository`
5. Recovery-from-expired-mid-PR procedure

**Default decision**: defer. v2.0 ships long-lived PAT + informal rotation reminder.

#### BL-235 - v2.2: `.first-run-marker` integrity binding + `brainstorm_session_id` schema field + `.first-run-marker.lock`

**Driver**: Layer 4 integrity binding + Layer 5 frontend-races P1-L5-A FD-based TOCTOU close + security-auditor P1-1 + spec-flow P1-LF3 + schema-drift P1-SD5-1 (Layer 7 strip-back deferral). v2.0 ships the original Layer 3 `.first-run-marker` as a simple positive-presence sentinel: empty file written by `/lp-brainstorm` ONLY when `greenfield: true`, consumed (renamed to `.first-run-marker.consumed.<iso-ts>`) by `/lp-scaffold-stack` after first successful run. No JSON envelope, no `schema_version`/`brainstorm_session_id`/`bound_cwd`/`sha256` fields, no dedicated `.first-run-marker.lock`, no FD-based read with pre-rename re-stat, no microsecond+pid timestamp precision.

**Trade-off**: v2.0 marker defends only the canonical "first run" boundary (was a 60s ctime/mtime heuristic in pre-Layer-3 spec; the simple positive-marker is an upgrade). It does NOT defend cross-project marker-copy attacks, replay attacks via session_id mismatch, path-vs-inode TOCTOU, or DoS lock-coupling. Threat model concedes "compromised in-process Claude session is out of scope" + "same-UID attacker is out of scope"; cross-project marker-copy requires an attacker with file-write access to both projects, which is out of scope.

**At v2.2 design time**:

1. Restore Layer 5 marker JSON envelope: `{schema_version, generated_at, brainstorm_session_id, generated_by, bound_cwd, sha256}`
2. Add `brainstorm_session_id` field to `scaffold-decision.json` schema (§4 rule 12 validation)
3. Dedicated `.first-run-marker.lock` (split from `.scaffold-nonces.lock`)
4. FD-based consumption: `O_RDONLY|O_NOFOLLOW` + `os.fstat` + pre-rename re-stat under lock
5. Microsecond+pid timestamp on `.consumed.<ts>.<pid>` rename target
6. LOCK_NB acquisition timeout (10s ceiling)
7. Closes: cross-project marker copy, replay-via-stale-session_id, path-vs-inode TOCTOU, lock-coupling DoS

**Default decision**: defer. v2.0 ships simple positive-marker.

#### BL-236 - v2.1: Lefthook Python coverage expansion (ruff + pytest + pyright + v2-handshake-lint pre-push)

**Driver**: v2.0 ships ~25+ new Python modules (`lp_pick_stack/`, `lp_scaffold_stack/`, primitives, CLIs, hooks) with zero project-wide Python style/lint enforcement and zero pre-commit pytest gate. Today's lefthook covers the TypeScript side comprehensively (prettier-fix + `eslint-fix` + `typecheck` + structure-check + large-file/whitespace/EOL guards) but the Python side is essentially uncovered: (1) no style/lint, (2) no static type-check, (3) no test execution pre-commit, (4) no v2.0 contract validation pre-push. CI catches all four on PR push, but a contributor who breaks any of them locally only learns at PR time. The asymmetry was deliberately accepted at v2.0 (the v2.0 ship surface itself was the hot path); now that v2.0 has shipped, closing the symmetry is the natural v2.1 move.

**Why v2.1 (not v2.2)**: BL-237 already established the precedent — small lefthook/CI-lint configuration tweaks count as "configuration adjustments, not implementation work" and fit within v2.1's documentation-focused framing without crossing the docs-only boundary. The lefthook expansion here is the same shape (config wiring + `pyproject.toml` authoring + auto-fix baseline commit). Unlike the v2.2 operational/security infrastructure (forensic_writer split, AST PR-target check, multi-signal CI detection), this BL doesn't add a new module, schema, runtime, or threat-model surface — it wires existing tools (`ruff`, `pytest`, `pyright`, the already-shipped `plugin-v2-handshake-lint.py`) into the local hook chain.

**Trade-off**: v2.0 ships without these gates because (a) adding `ruff` now would surface hundreds of pre-existing style warnings, blocking ship for cosmetic-only fixes; (b) `pytest` in pre-commit on a 546-test suite (33s wall) would slow the inner loop materially; (c) `pyright` requires a pyproject + annotation pass that's better done deliberately, not mid-ship; (d) `v2-handshake-lint` runs on every PR via CI already. The v2.0 Python gates of record were `pytest` correctness + the custom schema/grep checks — both adequate for ship, neither adequate as the inner-loop developer feedback path post-ship.

**At v2.1 design time**:

**A. Ruff (style + simple bugs)**

1. Add `ruff` to `_vendor/RUFF_VERSION` pin (parallel to `PSUTIL_VERSION` and `PYYAML_VERSION` per HANDSHAKE §1.4 supply-chain pattern); CVE-feed acceptance gate at v2.1 Phase -1.
2. Author a top-level `pyproject.toml` (or `ruff.toml`) with the project's chosen rule set. Suggested starter: `extend-select = ["E", "F", "I", "B", "UP"]` (errors, pyflakes, import-sort, bugbear, pyupgrade); `target-version = "py311"`.
3. Run `ruff check --fix` once across `plugins/launchpad/scripts/` to baseline. Land the auto-fixes in a single ride-along commit before adding the gate.
4. Add `ruff-check` to `lefthook.yml` `pre-commit.commands`: `glob: "*.py"`, `run: ruff check {staged_files}`, priority 10 (read-only check, blocks on failure). Pair with `ruff-format` if format consistency is also wanted (mirrors the prettier+eslint pairing on the TS side).
5. Add a `ruff` step to `.github/workflows/v2-handshake-lint.yml` between `pytest` and the existing custom lint, so CI catches what dev-side lefthook missed (or what fork-PR contributors didn't run locally).

**B. Pytest in lefthook pre-commit**

6. Add `pytest` to `lefthook.yml` `pre-commit.commands`: `run: cd plugins/launchpad/scripts && pytest -q`, priority 20 (after lint/typecheck so style failures surface first). Wall-time concern at 546 tests / ~33s — if friction surfaces, fall back to changed-files-only with `pytest --picked` (pytest-picked plugin) and run the full suite in `pre-push` instead.
7. Decision criterion at v2.1 design: measure inner-loop friction during a single dev session before committing to the always-on pre-commit pytest. If 33s per commit is too slow, use the pre-push fallback. The full suite WILL run on PR via CI either way; this is purely about local feedback latency.

**C. Pyright/Pylance (Python static type-check, symmetric with TS `typecheck`)**

8. Author `pyrightconfig.json` (or extend `pyproject.toml`'s `[tool.pyright]`) with `include = ["plugins/launchpad/scripts"]`, `exclude = ["**/_vendor", "**/tests"]`, `pythonVersion = "3.11"`, `typeCheckingMode = "standard"` (NOT strict — strict-mode would force annotation churn across the v2.0 codebase). Tighten to `strict` for contract-touching modules only via per-file `# pyright: strict` directives: `decision_validator.py`, `nonce_ledger.py`, `engine.py` (pick_stack + scaffold_stack), `decision_integrity.py`.
9. Add `pyright-check` to `lefthook.yml` `pre-commit.commands`: `run: pyright`, priority 10 (parallel with typecheck on the TS side). Pin pyright version via `_vendor/PYRIGHT_VERSION` (same pattern as ruff).
10. Add a `pyright` step to `.github/workflows/v2-handshake-lint.yml` for CI parity.

**D. v2-handshake-lint in pre-push (cheap local enforcement of the v2.0 contract)**

11. Add `v2-handshake-lint` to `lefthook.yml` `pre-push.commands`: `run: python3 plugins/launchpad/scripts/plugin-v2-handshake-lint.py && python3 plugins/launchpad/scripts/plugin-v2-handshake-lint.py --check-leakage && python3 plugins/launchpad/scripts/plugin-v2-handshake-lint.py --check-version-coherence --phase=post-tag`. Pre-push (not pre-commit) because the full lint runs are cheap (~1s) but already caught upstream by lefthook's pre-commit eslint/typecheck pair on the JS side; pre-push is the natural symmetric placement and prevents pushing a contract-violating commit even if a pre-commit gate was bypassed.
12. Closes: silent v2.0-contract regressions that today only surface on CI; symmetry with the TS `pre-commit typecheck` pattern; faster inner-loop feedback for Python contract violations.

**E. Cross-cutting**

13. Update `CLAUDE.md` "Definition of Done" subsection (project root) to add `pytest -q`, `ruff check`, `pyright` to the gates list. Currently lists only `pnpm test` / `pnpm typecheck` / `pnpm lint`.
14. Update `.harness/harness.local.md` review-context block if it documents the lefthook coverage explicitly.
15. Closes: style drift across contributors, unused-import accumulation, import-order chaos, simple bug classes that pytest doesn't catch (e.g., shadowed builtins, accidental `==` vs `is`); Python type-check parity with the TS side; v2.0 contract enforcement at the local hook chain (not just CI).

**Phase 7.5 pre-ship review findings (D-verdict, fold into the v2.1 ruff sweep)**: a `lp-kieran-foad-python-reviewer` pre-ship pass surfaced 13 D-verdict items that ruff would catch or that pair with the ruff rollout. Listed here so the v2.1 implementer has a concrete starter punch-list:

- D3: `lp_pick_stack/rationale_renderer.py:189-192` — default `alternatives` fallback bullet length is just barely above the 30-char minimum; add a unit-test pin so future shortening doesn't silently break ambiguity-cluster validator output.
- D4: `lp_scaffold_stack/cross_cutting_wirer.py:109-116` — `_atomic_write` uses `path.write_text` instead of the `O_CREAT|O_EXCL|fsync` pattern used by `decision_writer.py` and `receipt_writer.py`. Harmonize to close the TOCTOU window.
- D5: `lp_scaffold_stack/cleanup_recorder.py:240-242` — `target.exists() + os.open(O_CREAT|O_EXCL)` doesn't catch `FileExistsError` for retry. Mirror `rejection_logger.py`'s retry ladder.
- D6: `telemetry_writer.py:36-56` — `_telemetry_off` uses single-line grep parser for `telemetry: off`; replace with `yaml.safe_load` once config-loader is on the v2.0 hot path.
- D7: `lp_scaffold_stack/nonce_ledger.py:144-148` — Linux mountinfo parser doesn't decode `\040`-escaped spaces in mount points; mountpoints with spaces would silently mis-parse.
- D8: `lp_pick_stack/decision_writer.py:126-133` and `receipt_writer.py:152-159` — directory `fsync` failure silently swallowed; emit a debug-level telemetry signal instead of `pass`.
- D9: `plugin-v2-handshake-lint.py:241-258` — `_git_grep` walks the filesystem (no git involved); rename to `_walk_grep` or update docstring to lead with the actual semantics.
- D10: `lp_pick_stack/engine.py:520-521` and `lp_scaffold_stack/engine.py:188-191` — `_emit_telemetry` uses bare `except Exception: pass`; narrow to `(OSError, ValueError, json.JSONDecodeError)` for explicit failure modes.
- D11: `lp_scaffold_stack/nonce_ledger.py:131-148` — longest-prefix-match for mount-point detection uses `>=` not `>`, so two equal-length matches keep the LATER one (filesystem-ordering-dependent). Replace with `>` for strict longest-match-wins, OR document the tiebreak explicitly.
- D12: `lp_scaffold_stack/engine.py:330-338` — pre-resolve nonce-ledger lookup uses character-by-character hex check instead of the existing `_UUID4_HEX_RE.fullmatch`; consolidate.
- D13: `lp_pick_stack/engine.py:267` — `len(clusters) != 1 or None in {c.cluster for c in candidates}` re-builds the set without the None-filter; refactor for clarity (logic is correct, double-scan is wasteful).
- D14: `lp_scaffold_stack/decision_validator.py:138` — `reason = "path_traversal" if "traversal" in msg or "escapes cwd" in msg else …` — substring-matching on error messages is brittle. Have `PathValidationError` carry a `category` attribute (`"shape" | "traversal" | "ancestor_symlink"`) for direct dispatch.
- D15: `cwd_state.py:73-76` — single-README greenfield carve-out logic reads inverse to the comment intent (`README.md` already in `GREENFIELD_OK_FILES` is filtered out before `extras` is computed). Either inline-check `"README.md" in names` more clearly or remove the redundant condition.

These are the polish/hardening items the agent surfaced; ruff itself catches a subset (D9 naming, D10 broad-except, D13 redundant computation), the rest are spec-vs-code drift fixed during the v2.1 implementation pass.

**Default decision**: defer to v2.1. v2.0 ships with `pytest` + custom lint as the Python gates; the lefthook expansion (ruff + pytest + pyright + v2-handshake-lint pre-push) lands alongside the v2.1 documentation refresh as a small configuration adjustment, not implementation work — same precedent as BL-237.

#### BL-237 - v2.1: Tighten `V2_MODULES` scope to package-aware path-prefix matching

**Driver**: Phase 7.5 pre-ship Python review surfaced a CI-lint coverage hole. `plugin-v2-handshake-lint.py:147-159` defines `V2_MODULES` as a frozenset of top-level basenames only (e.g., `decision_integrity.py`, `safe_run.py`, `cwd_state.py`). The `check_no_raw_subprocess` and `check_no_shell_true` rules iterate over this set, so they silently SKIP every `.py` file under `lp_pick_stack/`, `lp_scaffold_stack/`, and `plugin_stack_adapters/` — the bulk of v2.0's Python surface. Result: a future regression introducing `subprocess.run` or `shell=True` in any package module would not be flagged.

**Concrete instance the gap masks today**: `lp_scaffold_stack/nonce_ledger.py:152-184` (`_detect_filesystem_type` macOS branch) calls `subprocess.run(["/sbin/mount"], …)` directly. The module docstring documents this as a deliberate exception. Practically low-risk (fixed argv, no shell, no user-controlled input), but the call (a) bypasses `safe_run`'s env-allowlist (inherits ambient `PATH`/`TMPDIR`), and (b) is missed by the v2 lint per the scope hole above.

**Trade-off**: v2.0 ships without the fix because (a) the actual `subprocess.run` call is benign in shape, (b) the lint passes today (silently — that's the bug), and (c) tightening the scope mid-flight in Phase 7.5 was out of the strip-back-aware ship surface. v2.1 is documentation-only per Layer 7 strip-back, but a lint-config tweak counts as a small configuration adjustment, not implementation work — it fits within v2.1's framing without crossing the docs-only boundary.

**At v2.1 design time**:

1. Replace the `V2_MODULES` frozenset with a path-prefix matcher: any `.py` file under `plugins/launchpad/scripts/` (excluding `_vendor/` and `tests/`) is in scope by default.
2. Re-run `check_no_raw_subprocess` + `check_no_shell_true` against the broadened scope. Triage any new hits.
3. `nonce_ledger.py:_detect_filesystem_type` macOS branch: route through `safe_run` with explicit env-allowlist override for the `/sbin/mount` invocation, OR replace with `os.statvfs` + `posix.statvfs.f_fstype` if a Python release adds the field cross-platform, OR add to a small `LINT_RAW_SUBPROCESS_ALLOWLIST` constant that names this exact call site with a comment block citing the fixed-argv/no-shell rationale.
4. Add a CI-lint sub-rule asserting that any new entry to the allowlist requires a docstring + module-level comment explaining the deviation.
5. Closes: silent CI-lint coverage hole that would mask future regressions; the broad-scope `safe_run` mandate from HANDSHAKE §6 is now actually enforced everywhere it claims to be.

**Default decision**: defer to v2.1. The v2.0 ship is clean (the fixed-argv mount call is not exploitable at single-maintainer scale); the lint-tightening is the correct fix and lands as a small configuration adjustment in v2.1.

#### BL-238 - v2.2: Promote django from curate → orchestrate-headless via auto-name derivation

**Driver**: PR #41 Codex review cycle 2 (P1 finding #3) escalated the original cycle 1 deferral. Codex argued (correctly) that shipping `django` as `type: orchestrate` with empty `destination_argv` is a known-broken catalog entry — `/lp-scaffold-stack` would invoke `django-admin startproject` without the required positional project name and either prompt (defeating pure-headless), fail with a usage error, or scaffold in the wrong shape.

v2.0 resolves this by demoting django from `orchestrate` → `curate` (matching the eleventy + fastapi shape — knowledge_anchor + options_schema only, no command). Users follow the django-pattern.md doc and run `django-admin startproject` themselves. The category-patterns.yml entries (saas-django-postgres, api-only-django-drf, realtime-django-channels) and the differentiator clusters that reference them remain valid; only the headless-orchestration path is removed.

**v2.2 retarget rationale**: when this BL was originally written for v2.1, the assumption was the auto-name derivation work was small enough to fit v2.1's docs-focused window. Codex's cycle-2 escalation forced a re-think — the correct shape requires (a) a `destination_argv_template` field with `${PROJECT_NAME}` substitution semantics, (b) a project_name allowlist regex matching django identifier rules, (c) layer.options schema extension with optional `project_name` override + tests for cwd-basename auto-derivation + sanitization. That's implementation work, not a config tweak; v2.2 (which ships the operational/security infrastructure layer) is the right home alongside BL-100/BL-101/etc. catalog restorations.

**At v2.2 design time**:

1. Extend `_build_orchestrate_argv` in `lp_scaffold_stack/layer_materializer.py` to support a `destination_argv_template` field with `${CWD_BASENAME}` and `${PROJECT_NAME}` substitutions (sourced from `cwd.name` and the scaffold-decision's project_name field respectively).
2. Update `scaffolders.yml` django entry: promote `type: curate` → `type: orchestrate`; add `command: "django-admin startproject"` + `destination_argv_template: ["${PROJECT_NAME}", "."]` (creates the python module with the user's chosen name, files in cwd).
3. Add validation: project*name must match `^[a-z]a-z0-9*]\*$` (django identifier rules — starts with letter, alphanumeric + underscore). Reject if cwd basename or supplied name fails the pattern.
4. Update layer.options schema to allow optional `project_name` override (otherwise auto-derive from cwd basename, sanitized via the regex above + s/-/\_/g).
5. Tests: add positive cases for cwd basename auto-derivation, override via layer.options.project_name, and rejection cases for invalid python identifiers.
6. Closes: headless django scaffolding works without interactive prompt; v2.0 curate-mode workaround obsolete.

**Default decision**: defer to v2.2. v2.0 ships django as `curate` so the orchestrate path can't fail; v2.2 promotes it back to orchestrate-headless via the template-based destination_argv shape.
