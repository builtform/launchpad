# Upstream pin rotations: append-only audit log

Every modification of an `_UPSTREAM_SHA` value in
`plugins/launchpad/scripts/plugin_stack_adapters/pin_registry.py` requires a
same-commit append-only entry in the table below. The rotation-detector lint
rule in `plugin-v2-handshake-lint.py` fails the build if a SHA changes without
a corresponding row landing in the same commit.

This file is committed (not gitignored). It lives at `docs/maintainers/` to
match the `RELEASE_PROCESS.md` precedent.

## Resolution method

Every recorded SHA must have been dual-resolved before landing:

1. Authenticated `git ls-remote` (`GH_TOKEN` / `GITHUB_TOKEN` env-var when
   present).
2. GitHub REST `/repos/{owner}/{repo}/git/refs/tags/{tag}`, with annotated tags
   dereferenced via `/repos/{owner}/{repo}/git/tags/{sha}`.
3. Both calls MUST return the same commit-object SHA. Mismatch aborts the
   rotation.
4. `gh attestation verify` is invoked where the upstream publishes
   attestations. If absent, `attestation_ref` in `pin_registry.py` is recorded
   as `unsigned`.

## Schema

| Column     | Description                                                                         |
| ---------- | ----------------------------------------------------------------------------------- |
| Date       | ISO-8601 `YYYY-MM-DD` (UTC).                                                        |
| Adapter    | `adapter_id` from `pin_registry.py` (e.g. `nextjs_standalone`, `astro/docs`).       |
| Old SHA    | Previous 40-char commit SHA, or `(initial)` for the first record of a pin.          |
| New SHA    | New 40-char commit SHA. Must match `^[0-9a-f]{40}$`.                                |
| Reason     | Free text. For initial entries: dual-resolution evidence. For rotations: CVE / fix. |
| Reviewer   | Maintainer handle who verified the dual-resolution.                                 |
| Linked CVE | CVE id when the rotation responds to a vulnerability; `n/a` otherwise.              |

## Rotations

| Date       | Adapter           | Old SHA   | New SHA                                  | Reason                                                                                                             | Reviewer | Linked CVE |
| ---------- | ----------------- | --------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------- | ---------- |
| 2026-05-05 | nextjs_standalone | (initial) | 9aad7123ef8accc79d6ece399f249c46bdb6b138 | Slice A0b lock; vercel/next-forge@v6.0.2; dual-resolved (git ls-remote + GitHub REST); attestation unsigned        | foad     | n/a        |
| 2026-05-05 | nextjs_fastapi    | (initial) | 62b67456e8f01760970455282282ecaa393fbd38 | Slice A0b lock; vintasoftware/nextjs-fastapi-template@0.0.8 (lightweight tag); dual-resolved; attestation unsigned | foad     | n/a        |
| 2026-05-05 | astro/docs        | (initial) | 2c530192705d569a7f6f29a33cd34b61932f786e | Slice A0b lock; withastro/starlight@@astrojs/starlight@0.38.5; dual-resolved; attestation unsigned                 | foad     | n/a        |
| 2026-05-05 | astro/blog        | (initial) | 3f67b84bcfd232574a4832d4d32fcc724fdd3be5 | Slice A0b lock; withastro/astro@astro@6.2.2 (examples/blog path); dual-resolved; attestation unsigned              | foad     | n/a        |
| 2026-05-05 | astro/marketing   | (initial) | 3f67b84bcfd232574a4832d4d32fcc724fdd3be5 | Slice A0b lock; withastro/astro@astro@6.2.2 (examples/portfolio path); dual-resolved; attestation unsigned         | foad     | n/a        |
