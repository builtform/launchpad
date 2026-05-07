---
name: lp-scaffold-stack
description: Consume scaffold-decision.json, materialize the chosen stack layers, and write scaffold-receipt.json for /lp-define. Greenfield-only; refuses on brownfield/ambiguous cwd.
---

# /lp-scaffold-stack

Consumer half of the v2.0 greenfield pipeline. Reads the integrity-bound
`.launchpad/scaffold-decision.json` produced by `/lp-pick-stack`, validates
it against all 12 active `SCAFFOLD_HANDSHAKE.md` §4 rules (rule 12 deferred
to v2.2 per BL-235), runs each layer's scaffolder via `safe_run`, and writes
`.launchpad/scaffold-receipt.json` for `/lp-define` to consume.

**Arguments:** none. The command discovers the decision file at the
canonical path `.launchpad/scaffold-decision.json`.

**Strip-back constraints (HANDSHAKE §1.5):**

- Validation rule 12 (`brainstorm_session_id`) is BL-235 deferred — Phase 3
  does NOT enforce it.
- The `.first-run-marker` is consumed via simple `os.rename` to
  `.first-run-marker.consumed.<iso-sec-ts>` — no JSON envelope, no sha256,
  no `bound_cwd` check (BL-235 deferred).
- The `recovery_commands` array in `scaffold-failed-<ts>.json` is a
  forward-compat hint at v2.0 — humans consume `recommended_recovery_action`
  prose and `see_recovery_doc` URL. Closed-enum + denylist + idempotency +
  sha256-self-hash + `.recovery.lock` + at-most-one-rerun are BL-231 deferred.
  Write-time destructive-path denylist DOES apply (refuses to write entries
  with forbidden paths).

---

## Phase 0: Pre-validation greenfield gate

Call `cwd_state.refuse_if_not_greenfield(cwd, "/lp-scaffold-stack")`. Refusal
on `brownfield` AND `ambiguous`. The refusal emits a `scaffold-rejection-<ts>.jsonl`
forensic record under `.harness/observations/` with `reason: "cwd_state_brownfield"`
or `reason: "cwd_state_ambiguous"`.

Read `.launchpad/.first-run-marker` if present; absence routes the engine
through the slow-path nonce-ledger check (no fast-path empty-ledger
authorization at v2.0 — BL-235 deferred). The marker exists only when
`/lp-brainstorm` ran in this cwd with `cwd_state == "empty"`.

## Phase 1: Decision file load + 12-rule validation

Read `.launchpad/scaffold-decision.json` via `Path.read_text()` (no
subprocess indirection). JSON parse failures emit
`reason: "scaffold_decision_invalid_json"`.

Run `lp_scaffold_stack.decision_validator.validate_decision()` with the
loaded scaffolders catalog + category-patterns ids. Each rule failure
produces a distinct `reason:` enum value:

- **Rule 1 — version**: ∈ `EXPECTED_DECISION_VERSION`. Unknown → `version_unsupported`
  - `seen_version` field + remediation hint "delete `.launchpad/scaffold-decision.json`
    and re-run `/lp-pick-stack`."
- **Rule 2 — layers**: each layer's `stack` ∈ scaffolders.yml keys; `role` ∈
  `ALLOWED_ROLES`; `path` passes the §6 path validator (re-validated at
  execute-time per Layer 8 closure); two layers cannot share `path`;
  `options` keys allowlisted per the scaffolder's `options_schema`.
- **Rule 3 — monorepo**: boolean. `true` → `layers.length >= 2`; `false` →
  `layers.length == 1` OR all layers share `path == "."`.
- **Rule 4 — matched_category_id**: ∈ category-patterns.yml keys OR
  `"manual-override"`.
- **Rule 5 — rationale_path**: equals `.launchpad/rationale.md` exactly.
- **Rule 6 — rationale_sha256**: equals SHA-256 of the file at rationale_path.
  Re-computed at read.
- **Rule 7 — rationale_summary**: present; AT LEAST one section has ≥1
  non-empty bullet; sanitization filter compliance per HANDSHAKE §9.1
  (re-applies the FORBIDDEN_BULLET_RE + 240-char cap).
- **Rule 8 — generated_by**: equals `"/lp-pick-stack"` exactly.
- **Rule 9 — generated_at**: ISO 8601 UTC with `Z` suffix; ≤ 4 hours old.
- **Rule 10 — nonce**: UUIDv4 hex format; not previously seen in
  `.launchpad/.scaffold-nonces.log` (live ledger ∪ in-window `.bak` files
  per backward-NTP `max(filename_ts, file_ctime)` rule).
- **Rule 11 — bound_cwd**: triple `(realpath, st_dev, st_ino)` recomputed
  via `os.path.realpath` + `os.stat`. ALL THREE must match. Distinguishes
  UX (`bound_cwd_realpath_changed_inode_match`) from attack
  (`bound_cwd_inode_mismatch`).
- **Rule 12 — brainstorm_session_id**: **DEFERRED to v2.2 per BL-235.
  SKIP THIS RULE at v2.0.**
- **Rule 13 — sha256**: equals `canonical_hash` of payload with `sha256`
  field removed. Mismatch → `sha256_mismatch`.

On any rule failure: emit `scaffold-rejection-<ts>.jsonl` per the inline
Layer 8/9 protocol (see Phase 4 below). NO subprocess executes.

## Phase 2: Marker consumption

If `.launchpad/.first-run-marker` exists: `os.rename(.first-run-marker,
.first-run-marker.consumed.<iso-sec-ts>)` per Layer 7 strip-back substitute.
No FD-based read, no pre-rename re-stat, no payload parse.

On rename failure (e.g., file gone): proceed without consumption (race or
stale marker; not a hard error at v2.0).

Retain at most 5 most-recent `.first-run-marker.consumed.<ts>` files;
older ones unlinked under no lock (single-process invocation model).

## Phase 3: v2.1 adapter dispatch

v2.1.0 ships the **v2.1 Adapter Protocol** in production. The engine
calls `dispatch_by_stack_ids(decision["stacks"], cwd,
accept_v22_fallback=...)` from
`lp_scaffold_stack.v21_adapter_dispatch`; the legacy v2.0 per-layer
`scaffolders.yml`-driven dispatch (`type: "orchestrate"` / `"curate"`)
and the `layer_materializer` module are **deleted** per the v2.1.0
completion plan §3.6.

Behavior:

- `len(stacks) == 1` → `dispatch_single_adapter(adapter, workspace_dir)`.
  The adapter handles its own workspace shape (e.g. `nextjs_fastapi`'s
  `workspace_source_map_single` lifts subtrees to `apps/`).
- `len(stacks) >= 2` → `dispatch_composition(adapters, composition_root)`.
  N=2 cap enforced upstream by `composition.validate_pair`.
- v2.2-candidate stack-ids (`python_django`, `python_generic`,
  `nextjs_hono_cloudflare`, `nextjs_trpc_prisma`, `rails`) hard-fail
  by default with `Rejected(reason="v22_candidate_unsupported")`.
  Pass `accept_v22_fallback=True` (kwarg only — `/lp-scaffold-stack`
  is invoked from Claude Code's slash-command machinery, no shell CLI
  flag) to route via the `generic` adapter; the receipt records the
  fallback in `adapter_dispatch_meta.fallback_ids`.

Cleanup contract on dispatch failure:

- **Composition mode** (`CompositionAbortError`): `composition._rollback`
  drains `placed_paths` + the `.lp-tmp/` tempdir on its own failure
  path. No engine-side cleanup needed.
- **Single-adapter mode** (`ScaffoldStepFailedError`): the adapter's
  own `scaffold_into` is responsible for tempdir cleanup. The engine
  logs the path in the recovery record for forensic inspection but
  does NOT auto-clean (preserves the user's ability to inspect
  partial state).

`materialized_files` is captured by walking the post-dispatch
workspace via `lp_scaffold_stack.dispatch_enumeration.enumerate_files`
— symlink-escape, oversized walks, and out-of-tree paths are filtered
or rejected, never silently included. Trust boundary: adapter output
is treated as untrusted.

## Phase 4: Cross-cutting wiring + secret-scan

For monorepo layouts (≥2 layers under apps/packages/services/supabase):

- Generate `pnpm-workspace.yaml` (atomic `O_CREAT|O_EXCL` write per file).
- Generate `turbo.json` with the standard task tree (build, test, lint,
  typecheck).
- On collision (any file exists): emit `scaffold-failed-<ts>.json` with
  `reason: "cross_cutting_wiring_collision"`.

Always:

- Generate `lefthook.yml` with the 4 standard hooks (`secret-scan`,
  `structure-drift`, `typecheck`, `lint`) — toolchain-specific commands
  for node/python/ruby/go.
- Detect toolchains (`node`, `python`, `ruby`, `go`) from layer stack ids.
- Run a basic regex secret-scan over materialized files — if any pattern
  matches (OpenAI keys, AWS keys, GitHub PATs, PEM blocks): emit
  `scaffold-failed-<ts>.json` with `reason: "secret_scan_failed"`.

## Phase 4.5: Kernel render + scaffold-decision re-seal (Phase 10 v2.1 DA7-flipped)

After Phase 4 cross-cutting wiring lands and BEFORE Phase 5a receipt
write, the engine writes the `.scaffold-stack-in-progress` sentinel
(via `lp_scaffold_stack/sentinel.py:write_sentinel`) and invokes
`KernelRenderer.render_all(cwd, identity)`. The engine then re-seals
`scaffold-decision.json` with the populated `kernel_render_state` via a
single `re_seal_decision_atomic` invocation routed through
`mark_kernel_seeded()` (the single-owner ratchet helper) — see
`engine.py` `_seal_kernel_render_state` closure. Per the v2.1.0
completion plan §3.5 single-seal prescription: there is exactly ONE
`re_seal_decision_atomic` call per pipeline run; the sentinel is
cleared in the `finally` block AFTER the receipt is written.

Bidirectional cross-detect: `/lp-bootstrap` and `/lp-update-identity`
refuse on a live scaffold-stack sentinel (per Phase 10 cycle-2 F9 +
cycle-3 P2-2 lock).

## Phase 5a: Receipt write

Build the payload per HANDSHAKE §5 schema:

```python
{
  "version": <lp_scaffold_stack.WRITTEN_RECEIPT_VERSION>,  # bumps from rc to final at Phase 7.5
  "scaffolded_at": "<ISO 8601 UTC>",
  "decision_sha256": "<sha256 of input scaffold-decision.json bytes>",
  "decision_nonce": "<UUID4 hex from input>",
  "layers_materialized": [
      {"stack": ..., "path": ..., "role": ...,
       "adapter_used": "<resolved adapter id>",  # "generic" when v2.2-candidate fallback
       "files_created": [...]},
      ...
  ],
  # When `accept_v22_fallback=True` and any v2.2-candidate stack-id
  # routed via the generic adapter, the receipt also carries:
  "adapter_dispatch_meta": {"fallback_ids": [...]},
  "cross_cutting_files": ["pnpm-workspace.yaml", "turbo.json", "lefthook.yml", ...],
  "toolchains_detected": ["node", "python", ...],
  "secret_scan_passed": True | False,
  "tier1_governance_summary": {
      "whitelisted_paths": null,             # /lp-define computes live at panel render
      "lefthook_hooks": ["secret-scan", "structure-drift", "typecheck", "lint"],
      "slash_commands_wired": null,          # /lp-define computes live at panel render
      "architecture_docs_rendered": 4,        # PRD + TECH_STACK + BACKEND_STRUCTURE + APP_FLOW
  },
  "sha256": <canonical_hash over fields above>,
}
```

Atomic write to `.launchpad/scaffold-receipt.json` via
`os.open(..., O_WRONLY|O_CREAT|O_EXCL, 0o600)`. On `FileExistsError`:
refuse with `reason: "scaffold_receipt_already_exists"` and a hint about
concurrent invocation. `os.fsync(fd)` + `os.fsync(dirfd)`. On
`sys.platform == 'darwin'`: `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)`.

## Phase 5b: Nonce ledger append

**AFTER** the receipt fsync (per HANDSHAKE §4 rule 10 ordering):
`nonce_ledger.append_nonce(nonce, repo_root)`. The order matters — if
the ledger append happened FIRST and the receipt write crashed, the user
would be locked out (nonce consumed, no receipt to show for it). Receipt
fsync is the chain-of-custody commit point.

The ledger lives at `.launchpad/.scaffold-nonces.log`, fixed 33-byte
records, format header `# nonce-ledger-format: v1\n`. 1MB rollover with
5-bak retention. F_FULLFSYNC on darwin.

## Phase 5c: Telemetry

Write a `v2-pipeline-*.jsonl` entry via `telemetry_writer.write_telemetry_entry()`:

```json
{"schema_version": "1.0", "command": "/lp-scaffold-stack",
 "timestamp": "<ISO>", "outcome": "completed", "time_seconds": ...,
 "cwd_state": "empty", "install_seconds": ..., "secret_scan_passed": true}
```

Honors `.launchpad/config.yml: telemetry: off` opt-out.

---

## Rejection forensic record (Phase 1 failures)

`scaffold-rejection-<ISO 8601 microsec>.<pid>.jsonl` under `.harness/observations/`:

- TWO-PART user-visible stderr surfacing:
  - **Part 1 (BEFORE write)**: one-line `reason:` + §4-rule-specific hint.
  - **Part 2 (AFTER `O_CREAT|O_EXCL` retry resolves)**: "log written to:
    `<actual_path>`" or "forensic log unavailable; reason captured above".
- Microsec + pid suffix closes same-second collision class.
- NO lock — `O_CREAT|O_EXCL|O_WRONLY` is the atomicity guarantee. On
  `FileExistsError`: retry with `.r2`/`.r3` suffix (max 5).
- ENOENT/EROFS/EACCES/ENOSPC try/except fallback to stderr with
  `JSONL-fallback:` prefix. Validation-rejection signal MUST survive even
  on read-only / full filesystems.
- Schema (closed):

```json
{
  "schema_version": "1.0",
  "reason": "<from §4 enum>",
  "seen_version": "<optional, only on version_unsupported>",
  "field_name": "<optional, only on path_traversal/forbidden_bullet_*>",
  "timestamp": "<ISO 8601 UTC sec-precision>",
  "pid": <int>,
  "pid_start_time": "<ISO 8601 UTC sec-precision via pid_identity.get_pid_start_time()>"
}
```

`schema_version` strict-policy per OPERATIONS §4 — readers reject absent
OR unknown via single reason `scaffold_rejection_schema_version_invalid`.

ALWAYS-WRITTEN: NOT gated by `telemetry: off`.

---

## Partial-failure record (Phase 3 / Phase 4 failures)

`.launchpad/scaffold-failed-<ts>.json` per OPERATIONS §6 gate #11:

```json
{
  "schema_version": "1.0",
  "version": "1.0",
  "failed_at": "<ISO 8601 UTC>",
  "reason": "<closed enum: layer_materialization_failed | auth_precondition_unmet | network_precondition_unmet | cross_cutting_wiring_collision | secret_scan_failed | recovery_precondition_unmet>",
  "failed_layer_index": <int> | null,
  "materialized_files": ["<relative path>", "..."],
  "recovery_commands": [
    {"op": "rmdir_recursive", "path": "..."},
    {"op": "rerun", "command": "/lp-scaffold-stack"}
  ],
  "recommended_recovery_action": "<prose, human-readable>",
  "see_recovery_doc": "docs/troubleshooting.md#scaffold-partial-failure"
}
```

**Forward-compat hint only at v2.0** (BL-231 strip-back). Phase 3 EMITS
the structured array; Phase 3 does NOT enforce closed-`op` enum / idempotency
contract / sha256 self-hash / `.recovery.lock` / at-most-one-rerun rule on
read.

**Write-time destructive-path denylist DOES apply**: the writer refuses to
emit entries with `path` ∈ `{".", "./", "..", "/", "~", ".launchpad",
".git", ".github"}` (defense-in-depth).

`failed_layer_index: null` allowed for `cross_cutting_wiring_collision`
and `secret_scan_failed` (per Layer 5 spec-flow P3-LF8).

Atomic `O_CREAT|O_EXCL` write. fsync + F_FULLFSYNC on darwin.

On materialization failure: nonce is NOT consumed (Step 5b never reached).
Re-running with the same `scaffold-decision.json` after fixing the cause
succeeds.

---

## Strict Rules

- NEVER bypass `safe_run` — every subprocess call goes through it.
- NEVER consume the marker via FD-read or integrity check at v2.0
  (BL-235 deferred).
- ALWAYS fsync + F_FULLFSYNC on darwin for persisted state (receipt,
  ledger, marker, rejection log).
- NEVER consume the nonce BEFORE the receipt fsync — that ordering is
  load-bearing for partial-cleanup recovery.
- The user can re-run after a partial failure once the cause is fixed —
  the unconsumed nonce remains valid for the 4h replay window.

---

## v2.1 Trust-model banner + cold-cache progress (Phase 4 §3.12 verbatim)

When the scaffold step is about to fetch an upstream template,
`/lp-scaffold-stack` prints the trust-model banner BEFORE any cache fetch
runs. Banner text matches `/lp-pick-stack` verbatim (substitution glossary
identical). The banner gives the user a final read on what is about to be
fetched so they can abort cleanly before any disk activity.

```
This project will fetch the following pinned upstream templates:
  - <repo>@<sha-prefix> (license: MIT, attestation: <verified|unsigned>)
  - <repo>@<sha-prefix> (license: MIT, attestation: <verified|unsigned>)
  ...
SHAs are dual-resolved (git ls-remote + GitHub REST). Audit log: docs/maintainers/upstream-pin-rotations.md.
```

### Cold-cache progress lines

When the template_cache reports a miss, `/lp-scaffold-stack` emits the
following progress lines (heartbeat cadence is one `.` every 5 seconds via
carriage-return repaint, single newline at completion):

```
Fetching <repo>@<sha-prefix> (cold cache, ~30s)…
```

then 5-second `.` heartbeats appended to the same line, then a newline at
completion. Subsequent stages emit:

```
Verifying sha256…
Rendering overlay…
```

### Network-bound failure exit codes

- Cache miss + offline: exit 75 (`EX_TEMPFAIL`) with the verbatim message
  "Cannot fetch upstream <repo>@<sha-prefix> (network unreachable). Connect
  to network and re-run, or pick a different stack."
- TMPDIR cross-FS: exit 1 with "TMPDIR is on a different filesystem than
  your project. Set TMPDIR to a path under <project_root> and re-run."
- Disk-full during cache write: exit 28 (`ENOSPC`) with "Out of disk space
  while caching <repo>@<sha-prefix>. Free space and re-run, or set
  LAUNCHPAD_CACHE_DIR to a different volume."
- SIGINT received: exit 130 with "Aborted by user; cleaning up partial
  scaffold..." then "Cleanup complete." after the SIGINT/SIGTERM/SIGKILL
  ladder finishes per `safe_run.safe_run_long`.

### What the trust banner does and does not prove

The banner proves the SHA was dual-resolved at Slice A0b time AND that the
audit log records the dual-resolution evidence. It does NOT prove the
upstream is malware-free; users who require additional supply-chain
assurance should pin LaunchPad to a known-good version and review
`docs/maintainers/upstream-pin-rotations.md` before re-running.
