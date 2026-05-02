"""Top-level /lp-pick-stack 6-step pipeline orchestrator (Phase 2 §4.1).

Coordinates Steps 0-6 into a single `run_pipeline()` entrypoint:

  Step 0 — Greenfield gate (cwd_state.refuse_if_not_greenfield + brainstorm
           summary frontmatter parse, optional)
  Step 1 — Project description envelope (privacy notice, free-text capture)
  Step 2 — 5-question funnel validation (question_funnel.validate_answers)
  Step 3 — Match + resolve (matcher.match_categories + cluster narrowing)
  Step 4 — Manual-override branch (manual_override_resolver.resolve_manual)
  Step 5 — Rationale generation + extract_summary (rationale_renderer +
           rationale_summary_extractor)
  Step 6 — Integrity envelope + atomic decision-file write
           (decision_writer.write_decision_file)

Markdown command (`commands/lp-pick-stack.md`) handles user-facing prompting
and passes the collected inputs to `run_pipeline()` via a Result object so
the command can surface the final outcome (path written, rejection reason).

Per HANDSHAKE §1.5 strip-back: brainstorm_session_id field OMITTED from
decision file; marker is simple positive-presence sentinel only at v2.0
(BL-235). The engine does NOT read .first-run-marker for a session_id.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

# Ensure scripts/ is on path for sibling-module imports when invoked as a
# library from outside the package.
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cwd_state import refuse_if_not_greenfield  # noqa: E402
from telemetry_writer import write_telemetry_entry  # noqa: E402

from lp_pick_stack.decision_writer import (  # noqa: E402
    DecisionWriteError,
    EMPTY_FILE_SHA256,
    write_decision_file,
    write_rationale_atomic,
)
from lp_pick_stack.manual_override_resolver import (  # noqa: E402
    ManualOverrideError,
    resolve_manual,
)
from lp_pick_stack.matcher import (  # noqa: E402
    MANUAL_OVERRIDE_ID,
    MatchCandidate,
    match_categories,
    resolve_in_cluster,
)
from lp_pick_stack.question_funnel import (  # noqa: E402
    AnswerValidationError,
    validate_answers,
)
from lp_pick_stack.rationale_renderer import render_rationale  # noqa: E402
from lp_pick_stack.rationale_summary_extractor import extract_summary  # noqa: E402


COMMAND_NAME = "/lp-pick-stack"
DEFAULT_CATEGORY_PATTERNS_PATH = (
    Path(__file__).resolve().parent / "data" / "category-patterns.yml"
)


# Outcome enum for the telemetry entry (OPERATIONS §5).
class Outcome:
    ACCEPTED = "accepted"
    MANUAL_OVERRIDE = "manual_override"
    ABORTED = "aborted"


@dataclass
class PipelineResult:
    """Structured result of a `run_pipeline()` invocation.

    On success, `decision_path` is the written `.launchpad/scaffold-decision.json`
    Path. On failure, `reason` is a §4-style error tag and `message` is the
    user-facing hint.
    """

    success: bool
    outcome: str  # one of Outcome.{ACCEPTED, MANUAL_OVERRIDE, ABORTED}
    matched_category_id: str | None = None
    decision_path: Path | None = None
    rationale_path: Path | None = None
    reason: str | None = None
    message: str | None = None
    candidates: list[MatchCandidate] = field(default_factory=list)
    cluster: str | None = None  # set when ambiguity cluster needs disambiguation
    elapsed_seconds: float = 0.0


def _load_category_patterns(path: Path | None) -> dict:
    """Read + YAML-parse the v2.0 category-patterns catalog.

    YAML is loaded via `yaml.safe_load` (no aliases-as-references; HANDSHAKE
    §2 rule for trusted-as-data plugin-shipped configs).
    """
    try:
        import yaml  # late import to avoid making yaml a hard dep at module load
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "pyyaml is required for /lp-pick-stack. Install with: "
            "`pip install -r plugins/launchpad/scripts/requirements.txt` "
            "(pinned version lives in plugins/launchpad/scripts/_vendor/PYYAML_VERSION)."
        ) from exc

    target = path if path is not None else DEFAULT_CATEGORY_PATTERNS_PATH
    text = target.read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def _build_telemetry(
    outcome: str,
    *,
    matched_category_id: str | None,
    elapsed_seconds: float,
    cwd_state_value: str | None = "empty",
) -> dict:
    """Construct the OPERATIONS §5 telemetry payload (no free-text fields)."""
    payload: dict[str, Any] = {
        "command": COMMAND_NAME,
        "outcome": outcome,
        "time_seconds": round(elapsed_seconds, 3),
    }
    if matched_category_id is not None:
        payload["matched_category_id"] = matched_category_id
    if cwd_state_value is not None:
        payload["cwd_state"] = cwd_state_value
    return payload


def run_pipeline(
    cwd: Path,
    answers: Mapping[str, str],
    *,
    project_description: str = "",
    no_rationale: bool = False,
    manual_override: bool = False,
    manual_layer_specs: Sequence[Mapping[str, Any]] | None = None,
    cluster_choice: str | None = None,
    project_understanding: Sequence[str] = (),
    why_this_fits: Sequence[str] = (),
    alternatives: Sequence[str] = (),
    notes: Sequence[str] = (),
    category_patterns_path: Path | None = None,
    skip_greenfield_gate: bool = False,
    write_telemetry: bool = True,
    monorepo: bool | None = None,
) -> PipelineResult:
    """Execute the 6-step pick-stack pipeline.

    Returns a PipelineResult; the engine never raises for expected refusal
    paths (greenfield gate, ambiguity-without-cluster, write-conflict),
    instead returning `success=False` with a `reason` tag the markdown
    command surfaces. Programming errors (TypeError, etc.) propagate.

    Inputs:

    - `cwd`: working directory the decision file is written into. MUST exist.
    - `answers`: validated by question_funnel; the engine re-runs validation
      defensively in case the caller skipped that step.
    - `project_description`: free-text from Step 1 (used as `describe` if
      Q1 == something-else-describe AND not already in answers).
    - `no_rationale`: when True, skip rationale.md write; rationale_sha256
      becomes EMPTY_FILE_SHA256 (per Phase 2 handoff §4.1 Step 5 + §6
      acceptance criterion).
    - `manual_override`: True when user picks `[m]anual override`. Caller
      MUST pass `manual_layer_specs`.
    - `manual_layer_specs`: list of {stack, role, path, options?} dicts.
    - `cluster_choice`: when the matcher returns multiple tied candidates in
      the same cluster, this picks one (must be in the tied set).
    - `project_understanding`/`why_this_fits`/`alternatives`/`notes`:
      caller-supplied bullets for the rationale renderer.
    - `category_patterns_path`: override the default catalog path (test hook).
    - `skip_greenfield_gate`: test hook to bypass cwd_state check (used by
      unit tests that exercise the engine on non-greenfield tmp dirs).
    - `write_telemetry`: emit the OPERATIONS §5 v2-pipeline-*.jsonl entry.
    - `monorepo`: override the monorepo bool (defaults to len(layers) > 1).
    """
    start = time.monotonic()
    cwd = Path(cwd)

    # --- Step 0: greenfield gate ---
    if not skip_greenfield_gate:
        try:
            refuse_if_not_greenfield(cwd, COMMAND_NAME)
        except (RuntimeError, NotADirectoryError) as exc:
            elapsed = time.monotonic() - start
            result = PipelineResult(
                success=False,
                outcome=Outcome.ABORTED,
                reason="cwd_state_brownfield_or_ambiguous",
                message=str(exc),
                elapsed_seconds=elapsed,
            )
            if write_telemetry:
                _emit_telemetry(cwd, result, cwd_state_value=None)
            return result

    # --- Step 2: validate answers (defensive re-validation) ---
    try:
        # If caller has Q1=something-else-describe but didn't include
        # `describe`, fold project_description into the answers dict.
        merged: dict[str, str] = dict(answers)
        if (
            merged.get("Q1") == "something-else-describe"
            and "describe" not in merged
            and project_description
        ):
            merged["describe"] = project_description
        elif project_description and "describe" not in merged:
            # Even when Q1 is enum, we still capture project_description as
            # describe so the matcher's `describe contains` predicates fire.
            merged["describe"] = project_description
        validated = validate_answers(merged)
    except AnswerValidationError as exc:
        elapsed = time.monotonic() - start
        result = PipelineResult(
            success=False,
            outcome=Outcome.ABORTED,
            reason="answer_validation_failed",
            message=str(exc),
            elapsed_seconds=elapsed,
        )
        if write_telemetry:
            _emit_telemetry(cwd, result)
        return result

    # --- Step 3 / 4: match (or manual-override) ---
    if manual_override:
        return _run_manual_override_branch(
            cwd=cwd,
            layer_specs=manual_layer_specs or [],
            answers=validated,
            no_rationale=no_rationale,
            project_understanding=project_understanding,
            why_this_fits=why_this_fits,
            alternatives=alternatives,
            notes=notes,
            monorepo=monorepo,
            start=start,
            write_telemetry=write_telemetry,
        )

    catalog = _load_category_patterns(category_patterns_path)
    candidates = match_categories(validated, catalog)

    if not candidates:
        elapsed = time.monotonic() - start
        result = PipelineResult(
            success=False,
            outcome=Outcome.ABORTED,
            reason="category_no_match",
            message=(
                "No category matched your answers. Re-describe the project "
                "shape, or re-run with manual override."
            ),
            elapsed_seconds=elapsed,
        )
        if write_telemetry:
            _emit_telemetry(cwd, result)
        return result

    if len(candidates) > 1:
        # Tied-at-the-top: ambiguity cluster narrowing.
        clusters = {c.cluster for c in candidates if c.cluster}
        if len(clusters) != 1 or None in {c.cluster for c in candidates}:
            elapsed = time.monotonic() - start
            result = PipelineResult(
                success=False,
                outcome=Outcome.ABORTED,
                reason="category_match_ambiguous_no_cluster",
                message=(
                    "Multiple categories tied without a documented ambiguity "
                    "cluster — defensive refusal. Categories: "
                    f"{[c.id for c in candidates]}"
                ),
                candidates=list(candidates),
                elapsed_seconds=elapsed,
            )
            if write_telemetry:
                _emit_telemetry(cwd, result)
            return result

        cluster_name = next(iter(clusters))
        if cluster_choice is None:
            elapsed = time.monotonic() - start
            return PipelineResult(
                success=False,
                outcome=Outcome.ABORTED,
                reason="ambiguity_cluster_disambiguation_required",
                message=(
                    f"Ambiguity cluster {cluster_name!r}: caller must pass "
                    "cluster_choice to narrow to one of: "
                    f"{[c.id for c in candidates]}"
                ),
                candidates=list(candidates),
                cluster=cluster_name,
                elapsed_seconds=elapsed,
            )
        try:
            chosen = resolve_in_cluster(candidates, cluster_choice)
        except ValueError as exc:
            elapsed = time.monotonic() - start
            return PipelineResult(
                success=False,
                outcome=Outcome.ABORTED,
                reason="ambiguity_cluster_choice_invalid",
                message=str(exc),
                candidates=list(candidates),
                cluster=cluster_name,
                elapsed_seconds=elapsed,
            )
    else:
        chosen = candidates[0]

    # --- Step 5: rationale + extract_summary ---
    return _finalize_decision(
        cwd=cwd,
        matched=chosen,
        layers=list(chosen.canonical_stack),
        matched_category_id=chosen.id,
        answers=validated,
        no_rationale=no_rationale,
        project_understanding=project_understanding,
        why_this_fits=why_this_fits,
        alternatives=alternatives,
        notes=notes,
        outcome=Outcome.ACCEPTED,
        monorepo=monorepo,
        start=start,
        write_telemetry=write_telemetry,
    )


def _run_manual_override_branch(
    *,
    cwd: Path,
    layer_specs: Sequence[Mapping[str, Any]],
    answers: Mapping[str, str],
    no_rationale: bool,
    project_understanding: Sequence[str],
    why_this_fits: Sequence[str],
    alternatives: Sequence[str],
    notes: Sequence[str],
    monorepo: bool | None,
    start: float,
    write_telemetry: bool,
) -> PipelineResult:
    """Execute Step 4 + Step 5 + Step 6 for the manual-override branch."""
    try:
        layers = resolve_manual(layer_specs, cwd)
    except ManualOverrideError as exc:
        elapsed = time.monotonic() - start
        result = PipelineResult(
            success=False,
            outcome=Outcome.ABORTED,
            reason="manual_override_invalid",
            message=str(exc),
            elapsed_seconds=elapsed,
        )
        if write_telemetry:
            _emit_telemetry(cwd, result)
        return result

    # Synthesize a MatchCandidate-shaped object for the renderer.
    fake_match = MatchCandidate(
        id=MANUAL_OVERRIDE_ID,
        name="Manual override",
        score=0,
        canonical_stack=tuple(layers),
        explanation="User chose stack manually via [m]anual override.",
        cluster=None,
    )

    return _finalize_decision(
        cwd=cwd,
        matched=fake_match,
        layers=layers,
        matched_category_id=MANUAL_OVERRIDE_ID,
        answers=answers,
        no_rationale=no_rationale,
        project_understanding=project_understanding,
        why_this_fits=why_this_fits,
        alternatives=alternatives,
        notes=notes,
        outcome=Outcome.MANUAL_OVERRIDE,
        monorepo=monorepo,
        start=start,
        write_telemetry=write_telemetry,
    )


def _finalize_decision(
    *,
    cwd: Path,
    matched: MatchCandidate,
    layers: Sequence[Mapping[str, Any]],
    matched_category_id: str,
    answers: Mapping[str, str],
    no_rationale: bool,
    project_understanding: Sequence[str],
    why_this_fits: Sequence[str],
    alternatives: Sequence[str],
    notes: Sequence[str],
    outcome: str,
    monorepo: bool | None,
    start: float,
    write_telemetry: bool,
) -> PipelineResult:
    """Run Step 5 (rationale + extract_summary) + Step 6 (integrity envelope
    + atomic write).

    Per HANDSHAKE §7 (Layer 9): rationale.md FIRST with O_CREAT|O_EXCL, then
    decision file with O_CREAT|O_EXCL. On either's FileExistsError, refuse
    with reason `scaffold_decision_already_exists`.
    """
    rendered = render_rationale(
        matched,
        answers,
        project_understanding=project_understanding,
        why_this_fits=why_this_fits,
        alternatives=alternatives,
        notes=notes,
        matched_category_id=matched_category_id,
        canonical_stack=list(layers),
    )

    rationale_path: Path | None = None
    rationale_sha256: str

    if no_rationale:
        rationale_sha256 = EMPTY_FILE_SHA256
    else:
        try:
            rationale_path, rationale_sha256 = write_rationale_atomic(rendered, cwd)
        except DecisionWriteError as exc:
            elapsed = time.monotonic() - start
            result = PipelineResult(
                success=False,
                outcome=Outcome.ABORTED,
                reason=exc.reason,
                message=str(exc),
                elapsed_seconds=elapsed,
            )
            if write_telemetry:
                _emit_telemetry(cwd, result)
            return result

    # Build the structured rationale_summary array. When --no-rationale,
    # produce a degraded-mode placeholder array satisfying HANDSHAKE §4
    # rule 7's ≥1-non-empty-bullet rule.
    if no_rationale:
        rationale_summary: list[dict] = [
            {"section": "project-understanding", "bullets": ["Rationale rendering disabled via --no-rationale."]},
            {"section": "matched-category", "bullets": [f"{matched_category_id}: matched."]},
            {"section": "stack", "bullets": [f"{layer['stack']} as {layer['role']} at {layer['path']}" for layer in layers]},
            {"section": "why-this-fits", "bullets": ["Engine matched on funnel answers (rationale not rendered)."]},
            {"section": "alternatives", "bullets": ["No alternatives surfaced (degraded mode)."]},
            {"section": "notes", "bullets": ["--no-rationale flag was set; rationale.md was not written."]},
        ]
    else:
        assert rationale_path is not None
        rationale_summary = extract_summary(rationale_path)

    try:
        decision_path, _ = write_decision_file(
            layers=layers,
            matched_category_id=matched_category_id,
            rationale_summary=rationale_summary,
            rationale_sha256=rationale_sha256,
            cwd=cwd,
            monorepo=monorepo,
        )
    except DecisionWriteError as exc:
        elapsed = time.monotonic() - start
        result = PipelineResult(
            success=False,
            outcome=Outcome.ABORTED,
            reason=exc.reason,
            message=str(exc),
            elapsed_seconds=elapsed,
            rationale_path=rationale_path,
        )
        if write_telemetry:
            _emit_telemetry(cwd, result, matched_category_id=matched_category_id)
        return result

    elapsed = time.monotonic() - start
    result = PipelineResult(
        success=True,
        outcome=outcome,
        matched_category_id=matched_category_id,
        decision_path=decision_path,
        rationale_path=rationale_path,
        elapsed_seconds=elapsed,
    )
    if write_telemetry:
        _emit_telemetry(cwd, result, matched_category_id=matched_category_id)
    return result


def _emit_telemetry(
    cwd: Path,
    result: PipelineResult,
    *,
    matched_category_id: str | None = None,
    cwd_state_value: str | None = "empty",
) -> None:
    """Best-effort telemetry write; failures are swallowed (analytics, not
    forensic — non-fatal per OPERATIONS §5)."""
    try:
        payload = _build_telemetry(
            result.outcome,
            matched_category_id=matched_category_id or result.matched_category_id,
            elapsed_seconds=result.elapsed_seconds,
            cwd_state_value=cwd_state_value,
        )
        write_telemetry_entry(cwd, payload)
    except Exception:
        pass


__all__ = [
    "COMMAND_NAME",
    "DEFAULT_CATEGORY_PATTERNS_PATH",
    "Outcome",
    "PipelineResult",
    "run_pipeline",
]
