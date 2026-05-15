---
title: Scaffold Handshake — v2.0 Cross-Plan Contracts
date: 2026-04-30
status: Binding contract for v2.0 implementation; Layer 3-absorbed (Path γ, 2026-04-30); both v2.0 plans reduce to references against this document
applies_to: LaunchPad plugin v2.0+ (`/lp-brainstorm`, `/lp-pick-stack`, `/lp-scaffold-stack`, `/lp-define`)
companion: docs/architecture/SCAFFOLD_OPERATIONS.md (governance, CI, freshness, telemetry, Tier 1 panel, acceptance gates, amendment trail)
last_validated: 2026-05-01
---

# Scaffold Handshake — v2.0 Cross-Plan Contracts

This document is the binding **contract** layer of v2.0's cross-plan handshake. It defines schemas, algorithms, validators, and version policy. It does NOT define governance, drift mitigation, freshness policy, telemetry, panels, or amendment process — those live in the companion document `docs/architecture/SCAFFOLD_OPERATIONS.md`. The split exists so the contract layer stays small and stable; the operations layer absorbs ongoing changes without requiring a contract bump.

The two v2.0 implementation plans (`docs/plans/launchpad_plans/2026-04-29-v2-scaffolding-layer-test-plan.md` and `docs/plans/launchpad_plans/2026-04-29-v2-pick-stack-implementation-plan.md`) reference this doc + the operations doc rather than re-declaring contracts independently. Where a plan body and these documents conflict, **these documents win.** Where the two documents conflict with each other, **the contracts doc wins** (this file).

This is a LaunchPad-internal architecture contract, not a downstream-template doc. Downstream projects consume the v2.0 pipeline as users; they do not need to understand or modify these documents.

## 1. Purpose

The v2.0 pipeline crosses three trust boundaries (user input → pick-stack → scaffold-stack → define) and four commands. Each boundary needs a deterministic, integrity-checked contract or the pipeline collapses into "trust the JSON file someone wrote." The joint cross-plan hardening review on 2026-04-29, plus a follow-up final review on 2026-04-30 and a final-final consolidation pass on 2026-04-30, together surfaced eight P1-severity gaps and ~80 P2/P3 items caused by under-specified contracts; this document closes the contract layer.

## 1.4. `pid_start_time` cross-platform format (Layer 7 v2.0 — closes L6-λ #3; Layer 8 hardened)

`restamp-history.jsonl` and `scaffold-rejection-<ts>.jsonl` both carry `pid` + `pid_start_time` as baseline forensic identity at v2.0. Format is pinned to **ISO 8601 UTC second-precision** with cross-platform reader:

```python
import psutil
from datetime import datetime, timezone

def get_pid_start_time() -> str:
    """Return the start time of the CURRENT process as ISO 8601 UTC sec-precision.

    Cross-platform via psutil. Linux reads /proc/self/stat; macOS reads via Mach kernel API;
    Windows reads via QueryProcessTimes. All produce a Unix epoch float; we render to ISO 8601
    UTC sec-precision (matches `generated_at` format used elsewhere in v2.0).

    Layer 8 narrowing: signature accepts NO arbitrary pid argument at v2.0. Only own-process
    forensic identity is sanctioned. Cross-process forensic identity (with PID-reuse race
    handling) deferred to v2.2 alongside forensic_writer.py per BL-223 — at which point the
    signature MAY widen to accept (pid: int, expected_start_time: float) for verified lookup.
    """
    return datetime.fromtimestamp(
        psutil.Process().create_time(), tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
```

`psutil` is added to `plugins/launchpad/scripts/_vendor/` alongside vendored `yaml`. **psutil version pin (Layer 8 — closes adversarial P1 + security-lens P2)**: `_vendor/PSUTIL_VERSION` constant pins the vendored psutil version (mirrors the existing `_vendor/PYYAML_VERSION` pattern). Phase -1 acceptance gate parallel to PyYAML: `plugin-v2-handshake-lint.py` cross-references the pinned version against the public CVE feed and refuses to ship if a CVE-affected version is pinned. Without the pin, a hostile psutil upgrade (psutil has had real CVEs around temp-file handling and privilege escalation historically) would silently absorb into v2.0 and become a supply-chain pivot for forensic-identity forgery.

CI lint asserts no platform-specific shell-out (`/proc/<pid>/stat` parsing, `ps -o lstart`, etc.) appears anywhere in the v2.0 codebase — `psutil.Process().create_time()` is the only sanctioned producer, ensuring identical schema validation across Linux/macOS/Windows. CI lint also asserts the function signature accepts no arguments (closes the PID-reuse race for arbitrary-pid callers; v2.2 may widen with verified-lookup semantics).

**Container-namespace caveat (Layer 8 — security-lens P3 noted but not blocking)**: under PID-namespace isolation (Docker, podman), `psutil.Process().create_time()` reads namespace-local `/proc`; values are consistent within a namespace but may differ across namespace boundaries. Within v2.0 threat model (single-maintainer, same-UID concession), this is not exploitable — the forensic identity is still consistent for the writer process across its own lifetime, which is the load-bearing invariant. Cross-namespace forensic identity is not a v2.0 goal.

## 1.5. Strip-Back Notice (v2.0 — Layer 7 strip-back, 2026-04-30) — READ FIRST

> **Elevator pitch (Layer 8 — closes code-simplicity P3)**: v2.0 ships the 4-step user pipeline (`/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define`) + integrity envelopes (SHA-256, nonce ledger, bound_cwd triple) + path validator + greenfield detection + rationale_summary extractor + LP_CONFIG_REVIEWED migration UX. Defers operational/security infrastructure to v2.2 per BL-220 through BL-235. v2.1 is documentation-only. **Inline sections marked `[v2.0 STRIP-BACK: DEFERRED]` override Layer 5 wording**; conflict-resolution always picks the strip-back marker over inline prose.

**Detail follows.** This document was authored across 6 layers of pre-implementation hardening review and accumulated ~50-60% operational/security infrastructure that does not earn its place against v2.0's stated threat model (single-maintainer plugin, ~3-4 downstream projects, "compromised in-process Claude session out of scope," "same-UID attacker out of scope"). Layer 7 strip-back applies user-directed deferral of that infrastructure to v2.2 BL entries, returning v2.0 closer to the original 4-step intent.

**v2.1.x evolution (status update, 2026-05-09):** the original Layer-7 framing of "v2.1 is documentation-only" did not hold. **v2.1.0 shipped the Adapter Protocol** (`composes_with`, `unwrap_strategy`, dispatch routing) and the `scaffold-decision.json` `schema_version: "1.1"` envelope with sealed `identity` block — see [docs/releases/v2.1.0.md](../releases/v2.1.0.md). **v2.1.1 ships review + lefthook hardening** (mandatory dual-pass at `/lp-commit` + `/lp-ship`, `--no-context` flag, Layer 3 static-analysis stack on plugin scripts) — see [docs/releases/v2.1.1.md](../releases/v2.1.1.md). v2.1.1's schema-source touches are **pure refactor** (ruff format, `# type: ignore` comments, per-rule pyright severity downgrades, `# nosec` annotations, plus a public-alias promotion of `nonce_ledger._UUID_HEX_RE` → `UUID_HEX_RE` for SoT consolidation) without changes to documented schema contracts (§3 canonicalization, §4 `scaffold-decision.json` schema, §5 `scaffold-receipt.json` schema, §6 path validator).

**v2.2 absorbs the heavyweight operational/security infrastructure deferred below.**

### What v2.0 SHIPS (this document, as written below, is binding for these primitives)

- **§3 JSON canonicalization + `canonical_hash()`** + `LP_CONFIG_REVIEWED` 5-branch migration UX + `_legacy_yaml_canonical_hash` 12-month deprecation + KAT pair (Linux-only at v2.0; macOS deferred per BL-233)
- **§4 `scaffold-decision.json` schema + 13 validation rules** EXCEPT rule 12 `brainstorm_session_id` (deferred per BL-235; rule renumbers as needed) AND EXCEPT the FD-based marker consumption protocol in rule 10 (deferred per BL-235)
- **§4 rule 10 nonce ledger**: 33-byte fixed records, format header migration, `.scaffold-nonces.lock` separate sentinel, 1MB rollover with 5-bak retention, `max(filename_ts, file_ctime)` backward-NTP `.bak` window, F_FULLFSYNC on darwin, EIO/EROFS handling, filesystem whitelist
- **§4 rule 11 `bound_cwd` triple** (realpath + st_dev + st_ino) with UX-vs-attack rejection distinction
- **§5 `scaffold-receipt.json` schema** including hardcoded `8` for `architecture_docs_rendered` (BL-217 single-source deferred)
- **§6 path validator** with shape + filesystem-realpath checks + ancestor-symlink rejection
- **§7 brainstorm output contract** + `cwd_state_when_generated` + `greenfield` recompute on every re-run
- **§8 greenfield-detection** including `BROWNFIELD_MANIFESTS` single-source enforcement + `cwd_state(cwd)` 500-entry iteration cap + `refuse_if_not_greenfield()` shared helper
- **§9.1 `rationale_summary` extractor** (prompt-injection defense) + **§9.2 `read_and_verify()` knowledge-anchor loader**
- **§10 version policy**: strict-equality `EXPECTED_DECISION_VERSION = frozenset({"1.0"})`; `0.x-test` → `1.0` coordinated bump; user-tree carve-out
- **§11 stack catalog (10 entries)**
- **§12 implementation files** with the deferrals enumerated below

### What v2.0 STRIPS (deferred to v2.2 — read inline sections with this list in mind)

| Stripped from v2.0                                                                                                                                                                                                                                         | Defer to                                                                                                                            | BL                   |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| `forensic_writer.py` SRP-split module + 4 separate locks                                                                                                                                                                                                   | v2.2                                                                                                                                | BL-223               |
| `security-events.jsonl` — entire file path, write protocol, closed event enum, chain-hashing                                                                                                                                                               | v2.2                                                                                                                                | BL-220 + BL-223      |
| `restamp-history.jsonl` `prev_entry_sha256` chain field (baseline injection-defense at v2.0 KEEPS: json.dumps + reject \r\n + flock + 0o600 + schema_version + pid forensic identity, written inline by lefthook commit-msg hook, not via forensic_writer) | v2.2                                                                                                                                | BL-215               |
| Multi-signal CI detection (`_has_ci_filesystem_signal()` filesystem + parent-process check)                                                                                                                                                                | v2.2                                                                                                                                | BL-224               |
| AST `pull_request_target` shape check via PyYAML                                                                                                                                                                                                           | v2.2 (v2.0 ships grep-based)                                                                                                        | BL-225               |
| Tag protection rule + content verification + watchdog                                                                                                                                                                                                      | v2.2 (v2.0 uses branch protection on `main` only)                                                                                   | BL-226               |
| §7.0 `vX.Y.Z-recalled` rename procedure + namespace-squat 404-check                                                                                                                                                                                        | v2.2                                                                                                                                | BL-227               |
| §7.3 24h post-tag observation window + decision matrix                                                                                                                                                                                                     | v2.2                                                                                                                                | BL-228               |
| `rollback-runbook.md` + `branch-protection-token.md` authored runbooks                                                                                                                                                                                     | v2.2                                                                                                                                | BL-229               |
| Consolidated `v2-nightly-checks.yml` workflow + `v2-handshake-lint-static.yml` + `v2-branch-staleness-check.yml` + `branch-protection-watchdog.yml`                                                                                                        | v2.2 (v2.0 ships only `v2-handshake-lint.yml` PR-triggered)                                                                         | BL-230               |
| `recovery_commands` runtime enforcement contract (closed enum + denylist + idempotency + sha256 + `.recovery.lock` + execute-time path re-validation + at-most-one-rerun)                                                                                  | v2.2 (v2.0 ships structured array as forward-compat hint; humans consume prose)                                                     | BL-231               |
| Exponential-backoff polling for `verify-v2-ship`                                                                                                                                                                                                           | v2.2 (v2.0 ships single-shot)                                                                                                       | BL-232               |
| KAT cross-platform parity (macOS CI leg)                                                                                                                                                                                                                   | v2.2 (v2.0 ships Linux-only)                                                                                                        | BL-233               |
| 90-day PAT lifecycle ceremony                                                                                                                                                                                                                              | v2.2 (v2.0 uses long-lived PAT + informal rotation)                                                                                 | BL-234               |
| `.first-run-marker` integrity binding (JSON envelope + sha256 + bound_cwd + dedicated lock + FD-based read + pre-rename re-stat + microsecond+pid timestamp)                                                                                               | v2.2 (v2.0 ships simple positive-presence sentinel)                                                                                 | BL-235               |
| `scaffold-decision.json.brainstorm_session_id` field + §4 rule 12                                                                                                                                                                                          | v2.2 (depends on BL-235)                                                                                                            | BL-235               |
| `verify-v2-ship` 8-check battery (v2.0 ships 4 checks: tag SHA matches squash-merge HEAD; plugin.json version matches tag; no `0.x-test` residual; no leakage regex)                                                                                       | v2.2 absorbs the other 4 (marketplace.json schema + automated reviews green + tag protection content + pre-existing recall-tag 404) | BL-226/BL-227/BL-232 |
| `tests/fixtures/manifest.yml` schema-versioning EVOLUTION POLICY (the field itself ships at v2.0 with `schema_version: "1.0"` per §10 + §12 + §4 strict-equality enforcement; only the v1.1+ schema-bridge spec defers)                                    | v2.2 (Layer 9 reword — closes schema-drift P3-2; v2.1 retarget per Layer 7 strip-back since v2.1 is doc-only)                       | BL-219               |
| `LP_ALLOW_NONLOCAL_FS=1` env-var override                                                                                                                                                                                                                  | v2.1 (already deferred)                                                                                                             | BL-218               |

### What v2.0 SHIPS in DOWNGRADED form (per strip-back)

- **`_is_ci_environment()`** checks env vars only (CI=true + recognized vendor — `GITHUB_ACTIONS`/`GITLAB_CI`/`CIRCLECI`/etc.). No filesystem-marker check, no parent-process check. `LP_CONFIG_AUTO_REVIEW=1` opt-out is honored on env-var match alone. Threat model: a hostile rcfile / dependency postinstall can pivot. Load-bearing defenses remain: CODEOWNERS gate (OPERATIONS §2), soft-warn UX is non-blocking by design.
- **`plugin-v2-handshake-lint.py`** AST `pull_request_target` shape check downgrades to grep-based forbidden-pattern check (regex enumerated in BL-225). Trade-off: bracket-notation/`fromJSON(toJSON())` bypass possible.
- **`verify-v2-ship` CI job** runs 4 checks (tag SHA / plugin.json / `0.x-test` residual / leakage regex), single-shot, no exponential-backoff polling, no `${{ github.run_id }}` self-loop break, no pre-existing recall-tag 404 gate.
- **`.harness/observations/restamp-history.jsonl`** ships baseline injection-defense (json.dumps + reject \r\n via lefthook commit-msg hook, flock on `.restamp-audit.lock`, 0o600, `schema_version: "1.0"`, pid+pid_start_time forensic identity) — but written INLINE by the lefthook commit-msg hook, not via `forensic_writer.write_restamp_audit()`. The `forensic_writer.py` module itself does NOT ship at v2.0.
- **§10 lifecycle bump list** drops references to deferred files: `security-events.jsonl`, `.first-run-marker` JSON envelope schema_version, `restamp-history.jsonl` chain field. Bump list at v2.0 covers: `category-patterns.yml`, `scaffolders.yml`, `plugin-scaffold-stack.py` constants, `lp_pick_stack/__init__.py`, `plugin-scaffold-receipt-loader.py`, frontmatter of HANDSHAKE/OPERATIONS, `tests/fixtures/manifest.yml` AND its top-level `schema_version` (per BL-219 staying v2.1; field exists at v2.0 in stubbed form), recovery JSON `version: "1.0"`, freshness report `schema_version`, telemetry JSONL `schema_version`, plugin.json, marketplace.json, `docs/releases/v2.0.0.md`, `ROADMAP.md` (consolidated 2026-04-30 from prior `docs/v2-roadmap.md`), `restamp-history.jsonl` `schema_version: "1.0"` field (baseline injection-defense ships at v2.0; chain field per BL-215 defers to v2.2).
- **`scaffold-failed-<ts>.json`** ships the structured `recovery_commands` array as a forward-compat hint (per OPERATIONS §6 gate #11). v2.0 readers (humans) consume `recommended_recovery_action` prose + `see_recovery_doc` URL. Closed-enum + denylist + idempotency + sha256 + `.recovery.lock` + execute-time path re-validation + at-most-one-rerun rule + closed `command` set defer to v2.2 BL-231. **v2.0 wirteers MUST emit the structured array** (so v2.2 consumers can validate forward-compat); v2.0 consumers do NOT enforce it.

### Conflict resolution

If any inline section below contradicts this strip-back notice, **THIS NOTICE WINS**. Inline sections retain Layer 5 wording for full audit trail of what was considered; implementers ship per the strip-back contract.

## 2. Trust boundaries

| Source                                                                                  | Trust level                                                          | Validation point                                                                                                                                              |
| --------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins/launchpad/scaffolders.yml`                                                     | **Trusted** (plugin-shipped, CODEOWNERS-gated per OPERATIONS §2)     | Schema validated at load                                                                                                                                      |
| `plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml`                    | **Trusted** (plugin-shipped, CODEOWNERS-gated)                       | Schema validated at load                                                                                                                                      |
| `plugins/launchpad/scripts/lp_pick_stack/data/pillar-framework.md`                      | **Trusted** (plugin-shipped)                                         | Read-only context                                                                                                                                             |
| `plugins/launchpad/scaffolders/<stack>-pattern.md`                                      | **Trusted** (plugin-shipped, checksum-pinned)                        | SHA-256 verified via atomic `read_and_verify()` (§9), bytes-buffer-only consumption                                                                           |
| User free-text input (project description, Q1 free-text branch, manual-override values) | **Untrusted**                                                        | Wrapped in `<untrusted_user_input>` envelope; never reaches a tool with shell or filesystem access                                                            |
| `.launchpad/brainstorm-summary.md`                                                      | **Untrusted-as-data** (contains user-derived content)                | Frontmatter validated; body treated as data, never instructions                                                                                               |
| `.launchpad/scaffold-decision.json`                                                     | **Untrusted-as-input** (orchestration treats as adversarial)         | Full schema validation + SHA-256 + nonce + bound_cwd-triple at consumption (§4)                                                                               |
| `.launchpad/rationale.md`                                                               | **Untrusted-as-data** (derived from user input)                      | NEVER read directly by `/lp-define`; `/lp-define` reads only the pre-extracted, sanitized `rationale_summary` array embedded in `scaffold-decision.json` (§9) |
| `.launchpad/scaffold-receipt.json`                                                      | **Trusted-internally** (orchestration writes; `/lp-define` consumes) | SHA-256 self-hash; orchestration is the only writer                                                                                                           |

### Residual trust assumptions (explicit non-goals)

This contract does NOT protect against the following threat classes; defense at those layers is out of scope for v2.0 and is documented here so reviewers don't read silence as coverage:

- **Compromised in-process Claude session.** All four commands run in the same Claude session with the same tool grants. SHA-256 + nonce + bound_cwd defend against on-disk tampering, replay across repos, and confused-deputy. They do NOT defend against an attacker who has already compromised the session and can both write `scaffold-decision.json` AND read any session-local secrets. Defense at this layer requires OS-process isolation, which is deferred to v3.0.
- **Local-machine root or same-user write attackers.** A user-level attacker on the dev machine (compromised editor extension, hostile dependency `postinstall`) can swap files between command boundaries within the limits of OS file permissions. The atomic `read_and_verify()` helper (§9) closes the specific TOCTOU window for plugin-shipped knowledge-anchor docs; broader local-machine threats require OS-layer defense (file integrity monitoring, sandboxed dev env) and are out of scope.
- **Compromised LaunchPad plugin install.** If `claude /plugin install launchpad` pulls a poisoned version, every contract this document defines is bypassed. CODEOWNERS + branch protection (OPERATIONS §2) reduces the upstream risk; client-side verification is deferred.
- **Parent-process environment.** `safe_run`'s env-allowlist (OPERATIONS §1) protects spawned subprocesses, NOT the orchestrator itself. If Claude is launched with sensitive env vars (`OPENAI_API_KEY`, `GITHUB_TOKEN`, etc.), those remain readable by Claude during pipeline execution. Users running pick-stack with sensitive env vars in their shell environment should `unset` them before invocation, or use a fresh terminal.

### User-facing privacy disclosure

`/lp-pick-stack`'s Step 1 prompt MUST display a one-line privacy notice: "Your project description will be written to `.launchpad/rationale.md`. If you commit `.launchpad/`, this content goes into your git history. Run with `--no-rationale` to skip rationale rendering." `/lp-brainstorm`'s Step 0 prompt mirrors this notice (since brainstorm-summary.md captures user-derived content earlier in the pipeline). `.harness/observations/pick-stack-*.jsonl` and `.harness/observations/v2-pipeline-*.jsonl` audit logs explicitly exclude free-text fields, but their `matched_category_id` sequences across many runs reveal project history. CLAUDE.md's `.gitignore` template lists `.launchpad/rationale.md` AND `.harness/observations/` as candidates for exclusion in downstream projects.

## 3. Canonicalization algorithm

All SHA-256 integrity bindings in v2.0 use **JSON canonicalization** for byte-determinism. This is a deliberate departure from the YAML scheme used in `plugins/launchpad/scripts/plugin-config-hash.py`, which is not reliably byte-deterministic across PyYAML versions for inputs containing user-derived strings. JSON canonicalization is byte-deterministic by spec.

```python
import hashlib
import json

def canonical_hash(payload: dict) -> str:
    """Stable SHA-256 over a dict-shaped payload via JSON canonicalization.

    JSON canonicalization is byte-deterministic across implementations:
    sort_keys + tight separators + ASCII escape + reject NaN/Infinity.
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"canonical_hash requires a dict payload, got {type(payload).__name__}"
        )
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

This module lives at `plugins/launchpad/scripts/decision_integrity.py` and is imported by both `/lp-pick-stack` (write side) and `/lp-scaffold-stack` (read/validate side). It exports `canonical_hash()` only — `read_and_verify()` lives in the sibling module `plugins/launchpad/scripts/knowledge_anchor_loader.py` (§9.2). The split keeps each module single-responsibility: integrity envelope vs. plugin-shipped-asset loading. One import per concern, one implementation, one set of tests.

### Backport requirement

`plugins/launchpad/scripts/plugin-config-hash.py` MUST be migrated to JSON canonicalization in the same v2.0 ship commit. The current YAML scheme works for `config.yml`'s `commands:` block (small, controlled, no user-derived strings), but maintaining two canonicalization schemes invites drift. The v2.0 ship commit bumps both modules atomically.

**Downstream `LP_CONFIG_REVIEWED` migration UX (closes Layer 2 deploy F-14 + data P1-2; Layer 3 spec-flow P1-3 + adversarial P1-RT-8 + product P1-4 + security-lens P1-S3).** The hash-scheme switch is destructive — every downstream user with `LP_CONFIG_REVIEWED=<old-yaml-hash>` set in their shell rcfile, CI secrets, or `.env.local` would otherwise see a hash-mismatch hard-reject on first v2.0 invocation. Spec the migration as the full 5-branch truth table:

```python
import hmac
import os
import sys

reviewed = os.environ.get("LP_CONFIG_REVIEWED")
auto_review = os.environ.get("LP_CONFIG_AUTO_REVIEW") == "1"

# Cell E: env var unset entirely (first-time user OR ephemeral CI without setup).
if reviewed is None:
    if auto_review:
        return ACCEPTED  # CI opt-out: env is already trusted by definition
    return REPROMPT_FIRST_TIME  # distinct user-facing message

# Use hmac.compare_digest for both checks (defensive; both sides public-deterministic
# but constant-time comparison is free and sets a good precedent).
new_hash = canonical_hash(config)
old_hash = _legacy_yaml_canonical_hash(config)

# Cells A + C: current scheme matches (silent ACCEPTED).
if hmac.compare_digest(reviewed, new_hash):
    return ACCEPTED

# Cell B: legacy match (soft-warn; non-blocking).
if hmac.compare_digest(reviewed, old_hash):
    print(  # stderr, not stdout — avoids pipe capture + CI log fingerprinting
        "LaunchPad v2.0 changed how config-review hashes are computed (v1.x used\n"
        "YAML; v2.0 uses JSON for cross-platform reliability). Your existing\n"
        "LP_CONFIG_REVIEWED hash is still honored — but to dismiss this notice:\n"
        f"\n  export LP_CONFIG_REVIEWED={new_hash}\n\n"
        "The legacy hash continues to work through v2.0.x; v2.1.0 will require\n"
        "the new hash. To roll back to v1.1.0 instead:\n"
        "  unset LP_CONFIG_REVIEWED && claude /plugin install launchpad@v1.1.0",
        file=sys.stderr,
    )
    return ACCEPTED

# Cell D: neither matches — config genuinely changed since last review.
return REPROMPT
```

**`LP_CONFIG_AUTO_REVIEW=1` opt-out** — **[v2.0 STRIP-BACK per §1.5: the multi-signal `_has_ci_filesystem_signal()` + `/proc/{ppid}/comm` parent-process check below DEFERRED to v2.2 per BL-224. v2.0 SUBSTITUTE: `_is_ci_environment()` checks env vars only — `os.environ.get("CI") == "true"` AND any of `GITHUB_ACTIONS`/`GITLAB_CI`/`CIRCLECI`/`BUILDKITE`/`JENKINS_HOME`/`TRAVIS` is set. No filesystem-marker check, no parent-process check. Threat-model concession: hostile rcfile / dependency postinstall can pivot via env var alone — load-bearing defenses remain CODEOWNERS gate (OPERATIONS §2) + non-blocking soft-warn UX. Layer 5 wording below preserved as audit trail; v2.0 implementers SKIP it.]** (Layer 3 adversarial P1-RT-8 + Layer 4 security-lens P1-S1 hardened + Layer 5 adversarial P1-A4 + security-auditor P2-2 + security-lens P2-2 hardened with positive filesystem signal): downstream users running in ephemeral environments (Docker, CI, audit-controlled multi-team monorepos) where re-exporting `LP_CONFIG_REVIEWED` between command invocations is operationally heavy can set this env var to suppress the soft-warn — but ONLY honored when the process is detected as CI via **multi-layer signal** (env var + positive filesystem evidence):

```python
import os
import subprocess

# Filesystem signals that interactive shells genuinely lack.
_CONTAINER_MARKERS = ("/.dockerenv", "/run/.containerenv")
_RUNNER_ENV_VARS = ("RUNNER_TEMP", "RUNNER_TOOL_CACHE", "GITHUB_WORKSPACE")
_CI_PARENT_PROCESSES = frozenset({
    "Runner.Worker", "runner.worker", "gitlab-runner", "buildkite-agent",
    "circleci-agent", "jenkins-agent", "agent", "buildkite-builder",
})


def _has_ci_filesystem_signal() -> bool:
    """Positive filesystem evidence of CI runner — env vars alone are forgeable."""
    if any(os.path.isfile(m) for m in _CONTAINER_MARKERS):
        return True
    if any(os.environ.get(v) for v in _RUNNER_ENV_VARS):
        return True
    try:
        ppid = os.getppid()
        with open(f"/proc/{ppid}/comm", encoding="utf-8") as f:
            parent_comm = f.read().strip()
        if parent_comm in _CI_PARENT_PROCESSES:
            return True
    except (OSError, FileNotFoundError):
        pass  # /proc unavailable on macOS; fall through
    return False


def _is_ci_environment() -> bool:
    """Detect CI environment via multi-signal defense.

    CI=true + recognized vendor env + at least one positive filesystem signal.
    Single env-var checks are forgeable by hostile rcfile / dependency postinstall;
    requiring a positive filesystem signal raises the bar significantly.
    """
    if os.environ.get("CI") != "true":
        return False
    if not any(os.environ.get(v) for v in (
        "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI",
        "BUILDKITE", "JENKINS_HOME", "TRAVIS",
    )):
        return False
    return _has_ci_filesystem_signal()


if reviewed is None:
    if auto_review and _is_ci_environment():
        # Audit log: env-trusted opt-out used. Always written, NOT gated by `telemetry: off`
        # (security event, not analytics). See "Security event log" subsection below
        # for the integrity-bound write protocol.
        write_security_event({
            "schema_version": "1.0",
            "event": "auto_review_accepted",
            "config_hash": new_hash,
        })
        return ACCEPTED
    if auto_review and not _is_ci_environment():
        # Also a security event — attempted bypass without CI signals.
        write_security_event({
            "schema_version": "1.0",
            "event": "auto_review_rejected_outside_ci",
            "config_hash": new_hash,
        })
        return REPROMPT_AUTO_REVIEW_OUTSIDE_CI  # distinct user-facing error
    print(  # stderr: hint for headless/CI users on first run
        "First-time setup: please review and export LP_CONFIG_REVIEWED.\n"
        "Headless/CI environment? Set CI=true + LP_CONFIG_AUTO_REVIEW=1 to skip.\n"
        "Note: LP_CONFIG_AUTO_REVIEW requires positive CI filesystem signals\n"
        "(/.dockerenv, GitHub Actions runner env, etc.) — env vars alone do not\n"
        "satisfy the multi-signal CI detector.",
        file=sys.stderr,
    )
    return REPROMPT_FIRST_TIME
```

**Threat-model honesty caveat (Layer 5 security-lens P2-2 + adversarial P1-A4)**: the multi-signal CI detector is **defense-in-depth, not a security boundary**. An attacker with full UID compromise (control over `~/.zshrc` AND `/proc` inspection AND ability to spawn under a recognized parent process name) can still bypass. The `_has_ci_filesystem_signal()` raises the bar significantly past a trivial env-var pivot, but it cannot exceed shell-environment trust. The load-bearing defenses are: (a) the always-written audit log (see "Security event log spec" subsection below — file-mode 0o600, separate lock, append-only, chain-hashed), (b) CODEOWNERS gate on the loader code path (OPERATIONS §2), (c) `.first-run-marker` integrity binding (§4 rule 10). §2 trust assumptions explicitly concede "compromised in-process Claude session is out of scope"; this gate is a thoughtful raise of the bar, not an absolute boundary.

**stderr-not-stdout** (Layer 3 security-lens P1-S3): the migration notice prints to stderr to avoid capture by `pipe to script` patterns and to reduce visibility in CI logs (where the printed hash would otherwise fingerprint the user's `config.yml`). Hash is non-secret but acts as a fingerprint; stderr-routing is a cheap mitigation.

**`hmac.compare_digest`**: defensive constant-time comparison. Both sides are public-deterministic so timing attacks are not in scope, but the precedent matters and the cost is zero.

**Legacy retention with v2.1.0 removal gate** (Layer 3 data-migration P1-A): the legacy `_legacy_yaml_canonical_hash` function is **kept for one minor cycle** (the v2.0.x line) under a `DeprecationWarning(stacklevel=2)`, and removed in v2.1.0 per BACKLOG entry **BL-210**. CI gate enforces removal: `plugin-v2-handshake-lint.py` includes a check that, when plugin.json `version >= 2.1.0`, asserts `git grep -F '_legacy_yaml_canonical_hash' plugins/launchpad/scripts/` returns empty. The keep-then-remove pattern is load-bearing for the v2.0.0-yanked rollback story (see OPERATIONS §7): a downstream rolling back to v1.1.0 needs its old YAML hash to still validate.

**Audit-trail fallback when `.harness/` is empty/missing** (Layer 5 data-migration P2-DM5-3 hardened). Phase -1 step 4's "validate no downstream `LP_CONFIG_REVIEWED` env-var hash drift in `.harness/` history" assumes `.harness/` carries history. Many downstream `.gitignore` configurations exclude `.harness/` aggressively (see memory `project_harness_gitignore_architecture`). When `.harness/observations/` is empty or missing, the validation is SKIPPED — but the skip is itself a security event: the consumer MUST `os.makedirs(".harness/observations/", exist_ok=True)` and write a single entry to `security-events.jsonl`:

```python
write_security_event({
    "schema_version": "1.0",
    "event": "config_review_skipped_harness_missing",
    "config_hash": new_hash,
})
```

The act of creating the security-events file is itself the durability anchor — a hostile attacker re-deleting `.harness/` between runs creates a visible pattern in the next `lp-memory-report` run. The user remains responsible for re-running config review on first v2.0 invocation.

### Security event log spec (Layer 5 security-lens P1-S1 + security-auditor P2-1 + frontend-races P1-L5-B + adversarial P2-A6)

Layer 4 introduced `.harness/observations/security-events.jsonl` as the audit trail for config-review CI bypasses, but did not specify its integrity contract. Layer 5 closes this gap; the file is now load-bearing for forensic detection of attacker bypass attempts.

**File path**: `.harness/observations/security-events.jsonl`. Auto-created on first event via `os.makedirs(".harness/observations/", exist_ok=True)` if absent.

**Mode**: explicit `os.fchmod(fd, 0o600)` after open — defends against world-readable umask. Mirrors the OPERATIONS §5 hardening for `.telemetry.lock`/`.prune-progress`.

**Lock**: separate sentinel `.harness/observations/.security-events.lock`, opened with `O_CREAT|O_RDWR, mode=0o600`, held under `fcntl.flock(LOCK_EX)` for the entire write cycle. **MUST NOT share the telemetry lock** — coupling a security-event write path to telemetry pruning creates a DoS vector where a long-held prune lock blocks security-event audit writes. The security-events lock is held briefly (single append) and never blocks under load.

**Write protocol** (per entry, atomic append):

1. Compute `prev_entry_sha256` by SHA-256-hashing the canonical-JSON of the prior entry (or `"genesis"` literal string for the first entry — bootstraps the chain).
2. Construct payload:
   ```json
   {
     "schema_version": "1.0",
     "event": "<enum: auto_review_accepted|auto_review_rejected_outside_ci|config_review_skipped_harness_missing|nonlocal_fs_override_used|...>",
     "timestamp": "<ISO 8601 UTC>",
     "pid": <int>,
     "pid_start_time": "<ISO 8601 UTC of process start>",
     "prev_entry_sha256": "<hex-of-prior-entry-canonical-hash | 'genesis'>",
     "<event-specific fields, e.g. config_hash, fs_type>": "..."
   }
   ```
3. `_validate_argv`-style allowlist check on event enum (closed set; unknown event → ValueError).
4. Acquire `LOCK_EX` on `.security-events.lock`.
5. Open file `O_APPEND|O_WRONLY|O_CREAT, 0o600`; `os.fchmod(fd, 0o600)` (defensive even if umask drifts).
6. Single `os.write(fd, (json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=True) + "\n").encode("utf-8"))`. MUST be ≤ 4096 bytes (PIPE_BUF on Linux); event-specific fields are bounded.
7. `os.fsync(fd)` + `os.fsync(dirfd)`; on `sys.platform == 'darwin'`, also `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)`.
8. Release lock.

**Tamper-evidence via `prev_entry_sha256` chain (v2.0; ships at v2.0.0)**: each entry references the canonical-hash of the prior entry. A maintainer running `lp-memory-report --security-events --verify-chain` can detect ANY tampering — truncation breaks the chain at the deletion point; entry mutation breaks the chain at the next entry. v2.0 ships the chain field; v2.1 (BL-220) adds the verify-chain consumer. Note: same-UID attacker who controls the file CAN regenerate the chain consistently by re-hashing forward — chain tampering becomes detectable only by external snapshot comparison, but truncation/silent-deletion attacks (the realistic single-maintainer threat) ARE detectable.

**Always-written semantics**: NOT gated by `telemetry: off`. Security events trump analytics opt-out. The `forensic_writer.py` module owns this path (separate from `telemetry_writer.py` per OPERATIONS §5 — Layer 5 architecture P2-A2 split).

**Retention**: NEVER pruned in v2.0 (security events are forensically valuable; bounded growth in practice). v2.1 BL-220 may add 1MB rollover with 10-bak retention if file growth becomes operationally painful.

**Closed event enum** (v2.0): `{auto_review_accepted, auto_review_rejected_outside_ci, config_review_skipped_harness_missing, nonlocal_fs_override_used, first_run_marker_corrupt, first_run_marker_replayed, first_run_marker_swapped, recall_tag_squat_attempt, restamp_chain_violation, branch_protection_token_unauthorized, tag_protection_token_unauthorized}`. Unknown event values rejected at write-time.

**v2.0.0 release notes documentation.** `docs/releases/v2.0.0.md` MUST include a "Breaking changes" section that documents (a) the hash-scheme change, (b) the copy-paste shell command for re-export, (c) the v2.0.x deprecation window for `_legacy_yaml_canonical_hash`, (d) the `unset LP_CONFIG_REVIEWED && claude /plugin install launchpad@v1.1.0` rollback path, (e) **mid-pipeline upgrade fix (Layer 5 data-migration P1-DM5-2)**: "If you upgraded mid-pipeline (e.g., from v2.0-rc to v2.0.0): delete `.launchpad/scaffold-decision.json` and re-run `/lp-pick-stack`. Your `.launchpad/.scaffold-nonces.log` ledger is preserved (replay protection intact).", (f) `LP_CONFIG_AUTO_REVIEW=1` env-var documentation with explicit positive-filesystem-signal requirements (Layer 5 product-lens P2-PL5-2). The Tier 1 reveal panel (OPERATIONS §5) ALSO mentions `LP_CONFIG_AUTO_REVIEW=1` for CI-using developers in the success-path moment.

### Canonicalization rules

- Input must be a `dict` whose values are JSON-serializable (str, int, bool, None, list, dict). Floats are forbidden (use stringified decimals if needed).
- Lists preserve order (treated as ordered tuples; reordering changes the hash).
- Nested dicts are recursively sorted by key (`sort_keys=True` does this).
- Strings are UTF-8; `ensure_ascii=True` escapes non-ASCII as `\uXXXX` for byte-stability across locales.
- Missing fields are explicitly forbidden in the payload — every field listed in §4 / §5 must be present (use empty string `""`, empty list `[]`, or `null` for absent values).
- A known-answer test vector lives at `plugins/launchpad/scripts/tests/test_decision_integrity.py`: `canonical_hash({"a": 1, "b": [2, "3"], "c": None}) == "<pinned-hex>"`. Test runs on the **Linux + macOS CI matrix** every PR (Layer 2 P2-4: macOS added to GitHub Actions matrix is cheap on free tier for public repos and replaces the prior "manual macOS gate" honor system). Phase -1 acceptance gate requires both matrix legs pass; Phase 7.5 re-confirms before tagging v2.0.0.
- **KAT pair** (Layer 2 P2-11; Layer 3 simplicity P1-A simplified from triplet by dropping tautological "Stability KAT" which only tested `json.dumps` Python-stdlib determinism) for `plugin-config-hash.py` backport in `test_config_hash_backport.py`:
  - **Divergence KAT**: `_legacy_yaml_canonical_hash(fixture_config) != canonical_hash(fixture_config)` — proves the migration actually changed the output (otherwise no migration occurred).
  - **Cross-platform parity**: Linux CI and macOS CI produce identical new hashes for the same fixture.

## 4. `scaffold-decision.json` — schema

`/lp-pick-stack` writes `.launchpad/scaffold-decision.json`. `/lp-scaffold-stack` reads it.

The v1.1 envelope (v2.1+) is additive on top of the v1.0 envelope (v2.0):
new fields (`schema_version`, `plugin_version`, `stacks`, `identity`,
`identity_updated_at`) are added; legacy fields (`version`, `layers`,
`monorepo`, etc.) are preserved verbatim. v2.0 readers ignore the new
fields. v2.1+ readers key off `schema_version` per the §10.v2.1
acceptance ladder. The canonical reader is
`plugin-config-loader.py:read_scaffold_decision()`.

```json
{
  // v1.0 envelope — unchanged from v2.0
  "version": "1.0",
  "layers": [
    {
      "stack": "<id-from-scaffolders.yml>",
      "role": "<frontend|backend|frontend-main|frontend-dashboard|fullstack|mobile|backend-managed|desktop>",
      "path": "<relative POSIX path>",
      "options": {}
    }
  ],
  "monorepo": false,
  "matched_category_id": "<id-from-category-patterns.yml>",
  "rationale_path": ".launchpad/rationale.md",
  "rationale_sha256": "<hex>",
  "rationale_summary": [
    {"section": "project-understanding", "bullets": ["..."]},
    {"section": "matched-category",     "bullets": ["..."]},
    {"section": "stack",                "bullets": ["..."]},
    {"section": "why-this-fits",        "bullets": ["..."]},
    {"section": "alternatives",         "bullets": ["..."]},
    {"section": "notes",                "bullets": ["..."]}
  ],
  "generated_by": "/lp-pick-stack",
  "generated_at": "<ISO 8601 UTC, second precision>",
  "nonce": "<UUID4 hex>",
  // brainstorm_session_id field DEFERRED to v2.2 per BL-235 (Layer 7 strip-back).
  // v2.0 producers OMIT this field entirely; v2.0 consumers do NOT validate it.
  // Rule 12 below is correspondingly deferred. Re-introduced in v2.2 alongside
  // .first-run-marker integrity binding via a coordinated `version` bump.
  "bound_cwd": {
    "realpath": "<absolute realpath of pick-stack invocation cwd>",
    "st_dev":   <integer device id>,
    "st_ino":   <integer inode number>
  },

  // v1.1 envelope additions (v2.1+) — see §10.v2.1 acceptance rules
  "schema_version": "1.1",
  "plugin_version": "2.1.0",
  "stacks": ["<stack-id>", "..."],
  "identity": {
    "pii_opt_in": false,
    "project_name": "<project-name-or-placeholder>",
    "email": "<email-or-placeholder>",
    "copyright_holder": "<copyright-holder-or-placeholder>",
    "repo_url": "<repo-url-or-placeholder>",
    "license": "<MIT|Apache-2.0|GPL-3.0|BSD-3-Clause|ISC|MPL-2.0|Other>",
    "license_other_body": ""  // only populated when license=="Other"
  },
  // identity_updated_at present only after /lp-update-identity has run
  "identity_updated_at": "<ISO 8601 UTC, optional>",
  // kernel_render_state sealed by lp_scaffold_stack engine after a
  // successful KernelRenderer.render_all (Phase 10 DA7-flipped). Updated
  // by /lp-update-identity on each refresh per §3.7.
  "kernel_render_state": [
    {
      "path": "<relpath e.g. LICENSE>",
      "rendered_content_sha256": "<hex sha256 of the file as written>",
      "source_template_sha256": "<hex sha256 of the .j2 template source>",
      "missing_on_disk": false
    }
  ],
  // version_drift_log appended by /lp-update-identity on each successful
  // identity update (DA8). Absent on the original /lp-pick-stack write.
  "version_drift_log": [
    {
      "from_version": "<plugin_version before this update>",
      "to_version":   "<plugin_version after this update>",
      "via":          "/lp-update-identity",
      "fields_changed": ["<identity field name>"],
      "accepted_at":  "<ISO 8601 UTC>"
    }
  ],

  "sha256": "<hex of canonical_hash over all fields above except sha256 itself>"
}
```

**v1.1 envelope field semantics**:

- `schema_version`: indicator field for the §10.v2.1 acceptance ladder.
  Absent or `"1.0"` reads as legacy 1.0 with UNSET identity sentinels;
  `"1.1"` reads in full v2.1 mode.
- `plugin_version`: the running plugin version captured at
  `/lp-pick-stack`. `/lp-scaffold-stack` and `/lp-bootstrap` abort with
  a structured error if the running plugin version differs from this
  recorded value, preventing a `/plugin update` between pipeline steps
  from invalidating the manifest's hash chain (V3 plan §11.1).
- `stacks`: flat dedup'd array derived from `layers[].stack` with
  first-occurrence order preserved. Fast-access summary so consumers do
  not need to walk `layers` to enumerate stacks.
- `identity`: sealed at `/lp-pick-stack` time per §10.v2.1 input
  allowlist regexes; the `pii_opt_in: false` posture writes placeholders
  for `email`, `copyright_holder`, and `repo_url` (always-placeholder
  for `repo_url` until the user fills it in via `/lp-update-identity`).
  License `"Other"` carries a free-form `license_other_body` constrained
  by §10.v2.1 sanitization rules (max 10KB, printable ASCII, no Jinja
  delimiters, no HTML tags). The canonical reader
  (`plugin-config-loader.read_scaffold_decision()`) validates the
  identity block on read against the §10.v2.1 allowlist regexes
  (Phase 1+2 retroactive amendment A5), so a hand-edited or tampered
  envelope is rejected before downstream renderers run.
- `identity_updated_at`: ISO 8601 UTC timestamp written by
  `/lp-update-identity` (Phase 10+) on each successful identity update.
  Absent on the original `/lp-pick-stack` write.
- `kernel_render_state`: per-file sha256 record of the last successful
  kernel render. Sealed by `lp_scaffold_stack` engine (greenfield) and
  re-sealed by `lp_update_identity` engine (refresh) so the renderer's
  per-file sha is the single source of truth at refresh time
  (architecture-strategist P2-A; eliminates asymmetric coupling).
  `KernelRenderer.refresh()` reads this list from the caller, computes
  on-disk sha for each kernel file, and refuses individual files whose
  sha drifted from the recorded value (`USER_EDIT_BLOCKS_REFRESH` per
  §3.7). `missing_on_disk` (boolean, default `false`) is set to `true`
  when `KernelRenderer.refresh()` finds the file absent from disk;
  controls the re-render branch in `compute_current_on_disk_state()`.
  Phase 1+2 retroactive amendment A7 made the seal a caller-side
  responsibility to remove the renderer's prior dependency on
  `lp_pick_stack.decision_writer`.
- `version_drift_log`: append-only audit trail of plugin-version
  transitions captured by `/lp-update-identity`. Each entry records the
  `from_version`/`to_version` `plugin_version`, the calling command
  (`via`), the list of identity field NAMES that changed (NOT the
  values, per Phase 10 DA8 PII rule), and the `accepted_at` UTC
  timestamp. Empty/absent on the original `/lp-pick-stack` write;
  `/lp-update-identity` appends one entry per successful update (no-op
  fast-path skips the append per adversarial P3).

### Validation rules (orchestration MUST enforce all of them before any subprocess executes)

1. **`version`** ∈ `{"0.x-test"}` during pre-ship. At v2.0.0 ship time, bumped in a coordinated commit to `{"1.0"}`. Unknown versions → hard reject with `reason: "version_unsupported"`, `seen_version: "<actual>"`, AND user-facing hint **"decision file generated by older or newer plugin version; delete `.launchpad/scaffold-decision.json` and re-run /lp-pick-stack to regenerate."** (Layer 5 data-migration P1-DM5-2 — closes mid-pipeline upgrade dead-end where a user with a v2.0-rc-stamped decision file from before they upgraded to stable v2.0.0 cannot proceed within the 4h replay window.)
2. **`layers`** non-empty array. Each layer:
   - `stack` ∈ keys of `scaffolders.yml` (plugin-shipped catalog).
   - `role` ∈ enumerated set above.
   - `path` passes the §6 path validator. Two layers cannot share a `path`.
   - `options` keys allowlisted per the scaffolder's `options_schema` field in `scaffolders.yml`.
3. **`monorepo`** boolean. If `true`, `layers.length >= 2`. If `false`, `layers.length == 1` OR all layers share `path == "."`.
4. **`matched_category_id`** ∈ keys of `category-patterns.yml`, OR equal to `"manual-override"` if the user picked stacks via `[m]anual override`.
5. **`rationale_path`** equals `.launchpad/rationale.md` exactly.
6. **`rationale_sha256`** equals SHA-256 of the file at `rationale_path`. Re-computed at read; mismatch → hard reject.
7. **`rationale_summary`** present; AT LEAST ONE section MUST contain ≥1 non-empty bullet. Empty-but-structurally-valid summary → hard reject. `/lp-define` consumes only this array; raw `rationale.md` is never read by downstream commands. Each bullet ≤ 240 chars; passes the §9 sanitization filter. **Ambiguous-category enforcement**: when `matched_category_id` belongs to a known-ambiguity cluster (Hugo/Astro/Eleventy share Q1+Q2+Q3+Q4; Phoenix/Convex differ only on Q4; Expo/Flutter differ only on Q4), `rationale_summary[alternatives].bullets.length >= 1` AND each bullet > 30 chars. Documented ambiguity clusters live in `category-patterns.yml`'s top-level `ambiguity_clusters:` field.
8. **`generated_by`** equals `"/lp-pick-stack"` exactly.
9. **`generated_at`** ISO 8601 UTC with `Z` suffix. Rejected if more than **4 hours** old. (Tightened from 7 days; covers a realistic interactive session including a lunch-break gap, while bounding replay risk to a single working session.)
10. **`nonce`** UUIDv4 format. Refuses to consume the same nonce twice. Concrete protocol (Layer 2 P1-3 + Layer 3 frontend-races P1-A/B/C/D + adversarial P1-RT-4 + pattern-finder P1-C hardening):
    - **Ledger format**: `.launchpad/.scaffold-nonces.log`, append-only, line-delimited fixed 33-byte records `<UUIDv4-hex-32-chars>\n`. CI lint enforces 33-byte record length at runtime; longer payloads hard-rejected. The 33-byte cap keeps writes well under PIPE_BUF (4096 on Linux), preserving `O_APPEND` byte-atomicity. Comment lines `# ...\n` (sentinels) are skipped during read; never mixed with data lines for length validation.
    - **Format header** (Layer 3 data-migration P2-F + Layer 5 data-migration P1-DM5-1 v0 migration bridge): first line of every fresh ledger MUST be `# nonce-ledger-format: v1\n` (a comment, treated as skip-line by v1 readers). v2.1+ readers check the header and hard-reject on mismatch with `reason: "nonce_ledger_format_unsupported"`. **Header-absent v0 migration**: a ledger whose first line is a valid 32-char UUID-hex (not a comment) is treated as a v0 ledger written by an unreleased pre-v1.0 implementation (e.g., a v2.0-rc that a user installed and is now upgrading from). v2.0 readers MUST migrate it under the lock by: (1) acquire `LOCK_EX` on `.scaffold-nonces.lock`, (2) read all entries into memory, (3) `os.open(".scaffold-nonces.log.tmp.<pid>", O_WRONLY|O_CREAT|O_EXCL, 0o600)` and write `# nonce-ledger-format: v1\n` header line + prior entries verbatim, (4) `os.fsync(tmpfd)` + F_FULLFSYNC on darwin, (5) `os.rename(tmp, log)` (atomic-on-POSIX), (6) `os.fsync(dirfd)`, (7) release lock. Migrated ledgers retain all prior nonces (replay protection preserved). One-shot migration; idempotent on second run (idempotent because the file already has the header). **Mid-write crash orphan cleanup (Layer 7 — closes L6-κ #3; Layer 8 scope-pinned per security-lens P2)**: at migration entry, BEFORE any tmp create AND BEFORE the FIRST `os.open` of this acquisition's tmp file, `os.unlink` any pre-existing `.scaffold-nonces.log.migration-tmp.*` (glob restricted to **migration-specific naming** — the migration tmp pattern is `.scaffold-nonces.log.migration-tmp.<pid>` to keep it disjoint from rollover tmps). The 1MB rollover protocol uses a DISTINCT tmp pattern `.scaffold-nonces.log.rollover-tmp.<pid>` (Layer 8 pin) so the migration cleanup glob has provably-disjoint scope from rollover state. Both patterns are owned by code paths inside `.scaffold-nonces.lock` flock, so cleanup-of-orphans-from-prior-crashed-acquisitions cannot race against an in-flight writer. One-line cleanup; bounds disk growth on repeatedly-crashing systems. Phase 7 sub-test: pre-write a header-less ledger with 3 valid UUID lines, run `/lp-scaffold-stack`, assert ledger now has header line as first record AND all 3 prior nonces preserved.
    - **Lock sentinel — separate file, NEVER renamed** (Layer 3 frontend-races P1-A FIX — closes inode-swap race during atomic-rename pruning): the `fcntl.flock(LOCK_EX)` lock is held on `.launchpad/.scaffold-nonces.lock`, opened with `O_CREAT|O_RDWR`, mode `0o600`. The lock file is opened via `os.open` BEFORE the data file on every operation. The lock file is **never renamed, never unlinked, never rotated** — only the `.scaffold-nonces.log` data file is rotated. This makes the lock object stable across data-file inode changes from atomic-rename pruning. Without this separation, a writer arriving between the pruner's `os.rename` and `os.fsync(dirfd)` would `O_CREAT` a fresh inode at the data path and acquire flock on a different inode than the pruner held — torn writes possible.
    - **Open mode** (closes Layer 2 P1-3 case 1 — append atomicity): `os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)`. Single `os.write(fd, (uuid + "\n").encode("ascii"))` call — no `print`/`io.write` buffering. POSIX guarantees `O_APPEND` writes seek to EOF atomically per `write(2)` for writes ≤ PIPE_BUF on local filesystems.
    - **Filesystem detection at ledger-init — WHITELIST** (Layer 3 frontend-races P1-C + adversarial P1-RT-4 + Layer 4 feasibility P2-3 + adversarial P2-RT4-E + Layer 5 product-lens P1-PL5-1 + adversarial P2-A10): on first ledger access in a process, probe `os.statvfs(.launchpad)` (Linux: parse `/proc/self/mountinfo`; macOS: `df -T`). **Whitelist of accepted filesystem types**: `apfs`, `hfs`, `hfs+`, `ext2`, `ext3`, `ext4`, `xfs`, `btrfs`, `zfs`. Anything not on the whitelist hard-rejects with `reason: "platform_unsupported_filesystem"`, with hint **"remediation: move `.launchpad/` to a local POSIX filesystem (apfs/ext4/xfs/btrfs/zfs). Non-local filesystem support (WSL2 `9p`, `tmpfs`, `overlayfs`, FUSE) is deferred to v2.1 (BL-218)."** No `LP_ALLOW_NONLOCAL_FS=1` override at v2.0 — Layer 5 product-lens flagged the prior phantom hint as half-implementation. The whitelist is fail-closed; a real CI-runner overlayfs need is addressed by **Phase -1 acceptance gate** (test plan): empirically verify on GHA Ubuntu runner what `/proc/self/mountinfo` reports; if `overlayfs` is the runner default, add it to the whitelist with documented justification (Layer 5 adversarial P2-A10). Whitelist-by-default is safer than the prior blacklist for unknown-FS scenarios (closes WSL2 `9p` gap, `tmpfs`/`ramfs` volatile-FS replay, `fuseblk` over-broad rejection). The detection result is cached **per-process** (not per-session), and re-checked on each ledger operation in long-running processes via cheap `os.statvfs` (microseconds; no parsing). Detection failure (e.g., `/proc/self/mountinfo` unreadable in a hardened sandbox) hard-rejects with `reason: "filesystem_detection_failed"` — fail-closed.
    - **Durability** (Layer 3 pattern-finder P1-C — F_FULLFSYNC on macOS): after append, `os.fsync(fd)` then `os.fsync(dirfd)` where `dirfd = os.open(parent_dir, os.O_RDONLY | os.O_DIRECTORY)`. **On `sys.platform == 'darwin'`, additionally call `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)` before close** — macOS `fsync(2)` does NOT flush to platter (only to disk write cache), so the F_FULLFSYNC variant is required for true power-loss durability within the 4h replay window.
    - **EIO handling** (closes Layer 2 P1-3 case 2 + Layer 3 frontend-races P2-C): on `OSError` from `os.write` or `os.fsync`, detect potential partial line via `os.fstat(fd).st_size` delta vs. pre-write size. If partial-line suspected, write a sentinel comment line `# corrupt:<iso-timestamp>\n` under the same lock, then hard-reject with `reason: "nonce_ledger_corrupt"`. If the sentinel write itself fails with EIO (genuinely failing disk), hard-reject with `reason: "nonce_ledger_io_unrecoverable"` AND chmod the lock file 000 to prevent further attempts until human intervention.
    - **Append failure → hard reject** with `reason: "nonce_ledger_append_failed"`. EROFS distinguished separately as `reason: "filesystem_readonly"` with hint "mount .launchpad/ writable" (Layer 3 security-lens P3-S6).
    - **Pruning RESOLVED — by 1MB rollover only, not by `generated_at`** (Layer 3 frontend-races P1-D FIX + Layer 4 spec-flow P1-2 + frontend-races P1-C tightened + Layer 5 frontend-races P2-L5-A8 backward-NTP handling): the ledger has NO per-entry timestamp. Pruning happens ONLY at the 1MB size-cap rollover (below). The 4-hour replay-window check is enforced by `generated_at` in `scaffold-decision.json` itself, not by ledger filtering. **The validator's "is this nonce already seen?" check consults BOTH the live ledger AND ALL `.scaffold-nonces.log.bak.<ts>` files where `max(filename_ts, file_ctime)` is within 4h of `now`** (filename source-of-truth for the upper bound; ctime as defensive lower bound to handle backward NTP corrections — backward clock jumps could otherwise produce filename `<ts>` values numerically smaller than the real rotation time, silently shrinking the replay-rejection window. Using `max()` is conservative — slightly EXPANDS the window across clock skew without forensic cost, since `ctime` cannot be set backward by user-level processes on the platforms in OPERATIONS §1 whitelist). Filename source-of-truth, not mtime — mtime is forgeable by user-level processes via `cp -p` etc.; filename was set at rotation time under the lock. The validator's `.bak` listing happens UNDER THE SAME `LOCK_EX` as the prune/rotation operation, so listing/reading cannot race against retention deletion. Rejection on first hit across the union (live ∪ all-in-window-bak). This closes the rollover-orphan window where in-flight nonces in a recently-rotated `.bak` would otherwise be replayable.
    - **Size cap + rollover retention bound** (Layer 2 P3-4 + Layer 3 security-lens P2-S4): if ledger `st_size > 1 MiB`, atomic-rename to `.scaffold-nonces.log.bak.<iso-timestamp>` under the lock, then create a fresh ledger with the format header. **Retention**: keep at most 5 most-recent `.bak` files; older `.bak` files are deleted to bound disk growth and limit forensic-data retention drift on multi-tenant environments. Rotation atomic-rename protocol: open tmp via `O_CREAT|O_EXCL` with header line, fsync(tmp), rename, fsync(dirfd) — same protocol as the prior pruning subsection but applied to rollover.
    - **First-run via positive marker file** — **[v2.0 STRIP-BACK per BL-235: the integrity-bound JSON envelope + dedicated lock + FD-based read + pre-rename re-stat + microsecond+pid timestamp + 10-step consumption protocol below are ALL DEFERRED to v2.2. At v2.0, `/lp-brainstorm` writes `.launchpad/.first-run-marker` as a simple positive-presence empty file via `os.open(... O_WRONLY|O_CREAT|O_EXCL, 0o600)` (the `O_EXCL` race-detects concurrent `/lp-brainstorm` invocations); `/lp-scaffold-stack` consumes by `os.rename(.first-run-marker, .first-run-marker.consumed.<iso-sec-ts>)` under no lock (single-writer assumption at single-maintainer scale; cross-process collision is "user error" scope at v2.0). Marker semantic value at v2.0: its presence signals `/lp-brainstorm` has run in this cwd, authorizing the empty-nonce-ledger first-run fast path in `/lp-scaffold-stack`. Standalone `/lp-pick-stack` invocations (no prior brainstorm) have no marker; `/lp-scaffold-stack` then takes the slow path (full nonce-ledger check). Layer 5 wording below preserved as audit trail; v2.0 implementers SKIP it.]** (Layer 3 spec-flow P1-5 + frontend-races P1-B + Layer 4 adversarial P1-RT4-A + security-lens P2-S1 + frontend-races P1-A/B + spec-flow P1-1 + schema-drift P1-1 hardened): `/lp-brainstorm` writes `.launchpad/.first-run-marker` at session start with this INTEGRITY-BOUND payload (canonical_hash-enveloped + bound_cwd-bound):

      ```json
      {
        "schema_version": "1.0",
        "generated_at": "<ISO 8601 UTC>",
        "brainstorm_session_id": "<secrets.token_hex(16) — 32 hex chars / 128 bits>",
        "generated_by": "/lp-brainstorm",
        "bound_cwd": {"realpath": "...", "st_dev": <int>, "st_ino": <int>},
        "sha256": "<canonical_hash of payload above with sha256 omitted>"
      }
      ```

      **Write protocol** (atomic-rename via flock-on-DEDICATED `.first-run-marker.lock` — Layer 5 security-auditor P1-1 + frontend-races P1-L5-A: split from `.scaffold-nonces.lock` to avoid lock-coupling DoS where a slow `/lp-brainstorm` would block every concurrent nonce-append; lifecycle of `.first-run-marker.lock` mirrors `.scaffold-nonces.lock` — opened with `O_CREAT|O_RDWR, 0o600`, never renamed, never unlinked):
      1. Acquire `LOCK_EX` on `.launchpad/.first-run-marker.lock` (NEW dedicated lock; created if absent).
      2. Refuse if `.first-run-marker` already exists (`O_CREAT|O_EXCL`) — surfaces concurrent `/lp-brainstorm` race rather than silently overwriting. **Greenfield-only**: per §7 brainstorm output contract, the marker write is ONLY performed when `cwd_state(cwd) == "empty"` AND output `greenfield: true`. Brownfield/ambiguous cwds skip the marker write entirely (Layer 5 spec-flow P3-LF7 + scope P1-NEW).
      3. Write payload JSON to `.first-run-marker.tmp.<pid>` via `os.open(... O_WRONLY|O_CREAT|O_EXCL, 0o600)`.
      4. `os.fsync(tmpfd)` + `F_FULLFSYNC` on darwin.
      5. `os.rename(tmp, marker)` (atomic-on-POSIX).
      6. `os.fsync(dirfd)`.
      7. Release lock. **Lock-acquisition timeout**: use `fcntl.flock(LOCK_EX | LOCK_NB)` retry loop with 10s ceiling; on timeout hard-reject with `reason: "lock_acquisition_timeout"` and emit `write_security_event({"event": "first_run_marker_lock_timeout", ...})`. Maximum hold time per spec: ≤500ms (no I/O beyond small JSON write + 2× fsync).

      **Consumption protocol** (`/lp-scaffold-stack` first-run fast path — Layer 5 frontend-races P1-L5-A FD-based TOCTOU close):
      1. Acquire `LOCK_EX` on `.launchpad/.first-run-marker.lock` (10s LOCK_NB retry timeout).
      2. **Open marker by FD with `O_RDONLY|O_NOFOLLOW`** and record `(st_dev, st_ino)` via `os.fstat(markerfd)`. All subsequent reads use the FD, not the path — closes the path-vs-inode TOCTOU where an attacker (without the lock) could `rename(marker, …)` between open and use because the lock is on a different inode.
      3. Read `scaffold-decision.json.brainstorm_session_id`; if non-null AND any existing `.first-run-marker.consumed.<ts>` file's payload (parse JSON via separate FD-open) carries the same `brainstorm_session_id`, refuse with `reason: "first_run_marker_replayed"` (replay-via-already-consumed-marker; payload check, not filename — `.consumed.<ts>` filenames don't carry session_id).
      4. Parse marker bytes from FD into JSON. Reject on parse-error or schema-version mismatch with `reason: "first_run_marker_invalid"`.
      5. Recompute SHA-256 over payload (sha256 field omitted) using the FD-buffered bytes; compare. Mismatch → reject `reason: "first_run_marker_corrupt"`.
      6. Recompute `bound_cwd` triple from current cwd; assert match against marker's bound_cwd. Mismatch → reject `reason: "first_run_marker_cwd_mismatch"` (closes cross-project marker-copy attack).
      7. Assert marker `generated_at` ≤ 4h old. Older → reject `reason: "first_run_marker_expired"`.
      8. Assert marker's `brainstorm_session_id` matches `scaffold-decision.json.brainstorm_session_id` (decision file's session_id is the authoritative reference per §4 rule 12 — closes confused-deputy via stale marker).
      9. **Pre-rename re-stat under lock**: `os.stat(marker_path)` and assert `(st_dev, st_ino)` match the values recorded in step 2. Mismatch → reject with `reason: "first_run_marker_swapped"` and emit `write_security_event({"event": "first_run_marker_swapped", ...})` — closes rename-into-place attack window.
      10. On all assertions PASS: `os.rename(.first-run-marker, .first-run-marker.consumed.<iso-microsec-ts>.<pid>)` under same lock; release lock; proceed.

      **Consumed-marker timestamp precision** (Layer 5 adversarial P2-A7 — collision avoidance): the rename target uses ISO 8601 with **microsecond precision PLUS `.<pid>` suffix** (e.g., `.first-run-marker.consumed.2026-04-30T19:42:11.583291Z.12345`). Two consumption attempts within the same microsecond on the same project are vanishingly rare; the `.pid` suffix closes the residual collision. Use `os.link()` + `os.unlink()` (link refuses on existing target on POSIX) instead of `os.rename()` — defends against silent overwrite of prior audit records. On `FileExistsError`, retry with incremented suffix `.<pid>.r2`, etc.

      **Lifecycle**: re-running `/lp-brainstorm` on a project with an existing unconsumed `.first-run-marker` raises an error ("session in progress; remove `.launchpad/.first-run-marker` if stale OR run `/lp-scaffold-stack` to consume it first"). Re-running `/lp-brainstorm` after marker has been `.consumed.<ts>` succeeds: a fresh marker with new `session_id` overwrites prior — the prior `.consumed.<ts>` is preserved as audit trail. **Retention**: keep at most 5 most-recent `.first-run-marker.consumed.<ts>` files; older deleted under same lock as the new consumption. Empty (`st_size == 0`) ledger combined with marker absence → hard-reject with `reason: "nonce_ledger_empty_unexpected"`. The canonical "first run" is "ledger absent OR ledger empty AND valid first-run-marker present + unconsumed + session_id matches decision file." **Brownfield re-run handling** (Layer 5 spec-flow P2-LF4): after a successful `/lp-scaffold-stack`, the cwd transitions from "empty" to "brownfield." Subsequent `/lp-brainstorm` re-runs in the same cwd will detect brownfield and route to `/lp-define` (the brownfield happy path), NOT to `/lp-pick-stack`. The "redo scaffold" workflow is not supported in v2.0; the user must `cd` to a fresh directory to re-invoke the greenfield pipeline.

      **scaffold-decision.json field addition**: §4 schema gets a new `brainstorm_session_id` field (32-hex-char OR null). pick-stack reads the marker's session_id at decision-file generation time and embeds it (or null if no marker). CI lint asserts presence + format. Closes the cross-pipeline replay vector where a stale marker could authorize a different brainstorm's decision file. See §4 rule 12 for the standalone-`/lp-pick-stack` (null) branch.

    - **Crash-recovery test** (Layer 2 P1-3 fix item f): a Phase 7 sub-test SIGKILLs `/lp-scaffold-stack` mid-prune and asserts the ledger is either pre-prune state OR post-prune state, never empty/corrupt.
    - **Platform**: POSIX-only. On `sys.platform == 'win32'`, `/lp-scaffold-stack` hard-rejects with `reason: "platform_unsupported_v2_0"`. Windows support deferred to v2.1.

11. **`bound_cwd`** is a triple `(realpath, st_dev, st_ino)`. Orchestration recomputes `os.path.realpath(os.getcwd())` AND `os.stat(cwd_real)` for st_dev/st_ino. ALL THREE must match. Defeats both volume-rename and symlink-swap-after-pick-stack. **Known false positives**: APFS/btrfs CoW snapshots and Docker bind-mounts can change `st_ino` or `st_dev` legitimately; users hitting these cases re-run `/lp-pick-stack` (cheap; preferred over a `--reissue-cwd-binding` flag in v2.0). v2.1 may revisit if telemetry shows frequent pain. **Layer 5 adversarial P1-A5 — UX-vs-attack distinction**: when `realpath` differs but `(st_dev, st_ino)` matches, the rejection emits `reason: "bound_cwd_realpath_changed_inode_match"` with hint "directory was renamed or moved; re-run /lp-pick-stack to re-bind." When `realpath` matches but `(st_dev, st_ino)` differs, the rejection emits `reason: "bound_cwd_inode_mismatch"` (the symlink-swap or volume-remount attack signal). Distinguishing the two is operationally important: rename = benign user action; inode-mismatch under same realpath = real attack signal. Both branches still hard-reject; the distinction is in the user-facing message + audit log entry.
12. **`brainstorm_session_id`** — **[v2.0 STRIP-BACK: ENTIRE RULE DEFERRED to v2.2 per BL-235. v2.0 producers do NOT emit the field; v2.0 consumers do NOT validate it. Skip this rule at v2.0 implementation time.]** ∈ `{32-hex-char string matching ^[0-9a-f]{32}$, null}` (Layer 5 spec-flow P1-LF3 + schema-drift P1-SD5-1).
    - If non-null AND `.first-run-marker` exists: marker's `brainstorm_session_id` MUST match (consumption protocol step 7).
    - If non-null AND `.first-run-marker` does NOT exist: hard-reject with `reason: "first_run_marker_missing_session_bound"` — the decision file claims a brainstorm session that left no marker; suspicious.
    - **If null**: standalone `/lp-pick-stack` invocation (no prior `/lp-brainstorm`). Orchestration takes the slow path (full nonce-ledger check, no first-run fast path). NOT an error.
    - Hard-reject when non-null format is malformed (not 32 hex chars) with `reason: "brainstorm_session_id_malformed"`.
    - **Pick-stack writer behavior**: at decision-file generation, pick-stack reads `.launchpad/.first-run-marker` if present, parses the JSON, and embeds `brainstorm_session_id` from the marker payload. If marker is absent, embeds `null`. CI lint asserts the field is present (either string or null) on every test fixture.
13. **`sha256`** equals `canonical_hash` of the payload with `sha256` field removed. Mismatch → hard reject.

If any validation fails, `/lp-scaffold-stack` exits non-zero with a structured error and writes `.harness/observations/scaffold-rejection-<timestamp>.jsonl` with a `reason` field naming the specific check that failed (e.g., `reason: "sha256_mismatch"`, `reason: "nonce_seen"`, `reason: "bound_cwd_realpath_mismatch"`, `reason: "bound_cwd_inode_mismatch"`, `reason: "generated_at_expired"`, `reason: "path_traversal"`, `reason: "unknown_stack_id"`, `reason: "rationale_summary_empty"`, `reason: "forbidden_bullet_token"`, `reason: "forbidden_bullet_unicode"`, `reason: "platform_unsupported_v2_0"`, `reason: "platform_unsupported_network_filesystem"`, `reason: "filesystem_readonly"`, `reason: "nonce_ledger_format_unsupported"`, `reason: "nonce_ledger_io_unrecoverable"`, `reason: "version_unsupported"`, `reason: "scaffold_rejection_schema_version_invalid"`, `reason: "restamp_audit_schema_version_invalid"`, `reason: "manifest_schema_version_invalid"`). The `version_unsupported` reason fires when `version` is in a recognizably-newer-but-unknown form (e.g., consumer at v2.0 sees a `version: "1.1"` decision file written by a v2.1 producer); rejection includes a `seen_version` field and a "upgrade plugin to v2.1+" hint. No subprocess executes.

**`scaffold-rejection-<ts>.jsonl` write protocol (Layer 7 v2.0 inline; Layer 8 hardened)** — closes Layer 6 L6-ε #2 schema gap + post-strip-back review L6-ε hardening. Forensic_writer is deferred per BL-223; this file is written INLINE by `/lp-scaffold-stack`:

- **User-visible surfacing (Layer 9 — closes security-lens P3-1 path-mismatch)**: emit a TWO-PART user-facing message to stderr:
  - **Part 1 (FIRST, BEFORE forensic-log write attempt)**: one-line containing the `reason:` enum value + the §4-rule-specific hint (e.g., "decision file generated by older or newer plugin version; delete `.launchpad/scaffold-decision.json` and re-run `/lp-pick-stack`"). Independent of forensic-log success — a user hitting a validation error MUST see the reason without grepping `.harness/observations/`.
  - **Part 2 (AFTER `O_CREAT|O_EXCL` retry resolves)**: one-line containing either "log written to: `<actual_path>`" (where `<actual_path>` is the FINAL path written, including any `.r2`/`.r3` suffix) on success, OR "forensic log unavailable; reason captured above" on retry exhaustion or filesystem fallback. This ordering closes the L9 path-announcement-before-retry race where the announced path could differ from the final `.r2`/`.r3` path actually written.
- **Path**: `.harness/observations/scaffold-rejection-<ISO 8601 UTC microsecond-precision>.<pid>.jsonl` (microsecond + pid suffix closes same-second collision class — mirrors the `.first-run-marker.consumed` pattern at v2.2 per BL-235).
- **No lock** (Layer 8 simplification — closes Layer 7 review's "single-entry-per-file means lock protects nothing" finding): the timestamp+pid filename is collision-free under the v2.0 single-process invocation model; `O_CREAT|O_EXCL|O_WRONLY` on the path is the atomicity guarantee. On `FileExistsError`, retry with `.r2`/`.r3` suffix (max 5 retries; otherwise emit to stderr and continue without forensic log).
- **File mode**: `os.fchmod(fd, 0o600)` after open. Defends against world-readable umask.
- **Best-effort write with ENOENT/EROFS/EACCES/ENOSPC fallback** (Layer 8 closes adversarial P1 ENOENT crash): the entire forensic-log write is wrapped in `try/except (OSError,)` with a stderr-only fallback emitting `JSONL-fallback: <payload>` so the rejection signal survives even on read-only or full filesystems. Validation-rejection MUST surface to the user even when forensic logging is broken. `os.makedirs(".harness/observations/", exist_ok=True)` is itself wrapped in the try/except; if it fails, skip forensic write.
- **Single-entry-per-file** (timestamp+pid filename guarantees uniqueness across the v2.0 single-process invocation model).
- **Schema** (closed):
  ```json
  {
    "schema_version": "1.0",
    "reason": "<from §4 enum>",
    "seen_version": "<optional, only on version_unsupported>",
    "field_name": "<optional, only on path_traversal/forbidden_bullet_*>",
    "timestamp": "<ISO 8601 UTC sec-precision>",
    "pid": <int>,
    "pid_start_time": "<ISO 8601 UTC sec-precision via psutil.Process().create_time() — own-pid only at v2.0; arbitrary-pid forensic identity deferred to v2.2 alongside forensic_writer.py per BL-223>"
  }
  ```
- **Write**: `os.write(fd, (json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=True) + "\n").encode("utf-8"))` — single `os.write` call, ≤ 4096 bytes (PIPE_BUF). Subsequent `os.fsync(fd)` + `os.fsync(dirfd)`; on `sys.platform == 'darwin'`, also `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)`.
- **Always-written (when filesystem permits)**: NOT gated by `telemetry: off`. Rejection logs are forensically valuable; opt-out is for analytics, not for rejection records.
- **Retention**: NEVER pruned at v2.0 (rejection events bounded in practice; user-driven cleanup if desired). v2.2 BL-220-equivalent rotation policy if file growth becomes operationally painful.
- **schema_version registered in §10 lifecycle bump list** alongside `restamp-history.jsonl`. v2.0 readers reject entries with absent `schema_version` field as `reason: "scaffold_rejection_schema_version_invalid"` (Layer 8 simplification per code-simplicity P3 — collapses `*_missing` and `*_unsupported` to a single reason; distinction reclaimable at v2.2 if telemetry shows confusion).

### 4.1 `scaffold-failed-<ts>.json` schema location (Layer 7 — closes L6-δ #1)

The full schema for `.launchpad/scaffold-failed-<ts>.json` (the partial-scaffold cleanup record emitted on `/lp-scaffold-stack` layer-materialization failure) lives in **`SCAFFOLD_OPERATIONS.md` §6 gate #11** (the partial-scaffold cleanup gate). The schema is operational/runtime in nature (recovery commands + recommended action prose + see_recovery_doc URL) rather than contract-layer (no SHA-256 envelope, no nonce, no bound_cwd binding); it earns its place in OPERATIONS rather than HANDSHAKE.

**v2.0 readers** (humans + future BL-231 automated recovery tooling): consume the structured `recovery_commands` array as a forward-compat hint; `recommended_recovery_action` prose is the load-bearing field at v2.0 (per §1.5 strip-back). v2.0 writers (`/lp-scaffold-stack`) MUST emit the structured array even though no v2.0 consumer enforces it, to preserve forward-compat with v2.2 BL-231.

## 5. `scaffold-receipt.json` — schema

After `/lp-scaffold-stack` materializes a stack, it writes `.launchpad/scaffold-receipt.json` for `/lp-define` to consume:

```json
{
  "version": "0.x-test",
  "scaffolded_at": "<ISO 8601 UTC>",
  "decision_sha256": "<hex of input scaffold-decision.json>",
  "decision_nonce": "<UUID4 from input>",
  "layers_materialized": [
    {
      "stack": "<id>",
      "path": "<path>",
      "scaffolder_used": "<orchestrate|curate>",
      "files_created": ["<relative path>", "..."]
    }
  ],
  "cross_cutting_files": ["pnpm-workspace.yaml", "turbo.json", "lefthook.yml", "..."],
  "toolchains_detected": ["node", "python", "ruby", "elixir", "go", "dart"],
  "secret_scan_passed": true,
  "tier1_governance_summary": {
    "whitelisted_paths": <int>,
    "lefthook_hooks": ["secret-scan", "structure-drift", "typecheck", "lint"],
    "slash_commands_wired": <int>,
    "architecture_docs_rendered": 8
  },
  "sha256": "<hex of canonical_hash over all fields above except sha256>"
}
```

`/lp-define` reads the receipt to decide which adapter modules to dispatch (one adapter per layer), and to render the **Tier 1 governance reveal panel** (OPERATIONS §5). The receipt's `decision_sha256` lets `/lp-define` cross-check the chain-of-custody back to pick-stack.

## 6. Path validator

Single source of truth. Implementation lives at `plugins/launchpad/scripts/path_validator.py`. Imports: `/lp-pick-stack` (manual-override path validation, write-side), `/lp-scaffold-stack` (decision-input layer paths, read-side), `/lp-define` (output adapter paths).

Internally split into a string-shape check (`_validate_path_shape`) and a filesystem-realpath check (`_validate_filesystem_safety`); the public `validate_relative_path()` orchestrates both. The split lets unit tests cover string-shape rules without touching the filesystem.

```python
from __future__ import annotations

import re
from pathlib import Path

ALLOWLIST_RE = re.compile(r"^[A-Za-z0-9_./\-]+$")
FORBIDDEN_PREFIXES = (".git/", ".launchpad/.", "node_modules/", ".env")


class PathValidationError(ValueError):
    """Raised when a path crossing a trust boundary fails validation.

    Mirrors the ConfigError pattern in plugin-config-loader.py: domain-specific
    exception subclass + field_name attribute for telemetry.
    """
    def __init__(self, message: str, field_name: str = "path"):
        super().__init__(f"{field_name}: {message}")
        self.field_name = field_name


def _validate_path_shape(raw: str, field_name: str) -> None:
    """String-only validation: type, emptiness, allowlist, traversal, reserved prefixes.

    No filesystem access. Pure-CPU; cheap to fuzz.
    """
    if not isinstance(raw, str):
        raise PathValidationError(f"expected str, got {type(raw).__name__}", field_name)
    if not raw:
        raise PathValidationError("empty path", field_name)
    if "\x00" in raw:
        raise PathValidationError("null byte in path", field_name)
    if not ALLOWLIST_RE.fullmatch(raw):
        raise PathValidationError(f"disallowed characters: {raw!r}", field_name)
    if raw.startswith("/"):
        raise PathValidationError("absolute path forbidden", field_name)
    if any(p == ".." for p in raw.split("/")):
        raise PathValidationError("parent traversal forbidden", field_name)
    for prefix in FORBIDDEN_PREFIXES:
        if raw == prefix.rstrip("/") or raw.startswith(prefix):
            raise PathValidationError(f"reserved area: {prefix}", field_name)


def _validate_filesystem_safety(raw: str, cwd: Path, field_name: str) -> Path:
    """Filesystem-bound validation: realpath cwd-containment + ancestor symlink check.

    Caller must have already passed _validate_path_shape on raw.
    """
    cwd_real = cwd.resolve(strict=True)
    candidate = (cwd_real / raw).resolve(strict=False)
    if not candidate.is_relative_to(cwd_real):
        raise PathValidationError("resolved path escapes cwd", field_name)
    cur = candidate
    while cur != cwd_real:
        if cur.is_symlink():
            raise PathValidationError(f"ancestor is symlink: {cur}", field_name)
        if cur.parent == cur:
            break
        cur = cur.parent
    return candidate


def validate_relative_path(
    raw: str,
    cwd: Path,
    field_name: str = "path",
) -> Path:
    """Validate a relative POSIX path supplied across a trust boundary.

    Orchestrates shape + filesystem checks. Raises PathValidationError on any
    rule violation; returns the resolved absolute Path on success.
    """
    _validate_path_shape(raw, field_name)
    return _validate_filesystem_safety(raw, cwd, field_name)
```

The `field_name` parameter lets callers emit precise rejection logs (e.g., `field_name="layers[0].path"` vs `field_name="manual_override.layer.path"`), matching the `plugin-config-loader.py` pattern. Caller contract: `cwd` must pre-exist; `.launchpad/` may not yet exist when callers pass `cwd=Path(".launchpad")`, so callers MUST `mkdir(parents=True, exist_ok=True)` before invoking the validator on subdirectories. The two underscore-prefixed helpers are module-private (test-only callers); the public surface is `validate_relative_path()` + `PathValidationError`.

## 7. Brainstorm output contract

`/lp-brainstorm` writes `.launchpad/brainstorm-summary.md` for `/lp-pick-stack` to consume.

```markdown
---
generated_at: 2026-04-30T19:42:11Z
generated_by: /lp-brainstorm
greenfield: true
cwd_state_when_generated: empty
---

# Project summary

<2-4 paragraphs of free-form Markdown describing the project intent.
Written by Claude during the brainstorm session. Treated as untrusted-as-data
by all downstream consumers.>

# Suggested next step

Run `/lp-pick-stack` next to choose a stack.
```

Frontmatter validation: `generated_at` ISO 8601 UTC; `generated_by` ∈ `{"/lp-brainstorm"}`; `greenfield` boolean; `cwd_state_when_generated` ∈ `{"empty", "brownfield", "ambiguous"}` (see §8).

`/lp-pick-stack` always re-asks the user for a project description rather than parsing the brainstorm body. The brainstorm summary is shown to the user as context but never piped into Claude as instructions. Re-running `/lp-brainstorm` overwrites the existing summary with a new `generated_at`.

### `.first-run-marker` write — greenfield-only (Layer 5 spec-flow P3-LF7)

The `.first-run-marker` (per §4 rule 10) is written ONLY when `greenfield: true`. On `greenfield: false` (brownfield) or `ambiguous-without-confirmation`, NO marker is written; subsequent `/lp-pick-stack`/`/lp-scaffold-stack` invocations route via the brownfield path which doesn't require the marker. This prevents the footgun where a brownfield-context marker collides with a future `cd <new-dir>` greenfield run if the user moves the marker file. The marker is ONLY a positive first-run signal for the greenfield happy path.

### Brainstorm re-run on cwd with unconsumed marker (Layer 8 — closes spec-flow P2-1)

If `/lp-brainstorm` is re-invoked in a cwd where `.launchpad/.first-run-marker` already exists (and is unconsumed — i.e., not yet renamed to `.first-run-marker.consumed.<ts>`), the new invocation MUST refuse with `reason: "first_run_marker_concurrent_invocation"` and the user-facing message: "session in progress; remove `.launchpad/.first-run-marker` if stale OR run `/lp-scaffold-stack` to consume it first." The `O_CREAT|O_EXCL` flag in the v2.0 marker write protocol (per §4 rule 10 strip-back substitute) provides the race-detection mechanism.

After marker has been `.consumed.<ts>` by `/lp-scaffold-stack`, re-running `/lp-brainstorm` succeeds: a fresh empty marker overwrites prior state; the prior `.consumed.<ts>` is preserved as audit trail.

### Mid-pipeline `cd` parity (Layer 8 — closes spec-flow P2-2)

`bound_cwd` triple binding at `/lp-pick-stack` write-time + `/lp-scaffold-stack` consume-time covers the pick-stack → scaffold-stack boundary. The brainstorm → pick-stack boundary is unbound at v2.0: `/lp-pick-stack` does NOT verify cwd parity with the brainstorm summary's location. **Documented v2.0 behavior**: if the user `cd`s between `/lp-brainstorm` and `/lp-pick-stack`, pick-stack proceeds in the new cwd; if the new cwd does not contain a `.launchpad/brainstorm-summary.md`, pick-stack treats the invocation as standalone (no marker, no session continuity). v2.2 may add cwd-parity verification alongside `brainstorm_session_id` per BL-235.

### Concurrent `/lp-pick-stack` race (Layer 8 — closes spec-flow P2-4; Layer 9 hardened — closes spec-flow P3 rationale.md atomicity)

Two simultaneous `/lp-pick-stack` invocations on the same cwd would each compute their own integrity envelope and race to write `.launchpad/scaffold-decision.json` AND `.launchpad/rationale.md`. v2.0 acceptance scope: **single-process invocation model** — concurrent pick-stack on same cwd is "user error scope," undefined behavior. The pick-stack writer SHOULD use `os.open(... O_WRONLY|O_CREAT|O_EXCL, 0o600)` on **both** files: write `rationale.md` FIRST (closes the L9-surfaced footgun where the loser's rationale.md would otherwise overwrite the survivor's, surfacing later as a confusing scaffold-stack `rationale_sha256` mismatch), then compute `rationale_sha256`, then write `scaffold-decision.json` second. On `FileExistsError` from EITHER file, refuse with `reason: "scaffold_decision_already_exists"` (covers both rationale.md and decision.json races under the same reason — the user's recovery action is identical: remove `.launchpad/` and re-run). This is a defense-in-depth measure; the load-bearing race protection is the user-driven single-process invocation model.

### Brainstorm re-run state recomputation

Every `/lp-brainstorm` re-run **recomputes** `cwd_state_when_generated` and `greenfield` against the current cwd; never inherited from a prior summary. If state changed since the prior run (e.g., user added files between sessions, going from `empty` to `brownfield`), the new summary's "Suggested next step" reflects the new state. Pick-stack reads only the current summary; never caches across runs.

**Brownfield re-run + cwd-state transition** (Layer 5 spec-flow P2-LF4; Layer 8 wording normalized — closes spec-flow P2-3): after a successful `/lp-scaffold-stack`, the cwd transitions from "empty" to "brownfield." Subsequent `/lp-brainstorm` re-runs in the same cwd will detect brownfield and **suggest** `/lp-define` (the brownfield happy path), NOT `/lp-pick-stack`. v2.0 has NO auto-routing or auto-invocation across commands; everything is user-driven. This is correct behavior: the user's intent in re-running is captured by `/lp-brainstorm`'s brownfield suggestion, not by fighting `/lp-scaffold-stack`'s idempotency check. The "redo scaffold" workflow is not supported in v2.0; the user must `cd` to a fresh directory or manually clean cwd before re-invoking the greenfield pipeline.

## 8. Greenfield-detection heuristic

Single source of truth, used by `/lp-brainstorm` (routing) and `/lp-scaffold-stack` (idempotency). Lives at `plugins/launchpad/scripts/cwd_state.py`. The shared `BROWNFIELD_MANIFESTS` constant is also imported by `plugins/launchpad/scripts/plugin-stack-detector.py` so the heuristic does not drift between v1 and v2 surfaces.

**Single-source enforcement (Layer 2 P2-1 + P3-7).** The "single source of truth" claim is enforced at three layers:

1. **Unit test** at `plugins/launchpad/scripts/tests/test_brownfield_manifests_single_source.py`:
   ```python
   import inspect
   from cwd_state import BROWNFIELD_MANIFESTS as cwd_set
   import plugin_stack_detector
   src = inspect.getsource(plugin_stack_detector)
   assert "BROWNFIELD_MANIFESTS = {" not in src, "v1 must IMPORT, not redefine. See HANDSHAKE §8."
   assert plugin_stack_detector.BROWNFIELD_MANIFESTS is cwd_set, "identity check"
   ```
2. **CI lint grep**: `plugin-v2-handshake-lint.py` asserts `grep -rEn 'BROWNFIELD_MANIFESTS\s*=\s*\{' plugins/launchpad/scripts/` matches exactly one file (`cwd_state.py`); any other definition is a CI failure.
3. **Import grep** (Layer 5 pattern P3-L5-F tightened for relative-import resilience): `grep -rEn '^\s*from\s+(\.|cwd_state)\s+import.*BROWNFIELD_MANIFESTS' --include='*.py' plugins/launchpad/scripts/` (with cwd_state.py self-excluded) MUST account for every reference outside `cwd_state.py`. Pattern handles both absolute (`from cwd_state import`) and relative (`from .cwd_state import`) import forms; multi-line `from cwd_state import (BROWNFIELD_MANIFESTS,` paren-style imports also matched via subsequent line continuation. Commented imports (`# from cwd_state import …`) are excluded by the `^\s*` anchor.

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

GREENFIELD_OK_FILES = {".gitignore", "README.md", "LICENSE"}
GREENFIELD_OK_DIRS  = {".git", ".launchpad"}

# Single source of truth — also imported by plugin-stack-detector.py.
# Compared case-INsensitively below: macOS (APFS default) and Windows (NTFS default)
# are case-insensitive filesystems where `Package.json` and `package.json` resolve
# to the same file. Linux comparison is also lower-cased for cross-platform parity.
BROWNFIELD_MANIFESTS = {
    # Node / TS
    "package.json", "tsconfig.json", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb",
    # Python
    "pyproject.toml", "requirements.txt", "Pipfile", "Pipfile.lock",
    "poetry.lock", ".python-version",
    # Ruby
    "Gemfile", "Gemfile.lock",
    # Elixir
    "mix.exs", "mix.lock",
    # Go
    "go.mod", "go.sum",
    # Dart / Flutter
    "pubspec.yaml", "pubspec.lock",
    # Rust
    "Cargo.toml", "Cargo.lock",
    # PHP
    "composer.json", "composer.lock",
    # Nix
    "flake.nix", "shell.nix", "default.nix",
    # asdf / version managers
    ".tool-versions",
}

_BROWNFIELD_MANIFESTS_LOWER = frozenset(m.lower() for m in BROWNFIELD_MANIFESTS)


# Layer 5 performance P3-L5-1: cap iteration at 500 entries to bound the
# slow-path syscall burst for users who accidentally invoke from /, ~, or
# a giant monorepo root. "User ran from a giant cwd" is a misuse; the safe-
# fail answer is "ambiguous" (refuses without per-entry stat()).
_CWD_STATE_MAX_ENTRIES = 500


def cwd_state(cwd: Path) -> Literal["empty", "brownfield", "ambiguous"]:
    if not cwd.exists():
        raise NotADirectoryError(f"cwd_state: path does not exist: {cwd!r}")
    if not cwd.is_dir():
        raise NotADirectoryError(f"cwd_state: path is not a directory: {cwd!r}")
    entries = []
    for i, e in enumerate(cwd.iterdir()):
        if i >= _CWD_STATE_MAX_ENTRIES:
            return "ambiguous"  # too many entries — fail safe without stat()
        entries.append(e)
    names = {e.name for e in entries}
    names_lower = {n.lower() for n in names}
    if names_lower & _BROWNFIELD_MANIFESTS_LOWER:
        return "brownfield"
    extras = names - GREENFIELD_OK_FILES - GREENFIELD_OK_DIRS
    if not extras:
        return "empty"
    if len(extras) == 1 and "README.md" in names:
        readme = cwd / "README.md"
        if readme.stat().st_size < 500:
            return "empty"
    # Generic safeguard: any unrecognized file > 100 bytes triggers ambiguous
    # so unknown ecosystems fail safe rather than greenfield-by-omission.
    for name in extras:
        path = cwd / name
        if path.is_file() and path.stat().st_size > 100:
            return "ambiguous"
    return "ambiguous"


def refuse_if_not_greenfield(cwd: Path, command_name: str) -> None:
    """Shared refusal helper. Raises NotADirectoryError or RuntimeError with a
    structured `reason:` field that callers wire into the §4 rejection JSONL.

    Callers: /lp-pick-stack (Step 0.5 pre-question gate), /lp-scaffold-stack
    (idempotency gate). Eliminates two near-identical `if state == "brownfield":`
    branches across commands.
    """
    state = cwd_state(cwd)
    if state == "brownfield":
        raise RuntimeError(
            f"{command_name}: cwd is brownfield; not applicable. "
            f"Use /lp-define instead. reason: cwd_state_brownfield"
        )
    if state == "ambiguous":
        raise RuntimeError(
            f"{command_name}: cwd is ambiguous; refuse to proceed without user "
            f"confirmation. reason: cwd_state_ambiguous"
        )
```

| State        | `/lp-brainstorm` action                                    | `/lp-pick-stack` action                                                           | `/lp-scaffold-stack` action                            |
| ------------ | ---------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `empty`      | Write summary `greenfield: true`; suggest `/lp-pick-stack` | Proceed                                                                           | Proceed                                                |
| `brownfield` | Write summary `greenfield: false`; suggest `/lp-define`    | **Refuse before asking questions** with structured error pointing at `/lp-define` | Refuse: "cwd is brownfield; pick-stack not applicable" |
| `ambiguous`  | Prompt user; default to brownfield path on no-answer       | Prompt user (proceed at user's confirmation)                                      | Refuse and ask user to clean cwd                       |

### Brownfield sub-app workflow

A user wanting to add a sub-app inside an existing brownfield monorepo (e.g., adding `apps/admin` next to an existing `apps/web`) does not use the four-command pipeline. The "refuse before asking questions" behavior of `/lp-pick-stack` is correct — its contract is "scaffold a fresh project," not "extend an existing one."

**Canonical workflow**: use a live Claude Code session. Have a regular conversation about whether you need a separate sub-app or just a route in the existing app. When you've decided, ask Claude to scaffold the new sub-app, matching existing monorepo conventions read live from the parent (shared `@repo/*` packages, ESLint inheritance, tsconfig path aliases, lefthook config, `pnpm-workspace.yaml`, `turbo.json`). LaunchPad's value-add for this task is the workflow harness around live agentic work (`/lp-review`, `/lp-learn`, `/lp-plan`, `/lp-build`, `/lp-design-review`), not the file-creation step itself — the catalog scaffolder cannot read parent-monorepo conventions, so a live Claude session is structurally better suited to producing output that integrates cleanly.

No `--allow-brownfield` flag is added to the four-command pipeline because that pattern normalizes "edit safety check locally."

## 9. `rationale.md` summary extractor + knowledge-anchor read-and-verify

### 9.1 Summary extractor

Closes the persistent prompt-injection vector: `/lp-define` never reads `rationale.md` directly. It reads only the pre-extracted, sanitized `rationale_summary` array embedded in `scaffold-decision.json` (§4 field 7).

`/lp-pick-stack` runs the extractor immediately after writing `rationale.md`:

````python
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ALLOWED_SECTIONS = {
    "project-understanding", "matched-category", "stack",
    "why-this-fits", "alternatives", "notes",
}
MAX_BULLETS_PER_SECTION = 8
MAX_BULLET_CHARS = 240

# ASCII attack patterns
FORBIDDEN_BULLET_RE = re.compile(
    r"```|<|>|http://|https://|file://|data:|javascript:|vbscript:",
    re.IGNORECASE,
)

def _has_dangerous_unicode(s: str) -> bool:
    """Reject strings containing format/control characters or whose NFKC
    differs from input (catches fullwidth confusables like ＜＞ and zero-
    width joiners that bypass byte-length checks).
    """
    nfkc = unicodedata.normalize("NFKC", s)
    if nfkc != s:
        return True
    for ch in s:
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Cc") and ch not in (" ", "\t"):
            return True
    return False


def extract_summary(rationale_path: Path) -> list[dict]:
    text = rationale_path.read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {k: [] for k in ALLOWED_SECTIONS}
    current = None
    for line in text.splitlines():
        h2 = re.fullmatch(r"##\s+(.+?)\s*", line)
        if h2:
            slug = re.sub(r"[^a-z0-9-]", "-", h2.group(1).lower()).strip("-")
            current = slug if slug in ALLOWED_SECTIONS else None
            continue
        if current is None:
            continue
        bullet = re.fullmatch(r"\s*[-*]\s+(.+?)\s*", line)
        if not bullet:
            continue
        body = bullet.group(1)
        if FORBIDDEN_BULLET_RE.search(body):
            continue
        if _has_dangerous_unicode(body):
            continue
        if len(body) > MAX_BULLET_CHARS:
            body = body[:MAX_BULLET_CHARS] + "…"
        if len(sections[current]) < MAX_BULLETS_PER_SECTION:
            sections[current].append(body)

    return [
        {"section": s, "bullets": sections[s]}
        for s in ("project-understanding", "matched-category", "stack",
                 "why-this-fits", "alternatives", "notes")
    ]
````

The extractor is pure-Python — no Markdown rendering, no LLM in the loop, no regex backtracking on user input. Implementation lives at `plugins/launchpad/scripts/lp_pick_stack/rationale_summary_extractor.py`. Tests lower-bound at 50 fuzz inputs derived from `MAX_BULLET_CHARS` boundary, NFKC confusable list, and known prompt-injection corpus.

`/lp-define` consumes `rationale_summary` exclusively. If the field is missing, malformed, or all-bullets-empty, `/lp-define` produces docs WITHOUT rationale context (degraded gracefully) and emits a warning. It NEVER falls back to reading `rationale.md` directly.

### 9.2 Knowledge-anchor read-and-verify (closes TOCTOU)

Curate-mode scaffolders pin `knowledge_anchor` pattern docs by `knowledge_anchor_sha256`. The contract requires atomic read-then-hash with symlink-resolution pinning. Lives in its own module `plugins/launchpad/scripts/knowledge_anchor_loader.py` (separated from `decision_integrity.py` per SRP — integrity envelope vs. plugin-shipped-asset loading are distinct concerns):

```python
from __future__ import annotations

import hashlib
from pathlib import Path


def read_and_verify(
    path: Path,
    expected_sha256: str,
    plugins_root: Path,
) -> bytes:
    """Read a plugin-shipped trusted file once, hash the buffer, return buffer.

    Symlink resolution happens BEFORE read; ancestor-symlink rejection mirrors
    the §6 path validator's TOCTOU defense. Callers MUST pass the buffer
    (never the path) into Claude's context constructor.
    """
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(plugins_root.resolve(strict=True)):
        raise ValueError(f"knowledge anchor escapes plugins root: {resolved}")
    if resolved.is_symlink():
        raise ValueError(f"knowledge anchor is symlink: {resolved}")
    cur = resolved
    while cur != plugins_root:
        if cur.is_symlink():
            raise ValueError(f"ancestor of knowledge anchor is symlink: {cur}")
        if cur.parent == cur:
            break
        cur = cur.parent

    buf = resolved.read_bytes()
    actual = hashlib.sha256(buf).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"checksum mismatch on {resolved}: expected {expected_sha256}, got {actual}"
        )
    return buf
```

CI lint (per OPERATIONS §2) greps the codebase for any opening of `plugins/launchpad/scaffolders/*.md` outside of `knowledge_anchor_loader.read_and_verify()`, and fails on any non-helper read site.

## 10. Version policy

v2.0 development uses a single provisional version string for both decision and receipt JSON: `version: "0.x-test"`. Coordinated bump to `"1.0"` in a single commit at v2.0.0 ship.

Lifecycle:

- **During v2.0 development**: `version: "0.x-test"`. Both commands validate `version` against this exact string. Unknown values rejected.
- **At v2.0.0 ship**: a single coordinated commit bumps `version` to `"1.0"` in this **exhaustive list** (Layer 2 P2-7 + P3-3 + Layer 3 schema-drift P1-4 + data-migration P2-C/D/E/F — gated by `plugin-v2-handshake-lint.py --check-version-coherence` per OPERATIONS §6 gate workflow):
  - `plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml` (top-level + per-entry)
  - `plugins/launchpad/scaffolders.yml` (`schema_version:` top-level field per Layer 2 P2-6)
  - `plugins/launchpad/scripts/plugin-scaffold-stack.py` (validator constant `EXPECTED_DECISION_VERSION`)
  - `plugins/launchpad/scripts/lp_pick_stack/__init__.py` (writer constant `WRITTEN_DECISION_VERSION`)
  - `plugins/launchpad/scripts/plugin-scaffold-receipt-loader.py` (`ACCEPTED_RECEIPT_VERSIONS` + writer `WRITTEN_RECEIPT_VERSION`)
  - This document's frontmatter + `SCAFFOLD_OPERATIONS.md`'s frontmatter
  - All test fixtures under `plugins/launchpad/scripts/tests/fixtures/` (regenerated + re-signed via `plugin-v2-handshake-lint.py --regenerate-fixtures` per Layer 2 P1-1 + deploy F-15; sweep gated by `plugins/launchpad/scripts/tests/fixtures/manifest.yml` per Layer 3 data-migration P2-D — every fixture file MUST be enumerated in the manifest, CI lint asserts no fixture exists outside)
  - **NEW Layer 3 schema-drift P1-2/P1-3/P1-4**: `recommended_recovery_action` JSON shape in OPERATIONS §6 gate #11 (carries `version: "1.0"`); freshness report YAML schema (`schema_version` field added in OPERATIONS §4); telemetry JSONL line schema (`schema_version: "1.0"` field added in OPERATIONS §5)
  - **NEW Layer 5 schema-drift P2-SD5-1/2/3 + data-migration P2-DM5-2** (Layer 7 strip-back drops `security-events.jsonl` per BL-220+BL-223 and `.first-run-marker` envelope schema per BL-235): `tests/fixtures/manifest.yml` top-level `schema_version: "1.0"` field; `.harness/observations/restamp-history.jsonl` line schema (carries `schema_version: "1.0"` field at v2.0 per Layer 5 data-migration P3-DM5-3 — even though BL-215 defers chain-hashing to v2.2, the field itself ships at v2.0 to avoid forward-compat coupling); `.harness/observations/scaffold-rejection-<ts>.jsonl` line schema (carries `schema_version: "1.0"` field at v2.0 per Layer 7 closure of L6-ε #2). v2.0 readers REJECT absent `schema_version` lines per OPERATIONS §4 schema_version handling subsection (NOT silent-treat-as-v0; that v2.1+ reader policy is a forward-compat trap at v2.0)
  - `ROADMAP.md` (v2.0 / v2.1 / v2.2 sections; any version pin) — H1 consolidation 2026-04-30 retired the prior `docs/v2-roadmap.md`
  - `docs/releases/v2.0.0.md` (release notes file MUST exist before tagging per `feedback_release_notes_required` global rule)
  - `.claude-plugin/marketplace.json` (Layer 3 deployment P1-C: schema-valid + points at this repo; explicit `latest` version pin DROPPED per PR #38 cache-pinning policy — adversarial P1-RT-6 reconciliation)
  - `plugins/launchpad/.claude-plugin/plugin.json` (`version` field)
  - **The bump commit is the responsibility of the orchestration plan's Phase 7.5 freshness pass**.
- **Post-bump invariant** (Layer 2 P1-1 case 2 + Layer 5 data-migration P1-DM5-2 user-tree carve-out): the string `0.x-test` MUST NOT appear anywhere in the **plugin-shipped repository tree** after the bump commit. Enforced by `plugin-v2-handshake-lint.py` via `git grep -F '"version": "0.x-test"'` returning empty AND `git grep -F '0.x-test'` returning empty (modulo this `HANDSHAKE.md` § itself, which is allowlisted because it documents the lifecycle). **User-tree carve-out**: the invariant applies to plugin-shipped trees (`plugins/launchpad/`, `docs/`, `tests/fixtures/`) ONLY. User-generated `.launchpad/scaffold-decision.json` / `.launchpad/scaffold-receipt.json` files in downstream-project working trees are out of scope of this invariant — those files are user-tree state, not plugin-tree state, and a user mid-pipeline at the v2.0-rc → v2.0.0 upgrade transition has the §4 rule 1 `version_unsupported` rejection + remediation hint as their recovery path.
- **In-flight test fixtures** (Layer 2 P1-1): any `scaffold-decision.json` / `scaffold-receipt.json` files written during testing with `version: "0.x-test"` are regenerated AND re-signed (SHA-256 envelopes recomputed against `"1.0"`) by `plugin-v2-handshake-lint.py --regenerate-fixtures` (folded into the lint CLI per Layer 3 simplicity P1-F + architecture P2-6 — was a separate `regenerate-fixtures.py` script in Layer 2 spec, consolidated into the existing lint CLI as a `--regenerate-fixtures` flag mode for SRP coherence — read-only verification + write-mutating regeneration both share the §10 bump-list awareness). The script is **2-pass atomic** (Layer 3 spec-flow P1-2): pass 1 (validate) parses every fixture in the manifest, computes target hashes in memory, exits non-zero if any fixture is malformed; pass 2 (atomic write) writes regenerated files via temp-file + atomic-rename. `--dry-run` flag runs pass 1 only.
- **Working-tree advisory** (Layer 2 P1-1 case 3): pre-merge of the v2.0.0 ship commit, every contributor on `feat/v2-greenfield-pipeline` MUST verify `git status` is clean and `find . -name 'scaffold-*.json'` returns no untracked fixtures. OPERATIONS §3 branch-drift discipline carries this advisory.
- **Post-ship breaking changes** (v2.1+): bump to `"1.1"` only if forward-compatible with `"1.0"`; bump to `"2.0"` for breaking changes.
- **v2.1 envelope (additive minor)**: v2.1 keeps the legacy `version` field at `"1.0"` for v2.0-reader compat and adds a NEW `schema_version` field carrying `"1.1"` as the v2.1 reader indicator. Acceptance ladder lives in §10.v2.1 (next sub-section). The §4 schema documents both the v1.0 and v1.1 fields side by side. New v2.1 fields (`schema_version`, `plugin_version`, `stacks`, `identity`, `identity_updated_at`) are all additive; v2.0 readers ignore them. Bootstrap-manifest envelope uses an independent `manifest_schema_version` field (rename closes the cross-envelope name collision) — see §10.v2.1 acceptance rules.

Both `scaffold-decision.json` and `scaffold-receipt.json` carry their own version field independently — they may diverge in future versions, subject to the receipt-version-≥-decision-version constraint (Layer 3 architecture P3-5): receipt cannot be older-versioned than the decision it acknowledges.

### Forward-compatibility policy — DEFERRED to v2.2 (Layer 3 + Layer 7 retarget)

**v2.0 ships strict-equality**: `EXPECTED_DECISION_VERSION = frozenset({"1.0"})` and `ACCEPTED_RECEIPT_VERSIONS = frozenset({"1.0"})`. Any unknown version triggers `reason: "version_unsupported"` (HANDSHAKE §4 rule 1).

**Naming-convention reservation for v2.2 forward-compat axis (Layer 9 — closes schema-drift P3-3)**: at v2.0, top-level `version` field rejection uses `version_unsupported` while JSONL `schema_version` rejection uses `*_schema_version_invalid` (single-reason design covers absent + unknown). If BL-211 forward-compat work at v2.2 reclaims the absent-vs-unknown distinction, the naming axis is reserved as: **`*_missing` for absent field**, **`*_unsupported` for unknown value**. Applied uniformly to BOTH top-level (`version_missing` / `version_unsupported`) AND JSONL (`*_schema_version_missing` / `*_schema_version_unsupported`). Costs nothing now; locks in the naming axis at v2.2 design time so consumers don't bikeshed.

The full forward-compat matrix (consumer-superset rule, producer-floor rule, per-version validation-pipeline-must-match invariant, version-confusion defenses) is **deferred to v2.2.0** and tracked at BACKLOG entry **BL-211** (Layer 7 retarget v2.1→v2.2: v2.1 reframed as documentation-only and has no cross-version need to bridge to). Rationale (Layer 3 simplicity P1-D + scope P2-3 + adversarial P1-RT-7): at v2.0 ship time, both frozensets are single-element — there is nothing to be forward-compatible WITH. Encoding the policy now means CI lint complexity, doc surface, and a matrix table with no current consumer. v2.2.0 is the right time to introduce it (when there's an actual cross-version need alongside other v2.2 manifest-coupled work), with full safeguards.

**`_legacy_yaml_canonical_hash` removal at v2.1.0 — bounded deprecation** (Layer 3 data-migration P1-A + Layer 5 security-lens P3-S3): tracked at BACKLOG entry **BL-210**. CI gate in `plugin-v2-handshake-lint.py`: when `plugin.json.version >= 2.1.0`, asserts `git grep -F '_legacy_yaml_canonical_hash' plugins/launchpad/scripts/` returns empty. **Bounded deprecation window**: the v2.0.x legacy retention is bounded at 12 months from v2.0.0 ship. If v2.1.0 has not shipped within 12 months of v2.0.0 ship, v2.0.x patches MUST drop legacy support (force users to re-export their hash) regardless of the v2.1.0 readiness — extended legacy retention is an attack surface for hash-downgrade games and is not justified by single-maintainer convenience.

**Tag immutability** (Layer 3 deployment P1-B + Layer 4 deployment N2 + adversarial P2-RT4-G + Layer 5 adversarial P1-A1 + security-lens P2-S3 hardened): GitHub repo settings MUST enable Tag protection rules matching the **broadened pattern** `v[0-9]+.[0-9]+.[0-9]+(-(yanked|recalled|rc[0-9]+|dryrun))?` (Layer 5 adversarial P1-A1: extended from `v[0-9]+.[0-9]+.[0-9]+` to also cover `-recalled`/`-yanked`/`-rc*`/`-dryrun` suffixes — closes namespace-squatting attack where a hostile contributor pre-creates `vX.Y.Z-recalled` BEFORE the maintainer needs to use that name in §7.0 procedure). Forbids deletion + force-push by anyone except admins. Tag protection rule creation is a **Phase -1 manual step** documented in `docs/runbooks/branch-protection-token.md` (so the rule is in place during the entire 22-34-week dev window, not just at ship). **Phase -1 acceptance gate verifies rule CONTENT, not just existence** (Layer 5 security-lens P2-S3 — closes admin-misclick gap where rule exists but force-push exception is enabled): `gh api repos/:owner/:repo/tags/protection --jq '.[] | select(.pattern == "v[0-9]+.[0-9]+.[0-9]+(-(yanked|recalled|rc[0-9]+|dryrun))?") | {pattern, allow_deletions, ...}'` MUST assert `allow_deletions: false`, no force-push exceptions, admins-only override. Phase 7.5 verification battery asserts the rule exists + content; the nightly `branch-protection-watchdog.yml` workflow extends to also assert tag-protection-rule existence + content daily. On endpoint deprecation: the watchdog probes `repos/:owner/:repo/rulesets` first (current GitHub standard) and falls back to legacy `tags/protection` for backward compat. **Yanked releases get a NEW `-yanked` suffix tag (per OPERATIONS §7); v2.0.0 is never reused against a different SHA. The §7.0 pre-launch tag-deletion exception was REMOVED in Layer 4 — see OPERATIONS §7.0.**

**Tag GPG signing — DEFERRED to v2.1** (Layer 4 simplicity P3 + scope P2-1 + deployment N1 + security-lens P2-S3 + feasibility P2-4 — collectively concluded the GPG signing infrastructure is over-spec for v2.0 single-maintainer + low-fork-PR threat model; tag protection rule alone suffices). Tracked at BACKLOG entry **BL-214**. v2.0 ships without GPG-signed tags; `verify-v2-ship` does NOT run `git verify-tag`. v2.1 reintroduces GPG signing only if external-contributor / fork-PR volume creates a real tag-impersonation threat. Drops: SIGNING.md doc, GPG-key-on-laptop maintainer overhead, `git verify-tag` step in verify-v2-ship (Layer 7 strip-back: v2.0 verify-v2-ship ships 4 checks per §1.5 — tag SHA / plugin.json / `0.x-test` residual / leakage regex; the Layer 5 8-check battery defers to v2.2 per BL-226/BL-227/BL-232; the Layer 4 "7 checks, not 8" phrase referenced an intermediate state and is moot under strip-back), key-rotation runbook, lost-key recovery procedure.

### 10.v2.1 — v2.1 schema acceptance rules + design-time decisions (Phase 0.3 lock)

**Canonical source**: [docs/plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md](../plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md) §11.3 + §11.7 + §17 Phase 0.3 + §22.

**`scaffold-decision.json` schema acceptance rules** (v2.1 reader; canonical at `plugin-config-loader.py:read_scaffold_decision()`):

| `schema_version`    | Behavior                                                                                                                                                                                                                                                                                                                                            |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| absent OR `"1.0"`   | Treat as 1.0; identity defaults to UNSET sentinels; stacks defaults to [detected]; emit WARN. `/lp-update-identity` transparently migrates legacy 1.0 envelopes to 1.1 on first invocation (Phase 1+2 retroactive amendment A3) by seeding `default_unset_identity()` if absent and bumping `schema_version` to `"1.1"` in the same atomic re-seal. |
| `"1.1"`             | Full read; identity required if present MUST validate against allowlist regex; stacks required (array). Known top-level fields include `kernel_render_state` and `version_drift_log` (Phase 10 + Phase 1+2 amendment A8).                                                                                                                           |
| `"1.x"` where x > 1 | Forward-compat: read known fields, ignore unknown, emit INFO                                                                                                                                                                                                                                                                                        |
| Major `>= 2`        | Fail closed: `"scaffold-decision.json schema 2.0+ requires plugin v3+"`                                                                                                                                                                                                                                                                             |
| Malformed           | Fail closed with clear error                                                                                                                                                                                                                                                                                                                        |

**`bootstrap-manifest.json` schema acceptance rules** (v2.1 reader; canonical at `plugin-config-loader.py:read_bootstrap_manifest()`):

| `manifest_schema_version` | Behavior                                                                         |
| ------------------------- | -------------------------------------------------------------------------------- |
| absent OR `"1.0"`         | Full read; required fields: `plugin_version`, `last_render_timestamp`, `files[]` |
| `"1.1+"`                  | Read known fields, ignore unknown, emit INFO                                     |
| Major `>= 2`              | Fail closed                                                                      |
| Malformed                 | Fail closed with clear error                                                     |

**`source_template_sha256` semantics for `lefthook.yml`** (v2.1.2 BL-316 Slice 4c.5; canonical at `lp_bootstrap.manifest_writer.compute_source_template_shas` + `lp_bootstrap.stack_lefthook.enumerate_lefthook_template_dependencies`): for every infrastructure file EXCEPT `lefthook.yml`, the manifest entry's `source_template_sha256` is the bare SHA-256 of the single `.j2` source template under `plugin_default_generators/infrastructure/`. For `lefthook.yml` specifically (and only when computed against the production root, not a fixture root), the field carries a COMPOSITE SHA-256 that incorporates the kernel template plus every plugin-shipped lefthook contributor under `plugin_stack_adapters/` — each per-stack `<stack>/templates/lefthook.j2.fragment` and every `_partials/*.fragment`. The composite is computed deterministically: `sha256(kernel_sha || "\n" || dep_name || ":" || dep_sha || "\n" || ...)` over the sorted-by-name dependency list. This widens `verify_source_template_shas` tamper-detection to fire when any contributor (not just the kernel) is modified, closing the Slice 4c.4 wiring's downstream-blast-radius gap. The composite is plugin-static — it does NOT depend on `.launchpad/config.yml` `stacks:` content — so legitimate user stack-list edits never trigger false-positive tamper warnings. v2.1.1→v2.1.2 upgrades will see a one-time MANIFEST_TAMPERED for `lefthook.yml` (kernel hash unchanged but composite-input set is new); the existing `--accept-plugin-version-drift` remediation covers this.

**v2.0 reader behavior on schema 1.1** (Round 3 closure of adversarial P3-8): v2.0 reader does NOT recognize `schema_version: "1.1"`. If a v2.0-era tool encounters a 1.1 envelope, the v2.0 reader's strict-equality `EXPECTED_DECISION_VERSION = frozenset({"1.0"})` check rejects with `version_unsupported`. The user-facing remediation: `"your plugin is too old; update via /plugin update"`.

**License enum starter set** (Phase 0.3 lock; canonical for v2.1 `/lp-pick-stack` identity questions):

```
MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, ISC, MPL-2.0, Other
```

Future additions require schema 1.x bump + HANDSHAKE update in same PR (CODEOWNERS gate).

**"Other" license body sanitization** (Phase 0.3 lock): max 10 KB; printable ASCII only; reject Jinja delimiters (`{{`, `{%`, `{#`); reject HTML tags; reject control characters except `\n` + `\t`. Implemented in `/lp-pick-stack` Step 0.3 input validation.

**Identity input allowlist regex** (canonical for v2.1 + Round 2 #16 supply-chain hardening):

- `project_name`: `^[A-Za-z][A-Za-z0-9_.-]{0,63}$` (must start with ASCII letter; the literal strings `.` and `..` are also explicitly rejected at validate_identity as defense-in-depth against path-traversal injection — Phase 1+2 retroactive amendment A2)
- `email`: RFC5322-lite (no whitespace, no quotes, must contain `@` + valid domain)
- `copyright_holder`: printable-ASCII; no backticks, quotes, dollar-signs, semicolons, newlines, Jinja delimiters (`{`, `}`), HTML angle brackets (`<`, `>`), or format-string `%`; max 200 chars (regex `^[\x20-\x7E]{1,200}$` plus a forbidden-chars deny list)
- `repo_url`: `^https?://[\w./%-]{1,512}$`

**Plugin version pin in scaffold-decision 1.1** (Round 3 P1 closure for `/plugin update` mid-pipeline): `/lp-pick-stack` records running plugin version into scaffold-decision.json `plugin_version` field. `/lp-scaffold-stack` and `/lp-bootstrap` ABORT with structured error if running plugin version differs from recorded version (prevents the §10.7 manifest-tampering check from rejecting freshly-sealed manifest because templates changed mid-flow). `/lp-update-identity` updates the field forward to running plugin version on each invocation.

**CODEOWNERS gate operationalization** (canonical at `.github/CODEOWNERS` + `plugin-v2-handshake-lint.py`): PRs that change `scaffold-decision.json` schema OR `bootstrap-manifest.json` schema OR `AdapterManifest` TypedDict definitions FAIL CI lint unless this `SCAFFOLD_HANDSHAKE.md` §10 / §10.v2.1 is also touched in the SAME PR. Single-developer caveat: gate enforces self-discipline at the commit boundary; even when the user is the only reviewer, schema changes + handshake doc updates ride together.

### 10.v2.1.4 — v2.1.4 amendments (BL-327 + BL-328 + BL-331)

Three additive amendments to the v2.1 schema contract land in v2.1.4 from the 2026-05-14 ulcspec.org dogfood test. None modify the on-disk envelope shape; all change the contract at the loader / validation layer.

- **BL-327: install-layout-aware default catalog paths.** `lp_scaffold_stack/engine.DEFAULT_SCAFFOLDERS_YML` and `DEFAULT_CATEGORY_PATTERNS_YML` now resolve via `Path(__file__).resolve().parents[2]` instead of `parents[4] / "plugins" / "launchpad"`. Path arithmetic is identical in both source-repo (`<repo>/plugins/launchpad/scripts/lp_scaffold_stack/engine.py`) and Claude Code marketplace cache (`~/.claude/plugins/cache/builtform/launchpad/<VERSION>/scripts/lp_scaffold_stack/engine.py`) layouts because in both cases `parents[2]` is the directory holding `scaffolders.yml` + `scripts/`. Pre-fix the install-layout default resolved to a non-existent path under a spurious `plugins/launchpad/` infix; every installed-plugin user hit `catalog_load_failed` on `/lp-scaffold-stack` manual-override invocations. The `--scaffolders-yml` / `--category-patterns-yml` CLI overrides are unchanged. `tests/test_install_layout_catalog_paths_v214.py` pins the path-arithmetic invariant against both layouts.

- **BL-328: `template_cache.fetch()` walk_scope kwarg.** `template_cache.fetch(repo_url, sha, *, fetcher=None, walk_scope=None)` and `template_cache.verify(repo_url, sha, *, walk_scope=None)` gain an optional `walk_scope: str | None` parameter — a relative POSIX subpath inside the fetched tree. When provided, the v2.1 D9.1 disallowed-entry walk (symlinks / block devices / char devices / FIFOs / sockets) is invoked against `handle.tmp_dir / walk_scope` rather than `handle.tmp_dir`. The "no symlinks reach user project" invariant is preserved at the same boundary, scoped to the actual copy path. The `_validate_walk_scope` validator at the cache boundary rejects traversal (`..`, `.`), absolute paths, NUL bytes, oversize (>256 chars), and chars outside `[A-Za-z0-9._/-]`. `_entry_files_match_manifest(entry_dir, *, walk_scope=None)` mirrors the parameter on the read side; the manifest comparison stays whole-tree so multiple sub-template adapters sharing a SHA do not race. AstroAdapter passes `walk_scope=_SUB_PATHS[sub_template_id]` (`""` is normalized to `None`). Co-shipped: `plugin-upstream-pin-walk-scope-parity.py` CI script wired into `v2-handshake-lint.yml` to catch this class of bug at PR time.

- **BL-331: `generic` selectable as primary stack.** `lp_pick_stack.VALID_COMBINATIONS` widens 21 → 26 tuples with 5 new `(generic, role)` entries: `frontend`, `frontend-main`, `frontend-dashboard`, `backend`, `fullstack`. The on-disk `scaffold-decision.json` v1.1 envelope's `layers[].stack` field accepts `"generic"` directly (no `_CATALOG_FALLBACK_MAP` translation needed because `generic` is already a `STACK_ID_ACTIVE_ENUM` member). The v1.1 envelope's flat `stacks` array therefore contains `"generic"` verbatim when picked. `scaffolders.yml` widens 10 → 11 entries with a `generic:` curate entry pointing at the new `plugins/launchpad/scaffolders/generic-pattern.md` knowledge anchor. `[scaffolders-catalog]` lint rule in `plugin-v2-handshake-lint.py` asserts exactly 11 stacks (was 10). The `generic`-as-primary path is DISTINCT from the v2.2-candidate fallback (`accept_v22_fallback=True`) which routes `python_django` / `python_generic` / `nextjs_hono_cloudflare` / `nextjs_trpc_prisma` / `rails` to the generic adapter as a "stack-aware adapter not yet ready" signal; `generic`-as-primary is positive intent and does NOT populate `adapter_dispatch_meta.fallback_ids` on the receipt. Receipt schema unchanged.

The §11 stack catalog wording below ("v2.0 — 10 entries") is a historical reference to the v2.0 ship lock; the v2.1.4 catalog ships 11 entries. Running source-of-truth: `plugins/launchpad/scaffolders.yml` `stacks:` map.

## 11. Stack catalog (v2.0 — 10 entries)

**Layer 3 catalog cut (feasibility P1-1 + scope cluster 7)**: catalog reduced from 15 → 10 entries, deferring 5 stacks to v2.1 (sveltekit, elysia, phoenix-liveview, convex, flutter). Rationale: 22-34 week solo dev calendar with branch drift risk + 5-7 hour per-stack adapter+walkthrough cost. Cutting 5 saves ~25-35h while preserving all 4 product pillars (frontend content, frontend app, backend Python, backend MVC, backend managed, mobile-via-Expo).

The 10-entry v2.0 catalog. Both plans reference this list as the authoritative v2.0 catalog.

| #   | Stack      | Pillar                       | Type        | Flavor                |
| --- | ---------- | ---------------------------- | ----------- | --------------------- |
| 1   | `astro`    | Frontend Content/Performance | orchestrate | pure-headless         |
| 2   | `next`     | Frontend App                 | orchestrate | pure-headless         |
| 3   | `eleventy` | Frontend Content             | curate      | n/a (no `npm create`) |
| 4   | `hugo`     | Frontend Content (Go)        | orchestrate | pure-headless         |
| 5   | `hono`     | Backend Edge-native TS       | orchestrate | pure-headless         |
| 6   | `fastapi`  | Backend Python               | curate      | n/a (no official CLI) |
| 7   | `django`   | Backend Python               | orchestrate | pure-headless         |
| 8   | `rails`    | Backend MVC (Ruby)           | orchestrate | pure-headless         |
| 9   | `supabase` | Backend Managed              | orchestrate | mixed-prompts         |
| 10  | `expo`     | Frontend Mobile (RN)         | orchestrate | pure-headless         |

The **10 deferred stacks** documented in [`ROADMAP.md` v2.2 section](../../ROADMAP.md#v22) (Layer 3 BL-212; H1 consolidation 2026-04-30 moved them from v2.1 to v2.2 alongside the operational/security infrastructure deferrals): `tauri`, `cloudflare-workers`, `nestjs`, `laravel`, `vite` (original 5 deferred) + `sveltekit`, `elysia`, `phoenix-liveview`, `convex`, `flutter` (Layer 3 catalog cut). They are NOT referenced by any v2.0 category-pattern.

## 12. Implementation files

These are the new files the v2.0 contract creates. Both plans reference this list as their joint deliverable surface (the v2.0 effort estimate accounts for these in **Phase -1: Foundation**).

### Naming convention

LaunchPad's existing `plugins/launchpad/scripts/` convention:

- **Hyphen-prefixed** filenames for CLI-invocable scripts: `plugin-config-hash.py`, `plugin-stack-detector.py`. **CLI scripts MUST live at `plugins/launchpad/scripts/<name>.py`, NOT inside `plugins/launchpad/scripts/tests/`** — pytest's default discovery (`test_*.py` / `*_test.py`) silently skips hyphen-prefixed filenames, so a CLI gate accidentally placed in `tests/` would never run as a unit test even if intended.
- **Underscored** module names for importable Python packages under `plugin_stack_adapters/` and `lp_pick_stack/`.
- **Pytest test files** MUST use `test_<unit>.py` naming (underscore, no hyphens). Discovery is configured at repo root via `pytest.ini` with `python_files = test_*.py`. Any test placed under `plugins/launchpad/scripts/tests/` failing this convention is a CI-lint violation (per OPERATIONS §2).

| File                                                                     | Owner                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Type             | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `plugins/launchpad/scripts/decision_integrity.py`                        | Both plans                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Library          | `canonical_hash()` per §3 (integrity envelope only; sibling module owns asset loading)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `plugins/launchpad/scripts/knowledge_anchor_loader.py`                   | Both plans                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Library          | `read_and_verify()` per §9.2 (split from `decision_integrity.py` per SRP)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `plugins/launchpad/scripts/path_validator.py`                            | Both plans                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Library          | `validate_relative_path()` + `PathValidationError` per §6 (internally `_validate_path_shape` + `_validate_filesystem_safety`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `plugins/launchpad/scripts/cwd_state.py`                                 | Both plans                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Library          | Greenfield/brownfield/ambiguous classifier + `refuse_if_not_greenfield()` shared refusal helper per §8                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `plugins/launchpad/scripts/safe_run.py`                                  | Orchestration plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Library          | `safe_run()` subprocess helper per OPERATIONS §1 (internally `_validate_argv` + `_safe_run_invoke`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `plugins/launchpad/scripts/telemetry_writer.py`                          | Both plans                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Library          | `write_telemetry_entry()` shared JSONL appender for `.harness/observations/v2-pipeline-*.jsonl` per OPERATIONS §5; opt-out aware (skips if `.launchpad/config.yml` has `telemetry: off`); owns `.telemetry.lock` only — security/forensic writes route through the SEPARATE `forensic_writer.py` module per Layer 5 architecture P2-A2 split                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `plugins/launchpad/scripts/forensic_writer.py`                           | **DEFERRED to v2.2 per §1.5 strip-back (BL-223)** — v2.0 does NOT ship this module; restamp-audit baseline injection-defense is written inline by lefthook commit-msg hook                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Library          | **NEW (Layer 5 architecture P2-A2 SRP split + security-lens P1-S1)**: `write_security_event()` + `write_scaffold_rejection()` + `write_recovery_partial()` + `write_restamp_audit()` for the 4 always-on forensic JSONL paths. Owns `.security-events.lock`, `.scaffold-rejection.lock`, `.recovery.lock`, `.restamp-audit.lock` — separate locks per concern to avoid DoS coupling. Always writes (NOT gated by `telemetry: off`). Per HANDSHAKE §3 "Security event log spec": file mode 0o600, atomic single-write ≤4096 bytes, fsync+F_FULLFSYNC, `prev_entry_sha256` chain field, closed event enum                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `plugins/launchpad/scripts/lp_pick_stack/__init__.py`                    | Pick-stack plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Library          | Pick-stack package init; **owns the manual-override `VALID_COMBINATIONS` frozenset of `(stack, role)` tuples** (inlined here; NOT a separate YAML or `.py` file — at 7 rules the file overhead doesn't earn its keep, promote to YAML when the matrix exceeds ~30 rules)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `plugins/launchpad/scripts/lp_pick_stack/rationale_summary_extractor.py` | Pick-stack plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Library          | Summary extractor per §9.1                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `plugins/launchpad/scripts/lp_pick_stack/data/category-patterns.yml`     | Pick-stack plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Data             | Category-pattern catalog (~18 entries)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `plugins/launchpad/scripts/lp_pick_stack/data/pillar-framework.md`       | Pick-stack plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Data             | Secondary doc for rationale generation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `plugins/launchpad/scripts/lp_pick_stack/data/rationale-template.md`     | Pick-stack plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Data             | Strict Markdown template Claude fills                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `plugins/launchpad/scripts/plugin-v2-handshake-lint.py`                  | Joint deliverable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | CLI (multi-mode) | CI lint per OPERATIONS §2. **Dispatch contract (Layer 4 architecture P1 + simplicity P3 + Layer 5 deployment P3-D1 + simplicity P2-2 + performance P2-L5-2 + security P2-S1)**: default invocation (no flag) is **read-only** and is the only mode permitted in PR-triggered CI workflows; `--regenerate-fixtures` is the SOLE write-mutating mode and may run only in `v2-release.yml` (Phase 7.5 ship workflow). Read-only modes: default (schema validation + grep checks for `safe_run`/`shell=True`/`read_and_verify` + `0.x-test` residual + `BROWNFIELD_MANIFESTS` single-source + hyphen-test-file rejection + **AST-based `pull_request_target` shape check inlined into default mode** (Layer 4 security-lens P1-S2 + Layer 5 security-auditor P2-4 extended: parses `.github/workflows/*.yml` via YAML AST using **`yaml.safe_load` ONLY** — Layer 5 security P2-S1 supply-chain pin; CI lint sub-rule asserts `yaml.load(` does not appear in this script; vendored PyYAML version pinned via `_vendor/PYYAML_VERSION` constant + Phase -1 acceptance gate checks against latest CVE list; rejects `actions/checkout` `with.ref` derived from `github.event.pull_request.*` AND any `${{ … }}` expression containing AST paths `github.event.pull_request.head.sha`/`head.ref`/`head.repo.*`/`merge_commit_sha`/`body`/`title`/`user.login`/`workflow_run.head_sha`/`head_branch`; closes bracket-notation/expression-evaluator bypasses AND attacker-controlled fork-PR fields used in `gh issue comment`/shell scripts)), `--check-version-coherence --phase=pre-bump | post-tag`(Layer 4 adversarial P1-RT-5 + Layer 5 deployment P3-D1: pre-bump asserts file-coherence-among-bump-list before commit lands; post-tag asserts tag-match-against-version-literal after push; explicitly enumerated in dispatch contract — Layer 5 simplicity P2-2 alternative renaming to`--check-tag-coherence`was rejected to preserve`--check-version-coherence`brand recognition; the`--phase=`discriminator is well-documented),`--check-\_legacy_yaml_canonical_hash-removal`(gates v2.1.0 removal via BL-210),`--verify-security-events-chain`(Layer 5 security-lens P1-S1: walks`.harness/observations/security-events.jsonl`and asserts`prev_entry_sha256`chain integrity; reports break point on tampering). Write-mutating mode:`--regenerate-fixtures`(2-pass atomic regen; consumes`tests/fixtures/manifest.yml`per Layer 3 data-migration P2-D as source-of-truth +`--max-fixtures 200`safety cap from Layer 5 performance P2-L5-2 — exits non-zero with`reason: "fixture_count_exceeded"`if manifest >200; runtime budget **<10s on the v2.0 fixture set; <60s at 5x growth**, asserted as Phase -1 acceptance gate). CI lint sub-rule:`git grep -F 'plugin-v2-handshake-lint.py --regenerate-fixtures'`MUST be empty in any`.github/workflows/\*.yml`other than`v2-release.yml`. Strict-equality version-check ships in v2.0; full forward-compat matrix consistency check is BL-211 deferred to v2.1 |
| `plugins/launchpad/scripts/plugin-scaffold-receipt-loader.py`            | Orchestration plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | CLI              | Receipt loader/validator for `/lp-define`; carries `ACCEPTED_RECEIPT_VERSIONS` and `WRITTEN_RECEIPT_VERSION` constants (single-element frozensets at v2.0; expanded under BL-211 forward-compat policy at v2.1)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `plugins/launchpad/scripts/plugin-freshness-check.py`                    | Joint deliverable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | CLI              | **Promoted to Phase -1 deliverable per Layer 2 F-02** (was Phase 7.5-only); runs advisory on every PR for the entire 22-34-week dev window so the script is well-exercised by ship time. Phase 7.5 promotes from advisory to gating                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `plugins/launchpad/scripts/plugin-config-hash.py`                        | Joint deliverable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | CLI              | **Layer 3 simplicity P2-E + architecture P2-6**: legacy YAML migration detection logic INLINED into this existing CLI as a function (was a separate `lp-migrate-config-hash.py` in Layer 2 spec; collapsed into the existing module that owns the hash function). When `LP_CONFIG_REVIEWED` is set but doesn't match new hash, the script invokes the soft-warn UX from HANDSHAKE §3                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `tests/fixtures/manifest.yml`                                            | Joint deliverable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Data             | **NEW (Layer 3 data-migration P2-D + Layer 5 data-migration P2-DM5-2 versioning)**: enumerates every fixture file under `plugins/launchpad/scripts/tests/fixtures/` with purpose + target schema version. Top-level `schema_version: "1.0"` field at v2.0 (registered in §10 lifecycle bump list — closes v2.0→v2.1 manifest schema drift trap). Per-fixture `target_decision_version: "1.0"` and `target_receipt_version: "1.0"` columns. `--regenerate-fixtures` pass 1 (validate) MUST hard-reject manifests with unknown `schema_version` and emit `reason: "manifest_schema_unsupported"`. CI lint asserts no fixture exists outside the manifest; `plugin-v2-handshake-lint.py --regenerate-fixtures` reads the manifest as source of truth                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `.launchpad/.first-run-marker`                                           | Brainstorm contract                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Sentinel         | **v2.0 (post-Layer-7 strip-back per §1.5)**: simple positive-presence sentinel — empty file written by `/lp-brainstorm` ONLY when `greenfield: true`, renamed to `.first-run-marker.consumed.<iso-ts>` after first successful `/lp-scaffold-stack`. **Integrity binding (JSON envelope + sha256 + bound_cwd + dedicated lock + FD-based read + pre-rename re-stat + microsecond+pid timestamp) DEFERRED to v2.2 (BL-235)**. Layer 5 wording below preserved as audit trail: ~~integrity-bound marker file for the greenfield first-run heuristic. `/lp-brainstorm` writes it at session start ONLY when `greenfield: true` (per §7) with full `{schema_version, generated_at, brainstorm_session_id, generated_by, bound_cwd, sha256}` JSON envelope under `.first-run-marker.lock` (DEDICATED lock — Layer 5 P1-1 split from nonce ledger lock); `/lp-scaffold-stack` requires it to exist + be unconsumed + integrity-valid + bound_cwd-matched + session_id-matched for the empty-ledger-allowed first-run path; consumed via FD-based read with pre-rename re-stat to close path-vs-inode TOCTOU; renamed to `.first-run-marker.consumed.<iso-microsec-ts>.<pid>` (microsecond + pid suffix to close collision) after successful first scaffold-stack run.~~                                                                                                                                                                                                                                                                                                                    |
| `.launchpad/.first-run-marker.lock`                                      | **DEFERRED to v2.2 per §1.5 strip-back (BL-235)**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Lock sentinel    | **NEW (Layer 5 security-auditor P1-1 + frontend-races P1-L5-A)** — does NOT ship at v2.0; the simple positive-presence marker has no lock contention. Audit-trail: dedicated `flock` sentinel for `.first-run-marker` write/consume — split from `.scaffold-nonces.lock` to eliminate DoS coupling where a slow `/lp-brainstorm` would block every concurrent nonce-append. Opened with `O_CREAT                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | O_RDWR, 0o600`, never renamed/unlinked. 10s LOCK_NB acquisition timeout                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `.harness/observations/security-events.jsonl`                            | **DEFERRED to v2.2 per §1.5 strip-back (BL-220 + BL-223)** — does NOT exist at v2.0                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Audit log        | Audit-trail: append-only JSONL of always-written security events per HANDSHAKE §3 "Security event log spec" — `prev_entry_sha256` chain, 0o600, separate `.security-events.lock`, fsync+F_FULLFSYNC, schema_version 1.0. v2.0 closed event enum + write protocol DEFERRED                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `.harness/observations/.security-events.lock`                            | **DEFERRED to v2.2 per §1.5 strip-back (BL-223)**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Lock sentinel    | Audit-trail: dedicated `flock` sentinel for `security-events.jsonl` writes — separate from telemetry/restamp/recovery locks to avoid DoS coupling                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `docs/maintainer/rollback-runbook.md`                                    | **DEFERRED to v2.2 per §1.5 strip-back (BL-229)** — v2.0 ships compressed §7.1 inline only                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Runbook          | Audit-trail: full 6-step compressed-rollback procedure; §7.0 `vX.Y.Z-recalled` rename detailed walkthrough; §7.2 un-yank walkthrough; severity decision tree; 24h post-tag observation window monitored signals; paper rollback drill protocol                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `docs/runbooks/branch-protection-token.md`                               | **DEFERRED to v2.2 per §1.5 strip-back (BL-229 + BL-234)** — v2.0 ships 1-paragraph PAT setup note in `docs/releases/v2.0.0.md`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Runbook          | Audit-trail: PAT lifecycle for `BRANCH_PROTECTION_READ_TOKEN`. Required H2 sections: Purpose, Threat Model, Rotation Cadence (90-day max), Secret Update Procedure, Fail-Closed Contract, Compromise Detection, Revocation Procedure, Recovery from Expired-Mid-PR                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `verify-v2-ship` CI job (lives in `.github/workflows/v2-release.yml`)    | **v2.0 ships SIMPLIFIED 4-check version per §1.5 strip-back** — tag SHA matches squash-merge HEAD; plugin.json version matches tag; no `0.x-test` residual; no leakage regex. The 8-check Layer 5 battery DEFERRED to v2.2 (BL-226 tag-protection content; BL-227 pre-existing recall-tag 404; BL-232 exponential-backoff polling + `${{ github.run_id }}` self-loop break — note: the Layer 5 JQ filter `databaseId != ${{ github.run_id }}` is semantically wrong — `run_id` is workflow-run-id namespace, not check-run-id — v2.2 BL-232 fixes via `name != "verify-v2-ship"` filter). Layer 5 wording below preserved as audit trail | CI               | **Layer 3 simplicity P1-G + architecture P2-6 + Layer 4 deployment N5 + Layer 5 deployment P2-D1 + frontend-races P2-L5-A2 + adversarial P1-A1 + security P3-3**: post-tag verification battery folded into the release CI workflow as a job. **Trigger**: `on: push: tags: ['v[0-9]+.[0-9]+.[0-9]+']` (regex excludes `*-yanked`/`*-recalled`/`*-rc*`/`*-dryrun`); job-level guard `if: !endsWith(github.ref, '-yanked') && !endsWith(github.ref, '-recalled')`. **8 checks** (Layer 5 deployment P2-L5-1 split prior compound check #7 into independent #7 + #8 for clarity; GPG remains deferred per BL-214; ALL checks include explicit non-empty assertions per Layer 5 deployment P2-D1 — vacuous-truth on empty API response is a fail-loud condition, NOT a silent pass): (1) tag SHA matches squash-merge HEAD; (2) marketplace.json schema-valid + points-at-this-repo (NOT version-pinned per PR #38 reconciliation); (3) plugin.json version matches tag; (4) no `0.x-test` residual in plugin-shipped tree (per §10 user-tree carve-out); (5) no private-origin-leakage regex match (pattern loaded from `.launchpad/secret-patterns.txt` per existing v1.x convention — gitignored config so the patterns themselves don't ship in plugin tree; pattern set covers private-project-name allowlist + `ported\s+from` + `originated\s+(at                                                                                                                                                                                                                               | in                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | from)`style markers; tightened per Layer 3 adversarial P3-RT-9 + Layer 9 strip private names from public artifacts); (6) CI green on tagged SHA — uses`${{ github.run_id }}`self-exclusion (Layer 5 security P3-3 + frontend-races P2-L5-A2:`gh api .../check-runs --jq ".check_runs \| map(select(.databaseId != ${{ github.run_id }}))"`for rename-immune self-loop break, with explicit non-empty assertion`length >= 1 \|\| fail "no check-runs found (propagation race?)"`; precedes the predicate by **60-90s exponential-backoff polling loop** to handle GitHub check-runs API ≤120s eventual consistency between squash-merge and tag-emission); (7) automated reviews green/waivered (separate `gh api .../reviews`query with non-empty assertion); (8) **GitHub tag protection rule exists AND has correct content** via`gh api repos/:owner/:repo/tags/protection`(Layer 3 deployment P1-B + Layer 5 security P2-S3: probe-then-fallback to`repos/:owner/:repo/rulesets`; asserts pattern matches broadened `v[0-9]+.[0-9]+.[0-9]+(-(yanked | recalled | rc[0-9]+ | dryrun))?`regex AND`allow_deletions: false`AND no force-push exceptions; explicit empty-rejection identical to OPERATIONS §2`branch_protection_unreadable`reason). **Pre-existing recall-tag check** (Layer 5 adversarial P1-A1, NEW gate, must run BEFORE checks 1-8):`gh api repos/:owner/:repo/git/refs/tags/v${VERSION}-recalled`MUST return 404 at tag-emission time. If a`vX.Y.Z-recalled`tag pre-exists pointing at a non-current SHA, hard-reject with`reason: "recall_tag_squat_attempt"`and emit`write_security_event(...)` — closes namespace-squatting attack where a hostile contributor pre-creates the recall tag. Failure → OPERATIONS §7 rollback procedure |
| `pytest.ini` (or `[tool.pytest.ini_options]` in `pyproject.toml`)        | Joint deliverable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Tooling          | `python_files = test_*.py` + `testpaths = plugins/launchpad/scripts/tests` to make pytest discovery deterministic                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `.github/workflows/v2-handshake-lint.yml`                                | Joint deliverable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | CI               | CI workflow per OPERATIONS §2; `pull_request` event with `permissions: read-all`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `.github/workflows/v2-handshake-lint-static.yml`                         | **DEFERRED to v2.2 per §1.5 strip-back (BL-230)** — v2.0 single-maintainer reads fork PRs manually                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | CI               | Audit-trail: `pull_request_target` event running ONLY the static lint against the merge-base diff (no fork-PR checkout)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `.github/workflows/v2-branch-staleness-check.yml`                        | **DEFERRED to v2.2 per §1.5 strip-back (BL-230)** — v2.0 ships manual monthly merge audit                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | CI               | Audit-trail: scheduled daily; runs `git log feat/v2-greenfield-pipeline..main --since=7.days.ago` against handshake-touched paths; opens GitHub issue `v2-merge-overdue`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `.github/workflows/branch-protection-watchdog.yml`                       | **DEFERRED to v2.2 per §1.5 strip-back (BL-230)** — v2.0 ships PR-required-check only                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | CI               | Audit-trail: nightly branch-protection assertion per OPERATIONS §2                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `.github/CODEOWNERS` (entries)                                           | Joint deliverable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Governance       | Approver gates per OPERATIONS §2                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

### Adapter contract widening

Phase 0.5 adds **6 new** `/lp-define` adapter modules under `plugins/launchpad/scripts/plugin_stack_adapters/` (Layer 3 catalog cut: was 10 in Layer 2 spec; reduced to 6 — astro, fastapi, rails, hugo, eleventy, expo — matching the 10-stack catalog minus `next` (already covered by ts_monorepo), `hono` (covered by ts_monorepo), `django` (covered by python_django), `supabase` (covered by generic adapter)). The same commit MUST widen `contracts.py:StackId` Literal:

```python
# Before (matches plugin_stack_adapters/contracts.py:17 verbatim — polyglot is the
# composer module, not a stack ID):
StackId = Literal["ts_monorepo", "python_django", "go_cli", "generic"]

# After (v2.0; Layer 3 catalog cut): underscore-naming convention preserved.
# Cut from Layer 2 list of 14: sveltekit, phoenix_liveview, convex, flutter
# (4 stacks deferred to v2.1 per BL-212; keeps frontend, content, app, mobile pillars).
StackId = Literal[
    "ts_monorepo", "python_django", "go_cli", "generic",
    "astro", "fastapi", "rails", "hugo",
    "eleventy", "expo",
]
```

Without the widen, every new adapter fails type-check on `AdapterOutput.stack_id` at module load.

### Vendored YAML preamble

All new modules using `yaml` MUST follow the existing vendor-bootstrap preamble (see `plugin-config-hash.py:30-35`):

```python
SCRIPT_DIR = Path(__file__).resolve().parent
VENDOR = SCRIPT_DIR / "plugin_stack_adapters" / "_vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

import yaml  # noqa: E402  (vendored)
```

Tests for each module live in `plugins/launchpad/scripts/tests/`. Test discovery via `pytest` from repo root.

## 13. References

- `plugins/launchpad/scripts/plugin-config-hash.py` — canonicalization scheme migrated to JSON in §3 backport
- `plugins/launchpad/scripts/plugin_stack_adapters/contracts.py` — `StackId` Literal widened in §12
- `plugins/launchpad/scripts/plugin-stack-detector.py` — shares `BROWNFIELD_MANIFESTS` per §8
- `plugins/launchpad/scripts/plugin-config-loader.py` — `ConfigError` pattern mirrored by `PathValidationError` in §6
- `docs/architecture/SCAFFOLD_OPERATIONS.md` — companion doc covering subprocess invocation, governance, drift, freshness, telemetry, panels, gates, amendments
- Joint hardening report (memory): `~/.claude/projects/.../memory/project_v2_0_joint_hardening_p1_blockers.md`
- Path C state (memory): `~/.claude/projects/.../memory/project_v2_0_path_c_state.md`
- v2.2 deferred stacks: [`ROADMAP.md` v2.2 section](../../ROADMAP.md#v22)

## 14. Bootstrap manifest contract (v2.1 Phase 3)

`/lp-bootstrap` (v2.1) materializes the 30-path infrastructure overlay
into a project root and writes `.launchpad/bootstrap-manifest.json` as
the audit trail that makes idempotency, refresh, and tampering detection
possible. This section pins the contract that every consumer of the
manifest, including Phase 4 adapters and Phase 10 `/lp-update-identity`,
must honor.

### 14.1 Envelope (schema 1.0)

```json
{
  "manifest_schema_version": "1.0",
  "plugin_version": "<semver from plugin.json>",
  "last_render_timestamp": "<UTC ISO-8601, second precision, Z suffix>",
  "files": [
    {
      "path": "<POSIX-relative-to-project-root>",
      "source_template_sha256": "<hex>",
      "rendered_content_sha256": "<hex>",
      "policy": "overwrite-if-unchanged | merge-keys | append-only",
      "mode": 420
    }
  ],
  "security_fields": []
}
```

Fields:

- `manifest_schema_version` is the v2.1 reader indicator. The Phase 1 canonical reader (`plugin-config-loader.read_bootstrap_manifest`) routes via the 4-rule ladder: missing or `1.0` -> full read, `1.x where x > 0` -> forward-compat with INFO on unknown fields, major >= 2 -> fail-closed.
- `plugin_version` matches `plugins/launchpad/.claude-plugin/plugin.json` `version` at render time. The engine's plugin-version pin check (Phase 3 §3.4) compares the running plugin's version against this field; mismatches abort with `plugin_version_mismatch` unless `--accept-plugin-version-drift` is passed.
- `last_render_timestamp` round-trips through git diffs as a human-readable signal of when the manifest was last rebuilt.
- `files[]` is a stable-sorted list of per-target entries. The path inventory MUST equal `lp_bootstrap.INFRASTRUCTURE_TARGETS`; missing entries trigger `manifest_tampered`.
- `mode` is stored as an integer (octal-style, e.g. `420` for `0o644`) so JSON round-trips cleanly.
- `security_fields` is reserved for forward-compat security extensions in v2.2 (e.g., signed-template attestations). The v2.1 reader treats a non-empty `security_fields` as `unsupported_security_extension` abort, pre-empting the v2.2 signature-field downgrade attack at zero v2.1 cost (harden B9).

Adding a new infrastructure file is additive (a new entry in `files[]` plus extending `INFRASTRUCTURE_FILES`); no `manifest_schema_version` bump. Removing or renaming an entry IS a schema change (bumps to 1.1 + canonical reader migration rule per the §10 ladder).

### 14.2 Per-file conflict policies

v2.1 ships three active policies plus one `--refresh`-mode variant. The two policies named in the original V3 contract (`skip-if-exists`, `overwrite-always`) are NOT shipped in v2.1; they defer to Phase 4 if an adapter overlay demands them, else to v2.2.

| Policy                   | Behavior                                                                                                                                                                                                                                                                                          | Used by                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `overwrite-if-unchanged` | Compare on-disk sha to manifest's `rendered_content_sha256`. Match -> write new content. Mismatch -> skip with `kept-user-edits` action message.                                                                                                                                                  | 26 of 30 paths                                                       |
| `merge-keys`             | YAML / JSON / CODEOWNERS only. Plugin can ADD top-level keys; CANNOT delete user keys. Conflict on duplicate-key value-type -> user wins, structured warning to `bootstrap-warnings.json`. Within an existing user-defined list, plugin appends new items but never deletes user-defined entries. | `lefthook.yml`, `scripts/compound/config.json`, `.github/CODEOWNERS` |
| `append-only`            | Read existing content; append plugin-required entries that aren't already present. NEVER reorders, deduplicates, or removes user entries. Symlink target rejected fail-closed.                                                                                                                    | `.gitignore`                                                         |
| `overwrite-with-backup`  | Reserved for `--refresh` and `--refresh-all`. Writes pre-edit content to `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>` before atomic-write. Backup contents must be byte-equal pre-edit; symlink rejected.                                                                                    | (refresh-only)                                                       |

### 14.3 Tampering check

The engine performs two distinct integrity validations on every run:

- **(a) Plugin-shipped template integrity** (mandatory): compares each manifest entry's `source_template_sha256` against a module-load cached map of plugin-shipped `.j2` shas. Mismatch -> `manifest_tampered` abort with structured remediation pointing at `--accept-plugin-version-drift` or manifest deletion.
- **(b) On-disk content fidelity** (advisory): recompute the on-disk sha against `rendered_content_sha256`. The manifest's `rendered_content_sha256` is updated at the END of every successful `/lp-bootstrap` run; partial-failure runs do NOT write the manifest, preserving the prior shas for the next attempt (harden B16).

`manifest_corrupt` (malformed JSON / wrong envelope shape) is distinct from `manifest_tampered` (sha mismatch). Both abort the run, but the remediation differs: `manifest_corrupt` is "delete and rebuild"; `manifest_tampered` is "accept plugin-version drift OR delete + rebuild".

### 14.4 Plugin-version pin + `--accept-plugin-version-drift`

`/lp-bootstrap` aborts when the recorded `plugin_version` in `scaffold-decision.json` does not match the running plugin's `plugin.json` version. Override path: `/lp-bootstrap --accept-plugin-version-drift` accepts the drift, records a `(from_version, to_version, accepted_at)` tuple in scaffold-decision's `version_drift_log[]` array, auto-triggers `--refresh-all` so manifest shas align with the new plugin's templates, and preserves the originally sealed `plugin_version` field (overwrite would erase the audit trail).

The original "re-run /lp-pick-stack" remediation is REMOVED; sealed identity precludes that path.

### 14.5 `--refresh` semantics

- `--refresh <path>` accepts ONE OR MORE infrastructure paths from the `lp_bootstrap.INFRASTRUCTURE_TARGETS` set (repeatable flag). Path validation rejects `..`, absolute paths, and off-inventory entries via `path_traversal_rejected` and `unknown_refresh_path` codes.
- Kernel paths (LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, README.md, etc.) are NOT accepted; kernel refresh goes through `KernelRenderer.refresh()` directly via `/lp-update-identity` (Day 1 decision D2).
- `--refresh-all` re-renders every infrastructure path with `overwrite-with-backup`. If no manifest exists, silently degrades to full bootstrap with INFO `no_manifest_to_refresh`.
- `--refresh-paths` comma-separated form is v2.2 backlog; glob support in `--refresh <path>` is v2.2 backlog.

### 14.6 What the manifest does and does not prove

- PROVES: on-disk files match what was rendered. `rendered_content_sha256` is recomputed at the END of every `/lp-bootstrap` run and compared against pre-write content via the per-file policy applicator.
- DOES NOT PROVE: the rendering plugin was authentic. v2.1 trusts the plugin-shipped template bytes; v2.2-backlog `gh attestation verify` work would close that surface.
- DOES NOT PROVE: the templates rendered were the templates the user expected. A `/plugin update` between bootstraps changes the `source_template_sha256` for every entry; the manifest catches this via `manifest_tampered` only when the next bootstrap runs (the user must explicitly accept via `--accept-plugin-version-drift`).

Cross-references: §4 (envelope contract), §10 (atomic writes), Phase 3 implementation plan sections 3.1, 3.2, 3.5, 3.7, 3.8, 6.1, 6.2.

---

## 15. v2.1 adapter Protocol + composition pair-table + template cache (Phase 4)

### 15.1 Adapter Protocol contract

Every v2.1 active stack id resolves to an `Adapter` Protocol implementation
under `plugins/launchpad/scripts/plugin_stack_adapters/<stack>.py`. The
Protocol is runtime-checkable (via `typing.runtime_checkable`) and coexists
with the existing `AdapterOutput` TypedDict family from
`contracts.py`: TypedDicts model adapter _data_ output (consumed by the
Jinja2 generator); the Protocol models adapter _behavior_ (consumed by the
v2.1 dispatch helper at `lp_scaffold_stack/v21_adapter_dispatch.py` and by
the composition wrapper).

```python
@runtime_checkable
class Adapter(Protocol):
    stack_id: StackIdActive
    upstream: UpstreamTemplate | None
    manifest_schema_version: str
    workspace_name: str | None
    unwrap_strategy: Literal["none", "nested_turborepo"]
    composes_with: dict[StackIdActive, CompositionRule]

    def scaffold_into(self, tempdir: Path) -> None: ...
    def apply_overlay(self, tempdir: Path) -> None: ...
```

Closed-enum `StackIdActive` covers the 5 v2.1 stack ids: `ts_monorepo`,
`nextjs_standalone`, `nextjs_fastapi`, `astro`, `generic`. Detector
encounters of v2.2-candidate stack ids (rails, python_django,
python_generic, nextjs_hono_cloudflare, nextjs_trpc_prisma) route to
`generic` with the verbatim INFO log per Phase 4 §3.12.

### 15.2 Composition pair-table-from-data

The composition wrapper (`plugin_stack_adapters/composition.py`) computes
the pair table at runtime from each adapter's `composes_with: dict[...]`
declaration. Adding a v2.2 adapter only requires adding entries to its own
`composes_with`; `composition.py` does NOT change. The 10 C(5,2) pairs
collapse to 6 substantive rows + 4 ts_monorepo+\* rejections + 2
duplicate-rejection rules outside C(5,2).

| Row                                  | Combined workspaces                            | Notes                               |
| ------------------------------------ | ---------------------------------------------- | ----------------------------------- |
| `ts_monorepo + *`                    | REJECT                                         | catch-all collapsing 4 C(5,2) pairs |
| `nextjs_standalone + astro`          | `app/` + `content/`                            | canonical hot-path #1               |
| `nextjs_standalone + nextjs_fastapi` | `app-fe/` + `api/` (collision suffix on `app`) | canonical hot-path #2               |
| `nextjs_standalone + generic`        | `app/` + `extra/`                              |                                     |
| `nextjs_fastapi + astro`             | `app/` + `api/` + `content/`                   | 3-workspace single composition      |
| `nextjs_fastapi + generic`           | `app/` + `api/` + `extra/`                     |                                     |
| `astro + generic`                    | `content/` + `extra/`                          |                                     |
| `astro + astro`                      | REJECT                                         | duplicate (outside C(5,2))          |
| `generic + generic`                  | REJECT                                         | duplicate (outside C(5,2))          |

### 15.3 Per-adapter `unwrap_strategy`

Each adapter declares `unwrap_strategy: Literal["none", "nested_turborepo"]`.
At v2.1 only `nextjs_standalone` declares `nested_turborepo` (next-forge
IS a Turborepo). The composition wrapper handles the unwrap algorithm:

1. Render root `package.json` + `turbo.json` + `pnpm-workspace.yaml` first.
2. Adapter `scaffold_into` materializes upstream into a tempdir.
3. Detect upstream Turborepo via `<tempdir>/turbo.json` AND
   `<tempdir>/pnpm-workspace.yaml` (dual signal).
4. Hoist `<tempdir>/apps/*` and `<tempdir>/packages/*` into composition root.
5. WARN on any unknown top-level directory.
6. DROP `<tempdir>/{package.json,turbo.json,pnpm-workspace.yaml}`.
7. Apply `OverlayConfig.replace`/`remove`/`add`.
8. Atomic `os.replace` of populated `apps/*` workspace dirs into final tree.

### 15.4 Template cache contract

`plugins/launchpad/scripts/template_cache/` is the SHA-pinned upstream tree
storage. Public API: `fetch(repo_url, sha) -> Path` and
`verify(repo_url, sha) -> bool`. Adapters call `template_cache.fetch` from
`scaffold_into`; the production fetcher is a depth-1 git clone via
`safe_run.safe_run_long`.

10 cache rules govern integrity (see Phase 4 plan §3.7 for the per-rule
test mapping):

1. SHA-pinned cache key (the SHA already comes pre-resolved from
   `pin_registry.py`).
2. Cache-hit verification via `.ready` sentinel + commit-object sha
   verify (~5ms, <20ms perf budget).
3. Atomic writes: tempdir then rename; `.ready` sentinel is the durable
   commit point. No per-file fsync; cold-fill 1k files <3s budget.
4. Per-entry `fcntl.flock` at `.locks/<slug>-<sha>.lock` (mode 0o600);
   `MAX_CONCURRENT_FETCHES=3` semaphore.
5. Validation-before-flock ordering (Phase 3 §3.11.5(c) inheritance).
6. 500MB LRU + lazy on-fetch eviction.
7. 90-day TTL re-validation; tag-replay defense in nightly tag-drift
   detector workflow.
8. Auto-purge on missing/extra files OR missing `.ready` OR
   `.compromised` sentinel.
9. Symlink rejection at root + per-entry.
10. Filesystem-full cleanup via try/finally on `<sha>.tmp.<uuid>/`.

### 15.5 Pin registry as single source of truth

`plugin_stack_adapters/pin_registry.py` is the CODEOWNERS-protected single
source of truth for upstream commit SHAs. Per-adapter SHA constants are
forbidden (`tests/test_no_floating_tag_pins.py` greps for the 40-char hex
regex and verifies dual-resolution evidence in
`docs/maintainers/upstream-pin-rotations.md`). Every modification of a
`sha` value requires a same-commit append-only audit-log entry; the
rotation-detector lint rule in `plugin-v2-handshake-lint.py` enforces.

---

**Status**: This document is the binding contract layer for v2.0 implementation as of 2026-04-30, extended by §14 for v2.1 Phase 3. The companion `SCAFFOLD_OPERATIONS.md` covers the operations layer. Both v2.0 plans reduce to references against these documents. Plan Hardening Notes appendices must not contradict them; if they do, these documents win.
