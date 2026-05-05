---
name: lp-bootstrap
description: Materialize the v2.1 30-path infrastructure overlay from sealed identity. Greenfield + brownfield-auto + refresh modes; manifest-backed integrity contract.
---

# /lp-bootstrap

> **Trust model.** `/lp-bootstrap` renders bash scripts that execute in your
> CI (lefthook hooks, GitHub Actions workflows). `/plugin update` changes
> those scripts. v2.1 ships the bootstrap-manifest tampering check (verifies
> the rendered bytes match what the plugin shipped) but ships zero
> update-time integrity verification beyond manifest tampering detection.
> Pin LaunchPad to a known-good version in `scaffold-decision.json` (use
> `--accept-plugin-version-drift` to override), and review the diff before
> running `/lp-bootstrap --refresh-all` after any `/plugin update`.
> Code-signing / Sigstore / `gh attestation verify` for plugin-shipped
> templates is v2.2 backlog.

Materialize the v2.1 infrastructure overlay (`.gitignore`, lefthook,
compound build pipeline, scripts/hooks, scripts/maintenance,
scripts/agent_hydration, secret-patterns, `.github/CODEOWNERS`,
ISSUE_TEMPLATEs, workflows, harness templates, greptile / gitleaks configs)
into the project root. The 30-path inventory is canonical and pinned in
`lp_bootstrap.INFRASTRUCTURE_FILES` per locked Phase 3 plan section 3.1.

The command writes `.launchpad/bootstrap-manifest.json` recording every
rendered file's source-template sha + rendered-content sha, the running
plugin version, and the render timestamp. Subsequent invocations read the
manifest, verify per-file integrity, and dispatch the per-file conflict
policy (overwrite-if-unchanged, append-only, merge-keys, or
overwrite-with-backup for `--refresh`).

**Boundary** (Day-1 decision D2, plan section 6.8): the bootstrap-manifest
covers infrastructure ONLY. Kernel-file refresh (LICENSE, CONTRIBUTING.md,
CODE_OF_CONDUCT.md, README.md, SECURITY.md, AGENTS.md, CLAUDE.md) goes
through `KernelRenderer.refresh()` directly via `/lp-update-identity`
(Phase 10), NOT through `/lp-bootstrap --refresh`. Passing a kernel path
to `--refresh` is rejected with `unknown_refresh_path`.

## Arguments

| Flag                            | Behavior                                                                                                                                                                                                                     |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (none)                          | Full bootstrap. Per-file policy from plan section 3.2 decides each file. Fast-path skips paths whose on-disk sha matches the manifest sha and the rendered sha.                                                              |
| `--refresh <path>`              | Re-render a single infrastructure path with `overwrite-with-backup`. Path must be in the v2.1 30-path inventory. Repeatable for batch refresh.                                                                               |
| `--refresh-all`                 | Re-render every infrastructure path with `overwrite-with-backup`. If no manifest exists, silently degrades to full bootstrap with INFO `no_manifest_to_refresh`.                                                             |
| `--accept-plugin-version-drift` | Override the plugin-version pin abort. Records the drift in `scaffold-decision.json` `version_drift_log[]`. Auto-triggers `--refresh-all` to align manifest shas with the new plugin's templates. Sealed identity preserved. |
| `--recover`                     | Inspect sentinel snapshot. If sentinel + manifest are consistent and on-disk reality matches snapshot's `target_paths`, auto-completes the interrupted run. If state diverges, fails with structured guidance.               |
| `--accept-bootstrap`            | Non-interactive consent flag for brownfield auto-invocation. Required by `/lp-define` brownfield dispatch in CI / scripted contexts when no terminal is available for the y/N prompt.                                        |

Glob support in `--refresh <path>` is v2.2 backlog; v2.1 accepts exact
paths only.

## Conflict policies (plan section 3.2)

| Policy                   | Behavior                                                                                                                                                                                                                                                                                          | Used by                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `overwrite-if-unchanged` | Compare on-disk sha to manifest's `rendered_content_sha256`. Match -> write new content. Mismatch -> skip with `kept-user-edits` action message.                                                                                                                                                  | 26 of 30 paths                                                       |
| `merge-keys`             | YAML / JSON / CODEOWNERS only. Plugin can ADD top-level keys; CANNOT delete user keys. Conflict on duplicate-key value-type -> user wins, structured warning to `bootstrap-warnings.json`. Within an existing user-defined list, plugin appends new items but never deletes user-defined entries. | `lefthook.yml`, `scripts/compound/config.json`, `.github/CODEOWNERS` |
| `append-only`            | Read existing content; append plugin-required entries that aren't already present. NEVER reorders, deduplicates, or removes user entries.                                                                                                                                                         | `.gitignore`                                                         |
| `overwrite-with-backup`  | Reserved for `--refresh` and `--refresh-all`. Writes pre-edit content to `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>` before atomic-write. Backup contents must be byte-equal pre-edit; symlink rejected.                                                                                    | (refresh-only)                                                       |

Two policies named in the original V3 contract (`skip-if-exists`,
`overwrite-always`) are NOT shipped in v2.1; they defer to Phase 4 if an
adapter overlay demands them, else to v2.2.

## Failure modes

The 17-code error contract lives in `lp_bootstrap.BootstrapErrorCode`.
Every code carries structured `remediation` so the user sees a concrete
next step:

- `manifest_tampered` -- the recorded `source_template_sha256` does not
  match the plugin-shipped template. Caused by hand-editing the manifest
  OR by `/plugin update` between bootstraps. Remediation: pass
  `--accept-plugin-version-drift` to accept, OR delete the manifest to
  rebuild.
- `manifest_corrupt` -- malformed JSON / wrong envelope shape. Distinct
  from `manifest_tampered`. Remediation: delete and rebuild.
- `plugin_version_mismatch` -- scaffold-decision recorded a different
  plugin version than the running plugin. Pass
  `--accept-plugin-version-drift` to accept.
- `sentinel_blocking` -- another `/lp-bootstrap` is running, OR a stale
  sentinel exists with a live PID. Wait for the other process, OR pass
  `--recover` after confirming the PID is dead.
- `gitignore_append_failed` -- post-write verification of the
  `.launchpad/backups/` entry failed. Fail-closed; aborts the entire
  bootstrap. Remediation: add the entry manually.
- `unknown_refresh_path` -- `--refresh <path>` argument is not in the
  30-path inventory. Often because a kernel file path was passed; use
  `/lp-update-identity` for kernel refresh.
- `path_traversal_rejected` -- `--refresh` argument contained `..` or an
  absolute path. Defense-in-depth on top of the canonical path
  normalizer.

Concurrency primitives:

- Flock: `.launchpad/.bootstrap.lock`. Acquired as the FIRST step.
- Sentinel: `.launchpad/.bootstrap-in-progress` (mode 0o600). Survives
  SIGKILL (flock auto-releases on process death). Carries
  `(command_pid, started_at, pre_edit_manifest_sha256, target_paths,
mode)` snapshot.

## Recovery from interrupted runs

If a `/lp-bootstrap` was killed mid-render, the sentinel remains. The
recovery surface:

1. Run `/lp-bootstrap --recover`. The engine inspects the sentinel
   snapshot, confirms PID liveness, and either auto-completes the
   interrupted run OR fails with structured guidance.
2. If `--recover` cannot resolve the state (e.g., sentinel is corrupt OR
   on-disk reality diverges from snapshot's `target_paths`), the engine
   surfaces remediation prose and exits non-zero.
3. As a last resort: manually `rm .launchpad/.bootstrap-in-progress` after
   confirming no `/lp-bootstrap` PID is alive (`ps -p <pid>` from the
   sentinel snapshot).

## Brownfield auto-invocation

`/lp-define` calls `/lp-bootstrap` automatically when
`cwd_state.infrastructure_present(cwd)` returns one of: `PARTIAL_MISSING`,
`PARTIAL_STALE`, `ABSENT`. The brownfield path surfaces a y/N consent
prompt before any write fires:

```
LaunchPad will create N files in your project, including 7 executable
bash scripts that run on git commit. Files: [list].
Proceed? [Y/n]
```

Default Y. CI / scripted contexts must pass `--accept-bootstrap` to
satisfy the consent gate non-interactively.

`PRESENT_UNMANAGED` (paths exist on disk, no manifest) is handled via
the adopt-path: write a manifest from the on-disk shas without
re-rendering, with INFO log "adopted N pre-existing infrastructure files".

## What the manifest does and does not prove

- PROVES: on-disk files match what was rendered. `rendered_content_sha256`
  is recomputed at the END of every `/lp-bootstrap` run and compared
  against pre-write content via the per-file policy applicator.
- DOES NOT PROVE: the rendering plugin was authentic. v2.1 trusts the
  plugin-shipped template bytes; v2.2-backlog `gh attestation verify`
  work would close that surface.
- DOES NOT PROVE: the templates rendered were the templates the user
  expected. A `/plugin update` between bootstraps changes the
  `source_template_sha256` for every entry; the manifest catches this
  via `MANIFEST_TAMPERED` only when the next bootstrap runs.

## Examples

```bash
# First run: full bootstrap with sealed identity from scaffold-decision.json.
/lp-bootstrap

# After /plugin update: re-align manifest shas to the new plugin version.
/lp-bootstrap --accept-plugin-version-drift

# Refresh a single executable that the user broke locally.
/lp-bootstrap --refresh scripts/compound/build.sh

# CI pipeline: brownfield auto-invocation requires explicit consent.
/lp-bootstrap --accept-bootstrap

# Recover from a SIGKILLed run; engine validates state + completes or fails.
/lp-bootstrap --recover
```
