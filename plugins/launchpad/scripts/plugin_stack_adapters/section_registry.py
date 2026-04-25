"""Read the section registry.

Canonical v1 location: `docs/tasks/SECTION_REGISTRY.md` (split from PRD).

Back-compat shim: if SECTION_REGISTRY.md is absent BUT PRD.md contains
section markers (legacy v0.1 shape), parse from PRD and emit a one-line
deprecation warning to stderr suggesting the user re-run `/lp-define`.
Shim is scheduled for removal in v1.1.

Contract:
  - load_sections(repo_root) -> list[SectionEntry]
  - raises FileNotFoundError if NEITHER SECTION_REGISTRY.md NOR PRD.md exists
  - returns empty list if registry exists but has no entries yet
  - emits `DeprecationWarning`-style stderr when back-compat shim fires
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SectionEntry:
    name: str                       # e.g. "auth-redesign"
    status: str | None              # "shaped" | "designed" | "planned" | "built" | None
    spec_path: str | None           # relative path to the section spec file
    added: str | None               # ISO date string, if recorded


# Matches the registry's documented shape (see SECTION_REGISTRY.md.j2):
#   ### <section-name>
#   - **Status:** shaped
#   - **Spec:** [path](...)
#   - **Added:** 2026-04-20
_HEADING_RE = re.compile(r"^###\s+(\S[\w-]*)\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^-\s+\*\*Status:\*\*\s+(\S+)", re.MULTILINE)
_SPEC_RE = re.compile(r"^-\s+\*\*Spec:\*\*\s+\[[^\]]+\]\(([^)]+)\)", re.MULTILINE)
_ADDED_RE = re.compile(r"^-\s+\*\*Added:\*\*\s+(\S+)", re.MULTILINE)

# Legacy PRD section markers — the pre-Phase-3 shape embedded sections
# directly inside PRD.md using the same `### <name>` convention. Fallback
# parser uses the same regex; only its source changes.


def _parse_entries(text: str) -> list[SectionEntry]:
    """Parse section entries from either SECTION_REGISTRY.md or legacy PRD.md.

    Splits the document by `### ` headings and extracts status/spec/added
    fields from the block following each heading (up to the next heading).
    """
    entries: list[SectionEntry] = []

    # Find heading positions to bound each section block.
    headings = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        name = m.group(1)
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[start:end]

        status_m = _STATUS_RE.search(block)
        spec_m = _SPEC_RE.search(block)
        added_m = _ADDED_RE.search(block)

        entries.append(
            SectionEntry(
                name=name,
                status=status_m.group(1) if status_m else None,
                spec_path=spec_m.group(1) if spec_m else None,
                added=added_m.group(1) if added_m else None,
            )
        )
    return entries


def load_sections(
    repo_root: Path | str,
    *,
    warn: bool = True,
    tasks_dir: str = "docs/tasks",
    architecture_dir: str = "docs/architecture",
) -> list[SectionEntry]:
    """Load sections from the registry, falling back to PRD.md if needed.

    Args:
        repo_root: project root. Accepts Path or str; str is coerced to Path.
        warn: if True, emit deprecation warning to stderr when shim fires
        tasks_dir / architecture_dir: overridable per `.launchpad/config.yml`
            `paths.*`; defaults match the canonical LaunchPad layout.
    """
    repo_root = Path(repo_root)
    registry_path = repo_root / tasks_dir / "SECTION_REGISTRY.md"
    prd_path = repo_root / architecture_dir / "PRD.md"

    if registry_path.is_file():
        text = registry_path.read_text(encoding="utf-8")
        return _parse_entries(text)

    if prd_path.is_file():
        if warn:
            print(
                f"DeprecationWarning: reading sections from {prd_path} (legacy shape). "
                f"Run /lp-define to split the section registry into "
                f"{registry_path}. Shim removed in v1.1.",
                file=sys.stderr,
            )
        text = prd_path.read_text(encoding="utf-8")
        return _parse_entries(text)

    raise FileNotFoundError(
        f"No section registry found. Expected {registry_path} (or legacy PRD.md at "
        f"{prd_path}). Run /lp-define to scaffold."
    )


def get_section(
    repo_root: Path | str,
    name: str,
    **kwargs,
) -> SectionEntry | None:
    """Convenience: lookup a specific section by name. Accepts Path or str."""
    for entry in load_sections(repo_root, **kwargs):
        if entry.name == name:
            return entry
    return None
