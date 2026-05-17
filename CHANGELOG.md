# Changelog

All notable changes to LaunchPad are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Tracked in [ROADMAP.md](ROADMAP.md). v2.1.9 candidates include BL-365 (parallelize preflight probe dispatch + short-TTL cache), BL-367 (programmatic GitHub-repo linkage verification for provider project probes), and BL-368 (DNS `dig +short --` sentinel bug). v2.1.x bundles BL-366 (18-item preflight polish). v2.2 lands the 15 operational/security infrastructure surfaces deferred from v2.0 plus the 10 deferred stacks. See `docs/tasks/BACKLOG.md` for full scope.

## [v2.1.8]

Autonomous-execution polish (BL-370 + BL-371 + BL-372 + BL-373). v2.1.8 closes four gaps that turned "autonomous /lp-build" into an interactive (and occasionally broken) flow in practice. Each gap surfaced from post-v2.1.7 scope-review reproduction on a real-world greenfield site build: the v2.1.7 preflight gate (BL-364) was invisible to users who never authored `.launchpad/preflight.config.yaml` by hand; configured preflight ran twice (once at /lp-build, again at /lp-ship) with no memoization; Claude Code prompted the user for every Skill or Monitor invocation during the /lp-build chain because LaunchPad's autonomous-ack.md gate was independent of Claude Code's permission system; and a build-time `fetch()` to a rate-limited public API (`api.github.com`) from a shared-IP build runner hit the 60-req/hour anonymous limit and failed the deploy because `GITHUB_TOKEN` was never set in the deploy environment.

### For LaunchPad users (downstream behavior changes)

- **`/lp-bootstrap` proposes a preflight config when deploy signals exist (BL-370, P1).** After the engine returns success, /lp-bootstrap scans the repo for `wrangler.{jsonc,toml,json}`, `vercel.json`, `.vercel/project.json`, `netlify.toml`, and `cloudflare/pages-action` / `cloudflare/wrangler-action` workflow references. When any signal is present AND `.launchpad/preflight.config.yaml` is absent AND the opt-out marker is absent, the user gets a single y/N prompt to create the config with the detected providers plus `spec-completeness`. On accept, the config lands at `.launchpad/preflight.config.yaml` and subsequent `/lp-build` + `/lp-ship` invocations actually probe Cloudflare / DNS / secrets. On decline, a skipped-marker file is written so future bootstrap runs do not re-prompt.
- **Preflight receipt memoization between `/lp-build` and `/lp-ship` (BL-371, P1).** A successful `/lp-build` Step 0.6 pass writes `.launchpad/preflight-receipt.json` with the config + checklist SHA-256 and the freshness window (default 3600s; override via top-level `freshness_window_seconds:` in `.launchpad/preflight.config.yaml`). `/lp-ship` Step 0.6 trusts a still-valid receipt and skips probes, emitting one `preflight-skipped-via-receipt` line to `.launchpad/audit.log`. Stale, mutated-config, mutated-checklist, prior-failed, or corrupt receipts are invalidated automatically and probes re-run; the invalidation reason is recorded as `preflight-receipt-<reason>` in the audit log.
- **Claude Code permission-mode autonomy via `.claude/settings.json` merger (BL-372, P1).** When `.launchpad/autonomous-ack.md` exists, `/lp-bootstrap` proposes merging a bundled tool-level allowlist template (`Skill`, `Bash`, `Read`, `Write`, `Edit`, `Grep`, `Glob`, `Monitor`, `TodoWrite`, `WebFetch`, `WebSearch`) into the user's `.claude/settings.json`. The merger preserves existing customizations: tightened `Bash(git:*)` rules are NOT broadened to bare `Bash`; scalar values and unrelated dicts pass through unchanged. After acceptance, the `/lp-build` -> `/lp-inf` -> `/lp-review` -> `/lp-resolve-todo-parallel` -> `/lp-test-browser` -> `/lp-ship` -> `/lp-learn` chain runs without per-Skill or per-Monitor permission prompts.
- **Build-time API auth preflight probe (BL-373, P1).** A new `build-time-api-auth` provider profile ships at `plugins/launchpad/preflight-profiles/build-time-api-auth.yaml` with two Category B checks (`github-api-token`, `gitlab-api-token`). Each scans the project for evidence the host (`api.github.com` / `api.gitlab.com`) is called at build time and verifies the corresponding auth env var is set; if the host is called but the env var is missing, the probe FAILs with a full remediation block before `/lp-build` even starts the autonomous loop. When BL-370 auto-generates a starter config, the new profile is included by default whenever any deploy target is detected; the probe is a no-op (PASS-with-skip-message) for projects that do not call rate-limited APIs at build time. Strategy A (trust-based local-env check) ships in v2.1.8; Strategy B (programmatic deploy-env verification against Cloudflare/Vercel/Netlify env-var APIs) is deferred to v2.2.

### Plugin-internal changes

See `docs/releases/v2.1.8.md` for full file-by-file breakdown.

### Scope deferred from v2.1.8

The following v2.1.8 candidates ship in v2.1.9 instead so the autonomy lane could ship as a coherent unit:

- **BL-365 (v2.1.9, P2)**: parallelize preflight probe dispatch + short-TTL cache.
- **BL-367 (v2.1.9, P2)**: programmatic GitHub-repo linkage verification.
- **BL-368 (v2.1.9, P1)**: DNS `dig +short --` sentinel bug. The workaround documented under BL-368 remains: untick the C1 box after probe false-fail OR drop the DNS profile from `.launchpad/preflight.config.yaml`.

### Test count

1967 passing + 4 skipped (+84 across three new test files spanning preflight-proposer, preflight-receipt, and claude-settings-merger surfaces, plus 14 BL-373 tests added to test_lp_preflight.py).

## [v2.1.7]

External-infrastructure preflight gate (BL-364). v2.1.7 ships `lp_preflight.py` (engine + 15 probes + CLI), 6 bundled provider profiles (cloudflare-pages, vercel, netlify, cloudflare-dns, namecheap-dns, spec-completeness), and Step 0.6 wiring on `/lp-build` + `/lp-ship`. The gate fails fast on provider account, deploy project, GitHub Secrets, DNS, and spec-completeness prerequisites BEFORE the autonomous implementation loop runs, so users don't waste a 30-minute `/lp-inf` cycle to learn that `CLOUDFLARE_API_TOKEN` was never set.

### For LaunchPad users (downstream behavior changes)

- **`/lp-preflight` standalone command + 6 provider profiles (BL-364, P1).** Drop `.launchpad/preflight.config.yaml` naming any subset of `{cloudflare-pages, vercel, netlify, cloudflare-dns, namecheap-dns, spec-completeness}` and the gate verifies provider-account existence, API-token validity, deploy-project existence, GitHub Secrets population, DNS resolution (Cloudflare edge ranges or CNAME suffix matching), and PRD/CHANGELOG/section-spec completeness. Per-item stale windows (default 30-365 days depending on item) re-prompt the user when a confirmation goes stale. The file's absence is opt-out: projects that haven't configured external prerequisites skip preflight silently.
- **`/lp-build` Step 0.6 + `/lp-ship` Step 0.6 wiring.** `/lp-build` resolves the target section name before preflight (new Step 0.55) and passes `--section docs/tasks/sections/<name>.md` so `section-specs-approved` scopes to the section being built. Multi-section projects with one approved section + others in `shaped`/`planned` state no longer false-fail the gate. `/lp-ship` runs the same gate without `--section` (project-wide).
- **Cloudflare DNS check covers the full `/12` + `/13` edge ranges.** The Cloudflare DNS probe parses `dig +short` answers via `ipaddress.IPv4Address` and matches against `104.16.0.0/12` (104.16.0.0 to 104.31.255.255) + `172.64.0.0/13` (172.64.0.0 to 172.71.255.255), so any IP across the full published ranges passes, and a CNAME hostname starting with a numeric octet (e.g., `104.16.cdn.example.com.`) cannot false-positive the IP-prefix check.
- **Provider project-existence probes verify EXISTENCE only, not GitHub linkage.** Profile titles are now scoped to "Cloudflare Pages project exists" / "Vercel project exists" / "Netlify site exists" with explicit setup_hint language that the user attests to the Git integration. Programmatic linkage verification via the API `source.config` / `link.repo` / `build_settings.repo_url` blocks is tracked as BL-367 (v2.1.8).

### Plugin-internal changes

See `docs/releases/v2.1.7.md` for full file-by-file breakdown.

### Scope deferred from v2.1.7

The following BLs were labeled v2.1.7 in `docs/tasks/BACKLOG.md` but ship in v2.1.8 instead. v2.1.7 is single-feature focused on BL-364 (preflight gate) plus the 5 follow-up review-iterate fixes; the items below either depend on unrelated stack-aware work or are independent polish that didn't make the v2.1.7 batch:

- **BL-357 (`/lp-shape-section --auto` synthesize-from-artifacts mode, P2)**: deferred to v2.1.8.
- **BL-359 (Hugo stack missing from `STACK_FAMILY` map, P1)**: deferred to v2.1.8.
- **BL-360 (CI workflow `pnpm/action-setup` + `actions/setup-node` for non-TS stacks, P1)**: deferred to v2.1.8.
- **BL-361 (v2.1.6 release notes claim `generic` renders "static site, no backend" but round-2 fix flipped `static_capable=False`, P3)**: deferred to v2.1.8.
- **BL-362 (v2.1.6 release notes claim non-TS prettier-fix/eslint-fix hooks are "inert and deferred" but round-1 strips them, P3)**: deferred to v2.1.8.
- **BL-363 (`ts_python` family loses `prettier-fix` / `eslint-fix` lefthook auto-fixers, P1)**: deferred to v2.1.8.

### Test count

1937 passing + 4 skipped (was 1854 at v2.1.6 squash; +91 across the new `tests/test_lp_preflight.py` suite).

## [v2.1.6]

Tier 2 stack-aware refactors + autonomous-ack gate generalisation. v2.1.6 closes the 8 Tier 2 BLs deferred from v2.1.5 (BL-345..BL-352) plus an architectural fix to the autonomous-ack gate (BL-356). The Tier 2 work makes `/lp-bootstrap` output coherent for non-TS-monorepo stacks (Astro, Next.js single-app, Python, Ruby, Hugo, Go) — pre-v2.1.6 every greenfield single-app project hit a P0 first-commit blocker because the rendered structure-check script's allowlist was monorepo-shaped, plus a cascade of TS-monorepo cruft in `.gitignore` / `.gitleaks.toml` / `.greptile.json` and `pnpm <cmd>` commands in lefthook + ci.yml that fail for non-TS users. BL-356 closes a direct-invocation bypass of the autonomous-ack gate that the v2.1.5 ack design only enforced on `/lp-build`.

### For LaunchPad users (downstream behavior changes)

- **Stack-aware `check-repo-structure.sh` allowlist (BL-347, P0).** Per-stack ALLOWED_DIRS / ALLOWED_CONFIGS data injected via sentinel comments at `/lp-bootstrap` render time. Greenfield single-app projects no longer hit a first-commit blocker; framework files at root (`astro.config.mjs`, `next.config.ts`, `public/`, `src/`, `manage.py`, `Gemfile`) pass the structure-check gate. `apps/` + `packages/` moved out of the universal kernel allowlist into the `ts_monorepo` stack entry.
- **Stack-aware `.gitignore` / `.gitleaks.toml` / `.greptile.json` (BL-350, P3).** TS-monorepo cruft (`.next/`, `.turbo/`, `pnpm-lock.yaml`) moved into per-stack data. Python / Ruby / Hugo / Go users no longer see irrelevant entries in their rendered ignore files. `.greptile.json`'s sentinels are stripped on every render (sentinels live inside a JSON string value).
- **Stack-aware `lefthook.yml` + `.github/workflows/ci.yml` package-manager commands (BL-346 + BL-352, both P1).** New `_package_managers.py` declares per-family lefthook bodies + CI setup actions. Two new enrichers rewrite `run: pnpm test` → `run: pytest`, `run: pnpm typecheck` → `run: pyright .`, etc. TS-family projects ship byte-identical to v2.1.5 (no-op path). Setup-action steps in ci.yml remain TS-shape for non-TS projects (documented limitation; deferred to v2.1.7).
- **Minimal APP_FLOW.md placeholder hints + `BackendInfo.static_capable` (BL-348 + BL-349, both P1).** Every adapter's `describe_app_flow()` previously emitted concrete fake routes that misled users. v2.1.6 emits `entry_routes=["/"]` plus an explicit `[Placeholder — add real routes via /lp-shape-section]` marker. `BackendInfo` gains a required `static_capable: bool` field so BACKEND_STRUCTURE.md can render "static site, no backend" framing for static-output stacks.
- **`<stack>-noop: run: 'true'` placeholder hooks dropped (BL-351, P3).** Cosmetic-only placeholders stripped from astro / generic / nextjs_standalone / ts_monorepo lefthook fragments.
- **Stack-detector recognises Astro, single-app Next.js, plain Python (BL-345, P2).** `plugin-stack-detector.py` adds `astro` / `nextjs_standalone` / `python_generic` stack-id mappings; surfaces `@11ty/eleventy` / `expo` / `@supabase/*` frameworks as v2.2 active enum candidates.
- **Autonomous-ack gate covers every direct-invocation autonomous-write command (BL-356, P1).** The v2.1.5 gate enforced `.launchpad/autonomous-ack.md` only on `/lp-build`. v2.1.6 lifts the gate into a shared helper (`assert_autonomous_ack`) and wires `/lp-inf`, `/lp-resolve-todo-parallel`, `/lp-ship` to call it. Refuse-message embeds a copy-pasteable starter template beginning with `# Autonomous Execution Acknowledgment`.

### Plugin-internal changes

See `docs/releases/v2.1.6.md` for full file-by-file breakdown — 3 new data modules, 3 new enricher modules, 10 adapter file updates, 5 command markdown updates, 1 detector update, +153 net new tests across 6 new test files.

### Test count

1730 passing + 4 skipped (was 1577 at v2.1.5 squash).

## [v2.1.5]

Tier 1 universal scope-review fixes — 15 BLs surfaced during a post-v2.1.4 real-world installed-plugin reproduction. v2.1.5 lands the universal fixes (template renders, bootstrap manifest additions, slash-command fallback modes); v2.1.6 ships the 8 Tier 2 stack-aware refactors as a separate PR per scope decision. Pre-v2.1.5, every greenfield TS-stack first push fails CI red at the pnpm/action-setup or actions/setup-node step (missing version source / `.nvmrc`); brainstorm content is discarded by `/lp-define`; CODEOWNERS ships a literal placeholder under PII opt-out; the lefthook EOF gate refuses LaunchPad's own canonical envelopes; `pnpm astro check`-style commands silently false-pass the build runner on non-TTY stdin.

### For LaunchPad users (downstream behavior changes)

- **Greenfield TS-stack CI is green on first push (BL-353 + BL-354, both P0).** The rendered `.github/workflows/ci.yml` now declares `version: '<DEFAULT_PNPM_VERSION>'` on the `pnpm/action-setup` step (BL-353), and `/lp-bootstrap` renders `.nvmrc` containing `<DEFAULT_NODE_VERSION>` at project root so `actions/setup-node`'s `node-version-file:` input resolves (BL-354). Both pnpm and Node versions are sourced from `plugin_stack_adapters/_constants.py` — single source of truth. Pre-fix the Build job aborted at the setup step on every greenfield TS-stack first push; all 5 downstream steps (Install / Type Check / Lint / Test / Build) were skipped.
- **`/lp-bootstrap` refuses to write inconsistent workflow + file-reference state (BL-355, P1).** Structural assertion at render time: every rendered `.github/workflows/*.yml` is parsed; for every step's `node-version-file` input (extended in v2.1.6 BL-345 to also cover `python-version-file` / `go-version-file` / `ruby-version-file` when stack-aware workflows ship), the referenced file MUST also be in the bootstrap render batch (or already on disk under cwd — the resolve+relative_to guard refuses `..` and absolute paths). On mismatch, `/lp-bootstrap` raises with a clear error naming the offending workflow + missing file before any disk write. Catches the BL-353/BL-354 class at write time — before the user pushes, before CI runs, before any failure round-trip.
- **`/lp-define` consumes `.launchpad/brainstorm-summary.md` into the canonical docs (BL-333, P0).** Pre-fix the `/lp-brainstorm` → `/lp-kickoff` → `/lp-define` happy path produced empty PRD/APP_FLOW/BACKEND_STRUCTURE placeholders regardless of what content the brainstorm phase captured. `/lp-define` now parses brainstorm-summary.md by `## ` section heading, slug-normalizes (`Success Criteria` → `success_criteria`), applies a small alias map (`Problem` → `overview`, `Personas` → `users`, `Goals` → `success_criteria`, etc.), and injects each section as `brainstorm.<slug>` into the Jinja context. PRD/APP_FLOW/BACKEND_STRUCTURE templates consume `brainstorm.*` when present, wrapped in a `<!-- v2.1.5 BL-333: filled from .launchpad/brainstorm-summary.md — verify and edit. -->` comment block so users see what came from the brainstorm phase and what's still placeholder.
- **`SECURITY.md`, `.github/dependabot.yml`, `.github/pull_request_template.md`, `docs/architecture/REPOSITORY_STRUCTURE.md` all render on greenfield scaffold (BL-336, BL-342, BL-343, BL-344).** Public-repo flip-public prerequisites that previously had no automated render path. `SECURITY.md` was already in `KernelRenderer.KERNEL_FILES` from a prior v2.1.x release — locked down with a regression test that prevents silent removal. `REPOSITORY_STRUCTURE.md` ships a universal-shape baseline; v2.1.6 BL-347 lands the stack-aware ALLOWED_DIRS/ALLOWED_CONFIGS variant.
- **CODEOWNERS no longer ships a broken owner line under PII opt-out (BL-334).** Pre-fix the rendered `.github/CODEOWNERS` contained the literal placeholder `* <copyright-holder>` when the user opted out of PII at `/lp-pick-stack` Step 1.5 — routing PR review requests to a non-existent user. CODEOWNERS now emits a `# TODO: set primary owner via /lp-update-identity (interactive prompt #3: copyright_holder)` comment in the PII-opt-out path instead of a broken owner line. The TODO also explains the valid GitHub owner-token shape (`@user` / `@org/team`) so bare display names aren't mistakenly accepted.
- **`/lp-commit` after `/lp-pick-stack` no longer triggers lefthook EOF-newline rejection (BL-339).** The rendered `lefthook.yml`'s `end-of-file-newline` pre-commit hook now excludes `.launchpad/(scaffold-decision|scaffold-receipt)\.json$` so the hook doesn't reject LaunchPad's own canonical byte-deterministic JSON envelopes (sha256 seal computed over canonicalized bytes — trailing-byte changes would break cross-writer/reader integrity).
- **`plugin-build-runner.py` no longer false-passes on non-TTY interactive prompts (BL-340).** Pre-fix `pnpm astro check` (and similar tools that prompt to auto-install missing dev-deps then bail silently on non-TTY stdin) returned exit 0 even when zero typechecking actually ran. The runner now tees stdout/stderr to the terminal AND scans each line for known prompt patterns (`Continue? Yes / No`, `[Y/n]`, `Do you want to install`, etc.). Exit 0 + prompt pattern detected = failure, with a clear error naming the pattern.
- **`/lp-review` works on freshly-initialized greenfield repos before first commit (BL-337).** Pre-fix the Step 1 diff-scope command (`git diff --name-only origin/main...HEAD`) failed on no-HEAD or no-remote with `fatal: ambiguous argument`. `/lp-review` now detects the pre-first-commit case and offers `--staged` or working-tree review modes; the agent dispatch treats each file as a new-file diff (no diff base, full-content review).
- **`/lp-commit` accepts an initial-scaffold commit on `main` (BL-338).** Pre-fix the Step 1 branch-guard refused commits on `main` (forcing feature-branch creation) — wrong shape for the very first commit on a freshly-initialized repo where there's no diff base for mandatory review. `/lp-commit` now auto-detects no-HEAD state (or accepts an explicit `--initial-scaffold` flag), prompts to confirm the initial-scaffold commit, skips Step 2.5 mandatory review (nothing to diff against), and emits an `Initial-Scaffold: true` trailer instead of the misleading `Mandatory-Review-Skipped: emergency-hotfix` value.
- **`scripts/compound/compound-learning.sh` no longer hard-deps on `prd.json` (BL-335).** LaunchPad never produces `prd.json` (it produces `docs/architecture/PRD.md` via `/lp-define`); the legacy CE-port assumed `prd.json` and exited early with "No prd.json found" on every LaunchPad project. Script now consumes the canonical LaunchPad artifacts (PRD.md + scaffold-receipt.json) while keeping hand-authored `prd.json` as an optional override.
- **Targeted kernel-file fallback for `/lp-define` (BL-341).** When kernel files (LICENSE / SECURITY.md / CONTRIBUTING.md / etc.) are missing from a scaffolded project (e.g., partial pipeline run, hand-crafted scaffold-receipt), `/lp-define` invokes `KernelRenderer.render_all` with the new `only_paths=missing` parameter so it renders ONLY the absent files. User-edited kernel files are never overwritten. A `SecretScannerViolation` or `OSError` during the fallback aborts with an explicit `error:` and does NOT let `/lp-define` continue against partial state; other failures log a warning and continue. BL-327 (v2.1.4) fixed the primary bug that would have triggered this; BL-341 covers the residual cases.

### Tier 2 scope-split rationale

Tier 2 stack-aware refactors (BL-345 through BL-352) deferred to v2.1.6. The 11-stack matrix means each stack-aware bug fans out to ~50+ per-stack template variants + 11 regression fixtures. Combining Tier 1 + Tier 2 into a single PR would have ~80 modified files; reviewer signal-to-noise on a PR that big is poor. Splitting:

- Tier 1 ships in <20 files with a high-precision review pass
- Tier 2 ships in a focused 50-80 file PR with its own review cycle
- Tier 1 users get universal fixes 2-3 weeks sooner
- If Tier 2 surfaces a per-stack regression post-merge, v2.1.5 stays clean as a recoverable baseline

### Plugin-internal changes

- New module: `plugin_stack_adapters/_constants.py` (`DEFAULT_PNPM_VERSION`, `DEFAULT_NODE_VERSION` — single source of truth for tool-version pins consumed by rendered CI workflow + `.nvmrc`).
- New template: `plugin_default_generators/infrastructure/nvmrc.j2`.
- New template: `plugin_default_generators/infrastructure/github/dependabot.yml.j2`.
- New template: `plugin_default_generators/infrastructure/github/pull_request_template.md.j2`.
- New template: `plugin_default_generators/REPOSITORY_STRUCTURE.md.j2`.
- New helper: `lp_define_runner.read_brainstorm_summary(repo_root)` + `_slug_section_name(heading)`.
- New helper: `lp_define_runner._kernel_fallback_render(repo_root)`.
- New helper: `plugin-build-runner._run_cmd_with_prompt_detection(cmd, repo_root)` + `_PROMPT_BAIL_PATTERNS` closed-enum.
- New helper: `plugin_default_generators.infrastructure_renderer._validate_workflow_self_consistency(batch, cwd)` + `assert_workflow_self_consistency(batch, cwd, *, error_cls)` helper + `_WORKFLOW_FILE_REF_INPUTS` closed-enum (1 row at v2.1.5; v2.1.6 BL-345 extends).
- New module-scope constants in `lp_define_runner`: `_BRAINSTORM_ALIASES` + `_BRAINSTORM_CANONICAL_SLUGS` (hoisted from per-call rebuild) + precompiled slug regexes `_SLUG_WS_RE` / `_SLUG_NONALNUM_RE` / `_SLUG_COLLAPSE_RE`.
- New Jinja partial: `plugin_default_generators/_brainstorm_macro.j2` (shared `brainstorm_section(content)` macro applying `| markdown_safe` + the BL-333 marker comment; consumed by PRD/APP_FLOW/BACKEND_STRUCTURE).
- `template_context()` renamed from `identity_inject` (the function now mixes identity + tool-version pins; old name preserved as a back-compat alias). Extended with `default_pnpm_version` + `default_node_version` keys.
- `KernelRenderer.render_all` gains an `only_paths: Sequence[str] | None = None` parameter mirroring `InfrastructureRenderer.render_all`; `_kernel_fallback_render` uses it so user-edited kernel files are never overwritten when one or two are absent.
- `INFRASTRUCTURE_FILES` count moves 31 → 34 (added `.nvmrc`, `.github/dependabot.yml`, `.github/pull_request_template.md`). `FILE_MODES` 0o644 count moves 19 → 22. Group-header integer ranges in the tuple's comments dropped (drift-prone; replaced with bare group labels).
- New tests added across v2.1.5: `test_ci_self_consistency_v215.py`, `test_kernel_security_md_v215.py`, `test_infrastructure_template_fixes_v215.py`, `test_brainstorm_define_v215.py`, `test_build_runner_non_tty_v215.py`, `test_kernel_fallback_v215.py` (new), `test_lp_review_md_invariants_v215.py` (new), `test_lp_commit_md_invariants_v215.py` (new). Plus new tests in `test_bootstrap_render_loop.py` for the BL-355 engine-path coverage. Full suite 1440 → 1577 passing + 4 skipped (1581 collected; +141 net new tests across v2.1.5 + the round-3/4/5 review-fix loops).

## [v2.1.4]

Greenfield-pipeline P0 unblock + bring-your-own-framework path + sub-template walk-scope fix. Surfaced during a 2026-05-14 first-user greenfield dogfood test, which exposed three distinct ship-blockers (one P0 + two P1) for installed-plugin users running through `/lp-pick-stack` → `/lp-scaffold-stack`. Pre-v2.1.4 every manual-override scaffold-stack invocation against the marketplace-cached install layout failed at catalog load — making v2.1.0/v2.1.1/v2.1.2/v2.1.3 effectively non-functional for real users on the install path.

### For LaunchPad users (downstream behavior changes)

- **`/lp-scaffold-stack` now resolves catalogs against the installed-plugin layout (BL-327, P0).** The engine's default `DEFAULT_SCAFFOLDERS_YML` and `DEFAULT_CATEGORY_PATTERNS_YML` previously assumed the source-repo path shape (`<repo>/plugins/launchpad/scaffolders.yml`) and computed `~/.claude/plugins/cache/builtform/plugins/launchpad/scaffolders.yml` against the install layout — wrong `plugins/` infix + missing version subdir. Result for every installed-plugin user: `catalog_load_failed` on every manual-override scaffold-stack invocation. Re-rooted the path arithmetic at `parents[2]` of `engine.py`, which is the LaunchPad ROOT (the dir holding `scaffolders.yml` + `scripts/`) in BOTH source-repo AND install layouts. Three regression tests at `tests/test_install_layout_catalog_paths_v214.py` pin the source-tree happy path, the install-layout path arithmetic, and the full E2E pipeline against a tempdir-built simulated install tree.
- **AstroAdapter `blog` and `marketing` sub-templates now scaffold without spurious symlink rejection (BL-328, P1).** The v2.1 D9.1 hardening (PR #50 P0) walked the entire fetched upstream tree at cache-fetch time rejecting symlinks. withastro/astro@3f67b84b contains test-fixture symlinks under `packages/astro/test/fixtures/...` — outside the `examples/blog` and `examples/portfolio` subtrees AstroAdapter actually copies — but the whole-tree walk rejected them anyway, raising `TemplateCacheError(reason="disallowed_entry_in_fetched_template")` and blocking every Astro `blog`/`marketing` scaffold. Added a `walk_scope: str | None` kwarg to `template_cache.fetch()` / `verify()` / `_entry_files_match_manifest()` (validated against traversal / absolute / NUL / oversize inputs at the cache boundary). AstroAdapter now passes `walk_scope=_SUB_PATHS[sub_template_id]` so the disallowed-entry walk is scoped to the subtree the adapter actually copies. Security invariant preserved at the same boundary, just scoped to the actual copy path. Regression tests at `tests/test_astro_walk_scope_v214.py` cover end-to-end against the real pinned SHA, synthetic outside-subtree symlinks (must succeed), and synthetic inside-subtree symlinks (must still reject).
- **`generic` selectable as a primary stack via `/lp-pick-stack` manual-override (BL-331, P1).** Previously the only path to the `generic` adapter as a primary stack was the v2.2-candidate fallback (passing `--accept-v22-fallback` against a candidate id like `python_generic`), which surfaced an unrelated WARN and obscured the actual user intent. Five new `(generic, role)` tuples land in `lp_pick_stack.VALID_COMBINATIONS` (frontend / frontend-main / frontend-dashboard / backend / fullstack); `scaffolders.yml` gains a `generic:` curate entry pointing at a new `plugins/launchpad/scaffolders/generic-pattern.md` knowledge anchor; `/lp-pick-stack` Step 4's catalog menu surfaces `generic` as the 11th option. Use case: bring-your-own-framework workflows where the user wants the LaunchPad pipeline (lefthook, agents.yml, config.yml, CI) but plans to wire their own framework over the empty workspace shell — third-party Astro themes, custom starters, frameworks not yet supported by a stack-aware adapter (SvelteKit, Remix, Solid, Phoenix-LiveView). The v2.2-candidate fallback path is unchanged. Regression coverage at `tests/test_pick_stack_generic_as_primary_v214.py`.

### For LaunchPad maintainers (developer-facing changes)

- **Pin-rotation parity gate (BL-328 co-ship).** New script `plugins/launchpad/scripts/plugin-upstream-pin-walk-scope-parity.py` clones every pinned upstream SHA and walks the SUBTREE the adapter actually copies (per `_SUB_PATHS` for sub-template adapters; whole-tree for others), failing CI if any disallowed filesystem entry (symlink / block_device / char_device / fifo / socket) is found inside that subtree. Wired into `.github/workflows/v2-handshake-lint.yml` with `--offline-skip` so ephemeral runners that can't reach github.com don't break the build. Catches the BL-328 class of bug at PR time rather than user runtime. Documented at `docs/maintainers/upstream-pin-rotations.md`.
- **`scaffolders.yml` widens 10 → 11 entries.** The `[scaffolders-catalog]` lint rule's hard-coded "exactly 10 stacks" assertion bumps to 11 to accommodate the BL-331 `generic:` entry. Future widening past 11 should land alongside an explicit BL + release-note callout (catalog additions are user-visible) rather than a silent drift.
- **`VALID_COMBINATIONS` widens 21 → 26 tuples.** The `tests/test_valid_combinations.py::test_valid_combinations_count_*` count assertion bumps from 21 to 26. Promotion from inline frozenset to YAML still triggers at >~30 tuples (no change to the threshold).
- **Two pre-existing pins waived in the parity gate's `KNOWN_BAD_PINS` allowlist.** The new parity check exposed two pins that would also fail at user runtime — `nextjs_fastapi` (vintasoftware/nextjs-fastapi-template@62b67456 has `docs/CHANGELOG.md` + `docs/README.md` symlinks) and `astro/docs` (withastro/starlight@2c530192 has `README.md` as a root symlink). Both consume whole-tree (no `walk_scope` to apply); rotation to clean SHAs is tracked as BL-329 + BL-330 for v2.1.5 / v2.2. Waived here so the gate enforces strict for FUTURE rotations without blocking v2.1.4. Workarounds for affected users until BL-329/BL-330 ship: pick `nextjs_standalone` (clean) and wire FastAPI manually, or pick `(generic, backend)` (BL-331) for the BYOF path.

### Backlog hygiene

- **5 new BL entries appended.** BL-327 (catalog-path P0), BL-328 (Astro symlink walk_scope P1 + parity gate), BL-329 (vinta pin rotation, deferred to v2.1.5/v2.2), BL-330 (starlight pin rotation, deferred to v2.1.5/v2.2), BL-331 (generic-as-primary P1). All five surfaced from the same 2026-05-14 first-user greenfield dogfood test session.
- **Latest BL is BL-331.** Sequential numbering preserved.

### Verification

- 1402 tests pass (4 skipped) across the Python suite: existing tests + 3 new install-layout regression tests + 6 new generic-as-primary tests + 19 new walk_scope tests + 1 updated count assertion. Real-world install-layout reproduction at `/tmp/repro_install_layout.py` confirms the P0 fix unblocks the surfacing dogfood scenario end-to-end (catalog resolves; pick-stack succeeds; scaffold-stack writes scaffold-receipt.json).
- `plugin-v2-handshake-lint.py` clean.
- `plugin-upstream-pin-walk-scope-parity.py` PASS (5 pins checked, 2 waived per `KNOWN_BAD_PINS`).

## [v2.1.3]

Polish release: documentation refresh + skill metadata correction + obsolete skill removal. No code-path changes. One intentional behavior change for users who previously relied on natural-language phrases to trigger `/lp-commit` — see the lp-commit skill retirement note below; it is by design (two-path commit workflow: `/lp-commit` for the full quality-gated path, natural-language commit phrases for a deliberate quick-bypass path that skips the gates). v2.1.3 is the version Anthropic Marketplace points at for the initial directory submission.

### For LaunchPad users (downstream behavior changes)

- **Skill discovery surface narrows.** Fourteen process skills (loaded by workflow commands; not directly user-invokable through any documented path) gain a `user-invocable: false` frontmatter field: `lp-brainstorming`, `lp-compound-docs`, `lp-creating-skills`, `lp-document-review`, `lp-frontend-design`, `lp-imgup`, `lp-prd`, `lp-rclone`, `lp-react-best-practices`, `lp-responsive-design`, `lp-step-zero`, `lp-stripe-best-practices`, `lp-tasks`, `lp-web-design-guidelines`. Claude Code uses this field to decide which skills are shown in user-facing skill lists. Net effect: cleaner skill autocomplete; users see only the skills they can directly trigger. Two skills are intentionally NOT given the field — `lp-creating-agents` (documented in the catalog as loaded by both `/lp-create-agent` AND natural language) and `lp-verification-before-completion` (documented as auto-triggering on completion-claim phrasing across commands). Adding the field to either would risk silently disabling a documented activation path under whatever Claude Code's `user-invocable` semantics resolves to.
- **`lp-commit` skill removed.** The `/lp-commit` slash command is unaffected — only the redundant `SKILL.md` sidecar (which duplicated the command's content) is gone. **Behavior change for natural-language users**: the deleted SKILL.md previously routed phrases like "commit changes", "commit this", "commit my work", and "ready to commit" to `/lp-commit` automatically. Those natural-language triggers no longer fire — to commit, invoke `/lp-commit` explicitly. The slash command itself is functionally identical. Anyone scripting against `plugins/launchpad/skills/lp-commit/SKILL.md` directly should switch to `plugins/launchpad/commands/lp-commit.md`.
- **Skills catalog count.** `docs/skills-catalog/skills-index.md` and `docs/skills-catalog/README.md` updated from 17 → 16 installed skills.

### For LaunchPad maintainers (developer-facing changes)

- **README major rewrite.** Top-level `README.md` replaces the terse one-line tagline with a structured pitch: "The cold-session tax" framing of the problem, a 7-row competitive landscape table (status quo / methodology plugins / first-party platform features / spec-driven IDEs / context-engineering systems / autonomous-engineer products / loop-and-orchestration toolkits), and a sharper distillation of LaunchPad's specific kernel surface. The competitive table positions LaunchPad against Compound Engineering, Superpowers, BMAD-METHOD, Anthropic Code Review, GitHub SpecKit, AWS Kiro, Tessl, HumanLayer CRISPY, Agent OS, Continue.dev, Devin, OpenHands, Factory.ai, Ralph Loop, Claude Flow, and Goose. Net delta: +259 lines.
- **Methodology-attribution guidance added.** `plugins/launchpad/commands/lp-create-agent.md`, `lp-create-skill.md`, `lp-port-skill.md`, `plugins/launchpad/skills/lp-creating-agents/SKILL.md`, and `plugins/launchpad/skills/lp-creating-skills/SKILL.md` gain a "Methodology attribution" section instructing agent/skill creators to use framework-citation form ("Based on [author]'s [framework]", "Operationalizes [author]'s methodology") rather than ingestion form ("faithful reading", "book-faithful", "ingested", "preserves exact terminology"). Verification grep recipe included. Prevents attribution drift in future agent/skill generation.
- **`docs/growth/` folder added with allowlist gitignore.** A new top-level docs folder (`docs/growth/`) lands with a nested `.gitignore` that allowlist-tracks only `README.md` + `.gitignore` itself; everything else (positioning.md, sales-pitch-storyboard.md, prepositioning-readme.md, and any future strategy work) is gitignored. The tracked `README.md` is the public-facing pointer to the paid Growth Toolkit plugin; the rest is internal strategy work that lives in the repo but stays out of git.

### Backlog hygiene

- **v2.1.3 → v2.1.4 retargets.** The originally-planned v2.1.3 hardening bundle (~22 items surfaced during v2.1.1 sweeps + Phase 4 deferrals) shifts to v2.1.4 to keep v2.1.3 narrowly scoped as a polish release. BL-297 (corpus-trained reviewer), 9 "defer to v2.1.3" decision lines, and 7 "At v2.1.3 design time" headings retargeted in `docs/tasks/BACKLOG.md`.
- **BL-325 seeded (v2.1.4).** New entry for `xargs -r` portability defense-in-depth: Codex flagged on PR #65 commit `0818c16` that `xargs -r` is GNU-specific; empirically disproven on macOS BSD xargs (silently accepts the flag), but worth fixing in v2.1.4 as defense-in-depth for exotic Unix variants. Fix recipe documented: `| xargs -0 sh -c '[ "$#" -eq 0 ] && exit 0; exec TOOL [args] -- "$@"' _` across 12 hook entries.

### Verification

- 1457 tests pass (4 skipped); manifest-version-contract test (BL-319) confirms `plugin.json.version` (2.1.3) matches the latest non-placeholder CHANGELOG heading.
- All lefthook pre-commit hooks pass on the new content (prettier, structure-check, large-file-guard, trailing-whitespace, end-of-file-newline, workflow-action-sha-pin).

## [v2.1.2]

Consumer-side Python lefthook propagation (BL-316). Projects scaffolded with the `nextjs_fastapi` stack now get bandit + ruff-check + ruff-format-check (pre-commit) and pyright + pytest (pre-push) in their generated `lefthook.yml`, propagated from the v2.1.1 self-host gates via a shared `_partials/_python_gates.j2.fragment` partial. Two ride-along fixes (BL-317 dead-code, BL-321 sibling-doc sync) and one new release-engineering invariant test (BL-319) round out the lane.

### For LaunchPad users (downstream behavior changes)

- **Consumer-side Python lefthook gates** (BL-316). Projects scaffolded with the `nextjs_fastapi` stack now get 5 propagated Python gates in their generated `lefthook.yml`: bandit + ruff-check + ruff-format-check (pre-commit) and pyright + pytest (pre-push). **Consumer install required**: gates fail loud with `GATE MISSING: <tool>. Install with: pip install '<tool>[>=minver]'.` if the tools aren't installed. To opt out of any gate: edit `lefthook.yml` and remove the entry, or set `LEFTHOOK=0` for one-off skip. See `docs/architecture/CI_CD.md#consumer-python-gates` for details.
- **Pyright probes `apps/api/` (composition layout) before `api/` (legacy single-stack), then silent-skips** if no Python workspace exists — never bare `pyright` cwd-walk. Pytest tolerates exit 5 (no tests collected on fresh scaffolds).
- **Per-stack scope**: `nextjs_fastapi` only at v2.1.2 (only Python-bearing stack). v2.2 stack adapters with Python workspaces include the new `_partials/_python_gates.j2.fragment` partial with one `{% include %}` line.
- **Tool minimum versions pinned in install hint**: `bandit>=1.7.10` `ruff>=0.5` `pyright>=1.1.350` `pytest>=8`.

### For LaunchPad contributors

- **New release-engineering invariant test** (BL-319). `plugins/launchpad/scripts/tests/test_manifest_version_contract.py` asserts `plugin.json.version` equals the latest non-placeholder `## [v<version>]` heading in `CHANGELOG.md` and that `docs/releases/v<version>.md` exists. Catches H.3-class staleness (plugin.json drifting from the release version) at PR time, not at ship pre-flight.
- **Sibling-doc frontmatter sync** (BL-321). Three reader/writer docs (`lp-harness-todo-resolver.md`, `lp-triage.md`, `lp-resolve-todo-parallel.md`) now document the `file:` field added in v2.1.1 Slice H.4 for `/lp-ship` Step 4.6 staged-diff scope filter.
- **Dead-code cleanup** (BL-317). Removed `validate_subject` from `plugin-restamp-history-hook.py` (zero callers since v2.0; defense preserved inline in `main()`).

### Internal

- New shared template artifacts at `plugins/launchpad/scripts/plugin_stack_adapters/_partials/`: `_python_gates.j2.fragment` (the BL-316 partial) + `_require_tool_macro.j2.fragment` (`require_tool` macro) + `README.md` (naming convention + loader-resolution semantics + v2.2 caveats).

## [v2.1.1]

Mandatory `/lp-review` dual-pass wiring + `--no-context` blind-review flag + Layer 3 static-analysis gate (ruff + bandit + semgrep + pyright). Universal `lefthook.yml` routes test/typecheck/lint through `plugin-build-runner.py` for stack-aware dispatch. **Validation:** v2.1.1's mandatory review gates were validated by passing this very release through them — Phase 5's commit was the first production exercise of the full Layer 1+2+3 stack.

### For LaunchPad users (downstream behavior changes)

- `/lp-review --no-context` flag (bias-stripped blind pass; Phase 1)
- **Mandatory dual-pass review in `/lp-commit` Step 2.5 + `/lp-ship` Step 4.6** — was previously optional yes/no prompt; honors `--skip-review` on hotfix branches with TTY-guarded `BYPASS REVIEW` confirmation + audit-trail trailer (Phase 2). **Behavior change.**
- `/lp-ship` 3-round autonomous fix loop with 90-min timeout (Phase 2)
- Universal `lefthook.yml` (self-host only at v2.1.1) routes test/typecheck/lint through `plugin-build-runner.py` — stack-aware per `.launchpad/config.yml` `commands.*` arrays (Phase 3 D1+D2). **Downstream lefthook propagation tracked as BL-316, scheduled for v2.1.2.**
- New guide: [`docs/guides/CODE_REVIEW_LAYERS.md`](docs/guides/CODE_REVIEW_LAYERS.md) — three-layer architecture rationale + override patterns
- `CLAUDE.md` Definition of Done extended with conditional Python gates (apply only when changes touch `*.py`)

### For LaunchPad contributors (self-host hardening)

- `pytest` direct pre-push lefthook entry (Phase 3 R1-T1-8)
- `plugin-v2-handshake-lint.py` `_is_v2_module()` path-prefix matcher (Phase 3 BL-237 closure)
- Layer 3 static-analysis stack on plugin scripts (ruff + bandit + semgrep + pyright + pytest)
- **3 active cross-cutting invariant semgrep rules + 1 BL-deferred** in `plugins/launchpad/.semgrep/launchpad-internal.yml` (Phase 4) — sentinel-precedes-materialize rule deferred to BL-303 per >2 fail-to-validate iterations
- 8 universal semgrep rules in `plugins/launchpad/.semgrep/general.yml` (Phase 4) — path-traversal rule narrowed post-iteration from `Path() / X` to `open(... + USER_INPUT)`
- pip-compile-locked `requirements.txt` with `--require-hashes` (Phase 4) — Path A authorization; +1228 LOC transitive lock
- `Makefile` with `lock-deps` target for regenerating `requirements.txt` (Phase 4 — Path A authorization)
- Pyright strict mode on 3 security-boundary modules (`decision_validator.py`, `nonce_ledger.py`, `decision_integrity.py`) with documented `# type: ignore` ladders for residual `Any`-leakage (Phase 4 Hybrid disposition); `decision_validator.py` extended directive disables 4 Any-leakage rules
- 8 pyright per-rule severity downgrades in `pyproject.toml` (`reportArgumentType`, `reportOptionalMemberAccess`, etc.) — admits pre-existing v2.0 surface as warnings; gate exits 0
- Vendored version-pin files: `_vendor/{BANDIT,PYRIGHT,RUFF,SEMGREP}_VERSION` (Phase 4)
- 4 `# nosec` annotations with BL/HANDSHAKE/plan cross-reference triple (B602 ×2 + B506 + B608)
- 2 NEW regression-shield tests at `plugins/launchpad/scripts/tests/`: `test_nonce_ledger_mountpoint_tiebreak.py` (D11), `test_cwd_state_single_readme_carveout.py` (D15). D3 cascade-recovery enforced via the pre-existing `test_brownfield_manifests_single_source.py` (which Phase 4 preserved by restoring the `from cwd_state import BROWNFIELD_MANIFESTS` re-export in `plugin-stack-detector.py` per Commit 1 ride-along).
- 6 new step entries in `.github/workflows/v2-handshake-lint.yml` (4 logical tools per Phase 4 R1-T1-12)
- 7 D-verdict FIX items absorbed (D3 + D9 + D10 + D11 + D12 + D13 + D15)
- `nonce_ledger.UUID_HEX_RE` promoted to public alias (Phase 4 amend P1 SoT consolidation)

### Closed BL items

- **BL-236** (Lefthook Python coverage expansion): SHIPPED via Phase 3 + Phase 4 — see PR #62
- **BL-237** (V2_MODULES scope tightening): SHIPPED via Phase 3 — see PR #62
- **BL-245** (Stack-aware lefthook generation): SHIPPED via universal lefthook + build-runner indirection (master plan D1); see PR #62
- **BL-309** (lp-ship.md `exit non_zero` typo): SHIPPED via Slice H.4 (Greptile review fold); see PR #62

### Deferred to v2.1.3 / v2.2

- BL-291..297 + 22 v2.1.1→v2.2 retags + 8 v2.1.1→v2.1.3 retags (per BACKLOG.md)
- BL-298 (pyright strict on engine modules) — v2.1.3
- BL-299 (nodeenv binary outside pip hash coverage) — v2.1.3
- BL-300 (`--strict-dispatch` flag on `/lp-review` — closes Phase 3 Hard Rule 6 violation class) — v2.1.3
- BL-301 (semgrep synthetic-violation fixtures — Phase 4 deferred; Phase 5 Slice F surfaced) — v2.1.3
- BL-303 (`lp-engine-sentinel-must-precede-materialize` semgrep rule — Phase 4 BL-deferred per >2 fail-to-validate iterations) — v2.1.3
- BL-304 (secret-patterns.txt over-match on `\bdownstream\s+project` — false-positive in Jinja-template comment surface) — v2.1.3
- BL-305 (portable timeout wrapper for macOS lefthook entries — `timeout` binary absent on macOS; wrappers removed) — v2.1.3
- BL-306 (semgrep allowlist-vs-handshake-lint parallelism — R2-T1-14 placeholder from Phase 4) — v2.1.3
- BL-307 (9 simplicity-reviewer cleanup-style P1s deferred from Phase 4 /lp-review — out of v2.1.1 scope per Phase 4 sibling triage) — v2.1.3 / v2.2
- Tag-signing automation (BL-258, v2.2) — v2.1.1 tag is unsigned per existing posture (see SECURITY.md)

## [2.1.0]

`/lp-scaffold-stack` now actually scaffolds via specialized v2.1 adapters — the v2.1 Adapter Protocol's `dispatch_by_stack_ids` is wired in production for the 5 active stacks (`ts_monorepo`, `nextjs_standalone`, `nextjs_fastapi`, `astro`, `generic`). The 5 v2.2-candidate stacks (`python_django`, `python_generic`, `nextjs_hono_cloudflare`, `nextjs_trpc_prisma`, `rails`) require explicit opt-in via `--accept-v22-fallback`; v2.2 ships dedicated support. Schema 1.0 decisions are now hard-rejected at validate time — v2.0 reached zero in-the-wild adoption before v2.1 ship; the rejection message names the regeneration recipe verbatim.

Full release notes in [docs/releases/v2.1.0.md](docs/releases/v2.1.0.md).

### Added (v2.1.0 ship)

- `dispatch_by_stack_ids` wired in `/lp-scaffold-stack`'s production pipeline; legacy `materialize_layer` orchestrate/curate path deleted (`layer_materializer.py` removed)
- `--accept-v22-fallback` kwarg surface on `run_pipeline` for v2.2-candidate stack-ids; receipt records `adapter_dispatch_meta.fallback_ids` when used
- `dispatch_enumeration.py` module: post-dispatch workspace walker with symlink rejection, cwd-containment check, `.git*` + credential-dotdir exclusion, 50k-file cap
- Receipt schema gains `LayerReceiptEntry` TypedDict (replaces deleted `MaterializationResult` dataclass) + `adapter_dispatch_meta` allowlisted sibling
- Decision schema_1.1 envelope gains `_META_KEY_REGEX` + `_ALLOWED_DECISION_META_KEYS` allowlist; new `*_meta` keys require schema_version bump

### Bug fixes (v2.1.0 ship)

- `atomic_io._write_all` POSIX short-write loop at all 3 atomic-write call sites (was `os.write` once; could silently truncate)
- Case E "y" all-files-missing schema corruption fix: signal moves from `_meta` smuggled into `kernel_render_state` (corrupted per-file uniform shape) to a top-level `kernel_render_state_meta` sibling
- Workflow SHA-pinning at all 8 sites (root + `.j2` templates) with new lefthook grep gate enforcing the pin
- Downstream `.j2` workflows gain `permissions: { contents: read }` and `persist-credentials: false` on `actions/checkout`
- `--seed-brownfield` reframed as `--dry-run`-only at v2.1.0; non-dry-run create path lands at v2.1.1 BL-271
- `lp-scaffold-stack.md` doc drift reconciled to the new v2.1 dispatch surface

### Added

- Sealed identity contract: 7-field identity block (`pii_opt_in`, `project_name`, `email`, `copyright_holder`, `repo_url`, `license`, `license_other_body`) sealed under `schema_version: "1.1"` envelope at `/lp-pick-stack` time
- `/lp-bootstrap` command: bootstraps the harness configuration from plugin-bundled defaults with sentinel-protected execution
- `/lp-update-identity` command: edits sealed identity values atomically with byte-identical preservation of `generated_at` across re-seal; 5-case re-entry detection (A through E) with transparent legacy v1.0 envelope migration
- Composition wrapper at `plugin_stack_adapters/composition.py`: pair-table-from-data resolution at runtime, per-stack tempdir isolation, N=2 cap on multi-stack scaffolds
- 7 stack-agnostic kernel templates (LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, README.md, SECURITY.md, AGENTS.md, CLAUDE.md) with full canonical license bodies for MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, ISC, MPL-2.0
- Stack-aware review dispatch: 36 review agents gain `stack_scope` frontmatter (16 `core_pipeline`, 13 `stack:any`, 6 `design_quality`, 1 `skill_quality`); `/lp-review` and `/lp-harden-plan` filter agents per detected stack
- `StackIdV22Candidate` forward-compat enum: 5 v2.2-candidate stack ids (`python_django`, `python_generic`, `nextjs_hono_cloudflare`, `nextjs_trpc_prisma`, `rails`) routed to `generic` with verbatim INFO log
- `lp_define_runner.py` render-batch flow: `render_batch` + `scan_batch` + `write_batch` gates every kernel and adapter render through a full-batch secret scanner; any finding refuses the entire batch atomically
- `secret_allowlist.py` with three suppression mechanisms (Jinja-comment, file-path-glob, regex) plus `BUNDLED_DEFAULT_PATTERNS` fallback when `.launchpad/secret-patterns.txt` is absent
- `docs/guides/SECRET_SCANNER_TUNING.md`: tuning guide for the secret-scanner gate

### Changed

- v2.0 scaffold artifacts auto-migrate to `schema_version: "1.1"` on first contact with the v2.1 plugin via in-memory-first transparent migration
- Bidirectional sentinel cross-detect across `/lp-bootstrap`, `/lp-update-identity`, `/lp-scaffold-stack` so two concurrent operations cannot corrupt each other's state
- ALLOWLIST-based handshake-lint over `atomic_write_replace` callers via AST + import-binding resolution; alias-rename bypasses caught at lint time
- CODEOWNERS extended with 8 v2.1 schema-source entries; modifications to schema constants require same-commit append-only audit-log entries

### Deferred

- v2.2: composition wrapper test stress harness (3 tests under `test_composition_wrapper.py` family); template cache concurrency hardening; brainstorm Python runner extraction; `pip-audit` and `osv-scanner` promotion from advisory to required gates; 4 manifest tampering scenarios (NullByteInjection, UnicodeNormalizationAttack, ZIP-bomb, ConcurrentModification); GPG-signed tags
- See `docs/tasks/BACKLOG.md` BL-251 through BL-254

## [2.0.0] — 2026-05-01

Major release. Greenfield project scaffolding pipeline ships: `/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define`. Chain-of-custody-bound (SHA-256 envelopes + UUID4 nonces + bound_cwd triple), brownfield-aware (refuses to scaffold over existing projects), 10-stack catalog. Brownfield path unchanged from v1.x.

Full release notes in [docs/releases/v2.0.0.md](docs/releases/v2.0.0.md).

### Added

- Four-command greenfield pipeline (brainstorm → pick-stack → scaffold-stack → define) with structured `rationale_summary` defense-in-depth so consumers never read raw rationale.md
- 10-stack catalog: `astro`, `next`, `eleventy`, `hugo`, `hono`, `fastapi`, `django`, `rails`, `supabase`, `expo`
- 6 new `/lp-define` adapters: `astro`, `fastapi`, `rails`, `hugo`, `eleventy`, `expo`
- 18-category routing catalog with 5 ambiguity clusters (`category-patterns.yml`)
- Forensic primitives: `decision_integrity.canonical_hash`, `path_validator`, `cwd_state`, `safe_run`, NFKC-aware sanitizer, 1MB-rollover nonce ledger, `bound_cwd` triple, `pid_identity` cross-platform
- 11 OPERATIONS §6 acceptance gates + 8 joint-pipeline integration tests + 100-iteration nonce concurrency race loop + adversarial corpus (10 mutations, 100% reason-match coverage)
- `.github/workflows/v2-handshake-lint.yml` (PR-triggered) + `.github/workflows/v2-release.yml` (tag-triggered single-shot 4-check verify-v2-ship battery)
- Python-wired `lefthook` commit-msg hook with subject-line injection-defense (`\n` / `\r\n` / lone `\r` rejection)

### Deferred

- v2.1: METHODOLOGY/HOW_IT_WORKS/governance documentation refresh
- v2.2: 15 operational/security infrastructure surfaces (BL-215 + BL-220–BL-235) plus 10 deferred stacks (sveltekit, elysia, phoenix-liveview, convex, flutter, tauri, cloudflare-workers, nestjs, laravel, vite)

## [1.1.0] — 2026-04-27

Minor release. Adds an enforcement-style skill that mandates fresh verification evidence before any agent claims work is done. No breaking changes; install path unchanged.

### Added

- **`lp-verification-before-completion` skill.** Enforces evidence-before-claims for completion assertions. Maps each kind of completion claim ("tests pass", "build green", "PR ready", "Definition of Done met") to the verification command that proves it (test/typecheck/lint/build) and refuses the claim until the command's exit code and output are attached. Auto-triggers on completion-claim phrasing across commands. Closes the most common agentic failure mode where work is declared done without running the checks. The TS-stack pnpm examples in the skill prose are illustrative; for other stacks, commands resolve to `.launchpad/config.yml`'s `commands.test`/`commands.typecheck`/`commands.lint`/`commands.build` arrays via `plugin-build-runner.py`. Adapted from [obra/superpowers](https://github.com/obra/superpowers) (MIT). See `plugins/launchpad/skills/lp-verification-before-completion/SKILL.md`.

### Documentation

- `docs/skills-catalog/skills-index.md` — new entry for `lp-verification-before-completion` plus full Detailed Description; closes a pre-existing gap by adding the missing entry for `lp-step-zero`; numbering 1–17 contiguous across all sections; header count reconciled with `README.md` and the on-disk skills directory at 17
- `docs/skills-catalog/README.md` — harness-skills count and alphabetical list updated (16 → 17)
- `docs/releases/v1.1.0.md` — hand-authored release notes (required by the LaunchPad-only release-notes-check gate)

### Internal

- All 15 plugin test suites pass; frontmatter integrity check now reports 17 skills (was 16)
- Full `ci.yml` required-checks suite green (Type Check, Lint, Build, Test, Repo Structure, Install)
- Greptile + Codex dual-reviewer cycle ran clean

## [1.0.1] — 2026-04-26

Patch release: dependency hygiene and a second AI code reviewer for every PR. No production code changes — the plugin behavior at install is identical to v1.0.0.

### Security

- **23 of 26 flagged CVEs cleared** via direct dep bumps + `pnpm update --recursive && pnpm dedupe`
  - High-severity fixes: `hono` → 4.12.15 (arbitrary file access via serveStatic), `@hono/node-server` → 1.19.14 (auth bypass via encoded slashes), `next` → 15.5.15 (Server Components DoS), `picomatch` (ReDoS), `defu` (proto pollution), `effect` (concurrency context contamination), `flatted` (proto pollution)
  - Medium-severity fixes: cleared 12+ medium CVEs across `hono`, `next`, `picomatch`, `brace-expansion`, `postcss`, `vite`, and others
- **3 residual CVEs** in deeply-transitive copies (esbuild 0.21.5, postcss 8.4.31, vite 5.4.21) pinned by other dependencies; addressable via `pnpm.overrides` if upstream Dependabot keeps flagging them
- **GitHub Actions runners upgraded** to current major versions (commit-pinned): `actions/checkout` v6.0.2, `actions/setup-node` v6.4.0, `actions/cache` v5.0.5

### Added

- **Greptile as a second AI code reviewer** alongside Codex on every PR. Codex covers the narrow / line-level lane (per-PR diff context); Greptile covers the wide / codebase-aware lane (pre-indexed graph of the whole repo). Both advisory only; merge gating remains the existing required `ci.yml` jobs. Configured via `greptile.json` at repo root.
- **Template support for downstream projects** — `greptile.template.json` + `init-project.sh` swap-chain wiring so projects scaffolded from the LaunchPad template inherit the dual-reviewer pattern automatically.
- New CI workflow `.github/workflows/release-notes-check.yml` (LaunchPad-only) — enforces that every release PR and tag push includes a hand-authored `docs/releases/v<VERSION>.md` file.
- New maintainer-only doc `docs/maintainers/RELEASE_PROCESS.md` (LaunchPad-only) — explicit step-by-step release checklist.

### Changed

- `/lp-commit`, `/lp-ship`, and `/lp-build` PR-monitoring loops now include Gate B3 for Greptile alongside Gate B2 for Codex
- Gate numbering aligned across `/lp-commit` and `/lp-ship` (B1 = human review, B2 = Codex, B3 = Greptile)
- `/lp-ship` autonomous auto-fix criteria for Greptile findings now use concrete signals (P0/P1 severity + cross-file evidence)

### Documentation

- New `docs/architecture/CI_CD.md` — full dual-reviewer reference, Dependabot hygiene, merge protocol
- `docs/guides/HOW_IT_WORKS.md` — tech-stack table updated; new "Setting up Greptile" subsection
- `SECURITY.md` — new hardening recommendation describing the dual-reviewer pattern
- `docs/architecture/REPOSITORY_STRUCTURE.md` + `scripts/maintenance/check-repo-structure.sh` — root-file whitelist now allows `greptile.json` and `greptile.template.json`

Full details in [docs/releases/v1.0.1.md](docs/releases/v1.0.1.md).

## [1.0.0] — 2026-04-24

First public release. LaunchPad is now installable as a Claude Code plugin from the BuiltForm marketplace and runs end-to-end in any brownfield repository — no template clone required.

### Added

- **Plugin packaging.** Repository ships `.claude-plugin/marketplace.json` (marketplace name: `builtform`) and `plugins/launchpad/.claude-plugin/plugin.json` (plugin name: `launchpad`). Installable via `/plugin install launchpad@builtform`.
- **38 slash commands** organized as four meta-orchestrators (`/lp-kickoff`, `/lp-define`, `/lp-plan`, `/lp-build`) plus L2 commands for review, ship, commit, harden, learn, and triage workflows.
- **36 sub-agents** in 6 namespaces: `research/`, `review/`, `resolve/`, `design/`, `skills/`, and `document-review/`. Code reviewers are stack-aware — TypeScript reviewer dispatches when TS detected, Python reviewer when Python detected.
- **16 skills** covering design workflows, document review, commit discipline, brainstorming, planning, and skill authoring.
- **Stack detector** with allowlist-only manifest reading. Reads `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json` only — never touches `.env*`, `.npmrc`, `secrets.yml`. Bounded walk depth, hard-excludes vendored directories, 1 MB per-manifest size cap. Output is alphabetically sorted for deterministic re-runs.
- **Stack adapters** for `ts_monorepo`, `python_django`, `go_cli`, `generic`, plus a `polyglot` composer that merges multi-stack outputs deterministically (TS > Python > Go > generic precedence).
- **Doc generator.** Jinja2-rendered (autoescape on) templates for `PRD.md`, `TECH_STACK.md`, `BACKEND_STRUCTURE.md`, `APP_FLOW.md`, `SECTION_REGISTRY.md`, `config.yml`, and `agents.yml`. Pre-write secret scanner refuses on AWS, GitHub, Stripe, Anthropic, OpenAI, Slack, and DB-credential patterns. Realpath-confined writes.
- **Vendored pure-Python runtime.** Jinja2 + MarkupSafe + PyYAML bundled inside the plugin. Zero `pip install` at plugin-install time; runs on any Python 3.10+.
- **Config-driven L2 commands.** `/lp-commit`, `/lp-ship`, `/lp-review`, `/lp-test-browser`, `/lp-harden-plan` read shell invocations from `.launchpad/config.yml`. Same command works in TypeScript monorepos, Python backends, Go CLIs, or polyglot repos.
- **Audit log.** `.launchpad/audit.log` (gitignored by default) records every autonomous command with ISO-8601 timestamp, git user, commit SHA, content-hash of canonical commands, and invoking command name. Hash survives rebase/amend/squash. Opt in to commit via `audit.committed: true`.
- **Autonomous-execution gates.** `/lp-build` requires `.launchpad/autonomous-ack.md` to exist as a tracked file, and refuses to run if the section spec and acknowledgment file land in the same commit. The `LP_CONFIG_REVIEWED` environment variable must match the canonical commands hash (full 64-char or 16-char prefix accepted).
- **Multi-agent review with confidence scoring.** `/lp-review` dispatches code, database, design, and copy reviewers in parallel. Findings carry confidence scores (0.00–1.00); only those at or above 0.60 reach actionable todos. Multi-agent agreement adds +0.10; security-flagged findings add +0.10; P1-severity has a 0.60 floor.
- **Multi-layer merge prevention.** Commands refuse to run `gh pr merge` or `git merge main`; a `PreToolUse` hook intercepts them at the tool level; GitHub branch protection backs the rule server-side.
- **Pre-dispatch secret scan.** `/lp-review` scans every added line against `.launchpad/secret-patterns.txt` before any review agent is dispatched. Hits block review.
- **`--dry-run` preview.** `/lp-inf --dry-run` reports which section, plan file, and branch the build would use without running the loop.
- **Compound learning.** `/lp-learn` writes structured solution docs to `docs/solutions/` after each `/lp-build` cycle, indexed by category and tags for semantic retrieval by `learnings-researcher` agent on subsequent builds.

### Documentation

- [README.md](README.md) — install paths, first 15 minutes, what's inside, security summary, links
- [HOW_IT_WORKS.md](docs/guides/HOW_IT_WORKS.md) — operator's manual covering every phase
- [METHODOLOGY.md](docs/guides/METHODOLOGY.md) — six-layer architecture, design principles, agent fleet
- [SECURITY.md](SECURITY.md) — threat model, what the harness controls / does not control, recommended companion (`dcg`), reporting channel
- [ROADMAP.md](ROADMAP.md) — v1.0.x patch line, v1.1 scope, what's not in v1.1, branch model
- [CONTRIBUTING.md](CONTRIBUTING.md) — getting started, PR guidelines, architecture decisions
- [AGENTS.md](AGENTS.md) — cross-tool bridge for Codex / Cursor / Aider / Windsurf / Gemini users
- [docs/guides/MEMPALACE_INTEGRATION.md](docs/guides/MEMPALACE_INTEGRATION.md) — optional pairing with MemPalace for verbatim session-memory recall

### Known limitations

Carried forward into v1.1:

- Python framework detection treats any `pyproject.toml` as `python_django`. FastAPI / Flask projects need manual edit to `.launchpad/config.yml` until the framework-distinction adapter ships.
- Polyglot design-field precedence defaults to `skipped` for TS+Python combinations. Workaround: hand-edit `pipeline.define.design`, `pipeline.plan.design_review`, `pipeline.build.test_browser` in `.launchpad/config.yml`.
- Bare `pytest` invocation assumes no env manager. Detection of `poetry.lock` / `uv.lock` is queued.
- Runner exit code `2` overlaps `pytest`'s collection-error exit. Remap to the reserved 64–78 range is queued.
- `/lp-pnf` and `/lp-brainstorm` Phase 1 are dialogue-heavy; no `--stub` / `--yes-to-all` non-interactive mode yet.
- `/lp-shape-section --from-todo <id>` import adapter for projects with existing TODO files is queued.

Full v1.1 scope in [ROADMAP.md](ROADMAP.md).

[Unreleased]: https://github.com/builtform/launchpad/compare/v2.1.3...HEAD
[v2.1.3]: https://github.com/builtform/launchpad/compare/v2.1.2...v2.1.3
[v2.1.2]: https://github.com/builtform/launchpad/compare/v2.1.1...v2.1.2
[v2.1.1]: https://github.com/builtform/launchpad/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/builtform/launchpad/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/builtform/launchpad/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/builtform/launchpad/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/builtform/launchpad/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/builtform/launchpad/releases/tag/v1.0.0
