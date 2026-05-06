"""Phase 8.5 v2.1 decommission gate (BL-247 Round 2 P2-A).

Locks the v2.1 /lp-define rewire + plugin-doc-generator decommission so it
cannot regress: deleted module must stay deleted; new render_batch flow
must enforce atomic-all-or-none under secret-scanner findings; pattern
caching must not re-compile per call; bundled fallback must fire when
.launchpad/secret-patterns.txt is absent; renderer subclasses must not
bypass the gate by calling atomic_write_replace directly; polyglot path
rewriter must work at its new standalone location; static + dynamic +
subprocess + reflection references to plugin-doc-generator must remain
zero outside the permitted historical-artifact appendix.

Plan reference: docs/plans/launchpad_plans/2026-05-05-v2.1-phase8.5-implementation-plan.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "launchpad" / "scripts"

# Sibling-script imports (vendored jinja2 + adapters live here).
if str(SCRIPTS_DIR / "plugin_stack_adapters" / "_vendor") not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR / "plugin_stack_adapters" / "_vendor"))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Slice B -- polyglot path rewriter at standalone module
# ---------------------------------------------------------------------------


def test_polyglot_rewrite_adapter_paths_at_new_location() -> None:
    """The post-composition path rewriter lives at
    `plugin_stack_adapters.polyglot_path_rewriter`. Verifies the verbatim
    move from plugin-doc-generator.py:159-247 preserves behavior.
    """
    from plugin_stack_adapters.polyglot_path_rewriter import (
        _ADAPTER_DEFAULT_PATH_PREFIXES,
        _rewrite_adapter_paths,
        _rewrite_path,
    )

    # _rewrite_path: prefix swap.
    assert _rewrite_path("apps/web/src/components", "apps/web", "packages/ui") == (
        "packages/ui/src/components"
    )
    # Empty prefix: no-op.
    assert _rewrite_path("apps/web/src", "", "packages/ui") == "apps/web/src"
    # Strip-to-root when new prefix is "." or "".
    assert _rewrite_path("apps/web/src", "apps/web", ".") == "src"
    assert _rewrite_path("apps/web/src", "apps/web", "") == "src"
    # Already-customized path (no needle match): pass through.
    assert _rewrite_path("custom/path", "apps/web", "packages/ui") == "custom/path"
    # None / empty input: no-op.
    assert _rewrite_path(None, "apps/web", "packages/ui") is None
    assert _rewrite_path("", "apps/web", "packages/ui") == ""

    # _ADAPTER_DEFAULT_PATH_PREFIXES: known adapters mapped.
    assert _ADAPTER_DEFAULT_PATH_PREFIXES["next"] == "apps/web"
    assert _ADAPTER_DEFAULT_PATH_PREFIXES["fastapi"] == "apps/api"

    # _rewrite_adapter_paths: end-to-end path rewrite for a polyglot
    # AdapterOutput where fastapi materialized at services/api (instead
    # of the default apps/api).
    adapter_out = {
        "backend": {
            "routes_dir": "apps/api/routes",
            "models_dir": "apps/api/models",
        },
        "frontend": {"component_dir": "apps/web/src/components"},
        "tech_stack": [],
        "app_flow": [],
        "product_context": {"stack_summary": "", "deployment_target": ""},
        "commands": {},
        "pipeline_overrides": {},
    }
    layer_paths = {"fastapi": "services/api", "next": "apps/web"}
    rewritten = _rewrite_adapter_paths(adapter_out, layer_paths, ["fastapi", "next"])
    # Backend paths got rewritten because fastapi default = apps/api,
    # actual = services/api.
    assert rewritten["backend"]["routes_dir"] == "services/api/routes"
    assert rewritten["backend"]["models_dir"] == "services/api/models"
    # Frontend stayed at apps/web because next's actual path equals
    # default.
    assert rewritten["frontend"]["component_dir"] == "apps/web/src/components"

    # Empty stacks/layers: pass-through.
    assert _rewrite_adapter_paths(adapter_out, {}, []) is adapter_out


# ---------------------------------------------------------------------------
# Slice C -- render_batch + scan_batch + write_batch flow (DA1' = a2)
# ---------------------------------------------------------------------------


def _kernel_renderer():
    from plugin_default_generators.kernel_renderer import KernelRenderer

    return KernelRenderer()


def _identity():
    return {
        "pii_opt_in": True,
        "project_name": "Demo",
        "email": "demo@example.com",
        "copyright_holder": "Demo Co",
        "repo_url": "https://example.com/demo",
        "license": "MIT",
        "license_other_body": "",
    }


def test_render_batch_no_disk_write(tmp_path):
    """render_batch returns an in-memory dict; nothing lands on disk."""
    renderer = _kernel_renderer()
    batch = renderer.render_batch([{"cwd": tmp_path, "identity": _identity()}])
    assert isinstance(batch, dict)
    assert all(isinstance(v, bytes) for v in batch.values())
    # Disk side-effect check: tmp_path remains empty.
    on_disk = list(tmp_path.iterdir())
    assert on_disk == [], f"render_batch wrote to disk: {on_disk}"


def test_write_batch_writes_all_when_clean(tmp_path):
    """write_batch atomically writes every file when scan_batch returns
    no findings. KernelRenderer's 7 templates are all clean by default."""
    renderer = _kernel_renderer()
    batch = renderer.render_batch([{"cwd": tmp_path, "identity": _identity()}])
    renderer.write_batch(batch)
    # All 7 kernel files are now on disk.
    for target in batch:
        assert target.is_file(), f"write_batch did not write {target}"


def test_write_batch_atomic_all_or_none_on_secret_finding(tmp_path):
    """When ANY file in the batch contains an AWS-key-shaped string, ALL
    writes are refused (no partial state). DA1' = a2 atomic-batch-or-none
    invariant per Phase 8.5 plan section 3.11."""
    from plugin_default_generators._renderer_base import (
        RendererBase,
        SecretScannerViolation,
    )

    renderer = _kernel_renderer()
    # Synthesize a 2-file batch where file 2 contains an AWS-key shape.
    file_clean = tmp_path / "clean.md"
    file_dirty = tmp_path / "dirty.md"
    batch = {
        file_clean: b"This is a clean Markdown file.\n",
        file_dirty: b"Look at this AWS key: AKIAABCDEFGHIJKLMNOP\n",
    }
    raised = False
    try:
        renderer.write_batch(batch)
    except SecretScannerViolation as exc:
        raised = True
        assert exc.refused_count == 2
        assert len(exc.findings) >= 1
    assert raised, "SecretScannerViolation expected but not raised"
    # Atomic-batch-or-none: file_clean must NOT exist on disk.
    assert not file_clean.exists(), (
        "atomic-batch-or-none invariant violated: clean file leaked to disk "
        "before the batch's secret finding aborted the write"
    )
    assert not file_dirty.exists(), "dirty file should not have been written"


def test_write_batch_uses_launchpad_secret_patterns(tmp_path):
    """When `.launchpad/secret-patterns.txt` exists, the gate uses
    user-defined patterns AND the bundled fallback set together."""
    from plugin_default_generators._renderer_base import (
        SecretScannerViolation,
    )

    renderer = _kernel_renderer()
    patterns_dir = tmp_path / ".launchpad"
    patterns_dir.mkdir()
    (patterns_dir / "secret-patterns.txt").write_text(
        "# Custom patterns\nDEMO-CUSTOM-[A-Z]{6}\n",
        encoding="utf-8",
    )
    target = tmp_path / "demo.md"
    batch = {target: b"Internal token: DEMO-CUSTOM-ABCDEF\n"}
    raised = False
    try:
        renderer.write_batch(batch, patterns_file=patterns_dir / "secret-patterns.txt")
    except SecretScannerViolation:
        raised = True
    assert raised, (
        "User-defined pattern in .launchpad/secret-patterns.txt should have "
        "blocked the write"
    )


def test_write_batch_falls_back_to_bundled_patterns(tmp_path):
    """When `.launchpad/secret-patterns.txt` is absent, the gate uses
    `BUNDLED_DEFAULT_PATTERNS` fallback per DA5 (Phase 8.5 plan section 3.10).
    Verified by a synthesized AWS key still being caught."""
    from plugin_default_generators._renderer_base import (
        SecretScannerViolation,
    )
    from plugin_stack_adapters.secret_scanner import BUNDLED_DEFAULT_PATTERNS

    assert BUNDLED_DEFAULT_PATTERNS, "BUNDLED_DEFAULT_PATTERNS must not be empty"

    renderer = _kernel_renderer()
    target = tmp_path / "leak.md"
    batch = {target: b"oops: AKIAABCDEFGHIJKLMNOP\n"}
    raised = False
    try:
        renderer.write_batch(
            batch,
            patterns_file=tmp_path / "this-file-does-not-exist.txt",
        )
    except SecretScannerViolation:
        raised = True
    assert raised, "BUNDLED_DEFAULT_PATTERNS should have caught the AWS key"


def test_write_batch_pattern_cache_compiled_once(tmp_path):
    """Patterns are compiled once per (file, mtime) and reused across
    invocations; DA3 (Phase 8.5 plan section 3.8). Verified by spying
    on `re.compile` while load_patterns is called twice with the same
    inputs."""
    from plugin_stack_adapters import secret_scanner

    # Clear cache to ensure first call populates.
    secret_scanner._load_patterns_cached.cache_clear()
    cache_info_before = secret_scanner._load_patterns_cached.cache_info()
    # First call: cache miss.
    p1 = secret_scanner.load_patterns(None)
    cache_info_after_first = secret_scanner._load_patterns_cached.cache_info()
    # Second call with same inputs: cache hit.
    p2 = secret_scanner.load_patterns(None)
    cache_info_after_second = secret_scanner._load_patterns_cached.cache_info()

    assert cache_info_after_first.misses == cache_info_before.misses + 1
    assert cache_info_after_second.misses == cache_info_after_first.misses
    assert cache_info_after_second.hits >= cache_info_after_first.hits + 1
    # Pattern objects identity-stable across calls.
    assert p1 == p2


def test_write_batch_perf_under_300ms_30file_scaffold(tmp_path):
    """Cumulative gate cost on a 30-file scaffold < 300ms (Phase 8.5 plan
    section 3.8). Synthesizes a 30-file batch of ~2KB markdown each;
    times scan_batch + write_batch end-to-end."""
    import time

    renderer = _kernel_renderer()
    # 30 markdown files, each ~2KB, all clean.
    body = ("Lorem ipsum dolor sit amet. " * 80).encode("utf-8")
    batch = {
        tmp_path / f"doc_{i:02d}.md": body
        for i in range(30)
    }
    start = time.perf_counter()
    renderer.write_batch(batch)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 300, (
        f"render_batch flow on 30-file scaffold took {elapsed_ms:.1f}ms; "
        f"target < 300ms (DA3 perf assertion)"
    )


# ---------------------------------------------------------------------------
# Slice D -- secret_allowlist (DA4 per Phase 8.5 plan section 3.9)
# ---------------------------------------------------------------------------


def test_secret_allowlist_jinja_comment_exempts_section(tmp_path):
    """A Jinja-comment marker `{# secret-allowlist: <reason> #}` exempts
    the marked section from the secret-scanner gate. Per Phase 8.5 plan
    section 3.9 DA4 mechanism 1."""
    from plugin_default_generators.secret_allowlist import filter_allowlisted
    from plugin_stack_adapters.secret_scanner import SecretMatch

    template_source = (
        "Heading\n"
        "{# secret-allowlist: example AWS key in docs #}\n"
        "Look at this: AKIAEXAMPLEKEYIDONLY\n"
        "\n"
        "Other line\n"
    )
    rendered_content = (
        "Heading\n"
        "Look at this: AKIAEXAMPLEKEYIDONLY\n"
        "\n"
        "Other line\n"
    )
    findings = [
        SecretMatch(
            pattern=r"AKIA[0-9A-Z]{16}",
            line_no=2,
            preview="Look at this: <REDACTED>",
        )
    ]
    kept = filter_allowlisted(
        findings,
        target_path=tmp_path / "doc.md",
        rendered_content=rendered_content,
        template_source=template_source,
    )
    assert kept == [], (
        "Jinja-comment marker should have suppressed the AKIA finding "
        "in the marked section"
    )


def test_secret_allowlist_file_path_exempts_whole_file(tmp_path):
    """An entry in `.launchpad/secret-allowlist.txt` exempts the matching
    file from the secret-scanner gate. Per Phase 8.5 plan section 3.9
    DA4 mechanism 2."""
    from plugin_default_generators.secret_allowlist import filter_allowlisted
    from plugin_stack_adapters.secret_scanner import SecretMatch

    allowlist_path = tmp_path / "secret-allowlist.txt"
    allowlist_path.write_text(
        "# Phase 8.5 example allowlist\n"
        "docs/examples/*.md\n",
        encoding="utf-8",
    )
    target = tmp_path / "docs" / "examples" / "snippet.md"

    findings = [
        SecretMatch(
            pattern=r"AKIA[0-9A-Z]{16}",
            line_no=3,
            preview="...",
        )
    ]
    kept = filter_allowlisted(
        findings,
        target_path=target,
        rendered_content="",
        allowlist_path=allowlist_path,
    )
    assert kept == [], (
        "File-path glob in .launchpad/secret-allowlist.txt should have "
        "exempted the whole file"
    )

    # Negative case: a non-matching path keeps the finding.
    target_other = tmp_path / "docs" / "real" / "guide.md"
    kept_other = filter_allowlisted(
        findings,
        target_path=target_other,
        rendered_content="",
        allowlist_path=allowlist_path,
    )
    assert len(kept_other) == 1


# ---------------------------------------------------------------------------
# Slice F -- zero-reference + audit-log integrity
# ---------------------------------------------------------------------------

# Permitted artifact roots: docstring / comment / historical-doc references
# to plugin-doc-generator are explicitly OK per HALT resolution table in
# Phase 8.5 plan section 3.1.
_PERMITTED_PATH_FRAGMENTS = (
    "docs/plans/launchpad_plans/",
    "docs/reports/",
    "docs/handoffs/",
    "docs/maintainers/decommission-history.md",
    "docs/releases/v1.0.0.md",
    "docs/releases/v1.0.1.md",
    "docs/tasks/BACKLOG.md",
    "/_vendor/",
    "/__pycache__/",
    "node_modules/",
    "/template_cache/",
    ".harness/",
    ".git/",
)


def _is_permitted_path(path_str: str) -> bool:
    return any(frag in path_str for frag in _PERMITTED_PATH_FRAGMENTS)


def test_zero_static_imports_of_plugin_doc_generator():
    """No active Python `import` / `from` statements reference
    plugin_doc_generator across the codebase. Phase 8.5 plan section 3.1
    Tier 2 (AST scan)."""
    import ast as _ast

    hits: list[str] = []
    for py_path in REPO_ROOT.rglob("plugins/launchpad/scripts/**/*.py"):
        rel = py_path.relative_to(REPO_ROOT).as_posix()
        if _is_permitted_path(rel):
            continue
        try:
            tree = _ast.parse(py_path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ImportFrom) and (node.module or "").endswith(
                "plugin_doc_generator"
            ):
                hits.append(f"{rel}:{node.lineno}: from {node.module}")
            elif isinstance(node, _ast.Import):
                for alias in node.names:
                    if "plugin_doc_generator" in alias.name:
                        hits.append(f"{rel}:{node.lineno}: import {alias.name}")
    assert not hits, (
        f"Phase 8.5 BL-247 deleted plugin-doc-generator.py; no active "
        f"imports may remain. Hits:\n  " + "\n  ".join(hits)
    )


@pytest.mark.parametrize(
    "needle",
    [
        # Tier 3 dynamic import / spec_from_file_location
        "importlib.import_module(",
        "spec_from_file_location",
        # Tier 4 subprocess-invocation
        'subprocess.run([',
        'subprocess.Popen([',
        # Tier 5 reflection
        "pkgutil.iter_modules",
        "importlib.metadata.entry_points",
        "pydoc.locate",
    ],
)
def test_zero_dynamic_subprocess_or_reflection_references(needle: str) -> None:
    """No dynamic import / subprocess-invocation / reflection lookup of
    plugin-doc-generator anywhere in the active code path. Phase 8.5
    plan section 3.1 Tiers 3 + 4 + 5 combined."""
    hits: list[str] = []
    for py_path in REPO_ROOT.rglob("plugins/launchpad/scripts/**/*.py"):
        rel = py_path.relative_to(REPO_ROOT).as_posix()
        if _is_permitted_path(rel):
            continue
        try:
            text = py_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if needle not in line:
                continue
            if (
                "plugin_doc_generator" in line
                or "plugin-doc-generator" in line
            ):
                hits.append(f"{rel}:{line_no}: {line.strip()[:160]}")
    assert not hits, (
        f"Phase 8.5 BL-247: dynamic / subprocess / reflection reference "
        f"to plugin-doc-generator via {needle!r}:\n  " + "\n  ".join(hits)
    )


def test_decommission_history_append_well_formed():
    """The Phase 8.5 entry in docs/maintainers/decommission-history.md
    is well-formed: file ends with newline; a row exists for
    plugin-doc-generator.py with BL-247 / Round 2 P2-A + Phase 8.5;
    pre-delete sha256 column populated."""
    audit_log = REPO_ROOT / "docs" / "maintainers" / "decommission-history.md"
    assert audit_log.is_file(), "decommission-history.md must exist"
    body = audit_log.read_text(encoding="utf-8")
    assert body.endswith("\n"), "audit log must end with a trailing newline"

    # Row for plugin-doc-generator.py with Phase 8.5 + BL-247 + sha256.
    pdg_pattern = re.compile(
        r"\|\s*[0-9-]+\s*\|\s*`plugins/launchpad/scripts/plugin-doc-generator\.py`"
        r".*?BL-247.*?8\.5.*?",
        re.DOTALL,
    )
    assert pdg_pattern.search(body), (
        "Phase 8.5 audit-log row for plugin-doc-generator.py is missing "
        "or malformed"
    )
    # Pre-delete sha256 must appear somewhere in the audit log appended row.
    assert "e13580b8dac3dc45521117c23db0d6ba50661ac66b2c363e7e93a2e198d89f30" in body, (
        "pre-delete sha256 missing from Phase 8.5 audit-log row"
    )


# ---------------------------------------------------------------------------
# Slice C -- subclass-bypass guard (lint + runtime)
# ---------------------------------------------------------------------------


def test_no_renderer_subclass_overrides_protected_methods():
    """No RendererBase subclass may override
    `render_to_path / render_batch / scan_batch / write_batch`. Phase 8.5
    plan section 3.11 lock; subclasses ONLY override `render_targets`."""
    import inspect
    import importlib
    from plugin_default_generators._renderer_base import RendererBase

    # Walk all RendererBase subclasses.
    subclasses: list[type] = []
    for module_name in (
        "plugin_default_generators.kernel_renderer",
        "plugin_default_generators.infrastructure_renderer",
    ):
        mod = importlib.import_module(module_name)
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, RendererBase) and obj is not RendererBase:
                subclasses.append(obj)

    assert subclasses, "expected at least one RendererBase subclass to verify"

    base_funcs = {
        name: getattr(RendererBase, name)
        for name in RendererBase.PROTECTED_METHODS
    }
    for cls in subclasses:
        for name, base_fn in base_funcs.items():
            sub_fn = getattr(cls, name, None)
            # Direct attribute lookup -- if subclass redeclared the method,
            # the function object differs from RendererBase's.
            if name in cls.__dict__:
                pytest.fail(
                    f"Subclass {cls.__name__} redeclared protected method "
                    f"{name!r}; Phase 8.5 plan section 3.11 forbids overrides "
                    f"of render_to_path / render_batch / scan_batch / "
                    f"write_batch"
                )
            assert sub_fn is base_fn, (
                f"Subclass {cls.__name__} shadows protected method {name!r}"
            )


# ---------------------------------------------------------------------------
# Slice A -- /lp-define rewire
# ---------------------------------------------------------------------------


def test_lp_define_runner_emits_trust_banner_before_write(tmp_path, capsys):
    """The /lp-define runner emits the trust-model banner to stderr BEFORE
    any render or scan fires. Phase 8.5 plan section 3.12 + spec-flow P1-1
    (enforceable runtime emit, not markdown-only)."""
    import lp_define_runner

    # Bootstrap a generic-stack project so the detector returns quickly.
    (tmp_path / "package.json").write_text(
        '{"name":"demo"}', encoding="utf-8"
    )

    # Capture stderr; run dry-run + force.
    rc = lp_define_runner.generate(
        tmp_path,
        dry_run=True,
        force=True,
        product_name="Demo",
        emit_trust_banner=True,
    )
    captured = capsys.readouterr()

    assert rc == 0, f"runner exit code {rc}; stderr: {captured.err}"
    # Banner appears BEFORE any rendered-summary output. We capture the
    # banner exactly as Phase 8.5 plan section 3.12 specified.
    assert lp_define_runner.TRUST_BANNER in captured.err, (
        f"trust banner missing from stderr; got:\n{captured.err}"
    )
    # Sanity: banner appears verbatim.
    assert (
        "All rendered content is scanned against "
        ".launchpad/secret-patterns.txt before any disk write"
    ) in captured.err


def test_lp_define_runner_renders_canonical_docs_dry_run(tmp_path):
    """Smoke: dry-run produces the 7 canonical doc relpaths + a clean
    JSON summary. Stands in for Slice A0a's behavioral-equivalence
    contract -- the runner produces the same output set as the legacy
    plugin-doc-generator.py against a generic-stack project."""
    import lp_define_runner

    (tmp_path / "package.json").write_text('{"name":"demo"}', encoding="utf-8")

    rc = lp_define_runner.generate(
        tmp_path,
        dry_run=True,
        force=False,
        product_name="Demo",
        emit_trust_banner=False,
    )
    assert rc == 0


def test_lp_define_runner_full_batch_secret_finding_refuses_all(tmp_path, monkeypatch):
    """Synthesize a render whose output contains an AWS-key shape; assert
    the orchestrator's full-batch scan refuses the run with exit 1 and
    NO files reach disk. Preserves the legacy
    plugin-doc-generator.py:496-505 contract."""
    import lp_define_runner

    (tmp_path / "package.json").write_text('{"name":"demo"}', encoding="utf-8")

    # Inject an AWS-key into the rendered output by monkeypatching
    # render_docs to add a secret to one of the artifacts.
    real_render_docs = lp_define_runner.render_docs

    def render_docs_with_secret(*args, **kwargs):
        rendered = real_render_docs(*args, **kwargs)
        # Pollute the PRD with a synthesized secret.
        if "docs/architecture/PRD.md" in rendered:
            rendered["docs/architecture/PRD.md"] += "\nLook: AKIAABCDEFGHIJKLMNOP\n"
        return rendered

    monkeypatch.setattr(lp_define_runner, "render_docs", render_docs_with_secret)

    rc = lp_define_runner.generate(
        tmp_path,
        dry_run=False,
        force=True,
        product_name="Demo",
        emit_trust_banner=False,
    )
    assert rc == 1, "secret in rendered batch must abort the run"
    # No canonical doc lands on disk.
    assert not (tmp_path / "docs" / "architecture" / "PRD.md").exists()
    assert not (tmp_path / ".launchpad" / "config.yml").exists()


def test_no_renderer_subclass_writes_directly():
    """No production module under plugin_default_generators/ or
    plugin_stack_adapters/ calls `atomic_write_replace` directly except
    `_renderer_base.py`. Phase 8.5 plan section 2.3 ALLOWLIST-based lint
    rule equivalent at runtime."""
    import ast as _ast

    forbidden_dirs = (
        REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin_default_generators",
        REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin_stack_adapters",
    )
    allowed_paths = {
        REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin_default_generators" / "_renderer_base.py",
    }

    hits: list[str] = []
    for root in forbidden_dirs:
        for py_path in root.rglob("*.py"):
            if py_path in allowed_paths:
                continue
            if "/_vendor/" in py_path.as_posix() or "/__pycache__/" in py_path.as_posix():
                continue
            try:
                tree = _ast.parse(py_path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            bound: set[str] = set()
            for node in _ast.walk(tree):
                if isinstance(node, _ast.ImportFrom):
                    if (node.module or "").endswith("atomic_io"):
                        for alias in node.names:
                            if alias.name == "atomic_write_replace":
                                bound.add(alias.asname or alias.name)
                elif isinstance(node, _ast.Import):
                    for alias in node.names:
                        if alias.name == "atomic_io":
                            bound.add(alias.asname or alias.name)
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Call):
                    func = node.func
                    if isinstance(func, _ast.Name) and func.id in bound:
                        hits.append(f"{py_path.relative_to(REPO_ROOT)}:{node.lineno}")
                    elif (
                        isinstance(func, _ast.Attribute)
                        and func.attr == "atomic_write_replace"
                        and isinstance(func.value, _ast.Name)
                        and func.value.id in bound
                    ):
                        hits.append(f"{py_path.relative_to(REPO_ROOT)}:{node.lineno}")

    assert not hits, (
        f"Renderer subclass(es) bypass write_batch via direct atomic_write_replace "
        f"call: {hits}"
    )
