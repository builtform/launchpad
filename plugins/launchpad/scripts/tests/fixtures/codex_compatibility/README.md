# Codex compatibility fixtures

This fixture records the disposable host-conformance probes used by Section 1 of
the Codex compatibility plan. It is test-only material. It is not a LaunchPad
release manifest, runtime router, support matrix, or production resolver.

The probe never installs into the user's normal Codex state. Give it a dedicated
temporary `CODEX_HOME`:

```bash
probe_home="$(mktemp -d /private/tmp/lp-codex-section1.XXXXXX)"
python run_conformance.py --codex-home "$probe_home"
```

The runner performs local lifecycle, installed-root, manifest, schema, and
Claude metadata checks. It cleans up the temporary marketplace and plugin when
possible. It does not invoke a model, write to the repository, or touch
`~/.agents`, `~/.codex`, or `~/.claude`.

The local `_sections` plan is the only authoritative Section 1 capability
record. The runner's JSON output is disposable test evidence, not a support
matrix or a second status ledger.

Every public command example in these fixtures uses bare `$lp`. Any internally
qualified component label observed during installation is diagnostic evidence
only and is never treated as public syntax.

## Section 6 router smoke

`run_router_smoke.py` projects the exact Section 6 runtime set into a temporary
local marketplace, installs it with isolated Codex state, confirms that Codex
advertises exactly one internally qualified packaged `lp` component, and
removes the plugin and marketplace registration. The internal component label
is diagnostic evidence, not public command syntax.

The runner also verifies the bare `$lp` CLI prompt shape, the app-server typed
skill-input fields, and the host's plugin-hook capability status. It records
missing authenticated binding as `BLOCKED`. It does not invoke a model or claim
that bare `$lp` has authenticated argument routing.

```bash
smoke_home="$(mktemp -d /private/tmp/lp-codex-section6.XXXXXX)"
python run_router_smoke.py --codex-home "$smoke_home"
```

## Section 7 fake-host coordinator

`fake_host_coordinator.py` freezes the typed coordinator endpoint and trace
contracts through an injected fake host. It covers execution snapshots,
capability preflight, project-prompt admission, authenticated approvals,
operation permits, receipt reservation and durable sync, mutation leases,
exact serialized egress scanning, bounded redacted logs, evidence expiry and
revocation, partial outcomes, and terminal states.

The fixture cannot start a model, spawn a process, write a product file, or
open a network connection. Production `plugin-codex-runtime.py` remains absent
because the real host boundary is still blocked. Real-host effectful paths
therefore continue to fail closed while Sections 7 and 8 use injected
capabilities for deterministic testing.

## Section 8 bounded scheduler and harden-plan slice

`fake_host_harden_plan.py` composes only the frozen Section 7 coordinator
endpoints. It loads the canonical harden-plan command and agent prompts by
exact digest, reads an injected `.launchpad/agents.yml` snapshot, applies the
canonical stack filter and banners, reserves the complete run budget, and
executes deterministic code and document waves through an in-memory event
loop.

The fixture covers bounded workers, queueing, fan-in, retries, wave barriers,
fresh minimal child contexts, strict child-result schemas, estimated versus
authoritative accounting, cancellation, task-tree termination, final join,
late-result rejection, deterministic finding synthesis, and one controlled
artifact proposal. The initial approval cannot authorize a product write. A
second authenticated approval must narrow the approved closure to the product
path and bind the exact escaped diff before the fake mutation can occur.

This remains a test-only conformance slice. It cannot dispatch a real child or
write the returned artifact bytes to disk, Codex `--auto` remains blocked, and
the absent production coordinator keeps every real-host effectful route
fail-closed.
