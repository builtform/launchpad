"""Pre-extract sanitized `rationale_summary` from `rationale.md` (HANDSHAKE §9.1).

Closes the persistent prompt-injection vector: `/lp-define` never reads
`rationale.md` directly; it consumes only the pre-extracted, sanitized
`rationale_summary` array embedded in `scaffold-decision.json` (§4 field 7).

Pure-Python — no Markdown rendering, no LLM, no regex backtracking on user
input.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ALLOWED_SECTIONS = {
    "project-understanding", "matched-category", "stack",
    "why-this-fits", "alternatives", "notes",
}
SECTION_ORDER = (
    "project-understanding", "matched-category", "stack",
    "why-this-fits", "alternatives", "notes",
)
MAX_BULLETS_PER_SECTION = 8
MAX_BULLET_CHARS = 240

# ASCII attack patterns
FORBIDDEN_BULLET_RE = re.compile(
    r"```|<|>|http://|https://|file://|data:|javascript:|vbscript:",
    re.IGNORECASE,
)


def _has_dangerous_unicode(s: str) -> bool:
    """Reject strings containing format/control characters or whose NFKC
    differs from input (catches fullwidth confusables like ＜＞ and zero-
    width joiners that bypass byte-length checks).
    """
    nfkc = unicodedata.normalize("NFKC", s)
    if nfkc != s:
        return True
    for ch in s:
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Cc") and ch not in (" ", "\t"):
            return True
    return False


def extract_summary(rationale_path: Path) -> list[dict]:
    text = rationale_path.read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {k: [] for k in ALLOWED_SECTIONS}
    current = None
    for line in text.splitlines():
        h2 = re.fullmatch(r"##\s+(.+?)\s*", line)
        if h2:
            slug = re.sub(r"[^a-z0-9-]", "-", h2.group(1).lower()).strip("-")
            current = slug if slug in ALLOWED_SECTIONS else None
            continue
        if current is None:
            continue
        bullet = re.fullmatch(r"\s*[-*]\s+(.+?)\s*", line)
        if not bullet:
            continue
        body = bullet.group(1)
        if FORBIDDEN_BULLET_RE.search(body):
            continue
        if _has_dangerous_unicode(body):
            continue
        if len(body) > MAX_BULLET_CHARS:
            # Truncate to MAX-1 then add "…" so total length is exactly MAX,
            # matching scaffold-stack's decision_validator strict ≤ MAX
            # rejection bound. Previous shape used `[:MAX] + "…"` producing
            # MAX+1 chars, which the validator rejected (PR #41 cycle 6 #3).
            body = body[: MAX_BULLET_CHARS - 1] + "…"
        if len(sections[current]) < MAX_BULLETS_PER_SECTION:
            sections[current].append(body)

    return [
        {"section": s, "bullets": sections[s]}
        for s in SECTION_ORDER
    ]


__all__ = [
    "ALLOWED_SECTIONS",
    "FORBIDDEN_BULLET_RE",
    "MAX_BULLETS_PER_SECTION",
    "MAX_BULLET_CHARS",
    "SECTION_ORDER",
    "extract_summary",
]
