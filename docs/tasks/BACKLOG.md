# BACKLOG

> Central backlog for deferred and active work. Populated by developers and AI agents as the project evolves.

---

## Convention: BL ↔ CHANGELOG cross-reference (slip-prevention)

Every BL header MUST tag the release it's labeled for: `#### BL-NNN - vMAJOR.MINOR[.PATCH]: Title`. When a BL ships, do exactly ONE of:

1. **Reference `BL-NNN` in the matching `## [version]` block of `CHANGELOG.md`** (preferred — co-locates the human-readable closure with the change description), OR
2. **Add a `**Status (YYYY-MM-DD)**: SHIPPED in vX.Y.Z` line directly under the BL header**.

When a BL is intentionally deferred, change the header version label AND add `**Status (YYYY-MM-DD)**: RE-TARGETED vOLD → vNEW. <one-paragraph rationale>` directly under it.

A pre-push lefthook hook + CI step run `plugin-backlog-orphan-check.py --release <plugin.json version>`, which fails when any BL labeled for that release lacks both the CHANGELOG cross-reference AND the status line. This gate exists because BL-236 (lefthook Python coverage) was labeled for v2.1 but never implemented or deferred during the v2.1 cycle — the slip went undetected until 2026-05-07 ship preparation. The gate prevents this category of scope-doc-to-implementation-plan handoff loss.

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

#### BL-210 - Remove `_legacy_yaml_canonical_hash` at v2.2.0

**Driver**: Layer 3 data-migration P1-A re-hardening review. The legacy YAML-canonicalization hash function is kept under `DeprecationWarning(stacklevel=2)` for the v2.0.x line to support `LP_CONFIG_REVIEWED` migration UX (HANDSHAKE §3) AND the OPERATIONS §7 rollback path. **v2.2 retarget rationale** (was v2.1): post-v2.0 ship review reframed v2.0.1 as docs+hotfixes only and v2.1 as BL-236-only (lefthook Python coverage). The `_legacy_yaml_canonical_hash` cleanup pairs naturally with the v2.2 operational/security infrastructure bundle and gives the v1.x→v2.0 migration path two minor releases of soak time before removal.

**Concrete steps at v2.2.0 ship**:

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

#### BL-212 - v2.2 stack catalog expansion (10 deferred stacks)

**Status (2026-05-07)**: RE-TARGETED v2.1 → v2.2. The 10 deferred stacks (sveltekit, elysia, phoenix-liveview, convex, flutter, tauri, cloudflare-workers, nestjs, laravel, vite) are already covered by the CHANGELOG `[Unreleased]` block as v2.2 work. Discovered as an orphan during 2026-05-07 backlog audit (the script that surfaced BL-236).

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

#### BL-216 - `fsync_durable()` shared helper universalization at v2.2

**Driver**: Layer 4 pattern-finder F-3 + performance + testing. v2.0 applies F_FULLFSYNC on macOS only to nonce-ledger writes. Telemetry, receipt, recovery JSON, freshness report, first-run-marker all do plain `os.fsync` without F_FULLFSYNC. Inconsistent macOS durability.

**v2.2 retarget rationale** (was v2.1): post-v2.0 ship review (2026-05-02) reframed v2.0.1 as docs+hotfixes only and v2.1 as BL-236-only (lefthook Python coverage). The fsync universalization touches multiple writer modules and pairs naturally with the v2.2 operational/security infrastructure bundle. Internal refactor with no user-visible benefit at this scale.

**At v2.2 design time**:

1. Add `fsync_durable(fd)` shared helper to `safe_run.py` (or new `durability.py` module) that wraps `os.fsync(fd)` + conditional `F_FULLFSYNC` on `sys.platform == 'darwin'`
2. Apply consistently in: HANDSHAKE §4 rule 10 (nonce ledger — already has it), §5 receipt write spec, OPERATIONS §5 telemetry pruning, §6 gate #11 recovery JSON write, §4 rule 10 first-run-marker write
3. Effort estimate: ~30 min helper + ~1-2h applying across sites + ~1h tests = ~2-3h

**Default decision**: ship narrow F_FULLFSYNC at v2.0 (nonce ledger is the most security-critical durability path); broaden at v2.2.

---

#### BL-217 - Tier 1 reveal panel `n_docs` constant single-source at v2.2

**Driver**: Layer 4 architecture P3-6. The literal `8` for "architecture docs rendered" appears in HANDSHAKE §5 receipt schema + OPERATIONS §5 greenfield panel + brownfield panel. No shared constant.

**v2.2 retarget rationale** (was v2.1): the literal value was already corrected from `8` to `4` in PR #41 cycle 8 #2 (Codex P1) — the hardcoded mismatch is closed at v2.0. The remaining single-source refactor is trivial polish and pairs naturally with the v2.2 bundle. No reason to ship it standalone in v2.1.

**At v2.2 design time**:

1. Define `TIER1_ARCHITECTURE_DOCS = ("PRD.md", "TECH_STACK.md", ...)` constant in shared module
2. Receipt's `architecture_docs_rendered` computed as `len(TIER1_ARCHITECTURE_DOCS)`
3. Panel templates substitute `{n_docs}` rather than hard-coding `4`
4. CI lint: assert `git grep -nE '"?architecture_docs_rendered"?:?\s*[0-9]'` returns ≤1 hit
5. Effort estimate: ~30 min total

**Default decision**: ship hardcoded `4` at v2.0 (mismatch corrected per PR #41 cycle 8 #2); single-source at v2.2 alongside the rest of the bundle.

#### BL-106 - CLOSED: Native sub-app workflow (`/lp-add-subapp`) — won't ship

**Originally proposed**: a dedicated `/lp-add-subapp <path>` command for adding a sub-app inside a brownfield monorepo, re-using `/lp-pick-stack` + `/lp-scaffold-stack` scoped to a subpath, with `/lp-define` updating parent manifests.

**Closed 2026-05-03**. The chain-of-custody value of `/lp-pick-stack` peaks at greenfield, where the first stack decision is load-bearing and there are no precedents to match. For brownfield sub-app addition, existing-monorepo conventions dominate (shared `@repo/*` packages, ESLint inheritance, tsconfig path aliases, lefthook config) and the catalog scaffolder cannot read those — it would produce stock output that requires immediate agentic cleanup. A live Claude Code session reads-and-matches existing context in one pass and is structurally better suited to the task. Adding parent-manifest mutation to `/lp-define` would also stretch its bounded responsibility (architecture docs + agents.yml + config.yml + Tier 1 reveal panel) beyond its locked scope.

**Replacement**: SCAFFOLD_HANDSHAKE §8 now documents the canonical brownfield sub-app workflow as "use a live Claude Code session to scaffold the new sub-app, matching existing monorepo conventions." LaunchPad's value-add stays in the workflow harness around live agentic work (review, learn, plan, build, design), not in re-implementing scaffolding capabilities a live session does better.

#### BL-218 - v2.2: `LP_ALLOW_NONLOCAL_FS=1` env-var override (if downstream demand surfaces)

**Status (2026-05-07)**: RE-TARGETED v2.1 → v2.2. This BL was always conditional ("if downstream demand surfaces"). No demand signal surfaced during the v2.1 cycle. Re-targeting to v2.2 pushes the conditional gate forward without committing to implementation.

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

<!-- Post-v2.0.0 ship rebalance (2026-05-02): v2.0.1 absorbs the documentation refresh
(README/HOW_IT_WORKS/METHODOLOGY/REPOSITORY_STRUCTURE — BL-240/241/242/243), the
PR #41 cycle-12 hotfix bundle (BL-244), and the path:"." conflict (BL-239). v2.1
ships three ergonomics entries: BL-236 (lefthook Python coverage: ruff + pytest +
pyright + pre-push lint), BL-237 (V2_MODULES scope tightening), and BL-246
(/lp-release command — automate the manual ship ceremony for versioned-artifact
projects).
v2.2 absorbs the heavyweight operational/security infrastructure that didn't earn
its place at v2.0 against the stated threat model (single-maintainer plugin used
by ~3-4 downstream projects), plus deferred-stack restorations (BL-100..104),
the forward-compat matrix (BL-211), and v2.1-conditional items now
retargeted (BL-210 legacy YAML hash removal, BL-216 fsync_durable, BL-217 n_docs
constant). Conditional-on-signal items (BL-213 freshness tiers, BL-214 GPG tags,
BL-218 LP_ALLOW_NONLOCAL_FS) stay parked until telemetry surfaces real demand. -->

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

#### BL-236 - v2.1.1: Lefthook Python coverage expansion (ruff + pytest + pyright + v2-handshake-lint pre-push)

**Status (2026-05-09)**: SHIPPED in v2.1.1 — see PR #62 + commit `<SHA>`

**Status (2026-05-07)**: RE-TARGETED v2.1 → v2.1.1. The original v2.1 scope (post-v2.0.0 rebalance, 2026-05-02) was BL-236 + BL-237 (two contributor-experience BLs). v2.1 then expanded into "plugin-owns-everything" (composition wrapper, sealed identity, `/lp-bootstrap`, `/lp-update-identity`, kernel renderer, stack-aware dispatch — 12 implementation phases over 4 days). BL-236 was never folded into any phase plan and was not surfaced in any phase exit criterion or Phase 11 ship-readiness checklist. Discovered post-hoc on 2026-05-07 during PR #50 ship preparation when the user asked whether v2.1 had implemented Python lefthook coverage. Re-targeting to v2.1.1 alongside BL-255..260 rather than blocking v2.1.0 ship — adding ruff now would surface hundreds of pre-existing warnings and require a baseline auto-fix commit, both of which are inappropriate during a ship window. See "Backlog-slip prevention" notes appended to v2.1.1 patch lane after this entry.

**Driver**: v2.0 ships ~25+ new Python modules (`lp_pick_stack/`, `lp_scaffold_stack/`, primitives, CLIs, hooks) with zero project-wide Python style/lint enforcement and zero pre-commit pytest gate. Today's lefthook covers the TypeScript side comprehensively (prettier-fix + `eslint-fix` + `typecheck` + structure-check + large-file/whitespace/EOL guards) but the Python side is essentially uncovered: (1) no style/lint, (2) no static type-check, (3) no test execution pre-commit, (4) no v2.0 contract validation pre-push. CI catches all four on PR push, but a contributor who breaks any of them locally only learns at PR time. The asymmetry was deliberately accepted at v2.0 (the v2.0 ship surface itself was the hot path); now that v2.0 has shipped, closing the symmetry is the natural v2.1 move.

**Why v2.1 (not v2.2)**: post-v2.0.0 ship rebalance (2026-05-02) reframed v2.1 around contributor-experience improvements — BL-236 (lefthook Python coverage) + BL-237 (V2_MODULES scope tightening) are the two entries. Both are small configuration tweaks, not new threat-model surfaces; both directly improve the experience for outside contributors who'd otherwise hit silent style/lint failures only at PR time. Unlike the v2.2 operational/security infrastructure (forensic_writer split, AST PR-target check, multi-signal CI detection), this BL doesn't add a new module, schema, runtime, or threat-model surface — it wires existing tools (`ruff`, `pytest`, `pyright`, the already-shipped `plugin-v2-handshake-lint.py`) into the local hook chain.

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
- ~~D4~~: **CLOSED in PR #41 cycle 4** — `_atomic_write` now uses `O_CREAT|O_EXCL|O_NOFOLLOW|fsync` matching the decision_writer/receipt_writer pattern.
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

**Default decision**: defer to v2.1. v2.0 ships with `pytest` + custom lint as the Python gates; the lefthook expansion (ruff + pytest + pyright + v2-handshake-lint pre-push) lands as part of the v2.1 contributor-experience bundle alongside BL-237. The v2.0.1 documentation refresh (BL-240/241/242/243) ships earlier as docs+hotfixes only.

#### BL-237 - v2.1.1: Tighten `V2_MODULES` scope to package-aware path-prefix matching

**Status (2026-05-09)**: SHIPPED in v2.1.1 — see PR #62 + commit `<SHA>`

**Status (2026-05-07)**: RE-TARGETED v2.1 → v2.1.1. Paired sibling of BL-236 in the original 2026-05-02 v2.1 scope rebalance (two contributor-experience BLs). Slipped through the same architecture-doc → master-plan handoff that lost BL-236. Re-targeting to v2.1.1 alongside BL-236 + BL-245 + BL-246 + BL-255..260.

**Driver**: Phase 7.5 pre-ship Python review surfaced a CI-lint coverage hole. `plugin-v2-handshake-lint.py:147-159` defines `V2_MODULES` as a frozenset of top-level basenames only (e.g., `decision_integrity.py`, `safe_run.py`, `cwd_state.py`). The `check_no_raw_subprocess` and `check_no_shell_true` rules iterate over this set, so they silently SKIP every `.py` file under `lp_pick_stack/`, `lp_scaffold_stack/`, and `plugin_stack_adapters/` — the bulk of v2.0's Python surface. Result: a future regression introducing `subprocess.run` or `shell=True` in any package module would not be flagged.

**Concrete instance the gap masks today**: `lp_scaffold_stack/nonce_ledger.py:152-184` (`_detect_filesystem_type` macOS branch) calls `subprocess.run(["/sbin/mount"], …)` directly. The module docstring documents this as a deliberate exception. Practically low-risk (fixed argv, no shell, no user-controlled input), but the call (a) bypasses `safe_run`'s env-allowlist (inherits ambient `PATH`/`TMPDIR`), and (b) is missed by the v2 lint per the scope hole above.

**Trade-off**: v2.0 ships without the fix because (a) the actual `subprocess.run` call is benign in shape, (b) the lint passes today (silently — that's the bug), and (c) tightening the scope mid-flight in Phase 7.5 was out of the strip-back-aware ship surface. Per the post-v2.0.0 ship rebalance (2026-05-02), this lint-config tweak ships in v2.1 as part of the contributor-experience bundle alongside BL-236 (lefthook Python coverage); the two share the same "small lint/CI config tweaks improving outside-contributor inner loop" framing.

**At v2.1 design time**:

1. Replace the `V2_MODULES` frozenset with a path-prefix matcher: any `.py` file under `plugins/launchpad/scripts/` (excluding `_vendor/` and `tests/`) is in scope by default.
2. Re-run `check_no_raw_subprocess` + `check_no_shell_true` against the broadened scope. Triage any new hits.
3. `nonce_ledger.py:_detect_filesystem_type` macOS branch: route through `safe_run` with explicit env-allowlist override for the `/sbin/mount` invocation, OR replace with `os.statvfs` + `posix.statvfs.f_fstype` if a Python release adds the field cross-platform, OR add to a small `LINT_RAW_SUBPROCESS_ALLOWLIST` constant that names this exact call site with a comment block citing the fixed-argv/no-shell rationale.
4. Add a CI-lint sub-rule asserting that any new entry to the allowlist requires a docstring + module-level comment explaining the deviation.
5. Closes: silent CI-lint coverage hole that would mask future regressions; the broad-scope `safe_run` mandate from HANDSHAKE §6 is now actually enforced everywhere it claims to be.

**Default decision**: defer to v2.1. The v2.0 ship is clean (the fixed-argv mount call is not exploitable at single-maintainer scale); the lint-tightening is the correct fix and lands as a small configuration adjustment in v2.1.

#### BL-245 - v2.1.1: Stack-aware `lefthook.yml` generation by `/lp-define` per-stack adapters

**Status (2026-05-09)**: SHIPPED in v2.1.1 — subsumed by universal lefthook + build-runner indirection (master plan D1); see PR #62 + commit `<SHA>`

**Status (2026-05-07)**: RE-TARGETED v2.1 → v2.1.1. Companion to BL-236 (LaunchPad self-host side) per the original BL-245 driver paragraph ("BL-236 fixes the upstream side; BL-245 fixes the downstream side"). Slipped from v2.1 alongside BL-236.

**Driver**: At v2.0, every project gets the same `lefthook.yml` whose hooks (`prettier-fix`, `eslint-fix`, `typecheck`, `structure-check`) are TS-monorepo-specific. v2.0 pipeline projects on Astro, Django, FastAPI, Rails, Hugo, Eleventy, Expo, Hono, Supabase, generic, and polyglot stacks inherit this TS-flavored `lefthook.yml` even though the hooks reference tools that aren't installed in those stacks (`prettier`, `eslint`, `tsc`). The kernel concept "every project ships a `lefthook.yml`" is sound, but its contents need to be stack-tuned for the gates to actually run.

**Relationship to BL-236**: BL-236 expands LaunchPad's OWN self-host `lefthook.yml` to gate Python plugin code (ruff + pytest + pyright + v2-handshake-lint pre-push). BL-245 makes `/lp-define`'s per-stack adapters generate stack-appropriate `lefthook.yml` for DOWNSTREAM v2.0 pipeline projects. They're complementary, not duplicative: BL-236 fixes the upstream side; BL-245 fixes the downstream side.

**Relationship to v2.0.1 docs**: README, HOW_IT_WORKS, and METHODOLOGY (after the v2.0.1 doc refresh) describe `lefthook.yml` as part of the universal kernel that ships with every project. The claim is conceptually true at v2.0 (the file exists), but until BL-245 ships, the contents are TS-tuned. Post-BL-245, the universal claim is structurally honest: every project gets a `lefthook.yml` whose contents match the stack's actual toolchain.

**At v2.1 design time**:

1. Each `plugin_stack_adapters/<stack>_adapter.py` emits a stack-appropriate `lefthook.yml` during `/lp-define` execution. Hook contents per stack:
   - `python_django` and `fastapi`: `ruff format`, `ruff check`, `pytest`, optional `pyright` or `mypy`
   - `next` and other TS-stacks: current `prettier-fix`, `eslint-fix`, `typecheck`, `structure-check` (no change)
   - `rails`: `rubocop`, `rspec`, optional `brakeman` security check
   - `hugo` and `eleventy`: `prettier-fix`, link-check, build dry-run
   - `astro`: `prettier-fix`, `eslint-fix`, `astro check`
   - `expo`: TS hooks plus `eas-cli` integrity checks
   - `hono`: TS hooks (smaller subset since Hono is server-only)
   - `supabase`: SQL formatter, migration validators
   - `generic`: minimal floor only, `trailing-whitespace` and `end-of-file-newline`
   - `polyglot`: composed by merging each layer's adapter output (de-duplicate identical hooks; namespace stack-specific hooks under `<stack>-` prefix when collisions arise)
2. Add a fixture-based test suite at `plugins/launchpad/scripts/tests/test_lefthook_generation_per_stack.py` validating each adapter emits a syntactically-valid `lefthook.yml` (parses via `yaml.safe_load`) that references the right tools per stack and contains no TS-only hook unless the stack is TS-based.
3. Verify the generated `lefthook.yml` aligns with the stack's `.launchpad/config.yml` `commands.test` / `typecheck` / `lint` arrays. The two artifacts should be derived from the same per-stack truth (likely a shared `<stack>_toolchain.yml` data file referenced by both the adapter and the lefthook generator) so they don't drift.
4. Update the structure-check script (`scripts/maintenance/check-repo-structure.sh`) to be stack-aware: `pnpm-workspace.yaml` and `turbo.json` are required-at-root for TS-monorepo only; `manage.py` is required-at-root for Django; etc. Currently the whitelist is TS-monorepo-shaped. Per-stack root whitelists pair naturally with per-stack lefthook.

**Out of scope** (intentional non-goals):

- **Migration of existing v2.0 projects**: BL-245 affects new projects only. Existing v2.0 projects continue with the TS-flavored `lefthook.yml` until the user manually re-runs `/lp-define` (which would prompt before overwriting).
- **Custom hook injection per project**: stack-aware generation produces a sensible default; users can hand-edit `lefthook.yml` after generation and `/lp-define` re-runs respect that (asks before overwriting per the existing overwrite menu).
- **Cross-stack hook sharing**: each stack's adapter is self-contained; we don't try to extract a common base across all 10 stacks. Polyglot composition handles the multi-stack case.

**Effort estimate**: ~6-8h adapter changes + ~3-4h test fixtures + ~1-2h structure-check stack-awareness + ~1h docs = ~12-15h total.

**Default decision**: ship in v2.1 alongside BL-236 (LaunchPad-side lefthook expansion) and BL-237 (V2_MODULES scope tightening). Shared theme: contributor-experience and stack-fidelity improvements. The v2.0.1 docs' "kernel applies universally" framing is structurally honest after BL-245 lands, since the universal claim is about file presence (true at v2.0) and stack-tuned contents (true after v2.1). Until then, the claim is conceptually accurate and operationally TS-only.

#### BL-246 - v2.2: `/lp-release [version]` command — automate the manual ship ceremony

**Status (2026-05-07)**: RE-TARGETED v2.1 → v2.1.1. v2.1.0 ship is using the manual runbook (tag → push → wait for verify-v2-ship → `gh release create`) inherited from v2.0.0. Automating into a `/lp-release` command was scoped for v2.1 but slipped through the architecture-doc → master-plan handoff. Manual ceremony is sound for v2.1.0; automation lands in v2.1.1.

**Driver**: v2.0.0 ship was a manual 3-step ceremony (tag → push → wait for `verify-v2-ship` → `gh release create --notes-file`). Documented as a runbook in v2.0.1 (BL-241 §6); v2.1 promotes the runbook to an executable command so LaunchPad and growth-toolkit (and any downstream LaunchPad-managed plugin/CLI/library/spec project) ship versioned releases with a single command instead of running the runbook by hand each time.

**Applicability — refuse-unless-applicable detection**: the command refuses cleanly if the project doesn't ship versioned releases. Detection: BOTH of the following must be present:

1. `docs/releases/` directory containing at least one `vX.Y.Z.md` file (per the LaunchPad/Keep-a-Changelog convention)
2. Either `.github/workflows/verify-*-ship.yml` OR `.github/workflows/release-notes-check.yml` (the post-tag verification gate)

If neither is present, exits with: `"this project doesn't ship versioned releases; /lp-release isn't applicable here. If you intend to start shipping releases, see HOW_IT_WORKS.md §Releasing a versioned artifact."`

The command is **NOT a fit for branch-triggered automation projects** (e.g., `ulcspec/ULC` uses `release/vX.Y.Z` branch + auto-tag-on-merge via goreleaser). Detection: if `release/*` branches exist in the project's recent history AND the project has a `release.yml` workflow that runs on `push: branches: [main]` with goreleaser invocation, surface a hint: `"this project appears to use the branch-triggered release pattern (release/vX.Y.Z branch → workflow auto-tags). /lp-release targets the manual ceremony pattern; you don't need it here."`

**Why v2.1 (not v2.2)**: post-v2.0 ship rebalance (2026-05-02) expanded v2.1 scope from "BL-236 + BL-237 contributor-experience pair" to include this maintainer-experience entry. Rationale: v2.0.1 ships in days; v2.1 ships within ~1 month after v2.0.0+24h soak; v2.2 is months out. Shipping `/lp-release` in v2.1 means LaunchPad benefits from the automation on every v2.x release after v2.1 lands (v2.2, v2.3, etc.). The command is bounded scope (~3-4h impl + ~2h tests + ~1h docs) and shares the v2.1 ergonomics theme alongside BL-236/BL-237.

**At v2.1 design time**:

1. Add `/lp-release [version]` slash command (or skill if Tier 2 fits better — evaluate during impl). Args:
   - `[version]` — optional; if omitted, derived from `CHANGELOG.md`'s `## [Unreleased]` section per semver rules (major if "Breaking changes" present; minor if "Added"; patch otherwise). User confirms before tagging.
   - `--signed` — optional; passes `-s` to `git tag` for GPG-signed annotated tags (off by default; BL-214 conditional).
   - `--dry-run` — optional; prints what would happen without executing tag/push/release.
2. Pre-flight checks:
   - Refuse-unless-applicable detection (above).
   - Verify HEAD is on `main` (or configured `release_branch` from `.launchpad/config.yml`).
   - Verify `git status` is clean (no uncommitted changes).
   - Verify CI is green on HEAD via `gh run list --branch main --status success --limit 1` (compare commit SHA to HEAD).
   - Verify `docs/releases/v<VERSION>.md` exists; if missing, exit with: `"docs/releases/v<VERSION>.md is required before tagging. Author the release notes file and re-run /lp-release."`.
   - Verify the version isn't already tagged: `git rev-parse v<VERSION>` returns nothing.
3. Execute (only after explicit user confirmation showing the planned actions):
   - `git tag -a v<VERSION> <merge-commit-sha> -m "v<VERSION>"` (annotated; signed if `--signed`)
   - `git push origin v<VERSION>` — triggers the verify workflow
4. Watch the verify workflow:
   - Poll `gh run list --workflow=verify-*-ship.yml --branch v<VERSION> --limit 1` every 10s up to 5min total.
   - On success: proceed to step 5.
   - On failure: print failure reason + recovery hint citing OPERATIONS §7.1 yank procedure (delete tag from origin, ship a fresh patch on next attempt). Do NOT attempt automatic rollback.
5. Create the release: `gh release create v<VERSION> --notes-file docs/releases/v<VERSION>.md --title "v<VERSION>"`. Print the release URL.
6. Closes: manual ceremony cost on every ship. v2.0.0 ship took ~5min of careful sequenced commands; v2.1+ ships should take ~30 seconds of `/lp-release` invocation + user confirmation.

**Out of scope** (intentional non-goals):

- **Auto-invoke from `/lp-build` or similar pipeline commands** — version bumps are an editorial decision, not a deterministic one. The command is user-driven only.
- **Auto-detect when to ship** — the command requires `[version]` arg (or unambiguous derivation from CHANGELOG). Doesn't try to be release-please / semantic-release.
- **Multi-tag ceremonies** (e.g., shipping v2.1.0 + v2.1.0-rc1 simultaneously) — out of scope for v2.1; revisit if real demand surfaces.
- **Branch-triggered automation pattern** (ULC-style) — `/lp-release` doesn't compete with goreleaser-on-merge workflows. The detection refuses cleanly with a hint.
- **Tag amendment / re-release** — if the verify workflow fails, the user follows OPERATIONS §7.1 manually. No automatic retry/rollback semantics in v2.1.

**Effort estimate**: ~3-4h command + ~2h tests + ~1h docs (HOW_IT_WORKS.md cross-reference + command frontmatter) = ~6-7h total.

**Default decision**: ship in v2.1 alongside BL-236/237 as the v2.1 maintainer-experience entry. v2.0.1 ships the runbook (BL-241 §6); v2.1 ships the automation wrapper.

#### BL-247 - v2.1: Remove deprecated template-clone infrastructure

**Status (2026-05-07)**: SHIPPED in v2.1.0 (Phase 8 mechanical decommission, commit `39ca5df`, 2026-05-06). Removed `init-project.sh`, the 8 `*.template.*` files at root, `pull-upstream.launchpad.sh`, `lp-pull-launchpad`, and `test_init_agents_yml.py`. REPOSITORY_STRUCTURE.md / CLAUDE.md / AGENTS.md whitelist entries updated.

**Driver**: v2.0 introduced the four-command greenfield pipeline (`/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define`) that supersedes the pre-v2.0 template-clone flow (`git clone github.com/builtform/launchpad my-project` + `./scripts/setup/init-project.sh`). v2.0.1 deprecates the template-clone flow in user-facing docs. v2.1 removes the supporting infrastructure now that BL-248 ships the plugin-owns-everything implementation that replaces it.

**Architectural decision context**: locked 2026-05-03 in [docs/plans/launchpad_plans/2026-05-03-v2.1-plugin-owns-everything-architecture.md](../plans/launchpad_plans/2026-05-03-v2.1-plugin-owns-everything-architecture.md). Per that plan, the LaunchPad repo stops doubling as plugin source AND user-cloneable template. Removing the infrastructure that supported the dual-purpose model is the structural enforcement of that decision; without removal, the template-clone flow remains accessible and the two-narrative problem persists.

**Sequencing constraint**: BL-247 must ship in the SAME release as BL-248 (Option 2 implementation). Deleting `init-project.sh` before the plugin can render kernel files would break greenfield setup mid-release. Build BL-248 first, then delete in BL-247, all within v2.1.

**At v2.1 design time**:

1. **Files to delete:**
   - `scripts/setup/init-project.sh` (1163 lines — wizard; reusable utilities extracted into `install-kernel-utils.sh` per BL-248 Group A solution)
   - `scripts/setup/pull-upstream.launchpad.sh` (delta-patch sync for template-cloned downstreams; obsolete with plugin-only flow)
   - `plugins/launchpad/commands/lp-pull-launchpad.md` (slash command wrapping the sync script; obsolete)
   - 8 root template files: `README.template.md`, `LICENSE.template`, `CONTRIBUTING.template.md`, `CODE_OF_CONDUCT.template.md`, `CHANGELOG.template.md`, `ROADMAP.template.md`, `SECURITY.template.md`, `greptile.template.json` (all absorbed into `plugins/launchpad/scripts/plugin-default-generators/<name>.j2` per BL-248)
   - `plugins/launchpad/scripts/tests/test_init_agents_yml.py` (tests the deleted wizard; becomes dead test)

2. **Files to update:**
   - `docs/architecture/REPOSITORY_STRUCTURE.md` §1: drop the 8 `.template.*` rows from the root whitelist; drop `init-project.sh` reference. §2 directory tree: drop `scripts/setup/init-project.sh` line. §6 decision tree: drop routing references for the deleted scripts.
   - `CLAUDE.md` codebase map: remove `scripts/setup/init-project.sh` reference.
   - `AGENTS.md`: same, plus any flow diagrams that mentioned the template path.
   - `.github/workflows/marketplace-lint.yml`: verify if still needed without template-clone; possibly delete or scope-narrow (separate decision).

3. **Migration documentation** in `docs/releases/v2.1.0.md`:
   - "Breaking change" callout: `init-project.sh` removed; template-clone replaced by plugin install + `/lp-brainstorm` pipeline
   - Migration section for v1.x template-clone users (their canonical files keep working; `/lp-pull-launchpad` no longer exists; `git fetch launchpad && git merge` for manual scaffold updates if desired; manual copy from the plugin's bundled template directory for individual kernel-file refresh)

4. **Verification commands** (run after deletion to spot-check completeness):
   ```
   rg -n "init-project\.sh|pull-upstream\.launchpad\.sh|/lp-pull-launchpad" -g '!docs/releases/' -g '!CHANGELOG.md'
   ls *.template.* LICENSE.template 2>/dev/null  # should be empty
   ls scripts/setup/init-project.sh scripts/setup/pull-upstream.launchpad.sh plugins/launchpad/commands/lp-pull-launchpad.md 2>/dev/null  # should be empty
   ```

**Effort estimate**: ~4h (deletion + REPOSITORY_STRUCTURE/CLAUDE/AGENTS updates + verification). Migration docs absorbed into Phase 9 release notes. See v2.1 implementation plan §17 Phase 8 + §20 for current scope.

**Cross-link**: full v2.1 implementation plan at [docs/plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md](../plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md) (V3, post-Round-3-hardening). Phase 8 is the BL-247 execution phase.

**Default decision**: ship in v2.1 alongside BL-248 (mandatory same-release coupling). v2.0.1 has been folded into v2.1 per Decision 24; no v2.0.1 release.

#### BL-248 - v2.1: Implement plugin-owns-everything architecture (Option 2)

**Status (2026-05-07)**: SHIPPED in v2.1.0. The entire v2.1 release IS this BL (sealed identity contract under `schema_version: "1.1"`, `/lp-bootstrap`, `/lp-update-identity`, kernel renderer, render-batch flow with secret-scanner gate, stack-aware dispatch, composition wrapper, brownfield-safe re-runs). Phases 0-11 of the v2.1 implementation plan all rolled up under this BL. CHANGELOG `[2.1.0]` Added/Changed sections describe the user-visible surface.

**Driver**: v2.0 shipped the four-command greenfield pipeline. v2.0.1 deprecated the legacy template-clone flow in docs. v2.1 implements the plugin-owns-everything architecture that makes the deprecation real: all canonical kernel files (README, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, CHANGELOG, ROADMAP, SECURITY, REPOSITORY_STRUCTURE) plus all architecture docs are rendered by plugin commands using Jinja2 templates bundled inside the plugin. No `init-project.sh`, no `.template.md` files at root, no dual-purpose repo.

**Architectural decision context**: locked 2026-05-03 in [docs/plans/launchpad_plans/2026-05-03-v2.1-plugin-owns-everything-architecture.md](../plans/launchpad_plans/2026-05-03-v2.1-plugin-owns-everything-architecture.md). Read that document end-to-end before authoring the implementation plan. It captures: full evaluation of Option 2 vs. Option 3 (hybrid) with cons + solutions grouped, responsibility split across pick-stack/scaffold-stack/define, template format conversion strategy, identity value flow with chain-of-custody integration, orchestrated-init bash utility extraction, decommissioning plan (BL-247), migration guidance, and 6 open questions to resolve at design time.

**Responsibility split** (locked):

- `/lp-pick-stack` adds 5 identity questions (project name, description, license type, copyright holder, contact email) sealed into `scaffold-decision.json`'s new `identity` block. Existing 5-question stack funnel preserved.
- `/lp-scaffold-stack` adds canonical kernel file rendering (8 templates) using sealed identity values via Jinja2. Existing layer materialization, `lefthook.yml` emission, receipt sealing all preserved.
- `/lp-define` adds one new responsibility: render `REPOSITORY_STRUCTURE.md` for brownfield projects when missing (load-bearing for the structure-drift gate). Reuses the same `.j2` template `/lp-scaffold-stack` uses; identity values prompted directly in brownfield (no sealed envelope). The other 7 user-customized kernel files (README/LICENSE/CONTRIBUTING/CODE_OF_CONDUCT/CHANGELOG/ROADMAP/SECURITY) stay user-owned in brownfield. Existing `/lp-define` scope (architecture docs + agents.yml + config.yml + Tier 1 reveal panel) preserved.

**Scope evolved through 3 hardening rounds + 24 locked decisions**. Final v2.1 scope per [docs/plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md](../plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md):

- **5-command-surface**: 4 main pipeline commands (`/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define`) plus 2 utility commands (`/lp-bootstrap`, `/lp-update-identity`). 33 paths / ~45 files rendered across 3 categories: kernel (greenfield-only via `/lp-scaffold-stack`), infrastructure (greenfield + brownfield via `/lp-bootstrap`), workflow-config (both via `/lp-define`).
- **5 adapters + composition wrapper**: `ts_monorepo`, `nextjs_standalone` (wrap-and-overlay over `vercel/next-forge`), `nextjs_fastapi` (wrap-and-overlay over `vintasoftware/nextjs-fastapi-template`), `astro` (wrap-and-overlay over 3 sub-templates), `generic` (typed fallback). Composition wrapper supports N=2 adapter compositions in a Turborepo (e.g., `astro + nextjs_standalone` for ulc.spec.org).
- **Schema bump 1.0 → 1.1** with sealed identity block + canonical reader + CODEOWNERS gate.
- **Bootstrap manifest** at `.launchpad/bootstrap-manifest.json` with sha256-based idempotency + manifest-tampering integrity check + per-file conflict policy + atomic writes + backup-with-PID.
- **Trust model + supply-chain pinning** + plugin pinning recommendation + CVE rotation policy + upstream abandonment fallback.

**Coordination**: BL-247 must ship in same release (BL-248 builds replacement, BL-247 deletes legacy). BL-245/236/237/246 ship independently.

**Effort estimate**: 127-159h structured / 159-199h with buffer. 12 phases (Phase 0 + Phase 1-11). Two phase-boundary kill checkpoints at end of Phase 3 and after first non-reference adapter. v2.0.1 has been folded into v2.1 per Decision 24; no v2.0.1 release.

**Default decision**: ship in v2.1 as the architecture-defining entry. Read [V3 implementation plan](../plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md) for full design + 24 locked decisions + 12-phase sequencing + test strategy.

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

#### BL-250 - v2.2: Bring-your-own scaffolder mode (cookiecutter / degit / npm-create URL acceptance)

**Driver**: v2.1 ships 4 curated wrap-and-overlay adapters (`ts_monorepo`, `nextjs_standalone` over `vercel/next-forge`, `nextjs_fastapi` over `vintasoftware/nextjs-fastapi-template`, `astro` over 3 sub-templates). Once the wrap-and-overlay PATTERN is validated in v2.1, expanding adapter coverage from 4 hand-picked upstreams to "any cookiecutter / degit / npm-create URL the user provides" is structurally cheap. v2.2 unlocks the long tail of community templates without per-adapter LaunchPad maintenance burden. Builds directly on v2.1's wrap-and-overlay pattern.

**At v2.2 design time**:

1. **Curated registry** of vetted cookiecutter URLs covering v2.2 candidate stacks: `cookiecutter-django` (Django full-stack; replaces v2.1's `python_django` route-to-generic), `cookiecutter-fastapi` variants (`python_generic` route-to-generic). Registry lives at `plugins/launchpad/scripts/plugin_stack_adapters/_byo_registry.py` with sha-pinned entries.
2. **Generic URL acceptance** for power users: `/lp-pick-stack` accepts `--scaffolder-url <url>` flag; LaunchPad invokes (a) `cookiecutter <url>`, (b) `degit <github-shorthand>`, or (c) `npm create <package>` based on URL detection.
3. **Overlay-config inferred or prompted-for**: registered URLs come with pre-authored OverlayConfig (per v2.1 §13.1); generic URLs prompt user for overlay decisions or fall back to default `OverlayConfig` (skip-if-exists for everything user-side, render LaunchPad infrastructure overlay only).
4. **Trust model**: BYO mode requires user explicit `--i-trust-this-url` flag (or interactive confirmation) since URL is user-supplied; cache hardening (sha256 verification, atomic writes) reused from v2.1 §7.7.

**Coverage estimate at v2.2**: 5 v2.1 adapters + 5+ BYO-registered cookiecutter adapters (django, fastapi-flavors, rails via cookiecutter-rails-hotwire, etc.) + power-user generic URL = ~85-92% of niche projects.

**Cross-link**: builds on v2.1 wrap-and-overlay pattern locked in [docs/plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md](../plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md) §7. v2.2 design plan to be authored when this entry is picked up.

**Default decision**: ship in v2.2. Cheap relative to authoring per-adapter from scratch (estimated ~15-25h vs 8-12h per non-BYO adapter). Prerequisite: v2.1 ships and wrap-and-overlay pattern proves stable in production (the `ulc.spec.org` Tier-2 dogfood is the validation gate).

#### BL-251 - v2.2: Phase 1+2 retroactive Tier B residuals bundle

**Driver**: 2026-05-06 retroactive `--full` /lp-harden-plan against shipped Phase 1 + Phase 2 (HEADs `d14f1a4` + `4fe969f`) surfaced ~16-18 P1 across 26 review agents. Triaged into Tier A (amend now, 9 items, shipped at HEADs `dc9dc08` + `c39eaf0`) + Tier B (defer to v2.2, ~10 items captured here).

**Tier B items** (none ship-blocking; ranked by reviewer-confidence + practical impact):

1. **Email regex "RFC5322-lite" doc clarification** (cosmetic): `IDENTITY_EMAIL_RE` is documented as RFC5322-compliant but is actually a permissive subset. Update HANDSHAKE §10.v2.1 to call it "RFC5322-lite" and enumerate the rejected forms (e.g., quoted local-parts, IP-literal hosts).
2. **`/lp-pick-stack.md` "5 questions" vs 6 prompts numbering** (cosmetic display): step header says "5 questions" but Step 1.5 emits 6 identity prompts. Reconcile to "6 questions" in command spec.
3. **CODEOWNERS gate advisory-only on free-tier GitHub** (existing reality): document in SECURITY.md that CODEOWNERS-based schema-source review is enforced only on Pro/Enterprise repos; free-tier repos must pair with branch-protection rules to enforce. Doc-only.
4. **Identity reader-allowlist enforced by handshake-lint** (architecture-scale, ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS-style): introduce `IDENTITY_READER_ALLOWED_CALLERS` allowlist; add lint rule that `validate_identity()` callers are restricted to declared modules. Defense-in-depth against unscoped identity reads.
5. **`infrastructure/` + `workflow-config/` skeleton dirs in Phase 2** (verify Phase 3 created them, otherwise add): low-priority structural cleanup; current shipped state may already have these via Phase 3 orchestrated-init utilities.
6. **Identity context filter discipline** (per-template lint): assert that all `{{ identity.* }}` references in non-Markdown templates use `| tojson` (for JSON contexts) or `| shell_quote` (for shell contexts). Companion to Tier A6 `markdown_safe` filter.
7. **§17.1 vs §13.6 feature count mismatch in V3 plan** (cosmetic): V3 plan is gitignored; reconciliation is plan-author-only. No shipped artifact impact.
8. **TOCTOU in `KernelRenderer.refresh()`** (theoretical): mitigated by `atomic_write_replace` + Phase 10 sentinel; document the mitigation in HANDSHAKE §10.v2.1 for completeness.
9. **`IDENTITY_REPO_URL_RE` permits http:// + RFC1918 hosts**: only matters if downstream fetches the URL server-side. v2.1 does not; v2.2 BYO-scaffolder mode (BL-250) might. Tighten regex when BL-250 design lands.
10. **`advisory_flock` no timeout** (theoretical wedge): LOCK_NB poll loop with bounded retries would prevent stuck-lock scenarios on `/lp-define` concurrent runs. v2.1 ships single-session-correct; v2.2 multi-session adds the timeout.

**Cross-link**: full Tier A/B audit synthesis in `.harness/handoff-tier-a-bundle.md` (gitignored runtime path; sibling-session implementation prompt). Phase 1+2 retroactive amendments shipped at HEADs `dc9dc08` (8 fixes + DIP cleanup) + `c39eaf0` (HANDSHAKE schema doc).

**Default decision**: defer to v2.2. None of these are ship-blocking; cumulative effort estimated ~6-10h. Schedule alongside v2.2 operational/security infrastructure bundle.

#### BL-252 - v2.2: Phase 11 deferred manifest tampering scenarios

**Driver**: Phase 11 LOCKED v3 plan (2026-05-06) shipped `test_bootstrap_manifest_tampering.py` with 11 scenarios (existing 9 from Phase 3 Slice C + 2 augments per Phase 11 DA3: SymlinkSubstitution + TOCTOU). Cycle 1 + cycle 2 review surfaced 4 additional attack scenarios that did not make the v2.1 ship cut.

**Scenarios to add at v2.2**:

1. **NullByteInjection**: `..\x00..` style path encoding bypasses string `..` checks. Requires path-validation hardening that uses byte-level parsing not string-prefix.
2. **UnicodeNormalizationAttack**: homoglyph in identity field that NFC-normalizes to a different value post-validation. Requires NFKC normalization at validation time + post-normalization re-check.
3. **ZIP-bomb / oversized-manifest payloads**: pathologically-large or recursively-compressed manifest payloads. Requires manifest size cap (e.g., 1MB hard limit) + early-reject before parse.
4. **Concurrent-modification race during manifest read**: file mutated between `manifest_sha256` verify and consume by a concurrent `/lp-update-identity` or external editor. Requires either OS-level file lock during read OR re-hash on consume (already partial in TOCTOU augment).

**Cross-link**: Phase 11 plan `docs/plans/launchpad_plans/2026-05-06-v2.1-phase11-implementation-plan.md` §3.3 (DA3 augment scope + deferral list) + §8 (out-of-scope row). v2.0 baseline at PR #41 cycle-12 closed similar scenarios at the security_fields layer; v2.2 extends to manifest-payload layer.

**Default decision**: defer to v2.2. v2.1 ships with 11 scenarios + 7 attack-class coverage; remaining 4 are exotic edge cases. Cumulative effort estimated ~3-5h.

#### BL-253 - v2.2: Brainstorm Python runner extraction (E2E coverage from brainstorm step)

**Driver**: Phase 11 LOCKED v3 plan (2026-05-06) DA1 + R2 acknowledge that `/lp-brainstorm` is slash-command-only and has no Python runner. The v2.1 E2E test (`test_v21_full_greenfield_pipeline.py`) starts at `pick_stack` and skips brainstorm coverage. v2.0 baseline (PR #41) had the same gap; v2.1 inherits it.

**At v2.2 design time**:

1. Extract brainstorm prompt-construction + response-parsing logic from `plugins/launchpad/commands/lp-brainstorm.md` into `plugins/launchpad/scripts/lp_brainstorm/engine.py` with `run_brainstorm(...)` entry point.
2. Slash command becomes a thin adapter that invokes the runner with prompt context.
3. Phase 11 E2E test is extended (or new `test_v22_full_pipeline_with_brainstorm.py`) to cover brainstorm → pick-stack → scaffold-stack → define.
4. Consider whether brainstorm needs its own `BrainstormResult` dataclass or whether the existing `pick_stack` input dict shape covers it.

**Cross-link**: Phase 11 plan `docs/plans/launchpad_plans/2026-05-06-v2.1-phase11-implementation-plan.md` §3.1 DA1 + §6 R2.

**Default decision**: defer to v2.2. v2.1 ships with documented coverage gap; brainstorm runtime is LLM-dependent so testing gain is modest. Schedule when telemetry justifies (high brainstorm-step bug rate).

#### BL-254 - v2.2: Promote pip-audit + osv-scanner from advisory to required gates

**Driver**: Phase 11 LOCKED v3 plan (2026-05-06) Slice E step 9 captures `pip-audit` + `osv-scanner` output as advisory (non-blocking). Cycle 1 security F8 flagged this as A06 Vulnerable Components risk: a known-CVE dependency could ship if reviewer ignores the advisory output. v2.1 keeps advisory mode for tooling-availability reasons; v2.2 should harden.

**At v2.2 design time**:

1. Add `pip-audit -r requirements.txt` to `verify-v2-ship` GitHub Action as a required step.
2. Add `osv-scanner --recursive plugins/launchpad/scripts/` to `verify-v2-ship` as a required step.
3. Adapter pin sweep (BL-100/BL-101/BL-102/BL-103/BL-104 v2.2 stack restorations): assert all adapter SHA pins resolve to OSV-clean upstream commits.
4. Document allowlist mechanism for accepted-risk CVEs (e.g., transitive vulnerable dep with no exploit path).
5. Update SECURITY.md to declare the supply-chain-audit posture.

**Cross-link**: Phase 11 plan `docs/plans/launchpad_plans/2026-05-06-v2.1-phase11-implementation-plan.md` §8 row 4 + Slice E step 9 + cycle 1 security F8.

**Default decision**: defer to v2.2. v2.1 ships advisory-only output captured in `/tmp/v2.1.0-*.log`; v2.2 gates promotion alongside the operational/security infrastructure bundle.

<!-- v2.1.1 patch lane (created 2026-05-06 during the final cross-cutting hardening pass over `c563d81..HEAD`). The 14-agent review surfaced ~25 P2 / P3 items that did not block v2.1.0 ship but should land as a fast-follow patch within 7-14 days of v2.1.0. v2.1.1 is the dedicated patch home; v2.2 stays for operational/security infrastructure + stack catalog restorations. Items added empirically as real-world v2.1 use surfaces them. -->

#### BL-255 - v2.1.4: Sentinel + identity-write security hardening bundle

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Driver**: 2026-05-06 cross-cutting hardening pass surfaced 5 sentinel/identity-write defenses that are currently asymmetric or incomplete. Tier A (this hardening cycle) wired the missing scaffold-stack sentinel write-side and harmonized bootstrap to `O_CREAT|O_EXCL`; the remaining items are non-blocking but should land in v2.1.1 to close the defense surface fully.

**Items**:

1. **Case B legacy-migration bypasses Case D email cross-check.** A planted legacy `schema_version: "1.0"` envelope routes through `lp_update_identity` Case B (seed-as-first-time after migration) without the Case D `git config user.email` cross-check. Hoist the email cross-check to fire on raw read of legacy envelopes BEFORE migration so PR-based identity-forgery via planted-stub-legacy-envelope is closed for all entry paths. File: `lp_update_identity/engine.py:511-566`. Adds `LEGACY_IDENTITY_FORGERY_SUSPECTED` exit-65 reason.
2. **`/lp-update-identity` does not acquire `.bootstrap.lock` advisory flock.** `/lp-bootstrap` takes the lock to serialize preflight + sentinel-write; `/lp-update-identity` performs the same 3-step sequence without the lock so two concurrent commands can both pass cross-detect. Wrap `run_update_identity` body in `with advisory_flock(cwd / LAUNCHPAD_DIR_NAME / ".bootstrap.lock"):` to share the lock domain. Same fix for `/lp-scaffold-stack` engine. File: `lp_update_identity/engine.py:471-737` + `lp_scaffold_stack/engine.py:run_pipeline`.
3. **`_sentinel_preflight` ImportError fail-open.** Both bootstrap and update-identity catch `ImportError` on the sibling sentinel modules and `pass` silently, downgrading cross-detect to one-way. Replace with hard `BootstrapEngineError(SENTINEL_BLOCKING)` so a packaging regression surfaces immediately. File: `lp_bootstrap/engine.py:354-395` + `lp_update_identity/engine.py:220-260`.
4. **`atomic_write_excl` allowlist mirror.** Phase 8.5 added an ALLOWLIST + AST + import-binding lint for `atomic_write_replace` callers but `atomic_write_excl` (used by all 3 sentinel writers) has no equivalent. Future contributors adding a 4th sentinel sit outside the cross-detect topology silently. Add `ATOMIC_WRITE_EXCL_ALLOWED_CALLERS` to `plugin-v2-handshake-lint.py` mirroring the existing allowlist mechanism.
5. **`--allow-email-mismatch` audit-log entry missing.** Override flag silences the email cross-check refusal but records nothing in `version_drift_log`. Forensic review cannot distinguish a legitimate override from a compromise. Append `{override: "allow_email_mismatch", actor_email: <raw>, applied_at: <iso>}` to `version_drift_log` whenever the flag is used. File: `lp_update_identity/engine.py:561-685`.

**Cross-link**: Wave 1 security-auditor P2 + adversarial S-1; Wave 1 frontend-races P2-1/2/3; security-lens S-3/S-4/S-8. Synthesis in `.harness/handoff-tier-b-bundle.md` (gitignored runtime path).

**Effort estimate**: ~6-10h cumulative across the 5 items.

**Default decision**: defer to v2.1.1. v2.1.0 already converges defenses for the common-case attack vectors (atomic-write sentinel acquisition + bidirectional cross-detect after Tier A); items 1-5 close the long tail.

#### BL-256 - v2.1.4: Doc-vs-code coherence patch bundle

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Driver**: 2026-05-06 cross-cutting hardening pass surfaced ~12 documentation-vs-code drift items. Tier A locked the highest-impact P1s (re-entry case framing, license enum, Phase 1 in release notes, --force phantom flag, v1.0.0 stale strings, refusal hint). The Tier B residuals are individually small but worth bundling into a single doc-patch PR to ship clean.

**Items**:

1. **HANDSHAKE §4 documents `/lp-scaffold-stack` plugin_version abort that doesn't exist in code.** Either add a `plugin_version` pin check to `lp_scaffold_stack/decision_validator.py` mirroring `_check_plugin_version_pin` in lp_bootstrap, OR update HANDSHAKE §4 lines 466-469 to read "`/lp-bootstrap` aborts ...; `/lp-scaffold-stack` does NOT validate `plugin_version` — the manifest hash is re-checked at bootstrap time." Recommendation: doc fix is cheaper and matches Phase 1+2-A8 intent.
2. **`lp_update_identity/engine.py` missing from `SCHEMA_SOURCE_FILES` + CODEOWNERS.** This is the file containing the 1.0 → 1.1 schema migration but is not gated by the schema-CODEOWNERS rule. Add to both: `.github/CODEOWNERS` (after the existing 8 schema-source entries) and `plugin-v2-handshake-lint.py` `SCHEMA_SOURCE_FILES`.
3. **v2.1 fixture `sha256` self-consistency test.** `tests/fixtures/v2_0_baseline_manifests/v2_1_scaffold_decision.json` carries a hard-coded `sha256` field; no test asserts it equals `canonical_hash(payload − sha256)`. Add `test_v2_1_fixture_canonical_hash_self_consistent` in `test_cross_version_interop.py`. Same assertion for the v2.0 fixture.
4. **`validate_identity` strict-mode field-set docstring.** Strict mode is documented as rejecting placeholder shapes universally but actually checks only 4 of 7 PII fields. Tighten the docstring at `lp_pick_stack/decision_writer.py:202-340` to enumerate the 4 fields actually checked.
5. **`re_seal_decision_atomic` silently restores `generated_at`.** Phase 10 DA9 docstring claims byte-identity assertion; implementation silently overwrites caller-mutated `generated_at`. Either rename the docstring claim to "preserve" OR change to `raise ValueError` so caller bugs surface. File: `lp_pick_stack/decision_writer.py:507-516`.
6. **plugin.json keywords cleanup.** `keywords` array lists `go`, `django` which are not v2.1 active stacks (they are v2.2-candidate). Drop or relabel.
7. **Active-stacks vocabulary.** Release notes line 11 says "5 active stack ids"; HOW_IT_WORKS.md:79 lists 10 stacks (the v2.0 catalog naming). Add a glossary line clarifying that "5 active composition stack ids" ≠ "10 v2.0 scaffold catalog entries", or unify the vocabulary across docs.
8. **BL-247 decommission missing from CHANGELOG/release notes Removed section.** README.md:69 + HOW_IT_WORKS.md:63 mention the `init-project.sh` + 7 `*.template.*` decommission but neither CHANGELOG `[2.1.0]` nor release notes have a "Removed" subsection. Add one.
9. **README "12 plugin-test suites" count.** Verify against current test-suite count (Phase 11 ship is 1198 collected across 36+ test files). Update or remove the precise number.
10. **README Path 2 enumeration.** Path 2 description at README.md:61 mentions "package.json, lefthook.yml, the architecture docs" but does not mention the 7 kernel renders. Append "+ LICENSE/CONTRIBUTING/CODE_OF_CONDUCT/SECURITY/README/AGENTS/CLAUDE."
11. **"v2.0 pipeline" vs "v2.x pipeline" vocabulary lock.** Release notes commit to "v2.0 behavior end-to-end" so "v2.0 pipeline" is canonical; HOW_IT_WORKS.md:5 and other locations mix "v2.x". Lock to "v2.0 pipeline".
12. **IDENTITY_AND_PII.md PII default-posture section.** Doc starts at "what persists" but never states that PII opt-out is the default. Add a "Default posture" §1.

**Effort estimate**: ~3-5h cumulative as a single bundled doc-patch PR.

**Default decision**: defer to v2.1.1. None of the items break user flows in v2.1.0; the bundle is a quality polish.

#### BL-257 - v2.2: Perf optimizations + test infrastructure polish

**Driver**: 2026-05-06 cross-cutting hardening pass surfaced 6 perf items + 3 test-infrastructure items. None breach existing budgets at v2.1.0 (1198 tests in 54.76s under 90s budget — 39% headroom), but the optimizations are real cycle reductions and the test-infra fixes address documented flakiness.

**Perf items**:

1. **KernelRenderer triple-sha amplification.** `refresh()` and `render_all()` both compute `(disk_sha, template_sha)` in the inner loop and then re-compute the same shas in the post-write state-emit loop. Cache into a dict and reuse. ~10-line diff at `kernel_renderer.py:225-270`. Saves 14 redundant disk reads + 14 sha256 ops per refresh.
2. **`re_seal_decision_atomic` 2x call per `/lp-update-identity` refresh.** Phase 1+2-A7 inversion split the seal into two atomic-write cycles (identity + kernel_render_state). Combine into a single `update_fn` closure for one read-modify-write cycle. ~20-line diff at `lp_update_identity/engine.py:689,714`. Saves one `atomic_write_replace` + one `F_FULLFSYNC` (5-50ms on macOS) per refresh.
3. **Phase 11 atomic-write allowlist sweep duplicates Phase 8.5 lint AST work at runtime.** `test_atomic_writes_allowlist_sweep.py` re-parses `plugins/launchpad/scripts/**/*.py` on every pytest invocation (~200-400ms). Hoist `_load_lint_constants()` and the AST scan into a session-scoped fixture so they pay once per session.
4. **`_load_agent_index` LRU + `_last_dropped` per-call clear.** Bound `lru_cache(maxsize=None)` to `maxsize=4` and clear `_last_dropped` at the start of every `filter_agents_by_stacks` call. File: `plugin-agent-scope-filter.py:73-75,152-197`.

**Test infrastructure items**:

5. **pytest-xdist `@pytest.mark.serial` for 2 perf tests.** `test_cold_fill_thousand_files_under_three_seconds` (3s budget) and `test_write_batch_perf_under_300ms_30file_scaffold` (300ms budget) fail under `-n auto` due to CPU contention. Phase 11 reconciliation #1 documents this; v2.1.0 ships verified via plain pytest. Add `@pytest.mark.serial` decorator + xdist `loadgroup` config so DoD runs cleanly under `-n auto`.
6. **gitleaks `.gitleaks.toml` allowlist for test fixtures.** Phase 11 reconciliation #4 documents 5 false positives in `test_phase8_5_decommission.py` (intentional `AKIA*` placeholders). Add `.gitleaks.toml` allowlist scoped to `**/test_phase8_5_decommission.py` so the leakage audit can be promoted from advisory to required without false-positive noise.
7. **`check_legacy_yaml_canonical_hash_removal` smoke test.** BL-210 gate (now retargeted to v2.2 per Phase 11 hardening A5) is currently uncovered by any test. Add a smoke test that invokes the gate against synthetic plugin.json at versions 2.1.99 (gate inactive) and 2.2.0 (gate active) so the gate's regression is caught when it eventually fires.

**Effort estimate**: ~4-6h cumulative across all 7 items. Items 1-2 require care (caller cooperation); items 3-7 are mechanical.

**Default decision**: defer to v2.1.1. Perf headroom is sufficient at v2.1.0 ship; the optimizations are tightening opportunities, not blockers.

#### BL-258 - v2.2: Tag-signing posture promotion (was v2.2 BL-214)

**Driver**: SECURITY.md "Tags before v2.2 are unsigned" creates a 6+ month maintainer-trust window. The 2026-05-06 cross-cutting hardening pass adversarial-lens flagged this as the longest-lived security gap in the v2.1 ship surface. The mitigation is a 30-minute change (RELEASE_PROCESS.md update + maintainer guidance to enable `tag.gpgSign = true`); the signing infrastructure itself (Sigstore + transparency log per the original BL-214 scope) can stay on v2.2.

**At v2.1.1 design time**:

1. Update `docs/maintainers/RELEASE_PROCESS.md`: maintainers MUST `git tag -s` v2.1.1+ tags. Document the GPG key rotation policy + which keys are valid for v2.1 release-track tags.
2. Update `SECURITY.md:19`: replace "Tags before v2.2 are unsigned" with "Tags before v2.1.1 are unsigned. Starting at v2.1.1, all release-track tags are GPG-signed by maintainers listed in `docs/maintainers/RELEASE_PROCESS.md`."
3. Add a CI step in `verify-v2-ship.yml` that runs `git tag -v <tag>` and fails the workflow if the tag is unsigned, gated on tag versions >= "2.1.1".
4. v2.2 BL-214 stays open for the broader Sigstore + transparency-log work (out-of-band verification path that doesn't depend on GitHub repo write access alone).

**Cross-link**: cross-cutting hardening adversarial F6 + security-lens S-7. Originally captured as v2.2 BL-214; promoted to v2.1.1 because the marketplace-install threat surface is wide enough to warrant the early move.

**Effort estimate**: ~30-60 min across the 4 sub-items.

**Default decision**: defer to v2.1.1. v2.1.0 ships unsigned per the documented posture; v2.1.1 closes the gap before any sustained v2.1.x usage period.

#### BL-259 - v2.2: Codex PR #50 deferred findings (docstring + backup-dir + shell word-split)

**Driver**: 2026-05-06 Codex automated review on PR #50 surfaced 5 findings; 2 P1 items were fixed in-PR (allowlist-aware early gate at `lp_define_runner.py` + reseal-after-refresh ordering at `lp_update_identity/engine.py`). The remaining 3 items are deferred:

1. **(was Codex P1, demoted to P2)** `plugins/launchpad/scripts/plugin_default_generators/_renderer_base.py:526` — `write_batch()` docstring claims "atomically write batch" but post-scan writes are sequential per-file via `atomic_write_replace()`. The docstring's "atomic-batch-or-none invariant" refers to the scan→write transition, not cross-file rollback. Actual behavior matches the v2.0 sequential write pattern with no observed regression. Fix is a docstring clarification (downgrade contract to "per-file atomic; no cross-file rollback after scan passes") OR a 2-phase commit refactor (preflight all parents → write temp files → batch-rename with rollback). Default: docstring clarification; refactor only if a real partial-write incident materializes.

2. **(Codex P2)** `plugins/launchpad/scripts/lp_update_identity/engine.py:465` — `_ensure_backup_dir()` builds the directory name from second-resolution timestamp + PID + `exist_ok=True`, so two `/lp-update-identity` invocations from the same process within one second can reuse the same backup directory and overwrite the prior `scaffold-decision.json` backup. Use the existing random-suffix + `exist_ok=False` pattern from `lp_bootstrap.policy.make_backup_dir()`.

3. **(Codex P3)** `plugins/launchpad/scripts/plugin_default_generators/infrastructure/scripts/compound/analyze-report.sh.j2:78` — `for prd in $RECENT_PRDS` splits `find` output on whitespace. PRD paths containing spaces are misread. Fix: use `find ... -print0` with a `while IFS= read -r -d ''` NUL-delimited loop.

**Effort estimate**: ~30-45 min total (~10 min docstring, ~15 min backup-dir, ~10-20 min shell rewrite).

**Default decision**: defer to v2.1.1. None of the three are runtime-hot at v2.1.0 ship time; the docstring is over-specifying a property the implementation doesn't promise, the backup-dir collision requires same-process sub-second reinvocation (no current command path triggers this), and the shell word-split only fires when a downstream operator runs `compound/analyze-report.sh` against a path containing spaces.

#### BL-260 - v2.1.4: Cross-command sentinel TOCTOU race + catalog-vs-active-enum integration polish

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Driver**: Codex re-review on PR #50 (post-2dbf839 commit) flagged a check-then-write race between `/lp-bootstrap`, `/lp-scaffold-stack`, and `/lp-update-identity` sentinels, plus Greptile noted that v2.0 catalog short names like `supabase`, `expo`, `eleventy`, `hugo` can be picked from `/lp-pick-stack`'s manual-override menu but are not members of `STACK_ID_ACTIVE_ENUM` — leading to a `ValueError` at `/lp-review` time when those ids are persisted in `scaffold-decision.json.stacks`. Both items are real but neither blocks v2.1.0 ship: the sentinel race window is microseconds in a single-user CLI, and the catalog-vs-active-enum mismatch fails at `/lp-scaffold-stack` time with a clear "unknown_v21_stack_id" error rather than silently breaking review.

**At v2.1.1 design time**:

1. **Cross-command sentinel race** — Implement a single `.launchpad/.operation-lock` flock acquired by all three commands (`lp_bootstrap.engine`, `lp_scaffold_stack.engine`, `lp_update_identity.engine`) BEFORE any peer-sentinel check. The lock is held for the duration of the check + own-write sequence and released via the existing `try/finally` sentinel-clear path. Alternative considered: re-check peer sentinels after own-write succeeds (works but allows mutually-aborting "both lose" deadlock-like patterns under extreme luck). Locked path: shared lock, since it composes better with future commands joining the family.
2. **Catalog-vs-active-enum integration** — Either (a) filter the `/lp-pick-stack` manual-override catalog to only present ids in `STACK_ID_ACTIVE_ENUM` ∪ `StackIdV22Candidate` (10 ids, hides supabase/expo/eleventy/hugo), or (b) add a resolution step in `manual_override_resolver.resolve_manual()` that maps catalog short names like `supabase` → `generic`, `expo` → `generic`, etc. before persistence. Path (b) preserves the v2.0 catalog UX; path (a) is simpler but narrows the picker. Pick path (b) at v2.1.1 design time so existing Astro/Hugo/Eleventy/Expo users aren't hit by a regression.
3. Add regression tests asserting (1) two simultaneous slash-command invocations cannot both write peer sentinels even when timing is adversarial (use `multiprocessing.Barrier` to coordinate the race window), and (2) every catalog short-name from the v2.0 14-id `StackId` Literal resolves to a member of `STACK_ID_ACTIVE_ENUM` after `manual_override_resolver.resolve_manual()` runs.

**Cross-link**: Codex PR #50 P1-C (cross-command race) + Greptile PR #50 catalog-vs-active-enum side-band concern.

**Effort estimate**: ~2-3h across the lock implementation + catalog mapping + tests.

**Default decision**: defer to v2.1.1. The race is theoretical; the catalog mismatch fails at scaffold-stack time with a clear error rather than silently breaking review.

#### BL-261 - v2.1.4: Backlog-slip prevention mechanisms #2, #4, #5

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-07)**: NEW. Prevention mechanisms #1 (orphan-check script + lefthook + CI) and #3 (BL ↔ CHANGELOG cross-reference convention) shipped in v2.1.0 alongside the BL-236 retroactive re-target. Three further structural mechanisms are deferred to v2.1.1.

**Driver**: 2026-05-07 root-cause investigation of how BL-236 slipped (originally labeled v2.1, never implemented, never deferred, undetected until ship preparation) surfaced a 5-mechanism prevention design. Mechanisms #1 + #3 ship in v2.1.0 because the orphan-check script + convention update were small enough not to disrupt the ship window. Mechanisms #2/#4/#5 require larger changes (plan template updates, new agent, phase-checklist amendment) and are batched as v2.1.1 contributor-experience work alongside BL-236 (lefthook Python coverage), BL-237 (V2_MODULES tightening), BL-245 (downstream stack-aware lefthook), BL-246 (`/lp-release` automation).

**At v2.1.1 design time**:

1. **Mechanism #2 — Mandatory BL coverage matrix in master plan template.** Every master implementation plan (e.g., `YYYY-MM-DD-vX.Y-implementation-plan.md`) MUST include a section titled "BL coverage matrix" — a table listing every BL labeled for the release × phase that owns it × shipped/deferred status. Update `/lp-harden-plan` Step 2 (document quality pre-check) to flag plans missing the matrix or containing BLs without phase ownership as a P1 finding. Estimated effort: ~45-60 min (template doc + lp-harden-plan check + 1 regression test).

2. **Mechanism #4 — `lp-backlog-auditor` agent for cross-cutting hardening.** When `/lp-harden-plan` runs in cross-cutting mode (the 14-agent pass used for v2.1 final hardening), include a new agent that reads BACKLOG.md + master plan + release notes + CHANGELOG and reports backlog-coverage drift as P1/P2 findings. Distinct from the orphan-check script (which is a binary CI gate); the agent provides advisory analysis at plan time. Estimated effort: ~1-2h (author agent under `plugins/launchpad/agents/research/` + wire into harden_plan_agents list in `.launchpad/agents.yml`).

3. **Mechanism #5 — Phase exit-criteria template amendment.** Every phase plan's exit-criteria checklist gains: `[ ] BACKLOG.md audit: every BL labeled for this release is either closed in this phase, planned for a later phase in this release, or explicitly deferred with status note.` Estimated effort: ~15 min (one-line addition to the phase-plan template).

**Cross-link**: BL-236 slip RCA (root cause: scope-doc-to-implementation-plan handoff was lossy + no reconciliation gate); orphan-check script at `plugins/launchpad/scripts/plugin-backlog-orphan-check.py` (mechanism #1, shipped v2.1.0); BACKLOG.md "Convention: BL ↔ CHANGELOG cross-reference" header section (mechanism #3, shipped v2.1.0).

**Default decision**: defer to v2.1.1. Mechanisms #1 + #3 close the immediate gap (an orphan in BACKLOG.md will now fail CI). Mechanisms #2 + #4 + #5 are belt-and-suspenders defenses that make slip impossible at multiple stages of the planning chain rather than only at ship time.

#### BL-262 - v2.1.4: `/lp-bootstrap --recover` full reconciliation

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 P1.D follow-up bundle. v2.1.0 ships only sentinel-clear + provably-stale-manifest unlink; full reconciliation (auto-completing partial runs by re-rendering paths whose hashes diverge from the current manifest) is the BL-262 scope. Documented at `docs/architecture/SCAFFOLD_OPERATIONS.md` §12.6 + `plugins/launchpad/commands/lp-bootstrap.md`.

**Default decision**: defer to v2.1.1. The narrow surface lands the must-fix (downgrade-attack closure) without the design lift of partial-render reconciliation.

#### BL-263 - v2.2: StackIdV22Candidate persistence widening for `python_django`

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 D5 (catalog fallback). Per the v2.1.0 fallback table, `django` resolves to `python_generic` (NOT `python_django`) at scaffold time. The widening — letting `python_django` flow through the closed-enum persistence — is deferred to BL-263 so the v2.1.0 fallback can be conservative.

**Default decision**: defer to v2.1.1. Conservative fallback at v2.1.0; widening lands once Django adapter dispatch is genuinely active.

#### BL-264 - v2.2: `version_drift_log` reader API + canonical normalization

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 D7. v2.1.0 ships writer-side canonical 5-key emission (bootstrap + identity-update both speak the same shape). No reader API exists at v2.1.0; pre-v2.1-rc mixed-shape entries are tolerated as historical data. BL-264 adds: (1) a typed `VersionDriftEntry` reader, (2) reader-side normalization for legacy 4-key entries, (3) accessor methods.

**Default decision**: defer to v2.1.1. No production reader exists at v2.1.0; the reader API can land alongside the first consumer.

#### BL-265 - v2.2: HOOK_CLASSIFICATIONS dataclass single-source refactor

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 D1. v2.1.0 ships HOOK_CLASSIFICATIONS as a parallel `Mapping[str, str]` keyed by target_relpath, co-located with `INFRASTRUCTURE_FILES`. The drift gate (`set(HOOK_CLASSIFICATIONS) <= INFRASTRUCTURE_TARGETS`) catches rename mismatch. BL-265 collapses the two structures into one dataclass per row.

**Default decision**: defer to v2.1.1. The parallel mapping is structurally safe at v2.1.0; the dataclass refactor is ergonomic cleanup.

#### BL-266 - v2.2: typed Rejected sub-types + `--accept-v2-2-fallback` CLI flag

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 D5/D9. v2.1.0 routes Rejected reasons through the existing `Rejected.extra` dict for missing_fields + ambiguity matches. BL-266 adds: (1) typed Rejected sub-types per failure category, (2) optional `--accept-v2-2-fallback` flag for downstream CI users that want to bypass the interactive confirmation for v2.2-candidate stack ids.

**Default decision**: defer to v2.1.1. The flag is intentionally NOT shipped at v2.1.0 (non-TTY contract refuses; explicit-accept opt-in is filed for downstream demand).

#### BL-267 - STALE: `/lp-bootstrap --refresh --accept-drift` consumer of `user_has_drift`

**Status (2026-05-08)**: STALE — `user_has_drift` field was DELETED during v2.1.0 PR #50 cycle 4 (atomic-io + kernel-drift fix; replaced with `missing_on_disk` boolean per F4 of cycle 5 plan). The consumer reference this BL describes is now structurally invalid. CLOSED with no replacement — if downstream readers eventually need a drift-accept consumer for the new `missing_on_disk` shape, file a fresh BL describing that surface.

**Original status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 D6. v2.1.0 seals `user_has_drift: bool` per kernel-render-state entry (Case E "y" path). The consumer that reads this flag — `/lp-bootstrap --refresh --accept-drift` — is BL-267. v2.1.0 documents the contract so downstream readers don't observe the field as orphaned data.

**Default decision**: CLOSED-as-stale. The field reference no longer exists at HEAD.

#### BL-268 - v2.2: `template_cache` symlink allowlist for monorepo workspaces

**Status (2026-05-07)**: NEW — deferred to v2.2 from v2.1.0 Codex PR #50 P0 (D9.1). v2.1.0 rejects ALL non-regular non-directory entries in fetched template trees (symlink, block/char devices, FIFOs, sockets). If real upstream monorepo workspaces use legitimate symlinks, BL-268 considers an allowlist that distinguishes intra-tree symlinks (allowed) from escape-target symlinks (rejected).

**Default decision**: defer to v2.2. v2.1.0 ships the conservative all-reject posture; allowlist work is dependent on real-world demand.

#### BL-269 - v2.2: safe_run regex extension for git ls-remote ^{} dereference

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 post-review-2 P1 #3. `template_cache/_resolver.py:142` invokes `git ls-remote refs/tags/<tag>^{}` to dereference annotated tags to their commit SHA. `safe_run._validate_argv()` rejects the argv because `^`, `{`, `}` are not in `_ARGV_SAFE_RE`. The fallback returns the tag-object SHA while GitHub REST returns the commit SHA → false `dual_resolution_mismatch`.

**Driver**: tag drift detector (cve-watch.yml) + future template-cache-fetched annotated tags would surface false-mismatch errors in CI. Workaround at v2.1.0: `template_cache.fetch()` only sees pre-resolved SHAs from `pin_registry.py`, so the path is not exercised in the canonical scaffold flow. The `resolve_sha()` helper is exercised only by tests and future drift detection.

**At v2.1.1 design time**: extend `safe_run._ARGV_SAFE_RE` to allow safe literal `^{}` refspec OR add a dedicated annotated-tag dereference helper that uses `git ls-remote --refs` and parses the tag-object referent inline. Estimated effort: ~30-60 min.

**Default decision**: defer to v2.1.1. Not exercised on the v2.1.0 canonical scaffold path.

#### BL-270 - v2.2: safe_run env-passthrough for GH_TOKEN/GITHUB_TOKEN

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 post-review-2 P1 #4. `template_cache/_resolver.py:167` calls `gh api` through `safe_run`, but `safe_run` strips `GH_TOKEN`/`GITHUB_TOKEN` from the subprocess environment per its sandboxing posture. Workflows set `GH_TOKEN`, but the resolver behaves unauthenticated (5000 req/hr → 60 req/hr) or fails outright in clean CI.

**Driver**: same as BL-269 — `resolve_sha()` is not exercised on the v2.1.0 canonical scaffold path; only future drift detection + tests would hit it.

**At v2.1.1 design time**: add a resolver-specific minimal env-passthrough that allows ONLY `GH_TOKEN` + `GITHUB_TOKEN` through to `gh` subprocess invocations (NOT broadening env exposure for all scaffolders). Estimated effort: ~30-60 min.

**Default decision**: defer to v2.1.1. Same scope rationale as BL-269.

#### BL-271 - v2.2: Case D `--seed-brownfield` non-dry-run create path

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 post-review-2 P1 #1. `/lp-update-identity --seed-brownfield` (non-dry-run) currently returns a structured `BROWNFIELD_SEED_NOT_IMPLEMENTED` error rather than crashing with `FileNotFoundError`, but the actual seed-from-scratch behavior the documentation advertises is not implemented.

**At v2.1.1 design time**: implement the create path via `write_decision_file()` from a fresh seed, OR add a dedicated seed writer that constructs a minimal valid v1.1 envelope from the supplied identity + git config. Add an integration test (BL-272 below) covering the full create-and-seal flow.

**Default decision**: defer to v2.1.1. v2.1.0 fail-closed prevents the unstructured crash; the actual seed flow is meaningful design work.

#### BL-272 - v2.2: Case D non-dry-run integration test

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 post-review-2 P3. `tests/test_update_identity_engine.py:341` explicitly avoids exercising the non-dry-run Case D brownfield seed flow. Once BL-271 implements the create path, add an integration test that runs the actual create-and-seal path end-to-end.

**Default decision**: ship alongside BL-271 in v2.1.1.

#### BL-273 - v2.2: signpost stub UX — Permission denied vs migration message

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 post-review-2 P2. `scripts/setup/init-project.sh` and `scripts/setup/pull-upstream.launchpad.sh` are signpost stubs at `mode 0o644` (`chmod -x` per Phase 8 deliberate design — `tests/test_decommissioning_paths_removed.py:67-70` enforces). Users invoking `./scripts/setup/init-project.sh` get `Permission denied` rather than the migration message embedded in the script. Two design tradeoffs in tension: (a) Phase 8 chose `chmod -x` to prevent accidental sourcing/invocation from CI; (b) Codex prefers the migration message reaching the user.

**At v2.1.1 design time**: replace the bash signpost stubs with a `README.md` in `scripts/setup/` that documents the v2.1 plugin install. Delete the bash stubs entirely (per Codex's "remove them entirely and update references" alternative). Update `tests/test_decommissioning_paths_removed.py` accordingly. Estimated effort: ~30 min.

**Default decision**: defer to v2.1.1. The Phase 8 design choice ships at v2.1.0 unchanged.

#### BL-274 - v2.2: cve-watch tag-drift detector noise reduction

**Status (2026-05-07)**: NEW — deferred to v2.1.1 from v2.1.0 Codex PR #50 post-review-2 P2. `.github/workflows/cve-watch.yml:93` checks whether each pinned SHA appears in the first 5 lines of `git ls-remote`. Many valid pins won't appear there (the tag they pin may be older than 5 ls-remote rows), and moved tags are not specifically checked.

**At v2.1.1 design time**: extend `pin_registry.py` to record the source tag/ref alongside each SHA; have the detector resolve THAT exact ref via `git ls-remote refs/tags/<tag>` and compare expected vs resolved SHA. Estimated effort: ~1h.

**Default decision**: defer to v2.1.1. The current detector emits soft `::warning ::` advisories that don't fail CI; noise is tolerable until the structured tag/ref recording lands.

#### BL-283 - v2.2: `analyze-report.sh.j2` word-split bug

**Status (2026-05-07)**: NEW — deferred from v2.1.0 Codex PR #50 cycle 4 P3. `plugins/launchpad/scripts/plugin_default_generators/infrastructure/scripts/compound/analyze-report.sh.j2:78` uses `for prd in $RECENT_PRDS` which word-splits paths returned from `find`, breaking on file paths containing spaces.

**At v2.1.1 design time**: quote the variable or switch to a `while IFS= read -r` loop consuming `find -print0` output. Add a test with space-containing paths.

**Default decision**: defer to v2.1.1+. Low severity (P3); the generated script is advisory and rarely encounters paths with spaces in practice.

#### BL-284 - v2.1.4: tier-2-nightly composition matrix not consumed

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-08)**: NEW — deferred from v2.1.0 Codex PR #50 cycle 5 P2. `.github/workflows/tier-2-nightly.yml:30` declares two canonical stack compositions in the matrix, but the test command at `:70` does not consume `matrix.composition.stacks` or run the composition suite. Both matrix jobs run identical adapter/template-cache tests, so the advertised hot-path compositions are not actually exercised.

**At v2.1.1 design time**: pass the matrix stacks into a composition/dispatch smoke runner, or include the relevant composition tests filtered per matrix entry. Folds into v2.1.1's universal-lefthook + CI parity work (Phase 4).

**Default decision**: defer to v2.1.1. CI hygiene only; doesn't affect runtime correctness.

#### BL-285 - v2.1.4: backup secret-scan gate

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 hardening (security-lens P1-1). `.launchpad/backups/<ts>-<PID>-<rand4>/` may contain user content with secrets-shaped files (e.g., `.env.example`). v2.1 secret-scanner does NOT walk this directory.

**At v2.1.1 design time**: extend the secret-scanner walker to include `.launchpad/backups/` OR document explicitly in IDENTITY_AND_PII.md that backups are out-of-scope and operators must sweep manually before sharing tarballs.

**Default decision**: defer to v2.1.1. Backups are short-lived runtime artifacts, gitignored; risk surfaces only if operator copies them off-machine.

#### BL-286 - v2.2: `.launchpad/backups/` at-rest encryption + GDPR + retention compliance docs

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 hardening (security-lens P3-1, P3-2, P3-3). Three doc additions:

- IDENTITY_AND_PII.md: at-rest encryption posture for `.launchpad/backups/` (typically inherited from disk encryption; document the assumption).
- IDENTITY_AND_PII.md: GDPR right-to-erasure note — backups MUST be included in user-erasure workflows.
- IDENTITY_AND_PII.md: SOC2/ISO27001/HIPAA retention enumeration — document that v2.1 ships with NO automated retention; operators with compliance obligations must add their own.

**At v2.1.1 design time**: ~30-line addition to IDENTITY_AND_PII.md; no code changes.

**Default decision**: defer to v2.1.1. Documentation hygiene; doesn't block ship.

#### BL-287 - v2.1.4: `/lp-cleanup-backups` retention command

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 (DA-F8.11; perf, scope-guardian, product-lens reviews concurred).

`/lp-cleanup-backups [--older-than=N-days] [--keep-last=N]` enumerates `.launchpad/backups/<ts>-<PID>-<rand4>/_manifest.json` entries, applies retention policy, and removes matching entries. Manifest schema (v2.1) already supports this.

**At v2.1.1 design time**: ~150 LOC new command + 3-4 tests. Reuses the manifest written by composition.

**Default decision**: defer to v2.1.1. v2.1.0 ships with stderr WARN at 50 entries / 1 GB; manual `rm -rf` is acceptable for early forensic use.

#### BL-288 - v2.2: backup tamper-detection (audit.log integrity hash)

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 hardening (security P2-2). When backups are relocated, log a sha256 of the relocated tree to `.launchpad/audit.log` so operators can detect post-hoc tampering.

**At v2.1.1 design time**: extend `_relocate_backups_to_launchpad` to write an audit-log entry with `{run_id, target_path, sha256, timestamp}`. ~30 LOC + 1 test.

**Default decision**: defer to v2.1.1. Sealed-envelope variant possible at v2.2+ if formal integrity contracts are added.

#### BL-289 - v2.2: full handshake-lint allowlist sweep post-F9

**Status (2026-05-08)**: NEW — partially closed in v2.1.0 PR #50 cycle 6. The F9 fix routed `_record_version_drift` through `re_seal_decision_atomic`, so the `lp_bootstrap/engine.py` entry was REMOVED from `ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS` (the in-tree allowlist-sweep test mechanically demanded the removal). Remaining v2.1.1 work: audit other allowlisted modules (`policy.py`, `manifest_writer.py`, `_renderer_base.py`) for similar narrowing opportunities.

**At v2.1.1 design time**: per-module audit of remaining allowlisted callers; consolidate atomic-write call sites where helper-routing is feasible.

**Default decision**: defer to v2.1.1. Hygiene; doesn't affect runtime. Cycle 6 closed the engine.py portion; v2.1.1 covers the rest.

#### BL-290 - v2.2: `read_decision_atomic_or_recover()` for corrupt files

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 (DA-F9.3). `re_seal_decision_atomic` currently raises `VERSION_DRIFT_RESEAL_FAILED` when scaffold-decision.json is missing or corrupt. The user-facing remediation says "run /lp-bootstrap --refresh", but `--accept-plugin-version-drift` is the canonical recovery flag — circular.

**At v2.1.1 design time**: introduce `read_decision_atomic_or_recover()` that gracefully handles already-corrupted files (the recovery scenario `--accept-plugin-version-drift` is meant to address).

**Default decision**: defer to v2.1.1. Edge case; v2.1.0 ships with refuse-loud + actionable error.

#### BL-291 - DUPLICATE of BL-269

**Status (2026-05-08)**: DUPLICATE — see [BL-269](#bl-269---v22-safe_run-regex-extension-for-git-ls-remote--dereference) for canonical entry. Filed by v2.1.0 cycle 6 post-push triage without recognizing BL-269 already covered the same `safe_run._ARGV_SAFE_RE` `^{}` syntax fix. BL-269 retargeted to v2.2; this stub preserves the audit trail of the dedupe.

#### BL-292 - DUPLICATE of BL-270

**Status (2026-05-08)**: DUPLICATE — see [BL-270](#bl-270---v22-safe_run-env-passthrough-for-gh_tokengithub_token) for canonical entry. Filed by v2.1.0 cycle 6 post-push triage without recognizing BL-270 already covered the `safe_run` env-allowlist `GH_TOKEN`/`GITHUB_TOKEN` passthrough fix. BL-270 retargeted to v2.2; this stub preserves the audit trail of the dedupe.

#### BL-293 - v2.2: `safe_run_long_shell` streaming for `commands.dev`

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 post-push Codex P2. `safe_run.py:296`'s `safe_run_long_shell()` captures stdout/stderr via pipes and waits on `communicate()`. For `commands.dev` (long-running dev servers via `/lp-build` dev stage), this hides server output from the parent terminal and grows memory unbounded as the server logs accumulate.

**Driver**: `safe_run_long_shell` was authored as a SIGINT-aware variant for long-running subprocesses but inherited the pipe-capture pattern from short-form `safe_run`. Long-running dev servers can run for hours with verbose log output; pipe buffering accumulates without bound, eventually pushing parent process toward OOM on long sessions.

**At v2.1.1 design time**:

1. Stream stdout/stderr to the parent terminal (inherit-fds pattern) for `commands.dev` invocations
2. OR use a bounded log buffer (ring buffer) with disk-backed overflow if structured capture is desired for telemetry
3. Decision criterion: if v2.1.1 introduces a "/lp-build dev --capture-logs" mode, use bounded buffer; otherwise prefer inherit-fds for simplicity
4. Add a long-session simulation test (10+ minute synthetic dev server) asserting parent memory stays bounded

**Default decision**: defer to v2.1.1. Memory growth requires hours of uninterrupted dev session; CI/short interactive sessions unaffected.

#### BL-294 - v2.2: `plugin-agent-scope-filter` preserve agents.yml input order

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 post-push Codex P2. `plugin-agent-scope-filter.py:273` sorts the surviving agents alphabetically after stack filtering, changing the order from how agents are listed in `.launchpad/agents.yml`. If `agents.yml` order represents review priority or expected dispatch order (it does for `/lp-review` Step 4 sequential-then-parallel), this is a behavior regression.

**Driver**: the filter was authored to make output deterministic for testing, but tests that assert deterministic order should pin to input order, not alphabetical. `/lp-review` Step 4 explicitly notes "Dispatch order defined in /lp-review Step 4 (sequential-then-parallel), not by list order" for DB agents but that exception was specific to Prisma sequencing — the rest of the dispatch chain assumes file-order semantics.

**At v2.1.1 design time**:

1. Change `plugin-agent-scope-filter.filter_agents_by_stacks()` to return survivors in input order (preserve list ordering from `agents.yml`)
2. If alphabetical ordering is desired for any specific consumer, that consumer sorts its own copy
3. Add a test asserting input order is preserved across filter invocations
4. Verify no existing test relies on alphabetical ordering — adjust if so

**Default decision**: defer to v2.1.1. Doesn't affect correctness of any current dispatch path (review agents are independent), but worth fixing before v2.1.1 expands the dispatch contract surface (e.g., when `/lp-review --no-context` lands and sequential-then-parallel ordering becomes more meaningful).

#### BL-295 - DUPLICATE of BL-274

**Status (2026-05-08)**: DUPLICATE — see [BL-274](#bl-274---v22-cve-watch-tag-drift-detector-noise-reduction) for canonical entry. Filed by v2.1.0 cycle 6 post-push triage without recognizing BL-274 already covered the cve-watch.yml tag-drift noise reduction fix (store expected tag/ref alongside SHA pin, resolve specific ref vs first-5-lines heuristic). BL-274 retargeted to v2.2; this stub preserves the audit trail of the dedupe.

#### BL-296 - v2.2: pin pip in `v2-handshake-lint.yml` + `v2-release.yml`

**Status (2026-05-08)**: NEW — deferred from v2.1.0 PR #50 cycle 6 post-push Codex P3. `.github/workflows/v2-handshake-lint.yml:38` and `.github/workflows/v2-release.yml:66` upgrade `pip` without a pin immediately before installing hash-pinned dependencies. This weakens reproducibility for otherwise hash-pinned workflows — a malicious or buggy `pip` release between hash-pin authoring and CI run could compromise dependency installation.

**Driver**: pip-upgrade-before-install is a common idiom but defeats the purpose of hash-pinning when pip itself is mutable. v2.1's supply-chain pinning policy (per HANDSHAKE §1.4) tightened transitive dependencies but left the bootstrap `pip` itself unconstrained.

**At v2.1.1 design time**:

1. Pin pip to a specific version (e.g., `pip install --upgrade "pip==24.X.Y"`) in both workflows
2. Add `pip` to the `_vendor/PIP_VERSION` pin file (parallel to other supply-chain pins)
3. CVE-feed acceptance gate covers pip the same as other pinned tools
4. OR: drop the `pip install --upgrade pip` line entirely and rely on the runner-provided pip (simpler; matches Codex's secondary suggestion)

**Default decision**: defer to v2.1.1. Low severity (P3); doesn't affect runtime correctness or downstream installs. Reproducibility hardening fits naturally with v2.1.1's supply-chain posture work.

#### BL-297 - v2.1.3: Codex/Greptile corpus-trained reviewer agent

**Status (2026-05-10)**: RE-TARGETED v2.1.2 → v2.1.3. See BL-316.

**Status (2026-05-08)**: NEW — v2.1.2 dedicated work; primary deliverable. Plan authored at [docs/plans/launchpad_plans/2026-05-07-v2.1.2-codex-corpus-trained-reviewer-plan.md](../plans/launchpad_plans/2026-05-07-v2.1.2-codex-corpus-trained-reviewer-plan.md).

**Driver**: closes the third review failure mode (pattern-recognition gap) that v2.1.1's three-layer fix explicitly does NOT cover. v2.1.1 closes plan-bias (Layer 2 `--no-context`) and structural invariants (Layer 3 semgrep). The remaining ~30% gap is novel-pattern detection — bug classes our agents have never seen. Closed via in-context learning over a corpus of past Codex + Greptile PR comments (NOT fine-tuning).

**Strategic value**: Codex narrow + Greptile wide are deliberately complementary lanes — the combined corpus produces richer training than either alone. Codex strengths populate buckets like `path_safety`, `error_handling`, `subprocess_shell`, `atomic_write_contracts` (line-level patterns). Greptile strengths populate `cross_file_invariants`, `convention_drift`, `architectural_deviation` (codebase-aware patterns). Same-line agreement between both reviewers in the historical record is treated as ground-truth signal (1.5× exemplar weight at sampling time).

**At v2.1.2 design time**:

1. `lp-corpus-extract.py` scans all PR review comments authored by `codex-bot` + `greptile-apps[bot]`, normalizes findings into `(diff_pattern, finding_class, severity, lane, fix_summary)` tuples with explicit `"narrow"`/`"wide"`/`"both"` lane tagging.
2. `lp-corpus-classify.py` assigns each tuple to one of ~14 pattern buckets (sentinel ordering, path safety, SHA domain confusion, resource cleanup, type confusion, subprocess/shell, atomic write contracts, schema drift, cross-file invariants, concurrency, error handling, documentation drift, naming/convention drift, architectural deviation).
3. New `lp-codex-trained-reviewer` agent loads top 30-50 exemplars (lane-balanced sampling) into its system prompt at dispatch time.
4. Wired as fourth pass in `/lp-review` alongside specialist + no-context passes (from v2.1.1 Layer 2).
5. `/lp-refresh-codex-corpus` slash command re-extracts corpus from latest PR history.
6. Corpus storage at `.harness/codex-corpus.jsonl` (gitignored runtime path).

**Validation**: synthetic-bug detection tests for the top 5 buckets (sentinel-after-materialize, atomic_io-no-trusted-root, sha-no-domain-tag, composition-no-rmtree, subprocess-shell-true). Dogfood metric on v2.1.2's own PR: Codex P0/P1 finding count should be LOWER than the v2.1 cycle baseline (cycles 1-5 averaged ~2-3 per push).

**Default decision**: ship after v2.1.1. ~12-16h of corpus tooling + agent definition + integration work. See plan file for full 5-phase breakdown + DA-decisions (D1: in-context learning not fine-tuning; D6: combined corpus complementary lanes; D9: lane-balanced sampling).

#### BL-298 - v2.1.4: Pyright strict on engine modules

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — deferred from v2.1.1 Phase 4 hybrid disposition.

**Driver**: Phase 4 R1-T1-10 graceful-fallback escalation. Pyright strict mode surfaced 209 errors across 5 modules:

- `decision_validator.py` — 73 errors (security boundary; absorbed via mechanical type-annotation pass + ignore ladder in Phase 4)
- `nonce_ledger.py` — 2 errors (trivial absorb in Phase 4)
- `decision_integrity.py` — 3 errors (trivial absorb in Phase 4)
- `lp_pick_stack/engine.py` — 23 errors (deferred to BL-298)
- `lp_scaffold_stack/engine.py` — 108 errors (deferred to BL-298)

**At v2.1.3 design time**:

1. Engine modules carry significant `Any`-leakage from subprocess + path APIs; evaluate per-module annotation strategy similar to `decision_validator.py` Phase 4 approach.
2. Lower priority than security-boundary modules already strict-pinned in v2.1.1 (R2-T1-18 honored at Phase 4).
3. Mechanical type-annotation pass first (kills 40-60% of errors), then targeted `# type: ignore[<rule>]` for legitimate `Any`-leakage at subprocess boundaries.

**Default decision**: defer to v2.1.3. Engine modules are subprocess/path-manipulation surfaces where pyright strict has lower bang-for-buck than at the JSON validation boundary.

#### BL-299 - v2.1.4: nodeenv binary download outside pip hash coverage

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — deferred from v2.1.1 Phase 4 R1-T1-16 escape hatch (pip-compile transitive coverage).

**Driver**: Phase 4 ships `requirements.txt` with `--require-hashes` (Path A pip-compile). Pyright pulls `nodeenv` as a transitive dependency; nodeenv downloads a Node.js binary at install time. The Node binary download is OUTSIDE pip's hash protection — pip-compile only hashes the Python distribution.

**At v2.1.3 design time**: two options:

1. Replace `pyright` with `mypy` (no Node.js dependency). Tradeoff: Pylance integration loss; cold-run slower.
2. Pin the node binary download via CI checksum verification (custom CI step that re-downloads + verifies SHA256 before pyright runs).

**Default decision**: defer to v2.1.3. Pyright was locked at master plan D6; nodeenv hole is a residual supply-chain surface acceptable for v2.1.1's single-maintainer threat model. Surfaced in user-facing `docs/guides/CODE_REVIEW_LAYERS.md` per Round 1 security-lens P2-2 (not BL-only).

#### BL-300 - v2.1.4: `--strict-dispatch` flag on `/lp-review`

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 Phase 3 sibling Hard Rule 6 violation (substituted self-review for parallel agent dispatch).

**Driver**: `/lp-review --headless` + `/lp-review --headless --no-context` (the v2.1.1 mandatory dual-pass) suppress interactive prompts and strip context, but neither enforces that the implementing session actually executes Step 3's parallel `Task` dispatch. Phase 3 sibling invoked both flags but skipped Step 3 dispatch — substituting spec-text-inspection (self-review) and writing a clean summary. The `tool_use_id` proof-of-dispatch enforcement at Phase 4 was a procedural workaround.

**At v2.1.3 design time**:

1. Add `--strict-dispatch` (or `--require-task-dispatch`) flag to `/lp-review`.
2. When set: refuse to fall back to self-review; exit non-zero if Step 3's parallel `Task` block doesn't fire (e.g., empty agent list, agent files missing, dispatch failure).
3. Wire into `/lp-commit` Step 2.5 + `/lp-ship` Step 4.6 mandatory dual-pass — both invocations gain `--strict-dispatch` post-BL-300.
4. Add an integration test that invokes `/lp-review --strict-dispatch` against a synthetic empty agents.yml roster; expect non-zero exit with clear error message.

**Default decision**: defer to v2.1.3. v2.1.1 closes the gap procedurally via `tool_use_id` reporting in handoff template + sweep-sibling validation (DA-5.7); programmatic enforcement deserves its own design pass.

#### BL-301 - v2.1.4: semgrep synthetic-violation fixtures

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — deferred from v2.1.1 Phase 5 Slice F. Phase 4 master plan §4 specified `tests/fixtures/semgrep_violations/{sentinel_after_materialize,atomic_io_no_trusted_root,sha_no_domain_tag,composition_no_rmtree}.py` as deliverables; not shipped at Phase 4 final state. Phase 5 deferred per "ships NO RUNTIME CODE" rule.

**Driver**: each Phase 4 cross-cutting invariant semgrep rule needs a known-violator fixture to assert the rule fires correctly during CI. Without fixtures, rule regressions surface only when production code accidentally violates them.

**At v2.1.3 design time**:

1. Author 4 minimal Python fixtures (~5-15 lines each) under `plugins/launchpad/scripts/tests/fixtures/semgrep_violations/`.
2. Each fixture triggers exactly ONE rule from `plugins/launchpad/.semgrep/launchpad-internal.yml`.
3. Verify via `semgrep --config=plugins/launchpad/.semgrep/launchpad-internal.yml plugins/launchpad/scripts/tests/fixtures/semgrep_violations/`.
4. Each fixture must NOT trigger OTHER rules (false positives break the test contract).
5. Add CI test that asserts each fixture triggers its target rule.

**Default decision**: defer to v2.1.3. Phase 4 invariants are still enforced on production code; fixtures formalize regression protection for the rules themselves.

#### BL-303 - v2.1.4: `lp-engine-sentinel-must-precede-materialize` semgrep rule

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — Phase 4 Slice 7 BL-DEFERRED per R1-T1-9 + adversarial P2-A iteration cap (>2 fail-to-validate iterations).

**Driver**: the `lp-engine-sentinel-must-precede-materialize` rule was specified in Phase 4 plan §4 as one of 4 cross-cutting invariants. Phase 4 sibling iterated >2 times trying to author a semgrep pattern that correctly fires on sentinel-after-materialize ordering violations without false-positives across the lp_pick_stack/lp_scaffold_stack engine modules. Pattern complexity exceeded Phase 4's iteration budget; rule disabled and BL'd.

**At v2.1.3 design time**:

1. Re-attempt rule authoring with semgrep `pattern-inside`/`pattern-not-inside` form (per Phase 4 R1-T1-9 best-practice).
2. Validate against the 2 actual engine modules — pattern MUST fire on a synthetic violation AND not false-positive on the actual sentinel-precedes-materialize ordering currently in production.
3. Once active, add to `plugins/launchpad/.semgrep/launchpad-internal.yml` (currently 3 active rules; this becomes the 4th).

**Default decision**: defer to v2.1.3. The invariant is real but enforcement is currently via code review + the existing sentinel acquisition contract documented in OPERATIONS.md.

#### BL-304 - v2.1.4: secret-patterns.txt over-match on `\bdownstream\s+project`

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — Phase 4 sibling iteration finding (1 false-positive in Jinja-template comment surface ride-along moved by ruff import-sort).

**Driver**: the secret-scanner pattern `\bdownstream\s+project` matches innocent prose mentions of "downstream project" in Jinja templates (which contain comment-style documentation about LaunchPad architecture). False-positives slow developer flow and risk normalizing "ignore secret-scanner" muscle memory.

**At v2.1.3 design time**:

1. Scope-narrow the pattern: require additional context (e.g., `=` or `:` indicating an actual key-value secret pattern, not prose).
2. Verify against the 1 known false-positive site + audit other Jinja-template comment surfaces.
3. Update `.launchpad/secret-patterns.txt`.

**Default decision**: defer to v2.1.3. False-positive frequency is low (1 confirmed); not blocking ship.

#### BL-305 - v2.1.4: portable timeout wrapper for macOS lefthook entries

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — Phase 4 sibling iteration finding. Plan DA-4.9 specified `timeout 60/120 semgrep ...` wrappers but `timeout` binary is absent on macOS (unlike Linux/CI). Phase 4 removed wrappers; lefthook handles its own timeouts.

**Driver**: portable cross-platform timeout would let plan-spec'd tool-level timeouts work on both macOS dev environments AND Linux CI. `gtimeout` (via `coreutils`) or `perl -e 'alarm shift @ARGV; exec @ARGV' SECONDS CMD` are portable patterns.

**At v2.1.3 design time**:

1. Choose portable timeout strategy (gtimeout via brew install OR perl alarm pattern).
2. Document in lefthook.yml or wrap in a `scripts/maintenance/portable-timeout.sh` helper.
3. Re-add timeout wrappers to lefthook entries that benefit (semgrep, pyright on large diffs).

**Default decision**: defer to v2.1.3. lefthook native timeout handling is sufficient at v2.1.1; portable wrappers are polish.

#### BL-306 - v2.1.4: semgrep allowlist-vs-handshake-lint parallelism

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — Phase 4 sibling /lp-review accepted finding (NOT amended); referenced in Phase 4 R2-T1-14.

**Driver**: semgrep `allowlist` (in semgrep configs) and `plugin-v2-handshake-lint.py` ALLOWLIST mechanism solve overlapping problems via different mechanisms. Operationally, contributor discovers an allowlist need and may modify the wrong system. Convergence opportunity.

**At v2.1.3 design time**:

1. Audit both allowlist mechanisms; identify overlap zones.
2. Either (a) document clear separation-of-concerns + when to use which, OR (b) consolidate into single allowlist with bidirectional reference.

**Default decision**: defer to v2.1.3. Operational hygiene; not a correctness issue.

#### BL-307 - v2.1.4 / v2.2: Phase 4 simplicity-reviewer cleanup-style P1s

**Status (2026-05-10)**: RE-TARGETED v2.1.3 / v2.2 → v2.1.4 / v2.2 (single-tag side only). See BL-316.

**Status (2026-05-09)**: NEW — bundle of 9 simplicity-reviewer findings from Phase 4 /lp-review Commit 2 (12 P1 total — 3 amended; 9 NOT amended with documented rationale "out of v2.1.1 scope").

**Driver**: Phase 4 simplicity reviewer surfaced 9 cleanup-style P1s on the Phase 4 surface (e.g., DRY refactors, naming standardization, comment density). Phase 4 sibling triaged out-of-scope for v2.1.1 ship.

**At v2.1.3 design time**:

1. Re-load Phase 4 /lp-review report from `.harness/observations/` (if retained) OR re-dispatch /lp-review against v2.1.1 surface.
2. Triage each P1 individually; absorb cheap items in v2.1.3 patch lane.
3. Defer architectural simplifications (DRY across packages) to v2.2 if any are non-trivial.

**Default decision**: defer to v2.1.3 / v2.2. Not blocking; quality-of-life polish.

#### BL-308 - v2.1.4: Resolve outstanding pyright/nosec `BL-<TBD>` deferrals from v2.1.1

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 cross-cutting sweep-review.

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09)

**Driver**: 16 sites shipped at v2.1.1 with `BL-<TBD>` placeholder pointers in nosec/pyright suppression comments. Phase 3 plan §6 + Phase 5 plan §1 intended these to be seeded at Phase 5 stash-pop, but the seeding slipped — the BL-298..307 set covers different items. Slice H.1 substituted all 16 occurrences with `BL-308`, deferring the underlying-issue resolution to v2.1.3.

**Sites**:

- `plugins/launchpad/scripts/safe_run.py:300` (B602 nosec, safe_run_long_shell)
- `plugins/launchpad/scripts/plugin-build-runner.py:338` (B602 nosec, stage runner)
- `plugins/launchpad/scripts/plugin-agent-scope-filter.py:147` (B506 nosec, \_SafeLoader binding indirection)
- `plugins/launchpad/scripts/pyproject.toml:59-66` (8 pyright per-rule severity downgrades)
- `plugins/launchpad/scripts/plugin-v2-handshake-lint.py:193, 196, 199, 202, 804` (4 deferral pointers + 1 B608 nosec)

**At v2.1.3 design time**:

1. Revisit each suppression and either (a) eliminate the underlying issue (preferred — e.g., refactor safe_run usage, narrow pyright type contracts), or (b) split into per-site dedicated tracking BLs with explicit per-site rationale.
2. The `BL-308` umbrella allows v2.1.1 to ship without a placeholder hole; v2.1.3 is the appropriate window to tease apart underlying issues vs. accepted-debt sites.

**Default decision**: defer to v2.1.3.

#### BL-309 - v2.1.x: lp-ship.md `exit non_zero` typo

**Status (2026-05-09)**: SHIPPED in v2.1.1 — see PR #62 (Greptile review folded into Slice H.4 fix bundle; `exit non_zero` → `exit 1` at `lp-ship.md:137`).

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09; sweep P2-1) + v2.1.1 PR #62 Greptile review (2026-05-09; G-3)

**Driver**: `plugins/launchpad/commands/lp-ship.md:137` contained the literal text `exit non_zero` inside a fenced bash code block (Step 4.6 HARD STOP path on resolver-completion check failure). Bash interprets this as `bash: exit: non_zero: numeric argument required`. Should be `exit 1`. Doc-only defect in shipped command spec; agent interpreting the spec will likely treat as "exit non-zero" but real bash fires an error.

**At v2.1.x design time**: ~~1-line edit, replace `exit non_zero` → `exit 1`. Suitable for a v2.1.x doc-quality patch lane.~~ Superseded — fix landed in v2.1.1 Slice H.4.

**Default decision**: ~~defer to v2.1.x~~ → SHIPPED in v2.1.1.

#### BL-310 - v2.1.x: Pin-file doc drift on "5 contract modules" vs canonical "3"

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 cross-cutting sweep-review.

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09; sweep P2-3)

**Driver**: 4 sites still say "5 contract modules" / "5 strict modules":

- `plugins/launchpad/scripts/pyproject.toml:10` (top-of-file overview comment)
- `plugins/launchpad/scripts/pyproject.toml:55` (per-rule severity block header comment)
- `plugins/launchpad/scripts/pyproject.toml:57` (in-block "outside the 5 strict modules" guidance)
- `plugins/launchpad/scripts/requirements.in:31` (pyright pin comment)

The canonical surface — `docs/architecture/CI_CD.md:108`, `docs/guides/CODE_REVIEW_LAYERS.md:72`, `CHANGELOG.md:33`, `.github/workflows/v2-handshake-lint.yml:62-64` — all say "3 (security-boundary) modules". Per Phase 4 R1-T1-10 hybrid escalation the original 5-module set was reduced to 3; the four pin/comment-block sites missed the reconciliation. Note: `pyproject.toml:68` correctly says "the original 5-module set" in context that explains the 5→3 reduction; that one is correct.

**At v2.1.x design time**: 4-line comment edit reconciling all four sites to "3 security-boundary modules".

**Default decision**: defer to v2.1.x.

#### BL-311 - v2.1.x: Dead code removal in plugin-build-runner.py

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 cross-cutting sweep-review.

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09; sweep P2-4)

**Driver**: `plugins/launchpad/scripts/plugin-build-runner.py` carries two unreferenced helpers: `_compute_hash` (lines 114-125) and `_is_hex` (lines 225-230). Both verified zero callsites via grep. The docstring of `check_ci_override` even says _"Previously this function did its own raw-string compare against `_compute_hash`"_ — i.e., it explicitly migrated AWAY from `_compute_hash` to `_resolve_review_state`, but the function was left behind. Multi-agent flagged: spec security-auditor + spec code-simplicity + blind code-simplicity.

**At v2.1.x design time**: delete `_compute_hash` (lines 114-125) and `_is_hex` (lines 225-230); ~17 LOC removal. Verify no lint regression on unused-import (`import json` is still used by `_resolve_review_state`).

**Default decision**: defer to v2.1.x.

#### BL-312 - v2.1.4: plugin-workflow-sha-pin-check.py regex bypass via GH Actions `${{ }}` expressions

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 cross-cutting sweep-review.

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09; sweep P2-5)

**Driver**: `_USES_RE = re.compile(r"uses:\s*([^#\s]+)")` at `plugin-workflow-sha-pin-check.py:19` stops the capture at the first whitespace. Any `uses:` value containing a GitHub Actions expression (e.g., `uses: ${{ matrix.action }}@v1`) truncates to `${{` at the space. `_extract_ref` returns None and the line is silently skipped (line 53-54 `continue`). Expression-form `uses:` resolves at runtime to a potentially attacker-controllable ref but slips the gate. Defense-in-depth gap, not exploitable in current corpus, but the gate's docstring claims "catch ALL non-SHA refs".

**At v2.1.3 design time**: parse workflow YAML with PyYAML AST traversal, walk `jobs.*.steps[].uses` nodes, hard-fail any value containing `${{` (expression) or whose ref is not a 40-hex SHA. Until the AST rewrite lands, add a regex pre-check that hard-fails on literal `${{` inside `uses:` values.

**Default decision**: defer to v2.1.3.

#### BL-313 - v2.1.4: lefthook here-string filename-quoting hardening

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 cross-cutting sweep-review (pre-existing pattern; v2.1.1 inherits).

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09; v2.1.3 candidate)

**Driver**: `lefthook.yml:163, 180, 196` (three pre-commit hooks: `large-file-guard` body line 163, `trailing-whitespace` body line 180, `end-of-file-newline` body line 196) interpolate `{staged_files}` into a double-quoted `echo` command before piping through `tr` and a here-string: `<<< "$(echo "{staged_files}" | tr ' ' '\n')"`. Inside double quotes, `$(...)` and backtick command substitution are evaluated by the shell. A staged file whose pathname contains `$(...)` (Git permits `$` and parentheses in pathnames on POSIX) would cause the embedded command to execute when the hook fires. Defense-in-depth bug; pre-existing in origin/main (NOT v2.1.1-introduced).

**At v2.1.3 design time**: replace `<<< "$(echo "{staged_files}" | tr ' ' '\n')"` with a safe iteration form. Options: (a) use lefthook's per-file `{staged_files}` expansion directly with `xargs -0` and a NUL-delimited list; (b) replace the inline shell with a Python helper script (the codebase already has `python3 plugins/launchpad/scripts/...` helpers for everything else); (c) at minimum, switch to `printf '%s\n' {staged_files}` form and stop double-quoting the substitution.

**Default decision**: defer to v2.1.3.

#### BL-314 - v2.1.4: nonce_ledger.py darwin branch tiebreak determinism

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 cross-cutting sweep-review.

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09; v2.1.3 candidate)

**Driver**: `lp_scaffold_stack/nonce_ledger.py:171` (Linux branch) uses strict `>` for longest-prefix-match, fixed per Phase 4 D11 absorption. `lp_scaffold_stack/nonce_ledger.py:203` (darwin branch) still uses `>=` — last-seen-wins, filesystem-ordering-dependent. The Linux comment at line 168-170 reads `# D11: strict longest-match-wins; tiebreak by first-seen (deterministic, not filesystem-ordering-dependent).` — that determinism rationale should apply to BOTH platforms. The regression-shield test `test_nonce_ledger_mountpoint_tiebreak.py` mocks Linux only.

**At v2.1.3 design time**: change line 203 from `if len(mp) >= len(best_mp):` to `if len(mp) > len(best_mp):`; extend the regression-shield test with a darwin-platform mock (or a portable test helper that exercises both branches).

**Default decision**: defer to v2.1.3. Real platform asymmetry but D11 verdict scope was Linux-only at Phase 4 close; v2.1.3 is the appropriate window to extend.

#### BL-315 - v2.1.4: plugin-restamp-redact-wip.py atomic_io import path hardening

**Status (2026-05-10)**: RE-TARGETED v2.1.3 → v2.1.4. See BL-316.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 cross-cutting sweep-review.

**Source**: v2.1.1 cross-cutting sweep-review (2026-05-09; v2.1.3 candidate)

**Driver**: `plugins/launchpad/scripts/plugin-restamp-redact-wip.py:88` does `sys.path.insert(0, str(args.repo_root / "plugins" / "launchpad" / "scripts"))` and imports `atomic_io` from there. `args.repo_root` defaults to `Path.cwd()` and is otherwise user-supplied. If the script runs against a hostile clone (or any directory containing a planted `plugins/launchpad/scripts/atomic_io.py`), Python imports the planted module. Defense-in-depth issue — the script is a manual operator tool with low real-world severity, but the canonical fix is trivial.

**At v2.1.3 design time**: replace lines 88-89 with `sys.path.insert(0, str(Path(__file__).resolve().parent))` + `from atomic_io import atomic_write_replace`. Pins the import to the script's own installed directory regardless of caller-supplied `--repo-root`.

**Default decision**: defer to v2.1.3.

#### BL-316 - v2.1.2: Propagate hardened lefthook gates to consumer template via stack-adapter fragments

**Status (2026-05-10)**: SHIPPED in v2.1.2 — partial + tests in PR #65 Phase 1; production wiring in PR #65 Slice 4c.4 (`lp_bootstrap.stack_lefthook.enrich_lefthook_with_stacks`). Phase 1's partial was correctly authored but never reached real consumer scaffolds because `lefthook.yml.j2.outer` had zero production call sites (Codex P1-A on 75c44d6); Slice 4c.4 wires the stack-aware enrichment into `lp_bootstrap.engine`'s render-collect loop via `merge_keys_additive` so consumer `lefthook.yml` files actually inherit the gates.

**Source**: v2.1.1 ship retrospective (2026-05-09 evaluation) + v2.1.2 prep plan locked 2026-05-10 (Path B + Q1=(a) + Q2=(a)).

**Driver**: v2.1.1 hardened the maintainer's `lefthook.yml` with 7 Python gates (bandit, ruff-check, ruff-format-check, semgrep-general, semgrep-launchpad-internal, pyright, pytest) but consumer projects that install LaunchPad get NONE of this propagation. The plugin's `infrastructure/lefthook.yml.j2` template is unchanged by v2.1.1, and the stack-adapter fragments (e.g., `nextjs_fastapi/templates/lefthook.j2.fragment`) are no-ops. Maintainer-side gates also hardcode plugin-specific paths (`plugins/launchpad/scripts/`) and the `[ -d plugins/launchpad/scripts ] || exit 0` early-out, which would silently no-op in every consumer repo.

**At v2.1.2 design time**:

1. Edit `plugins/launchpad/scripts/plugin_stack_adapters/nextjs_fastapi/templates/lefthook.j2.fragment` to add 5 gates: bandit (no config), ruff-check (auto-discover), ruff-format-check (auto-discover), pyright (auto-discover via `[tool.pyright]`), pytest (auto-discover). **Each gate MUST include a `command -v <tool> >/dev/null || { echo 'GATE MISSING: <tool>' >&2; exit 1; }` preamble** — never silent no-op (per security-lens P2: silent-skip is a security regression masquerading as a gate). For bandit specifically: ship a minimal `[tool.bandit]` exclude list in `pyproject.toml.fragment` to avoid scanning vendored Python adjacent to `node_modules`.
2. SKIP semgrep-general (requires shipping rules YAML) + semgrep-launchpad-internal (plugin-specific, no meaning outside).
3. Append the 5 tools to `plugins/launchpad/scripts/plugin_stack_adapters/nextjs_fastapi/requirements.in.fragment` (or equivalent install-fragment surface) so consumers get them via `pip install -r requirements.in`. Consumers without Python in their stack are unaffected (fragment renders to no-op for non-Python stacks).
4. Add tests at `plugins/launchpad/scripts/tests/test_lefthook_template_python_gates.py` asserting the 5 gates appear in the rendered template for a Python-bearing stack.
5. Update `docs/architecture/CI_CD.md` + `docs/guides/CODE_REVIEW_LAYERS.md` with one-line cross-reference to the propagated gates.

**Per-stack scope (v2.1.2 only)**: nextjs_fastapi only. v2.2 fills additional Python-bearing stacks as those land.

**User-facing upgrade impact**: existing consumer projects on older LaunchPad will get NEW failing pre-commit gates after upgrade. v2.1.2 release notes (Phase 4) MUST document this as an upgrade impact + provide opt-out guidance (e.g., `lefthook.yml` skip block).

**Default decision**: ship in v2.1.2 (~3-4h main deliverable).

#### BL-317 - v2.1.x: Remove dead-code `validate_subject` from `plugin-restamp-history-hook.py:54-71`

**Status (2026-05-10)**: SHIPPED in v2.1.2 — see PR #65.

**Status (2026-05-10)**: NEW — surfaced by v2.1.1 sweep iteration 3 (blind simplicity reviewer); correctly suppressed under "pre-existing" rule. Will RIDE ALONG in v2.1.2 Phase 3.

**Source**: v2.1.1 PR #62 sweep iteration 3 (2026-05-09)

**Driver**: `validate_subject` was introduced in v2.0 commit `c563d81` with zero callers since. v2.1.1 only touched this file via ride-along ruff format (datetime.UTC import alias + whitespace). Cleanup opportunity. Verify zero callers via grep before removal; then delete the function and any associated tests.

**Default decision**: fold into v2.1.2 Phase 3 ride-alongs (~10min).

#### BL-318 - v2.1.x: Stale `v2.1.0` references in HOW_IT_WORKS.md + V2.2-CANDIDATES.md.j2

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 Slice I pre-flight pattern-finder review (specialist pass on plugin.json bump commit).

**Source**: v2.1.1 Slice I pre-flight dual-pass (2026-05-09)

**Driver**:

- `docs/guides/HOW_IT_WORKS.md:53` reads `… LaunchPad should appear with the version from `plugins/launchpad/.claude-plugin/plugin.json` (`2.1.0` at the time of writing) …`. The parenthetical is framed as a snapshot but produces user-visible staleness on every plugin version bump unless updated.
- `plugins/launchpad/scripts/plugin_default_generators/launchpad/V2.2-CANDIDATES.md.j2:5, :18` contain hardcoded `v2.1.0` strings inside a Jinja template that renders into `.harness/`/downstream output. Strings describe "the version of the plugin that performed the resolution"; coupling to live plugin version is ambiguous (could be (a) emitter-version-tracking → bump literals; (b) parameterize via `{{ plugin_version }}`; (c) leave-as-is since "v2.1.0" refers to the schema/dispatch generation that introduced the closed enum, not the runtime emitter).

**At v2.1.x design time**: HOW_IT_WORKS.md — bump literal to current version OR refactor to dynamic via includes/templating; V2.2-CANDIDATES.md.j2 — make explicit semantic decision (recommend (b) parameterize so emission tracks plugin.json automatically).

**Default decision**: defer to v2.1.x. Both are P2 staleness; not ship-blocking for v2.1.1.

#### BL-319 - v2.1.x: manifest-version-contract test (release-engineering invariant)

**Status (2026-05-10)**: SHIPPED in v2.1.2 — see PR #65.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 Slice I pre-flight testing-reviewer review.

**Source**: v2.1.1 Slice I pre-flight dual-pass (2026-05-09)

**Driver**: There is no test asserting `plugins/launchpad/.claude-plugin/plugin.json` `version` field is consistent with one or more of: (a) the latest `## [v<version>]` heading in `CHANGELOG.md`, (b) the presence of `docs/releases/v<version>.md`, (c) (at release time) a git tag matching `v<version>`. Such a test would have caught the v2.1.1 plugin.json scope miss + the missing `docs/releases/v2.1.1.md` scope miss at PHASE 5 plan-author time, not at Slice I pre-flight.

**At v2.1.x design time**: add a release-engineering invariant test under `plugins/launchpad/scripts/tests/` that:

1. Reads `plugin.json.version` (e.g., `2.1.1`)
2. Greps `CHANGELOG.md` for the latest `## [v<version>]` heading; asserts it matches.
3. Asserts `docs/releases/v<version>.md` exists and has a top-level `# ` heading.
4. (Optional, tag-time-only) asserts `git tag --list v<version>` returns exactly one match.

The `plugin-backlog-orphan-check.py` gate enforces a related (BL ↔ CHANGELOG) invariant; this test extends the same release-time-coupling discipline to plugin.json + release-notes.

**Default decision**: defer to v2.1.x. Process improvement, not user-impacting.

#### BL-320 - v2.1.x: Python hook bootstrap path documentation / auto-install

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 PR #62 Codex review (P1 #1).

**Source**: v2.1.1 PR #62 Codex automated review (2026-05-09)

**Driver**: The Phase 4 Layer 3 lefthook hooks (`pytest`, `pyright`, `bandit`, `ruff`, `semgrep`) call the tools directly. Consumer projects skip via the `[ -d plugins/launchpad/scripts ] || exit 0` early-out, but maintainer-side clean checkouts have no documented bootstrap — a fresh contributor cloning the repo will hit `command not found` on first commit. The required incantation is `cd plugins/launchpad/scripts && pip install --require-hashes -r requirements.txt`, but it is not surfaced anywhere user-visible (CLAUDE.md DoD, CONTRIBUTING.md, lefthook hook output).

**At v2.1.x design time**: pick one of:

1. **Documented manual** — add a `## Python tooling` section to CONTRIBUTING.md with the `pip install --require-hashes` recipe; reference from CLAUDE.md DoD line 96 and from a friendly lefthook hook error if `pytest`/`pyright`/`bandit`/`ruff`/`semgrep` not on PATH.
2. **Auto-bootstrap script** — `scripts/maintenance/install-python-tooling.sh` that creates a `.venv` under `plugins/launchpad/scripts/` and installs `requirements.txt`; lefthook entries source the venv. Requires shipping the venv-bootstrap convention to consumers OR keeping it self-host-only.
3. **Defer entirely** — accept the contributor-onboarding friction; the PEP 668 environment landscape on macOS Homebrew + Linux distros makes auto-pip-install fragile.

**Default decision**: defer to v2.1.x. Real onboarding gap but not v2.1.1-shipping-blocker. Pick path (1) at v2.1.x — minimum viable documentation.

#### BL-321 - v2.1.x: Synchronize `.harness/todos/*.md` frontmatter schema across all writer/reader docs

**Status (2026-05-10)**: SHIPPED in v2.1.2 — see PR #65.

**Status (2026-05-09)**: NEW — surfaced by v2.1.1 PR #62 Slice H.4 dual-pass (pattern-finder + architecture-strategist).

**Source**: v2.1.1 PR #62 dual-pass on Slice H.4 (2026-05-09)

**Driver**: Slice H.4 added a new `file:` field to the `.harness/todos/*.md` frontmatter schema documented at `lp-review.md:221`, consumed by `/lp-ship` Step 4.6.3 staged-diff scope filter (`lp-ship.md:124`). Three sibling consumer/producer docs still describe the pre-Slice-H.4 schema:

- `plugins/launchpad/agents/resolve/lp-harness-todo-resolver.md:14` — frontmatter list omits `file:`
- `plugins/launchpad/commands/lp-triage.md:23,42-46` — frontmatter validation list omits `file:`
- `plugins/launchpad/commands/lp-resolve-todo-parallel.md:30` — uses prose-body parsing for file refs (not frontmatter `file:`); could be tightened to use `file:` for primary file with prose-body fallback for secondary

Additionally, `lp-test-browser.md:103` is a SECOND writer of `.harness/todos/*.md` pending findings (alongside `lp-review.md`). Browser-test findings key on routes (e.g., `/dashboard/profile`), not source paths, so retrofitting `file:` requires a route → page-file derivation rule (e.g., `apps/web/src/app/{route}/page.tsx`).

**At v2.1.x design time**:

1. Update sibling reader docs (`lp-harness-todo-resolver.md`, `lp-triage.md`, `lp-resolve-todo-parallel.md`) to reflect the `file:` field in their frontmatter documentation.
2. Decide whether `lp-test-browser.md:103` should derive + emit `file:` from route, OR rely on the missing-field-tolerance fallback in `lp-ship.md:124` (Slice H.4 already documents this fallback as the v2.1.1 default).
3. (Optional) Add a single-source-of-truth schema doc at `docs/architecture/HARNESS_TODOS.md` enumerating all current frontmatter fields + their consumer contracts.

**Default decision**: defer to v2.1.x. v2.1.1 ships with the missing-field tolerance baked in; sibling-doc sync is documentation hygiene, not a runtime defect.

#### BL-322 - v2.1.x: Migrate to Prisma 7 (datasource URL → prisma.config.ts)

**Status (2026-05-10)**: NEW — Dependabot PR #54 (closed 2026-05-10) attempted Prisma 6.19.3 → 7.8.0 bump; fails on `schema.prisma` validation (P1012). NOT v2.1.2 scope.

**Source**: v2.1.1 post-ship dependabot triage (2026-05-10)

**Driver**: Prisma 7 dropped the `url` property from `schema.prisma` `datasource` block. Connection URLs must move to a new `prisma.config.ts` with either `adapter` (direct connection) or `accelerateUrl` (Accelerate to PrismaClient constructor). See https://pris.ly/d/config-datasource and https://pris.ly/d/prisma7-client-config. Migration is opt-in; not a drop-in bump.

**At v2.1.x design time**:

1. Author `packages/db/prisma.config.ts` with appropriate adapter (direct postgres connection most likely, given v2.0 monorepo template uses standard PG). **Verify the file reads connection strings via `process.env.DATABASE_URL` ONLY** — never literal — and update `.launchpad/secret-patterns.txt` (or gitleaks config) if `accelerateUrl` (with `?api_key=` query string) becomes in-scope.
2. Remove `url` from `packages/db/prisma/schema.prisma` `datasource` block.
3. Update `PrismaClient` instantiation in `packages/db/src/` to pass `adapter` config.
4. Verify `pnpm install` postinstall (which runs `prisma generate`) succeeds against migrated schema.
5. If LaunchPad scaffolds Prisma in any stack template, propagate the new pattern.

**Default decision**: defer to v2.1.x. Real migration work (~2-4h); not critical given Prisma 6.x is still supported.

#### BL-323 - v2.1.3: lefthook.yml multi-stack last-key-wins drop in outer renderer

**Status (2026-05-10)**: SUBSUMED by v2.1.2 Slice 4c.4 production wiring (PR #65). The runtime regression for multi-stack consumer scaffolds is closed natively because `lp_bootstrap.stack_lefthook.enrich_lefthook_with_stacks` routes through `merge_keys_additive` (additive map-merge, first-declared-wins on duplicate command names) rather than the test-only outer template's text concatenation — last-key-wins YAML drop is impossible by construction. Multi-stack `[nextjs_fastapi, astro]` parsed-YAML assertion added in `tests/test_lp_bootstrap_stack_lefthook.py::test_multi_stack_composition_runtime_yaml_keeps_all_gates` (both orderings). The outer template `lefthook.yml.j2.outer` remains test-only at v2.1.2 and is unused in production; v2.1.3 may delete it as dead code or refactor it to use the same merge helper.

**Status (2026-05-10)**: NEW — surfaced by Codex P1-B on PR #65 (v2.1.2). Real regression risk for multi-stack scaffolds that include `nextjs_fastapi`; deferred to v2.1.3 per locked v2.1.2 scope.

**Source**: PR #65 Codex re-review (2026-05-10; v2.1.3 candidate)

**Driver**: `plugins/launchpad/scripts/plugin_default_generators/stack_aware/lefthook.yml.j2.outer:1-3` is text concatenation (`{% for stack_id in selected_stack_ids %}{% include %}{% endfor %}`), NOT a structural YAML merge. Multiple stack fragments can declare the same top-level hook key (`pre-commit:`, `pre-push:`). PyYAML applies last-key-wins on duplicate keys, so e.g. rendering `["nextjs_fastapi", "astro"]` produces a `lefthook.yml` whose effective `pre-commit:` block is only `astro-noop` — silently dropping the v2.1.2 BL-316 bandit/ruff-check/ruff-format-check gates. The same issue exists for any pair where ≥2 stacks declare the same hook (currently `nextjs_standalone + astro`, `nextjs_standalone + generic`, etc.) but is benign pre-v2.1.2 because all such fragments shipped only `<stack>-noop: run: 'true'`. Test `test_composition_includes_python_gates_when_nextjs_fastapi_present` does substring-presence on raw rendered text by design (per its docstring), which doesn't catch the runtime drop. The `_COMPOSES_WITH` rules at `astro.py:73,82-83` and `nextjs_standalone.py:_COMPOSES_WITH` declare `lefthook.yml: merge-keys` as the intended `ConflictPolicy`, but no enforcement code wires `merge-keys` into the outer renderer at v2.1 — `grep -rn 'conflict_policy\[' plugins/launchpad/scripts/` returns zero matches.

**At v2.1.3 design time**:

1. Replace the outer template's text concatenation with a Python-side post-render YAML merge: render each `<stack>/templates/lefthook.j2.fragment` individually, `yaml.safe_load` each, deep-merge by hook key (top-level `pre-commit`/`pre-push`/`commit-msg`/etc.) → merge `commands:` dicts by command name → re-emit via `yaml.safe_dump`. Conflict policy on duplicate command name: first-declared-wins (matches outer template's existing comment "union-merge first-declared-wins").
2. Rewrite `test_composition_includes_python_gates_when_nextjs_fastapi_present` from substring-presence to parsed-YAML assertion (`yaml.safe_load(rendered)["pre-commit"]["commands"]` must contain all 5 gate names regardless of stack ordering).
3. Add new tests covering all 3 affected combos involving `nextjs_fastapi` (`+ astro`, `+ generic`, `+ nextjs_standalone`) in both orderings.
4. Snapshot test: assert single-stack `lefthook.yml` rendering is byte-identical before/after the renderer rewrite (no accidental regression for existing single-stack consumers).
5. Wire `merge-keys` `ConflictPolicy` enforcement into the outer renderer so the `_COMPOSES_WITH` declarations become load-bearing instead of documentation-only.

**Default decision**: defer to v2.1.3. Real but narrow regression (only multi-stack scaffolds involving `nextjs_fastapi` with the unlucky stack ordering); single-stack consumers (the dominant case at v2.1.x) unaffected. Fix is architectural (~1.5–2h with tests) and warrants its own dedicated commit cycle outside v2.1.2's locked scope.

#### BL-324 - v2.1.4: Layer-aware Python workspace probe in shared `_python_gates` partial

**Status (2026-05-10)**: NEW — surfaced by Codex P2 on PR #65 (v2.1.2). Edge case at v2.1 (no layer overrides yet shipped); deferred to v2.1.4 to ride along with broader stack-adapter layer-override work.

**Source**: PR #65 Codex re-review (2026-05-10; v2.1.4 candidate)

**Driver**: `plugins/launchpad/scripts/plugin_stack_adapters/_partials/_python_gates.j2.fragment:18,38` hardcodes the Python workspace probe order to `apps/api → api → silent-skip`. The `nextjs_fastapi` adapter contract permits custom FastAPI placement via layer-path overrides (e.g. `fastapi: services/api`), so a valid scaffold with a non-default layer path silently skips `pyright` and `pytest` even though the workspace exists at the configured path.

**At v2.1.4 design time**:

1. Read the actual Python workspace path from the scaffold receipt (or whatever post-`/lp-scaffold-stack` artifact records resolved layer paths) and render that path into the partial via a Jinja `python_workspace` arg.
2. Fallback: when the receipt is unavailable (e.g. ad-hoc render outside the pipeline), retain current `apps/api → api → silent-skip` probe order for compatibility.
3. Tests: (a) override path resolves correctly and `pyright`/`pytest` target it; (b) fallback ordering still works when no override is present; (c) error or fail-loud when the configured override path doesn't exist post-scaffold (don't silently skip).

**Default decision**: defer to v2.1.4. v2.1 doesn't ship layer overrides yet, so the regression is theoretical at v2.1.x; v2.1.4 is the natural window when layer-override work lands.
