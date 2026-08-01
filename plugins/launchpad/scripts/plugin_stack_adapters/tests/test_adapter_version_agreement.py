"""Cross-file version-claim agreement across the adapter layer.

Why this exists (v2.1.11, PR #145): the same corrected framework version had
to be chased through five separate layers before it stopped contradicting
itself, and every layer was found by a human reviewer rather than a gate:

  1. plugins/launchpad/scaffolders/<stack>-pattern.md   (knowledge anchors)
  2. lp_pick_stack/data/pillar-framework.md             (pick-stack rationale)
  3. lp_pick_stack/data/category-patterns.yml           (stack routing)
  4. plugin_stack_adapters/<stack>.py                   (architecture-doc metadata)
  5. plugin_stack_adapters/<stack>/templates/*.fragment (rendered output)

Layers 4 and 5 are the ones this test covers, because they are the pair that
ships version strings into the architecture docs of downstream projects: a
mismatch means a scaffolded repo documents a framework major it does not have.

The check is deliberately narrow. It does NOT know which version is correct;
upstream truth lives in the knowledge anchors and is re-verified by hand per
OPERATIONS section 4. It only asserts that the adapter module and its own
template fragments do not disagree with each other, which is the failure mode
that actually occurred and which nothing else detects.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pytest

ADAPTERS_DIR = Path(__file__).resolve().parent.parent

# Version-bearing framework tokens that appear in both module source and
# fragments. Each pattern captures (family, version) so two spellings of the
# same family can be compared. Kept explicit rather than generic: a loose
# `\w+ \d+` matcher would fire on unrelated prose like "Layer 3" or "Phase 8".
_TOKEN_PATTERNS = (
    re.compile(r"\b(Astro) (\d+)"),
    re.compile(r"\b(Expo SDK) (\d+)"),
    re.compile(r"\b(Rails) (\d+(?:\.\d+)?)"),
    re.compile(r"\b(Next\.js) (\d+)"),
    re.compile(r"\b(Django) (\d+(?:\.\d+)?)"),
    re.compile(r"\b(Hugo) (0\.\d+)"),
)


def _tokens(text: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for pattern in _TOKEN_PATTERNS:
        for family, version in pattern.findall(text):
            found[family].add(version)
    return found


def _adapter_pairs() -> list[tuple[str, Path, list[Path]]]:
    """Every adapter module that also ships a templates/ directory."""
    pairs = []
    for template_dir in sorted(ADAPTERS_DIR.glob("*/templates")):
        package = template_dir.parent.name
        if package == "tests":
            continue
        fragments = sorted(template_dir.glob("*.fragment"))
        if not fragments:
            continue
        # The module is either <package>.py or <package>_adapter.py.
        module = ADAPTERS_DIR / f"{package}.py"
        if not module.exists():
            module = ADAPTERS_DIR / f"{package}_adapter.py"
        if not module.exists():
            continue
        pairs.append((package, module, fragments))
    return pairs


def test_adapter_pairs_are_discoverable() -> None:
    """Guard the guard: a rename that empties this list must not pass silently."""
    pairs = _adapter_pairs()
    assert pairs, (
        "no adapter module/templates pairs found — the discovery glob is stale, "
        "so the agreement assertions below would vacuously pass"
    )


@pytest.mark.parametrize("package,module,fragments", _adapter_pairs(), ids=lambda v: v if isinstance(v, str) else "")
def test_adapter_module_and_fragments_agree_on_versions(
    package: str, module: Path, fragments: list[Path]
) -> None:
    module_tokens = _tokens(module.read_text(encoding="utf-8"))

    for fragment in fragments:
        fragment_tokens = _tokens(fragment.read_text(encoding="utf-8"))
        for family, fragment_versions in fragment_tokens.items():
            module_versions = module_tokens.get(family)
            if not module_versions:
                # Fragment names a framework the module never mentions. Not a
                # contradiction, so out of scope for this check.
                continue
            assert fragment_versions <= module_versions, (
                f"{package}: {fragment.name} claims {family} "
                f"{sorted(fragment_versions)} but {module.name} declares "
                f"{family} {sorted(module_versions)}. Generated architecture "
                f"docs would contradict the adapter metadata. Update both, and "
                f"check the knowledge anchor at "
                f"plugins/launchpad/scaffolders/ for which version is correct."
            )
