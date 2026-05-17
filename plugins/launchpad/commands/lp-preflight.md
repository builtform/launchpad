---
name: lp-preflight
description: Run the external-infrastructure preflight gate (BL-364). Verifies provider account, deploy project, GitHub Secrets, DNS, and spec hygiene before ship.
---

# /lp-preflight

Standalone preflight runner. Reads `.launchpad/preflight.config.yaml`, loads every referenced provider profile from `plugins/launchpad/preflight-profiles/`, runs all checks, writes / updates `.launchpad/preflight-checklist.md`, and exits 0 on pass or non-zero on fail.

Use `/lp-preflight` to verify external-infrastructure prerequisites without committing to a full `/lp-build` or `/lp-ship` run. The same gate fires automatically at Step 0.6 of `/lp-ship` and Step 0.6 of `/lp-build`.

---

## Step 0: Prerequisite Check (Lite)

Run `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-prereq-check.sh --mode=lite --command=lp-preflight --require=.launchpad/preflight.config.yaml`.

If `.launchpad/preflight.config.yaml` is missing, the helper exits 1 with a pointer to this command's setup section.

If the file is missing, suggest a starter config like:

```yaml
# .launchpad/preflight.config.yaml
providers:
  - spec-completeness # always; covers PRD / CHANGELOG / sections / ack
  # add one deploy-provider profile:
  - cloudflare-pages # OR vercel, netlify
  # add one DNS profile (if the project uses a custom domain):
  - cloudflare-dns # OR namecheap-dns

overrides:
  # per-item stale window or args overrides go here. Example:
  cloudflare-pages.api-token-valid:
    stale_window_days: 30
```

---

## Step 1: Run Preflight

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lp_preflight.py --repo-root .
```

The script writes `.launchpad/preflight-checklist.md` and prints a one-screen summary:

- `OK: <N>` — auto-detected (category A) or API-verified (category B) checks that passed, plus user-confirmed (category C1) probes that passed and user-trusted (category C2) items confirmed within the stale window.
- `AWAITING CONFIRMATION: <N>` — C1 / C2 items where the user has not ticked the box yet, or where a previously-ticked confirmation has expired its stale window.
- `FAIL: <N>` — auto-detect or probe failures with the specific reason (env var missing, API returned 404, file not found, etc.).

Exit code 0 if all checks pass; 1 if any check fails or is awaiting confirmation; 2 on config / profile load errors (malformed YAML, profile-file-not-found, etc.).

---

## Step 2: Edit Checklist (if needed)

`.launchpad/preflight-checklist.md` is gitignored by default (per `.gitignore`); it's a user-local working file. Each item has a setup hint inline. To resolve:

- **Auto-detect (A) failures** — take the action named in the setup hint (e.g., create the missing file, remove the `[TBD]` marker, add the CHANGELOG entry). Re-run `/lp-preflight`.
- **API-verified (B) failures** — export the missing env var or fix the credential; re-run `/lp-preflight`.
- **C1 user-confirmation items** — read the setup hint, take the external action (e.g., create the Cloudflare Pages project, configure Namecheap DNS), tick the `- [ ]` box to `- [x]`, save the file, re-run `/lp-preflight`. The probe runs after your tick; probe failure blocks until the probe passes.
- **C2 trust-only items** — read the setup hint, take the action, tick the box. No probe runs; preflight trusts the confirmation. Failures will surface at the actual deploy step.

---

## Step 3: Re-run + Verify

After ticking boxes or fixing failures, re-run `/lp-preflight`. The checklist file regenerates with updated `Last confirmed:` timestamps for newly-ticked items. Items pass once their gate condition holds.

---

## Step 4: Report (TERMINAL)

Print the one-screen summary from Step 1. If exit 0, say "Preflight clean; ready to ship." If exit 1, the summary already named each failing item; do not duplicate it.

---

## Rules

1. **NEVER** auto-tick confirmation boxes. The user must confirm C1 / C2 items by editing the checklist file.
2. **NEVER** auto-create `.launchpad/preflight.config.yaml`. The user / team must declare which providers apply.
3. **NEVER** silently swallow probe errors. Surface every failure in both the terminal summary and the checklist file.
4. **NEVER** modify `.launchpad/preflight.config.yaml`. Reads only.
