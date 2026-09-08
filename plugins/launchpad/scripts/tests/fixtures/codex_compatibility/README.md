# Codex compatibility Section 1 fixture

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
