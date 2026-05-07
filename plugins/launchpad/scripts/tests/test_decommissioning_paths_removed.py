"""Phase 8 v2.1 (BL-247) decommission gate.

Locks the v0/v1 install + lp-pull-launchpad surface decommission so it
cannot regress: deleted paths must stay deleted; signpost stubs must keep
shape (chmod -x + exit 64); the seven *.template.* root files must not
reappear; the maintenance allowlist must run clean; no active workflow
or lefthook step may invoke a deleted script; the decommission audit log
must carry an entry per Phase 8 deletion; .gitignore must keep secret-
pattern entries intact.

Plan reference: docs/plans/launchpad_plans/2026-05-05-v2.1-phase8-implementation-plan.md §2.3.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

DELETED_PATHS_HARD = (
    "README.template.md",
    "CONTRIBUTING.template.md",
    "CODE_OF_CONDUCT.template.md",
    "SECURITY.template.md",
    "CHANGELOG.template.md",
    "ROADMAP.template.md",
    "greptile.template.json",
    "plugins/launchpad/scripts/tests/test_init_agents_yml.py",
)

SIGNPOST_STUB_PATHS = (
    "scripts/setup/init-project.sh",
    "scripts/setup/pull-upstream.launchpad.sh",
    "plugins/launchpad/commands/lp-pull-launchpad.md",
)

DELETED_OR_STUBBED = DELETED_PATHS_HARD + SIGNPOST_STUB_PATHS


@pytest.mark.parametrize("rel_path", DELETED_PATHS_HARD)
def test_hard_deleted_paths_absent(rel_path: str) -> None:
    target = REPO_ROOT / rel_path
    assert not target.exists(), (
        f"Phase 8 BL-247 decommissioned {rel_path}; it must not be re-introduced. "
        "If you need legacy v0/v1 behavior, pin to v2.0.x. See "
        "docs/maintainers/decommission-history.md."
    )


@pytest.mark.parametrize("rel_path", SIGNPOST_STUB_PATHS)
def test_signpost_stubs_have_decommission_shape(rel_path: str) -> None:
    target = REPO_ROOT / rel_path
    assert target.is_file(), f"Signpost stub missing at {rel_path}"
    body = target.read_text(encoding="utf-8")
    if rel_path.endswith(".sh"):
        assert "exit 64" in body, f"{rel_path} signpost stub must exit 64 (EX_USAGE)"
        assert "removed in v2.1" in body, (
            f"{rel_path} signpost stub must include the v2.1 removal message"
        )
        # chmod +x: signpost stubs are user-invokable on purpose so a
        # direct `./scripts/setup/init-project.sh` (per CLAUDE.md or any
        # prior doc reference) prints the v2.1 migration message instead
        # of failing with permission denied. The body just prints +
        # exit 64; being executable does not change the safety story.
        mode = target.stat().st_mode
        assert (mode & 0o111) != 0, (
            f"{rel_path} signpost stub must be executable (chmod +x); "
            f"current mode 0o{mode & 0o777:o}"
        )
    else:
        assert "Decommissioned in v2.1" in body, (
            f"{rel_path} stub must include the decommission marker"
        )


def test_no_template_files_at_root() -> None:
    matches = sorted(p.name for p in REPO_ROOT.glob("*.template.*"))
    permitted = {"LICENSE.template"}  # retained for kernel-renderer scaffolding
    leaked = [m for m in matches if m not in permitted]
    assert not leaked, (
        f"Unexpected *.template.* files at repo root: {leaked}. Phase 8 BL-247 "
        "decommissioned all such files except LICENSE.template. See "
        "docs/maintainers/decommission-history.md."
    )


def test_check_repo_structure_clean_post_decommission() -> None:
    script = REPO_ROOT / "scripts" / "maintenance" / "check-repo-structure.sh"
    result = subprocess.run(
        ["bash", str(script)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"check-repo-structure.sh must run clean post-Phase-8.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # Belt-and-braces: no warnings either.
    combined = result.stdout + result.stderr
    assert "❌" not in combined, f"check-repo-structure surfaced warnings:\n{combined}"


def _yaml_files(*globs: str) -> list[Path]:
    out: list[Path] = []
    for pattern in globs:
        out.extend(REPO_ROOT.glob(pattern))
    return out


WORKFLOWS = _yaml_files(".github/workflows/*.yml", ".github/workflows/*.yaml")
LEFTHOOK = REPO_ROOT / "lefthook.yml"

# Each (file, deleted_token) pair: every match against deleted_token in this
# file must live on a comment line; non-comment matches HALT (per plan §3.8
# active-code rule). Comments are permitted as historical context.
_REFERENCED_NAMES = (
    "init-project.sh",
    "pull-upstream.launchpad.sh",
    "lp-pull-launchpad",
)


@pytest.mark.parametrize("yml_path", WORKFLOWS + ([LEFTHOOK] if LEFTHOOK.is_file() else []))
def test_no_active_workflow_or_lefthook_invocation_of_deleted_scripts(
    yml_path: Path,
) -> None:
    text = yml_path.read_text(encoding="utf-8")
    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.lstrip()
        if stripped.startswith("#"):
            continue
        for token in _REFERENCED_NAMES:
            if token in raw_line:
                pytest.fail(
                    f"{yml_path.relative_to(REPO_ROOT)}:{line_num} contains "
                    f"non-comment reference to decommissioned token "
                    f"{token!r}: {raw_line.strip()!r}"
                )


def test_decommission_audit_log_seeded() -> None:
    audit_log = REPO_ROOT / "docs" / "maintainers" / "decommission-history.md"
    assert audit_log.is_file(), (
        "docs/maintainers/decommission-history.md must exist post-Phase-8 "
        "(audit-log lint rule extension is Phase 8.5 Slice E)."
    )
    body = audit_log.read_text(encoding="utf-8")
    # One row per deleted-or-stubbed path; row shape:
    #   | <date> | `<path>` | BL-247 | 8 | <reason> | <reviewer> | <replacement> |
    for rel_path in DELETED_OR_STUBBED:
        # Match the path inside backticks anywhere on a row that also mentions
        # BL-247 + Phase 8. We do NOT pin column ordering because prettier may
        # re-flow column widths.
        pattern = re.compile(
            rf"\|\s*[0-9-]+\s*\|\s*`{re.escape(rel_path)}`\s*\|\s*BL-247\s*\|\s*8\s*\|"
        )
        assert pattern.search(body), (
            f"docs/maintainers/decommission-history.md missing audit-log row "
            f"for Phase 8 path {rel_path!r}"
        )


_GITIGNORE_SECRET_PATTERN_ENTRIES = (".env", ".env.local", ".env.consultant")


def test_gitignore_protects_dotenv() -> None:
    gitignore = REPO_ROOT / ".gitignore"
    assert gitignore.is_file(), ".gitignore is required at repo root"
    body = gitignore.read_text(encoding="utf-8")
    lines = {
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    for entry in _GITIGNORE_SECRET_PATTERN_ENTRIES:
        assert entry in lines, (
            f".gitignore must keep the secret-pattern entry {entry!r} after "
            "Phase 8 deletions (harden security-lens P3 hard rule)."
        )
