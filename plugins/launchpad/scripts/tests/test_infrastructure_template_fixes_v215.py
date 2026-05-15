"""Tests for v2.1.5 infrastructure-template fixes:

BL-334: CODEOWNERS placeholder substitution (PII-opt-out path).
BL-335: compound-learning.sh no longer hard-deps on prd.json.
BL-339: lefthook EOF-newline hook excludes canonical sealed envelopes.
BL-343: .github/dependabot.yml rendered to project root.
BL-344: .github/pull_request_template.md rendered to project root.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plugin_default_generators.infrastructure_renderer import (  # noqa: E402
    InfrastructureRenderer,
)


_IDENTITY = {
    "project_name": "test-proj",
    "email": "owner@example.com",
    "repo_url": "https://github.com/test-org/test-proj",
    "license": "MIT",
    # v2.1.5 round-3 review fix B1: valid CODEOWNERS owner-token shape
    # (`@user` or `@org/team`), not a bare display name.
    "copyright_holder": "@real-org/real-team",
}

_IDENTITY_PII_OPT_OUT = {**_IDENTITY, "copyright_holder": "<copyright-holder>"}

# v2.1.5 round-3 review fix B1: a bare display name passes the placeholder
# gate but is NOT a valid GitHub CODEOWNERS token.
_IDENTITY_BARE_NAME = {**_IDENTITY, "copyright_holder": "Foad Shafighi"}

# v2.1.5 round-3 review fix C1: trailing-whitespace must not bypass the
# placeholder gate.
_IDENTITY_PLACEHOLDER_TRAILING_WS = {
    **_IDENTITY,
    "copyright_holder": "<copyright-holder>  ",
}


# ---------------------------------------------------------------------------
# BL-334: CODEOWNERS placeholder substitution
# ---------------------------------------------------------------------------


def test_bl334_codeowners_emits_owner_when_set() -> None:
    """When copyright_holder is a real GitHub owner-token (`@user` or
    `@org/team`), render `* <holder>` wrapped in LaunchPad-managed
    sentinels per B11."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string("github/CODEOWNERS.j2", _IDENTITY)
    assert "* @real-org/real-team" in out
    assert "TODO:" not in out
    # B11: LaunchPad-managed sentinel comments wrap the owner line so
    # apply_append_only on a brownfield project is visually distinct.
    assert "LaunchPad-managed default owner" in out
    assert "end LaunchPad-managed default owner" in out


def test_bl334_codeowners_emits_todo_on_pii_opt_out() -> None:
    """When copyright_holder is the literal placeholder, emit a TODO
    line that references the interactive `/lp-update-identity` prompt
    (NOT a fake `--copyright-holder` CLI flag — A4 fix)."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string("github/CODEOWNERS.j2", _IDENTITY_PII_OPT_OUT)
    assert "<copyright-holder>" not in out, (
        "BL-334: rendered CODEOWNERS must not ship the literal placeholder"
    )
    assert "TODO" in out
    # A4: TODO references the real recovery path (interactive prompt #3),
    # NOT the nonexistent `--copyright-holder` CLI flag.
    assert "/lp-update-identity" in out
    assert "interactive prompt" in out
    assert "copyright_holder" in out
    assert "--copyright-holder" not in out, (
        "A4: `--copyright-holder` is not a real CLI flag of /lp-update-identity"
    )


def test_b1_codeowners_rejects_bare_display_name() -> None:
    """B1 regression: a copyright_holder like `Foad Shafighi` passes the
    placeholder gate but is NOT a valid GitHub CODEOWNERS owner token.
    Emit TODO branch instead of a broken `* Foad Shafighi` line that
    GitHub would silently ignore."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string("github/CODEOWNERS.j2", _IDENTITY_BARE_NAME)
    # No broken owner line.
    assert "* Foad Shafighi" not in out
    # TODO branch fires.
    assert "TODO" in out
    assert "interactive prompt" in out


def test_c1_codeowners_trailing_whitespace_does_not_bypass_gate() -> None:
    """C1 regression: `<copyright-holder>  ` (trailing whitespace) must
    NOT slip past the placeholder gate. `|trim` filter is the fix."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string(
        "github/CODEOWNERS.j2", _IDENTITY_PLACEHOLDER_TRAILING_WS
    )
    # Placeholder string must be detected even with trailing whitespace
    # — TODO branch fires, no owner line emitted.
    assert "* <copyright-holder>" not in out
    assert "TODO" in out


# ---------------------------------------------------------------------------
# BL-335: compound-learning.sh tolerant of missing prd.json
# ---------------------------------------------------------------------------


def test_bl335_compound_learning_no_longer_hard_deps_prd_json() -> None:
    """The rendered script should reference PRD.md / scaffold-receipt.json
    (the canonical LaunchPad artifacts) and not exit early on missing
    prd.json. Hand-authored prd.json remains an optional override."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string(
        "scripts/compound/compound-learning.sh.j2", _IDENTITY
    )
    # The script should still know about prd.json (as optional override).
    assert "PRD_JSON_FILE" in out
    # The legacy "No prd.json found. Nothing to extract." early-exit must
    # be gone — we exit only on missing progress.txt.
    assert "No progress.txt found" in out
    # No early-exit on missing prd.json.
    assert "No prd.json found" not in out


# ---------------------------------------------------------------------------
# BL-339: lefthook EOF-newline hook excludes canonical envelopes
# ---------------------------------------------------------------------------


def test_bl339_lefthook_excludes_scaffold_envelopes() -> None:
    """The rendered lefthook.yml's end-of-file-newline hook must include
    an exclude pattern for .launchpad/scaffold-{decision,receipt}.json
    so the EOF-newline gate doesn't reject LaunchPad's own canonical
    byte-deterministic JSON envelopes."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string("lefthook.yml.j2", _IDENTITY)
    # Find the end-of-file-newline hook block
    assert "end-of-file-newline:" in out
    # Verify the exclude pattern targets the scaffold envelopes
    assert "scaffold-decision" in out
    assert "scaffold-receipt" in out
    # The exclude line should be inside the EOF-newline hook block
    eof_idx = out.index("end-of-file-newline:")
    # The next ~10 lines must contain the exclude pattern
    window = out[eof_idx : eof_idx + 600]
    assert "exclude:" in window
    assert "scaffold-decision" in window
    assert "scaffold-receipt" in window


# ---------------------------------------------------------------------------
# BL-343: dependabot.yml render
# ---------------------------------------------------------------------------


def test_bl343_dependabot_yml_rendered_with_expected_shape() -> None:
    """The rendered dependabot.yml must follow the public-repo guide:
    weekly cadence, grouped minor/patch, PR limits."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string("github/dependabot.yml.j2", _IDENTITY)
    import yaml

    parsed = yaml.safe_load(out)
    assert parsed["version"] == 2
    updates = parsed["updates"]
    assert len(updates) == 2  # npm + github-actions
    ecosystems = [u["package-ecosystem"] for u in updates]
    assert "npm" in ecosystems
    assert "github-actions" in ecosystems
    for u in updates:
        assert u["schedule"]["interval"] == "weekly"
        assert u["schedule"]["day"] == "monday"
        assert "open-pull-requests-limit" in u
        assert "groups" in u
        assert "minor-and-patch" in u["groups"]


def test_bl343_dependabot_in_infrastructure_files() -> None:
    """The dependabot.yml target relpath must be in INFRASTRUCTURE_FILES
    so /lp-bootstrap renders it."""
    from lp_bootstrap import INFRASTRUCTURE_TARGETS

    assert ".github/dependabot.yml" in INFRASTRUCTURE_TARGETS


# ---------------------------------------------------------------------------
# BL-344: pull_request_template.md render
# ---------------------------------------------------------------------------


def test_bl344_pr_template_rendered_with_expected_sections() -> None:
    """The rendered PR template must include Summary / Changes / Test plan /
    Related sections (the universal narrow shape; per-stack checklists are
    downstream concern)."""
    renderer = InfrastructureRenderer()
    out = renderer.render_to_string("github/pull_request_template.md.j2", _IDENTITY)
    assert "## Summary" in out
    assert "## Changes" in out
    assert "## Test plan" in out
    assert "## Related" in out


def test_bl344_pr_template_in_infrastructure_files() -> None:
    """The pull_request_template.md target must be in INFRASTRUCTURE_FILES."""
    from lp_bootstrap import INFRASTRUCTURE_TARGETS

    assert ".github/pull_request_template.md" in INFRASTRUCTURE_TARGETS
