---
name: lp-update-identity
description: Update sealed identity values (project rename, license change, copyright holder, email, repo URL fill-in) without re-scaffolding. Re-renders the 7 kernel files via KernelRenderer.refresh().
---

# /lp-update-identity

## Synopsis

```
/lp-update-identity                              → interactive identity update
/lp-update-identity --seed-brownfield            → seed identity for legacy v2.0 / manually-created project
/lp-update-identity --allow-email-mismatch       → override git config user.email cross-check (Case D)
/lp-update-identity --quiet                      → suppress PII WARN print + diff summary (does NOT suppress Case D --seed-brownfield banner, brownfield Continue prompt, or --allow-email-mismatch WARN)
/lp-update-identity --dry-run                    → compute diff but do not write
```

**Arguments**: `$ARGUMENTS` (parse for `--seed-brownfield`, `--allow-email-mismatch`,
`--quiet`, `--dry-run`).

Identity updates run via `lp_update_identity.engine.run_update_identity()`
which directly invokes `KernelRenderer.refresh()` per Phase 3 cement
(`lp_bootstrap/__init__.py:10-14`); NOT routed through `/lp-bootstrap --refresh`.

---

## Preconditions

`run_update_identity()` runs `_validate_preconditions()` (inline per DA4)
before any prompts fire. The 6 checks halt cleanly with structured error:

1. `scaffold-decision.json` exists and is readable → else `SCAFFOLD_DECISION_MISSING`.
2. Schema is `1.1` (legacy `1.0` triggers seed-as-first-time per re-entry case B).
3. No `/lp-update-identity` sentinel from a prior interrupted run → else recover-stale OR refuse.
4. No `/lp-bootstrap` sentinel from concurrent run → else `BOOTSTRAP_IN_PROGRESS`.
   Bidirectional cross-detect also covers `/lp-scaffold-stack`.
5. `.launchpad/` directory writable → else `PERMISSION_DENIED`.
6. `config.yml` schema readable → else WARN + fall back to scaffold-decision's `stacks:` array.

---

## Prompt protocol

Mirrors `/lp-pick-stack` Step 1.5 lines 88-151 per DA2. Up to 7 prompts:

1. **project_name** (regex-allowlisted)
2. **email** (regex-allowlisted; re-asked verbatim from /lp-pick-stack)
3. **copyright_holder** (printable ASCII; forbidden chars `` ` " ' $ ; { } < > % ``)
4. **repo_url** (`https?://...`)
5. **license** (closed enum: `MIT`, `Apache-2.0`, `GPL-3.0`, `BSD-3-Clause`, `ISC`, `MPL-2.0`, `Other` — sourced from `lp_pick_stack.LICENSE_ENUM`)
6. **PII opt-in** (Y/N) — ALWAYS re-asked per code-simplicity P3-folded.
7. **license_other_body** (conditional; only when license=`Other` is selected)

Each prompt shows the current value as the default ("Press Enter to keep '<current>'").

License enum transitions (e.g., MIT → Other) trigger the conditional Other-body prompt
with full Phase 1 sanitization (10KB cap, printable ASCII + newlines, no Jinja
delimiters, no HTML tags).

---

## Re-entry table

Per DA5 5-case matrix (detection order: flag → file → schema → identity → state-block):

| Case  | Trigger                                                                                                                  | Behavior                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ----- | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | scaffold-decision.json absent AND `--seed-brownfield` NOT passed                                                         | `SCAFFOLD_DECISION_MISSING`; remediation points at `/lp-pick-stack` OR `--seed-brownfield`.                                                                                                                                                                                                                                                                                                                                 |
| **B** | scaffold-decision present, schema 1.1, identity absent                                                                   | seed-as-first-time: prompt all 5 fields + PII opt-in + conditional Other-body; status `SEEDED_FIRST_TIME`.                                                                                                                                                                                                                                                                                                                  |
| **C** | All prompts return current values                                                                                        | no-op: skip writes; status `NO_OP`; print current sealed identity values verbatim.                                                                                                                                                                                                                                                                                                                                          |
| **D** | scaffold-decision absent AND `--seed-brownfield` passed                                                                  | Permitted; emit P1 console banner naming all 6 fields about to be seeded (banner + brownfield Continue prompt + `--allow-email-mismatch` WARN are NOT suppressed by `--quiet`); cross-check proposed `email` vs `git config user.email`. Empty/unset email = mismatch (fail-closed). Mismatch + no `--allow-email-mismatch` = REFUSE with `GIT_CONFIG_EMAIL_MISMATCH`. Mismatch + `--allow-email-mismatch` = WARN, proceed. |
| **E** | scaffold-decision present, identity present, but `kernel_render_state` field missing (pre-Phase-10 v2.0/v2.1.0 scaffold) | One-time prompt: `[N/diff/y]` (default N; recommends diff). On `diff`: show on-disk vs freshly-rendered template per file (~50-100ms typical). On `y`: seed `kernel_render_state` from current on-disk content. On `N`: refuse with branched remediation (`git checkout HEAD -- <file>` for tracked; `rm <file>` followed by re-running `/lp-bootstrap` for untracked).                                                     |

Detection-order rule (per DA5): the table is read in flag-then-file-then-schema-then-identity-then-state-block order; flag presence wins over file presence when both apply, so Case D fires before Case A when `--seed-brownfield` is passed and scaffold-decision.json is absent. Case A's trigger is now explicit about the absence-of-flag precondition so the table is self-disambiguating without requiring the reader to remember the detection order.

---

## Error codes

8 codes per DA4 (collapsed from v1's 10):

| Code                          | User category        | Meaning                                                                                                 |
| ----------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------- |
| `scaffold_decision_missing`   | Cannot start         | scaffold-decision.json absent / unreadable.                                                             |
| `identity_update_in_progress` | Cannot start         | another `/lp-update-identity` is running (live PID); OR sentinel JSON corrupt.                          |
| `bootstrap_in_progress`       | Cannot start         | `/lp-bootstrap` or `/lp-scaffold-stack` is running.                                                     |
| `permission_denied`           | Cannot start         | `.launchpad/` directory not writable.                                                                   |
| `user_edit_blocks_refresh`    | Blocked by user edit | per-file: on-disk sha ≠ prior `rendered_content_sha256` (user edited post-render).                      |
| `identity_validation_failed`  | Validation failure   | identity field fails allowlist regex / forbidden chars / license enum.                                  |
| `git_config_email_mismatch`   | Brownfield refused   | proposed email mismatches `git config user.email` (fail-closed; override via `--allow-email-mismatch`). |
| `brownfield_seed_refused`     | Brownfield refused   | scaffold-decision absent without `--seed-brownfield` flag.                                              |

Status codes (info-class returns; not errors): `updated`, `no_op`, `seeded_first_time`.

**Error message PII rule** (security-lens P2): structured errors quote the FIELD NAME but never the user-supplied VALUE; remediation messages may show the regex/enum but not the rejected input.

---

## PII WARN

Always print on every successful invocation when stdout is a TTY (per adversarial P2: respects CI/quiet workflows). For non-TTY runs, single-line WARN to stderr only. `--quiet` flag suppresses.

**Content** (locked verbatim per DA6; regression test in `test_update_identity_engine.py::test_pii_warn_locked_verbatim_two_line_string`):

```
WARN: prior identity values persist in git history (LICENSE, CONTRIBUTING.md, ...).
      See docs/guides/IDENTITY_AND_PII.md for removal options.
```

Yellow ANSI if TTY; uncolored otherwise. Print position: AFTER successful completion, BEFORE the diff summary print.

---

## Diff summary format

Phase 10 §3.12 literal mock:

```
✓ Identity updated.

Fields changed:
  project_name:     OldName  →  NewName
  license:          MIT      →  Apache-2.0
  copyright_holder: <unchanged, pii_opt_out placeholder>

Kernel files re-rendered (5 of 7):
  ✓ LICENSE
  ✓ CONTRIBUTING.md
  ✓ README.md
  ✓ AGENTS.md
  ✓ CLAUDE.md
  ✗ CODE_OF_CONDUCT.md (skipped: USER_EDIT_BLOCKS_REFRESH)
  ✗ SECURITY.md (skipped: USER_EDIT_BLOCKS_REFRESH)

WARN: prior identity values persist in git history (LICENSE, CONTRIBUTING.md, ...).
      See docs/guides/IDENTITY_AND_PII.md for removal options.
```

**Truncation rules**:

- Field values longer than 80 chars: truncate to first 77 chars + ellipsis `…`. Applies to `license_other_body` primarily.
- Multi-line values: replace newlines with literal `\n`. Full content stays in the file.
- Unicode width: rely on terminal's own rendering (CJK chars may visually exceed 80 cells; acceptable v2.1 first-cut).
- Left-align field names; values separated by `→` arrow.

---

## Examples

### 1. Project rename (most common)

```
$ /lp-update-identity
project_name [demo-project]: renamed-project
email [owner@example.com]:
copyright_holder [Demo Owner]:
repo_url [https://github.com/example/demo]:
license [MIT]:
PII opt-in [Y/n]: Y

✓ Identity updated.

Fields changed:
  project_name:  demo-project  →  renamed-project

Kernel files re-rendered (5 of 7):
  ✓ LICENSE
  ✓ README.md
  ✓ AGENTS.md
  ✓ CLAUDE.md
  ✓ CONTRIBUTING.md
  ✗ CODE_OF_CONDUCT.md (skipped: USER_EDIT_BLOCKS_REFRESH)
  ✗ SECURITY.md (skipped: USER_EDIT_BLOCKS_REFRESH)
```

### 2. License change MIT → Apache-2.0 (license enum transition)

```
$ /lp-update-identity
...
license [MIT]: Apache-2.0
...

✓ Identity updated.

Fields changed:
  license:  MIT  →  Apache-2.0

Kernel files re-rendered (1 of 7):
  ✓ LICENSE
```

### 3. Brownfield seed (legacy v2.0 / manually-created project)

```
$ /lp-update-identity --seed-brownfield
WARN: brownfield seed; about to seed:
  project_name: ...
  email: ...
  copyright_holder: ...
  repo_url: ...
  license: ...
  pii_opt_in: ...
Continue [y/N]:
```

If `git config user.email` is unset or mismatches the proposed email,
the engine refuses with `GIT_CONFIG_EMAIL_MISMATCH` unless
`--allow-email-mismatch` is also passed (in which case a WARN is
emitted and the seed proceeds).
