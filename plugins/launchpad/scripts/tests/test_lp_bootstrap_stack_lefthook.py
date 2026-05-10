"""Tests for v2.1.2 BL-316 production wiring (Slice 4c.4).

Covers `lp_bootstrap.stack_lefthook.enrich_lefthook_with_stacks`, which
closes the gap between the previously-test-only `_python_gates.j2.fragment`
partial and the consumer-emitted `lefthook.yml`.

Lanes covered (responding to PR #65 Codex P1-A):
  * Greenfield: no `.launchpad/config.yml` -> byte-identical kernel output.
  * Single-stack `nextjs_fastapi`: 5 Python gates (bandit, ruff-check,
    ruff-format-check at pre-commit; pyright, pytest at pre-push) appear
    AND kernel commands survive.
  * Single-stack `astro`: kernel commands + `astro-noop` survive; NO
    Python gates leak into a non-Python stack scaffold.
  * Multi-stack `[nextjs_fastapi, astro]` BOTH orderings: every Python
    gate AND `astro-noop` are present in the parsed YAML (closes the
    BL-323 runtime gap by routing through `merge_keys_additive` instead
    of YAML text concatenation).
  * Idempotency: enriching twice yields identical bytes.
  * Defensive paths: malformed config, malformed stack fragment,
    unknown stack id -> input bytes returned unchanged (never raise).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap.stack_lefthook import (  # noqa: E402
    enrich_lefthook_with_stacks,
    enumerate_lefthook_template_dependencies,
)

_PYTHON_PRECOMMIT_GATES = ("bandit", "ruff-check", "ruff-format-check")
_PYTHON_PREPUSH_GATES = ("pyright", "pytest")

_KERNEL_FIXTURE = b"""\
pre-commit:
  commands:
    prettier-fix:
      glob: "*.{js,jsx,ts,tsx,json,css,md,yml,yaml,html}"
      run: pnpm prettier --write {staged_files}
      stage_fixed: true
      priority: 1
    typecheck:
      run: pnpm typecheck
      priority: 10
"""


def _write_config(cwd: Path, stacks: list[str] | str) -> None:
    (cwd / ".launchpad").mkdir(exist_ok=True)
    if isinstance(stacks, list):
        body = "stacks: [{}]\n".format(", ".join(stacks))
    else:
        body = stacks  # raw YAML for malformed-config tests
    (cwd / ".launchpad" / "config.yml").write_text(body, encoding="utf-8")


def test_greenfield_no_config_returns_kernel_unchanged(tmp_path: Path) -> None:
    """No `.launchpad/config.yml` -> byte-identical kernel output. Critical
    for backwards compatibility with v2.1.1 and prior consumer scaffolds
    that bootstrap without a stacks declaration."""
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    assert out == _KERNEL_FIXTURE


def test_empty_stacks_list_returns_kernel_unchanged(tmp_path: Path) -> None:
    """`.launchpad/config.yml` with `stacks: []` -> kernel unchanged.
    Defensive: empty list is semantically equivalent to greenfield."""
    _write_config(tmp_path, [])
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    assert out == _KERNEL_FIXTURE


def test_single_stack_nextjs_fastapi_adds_python_gates(tmp_path: Path) -> None:
    """`stacks: [nextjs_fastapi]` -> all 5 Python gates appear under their
    correct hook keys AND kernel commands survive untouched."""
    _write_config(tmp_path, ["nextjs_fastapi"])
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    parsed = yaml.safe_load(out)
    assert isinstance(parsed, dict)

    pre_commit_cmds = parsed["pre-commit"]["commands"]
    for gate in _PYTHON_PRECOMMIT_GATES:
        assert gate in pre_commit_cmds, f"missing {gate} in pre-commit.commands"
    # Kernel commands preserved (additive merge contract).
    assert "prettier-fix" in pre_commit_cmds
    assert "typecheck" in pre_commit_cmds

    assert "pre-push" in parsed
    pre_push_cmds = parsed["pre-push"]["commands"]
    for gate in _PYTHON_PREPUSH_GATES:
        assert gate in pre_push_cmds, f"missing {gate} in pre-push.commands"


def test_single_stack_astro_adds_only_noop(tmp_path: Path) -> None:
    """`stacks: [astro]` -> `astro-noop` present, no Python gates leak,
    kernel commands survive. Confirms the stack-aware enrichment is
    correctly stack-scoped (Codex P1-B's parsed-YAML test for non-Python
    stacks)."""
    _write_config(tmp_path, ["astro"])
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    parsed = yaml.safe_load(out)

    pre_commit_cmds = parsed["pre-commit"]["commands"]
    assert "astro-noop" in pre_commit_cmds
    assert "prettier-fix" in pre_commit_cmds  # kernel survives
    for gate in (*_PYTHON_PRECOMMIT_GATES, *_PYTHON_PREPUSH_GATES):
        assert gate not in pre_commit_cmds, (
            f"{gate} unexpectedly leaked into astro-only scaffold"
        )


@pytest.mark.parametrize(
    "ordering",
    [
        ["nextjs_fastapi", "astro"],
        ["astro", "nextjs_fastapi"],
    ],
    ids=["fastapi_first", "astro_first"],
)
def test_multi_stack_composition_runtime_yaml_keeps_all_gates(
    tmp_path: Path, ordering: list[str]
) -> None:
    """Multi-stack composition: BOTH orderings keep all 5 Python gates
    AND `astro-noop` in the parsed YAML, regardless of which stack is
    declared first.

    This is the parsed-YAML test that the existing
    `test_composition_includes_python_gates_when_nextjs_fastapi_present`
    (substring-only) deferred to BL-323. Slice 4c.4's wiring through
    `merge_keys_additive` closes that runtime gap natively because
    additive map-merge cannot drop keys via last-key-wins."""
    _write_config(tmp_path, ordering)
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    parsed = yaml.safe_load(out)

    pre_commit_cmds = parsed["pre-commit"]["commands"]
    for gate in _PYTHON_PRECOMMIT_GATES:
        assert gate in pre_commit_cmds, (
            f"missing {gate} in ordering {ordering!r} (multi-stack drop)"
        )
    assert "astro-noop" in pre_commit_cmds, (
        f"missing astro-noop in ordering {ordering!r}"
    )
    assert "prettier-fix" in pre_commit_cmds, "kernel command lost"

    pre_push_cmds = parsed["pre-push"]["commands"]
    for gate in _PYTHON_PREPUSH_GATES:
        assert gate in pre_push_cmds, (
            f"missing {gate} in ordering {ordering!r} (pre-push drop)"
        )


def test_idempotency_double_enrichment_yields_identical_bytes(tmp_path: Path) -> None:
    """Running enrich twice on the same kernel + config produces identical
    bytes. Required for the engine's fast-path SHA comparison (line 1216
    in engine.py) to skip atomic writes on clean overlays."""
    _write_config(tmp_path, ["nextjs_fastapi"])
    out_a = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    out_b = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    assert out_a == out_b


def test_idempotency_re_enrichment_of_already_enriched_yields_same(
    tmp_path: Path,
) -> None:
    """Feeding the helper its OWN output (simulating an enrichment of an
    already-merged file) should not duplicate commands or further mutate
    the structure; this guards against the second-bootstrap scenario."""
    _write_config(tmp_path, ["nextjs_fastapi"])
    once = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    twice = enrich_lefthook_with_stacks(once, tmp_path)
    parsed_once = yaml.safe_load(once)
    parsed_twice = yaml.safe_load(twice)
    # Same set of pre-commit commands (no duplicates introduced).
    assert sorted(parsed_once["pre-commit"]["commands"].keys()) == sorted(
        parsed_twice["pre-commit"]["commands"].keys()
    )
    assert sorted(parsed_once["pre-push"]["commands"].keys()) == sorted(
        parsed_twice["pre-push"]["commands"].keys()
    )


def test_unknown_stack_id_is_silently_skipped(tmp_path: Path) -> None:
    """A stack id that has no fragment (e.g., legacy v2.0 catalog name or
    typo) -> silently skipped, kernel returned unchanged. The bootstrap
    engine treats lefthook.yml as load-bearing infrastructure, so unknown
    stack ids MUST NOT raise."""
    _write_config(tmp_path, ["nonexistent_stack_xyz"])
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    assert out == _KERNEL_FIXTURE


def test_malformed_kernel_yaml_falls_back_to_input(tmp_path: Path) -> None:
    """If the kernel template ever produces unparseable YAML (e.g.,
    Jinja error), the helper returns input unchanged rather than
    crashing the bootstrap render loop."""
    _write_config(tmp_path, ["nextjs_fastapi"])
    malformed = b": this is not valid yaml :::\n  - mismatched\n"
    out = enrich_lefthook_with_stacks(malformed, tmp_path)
    assert out == malformed


def test_malformed_config_yaml_falls_back_to_kernel(tmp_path: Path) -> None:
    """A user-corrupted `.launchpad/config.yml` -> read_stacks returns
    [] -> kernel unchanged. The helper never raises into bootstrap on
    config-side defects."""
    _write_config(tmp_path, "::: not valid YAML :::\n  - broken")
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    assert out == _KERNEL_FIXTURE


def test_python_gate_run_blocks_emitted_as_block_scalars(tmp_path: Path) -> None:
    """The serialized YAML keeps `run: |` block-scalar style (not quoted-
    string with embedded `\\n` escapes). Functional behavior is identical
    in either form, but block-scalar output matches the kernel template's
    human-readable shape and avoids review noise.

    This guards against PyYAML's default `width=80` regression where long
    gate-preamble lines force fallback to quoted-string style."""
    _write_config(tmp_path, ["nextjs_fastapi"])
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path).decode()
    # Substring test on the raw text: the bandit `run:` line must be
    # followed by `|` (block scalar) not `"` (double-quoted scalar).
    bandit_idx = out.index("bandit:")
    bandit_section = out[bandit_idx : bandit_idx + 200]
    assert "run: |" in bandit_section, (
        f"bandit `run:` not emitted as block scalar; got:\n{bandit_section}"
    )


def test_kernel_only_commands_preserved_exactly(tmp_path: Path) -> None:
    """Additive-merge contract: when stack fragments add new command
    names, kernel command bodies (`run:`, `glob:`, `priority:`, etc.)
    must remain byte-equivalent to the input. Regression shield against
    accidental kernel-command rewriting via merge."""
    _write_config(tmp_path, ["nextjs_fastapi"])
    out = enrich_lefthook_with_stacks(_KERNEL_FIXTURE, tmp_path)
    parsed = yaml.safe_load(out)
    prettier = parsed["pre-commit"]["commands"]["prettier-fix"]
    assert prettier["run"] == "pnpm prettier --write {staged_files}"
    assert prettier["stage_fixed"] is True
    assert prettier["priority"] == 1
    typecheck = parsed["pre-commit"]["commands"]["typecheck"]
    assert typecheck["run"] == "pnpm typecheck"
    assert typecheck["priority"] == 10


# --- BL-316 Slice 4c.5: manifest composite tamper-detection -----------------
#
# Closes the Codex P1 finding on b2d0673: pre-Slice-4c.5,
# `manifest_writer.compute_source_template_shas` only hashed the kernel
# `infrastructure/lefthook.yml.j2`. After Slice 4c.4 wired stack-aware
# enrichment in, the rendered `lefthook.yml` ALSO depends on per-stack
# lefthook fragments + the shared partials under `_partials/`. A
# modification to any contributor would silently bypass the manifest
# tamper-detection contract (`verify_source_template_shas`). Slice 4c.5
# extends the kernel SHA into a composite that includes every
# plugin-shipped contributor; the tests below lock that contract in.


def test_enumerate_dependencies_includes_shared_partials() -> None:
    """The two `_partials/` files must be in the dep list so
    `verify_source_template_shas` fires when either is modified."""
    deps = enumerate_lefthook_template_dependencies()
    dep_names = {p.name for p in deps}
    assert "_python_gates.j2.fragment" in dep_names
    assert "_require_tool_macro.j2.fragment" in dep_names


def test_enumerate_dependencies_includes_per_stack_fragments() -> None:
    """Every per-stack `lefthook.j2.fragment` must be enumerated.
    Regression shield against accidental directory-skip in the
    enumeration loop."""
    deps = enumerate_lefthook_template_dependencies()
    dep_relpaths = {str(p.parent.parent.name) for p in deps if p.parent.name == "templates"}
    # Active v2.1 stacks per STACK_ID_ACTIVE_ENUM should all have a
    # lefthook fragment (every adapter ships one).
    for stack_id in (
        "nextjs_fastapi",
        "nextjs_standalone",
        "astro",
        "generic",
        "ts_monorepo",
    ):
        assert stack_id in dep_relpaths, (
            f"missing lefthook fragment dep for stack {stack_id!r}"
        )


def test_enumerate_dependencies_is_deterministic_and_sorted() -> None:
    """Multiple invocations return identical ordering. Critical for the
    composite SHA's stability across processes / hosts."""
    a = [str(p) for p in enumerate_lefthook_template_dependencies()]
    b = [str(p) for p in enumerate_lefthook_template_dependencies()]
    assert a == b


def test_composite_lefthook_sha_changes_when_dep_content_modified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tamper detection: when ANY enumerated dependency's content
    changes, the composite SHA must change. Locks in the BL-316
    Slice 4c.5 fix for the Codex P1 manifest weakness on b2d0673."""
    from lp_bootstrap import manifest_writer, stack_lefthook

    fake_dep = tmp_path / "fake.fragment"
    fake_dep.write_bytes(b"original content")
    monkeypatch.setattr(
        stack_lefthook,
        "enumerate_lefthook_template_dependencies",
        lambda: [fake_dep],
    )

    sha_before = manifest_writer._composite_lefthook_sha("kernel_sha_abc")
    fake_dep.write_bytes(b"modified content")
    sha_after = manifest_writer._composite_lefthook_sha("kernel_sha_abc")

    assert sha_before != sha_after, (
        "composite SHA must change when contributing dep content changes"
    )


def test_composite_lefthook_sha_changes_when_kernel_sha_changes() -> None:
    """The kernel template SHA is part of the composite input; changing
    it must propagate."""
    from lp_bootstrap.manifest_writer import _composite_lefthook_sha

    a = _composite_lefthook_sha("kernel_sha_one")
    b = _composite_lefthook_sha("kernel_sha_two")
    assert a != b


def test_composite_lefthook_sha_is_stable_across_calls() -> None:
    """Determinism: two invocations on the same plugin install with the
    same kernel SHA produce the same composite. Required for manifest
    SHA comparison to skip atomic writes on clean overlays."""
    from lp_bootstrap.manifest_writer import _composite_lefthook_sha

    a = _composite_lefthook_sha("test_kernel_sha")
    b = _composite_lefthook_sha("test_kernel_sha")
    assert a == b
    assert len(a) == 64  # sha256 hex length


def test_composite_lefthook_sha_differs_from_kernel_only_sha() -> None:
    """The composite must integrate the kernel SHA non-trivially, NOT
    just return the kernel SHA verbatim. Otherwise Slice 4c.5 is a
    no-op and Codex P1 stays open."""
    from lp_bootstrap.manifest_writer import _composite_lefthook_sha

    kernel_sha = "a" * 64
    composite = _composite_lefthook_sha(kernel_sha)
    assert composite != kernel_sha


def test_compute_source_template_shas_uses_composite_for_lefthook_only() -> None:
    """End-to-end: `compute_source_template_shas` against the production
    root produces a `lefthook.yml` SHA that does NOT equal the bare
    kernel template SHA, while OTHER infrastructure files keep their
    plain per-template SHA. Confirms the composite is correctly scoped
    to lefthook.yml only and doesn't bleed into siblings."""
    from lp_bootstrap.manifest_writer import (
        _INFRA_TEMPLATE_ROOT,
        compute_source_template_shas,
    )
    from plugin_default_generators._renderer_base import sha256_file

    shas = compute_source_template_shas()
    kernel_lefthook_path = _INFRA_TEMPLATE_ROOT / "lefthook.yml.j2"
    bare_kernel_sha = sha256_file(kernel_lefthook_path)
    assert shas["lefthook.yml"] != bare_kernel_sha, (
        "lefthook.yml manifest SHA must be composite, not bare kernel SHA"
    )

    # Spot-check: gitignore (a non-stack-aware infra file) must still
    # have its plain template SHA.
    gitignore_path = _INFRA_TEMPLATE_ROOT / "gitignore.j2"
    assert shas[".gitignore"] == sha256_file(gitignore_path)
