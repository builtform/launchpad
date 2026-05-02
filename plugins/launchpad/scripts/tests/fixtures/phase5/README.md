# Phase 5 fixture pattern — runtime-generated decisions

Per Phase 5 handoff §4.2: Phase 5 smoke tests do **NOT** check static
decision JSON files into this directory. Instead, each test calls
`_phase5_decision_builder.build_decision()` at runtime to produce a
fresh sealed payload with:

- a fresh `nonce` (UUIDv4 hex, 32 chars)
- a fresh `generated_at` (ISO 8601 UTC sec, "now")
- a `bound_cwd` triple (realpath + st_dev + st_ino) bound to the
  per-test temp dir
- a `sha256` envelope computed via `decision_integrity.canonical_hash`
  over the rest of the payload

This dir exists so the test harness can drop transient artifacts
(per-test rejection logs, intermediate scaffold receipts) when manually
inspecting failures, but the dir itself stays empty in version control
beyond this README. Static fixture files would invalidate every test
the moment the 4-hour `generated_at` window expires.

The runtime-generation pattern is also why Phase 5 uses
`@pytest.fixture(scope="session")` for the adversarial corpus baseline —
the baseline is built ONCE per pytest session and cloned-then-mutated
per mutation test (per handoff §4.7 line 411).

See `plugins/launchpad/scripts/tests/_phase5_decision_builder.py` for
the public API and `plugins/launchpad/scripts/tests/scaffold_smoke_runner.py`
for the per-test usage pattern.
