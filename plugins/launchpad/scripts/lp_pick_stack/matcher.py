"""Category matcher (Phase 2 §4.1 Step 3).

Evaluates `fits_when` predicates from `category-patterns.yml` against
validated Q1-Q5 answers from `question_funnel.validate_answers()`.

Predicate grammar (closed; matches the strings in the v2.0
category-patterns.yml):

    expr        := atom (' AND ' atom)*
    atom        := q_eq | q_in | describe_clause | bare_keyword
    q_eq        := /Q[1-5]/ '=' value
    q_in        := /Q[1-5]/ ' IN [' value (',' value)* ']'
    describe    := 'describe contains' SP "'" alt ('|' alt)* "'"
    bare_keyword:= identifier (no '=' or 'contains') — soft signal,
                   matched against describe-text substring.

Each satisfied atom contributes 1 point to the category's score. The atom
count is bounded by the number of clauses in the predicate string (no
backtracking). Pure-CPU; no I/O.

Ambiguity-cluster handling (HANDSHAKE §4 rule 7): when ≥2 categories share
the highest score AND those categories are documented as members of the same
`ambiguity_clusters[]` entry, the matcher returns ALL tied candidates with
their cluster name. The engine surfaces a disambiguation prompt to the user;
on selection, the matcher's `resolve_in_cluster()` helper narrows to a
single category.

Manual-override (HANDSHAKE §4 rule 4): the reserved id `manual-override`
is filtered out of normal matching. The engine selects it explicitly when
the user picks `[m]anual override`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# Reserved category id for manual-override branch (HANDSHAKE §4 rule 4).
MANUAL_OVERRIDE_ID = "manual-override"

# Predicate atom shapes
_Q_EQ_RE = re.compile(r"^(Q[1-5])=([A-Za-z0-9_\-]+)$")
_Q_IN_RE = re.compile(r"^(Q[1-5])\s+IN\s+\[([^\]]+)\]$")
_DESCRIBE_RE = re.compile(r"^describe\s+contains\s+'([^']+)'$", re.IGNORECASE)


@dataclass(frozen=True)
class MatchCandidate:
    """A category that matched the answers, with its score."""

    id: str
    name: str
    score: int
    canonical_stack: tuple[dict, ...]
    explanation: str
    cluster: str | None  # ambiguity-cluster name if member; else None


def _split_atoms(predicate: str) -> list[str]:
    """Split a fits_when predicate string into AND-joined atoms.

    Bracket-aware split (the `Q3 IN [no, feature-not-core]` shape contains
    a comma but no AND inside the brackets, so a naive split-on-AND works
    against this v2.0 grammar). The describe-clause uses single-quoted
    alternation pipes inside, also AND-free.
    """
    return [p.strip() for p in predicate.split(" AND ") if p.strip()]


def _classify_atom(atom: str) -> str:
    """Classify an atom shape: 'q', 'describe', or 'keyword'.

    Q-atoms (Q1=, Q2=, ..., Q1 IN [...]) are HARD: a Q-atom mismatch
    disqualifies the category outright. Describe + bare-keyword atoms are
    SOFT: they boost the score on match but never disqualify.
    """
    if _Q_EQ_RE.match(atom) or _Q_IN_RE.match(atom):
        return "q"
    if _DESCRIBE_RE.match(atom):
        return "describe"
    return "keyword"


def _evaluate_atom(atom: str, answers: Mapping[str, str]) -> bool:
    """Evaluate one atom against the answers dict. Returns True if satisfied.

    Unknown/unparseable atoms return False (fail-closed); they contribute no
    score, which keeps adversarial fits_when shapes from over-scoring.
    """
    m = _Q_EQ_RE.match(atom)
    if m:
        q, value = m.group(1), m.group(2)
        return answers.get(q) == value

    m = _Q_IN_RE.match(atom)
    if m:
        q = m.group(1)
        values = [v.strip() for v in m.group(2).split(",")]
        return answers.get(q) in values

    m = _DESCRIBE_RE.match(atom)
    if m:
        describe = answers.get("describe", "")
        if not describe:
            return False
        alts = [a.strip().lower() for a in m.group(1).split("|") if a.strip()]
        describe_lower = describe.lower()
        return any(alt in describe_lower for alt in alts)

    # Bare keyword — soft signal; match describe substring.
    describe = answers.get("describe", "")
    if not describe:
        return False
    return atom.lower() in describe.lower()


def _score_predicate(predicate: str, answers: Mapping[str, str]) -> int:
    """Return the predicate's score against answers.

    Semantics: Q-atoms are DISQUALIFYING (any Q-atom that fails to match
    sets the score to 0 — the category is fundamentally inapplicable to
    the user's project shape). Describe + bare-keyword atoms are SOFT
    BOOSTERS — each match adds 1 to the score; misses contribute 0 but
    never disqualify.

    A category with no atoms scores 0. A category whose Q-atoms all match
    starts at 1 + the count of satisfied describe/keyword atoms. This
    makes Q1=mobile-app outweigh accidental Q4 matches on web/saas
    categories that have a Q1=web-app constraint.
    """
    if not isinstance(predicate, str) or not predicate.strip():
        return 0
    if predicate.strip() == "user_explicit_override":
        return 0  # never matched by normal funnel path

    score = 0
    has_q_atom = False
    for atom in _split_atoms(predicate):
        kind = _classify_atom(atom)
        matched = _evaluate_atom(atom, answers)
        if kind == "q":
            has_q_atom = True
            if not matched:
                return 0  # disqualifying mismatch
            score += 1
        elif matched:
            score += 1

    # Defensive: a predicate with NO Q-atoms (only describe/keyword) and no
    # matches scores 0; with matches, scores normally. Predicates with Q-
    # atoms that all matched have already contributed to score; if no other
    # atoms matched, score >= 1.
    if not has_q_atom and score == 0:
        return 0
    return score


def _build_cluster_lookup(
    ambiguity_clusters: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    """Map category id → cluster name. Categories outside any cluster omitted."""
    out: dict[str, str] = {}
    for cluster in ambiguity_clusters:
        name = cluster.get("name")
        members = cluster.get("members", [])
        if not isinstance(name, str) or not isinstance(members, list):
            continue
        for cat_id in members:
            if isinstance(cat_id, str):
                out[cat_id] = name
    return out


def match_categories(
    answers: Mapping[str, str],
    category_patterns: Mapping[str, Any],
) -> list[MatchCandidate]:
    """Evaluate every category's fits_when against answers; return top-scoring.

    Returns a list of MatchCandidate ordered by descending score. When the
    top score is shared (tie at the head), all tied candidates are returned;
    callers consult their `cluster` field to decide whether to invoke
    `resolve_in_cluster()` or refuse with `category_match_ambiguous_no_cluster`.

    `manual-override` is filtered out unconditionally — the engine selects it
    via an explicit user choice, never via score.

    Empty result list = zero categories matched (≥1 atom satisfied). Caller
    routes user to either re-describe or take manual-override.
    """
    categories = category_patterns.get("categories", [])
    clusters = category_patterns.get("ambiguity_clusters", [])
    cluster_lookup = _build_cluster_lookup(clusters)

    candidates: list[MatchCandidate] = []
    for cat in categories:
        cat_id = cat.get("id")
        if not isinstance(cat_id, str) or cat_id == MANUAL_OVERRIDE_ID:
            continue
        predicate = cat.get("fits_when", "")
        score = _score_predicate(predicate, answers)
        if score <= 0:
            continue
        canonical_stack = tuple(cat.get("canonical_stack", []))
        candidates.append(
            MatchCandidate(
                id=cat_id,
                name=cat.get("name", cat_id),
                score=score,
                canonical_stack=canonical_stack,
                explanation=cat.get("explanation", ""),
                cluster=cluster_lookup.get(cat_id),
            )
        )

    if not candidates:
        return []

    candidates.sort(key=lambda c: (-c.score, c.id))
    top_score = candidates[0].score
    return [c for c in candidates if c.score == top_score]


def resolve_in_cluster(
    candidates: Sequence[MatchCandidate],
    chosen_id: str,
) -> MatchCandidate:
    """Narrow a tied candidate set to one via the user's chosen id.

    Caller (engine) is responsible for prompting the user with the cluster's
    `differentiator` field and collecting the chosen id. This helper only
    enforces that the choice is among the tied set.
    """
    for c in candidates:
        if c.id == chosen_id:
            return c
    raise ValueError(
        f"chosen id {chosen_id!r} not in tied candidate set: "
        f"{[c.id for c in candidates]}"
    )


__all__ = [
    "MANUAL_OVERRIDE_ID",
    "MatchCandidate",
    "match_categories",
    "resolve_in_cluster",
]
