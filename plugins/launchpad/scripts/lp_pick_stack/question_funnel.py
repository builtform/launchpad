"""5-question funnel for /lp-pick-stack (Phase 2 §4.1 Step 2).

Per pick-stack plan §1.1 + handoff §4.1: pure-CPU validator for the 5 enum-
answer questions covering project shape. The Markdown command (`commands/
lp-pick-stack.md`) does the user-facing prompting; this module validates the
collected answers dict before they reach the matcher.

The enums are bounded so the matcher's `fits_when` predicates compose against
a known closed set. Q1's `something-else-describe` branch admits a free-text
follow-up captured in the `describe` key (sanitized by
`rationale_summary_extractor.py` filters before any consumption).

Per HANDSHAKE §1.5 strip-back: 5 questions remain at v2.0; the question count
is not deferred.
"""
from __future__ import annotations

from typing import Mapping

# Q1 — What are you building?
Q1_ALLOWED = frozenset({
    "web-app",
    "static-site-or-blog",
    "mobile-app",
    "data-ml-pipeline",
    "desktop-app",
    "api-only",
    "backend-managed",
    "something-else-describe",
})

# Q2 — Is there a dynamic backend?
Q2_ALLOWED = frozenset({
    "yes-needed",
    "static-content-only",
    "not-sure-decide-for-me",
})

# Q3 — Is AI/LLM/realtime a core feature?
Q3_ALLOWED = frozenset({
    "no",
    "feature-not-core",
    "core-AI-or-LLM",
    "core-realtime-collab",
})

# Q4 — Team's stack expertise + urgency profile?
Q4_ALLOWED = frozenset({
    "typescript-javascript",
    "python",
    "ruby-fast-MVP",
    "elixir",
    "mixed-no-strong-preference",
    "none-AI-driven-dev",
})

# Q5 — Deployment target / language preference (5th question for stack-edge
# disambiguation per pick-stack plan §1.1 evolution to 5-question funnel).
Q5_ALLOWED = frozenset({
    "edge-runtime",
    "node-server",
    "container",
    "managed-platform",
    "no-strong-preference",
})

# Maximum length of Q1 free-text branch ("something-else-describe"). The
# rationale_summary_extractor truncates to 240 chars per bullet at extraction
# time; the upstream cap here keeps the funnel's stored answer bounded.
MAX_DESCRIBE_CHARS = 1024

QUESTION_ENUMS: Mapping[str, frozenset[str]] = {
    "Q1": Q1_ALLOWED,
    "Q2": Q2_ALLOWED,
    "Q3": Q3_ALLOWED,
    "Q4": Q4_ALLOWED,
    "Q5": Q5_ALLOWED,
}


class AnswerValidationError(ValueError):
    """Raised when collected funnel answers fail validation.

    Mirrors PathValidationError pattern: domain-specific subclass +
    `field_name` attribute for telemetry routing.
    """

    def __init__(self, message: str, field_name: str = "answers"):
        super().__init__(f"{field_name}: {message}")
        self.field_name = field_name


def validate_answers(answers: Mapping[str, str]) -> dict[str, str]:
    """Validate a 5-question answers mapping; return a normalized dict copy.

    Required keys: Q1, Q2, Q3, Q4, Q5 (all enum-bounded).
    Optional: `describe` (free text, only present when Q1 ==
    `something-else-describe`); ≤ MAX_DESCRIBE_CHARS, no NUL bytes. The
    describe field is NEVER trusted — the matcher reads it via the
    `describe contains '<alts>'` predicate only, and the rationale extractor
    re-filters at write time.

    Raises AnswerValidationError on any rule violation.
    """
    if not isinstance(answers, Mapping):
        raise AnswerValidationError(
            f"expected mapping, got {type(answers).__name__}"
        )

    out: dict[str, str] = {}
    for key, allowed in QUESTION_ENUMS.items():
        if key not in answers:
            raise AnswerValidationError(f"missing answer for {key}", key)
        value = answers[key]
        if not isinstance(value, str):
            raise AnswerValidationError(
                f"expected str for {key}, got {type(value).__name__}", key
            )
        if value not in allowed:
            raise AnswerValidationError(
                f"value {value!r} not in allowed enum for {key}", key
            )
        out[key] = value

    describe = answers.get("describe")
    if out["Q1"] == "something-else-describe":
        if not isinstance(describe, str) or not describe.strip():
            raise AnswerValidationError(
                "Q1=something-else-describe requires non-empty 'describe' field",
                "describe",
            )
    if describe is not None:
        if not isinstance(describe, str):
            raise AnswerValidationError(
                f"describe must be str, got {type(describe).__name__}",
                "describe",
            )
        if "\x00" in describe:
            raise AnswerValidationError("null byte in describe", "describe")
        if len(describe) > MAX_DESCRIBE_CHARS:
            raise AnswerValidationError(
                f"describe length {len(describe)} > {MAX_DESCRIBE_CHARS}",
                "describe",
            )
        out["describe"] = describe

    return out


__all__ = [
    "AnswerValidationError",
    "MAX_DESCRIBE_CHARS",
    "Q1_ALLOWED",
    "Q2_ALLOWED",
    "Q3_ALLOWED",
    "Q4_ALLOWED",
    "Q5_ALLOWED",
    "QUESTION_ENUMS",
    "validate_answers",
]
