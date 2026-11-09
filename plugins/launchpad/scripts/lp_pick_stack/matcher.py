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

Q-atoms have three outcomes: an explicit match adds 1 point, an undecided
answer not listed in the atom adds 0 and records a wildcard, and a mismatch
(including a missing answer) disqualifies the category. Describe and keyword
matches each add 1 without disqualifying on a miss. Pure-CPU; no I/O.

`shortlist_categories()` returns every eligible positive-score category with
wildcard and description evidence, sorted by descending score then id.
`match_categories()` preserves the top-score slice for existing callers.
`confident_pick()` requires a unique top result with no wildcard and either
a description hit or no description atoms. `resolve_choice()` selects from
the entire shortlist. The legacy `resolve_in_cluster()` remains available
until engine callers migrate to shortlist selection.

Manual-override (HANDSHAKE §4 rule 4): the reserved id `manual-override`
is filtered out of normal matching. The engine selects it explicitly when
the user picks `[m]anual override`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Reserved category id for manual-override branch (HANDSHAKE §4 rule 4).
MANUAL_OVERRIDE_ID = "manual-override"

UNDECIDED_ANSWERS = {
    "Q2": frozenset({"not-sure-decide-for-me"}),
    "Q4": frozenset({"none-AI-driven-dev", "mixed-no-strong-preference"}),
    "Q5": frozenset({"no-strong-preference"}),
}

# Predicate atom shapes
_Q_EQ_RE = re.compile(r"^(Q[1-5])=([A-Za-z0-9_\-]+)$")
_Q_IN_RE = re.compile(r"^(Q[1-5])\s+IN\s+\[([^\]]+)\]$")
_DESCRIBE_RE = re.compile(r"^describe\s+contains\s+'([^']+)'$", re.IGNORECASE)


@dataclass(frozen=True)
class MatchCandidate:
    """An eligible category, its score, and wildcard and description evidence."""

    id: str
    name: str
    score: int
    canonical_stack: tuple[dict, ...]
    explanation: str
    cluster: str | None  # ambiguity-cluster name if member; else None
    matched_by_wildcard: tuple[str, ...] = ()
    describe_hits: tuple[str, ...] = ()
    describe_atoms: int = 0


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

    Q-atoms (Q1=, Q2=, ..., Q1 IN [...]) score explicit matches, record
    undecided answers as zero-point wildcards, and disqualify mismatches.
    Describe and bare-keyword atoms boost the score without disqualifying;
    the scorer records their matching alternatives as description evidence.
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


def _score_predicate(
    predicate: str, answers: Mapping[str, str]
) -> tuple[int, tuple[str, ...], tuple[str, ...], int]:
    """Return score, wildcard Q ids, description hits, and description count.

    Explicit Q matches add 1, undecided answers absent from the atom add 0
    and record the Q id in predicate order, and other mismatches disqualify.
    Missing answers are mismatches. Describe and keyword atoms add 1 on a
    match and never disqualify. Every matching lower-cased alternative is
    recorded; each describe or keyword atom counts once in describe_atoms.
    """
    if not isinstance(predicate, str) or not predicate.strip():
        return 0, (), (), 0
    if predicate.strip() == "user_explicit_override":
        return 0, (), (), 0

    score = 0
    wildcards: list[str] = []
    hits: list[str] = []
    describe_atoms = 0
    describe_lower = answers.get("describe", "").lower()
    for atom in _split_atoms(predicate):
        kind = _classify_atom(atom)
        matched = _evaluate_atom(atom, answers)
        if kind == "q":
            if matched:
                score += 1
                continue
            q = atom[:2]
            if answers.get(q) in UNDECIDED_ANSWERS.get(q, frozenset()):
                wildcards.append(q)
            else:
                return 0, (), (), 0
        else:
            describe_atoms += 1
            if matched:
                score += 1
                match = _DESCRIBE_RE.match(atom)
                alternatives = (
                    [a.strip().lower() for a in match.group(1).split("|") if a.strip()]
                    if match
                    else [atom.lower()]
                )
                hits.extend(alt for alt in alternatives if alt in describe_lower)

    return score, tuple(wildcards), tuple(hits), describe_atoms


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


def shortlist_categories(
    answers: Mapping[str, str],
    category_patterns: Mapping[str, Any],
) -> list[MatchCandidate]:
    """Return all eligible positive-score categories, sorted by (-score, id).

    Scores and evidence come from one predicate evaluation per category.
    Manual override is excluded; it is always an explicit engine branch.
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
        score, wildcards, hits, describe_atoms = _score_predicate(predicate, answers)
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
                matched_by_wildcard=wildcards,
                describe_hits=hits,
                describe_atoms=describe_atoms,
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.id))
    return candidates


def match_categories(
    answers: Mapping[str, str],
    category_patterns: Mapping[str, Any],
) -> list[MatchCandidate]:
    """Return the top-score slice of the evidence-bearing category shortlist."""
    candidates = shortlist_categories(answers, category_patterns)
    if not candidates:
        return []
    top_score = candidates[0].score
    return [c for c in candidates if c.score == top_score]


def confident_pick(shortlist: Sequence[MatchCandidate]) -> MatchCandidate | None:
    """Return a unique top candidate supported without wildcard answers.

    A candidate with description atoms also needs at least one description
    hit. The shortlist must be in the order returned by shortlist_categories.
    """
    if not shortlist:
        return None
    first = shortlist[0]
    if len(shortlist) > 1 and shortlist[1].score == first.score:
        return None
    if first.matched_by_wildcard:
        return None
    if first.describe_atoms and not first.describe_hits:
        return None
    return first


def resolve_choice(
    shortlist: Sequence[MatchCandidate], chosen_id: str
) -> MatchCandidate:
    """Select the user's chosen id from the entire eligible shortlist."""
    for candidate in shortlist:
        if candidate.id == chosen_id:
            return candidate
    raise ValueError(
        f"chosen id {chosen_id!r} not in category shortlist: "
        f"{[c.id for c in shortlist]}"
    )


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
    "UNDECIDED_ANSWERS",
    "confident_pick",
    "match_categories",
    "resolve_choice",
    "resolve_in_cluster",
    "shortlist_categories",
]
