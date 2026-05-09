"""Validate `.launchpad/brainstorm-summary.md` frontmatter (HANDSHAKE §7).

Per v2.0.1 BL-244 #3 (PR #41 cycle-12 #2 closure): `lp-pick-stack.md` Step 0
specifies that when `.launchpad/brainstorm-summary.md` exists, the engine
must parse + validate the frontmatter and refuse with `reason:
"brainstorm_summary_invalid_frontmatter"` on shape failure, OR
`reason: "brainstorm_summary_greenfield_false"` when `greenfield: false`.
The pre-fix engine only ran the cwd greenfield gate and silently ignored
the brainstorm-summary contract — meaning a stale or invalid summary
file would be treated as if absent.

Required frontmatter keys (per HANDSHAKE §7):
  - `generated_at`: ISO 8601 UTC sec-precision Z-suffix (e.g. `2026-05-02T14:30:00Z`)
  - `generated_by`: must equal `/lp-brainstorm`
  - `greenfield`: bool
  - `cwd_state_when_generated`: one of `empty` / `brownfield` / `ambiguous`

The frontmatter parser is intentionally minimal — we don't depend on the
heavyweight `frontmatter` package; the simple `---` block delimiters and
YAML body parse via the already-vendored PyYAML.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ALLOWED_CWD_STATES = ("empty", "brownfield", "ambiguous")
ALLOWED_GENERATED_BY = "/lp-brainstorm"

# ISO 8601 UTC sec-precision with explicit Z suffix per HANDSHAKE §7.
_ISO_Z_SEC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class BrainstormSummaryError(RuntimeError):
    """Raised when brainstorm-summary.md fails validation. Carries `reason:`."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_yaml, body) from a `---`-delimited Markdown file.

    Raises BrainstormSummaryError on malformed delimiter shape. The
    frontmatter MUST be the first non-empty content; leading whitespace
    or blank lines before the opening `---` are tolerated, but anything
    else (e.g., a stray `# heading` before the delimiter) is rejected.
    """
    lines = text.splitlines()
    # Skip leading blank lines.
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        raise BrainstormSummaryError(
            "brainstorm-summary.md missing opening `---` frontmatter delimiter",
            reason="brainstorm_summary_invalid_frontmatter",
        )
    start = i + 1
    # Find closing `---`.
    end = None
    for j in range(start, len(lines)):
        if lines[j].strip() == "---":
            end = j
            break
    if end is None:
        raise BrainstormSummaryError(
            "brainstorm-summary.md missing closing `---` frontmatter delimiter",
            reason="brainstorm_summary_invalid_frontmatter",
        )
    fm = "\n".join(lines[start:end])
    body = "\n".join(lines[end + 1:])
    return fm, body


def _parse_frontmatter(fm_yaml: str) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(fm_yaml) or {}
    except yaml.YAMLError as exc:
        raise BrainstormSummaryError(
            f"brainstorm-summary.md frontmatter is not valid YAML: {exc}",
            reason="brainstorm_summary_invalid_frontmatter",
        ) from exc
    if not isinstance(parsed, dict):
        raise BrainstormSummaryError(
            f"brainstorm-summary.md frontmatter must be a YAML mapping; "
            f"got {type(parsed).__name__}",
            reason="brainstorm_summary_invalid_frontmatter",
        )
    return parsed


def validate_frontmatter(fm: dict[str, Any]) -> None:
    """Validate the parsed frontmatter mapping.

    Raises BrainstormSummaryError on any rule failure. Returns None on
    success. The two reason-codes the caller may see:
      - `brainstorm_summary_invalid_frontmatter`: shape/type/value failure
      - `brainstorm_summary_greenfield_false`: well-formed but greenfield: false
    """
    # Required keys present.
    required = {"generated_at", "generated_by", "greenfield", "cwd_state_when_generated"}
    missing = required - set(fm.keys())
    if missing:
        raise BrainstormSummaryError(
            f"brainstorm-summary.md frontmatter missing required keys: "
            f"{sorted(missing)}",
            reason="brainstorm_summary_invalid_frontmatter",
        )

    # generated_at: ISO 8601 UTC sec-precision Z-suffix.
    # PyYAML auto-parses ISO 8601 timestamps into Python `datetime` per YAML
    # 1.1 spec, so we accept BOTH string and datetime shapes — but the
    # datetime must be UTC-aware AND its rendered ISO Z form must round-trip
    # to a valid sec-precision string.
    generated_at = fm["generated_at"]
    if isinstance(generated_at, datetime):
        # Reject naive datetimes (no tzinfo) — the spec requires UTC Z suffix.
        if generated_at.tzinfo is None or generated_at.utcoffset() != UTC.utcoffset(None):
            raise BrainstormSummaryError(
                f"brainstorm-summary.md `generated_at` must be UTC (Z suffix); "
                f"got {generated_at!r} (naive or non-UTC tzinfo)",
                reason="brainstorm_summary_invalid_frontmatter",
            )
        # Render to canonical sec-precision Z form for downstream checks.
        rendered = generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Verify nothing was lost in the round-trip (sub-second precision rejected).
        if generated_at.microsecond != 0:
            raise BrainstormSummaryError(
                f"brainstorm-summary.md `generated_at` must be sec-precision; "
                f"got {generated_at!r} with microseconds={generated_at.microsecond}",
                reason="brainstorm_summary_invalid_frontmatter",
            )
        generated_at = rendered
    if not isinstance(generated_at, str) or not _ISO_Z_SEC_RE.fullmatch(generated_at):
        raise BrainstormSummaryError(
            f"brainstorm-summary.md `generated_at` must be ISO 8601 UTC "
            f"sec-precision Z-suffix (e.g. `2026-05-02T14:30:00Z`); got "
            f"{fm['generated_at']!r}",
            reason="brainstorm_summary_invalid_frontmatter",
        )
    # Defensive: verify the timestamp is parseable as a real date.
    try:
        datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise BrainstormSummaryError(
            f"brainstorm-summary.md `generated_at` is shape-correct but "
            f"not a real datetime: {generated_at!r}: {exc}",
            reason="brainstorm_summary_invalid_frontmatter",
        ) from exc

    # generated_by: must equal /lp-brainstorm.
    generated_by = fm["generated_by"]
    if generated_by != ALLOWED_GENERATED_BY:
        raise BrainstormSummaryError(
            f"brainstorm-summary.md `generated_by` must be {ALLOWED_GENERATED_BY!r}; "
            f"got {generated_by!r}",
            reason="brainstorm_summary_invalid_frontmatter",
        )

    # cwd_state_when_generated: enum.
    cwd_state = fm["cwd_state_when_generated"]
    if cwd_state not in ALLOWED_CWD_STATES:
        raise BrainstormSummaryError(
            f"brainstorm-summary.md `cwd_state_when_generated` must be one of "
            f"{list(ALLOWED_CWD_STATES)}; got {cwd_state!r}",
            reason="brainstorm_summary_invalid_frontmatter",
        )

    # greenfield: bool. Strict isinstance — YAML's `true`/`false` parse as bool;
    # `"true"`/`"false"` strings would NOT pass and the user should be told.
    greenfield = fm["greenfield"]
    if not isinstance(greenfield, bool):
        raise BrainstormSummaryError(
            f"brainstorm-summary.md `greenfield` must be a YAML bool (true|false); "
            f"got {type(greenfield).__name__} ({greenfield!r})",
            reason="brainstorm_summary_invalid_frontmatter",
        )

    # Hard refuse on greenfield: false (per HANDSHAKE §7 + lp-pick-stack.md
    # Step 0 step 2: brownfield brainstorm summaries route to /lp-define).
    if not greenfield:
        raise BrainstormSummaryError(
            f"brainstorm-summary.md was generated for a NON-greenfield cwd "
            f"(cwd_state_when_generated={cwd_state!r}). /lp-pick-stack only "
            f"applies to greenfield projects. Use /lp-define instead.",
            reason="brainstorm_summary_greenfield_false",
        )


def validate_brainstorm_summary(cwd: Path) -> None:
    """Top-level entry: validate `.launchpad/brainstorm-summary.md` if present.

    If the file is absent: returns silently (standalone /lp-pick-stack
    invocation is permitted per HANDSHAKE §7 + lp-pick-stack.md Step 0
    step 3).

    If present: reads, parses, validates. Raises BrainstormSummaryError
    on any rule failure.
    """
    summary_path = cwd / ".launchpad" / "brainstorm-summary.md"
    if not summary_path.is_file():
        return

    try:
        text = summary_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BrainstormSummaryError(
            f"brainstorm-summary.md exists but is unreadable: {exc}",
            reason="brainstorm_summary_invalid_frontmatter",
        ) from exc

    fm_yaml, _body = _split_frontmatter(text)
    fm = _parse_frontmatter(fm_yaml)
    validate_frontmatter(fm)


__all__ = [
    "ALLOWED_CWD_STATES",
    "ALLOWED_GENERATED_BY",
    "BrainstormSummaryError",
    "validate_brainstorm_summary",
    "validate_frontmatter",
]
