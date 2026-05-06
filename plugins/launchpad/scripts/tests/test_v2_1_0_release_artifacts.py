"""Phase 9 v7 LOCKED: v2.1.0 release-artifact regression tests.

Pins the seven invariants that gate the v2.1.0 release notes draft and the
companion meta-doc updates so a future plan-author or finalizer cannot
silently regress them between Phase 9 ship and Phase 11 finalize.

Tests cover:

  1. Release notes file exists, has 6 H2 headings, has the DRAFT marker
     ABSENT (removed by Phase 11 §11 ship ceremony), and honors the DA7
     heading-collision invariant (no `^## ` line inside any fenced code
     block).
  2. No `.v2.md` siblings remain anywhere under `docs/`.
  3. `.claude-plugin/marketplace.json` plugin description matches the
     DA0a-locked phrasing byte-for-byte AND contains the Unicode-arrow
     `→` exactly six times (matching the locked pipeline string
     `(brainstorm → pick-stack → scaffold → define
      → plan → build → ship)`; plan-internal Test #3
      counting in §2.4 said `==3` but the locked phrasing has six;
     locked phrasing wins per DA0a "byte-for-byte" lock).
  4. `docs/guides/SECRET_SCANNER_TUNING.md` exists, has the four
     required H2 headings, the Warning regex, and the recommended
     remediation pattern.
  5. `.harness/phase9-fold-list.md` does NOT exist post-Phase-9.
  6. PII WARN block in release-notes Security section matches every
     line of the public `PII_WARN_LINES` tuple (imported via the
     Phase 10 amendment public surface) byte-for-byte.
  7. Release-notes Security section passes the DA7 deny-list: no
     STRIDE rows, no `cycle N` references, no `PR #N` references, no
     `lp-*-reviewer/auditor` agent names, no raw secret-pattern regex
     leakage.

Plan reference:
    docs/plans/launchpad_plans/2026-05-06-v2.1-phase9-implementation-plan.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "launchpad" / "scripts"
RELEASE_NOTES = REPO_ROOT / "docs" / "releases" / "v2.1.0.md"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


DA0A_LOCKED_DESCRIPTION = (
    "Autonomous AI coding harness for end-to-end software delivery across "
    "greenfield and brownfield codebases: picks the right stack for your new "
    "idea or detects your current stack if in brownfield. Scaffolds the "
    "infrastructure, then drives spec-driven development through the full "
    "pipeline (brainstorm → pick-stack → scaffold → define "
    "→ plan → build → ship). Backed by a persistent "
    "governance kernel: context, quality gates, and learnings carry across "
    "sessions so each run starts informed instead of cold."
)


def _read_release_notes() -> str:
    return RELEASE_NOTES.read_text(encoding="utf-8")


def _security_section(content: str) -> str:
    """Slice forward from `^## Security$` to next `^## ` heading or EOF.

    Same flag-based extractor as Risk #6 awk; both Test #6 and Test #7
    use this exact form per cycle 5 Spec-flow P2-1 + Adversarial P2-3
    absorption.
    """
    lines = content.splitlines()
    out = []
    in_sec = False
    for line in lines:
        if line == "## Security":
            in_sec = True
            continue
        if in_sec and line.startswith("## "):
            break
        if in_sec:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Test #1 -- release notes structure + DRAFT + heading-collision invariant
# ---------------------------------------------------------------------------


def test_release_notes_v2_1_0_structure() -> None:
    assert RELEASE_NOTES.exists(), f"missing release notes: {RELEASE_NOTES}"
    content = _read_release_notes()
    assert len(content) >= 1024, f"release notes too short: {len(content)} bytes"

    required_h2 = (
        "## Highlights",
        "## Migration from v2.0",
        "## Added",
        "## Security",
        "## Internal",
        "## Upgrading from v2.0",
    )
    for h in required_h2:
        assert h in content, f"missing H2: {h!r}"

    # DRAFT marker MUST be absent post-ship-ceremony per Phase 11 §11.
    # Phase 9 required marker presence as ship invariant; ship ceremony
    # removes it as part of finalization, and this assertion inverts to
    # guard against accidental re-introduction.
    assert "<!-- DRAFT:" not in content[:200], (
        "DRAFT marker must be absent in shipped release notes; Phase 11 "
        "ship ceremony removes the marker. If this fails, the marker was "
        "re-introduced in error."
    )

    # DA7 heading-collision invariant (cycle 6 v7 P1-3 absorption):
    # no `^## ` line inside any fenced code block. The flag-based
    # section extractor in Risk #6 + Test #6 + Test #7 is line-context-
    # blind, so a literal `## ` line inside a fenced bash example would
    # falsely trigger `f=0` and silently truncate the section content.
    in_fence = False
    for n, line in enumerate(content.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and line.startswith("## "):
            raise AssertionError(
                f"Test #1 fail: line {n} inside fenced code block matches "
                f"'^## ' regex; the flag-based section extractor would "
                f"falsely close the migration or security section. Use "
                f"single-# or inline-code form per DA7 heading-collision "
                f"invariant."
            )


# ---------------------------------------------------------------------------
# Test #2 -- no .v2.md siblings remain (DA2 fold-completeness guard)
# ---------------------------------------------------------------------------


def test_no_v2_md_siblings_in_docs() -> None:
    siblings = sorted(p for p in REPO_ROOT.glob("docs/**/*.v2.md") if p.is_file())
    assert siblings == [], f"unexpected .v2.md siblings: {[str(p) for p in siblings]}"


# ---------------------------------------------------------------------------
# Test #3 -- marketplace description byte-for-byte + Unicode-arrow byte count
# ---------------------------------------------------------------------------


def test_marketplace_json_description_locked() -> None:
    path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    desc = data["plugins"][0]["description"]
    assert desc == DA0A_LOCKED_DESCRIPTION, (
        "marketplace.json plugin description does not match DA0a-locked "
        "phrasing byte-for-byte"
    )
    # Six Unicode arrows (U+2192) per the locked pipeline string.
    # Plan §2.4 Test #3 stated ==3; that was a plan-internal counting
    # error vs the DA0a-locked text. The locked phrasing wins per
    # DA0a "byte-for-byte" lock.
    assert desc.count("→") == 6, (
        f"expected 6 Unicode arrows U+2192; got {desc.count(chr(0x2192))}"
    )
    assert desc.encode("utf-8").count(b"\xe2\x86\x92") == 6, (
        "Unicode-arrow utf-8 byte sequence count mismatch"
    )


# ---------------------------------------------------------------------------
# Test #4 -- secret scanner tuning guide structural + warning + remediation
# ---------------------------------------------------------------------------


def test_secret_scanner_tuning_guide_structural() -> None:
    path = REPO_ROOT / "docs" / "guides" / "SECRET_SCANNER_TUNING.md"
    assert path.exists(), f"missing scanner guide: {path}"
    content = path.read_text(encoding="utf-8")
    assert len(content) >= 512, f"scanner guide too short: {len(content)} bytes"

    required_h2 = (
        "## Allowlist mechanisms",
        "## Tuning workflow",
        "## Defense-in-depth framing",
    )
    for h in required_h2:
        assert h in content, f"missing H2: {h!r}"

    # Warning section heading with prefix-only mention; regex per cycle 2
    # Security P3-1 fragility absorption (light rewording does not break).
    assert re.search(r"^##\s+Warning.*prefix-only", content, re.M | re.I), (
        "Warning section heading must mention 'prefix-only' (regex form per "
        "DA5 + Security P1-A absorption)"
    )

    # Remediation pattern: canonical regex form per cycle 4 Coherence P1-1.
    assert re.search(r"\$REDACTED\$|REDACTED\b", content), (
        "scanner guide must include the recommended remediation pattern "
        r"(matches `$REDACTED$` literal-anchored or `REDACTED\b` "
        "word-boundary form)"
    )


# ---------------------------------------------------------------------------
# Test #5 -- fold-list deleted post-Phase-9 (DA8 absorption guard)
# ---------------------------------------------------------------------------


def test_phase9_fold_list_deleted() -> None:
    path = REPO_ROOT / ".harness" / "phase9-fold-list.md"
    assert not path.exists(), (
        f"`.harness/phase9-fold-list.md` must be deleted post-Phase-9 "
        f"(DA8 absorption guard). Found at {path}."
    )


# ---------------------------------------------------------------------------
# Test #6 -- PII WARN verbatim in release notes (via public PII_WARN_LINES)
# ---------------------------------------------------------------------------


def test_pii_warn_verbatim_in_release_notes() -> None:
    # Phase 10 amendment commit `387a143` exposed `PII_WARN_LINES` as a
    # public module constant for this exact import. DA6 + cycle 3
    # Adversarial P1 #5 + Path C amendment leverage.
    from lp_update_identity.engine import PII_WARN_LINES  # noqa: E402

    section = _security_section(_read_release_notes())
    assert len(section.strip()) > 0, (
        "Security section is empty; Slice A authoring error. The flag-based "
        "extractor sliced from `^## Security$` to next `^## ` heading or "
        "EOF and got nothing."
    )
    for line in PII_WARN_LINES:
        assert line in section, (
            f"PII_WARN line not found verbatim in Security section: {line!r}"
        )


# ---------------------------------------------------------------------------
# Test #7 -- DA7 deny-list negatives over Security section
# ---------------------------------------------------------------------------


def test_release_notes_security_section_denylist_clean() -> None:
    section = _security_section(_read_release_notes())
    assert len(section.strip()) > 0, (
        "Security section is empty; Slice A authoring error"
    )

    # Same-shape extraction as Test #6 + Risk #6 awk; the test asserts
    # non-empty before per-pattern checks to prevent vacuous green.
    deny_patterns = (
        (r"\bSTRIDE\b", re.I, "STRIDE threat-model row leakage"),
        (r"\bcycle \d+\b", re.I, "internal review-cycle reference"),
        (r"\bPR #\d+\b", 0, "internal PR-number reference"),
        (r"\blp-[a-z-]+-(reviewer|auditor)\b", 0, "agent-name leakage"),
    )
    for pat, flags, label in deny_patterns:
        m = re.search(pat, section, flags)
        assert m is None, (
            f"DA7 deny-list violation in Security section ({label}): "
            f"pattern {pat!r} matched {m.group()!r}"
        )

    # Bundled secret-pattern regex strings must not leak into the section.
    secret_patterns_path = (
        REPO_ROOT / ".launchpad" / "secret-patterns.txt"
    )
    if secret_patterns_path.exists():
        for line in secret_patterns_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for sec_line in section.splitlines():
                # The pattern is itself a regex; we look for verbatim
                # leakage of the pattern string into the public section.
                if line in sec_line:
                    raise AssertionError(
                        f"DA7 deny-list violation: bundled secret-pattern "
                        f"regex {line!r} leaked into Security section line "
                        f"{sec_line!r}"
                    )
