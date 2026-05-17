---
name: lp-bootstrap
description: Materialize the v2.1 34-path infrastructure overlay (v2.1.5+) from sealed identity. Greenfield + brownfield-auto + refresh modes; manifest-backed integrity contract.
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
into the project root. The 34-path inventory (v2.1.5+) is canonical and pinned in
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

| Flag                            | Behavior                                                                                                                                                                                                                                                                                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| (none)                          | Full bootstrap. Per-file policy from plan section 3.2 decides each file. Fast-path skips paths whose on-disk sha matches the manifest sha and the rendered sha.                                                                                                                                              |
| `--refresh <path>`              | Re-render a single infrastructure path with `overwrite-with-backup`. Path must be in the v2.1 34-path inventory (v2.1.5+). Repeatable for batch refresh.                                                                                                                                                     |
| `--refresh-all`                 | Re-render every infrastructure path with `overwrite-with-backup`. If no manifest exists, silently degrades to full bootstrap with INFO `no_manifest_to_refresh`.                                                                                                                                             |
| `--accept-plugin-version-drift` | Override the plugin-version pin abort. Records the drift in `scaffold-decision.json` `version_drift_log[]`. Auto-triggers `--refresh-all` to align manifest shas with the new plugin's templates. Sealed identity preserved.                                                                                 |
| `--recover`                     | v2.1 Codex PR #50 P1.D (D4): clears the bootstrap sentinel + unlinks a provably-stale manifest (when `manifest.created_at` predates `sentinel.acquired_at`). Returns `BootstrapStatus.RECOVERED_SENTINEL_CLEAR_ONLY`. Full reconciliation (auto-completing interrupted runs) is deferred to v2.1.1 (BL-262). |
| `--accept-bootstrap`            | Non-interactive consent flag for brownfield auto-invocation. Required by `/lp-define` brownfield dispatch in CI / scripted contexts when no terminal is available for the y/N prompt.                                                                                                                        |

Glob support in `--refresh <path>` is v2.2 backlog; v2.1 accepts exact
paths only.

## Conflict policies (plan section 3.2)

| Policy                   | Behavior                                                                                                                                                                                                                                                                                          | Used by                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `overwrite-if-unchanged` | Compare on-disk sha to manifest's `rendered_content_sha256`. Match -> write new content. Mismatch -> skip with `kept-user-edits` action message.                                                                                                                                                  | 30 of 34 paths (v2.1.5+)                                             |
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
  34-path inventory (v2.1.5+). Often because a kernel file path was passed; use
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

v2.1 Codex PR #50 P1.D (D4): `--recover` is intentionally narrow at
v2.1.0. Full reconciliation (auto-completing the interrupted run by
re-rendering partial files) is deferred to v2.1.1 (BL-262).

What `--recover` does at v2.1.0:

1. Clears the bootstrap sentinel.
2. Unlinks the manifest IFF `manifest.created_at` is older than
   `sentinel.acquired_at` (provably stale: a fresh manifest cannot exist
   prior to the sentinel that initiated its writing run; the inverse is
   the abandoned-bootstrap-followed-by-stale-manifest downgrade-attack
   surface, where stale manifest + cleared sentinel would let a future
   `_check_plugin_version_pin` pass for the OLD plugin version).
3. Returns `BootstrapStatus.RECOVERED_SENTINEL_CLEAR_ONLY` so callers can
   distinguish from a no-op clear.

What is deferred to v2.1.1 (BL-262):

- Auto-completing the partial run by re-rendering the
  `target_paths` whose hashes diverge from the current manifest.

Stale-sentinel detection during normal `/lp-bootstrap`:

When `_sentinel_preflight` observes a sentinel file owned by a non-live
PID, OR a hostname mismatch, OR an mtime older than
`STALE_SENTINEL_THRESHOLD_HOURS` (= 2), the engine returns
`BootstrapStatus.STALE_SENTINEL_DETECTED` with this remediation:

```
bootstrap sentinel from PID {pid} on {hostname_or_fingerprint} acquired_at {ts}
appears stale (reason: {triggered_reason}). Run /lp-bootstrap --recover to clear
and retry.
```

`{triggered_reason}` is exactly one of `pid_dead`, `hostname_mismatch`,
`age_exceeded` (single triggered reason, not a meta-list).

As a last resort: manually `rm .launchpad/.bootstrap-in-progress` after
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

## Python gates installed (consumer install required BEFORE first commit)

When `nextjs_fastapi` (or any future Python-bearing stack) is in the
detected stacks, the rendered `lefthook.yml` ships 5 Python gates
(bandit, ruff-check, ruff-format-check, pyright, pytest). They will fail
your first commit unless the tools are installed:

```
pip install 'bandit>=1.7.10' 'ruff>=0.5' 'pyright>=1.1.350' 'pytest>=8'
```

Recommended `pyproject.toml` addition (avoids bandit noise on test code):

```
[tool.bandit]
exclude_dirs = ["tests"]
```

Tooling notes:

- Prefer a virtual environment (`venv` / `poetry` / `uv`) over system pip.
- For a one-off skip without editing `lefthook.yml`: `LEFTHOOK=0 git commit ...`.
- To opt out permanently: remove the gate entry from `lefthook.yml`.

See https://github.com/builtform/launchpad/blob/main/docs/architecture/CI_CD.md#consumer-python-gates

## Post-bootstrap follow-up: Claude Code permission mode (BL-372, v2.1.8)

When the user has opted into autonomous mode by creating
`.launchpad/autonomous-ack.md` (BL-356), also propose merging the bundled
autonomous-mode template into `.claude/settings.json` so the
`/lp-build` -> `/lp-inf` -> `/lp-review` -> `/lp-resolve-todo-parallel` ->
`/lp-test-browser` -> `/lp-ship` chain does not hit a Skill or Monitor
permission prompt at every transition (5-7+ prompts per `/lp-build` run).

Run the merger in `--json` mode and decide from the structured output:

```bash
python -m lp_bootstrap.claude_settings_merger --json --cwd "$PWD"
```

Returned JSON:

```json
{
  "ack_present": true,
  "settings_present": true,
  "additions": ["permissions.allow['Skill']", "permissions.allow['Monitor']"],
  "already_satisfied": false,
  "template_path": "<plugin root>/templates/claude-settings-autonomous.json",
  "settings_path": "<cwd>/.claude/settings.json"
}
```

Decision matrix:

| `ack_present` | `already_satisfied` | Action                                                                                                     |
| ------------- | ------------------- | ---------------------------------------------------------------------------------------------------------- |
| false         | n/a                 | No action. The user has not opted into autonomous mode; prompts at runtime are the correct UX.             |
| true          | true                | No action. Existing `.claude/settings.json` already covers the autonomous-mode template.                   |
| true          | false               | Prompt the user with the additions list (see template below). On accept, run `--apply`. On decline, no-op. |

Prompt template (only fires on the last row):

> Detected `.launchpad/autonomous-ack.md`. Merge the LaunchPad
> autonomous-mode permission template into `.claude/settings.json` so the
> `/lp-build` autonomous chain runs without per-Skill prompts? The merge
> would add: **`<comma-joined additions>`**. Your existing entries are
> preserved (tightened rules like `Bash(git:*)` are NOT broadened, scalar
> values are NOT replaced). \[y/N]

On accept:

```bash
python -m lp_bootstrap.claude_settings_merger --apply --cwd "$PWD"
```

The `--apply` invocation refuses with exit 65 if `.launchpad/autonomous-ack.md`
is absent (the gate cannot be bypassed implicitly), and atomically writes
the merged JSON via `atomic_write_replace`. On decline, do nothing: the
user keeps the prompts. Future bootstrap runs will re-offer the prompt
as long as the settings file remains incomplete; the user can opt out
permanently by NOT creating `autonomous-ack.md`.

The shipped template uses TOOL-level entries (`"Skill"`, `"Bash"`, `"Edit"`,
`"Monitor"`, ...). Per-skill granularity (e.g. `"Skill(launchpad:lp-inf)"`)
is NOT supported by Claude Code's current permission schema; the merger
will not generate such entries even if requested.

## Post-bootstrap follow-up: preflight config (BL-370, v2.1.8)

After the engine returns `BootstrapStatus.SUCCESS`, scan for deploy-target
signals so the v2.1.7 external-infrastructure preflight gate actually
fires for default greenfield setups. The gap this closes: without a
`.launchpad/preflight.config.yaml`, `/lp-build` Step 0.6 and `/lp-ship`
Step 0.6 silently skip preflight and the user only discovers missing
Cloudflare / DNS / secret setup at deploy time, ~30 min into autonomous
`/lp-inf` work.

Run the proposer in `--json` mode and decide from the structured output:

```bash
python -m lp_bootstrap.preflight_proposer --json --cwd "$PWD"
```

Returned JSON:

```json
{
  "detected": ["cloudflare-pages"],
  "proposed_profiles": ["cloudflare-dns", "cloudflare-pages", "spec-completeness"],
  "config_present": false,
  "skipped_marker_present": false
}
```

Decision matrix:

| Detected  | `config_present` | `skipped_marker_present` | Action                                                                                                    |
| --------- | ---------------- | ------------------------ | --------------------------------------------------------------------------------------------------------- |
| empty     | any              | any                      | No action. Repo has no deploy target yet.                                                                 |
| non-empty | true             | any                      | No action. Config already authored; respect user edits.                                                   |
| non-empty | false            | true                     | No action. User previously opted out; do not re-prompt.                                                   |
| non-empty | false            | false                    | Prompt the user (see template below). On accept, run `--write-config`. On decline, run `--write-skipped`. |

Prompt template (only fires on the last row of the matrix):

> Detected deploy provider(s): **`<comma-joined detected>`**.
> Create `.launchpad/preflight.config.yaml` covering
> **`<comma-joined proposed_profiles>`** so `/lp-build` and `/lp-ship` can
> probe these prerequisites before deploy time? \[y/N]

On accept:

```bash
python -m lp_bootstrap.preflight_proposer --write-config \
  --providers "<comma-joined proposed_profiles>" --cwd "$PWD"
```

On decline:

```bash
python -m lp_bootstrap.preflight_proposer --write-skipped --cwd "$PWD"
```

The `--write-config` invocation atomically writes the YAML via
`atomic_write_replace` and refuses to overwrite an existing config (exit
65). The `--write-skipped` invocation writes a one-line
`.launchpad/preflight.config.skipped` sentinel so future bootstrap runs
do not re-prompt; the user can delete the sentinel to opt back in.

The detector currently covers `cloudflare-pages` (from `wrangler.{jsonc,toml,json}`
or `cloudflare/pages-action` / `cloudflare/wrangler-action` workflow refs),
`vercel` (from `vercel.json` or `.vercel/project.json`), and `netlify`
(from `netlify.toml`). Additional providers join as their profile lands
in `plugins/launchpad/preflight-profiles/`.

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
