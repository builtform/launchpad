# SCAFFOLD_OPERATIONS.v2 (Phase 4 v2.1 §11 sibling — NOT yet folded)

> **Folding policy.** This V2 sibling carries the Phase 4 §11 addition
> (adapter dispatch + composition sequencing + cache lifecycle + SIGINT
> semantics) destined for `SCAFFOLD_OPERATIONS.md`. Folding is deferred to
> Phase 9 per the v2.1 Phase 4 plan §2.3 + §8 (DEFERRED to Phase 9). Until
> then, readers consult both the canonical doc (sections 1–10) and this
> sibling (section 11).

---

## 11. v2.1 adapter dispatch + composition sequencing + cache lifecycle + SIGINT semantics

### 11.1 Adapter dispatch entrypoints

The v2.1 dispatch surface lives in
`plugins/launchpad/scripts/lp_scaffold_stack/v21_adapter_dispatch.py`:

- `resolve_adapter(stack_id) -> Adapter`: closed-enum lookup over the 5
  active stack ids; raises `ScaffoldStepFailedError` for unknown ids with
  the structured triple `reason / path / remediation`.
- `dispatch_single_adapter(adapter, workspace_dir)`: invokes
  `Adapter.scaffold_into(workspace_dir)` followed by
  `Adapter.apply_overlay(workspace_dir)`. The `bridge_to_scaffold_error`
  helper from `contracts.py` normalizes any per-module exception to
  `ScaffoldStepFailedError` while preserving the structured triple per
  Phase 3 §3.11.5(b) inheritance.
- `dispatch_composition(adapters, composition_root)`: wraps
  `composition.compose` with the §3.12 N=2 cap rejection surfaced verbatim
  via `CompositionAbortError`.
- `dispatch_by_stack_ids(stack_ids, workspace_dir)`: one-shot entrypoint
  returning `Path` for single-id input or `CompositionResult` for multi-id.

### 11.2 Composition sequencing

`compose(adapters, composition_root)`:

1. `validate_pair(adapters)` enforces N=2 cap, ts_monorepo + \* catch-all
   rejection (collapses 4 of the 10 C(5,2) pairs), duplicate rejection,
   and partner-missing-from-composes_with rejection.
2. `resolve_workspace_allocation` builds the `workspace_dir -> adapter`
   mapping with collision-suffix logic. The only v2.1 pair that triggers
   the `app -> app-fe` rename is `nextjs_standalone + nextjs_fastapi`; the
   verbatim §3.12 INFO log fires when the rename runs.
3. Same-FS pre-flight via `st_dev` comparison between `composition_root`
   and `composition_root/.tmp/`. Cross-FS aborts with the verbatim §3.12
   message and exit 1.
4. Per-adapter `scaffold_into + apply_overlay` runs into a tempdir under
   `composition_root/.tmp/lp-<stack_id>-<uuid>/`.
5. After all adapters complete, atomic `os.replace` into
   `composition_root/apps/<workspace_name>/` for each.
6. On any per-adapter failure, rollback runs `shutil.rmtree` on every
   rendered tempdir. Errors during cleanup log the verbatim secrets-warning
   recommendation per harden P0 ("manual cleanup required (may contain
   secrets-shaped files like .env.example)").

### 11.3 Template cache lifecycle

`plugins/launchpad/scripts/template_cache/` (hoisted out of
`plugin_stack_adapters/` per Slice B):

- Cache root resolves to `~/.launchpad/template-cache/` by default;
  override via `LAUNCHPAD_CACHE_DIR` (test + sandbox path; not user-facing
  documented at v2.1 per plan §8).
- Pre-flight: cache root must be a regular directory (not a symlink),
  mode 0o700, owned by `os.getuid()`. Failures emit the verbatim §3.12
  message and exit 1.
- Validation-before-flock ordering: malformed inputs (sha regex, repo URL
  shape) MUST raise BEFORE any lock file is created.
- Per-entry lockfile at `.locks/<slug>-<sha>.lock` (mode 0o600). Lockfile
  survives entry purge so concurrent fetchers race-safely against a
  recently-evicted entry.
- `MAX_CONCURRENT_FETCHES=3` process-local semaphore caps simultaneous
  fetches.
- 500MB LRU eviction is lazy on-fetch (NOT background-swept; per-rotation
  rationale in plan §8 deferred items).
- 90-day TTL re-validation triggers full-tree re-verify against
  `pin_registry.py`; tag-replay defense lives in the nightly
  tag-drift-detector workflow at `.github/workflows/cve-watch.yml`.
- `.compromised` sentinel auto-purges on next verify; the verbatim §3.12
  WARN message points the user at the GitHub Security Advisory and the
  `--refresh-all` recovery path.

### 11.4 SIGINT semantics

`safe_run.safe_run_long(argv, cwd, sigint_timeout_s=2.0,
sigterm_timeout_s=3.0)`:

- `subprocess.Popen(argv, start_new_session=True, ...)` puts the child in
  its own process group (`os.setsid`).
- On `KeyboardInterrupt`: `os.killpg(child_pgid, SIGINT)`, then
  `psutil.Process(pid).children(recursive=True)` SIGTERM sweep after
  `sigint_timeout_s`, then SIGKILL after `sigterm_timeout_s`.
- `LAUNCHPAD_SIGINT_TIMEOUT_S` env override (DA5 lock; opt-in 1s for fast
  CI matrices).
- Returns `CompletedProcess` on clean exit, raises `SafeRunInterrupted`
  on user SIGINT after cleanup, raises `SafeRunTimedOut` if descendants
  survive the SIGKILL ladder (rare).
- Lint exemption: `plugin-v2-handshake-lint.py` allowlists the
  `subprocess.Popen + start_new_session=True` pattern via the
  path-prefix check on `safe_run.py`.
- Cross-platform: macOS + Linux (POSIX-only). Windows is out of scope at
  v2.1 per plan §8.

### 11.5 Trust banner placement

Both `/lp-pick-stack` and `/lp-scaffold-stack` print the verbatim §3.12
trust-model banner BEFORE any cache fetch runs. The banner lists each
upstream (`<repo>@<sha-prefix>`) plus license + attestation status. Cache
miss + offline aborts with exit 75 (`EX_TEMPFAIL`) and the verbatim §3.12
"Cannot fetch upstream ..." message.

### 11.6 CVE rotation policy and tag-drift detector

`docs/maintainers/upstream-pin-rotations.md` is the append-only audit log.
Every modification of a `sha` value in `pin_registry.py` requires a
same-commit entry; `plugin-v2-handshake-lint.py
--check-pin-registry-rotation-audit-log` enforces.

`.github/workflows/cve-watch.yml` runs nightly at 02:00 UTC (osv-scanner
over `pin_registry.py` SHAs + tag-drift-detector). Manual
`workflow_dispatch` is the documented test path; scheduled-run
verification is post-ship monitoring per plan DoD.

`.github/workflows/tier-2-nightly.yml` runs at 04:00 UTC (cron stagger).
Real-network end-to-end of canonical compositions; failures auto-open a
GitHub Issue with the `nightly-failure` label per §3.12. Non-blocking on
PR merges per DA4 = c separate-fault-domain rationale.
