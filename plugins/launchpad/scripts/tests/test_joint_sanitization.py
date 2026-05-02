"""Phase 7 §4.4 — joint sanitization sub-test (OPERATIONS §6 gate #5).

Validates the Phase 7 §10 surgical patch (NFKC-normalize before
`_FORBIDDEN_BULLET_RE.search`) by driving four adversarial bullet inputs
end-to-end through `/lp-scaffold-stack` and asserting:

  1. ASCII `<script>alert(1)</script>` — rejected `forbidden_bullet_token`
  2. Triple-backtick code-fence (```bash; rm -rf /```) — rejected
     `forbidden_bullet_token`
  3. FULLWIDTH `＜script＞` (NFKC confusable, mutation #10 from Phase 5) —
     rejected `forbidden_bullet_token` POST-§10 PATCH (NFKC normalize before
     match makes the FULLWIDTH less-than/greater-than collapse to literal
     `<`/`>` which the existing regex catches)
  4. RTL-override character `‮` (U+202E) — rejected via the
     `_has_dangerous_unicode` defense-in-depth check on the pick-stack side
     (which DOES NFKC-normalize in `_has_dangerous_unicode` per
     `rationale_summary_extractor.py`); on the scaffold-stack side the §4
     validator does not gate dangerous-unicode bullets directly — the
     bullets are stored as supplied and rejected only if they trip
     `_FORBIDDEN_BULLET_RE` after NFKC normalization. Because U+202E is
     itself a Cf-category (format) character, NFKC normalization preserves
     it as-is — so this case is rejected via the `_has_dangerous_unicode`
     pick-stack gate, NOT via the scaffold-stack regex. Phase 7's §4.4
     verifies the pick-stack gate by calling
     `rationale_summary_extractor.extract_summary()` directly.

Per Phase 7 handoff §4.4 final paragraph: "It MUST PASS after the patch is
applied; it MUST FAIL on the unpatched Phase 3 code." This is the
acceptance criterion for the §10 surgical patch.

Stub-mode default (handoff §4.10): we drive the CLI for cases 1-3 (fast,
no real-tool spawn) and call the pick-stack helper directly for case 4.
Total runtime budget: <5s.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash  # noqa: E402

from _phase5_decision_builder import (  # noqa: E402
    STACK_COMBOS,
    build_decision,
    write_decision_to_cwd,
    write_first_run_marker,
    write_matching_rationale_md,
)
from lp_pick_stack.rationale_summary_extractor import (  # noqa: E402
    _has_dangerous_unicode,
    extract_summary,
)
from scaffold_smoke_runner import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
    DEFAULT_SCAFFOLDERS_YML,
    PLUGIN_SCAFFOLD_STACK,
    _read_latest_rejection,
)


def _make_tempdir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="lp-joint-sanitize-"))
    os.chmod(d, 0o700)
    return d


def _re_seal(payload: dict) -> dict:
    payload.pop("sha256", None)
    payload["sha256"] = canonical_hash(payload)
    return payload


def _build_decision_with_bullet(cwd: Path, bullet: str) -> Path:
    """Build a sealed decision whose `rationale_summary[0].bullets` contains
    the adversarial bullet. Returns the decision path.

    The bullet is intentionally NOT also placed in rationale.md — the
    scaffold-stack validator only checks `rationale_summary` bullets at
    read-time (§4 rule 7), so the adversarial input is the bullet itself.
    """
    spec = STACK_COMBOS["A"]
    decision = build_decision(
        spec["stack_combo"], cwd,
        monorepo=spec["monorepo"],
        matched_category_id=spec["matched_category_id"],
    )
    decision["rationale_summary"][0]["bullets"] = [bullet]
    decision["nonce"] = uuid.uuid4().hex
    decision["generated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ",
    )
    _re_seal(decision)
    return write_decision_to_cwd(decision, cwd)


def _invoke_cli(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, str(PLUGIN_SCAFFOLD_STACK),
            "--cwd", str(cwd),
            "--scaffolders-yml", str(DEFAULT_SCAFFOLDERS_YML),
            "--category-patterns-yml", str(DEFAULT_CATEGORY_PATTERNS_YML),
            "--plugins-root", str(DEFAULT_PLUGINS_ROOT),
            "--no-telemetry",
        ],
        capture_output=True, timeout=60, check=False,
    )


@pytest.fixture
def adversarial_cwd():
    """Per-test tempdir with a Test A baseline decision pre-built; the test
    body mutates the decision's bullets and re-seals before invoking the CLI."""
    cwd = _make_tempdir()
    spec = STACK_COMBOS["A"]
    decision = build_decision(
        spec["stack_combo"], cwd,
        monorepo=spec["monorepo"],
        matched_category_id=spec["matched_category_id"],
    )
    write_decision_to_cwd(decision, cwd)
    write_matching_rationale_md(decision, cwd)
    write_first_run_marker(cwd)
    yield cwd
    shutil.rmtree(cwd, ignore_errors=True)


@pytest.mark.parametrize(
    "case_name,bullet",
    [
        ("ascii_script_tag", "Try this: <script>alert(1)</script>"),
        ("code_fence_rce", "Run this: ```bash; rm -rf /```"),
        ("nfkc_fullwidth_script",
         "FULLWIDTH bullet: ＜script＞alert(1)＜/script＞"),
    ],
)
def test_adversarial_bullet_rejected(case_name, bullet, adversarial_cwd):
    """Three adversarial bullets all trip `forbidden_bullet_token`.

    `nfkc_fullwidth_script` is the Phase 5 mutation #10 case — only passes
    after the §10 patch (NFKC-normalize before regex match).
    """
    cwd = adversarial_cwd
    _build_decision_with_bullet(cwd, bullet)
    rv = _invoke_cli(cwd)
    assert rv.returncode != 0, (
        f"[{case_name}] CLI accepted adversarial bullet (expected reject): "
        f"stdout={rv.stdout!r}, stderr={rv.stderr!r}"
    )
    rejection = _read_latest_rejection(cwd)
    assert rejection is not None, (
        f"[{case_name}] no scaffold-rejection-*.jsonl written under "
        f"{cwd}/.harness/observations/"
    )
    assert rejection.get("reason") == "forbidden_bullet_token", (
        f"[{case_name}] reason mismatch: expected 'forbidden_bullet_token', "
        f"got {rejection.get('reason')!r}; full rejection={rejection!r}"
    )
    # No scaffold-receipt should be written (validation rejected before Step 5a).
    assert not (cwd / ".launchpad" / "scaffold-receipt.json").exists(), (
        f"[{case_name}] scaffold-receipt was written despite rejection"
    )


def test_rtl_override_caught_by_pick_stack_helper():
    """RTL-override character (U+202E) — caught defense-in-depth by the
    pick-stack-side `_has_dangerous_unicode` Cf-category check.

    The scaffold-stack §4 regex does NOT catch U+202E directly (it matches
    URL/HTML/code-fence tokens only); the pick-stack-side
    `rationale_summary_extractor` would have FILTERED the bullet OUT before
    it ever reached the decision file. This test exercises the pick-stack
    gate to confirm the layered defense holds.
    """
    rtl = "Right-to-left bullet ‮ with RTL override"
    assert _has_dangerous_unicode(rtl), (
        "_has_dangerous_unicode failed to flag U+202E (RTL override)"
    )
    # Confirm the extractor drops the bullet entirely (not just rewrites).
    cwd = _make_tempdir()
    try:
        rationale = cwd / "rationale.md"
        rationale.write_text(
            "## project-understanding\n"
            f"- {rtl}\n"
            "- A clean bullet that should survive\n",
            encoding="utf-8",
        )
        summary = extract_summary(rationale)
        understanding = next(
            s for s in summary if s["section"] == "project-understanding"
        )
        assert "RTL override" not in str(understanding["bullets"]), (
            f"RTL-override bullet leaked through the extractor: "
            f"{understanding['bullets']!r}"
        )
        assert "clean bullet" in str(understanding["bullets"]).lower(), (
            f"clean bullet was unexpectedly dropped: "
            f"{understanding['bullets']!r}"
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_extractor_drops_nfkc_confusable_bullets():
    """Defense-in-depth: the pick-stack `extract_summary` ALSO drops the
    NFKC-confusable bullet (it would have been filtered before it could
    appear in `scaffold-decision.json.rationale_summary`).

    This is the BELT in the belt-and-braces sanitization layering: pick-stack
    (write side) drops the bullet; scaffold-stack (read side, post-§10 patch)
    would also reject if a hostile actor bypassed the pick-stack and wrote
    the decision file directly.
    """
    cwd = _make_tempdir()
    try:
        rationale = cwd / "rationale.md"
        rationale.write_text(
            "## project-understanding\n"
            "- ＜script＞confusable＜/script＞ should drop\n"
            "- A clean bullet that should survive\n",
            encoding="utf-8",
        )
        summary = extract_summary(rationale)
        understanding = next(
            s for s in summary if s["section"] == "project-understanding"
        )
        joined = " ".join(understanding["bullets"])
        assert "script" not in joined.lower() or "confusable" not in joined, (
            f"NFKC confusable bullet leaked through extractor: "
            f"{understanding['bullets']!r}"
        )
        assert "clean bullet" in joined.lower(), (
            f"clean bullet was unexpectedly dropped: "
            f"{understanding['bullets']!r}"
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
