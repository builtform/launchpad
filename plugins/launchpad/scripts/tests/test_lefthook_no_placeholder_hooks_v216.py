"""BL-351 v2.1.6 — `<stack>-noop: run: 'true'` placeholder hooks dropped.

Before v2.1.6 every stack lefthook fragment shipped a no-op placeholder
hook (`astro-noop: run: 'true'`, `ts_monorepo-noop: run: 'true'`, etc.)
so consumers' rendered `lefthook.yml` contained a cosmetically-visible
entry per active stack. The no-op did nothing at hook-execution time and
confused users reviewing their `lefthook.yml`. BL-351 drops the
placeholder content from every fragment and keeps the file as a
comment-only stub for future per-stack hook additions.

Test coverage:
- (1) Per-fragment placeholder absence: every shipped
  `lefthook.j2.fragment` either contains no `run: 'true'` placeholder
  hook OR the fragment is comment-only (no `pre-commit:` block).
- (2) Enricher-side regression: when the enricher merges all four
  v2.1.5 placeholder fragments into a kernel-rendered lefthook, the
  output MUST NOT contain any `*-noop` command names. Catches the
  scenario where someone re-introduces the placeholder shape via a
  copy-paste of the historical fragment template.
- (3) Real-content fragments still merge correctly: the
  `nextjs_fastapi` fragment (which contains a real Python-gates
  include) must still produce a populated `pre-commit:` block in the
  enriched output.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# stack_lefthook uses relative imports (`from .policy import ...`) so it
# must load as a package member, not via spec_from_file_location.
from lp_bootstrap.stack_lefthook import enrich_lefthook_with_stacks  # noqa: E402

_FRAGMENTS_ROOT = _SCRIPT_DIR / "plugin_stack_adapters"

# Stack ids whose fragments existed in v2.1.5 with `-noop: run: 'true'`
# placeholder content. The post-BL-351 expectation is that none of these
# fragments still emit the placeholder hook.
_PLACEHOLDER_FRAGMENT_STACKS = ("astro", "generic", "nextjs_standalone", "ts_monorepo")


def _read_fragment(stack_id: str) -> str:
    """Return the fragment body for a stack id; raises if missing."""
    path = _FRAGMENTS_ROOT / stack_id / "templates" / "lefthook.j2.fragment"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# (1) Per-fragment placeholder absence.
# ---------------------------------------------------------------------------


def _walk_yaml_for_noop_hooks(node: Any) -> list[str]:
    """Walk a parsed YAML structure; return any command-name keys whose
    value is `{ "run": "true" }`. These are the placeholder hooks BL-351
    drops.

    Operates on the parsed YAML (comments stripped) so docstrings in
    fragment headers referencing the historical placeholder don't trip
    the check. The walker is lenient about structure — any dict node with
    a `run: 'true'` literal value is flagged regardless of nesting depth.
    """
    findings: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, dict) and value.get("run") == "true":
                findings.append(str(key))
            findings.extend(_walk_yaml_for_noop_hooks(value))
    elif isinstance(node, list):
        for item in node:
            findings.extend(_walk_yaml_for_noop_hooks(item))
    return findings


@pytest.mark.parametrize("stack_id", _PLACEHOLDER_FRAGMENT_STACKS)
def test_fragment_no_longer_emits_placeholder_hook(stack_id: str) -> None:
    """Each previously-noop fragment must no longer parse to a hook with
    `run: 'true'` content. The fragment may still mention the historical
    placeholder in its comment header (for context); only the parsed
    YAML structure is checked.
    """
    body = _read_fragment(stack_id)
    parsed = yaml.safe_load(body)
    noops = _walk_yaml_for_noop_hooks(parsed)
    assert not noops, (
        f"`{stack_id}/templates/lefthook.j2.fragment` still parses to "
        f"placeholder hooks with `run: 'true'` content: {noops}. BL-351 "
        f"drops the placeholder; the fragment may be comment-only."
    )


def test_no_fragment_emits_any_run_true_hook() -> None:
    """Sweep every `lefthook.j2.fragment` in the plugin and assert none
    of them PARSE to a `run: 'true'` hook. Catches a future contributor
    adding a new fragment with the same placeholder shape regardless of
    the per-stack header comment text.
    """
    for fragment_path in _FRAGMENTS_ROOT.glob("*/templates/lefthook.j2.fragment"):
        body = fragment_path.read_text(encoding="utf-8")
        try:
            parsed = yaml.safe_load(body)
        except yaml.YAMLError:
            # Fragment with a Jinja include directive (e.g.,
            # `{% include "_partials/..." %}`) parses to None / fails
            # because the include token is not valid YAML. Those are
            # exempt; the include resolves to real Python-gate content,
            # not a placeholder.
            continue
        noops = _walk_yaml_for_noop_hooks(parsed)
        assert not noops, (
            f"{fragment_path.relative_to(_FRAGMENTS_ROOT)} emits "
            f"placeholder hooks with `run: 'true'` content: {noops}. "
            f"BL-351 dropped this shape; either remove the hook or "
            f"replace with a real command."
        )


# ---------------------------------------------------------------------------
# (2) Enricher-side regression on multi-stack project.
# ---------------------------------------------------------------------------


def _write_config(tmp: Path, stacks: list[str]) -> None:
    cfg = tmp / ".launchpad" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"  - {s}" for s in stacks)
    cfg.write_text(f"stacks:\n{lines}\n", encoding="utf-8")


def test_enricher_output_contains_no_noop_command_names(tmp_path: Path) -> None:
    """With all four formerly-placeholder fragments enabled, the enriched
    lefthook.yml output MUST NOT contain `*-noop` command names.

    Builds a minimal kernel lefthook stub (just `pre-commit: commands: {}`)
    so the enricher has something to merge into. The contract under test
    is enricher → output content, not kernel template construction.
    """
    kernel = b"pre-commit:\n  commands: {}\n"
    _write_config(tmp_path, list(_PLACEHOLDER_FRAGMENT_STACKS))
    enriched = enrich_lefthook_with_stacks(kernel, tmp_path).decode("utf-8")

    for stack_id in _PLACEHOLDER_FRAGMENT_STACKS:
        assert f"{stack_id}-noop" not in enriched, (
            f"Enriched lefthook.yml contains `{stack_id}-noop` command "
            f"after BL-351 — the fragment is still emitting the "
            f"placeholder. Confirm the fragment is comment-only."
        )


# ---------------------------------------------------------------------------
# (3) Real-content fragment (nextjs_fastapi) still works.
# ---------------------------------------------------------------------------


def test_nextjs_fastapi_real_content_still_merges(tmp_path: Path) -> None:
    """The `nextjs_fastapi` fragment includes the
    `_partials/_python_gates.j2.fragment` shared partial (real content,
    not a placeholder). BL-351 must not break this path — the enricher
    output should contain Python-gate hook names like `pytest` or
    `ruff-check` that come from the partial.
    """
    kernel = b"pre-commit:\n  commands: {}\n"
    _write_config(tmp_path, ["nextjs_fastapi"])
    enriched = enrich_lefthook_with_stacks(kernel, tmp_path).decode("utf-8")
    # Sanity: real content from the Python-gates partial is present.
    # The partial emits multiple hook names; checking for the partial's
    # presence via any one of them is sufficient.
    assert any(
        marker in enriched for marker in ("pytest", "ruff", "pyright")
    ), (
        "nextjs_fastapi fragment should still contribute real Python-gate "
        "hooks (pytest / ruff / pyright) via the _python_gates partial. "
        "If BL-351's drop-the-placeholder change accidentally removed "
        "the partial include, the enricher returns an empty merge."
    )
