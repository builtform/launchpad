"""Secret-scanner false-positive allowlist (Phase 8.5 plan section 3.9 DA4).

Two mechanisms:

  1. Jinja-comment marker (preferred; per-section granularity). A template
     section flanked by `{# secret-allowlist: <reason> #}` ... blank line
     OR `{# secret-allowlist-end #}` opts out of the secret scan. Markers
     are removed by Jinja at render time, but their LINE positions in the
     rendered output are recorded by the renderer (Phase 8.5 plan section
     3.11) and consulted here.

  2. File-path allowlist (coarser; whole-file exemption). A line in
     `.launchpad/secret-allowlist.txt` matches the rendered target path
     against a glob; matches exempt the whole file from the scan.

`filter_allowlisted(findings, target_path, content)` consults both
mechanisms and returns the subset of `findings` not suppressed by an
allowlist entry. WARN logs (per Phase 8.5 plan section 3.9 sec-auditor
P2-1) are emitted for every suppression so maintainers see what is being
masked.
"""
from __future__ import annotations

import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# Jinja comment marker shape -- matches `{# secret-allowlist: <reason> #}`.
# The reason field is captured for the WARN log; trailing whitespace inside
# the marker is permitted.
_OPEN_MARKER_RE = re.compile(
    r"\{#\s*secret-allowlist:\s*(?P<reason>[^#]*?)\s*#\}"
)
_CLOSE_MARKER_RE = re.compile(r"\{#\s*secret-allowlist-end\s*#\}")


@dataclass
class _AllowlistRange:
    """A `[start_line, end_line]` (1-indexed inclusive) span in the
    rendered output that is exempt from the scanner. `reason` is the text
    from the open marker."""

    start_line: int
    end_line: int
    reason: str


def _scan_jinja_markers(template_source: str) -> list[_AllowlistRange]:
    """Locate `{# secret-allowlist: ... #}` markers in the TEMPLATE source
    and translate them to line ranges in the RENDERED output.

    Phase 8.5 plan section 3.9 simplification: markers must appear at the
    start of a line in the template, and their effect spans from the
    NEXT line until the next blank line OR until a
    `{# secret-allowlist-end #}` marker. The renderer strips Jinja
    comments at render time, so the rendered output's line numbers match
    the template's line numbers minus the marker's own line.

    For Phase 8.5 the simplified contract is: each open marker exempts
    the immediate following block, defined as either
      (a) the next paragraph (block until blank line), or
      (b) the explicit close marker.

    Returns ranges in the RENDERED line space.
    """
    lines = template_source.splitlines()
    ranges: list[_AllowlistRange] = []
    rendered_offset = 0  # number of marker-only lines stripped before this point
    i = 0
    while i < len(lines):
        line = lines[i]
        open_match = _OPEN_MARKER_RE.search(line)
        if open_match:
            reason = open_match.group("reason") or ""
            # Marker line itself is a Jinja comment; assume it renders to
            # nothing. Effective line in rendered output: i - rendered_offset.
            rendered_offset += 1
            j = i + 1
            range_start = j - rendered_offset + 1  # 1-indexed
            while j < len(lines):
                if _CLOSE_MARKER_RE.search(lines[j]):
                    rendered_offset += 1
                    break
                if lines[j].strip() == "":
                    break
                j += 1
            range_end = j - rendered_offset
            if range_end >= range_start:
                ranges.append(_AllowlistRange(range_start, range_end, reason))
            i = j + 1
            continue
        i += 1
    return ranges


def _strip_markers_from_content(content: str) -> str:
    """Remove Jinja markers from rendered content if any leaked through.

    Defensive: Jinja's comment stripping should already have removed them,
    but a non-Jinja caller might pass raw template-shaped content.
    """
    out = _OPEN_MARKER_RE.sub("", content)
    out = _CLOSE_MARKER_RE.sub("", out)
    return out


def _load_file_allowlist(allowlist_path: Path | None) -> list[str]:
    """Parse `.launchpad/secret-allowlist.txt` -- list of glob patterns,
    one per line. Comments (lines starting with `#`) and blanks ignored.
    Missing file -> empty list.
    """
    if allowlist_path is None or not allowlist_path.is_file():
        return []
    out: list[str] = []
    for raw in allowlist_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(stripped)
    return out


def _path_matches_allowlist(target_path: Path, patterns: Iterable[str]) -> str | None:
    """Return the matching glob pattern, or None if no match."""
    target_str = str(target_path)
    target_name = target_path.name
    for pat in patterns:
        if fnmatch.fnmatch(target_str, pat) or fnmatch.fnmatch(target_name, pat):
            return pat
    return None


def filter_allowlisted(
    findings: list,
    target_path: Path,
    rendered_content: str,
    *,
    template_source: str | None = None,
    allowlist_path: Path | None = None,
) -> list:
    """Return findings minus any suppressed by allowlist mechanisms.

    `findings` is a list of objects each carrying a `line_no` attribute
    (typically `secret_scanner.SecretMatch`). `target_path` is the
    rendered file's absolute or repo-relative path. `rendered_content` is
    the rendered text (used to detect leaked markers as a defensive
    fallback). `template_source` is the raw template text BEFORE render
    (used for Jinja-marker line-range computation; pass None to skip the
    Jinja-marker mechanism).

    WARN logs are emitted on stderr for every suppression so maintainers
    have audit visibility.
    """
    if not findings:
        return findings

    # Mechanism 2: file-path allowlist (whole-file exemption).
    file_globs = _load_file_allowlist(allowlist_path)
    matched_glob = _path_matches_allowlist(target_path, file_globs)
    if matched_glob is not None:
        for f in findings:
            print(
                f"WARN: secret-allowlist suppressed finding in {target_path} "
                f"at line {getattr(f, 'line_no', '?')}: file matched "
                f"glob {matched_glob!r} in .launchpad/secret-allowlist.txt",
                file=sys.stderr,
            )
        return []

    # Mechanism 1: Jinja-comment marker (per-section).
    if template_source:
        ranges = _scan_jinja_markers(template_source)
        if ranges:
            kept: list = []
            for f in findings:
                line_no = getattr(f, "line_no", -1)
                suppressed_reason = None
                for r in ranges:
                    if r.start_line <= line_no <= r.end_line:
                        suppressed_reason = r.reason
                        break
                if suppressed_reason is not None:
                    print(
                        f"WARN: secret-allowlist suppressed finding in "
                        f"{target_path} at line {line_no}: {suppressed_reason}",
                        file=sys.stderr,
                    )
                    continue
                kept.append(f)
            return kept

    return findings


__all__ = [
    "filter_allowlisted",
]
