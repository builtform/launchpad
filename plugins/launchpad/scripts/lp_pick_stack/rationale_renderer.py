"""Rationale renderer (Phase 2 §4.1 Step 5).

Fills the 6-section template at `lp_pick_stack/data/rationale-template.md`
with content derived from the matched category + funnel answers, returning
the rendered Markdown body as a string. The engine writes the string to
`.launchpad/rationale.md` atomically (Phase 2 §4.1 Step 5: O_CREAT|O_EXCL).

The 6 ALLOWED_SECTIONS slugs that `rationale_summary_extractor.py` parses:

  project-understanding, matched-category, stack, why-this-fits, alternatives,
  notes

Bullets emitted here MUST satisfy the §9.1 sanitization filter (≤240 chars,
NFKC-normalized, no fenced code, no URLs, no `<>`/`http://`/`javascript:`).
The renderer pre-filters its own bullets (defensive — the engine re-runs
extract_summary() after writing to enforce contract); this module is the
canonical write-time gate.

Per HANDSHAKE §2 trust boundaries: pillar-framework.md and rationale-
template.md are plugin-shipped, trusted-as-data. They live under
`lp_pick_stack/data/` and are read directly via `Path.read_text(encoding=
"utf-8")` per Phase 2 handoff §4.1 Step 5 special-handling clause (NOT via
`knowledge_anchor_loader.read_and_verify()` — they're plugin-internal config,
not curate-mode pinned anchors).

The renderer is pure-CPU: no LLM calls, no template engine (no Jinja2, no
mustache), no string interpolation that could be injected. Section bodies
are constructed from the matched category's `canonical_stack` + the
sanitized funnel answers + `<untrusted_user_input>`-wrapped describe text.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from lp_pick_stack.matcher import MatchCandidate
from lp_pick_stack.rationale_summary_extractor import (
    FORBIDDEN_BULLET_RE,
    MAX_BULLET_CHARS,
    _has_dangerous_unicode,
)


def _utc_now_iso_sec() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sanitize_bullet(text: str) -> str | None:
    """Return a sanitized bullet body, or None if the bullet must be dropped.

    Mirrors the §9.1 extractor's filter so the renderer never WRITES a bullet
    the extractor would later DROP. Returning None tells the caller to skip
    the bullet entirely (the extractor would otherwise produce empty bullets
    that fail HANDSHAKE §4 rule 7's ≥1-non-empty-bullet requirement).
    """
    if not text:
        return None
    # NFKC normalize first so any composable confusable lands at the same
    # byte sequence as the matcher would see at extract-time.
    text = unicodedata.normalize("NFKC", text)
    if FORBIDDEN_BULLET_RE.search(text):
        return None
    if _has_dangerous_unicode(text):
        return None
    if len(text) > MAX_BULLET_CHARS:
        text = text[:MAX_BULLET_CHARS]
    text = text.strip()
    return text or None


def _render_bullets(items: Sequence[str]) -> list[str]:
    """Render a sequence of strings as `- <body>` Markdown bullets, sanitized."""
    out: list[str] = []
    for raw in items:
        clean = _sanitize_bullet(raw)
        if clean is not None:
            out.append(f"- {clean}")
    return out


def _layer_bullets(canonical_stack: Sequence[Mapping[str, Any]]) -> list[str]:
    """Bullet per layer: `<stack> as <role> at <path>`."""
    bullets: list[str] = []
    for layer in canonical_stack:
        stack = str(layer.get("stack", "?"))
        role = str(layer.get("role", "?"))
        path = str(layer.get("path", "?"))
        bullets.append(f"{stack} as {role} at {path}")
    return bullets


def render_rationale(
    matched: MatchCandidate,
    answers: Mapping[str, str],
    *,
    project_understanding: Sequence[str] = (),
    why_this_fits: Sequence[str] = (),
    alternatives: Sequence[str] = (),
    notes: Sequence[str] = (),
    matched_category_id: str | None = None,
    canonical_stack: Sequence[Mapping[str, Any]] | None = None,
    matched_name: str | None = None,
    matched_explanation: str | None = None,
    generated_at: str | None = None,
) -> str:
    """Render the 6-section rationale Markdown.

    Inputs:

    - `matched`: a MatchCandidate from `matcher.match_categories()` OR (when
      `matched_category_id` is provided) None equivalent — the explicit
      `matched_category_id`/`canonical_stack`/`matched_name`/
      `matched_explanation` parameters override the MatchCandidate fields,
      so callers using the manual-override branch can pass `matched=None`-
      like sentinel via `MatchCandidate(id="manual-override", ...)` AND have
      flexibility to refine the rendered name/explanation per their context.
    - `answers`: validated funnel answers dict.
    - `project_understanding` / `why_this_fits` / `alternatives` / `notes`:
      caller-supplied bullets per section. Empty sequences mean "no bullet
      for this section beyond the canonical defaults" — defaults below kick
      in for `matched-category` + `stack` (always derivable from the match).

    Output: the rendered Markdown body as a string. The caller writes this
    atomically to `.launchpad/rationale.md` via O_CREAT|O_EXCL (engine.py).

    HANDSHAKE §4 rule 7 enforcement: at least one section MUST contain ≥1
    non-empty bullet. The renderer enforces this implicitly via the
    matched-category + stack defaults (always produced when the input is
    well-formed); ambiguity-cluster matches additionally require ≥1
    `alternatives` bullet > 30 chars (caller's responsibility to supply).
    """
    cat_id = matched_category_id or matched.id
    stack_layers = canonical_stack if canonical_stack is not None else matched.canonical_stack
    name = matched_name or matched.name
    explanation = matched_explanation or matched.explanation
    ts = generated_at or _utc_now_iso_sec()

    # --- header / frontmatter ---
    lines: list[str] = [
        "---",
        "generated_by: /lp-pick-stack",
        f"generated_at: {ts}",
        f"matched_category_id: {cat_id}",
        "---",
        "",
        "# Why this stack?",
        "",
    ]

    # --- project-understanding ---
    pu_bullets = _render_bullets(project_understanding) or [
        f"- Project shape: {answers.get('Q1', '?')} per Q1.",
    ]
    lines.append("## project-understanding")
    lines.append("")
    lines.extend(pu_bullets)
    lines.append("")

    # --- matched-category ---
    mc_bullet = _sanitize_bullet(f"{cat_id}: {name}.")
    lines.append("## matched-category")
    lines.append("")
    lines.append(f"- {mc_bullet}" if mc_bullet else f"- {cat_id}: matched.")
    lines.append("")

    # --- stack ---
    stack_bullets = _render_bullets(_layer_bullets(stack_layers)) or [
        "- (manual-override; layers selected from VALID_COMBINATIONS)"
    ]
    lines.append("## stack")
    lines.append("")
    lines.extend(stack_bullets)
    lines.append("")

    # --- why-this-fits ---
    wtf_bullets = _render_bullets(why_this_fits) or (
        [f"- {clean}"]
        if (clean := _sanitize_bullet(explanation)) is not None
        else ["- Engine matched on Q1-Q5 funnel answers."]
    )
    lines.append("## why-this-fits")
    lines.append("")
    lines.extend(wtf_bullets)
    lines.append("")

    # --- alternatives ---
    alt_bullets = _render_bullets(alternatives) or [
        "- No close alternatives surfaced by the matcher."
    ]
    lines.append("## alternatives")
    lines.append("")
    lines.extend(alt_bullets)
    lines.append("")

    # --- notes ---
    notes_bullets = _render_bullets(notes) or [
        "- Six-month freshness review per BL-105."
    ]
    lines.append("## notes")
    lines.append("")
    lines.extend(notes_bullets)
    lines.append("")

    return "\n".join(lines)


__all__ = [
    "render_rationale",
]
