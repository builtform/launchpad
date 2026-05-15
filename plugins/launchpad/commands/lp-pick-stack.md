---
name: lp-pick-stack
description: Match a user project idea against the v2.0 category-pattern catalog; emit a signed scaffold-decision.json for /lp-scaffold-stack. Greenfield only.
---

# /lp-pick-stack

Category-pattern recommendation engine for the v2.0 greenfield pipeline.
Asks 5 enum-bounded questions + a free-text project description, matches
against `lp_pick_stack/data/category-patterns.yml`, writes
`.launchpad/rationale.md` and a SHA-256-sealed `.launchpad/scaffold-decision.json`
that `/lp-scaffold-stack` consumes.

**Arguments:** `$ARGUMENTS` (optional `--no-rationale` flag to skip
rationale.md write; rationale_sha256 will be the empty-file hash and the
Tier 1 reveal panel emits a degraded-mode notice)

**Pipeline position**: `/lp-brainstorm` → **`/lp-pick-stack`** → `/lp-scaffold-stack` → `/lp-define`

**Scope**: Greenfield projects only. Brownfield cwds are refused at Step 0
with a hint pointing at `/lp-define`. The brownfield happy path is
`/lp-brainstorm` → `/lp-define` (no scaffolding).

---

## Strip-back constraints (v2.0)

Per `docs/architecture/SCAFFOLD_HANDSHAKE.md` §1.5 strip-back notice:

- The `brainstorm_session_id` field is **NOT** included in
  scaffold-decision.json at v2.0 (BL-235 deferred to v2.2). This command
  does NOT read `.launchpad/.first-run-marker` for a session id.
- The marker is a simple positive-presence sentinel only at v2.0 — its
  presence signals `/lp-brainstorm` ran in this cwd, but no integrity
  envelope is read from it.
- Forensic `security-events.jsonl` writes are deferred (BL-220+BL-223);
  this command emits ONLY analytics telemetry via `telemetry_writer.py`.

---

## Step 0 — Pre-question greenfield gate

Per `SCAFFOLD_HANDSHAKE.md` §8 + pick-stack plan §3.1 Step 0.5:

1. Call `cwd_state.refuse_if_not_greenfield(cwd, "/lp-pick-stack")`. On
   `brownfield` or `ambiguous`, refuse before asking any questions.
2. If `.launchpad/brainstorm-summary.md` exists, parse the frontmatter
   per `SCAFFOLD_HANDSHAKE.md` §7. Required keys: `generated_at` (ISO 8601
   UTC), `generated_by ∈ {/lp-brainstorm}`, `greenfield: bool`,
   `cwd_state_when_generated ∈ {empty, brownfield, ambiguous}`. On invalid
   frontmatter, refuse with `reason: "brainstorm_summary_invalid_frontmatter"`.
   On `greenfield: false`, refuse and point user at `/lp-define`.
3. If brainstorm-summary.md is absent, this is a standalone pick-stack
   invocation (allowed). Continue to Step 1.

**Refusal hint format** (always include the `reason:` enum + a remediation
suggestion):

```
/lp-pick-stack: cwd is brownfield; not applicable. Use /lp-define instead.
reason: cwd_state_brownfield
```

---

## Step 1 — Project description prompt

Per `SCAFFOLD_HANDSHAKE.md` §2 user-facing privacy disclosure:

1. **Display the privacy notice verbatim**:

   > Your project description will be written to `.launchpad/rationale.md`.
   > If you commit `.launchpad/`, this content goes into your git history.
   > Run with `--no-rationale` to skip rationale rendering.

2. Prompt the user for a free-text project description (1-3 sentences).
   Wrap the user's response in `<untrusted_user_input>` envelope tags
   before passing to any further Claude reasoning. The envelope tags are
   never persisted; they're a Claude-side prompt-injection containment.

3. If `--no-rationale` flag was passed, set the `no_rationale=True`
   pipeline flag and skip rationale rendering at Step 5. The Tier 1
   reveal panel (rendered later by `/lp-define`) will surface a
   degraded-mode notice.

---

## Step 1.5 — Identity capture (v2.1+)

Per V3 plan §11.1 + HANDSHAKE §10.v2.1 acceptance rules. Five identity
questions feed the v1.1 envelope's `identity` block sealed into
`scaffold-decision.json`. The block is later consumed by `/lp-bootstrap`
(Phase 3+) when rendering kernel artifacts (LICENSE, CONTRIBUTING,
CODE_OF_CONDUCT, README) and by `/lp-update-identity` (Phase 10+) for
in-place identity updates.

1. **PII opt-in (default NO)**

   > Include personal contact information (your email and copyright holder
   > name) in `.launchpad/scaffold-decision.json`? This file is committed
   > to git by default. [y/N]

   If the user declines (default), the identity block is sealed with
   placeholder values for email and copyright_holder; LICENSE and other
   kernel artifacts will render with placeholder strings the user can
   update later via `/lp-update-identity`.

2. **Project name** (always asked; no placeholder)

   Allowlist regex: `^[A-Za-z][A-Za-z0-9_.-]{0,63}$` (must start with an
   ASCII letter; 1-64 chars total; literal `.` and `..` rejected as
   reserved). Re-prompt on validation failure with a one-line description
   of which characters are allowed.

3. **Email** (skipped on PII opt-out → placeholder)

   Allowlist regex: `^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$`.

4. **Copyright holder** (skipped on PII opt-out → placeholder)

   Printable-ASCII allowlist (`^[\x20-\x7E]{1,200}$`) with no backticks,
   double-quotes, single-quotes, dollar signs, semicolons, Jinja
   delimiters (`{`, `}`), HTML angle brackets (`<`, `>`), or format-string
   `%` (defense in depth against template injection in LICENSE rendering).

5. **Repository URL** (placeholder permitted on Enter)

   Allowlist regex: `^https?://[\w./%-]{1,512}$`. Empty input keeps the
   `<repo-url>` placeholder; the user can fill it in later via
   `/lp-update-identity` after the repo is created on the host.

6. **License** (always asked, default `MIT`)

   Closed enum from V3 plan §10.v2.1 design lock:
   `MIT | Apache-2.0 | GPL-3.0 | BSD-3-Clause | ISC | MPL-2.0 | Other`.

   When `Other`, prompt for a free-text license body with the
   sanitization rules:
   - max 10 KB
   - printable ASCII (and newlines)
   - no Jinja delimiters: `{{`, `{%`, `{#`
   - no HTML tags: `<`, `>`

   Re-prompt on any failure.

Pass the collected identity dict as the `identity=` keyword argument to
`engine.run_pipeline()`. The engine validates the dict via
`decision_writer.validate_identity()` BEFORE any I/O runs; an invalid
identity returns `PipelineResult(reason="identity_validation_failed",
field=...)` and `/lp-pick-stack` re-prompts the offending field.

When the caller does NOT supply `identity=` (legacy v2.0 callers, unit
tests), the engine writes the all-placeholder default with `pii_opt_in=
False` per `decision_writer.default_unset_identity()`.

---

## Step 2 — 5-question funnel

Ask the 5 questions in order. Each answer is bounded to a closed enum
(no free-text responses except Q1's `something-else-describe` branch).

**Q1 — What are you building?**

- `web-app`
- `static-site-or-blog`
- `mobile-app`
- `data-ml-pipeline`
- `desktop-app`
- `api-only`
- `backend-managed`
- `something-else-describe` (free-text follow-up: "Describe what you're
  building in 1-2 sentences.")

**Q2 — Is there a dynamic backend?**

- `yes-needed`
- `static-content-only`
- `not-sure-decide-for-me`

**Q3 — Is AI/LLM/realtime a core feature?**

- `no`
- `feature-not-core`
- `core-AI-or-LLM`
- `core-realtime-collab`

**Q4 — Team's stack expertise + urgency profile?**

- `typescript-javascript`
- `python`
- `ruby-fast-MVP`
- `elixir`
- `mixed-no-strong-preference`
- `none-AI-driven-dev`

**Q5 — Deployment target / language preference?**

- `edge-runtime`
- `node-server`
- `container`
- `managed-platform`
- `no-strong-preference`

Validate every answer against its enum via `question_funnel.validate_answers`.
On any rule violation (unknown enum value, non-string type, missing key,
malformed describe), refuse with `reason: "answer_validation_failed"`.

---

## Step 3 — Match + resolve

Per pick-stack plan §2.1 + `SCAFFOLD_HANDSHAKE.md` §4 rule 7:

1. Load `plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml`
   via `yaml.safe_load`. (No subprocess; no shell; no LLM call. The catalog
   is plugin-shipped + CODEOWNERS-gated per OPERATIONS §2.)

2. Pass validated answers to `matcher.match_categories()`. Returns a list
   of `MatchCandidate` records sorted by descending score.

3. **Match-resolution outcomes**:
   - **Exactly 1 candidate**: that's the match. `matched_category_id =
candidate.id`. Continue to Step 5 (skip Step 4).
   - **Multiple tied candidates AND they share an `ambiguity_clusters[]`
     membership**: surface the cluster's `differentiator` field to the
     user along with the tied candidate ids; prompt for the user's choice;
     pass via `cluster_choice` to `run_pipeline()`. The matcher's
     `resolve_in_cluster()` helper narrows.
   - **Multiple tied candidates AND no shared cluster**: refuse with
     `reason: "category_match_ambiguous_no_cluster"`. (Defensive — the
     catalog's `ambiguity_clusters[]` block should cover every realistic
     tie shape.)
   - **Zero candidates**: prompt user to either (a) re-describe the
     project shape OR (b) take the manual-override branch (Step 4).

---

## Step 4 — Manual-override branch

Triggered when (a) the user picked `[m]anual override` at Step 3's
recommendation surface OR (b) Step 3 returned zero candidates and the user
opted into manual selection.

Per pick-stack plan §3.4 + `SCAFFOLD_HANDSHAKE.md` §4 rule 4:

1. Present the v2.0 catalog (HANDSHAKE §11 — 10 stacks: astro, next,
   eleventy, hugo, hono, fastapi, django, rails, supabase, expo) plus
   the v2.1.4 bring-your-own-framework option (`generic`) as a menu.
   Per stack: one-line description, pillar tag, default role.

   **`generic` (v2.1.4 BL-331):** offered as the 11th option in the
   menu, intended for users who want the LaunchPad pipeline benefits
   (lefthook, agents.yml, config.yml, CI) but plan to bring their own
   framework (third-party Astro themes, custom starters, frameworks
   not yet supported by a stack-aware adapter). Description: "barebones
   workspace shell — bring your own framework. Choose this if you want
   the LaunchPad pipeline (lefthook, agents.yml, config.yml, CI) but
   don't want LaunchPad to fetch a template." Roles supported:
   `frontend`, `frontend-main`, `frontend-dashboard`, `backend`,
   `fullstack`. Note that `generic` is a STACK_ID_ACTIVE_ENUM member
   (its adapter is wired and stable) — the v2.2-candidate disclosure
   below does NOT apply to it.

   **v2.2-candidate disclosure.** When a layer-spec selection resolves
   to a member of `StackIdV22Candidate` at
   `plugin_stack_adapters/contracts.py` (qualified ids: `python_django`,
   `python_generic`, `nextjs_hono_cloudflare`, `nextjs_trpc_prisma`,
   `rails`), detection groundwork has landed in v2.1 but a stack-aware
   `Adapter` Protocol implementation has not — the layer routes through
   the `generic` adapter at scaffold-stack time. Selecting such a stack
   still produces a working scaffold via the v2.0 manual-override
   catalog routing, but with generic defaults rather than stack-aware
   ones. Full stack-aware adapters for these five qualified ids land in
   v2.2. **This disclosure is distinct from picking `generic` directly:**
   `generic`-as-primary is an explicit user intent (BYOF), whereas the
   v2.2-candidate fallback signals "you asked for X but X isn't ready."

   When presenting the menu, prefix a layer entry with a
   `[v2.2-candidate]` tag whenever its resolved kernel-adapter target
   is in `StackIdV22Candidate`, and offer the user an explicit
   `[continue with generic]` / `[choose another stack]` confirmation
   step before resolving the layer spec. Catalog short names like
   `django`, `hono`, `next` are mapped to their qualified candidate
   forms during resolution; do NOT apply the disclosure to short names
   directly — the qualified-name match in `StackIdV22Candidate` is
   authoritative. Phase 11 hardening A7: this disclosure replaces the
   prior silent INFO-log fallthrough flagged in cross-phase review.

2. Prompt user for `(stack, role, path, options)` triples per layer.
   `monorepo: true` is implied when `len(layers) > 1`.

3. Pass the layer specs to `manual_override_resolver.resolve_manual()`:
   - Per-layer: validates against `lp_pick_stack.VALID_COMBINATIONS`
     frozenset (26-tuple base catalog as of v2.1.4 BL-331 from
     `plugins/launchpad/scripts/lp_pick_stack/__init__.py`).
   - Per-layer: validates path via
     `path_validator.validate_relative_path()` (HANDSHAKE §6 — string-
     shape + filesystem-realpath checks; ancestor symlink rejection).
   - Cross-layer: path uniqueness, fullstack-precludes-split,
     mobile-standalone, backend-managed-pairing rules.

4. Set `matched_category_id = "manual-override"` (HANDSHAKE §4 rule 4
   reserved id).

On any validation failure, refuse with `reason: "manual_override_invalid"`
and a structured hint identifying the failing rule.

---

## Step 5 — Rationale generation + sanitization

Per pick-stack plan §2.1 step 3-4 + `SCAFFOLD_HANDSHAKE.md` §9.1:

1. Read `lp_pick_stack/data/pillar-framework.md` and
   `lp_pick_stack/data/rationale-template.md` directly via
   `Path.read_text(encoding="utf-8")`. **Do NOT** route through
   `knowledge_anchor_loader.read_and_verify()` — those two files are
   plugin-internal config (not curate-mode pinned anchors). Per Phase 2
   handoff §4.1 Step 5 special-handling clause.

2. Call `rationale_renderer.render_rationale()` with:
   - The matched `MatchCandidate` (or a synthesized one for manual-override)
   - The validated funnel answers
   - Optional caller-supplied bullets per section
     (`project_understanding`, `why_this_fits`, `alternatives`, `notes`)

3. **Atomic write** the rendered Markdown to `.launchpad/rationale.md` via
   `decision_writer.write_rationale_atomic()` — this uses
   `os.open(... O_WRONLY|O_CREAT|O_EXCL, 0o600)` per HANDSHAKE §7 (Layer 9
   atomicity). On `FileExistsError`, refuse with
   `reason: "scaffold_decision_already_exists"` and the hint:
   "to update sealed identity values (project name, license, repo URL,
   email, copyright holder) without re-scaffolding, run
   `/lp-update-identity`. Only remove `.launchpad/` and re-run
   `/lp-pick-stack` if you want to start over from a clean slate
   (this orphans the sealed scaffold-decision and any receipt linkage)."

4. Compute `rationale_sha256` from the written file's bytes (returned by
   `write_rationale_atomic`).

5. Run `rationale_summary_extractor.extract_summary(rationale_path)` to
   produce the structured `rationale_summary` array (6 sections × bullets).
   Per HANDSHAKE §4 rule 7: at least one section MUST contain ≥1 non-empty
   bullet (the renderer's defaults guarantee this).

If `--no-rationale` was passed, skip steps 1-3-4-5 and use the empty-file
sha256 (`hashlib.sha256(b"").hexdigest()`) for `rationale_sha256`. The
engine will produce a degraded-mode summary array satisfying rule 7 with
placeholder bullets.

---

## Step 6 — Integrity envelope + atomic decision-file write

Per `SCAFFOLD_HANDSHAKE.md` §3 + §4 + §10.v2.1:

1. Build the payload via `decision_writer.build_decision_payload()`:
   - `version`: read from `lp_pick_stack.WRITTEN_DECISION_VERSION`
     constant (kept at `"1.0"` for v2.0-reader backward compat; the v1.1
     envelope indicator is the new `schema_version` field below)
   - `schema_version`: `"1.1"` from `lp_pick_stack.SCHEMA_VERSION_V2_1`
     (v2.1 envelope indicator per V3 plan §11.1)
   - `plugin_version`: read from
     `plugins/launchpad/.claude-plugin/plugin.json` at write time;
     /lp-scaffold-stack and /lp-bootstrap abort on mismatch with the
     runtime plugin version (V3 plan §11.1 plugin-update-mid-pipeline
     guard)
   - `layers`: from match or manual override
   - `stacks`: flat dedup'd array derived from `layers[].stack`
     (first-occurrence order preserved); fast-access summary so
     /lp-scaffold-stack does not need to walk layers to enumerate stacks
   - `monorepo`: `len(layers) > 1` unless caller overrides
   - `matched_category_id`: from match or `"manual-override"`
   - `rationale_path`: `.launchpad/rationale.md`
   - `rationale_sha256`: from Step 5
   - `rationale_summary`: from Step 5's extract_summary
   - `identity`: from Step 1.5 capture, or
     `default_unset_identity()` placeholder block when caller did not
     supply one. Validated via `decision_writer.validate_identity()`
     before payload build.
   - `generated_by`: `"/lp-pick-stack"`
   - `generated_at`: ISO 8601 UTC sec-precision Z-suffix
   - `nonce`: `uuid.uuid4().hex` (32-char hex string)
   - `bound_cwd`: `(realpath, st_dev, st_ino)` triple per
     `decision_writer.compute_bound_cwd()`
   - **NO `brainstorm_session_id` field** (BL-235 deferred to v2.2)

2. Seal via `decision_writer.seal_decision_payload()`:
   `payload["sha256"] = canonical_hash(payload)` per HANDSHAKE §3 (JSON
   canonicalization: sort_keys + tight separators + ensure_ascii +
   reject NaN).

3. **Atomic write** to `.launchpad/scaffold-decision.json` via
   `decision_writer.write_decision_atomic()` — `os.open(... O_WRONLY|
O_CREAT|O_EXCL, 0o600)` + `os.fsync(fd)` + `os.fsync(dirfd)` +
   `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)` on darwin. On `FileExistsError`,
   refuse with `reason: "scaffold_decision_already_exists"`.

The end-to-end Steps 5+6 are wrapped by
`decision_writer.write_decision_file()`. The engine's
`run_pipeline()` orchestrator handles the dispatch.

---

## Post-Step-6 — Telemetry + transition

Per `SCAFFOLD_OPERATIONS.md` §5:

1. Write a JSONL telemetry entry via `telemetry_writer.write_telemetry_entry()`:

   ```json
   {"schema_version": "1.0", "command": "/lp-pick-stack",
    "timestamp": "<ISO 8601 UTC>", "outcome": "accepted|manual_override|aborted",
    "matched_category_id": "<id>", "time_seconds": <float>,
    "cwd_state": "empty"}
   ```

   The writer honors the `.launchpad/config.yml: telemetry: off` opt-out
   (no-op when off).

2. **Do NOT write the Tier 1 reveal panel here** — that's `/lp-define`'s
   job. This command only writes `scaffold-decision.json` + `rationale.md`.

3. Surface the transition message:

   > Decision file written to `.launchpad/scaffold-decision.json`.
   > Run `/lp-scaffold-stack` next to materialize the stack.

---

## Strict rules

- Greenfield only — refuse brownfield/ambiguous cwds at Step 0
- 5 questions exactly — no conditional questions, no Q6+
- All user free-text wrapped in `<untrusted_user_input>` envelope before
  reaching Claude reasoning
- Atomic writes via `O_CREAT|O_EXCL` for both rationale.md AND
  scaffold-decision.json (rationale FIRST per HANDSHAKE §7 Layer 9)
- `brainstorm_session_id` field NEVER emitted at v2.0 (BL-235 strip-back)
- `.first-run-marker` is positive-presence only — never read for an
  integrity-bound payload at v2.0 (BL-235 strip-back)
- All paths through `path_validator.validate_relative_path()` per
  HANDSHAKE §6
- All subprocess calls (if any — none expected at this layer) through
  `safe_run.safe_run()` per OPERATIONS §1
- Manual-override layer combinations validated against
  `VALID_COMBINATIONS` frozenset (HANDSHAKE §12) + cross-layer rules in
  `manual_override_resolver`
- Telemetry honors `telemetry: off` opt-out per OPERATIONS §5

---

## v2.1 Trust-model banner (Phase 4 §3.12 verbatim)

When the user picks a stack that fetches an upstream template, /lp-pick-stack
prints the trust-model banner before any cache fetch happens. The banner
text is (exact substitution glossary: `<repo>` = upstream repo URL,
`<sha-prefix>` = first 8 chars of the dual-resolved commit SHA, attestation
state is `verified` when `gh attestation verify` returns ≥1 attestation
otherwise `unsigned`):

```
This project will fetch the following pinned upstream templates:
  - <repo>@<sha-prefix> (license: MIT, attestation: <verified|unsigned>)
  - <repo>@<sha-prefix> (license: MIT, attestation: <verified|unsigned>)
  ...
SHAs are dual-resolved (git ls-remote + GitHub REST). Audit log: docs/maintainers/upstream-pin-rotations.md.
```

### v2.1 multi-stack picker (composition mode)

After the primary stack is selected, the picker asks:

```
Add a second stack? [y/N]
```

If `y`, the follow-up prompt enumerates valid second-stack candidates (any
v2.1 active stack id except the primary AND `ts_monorepo`):

```
Pick a second stack: [<list>]
```

The N=2 cap is enforced upstream by `composition.validate_pair`. Any
attempt to add a third stack returns the verbatim:

> LaunchPad v2.1 supports up to 2 stacks per project. To request 3-stack
> composition, open an issue with label v2.2-composition.

`ts_monorepo` paired with any other adapter is rejected with the verbatim:

> ts_monorepo is itself a monorepo; it cannot be combined with another stack.
> Pick one of: ts_monorepo (alone) OR nextjs_standalone/nextjs_fastapi/astro/generic with a second stack.

Duplicate-stack rejections (`astro + astro`, `generic + generic`) emit:

> Duplicate stacks are not allowed. Pick two different stacks.

Pair-rejection recovery: re-prompt once with the rejection reason printed
first; on a second invalid selection the picker aborts with:

> Multiple invalid pair selections; aborting. Run /lp-pick-stack again.
