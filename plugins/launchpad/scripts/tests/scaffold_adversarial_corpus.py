"""Phase 5 adversarial corpus — 10 mutations of a valid Test A baseline.

Per Phase 5 handoff §4.7: each mutation must be hard-rejected by
`/lp-scaffold-stack`, and the resulting `scaffold-rejection-<ts>.<pid>.jsonl`
file must contain a `reason` field matching the EXACT value Phase 3 emits for
that failure mode. The 10 mutations cover the high-value attack surface from
HANDSHAKE §4 + §9.1.

The expected `reason` strings below are CROSS-CHECKED against Phase 3's
actual implementation (via the engine's `_emit_rejection` → `write_rejection`
path; see `lp_scaffold_stack/decision_validator.py` + `engine.py` Step 0/1):

  | # | Mutation                              | Expected `reason`                |
  |---|---------------------------------------|----------------------------------|
  | 1 | Mutate `sha256` last byte             | sha256_mismatch                  |
  | 2 | Replay nonce already in ledger        | nonce_seen                       |
  | 3 | Mismatched `bound_cwd.realpath`       | bound_cwd_realpath_mismatch      |
  | 4 | Mismatched `bound_cwd.st_ino`         | bound_cwd_inode_mismatch         |
  | 5 | `generated_at` 5 hours old            | generated_at_expired             |
  | 6 | Path-traversal layer (`../../etc/passwd`) | path_traversal               |
  | 7 | `stack: tauri` (deferred to v2.1)     | unknown_stack_id                 |
  | 8 | All-empty rationale_summary bullets   | rationale_summary_empty          |
  | 9 | Bullet contains raw `<script>`        | forbidden_bullet_token           |
  | 10| Bullet contains FULLWIDTH `＜script＞` | forbidden_bullet_token (post-§10 patch) |

Mutation #10 note (Phase 7 §10 patch applied):
  Phase 5 originally surfaced this as a Phase 3 contract gap and marked the
  test `xfail(strict=True)`. Phase 7 §10 applied the surgical NFKC-normalize
  patch in `decision_validator.py:243`, so the FULLWIDTH `＜script＞`
  confusable now normalizes to literal `<script>` BEFORE the regex match
  and trips the existing `forbidden_bullet_token` reason. The xfail
  decorator was removed; the historical finding observations at
  `.harness/observations/phase5-finding-mutation-10-nfkc-bypass-*.md` are
  intentionally LEFT IN PLACE as the patch's lineage record.

Per handoff §4.7: write ONE valid baseline decision per pytest session via
`@pytest.fixture(scope="session")`; clone+mutate per test (cuts setup ~80%).
Total runtime budget: <60s.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from decision_integrity import canonical_hash  # noqa: E402

from _phase5_decision_builder import (  # noqa: E402
    DEFAULT_RATIONALE_BODY,
    STACK_COMBOS,
    build_decision,
    write_decision_to_cwd,
    write_first_run_marker,
    write_matching_rationale_md,
)
from scaffold_smoke_runner import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
    DEFAULT_SCAFFOLDERS_YML,
    PLUGIN_SCAFFOLD_STACK,
    _read_latest_rejection,
)


# Phase 5 finding output path (handoff §10).
_FINDINGS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / ".harness" / "observations"
)


def _re_seal(payload: dict) -> dict:
    """Recompute and overwrite payload['sha256'] over canonical_hash(rest).

    Used by mutations #2 (replay), #5 (expired), #7-#10 (semantic) where the
    envelope must remain valid so the validator advances past sha256 check
    and trips on the semantic rule under test.
    """
    payload.pop("sha256", None)
    payload["sha256"] = canonical_hash(payload)
    return payload


def _invoke_cli_against(cwd: Path) -> subprocess.CompletedProcess:
    """Run plugin-scaffold-stack.py against `cwd`, capturing stderr/exit."""
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


# --- Session-scoped baseline ----------------------------------------------

@pytest.fixture(scope="session")
def baseline_decision_template():
    """Build ONE valid Test A decision payload at session scope; tests CLONE
    this dict and mutate per-test. Cuts the per-test build cost ~80% per
    handoff §4.7 line 411."""
    # We can't bind bound_cwd at session scope (each test has its own tmpdir),
    # so we build a TEMPLATE without bound_cwd; tests rebuild bound_cwd +
    # re-seal sha256 for their own tempdir.
    spec = STACK_COMBOS["A"]
    # Build a throwaway decision against /tmp to get the schema shape; tests
    # discard the bound_cwd field and rebuild.
    throwaway_dir = Path(tempfile.mkdtemp(prefix="lp-scaffold-test-baseline-"))
    try:
        decision = build_decision(
            spec["stack_combo"], throwaway_dir,
            monorepo=spec["monorepo"],
            matched_category_id=spec["matched_category_id"],
        )
    finally:
        shutil.rmtree(throwaway_dir, ignore_errors=True)
    # Strip bound_cwd + sha256; tests will rebuild for their own tempdir.
    decision.pop("bound_cwd", None)
    decision.pop("sha256", None)
    return decision


def _per_test_setup(
    baseline: dict,
    *,
    skip_marker: bool = False,
    skip_rationale: bool = False,
) -> Path:
    """Create a fresh tempdir, clone baseline, rebind bound_cwd, write all the
    .launchpad/ artifacts. Returns the tempdir path."""
    cwd = Path(tempfile.mkdtemp(prefix="lp-scaffold-test-adv-"))
    os.chmod(cwd, 0o700)
    decision = copy.deepcopy(baseline)
    real = os.path.realpath(str(cwd))
    st = os.stat(real)
    decision["bound_cwd"] = {
        "realpath": real, "st_dev": int(st.st_dev), "st_ino": int(st.st_ino),
    }
    # Fresh nonce per test so we never collide with another test's ledger entry.
    decision["nonce"] = uuid.uuid4().hex
    decision["generated_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ",
    )
    _re_seal(decision)
    write_decision_to_cwd(decision, cwd)
    if not skip_rationale:
        write_matching_rationale_md(decision, cwd)
    if not skip_marker:
        write_first_run_marker(cwd)
    return cwd


def _write_finding(slug: str, body: str) -> Path | None:
    """Write a phase5-finding-<ts>.md observation per handoff §10. Best-effort;
    silently swallow if .harness/observations/ unwritable."""
    try:
        _FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        target = _FINDINGS_DIR / f"phase5-finding-{slug}-{ts}.md"
        target.write_text(body, encoding="utf-8")
        return target
    except OSError:
        return None


def _assert_rejected_with(cwd: Path, expected_reason: str) -> dict:
    """Invoke CLI, assert non-zero exit + scaffold-rejection-<ts>.jsonl with
    expected reason. Returns the rejection payload for further assertions."""
    rv = _invoke_cli_against(cwd)
    assert rv.returncode != 0, (
        f"CLI accepted mutated decision (expected reject): "
        f"stdout={rv.stdout!r}, stderr={rv.stderr!r}"
    )
    rejection = _read_latest_rejection(cwd)
    assert rejection is not None, (
        f"no scaffold-rejection-*.jsonl written under {cwd}/.harness/observations/"
    )
    actual = rejection.get("reason")
    assert actual == expected_reason, (
        f"reason mismatch: expected {expected_reason!r}, got {actual!r}; "
        f"full rejection={rejection!r}"
    )
    return rejection


# --- Mutations #1 through #10 ----------------------------------------------

def test_mutation_01_sha256_byte_flip(baseline_decision_template):
    """Flip last byte of `sha256` envelope — Phase 3 should reject with
    `sha256_mismatch`."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        # Read the on-disk decision, flip last sha256 byte, write back.
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        sha = decision["sha256"]
        flipped = sha[:-1] + ("0" if sha[-1] != "0" else "1")
        decision["sha256"] = flipped
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "sha256_mismatch")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_02_nonce_replay(baseline_decision_template):
    """Pre-seed `.scaffold-nonces.log` with the decision's nonce → Phase 3
    rejects with `nonce_seen` on read-side replay check."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        # Read decision to get the nonce.
        decision = json.loads(
            (cwd / ".launchpad" / "scaffold-decision.json").read_text(
                encoding="utf-8",
            ),
        )
        nonce = decision["nonce"]
        # Use the nonce_ledger module to seed the ledger correctly (header +
        # 33-byte record).
        from lp_scaffold_stack.nonce_ledger import append_nonce
        append_nonce(nonce, cwd)
        _assert_rejected_with(cwd, "nonce_seen")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_03_bound_cwd_realpath_mismatch(baseline_decision_template):
    """Set `bound_cwd.realpath` to a different path → Phase 3 rejects with
    `bound_cwd_realpath_mismatch` (both realpath AND inode mismatch).

    Per Phase 3's `_validate_bound_cwd`: if realpath differs AND inode
    differs, fires `bound_cwd_realpath_mismatch`. If realpath differs but
    inode matches, fires `bound_cwd_realpath_changed_inode_match` (UX case).
    Mutation #3 changes realpath to `/tmp` which has a different inode →
    expect `bound_cwd_realpath_mismatch`.
    """
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        # Use /tmp itself as the mismatched realpath — its inode WILL differ
        # from cwd's, so the validator fires `bound_cwd_realpath_mismatch`
        # (NOT `bound_cwd_realpath_changed_inode_match`).
        decision["bound_cwd"] = {
            "realpath": os.path.realpath("/tmp"),
            "st_dev": 99999, "st_ino": 99999,
        }
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "bound_cwd_realpath_mismatch")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_04_bound_cwd_inode_mismatch(baseline_decision_template):
    """Keep `bound_cwd.realpath` correct but mutate `st_ino` → Phase 3
    rejects with `bound_cwd_inode_mismatch` (symlink-swap attack signal)."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        # Real realpath, but bogus st_ino — fires inode_mismatch branch.
        decision["bound_cwd"]["st_ino"] = decision["bound_cwd"]["st_ino"] ^ 0xFFFF
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "bound_cwd_inode_mismatch")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_05_generated_at_expired(baseline_decision_template):
    """Set `generated_at` 5 hours in the past → Phase 3 rejects with
    `generated_at_expired` (>4h replay window per HANDSHAKE §4 rule 9)."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        decision["generated_at"] = old.strftime("%Y-%m-%dT%H:%M:%SZ")
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "generated_at_expired")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_06_path_traversal(baseline_decision_template):
    """Layer with `path: "../../etc/passwd"` → Phase 3 rejects with
    `path_traversal` per HANDSHAKE §6 path validator."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["layers"][0]["path"] = "../../etc/passwd"
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "path_traversal")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_07_unknown_stack_id(baseline_decision_template):
    """`stack: tauri` is deferred to v2.1 per HANDSHAKE §11; v2.0 scaffolders.yml
    does NOT list it → Phase 3 rejects with `unknown_stack_id`."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["layers"][0]["stack"] = "tauri"
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "unknown_stack_id")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_08_rationale_summary_empty(baseline_decision_template):
    """All rationale_summary bullets empty → Phase 3 rejects with
    `rationale_summary_empty` (HANDSHAKE §4 rule 7)."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["rationale_summary"] = [
            {"section": s, "bullets": []}
            for s in (
                "project-understanding", "matched-category", "stack",
                "why-this-fits", "alternatives", "notes",
            )
        ]
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "rationale_summary_empty")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_09_forbidden_bullet_token(baseline_decision_template):
    """Bullet contains raw `<script>` → Phase 3 rejects with
    `forbidden_bullet_token` (HANDSHAKE §9.1 sanitization)."""
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["rationale_summary"][0]["bullets"] = ["A bullet with <script>alert(1)</script>"]
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "forbidden_bullet_token")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def test_mutation_10_forbidden_bullet_unicode(baseline_decision_template):
    """Bullet contains FULLWIDTH `＜script＞` (U+FF1C/FF1E NFKC confusables) →
    Phase 3 (post-Phase 7 §10 patch) NFKC-normalizes the bullet BEFORE
    `_FORBIDDEN_BULLET_RE.search`, so the confusable normalizes to literal
    `<script>` and trips the existing `forbidden_bullet_token` reason.

    Phase 5 originally surfaced this case as `xfail(strict=True)`; the
    Phase 7 §10 surgical patch (`unicodedata.normalize("NFKC", bullet)`)
    closes the bypass. The historical finding observation files at
    `.harness/observations/phase5-finding-mutation-10-nfkc-bypass-*.md`
    are intentionally LEFT IN PLACE per Phase 7 handoff §10 patch checklist
    — they document the contract patch's lineage.
    """
    cwd = _per_test_setup(baseline_decision_template)
    try:
        decision_path = cwd / ".launchpad" / "scaffold-decision.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        # FULLWIDTH LESS-THAN (U+FF1C) + GREATER-THAN (U+FF1E) — these NFKC-
        # normalize to U+003C / U+003E, hitting the regex that previously
        # only saw raw bytes.
        decision["rationale_summary"][0]["bullets"] = [
            "A bullet with ＜script＞alert(1)＜/script＞",
        ]
        _re_seal(decision)
        decision_path.write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _assert_rejected_with(cwd, "forbidden_bullet_token")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


# Cross-check that the rationale baseline body matches what the validator
# expects (sanity guard against drift between this corpus and the builder).
def test_baseline_rationale_body_consistent():
    assert "## project-understanding" in DEFAULT_RATIONALE_BODY
    assert "## matched-category" in DEFAULT_RATIONALE_BODY
    assert "## stack" in DEFAULT_RATIONALE_BODY
    assert "## why-this-fits" in DEFAULT_RATIONALE_BODY
    assert "## alternatives" in DEFAULT_RATIONALE_BODY
    assert "## notes" in DEFAULT_RATIONALE_BODY
