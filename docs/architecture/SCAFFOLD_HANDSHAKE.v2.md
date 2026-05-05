# SCAFFOLD_HANDSHAKE.v2 (Phase 4 v2.1 §15 sibling — NOT yet folded)

> **Folding policy.** This V2 sibling carries the Phase 4 §15 addition
> (Adapter Protocol + composition pair-table-from-data + cache rules)
> destined for `SCAFFOLD_HANDSHAKE.md`. Folding is deferred to Phase 9 per
> the v2.1 Phase 4 plan §2.3 + §8 (DEFERRED to Phase 9). Until then,
> readers consult both the canonical doc (sections 1–14) and this sibling
> (section 15).

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
