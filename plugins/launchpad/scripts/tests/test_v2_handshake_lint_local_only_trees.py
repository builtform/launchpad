"""Guards the invariant that keeps LINT_SCAN_EXCLUDES safe.

`_walk_grep` filters on path prefix and knows nothing about tracked-ness, so
any file committed under an excluded tree ships publicly while remaining
invisible to `check_private_origin_leakage`. Greptile P2 on PR #149 flagged
this; the fix pairs the exclusion with `check_local_only_trees_untracked`.

These tests are written to be capable of failing. The positive case runs
against a real throwaway git repo with a real tracked file rather than
asserting `[] == []` on the clean worktree, which would pass no matter what
the checker did.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
LINT_SCRIPT = REPO_ROOT / "plugins" / "launchpad" / "scripts" / "plugin-v2-handshake-lint.py"


def _load_lint_module():
    spec = importlib.util.spec_from_file_location("v2_lint_local_only", LINT_SCRIPT)
    assert spec is not None and spec.loader is not None, (
        f"could not load lint module from {LINT_SCRIPT}"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v2_lint_local_only"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint_module()


def test_local_only_trees_are_a_subset_of_scan_excludes(lint):
    """Every local-only tree must actually be excluded from the scan.

    A tree in LOCAL_ONLY_TREES but not LINT_SCAN_EXCLUDES would be scanned,
    spilling a contributor's private working notes into CI stderr via `_emit`.
    """
    missing = [t for t in lint.LOCAL_ONLY_TREES if t not in lint.LINT_SCAN_EXCLUDES]
    assert not missing, (
        f"local-only trees absent from LINT_SCAN_EXCLUDES: {missing}. These "
        f"would be scanned, printing local file contents into CI logs."
    )


def _is_ignored(tree: str) -> bool:
    """Ask the ignore rules only.

    `git check-ignore` suppresses paths that are tracked, so without
    `--no-index` a gitignored tree carrying a stray tracked file reports as
    NOT ignored. That masks precisely the state these tests exist to detect.
    """
    return subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", tree],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
    ).returncode == 0


def test_local_only_trees_are_gitignored(lint):
    """A non-gitignored tree in this tuple would fail the lint the moment
    anyone legitimately committed to it."""
    for tree in lint.LOCAL_ONLY_TREES:
        assert _is_ignored(tree), (
            f"{tree} is in LOCAL_ONLY_TREES but is not gitignored. Either add "
            f"it to .gitignore or drop it from the tuple."
        )


def test_every_excluded_docs_tree_is_declared_local_only(lint):
    """No `docs/` tree may be excluded from the scan without being local-only.

    The general form of the bug. Excluding a tree that can carry committed
    files means those files ship unscanned; declaring it local-only is what
    brings `check_local_only_trees_untracked` to bear on it. Repo-tree
    excludes only, since build and cache dirs are never git-managed.
    """
    undeclared = [
        t
        for t in lint.LINT_SCAN_EXCLUDES
        if t.startswith("docs/") and t not in lint.LOCAL_ONLY_TREES
    ]
    assert not undeclared, (
        f"{undeclared} are skipped by the leakage scan but not declared in "
        f"LOCAL_ONLY_TREES, so nothing stops files being committed there and "
        f"shipping unscanned. Add them to LOCAL_ONLY_TREES (and .gitignore), "
        f"or drop them from LINT_SCAN_EXCLUDES."
    )


def test_articles_tree_stays_excluded(lint):
    """docs/articles/ holds private local research and personal writing
    material, so the scan must not read it. `_emit` prints matching lines, and
    a local hit would put that content on the contributor's terminal."""
    assert "docs/articles/" in lint.LINT_SCAN_EXCLUDES
    assert "docs/articles/" in lint.LOCAL_ONLY_TREES


def _git(repo: Path, *argv: str) -> None:
    subprocess.run(
        ["git", *argv], cwd=str(repo), check=True, capture_output=True, text=True
    )


@pytest.fixture(scope="module")
def repo_with_tracked_plan(tmp_path_factory):
    """A real git repo with a real tracked file under docs/plans/.

    Force-added past a .gitignore rule, which is exactly the bypass the
    checker exists to catch.
    """
    repo = tmp_path_factory.mktemp("tracked-plan-repo").resolve()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    (repo / ".gitignore").write_text("docs/plans/\n", encoding="utf-8")
    (repo / "docs" / "plans").mkdir(parents=True)
    (repo / "docs" / "plans" / "private.md").write_text(
        "a plan with no leakage markers at all\n", encoding="utf-8"
    )
    _git(repo, "add", ".gitignore")
    _git(repo, "add", "-f", "docs/plans/private.md")
    _git(repo, "commit", "-qm", "force-add a plan")
    return repo


def test_checker_flags_a_real_tracked_plan(lint, repo_with_tracked_plan, monkeypatch):
    """The positive case: a tracked plan must produce a failure."""
    monkeypatch.setattr(lint, "REPO_ROOT", repo_with_tracked_plan)
    failures: list[str] = []
    lint.check_local_only_trees_untracked(failures)

    joined = "\n".join(failures)
    assert failures, (
        "a force-added file under docs/plans/ produced no failure; the "
        "checker is not seeing tracked files"
    )
    assert "local-only-trees-untracked" in joined
    assert "docs/plans/private.md" in joined, (
        f"the offending path must be named so the failure is actionable; got:\n{joined}"
    )


def test_checker_catches_plans_with_no_leakage_markers(
    lint, repo_with_tracked_plan, monkeypatch
):
    """Why this is a tracked-file assertion and not a content scan.

    The content gate reports clean on this repo for two compounding reasons:
    docs/plans/ is excluded from the scan, and the fixture trips none of
    PRIVATE_ORIGIN_PATTERNS anyway. Either alone is enough. A private plan for
    an unrelated product is a leak regardless of which strings it contains, so
    only a tracked-file rule closes it.
    """
    monkeypatch.setattr(lint, "REPO_ROOT", repo_with_tracked_plan)

    content_failures: list[str] = []
    lint.check_private_origin_leakage(content_failures)
    assert not content_failures, (
        f"the content gate was expected to report clean here (that is the "
        f"whole point); it flagged: {content_failures}"
    )

    tracked_failures: list[str] = []
    lint.check_local_only_trees_untracked(tracked_failures)
    assert tracked_failures, (
        "the tracked-file gate must catch what the content gate cannot"
    )


def test_clean_repo_produces_no_failure(lint, tmp_path_factory, monkeypatch):
    """Negative control: same checker, same code path, nothing tracked."""
    repo = tmp_path_factory.mktemp("clean-repo").resolve()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    (repo / ".gitignore").write_text("docs/plans/\n", encoding="utf-8")
    (repo / "docs" / "plans").mkdir(parents=True)
    (repo / "docs" / "plans" / "local.md").write_text("local only\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "init")

    monkeypatch.setattr(lint, "REPO_ROOT", repo)
    failures: list[str] = []
    lint.check_local_only_trees_untracked(failures)
    assert not failures, (
        f"an untracked local plan must not fail the lint; got: {failures}"
    )


def test_checker_fails_closed_without_git(lint, tmp_path_factory, monkeypatch):
    """A non-repo cannot verify the invariant, so it must not report success."""
    not_a_repo = tmp_path_factory.mktemp("not-a-repo").resolve()
    monkeypatch.setattr(lint, "REPO_ROOT", not_a_repo)
    failures: list[str] = []
    lint.check_local_only_trees_untracked(failures)
    assert failures, (
        "git ls-files failing must surface as a failure, not a silent pass"
    )
    assert "cannot verify" in "\n".join(failures)


# ---------------------------------------------------------------------------
# check_no_local_plan_citations: plan PATHS are the same disclosure as plan
# CONTENT, at lower resolution. A filename publishes the existence, name, and
# date of private work, and cannot be opened from a fresh clone anyway.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def repo_with_citations(tmp_path_factory):
    """A tree exercising all four cases the two-tier rule must separate."""
    repo = tmp_path_factory.mktemp("citation-repo").resolve()
    (repo / "docs").mkdir()
    (repo / "plugins").mkdir()

    # Tier 1: LaunchPad's own plan tree, illegitimate anywhere.
    (repo / "docs" / "tier1.md").write_text(
        "See docs/plans/launchpad_plans/2026-05-04-v2.1-implementation-plan.md\n",
        encoding="utf-8",
    )
    # Tier 2: dated plan file cited from repo documentation.
    (repo / "docs" / "tier2.md").write_text(
        "Plan at docs/plans/2026-05-04-some-plan.md\n", encoding="utf-8"
    )
    # Legitimate: same dated form inside plugins/, describing downstream repos.
    (repo / "plugins" / "template.md").write_text(
        "Downstream plans live at `docs/plans/2025-01-08-improve-error-handling.md`\n",
        encoding="utf-8",
    )
    # Legitimate: bare directory, which is how the ignore policy is stated.
    (repo / "docs" / "policy.md").write_text(
        "`docs/plans/` is gitignored: local-only, never committed.\n",
        encoding="utf-8",
    )
    return repo


def _citation_hits(lint, repo, monkeypatch):
    monkeypatch.setattr(lint, "REPO_ROOT", repo)
    failures: list[str] = []
    lint.check_no_local_plan_citations(failures)
    return "\n".join(failures)


def test_flags_launchpad_plan_tree_citation(lint, repo_with_citations, monkeypatch):
    assert "tier1.md" in _citation_hits(lint, repo_with_citations, monkeypatch)


def test_flags_dated_plan_file_in_repo_docs(lint, repo_with_citations, monkeypatch):
    assert "tier2.md" in _citation_hits(lint, repo_with_citations, monkeypatch)


def test_allows_dated_example_inside_plugins(lint, repo_with_citations, monkeypatch):
    """Plugin templates teach downstream layout, where docs/plans/ is tracked.

    Without this carve-out the rule fires on lp-docs-locator.md teaching the
    naming convention, which is correct documentation and not a leak.
    """
    assert "template.md" not in _citation_hits(lint, repo_with_citations, monkeypatch)


def test_allows_bare_plans_directory(lint, repo_with_citations, monkeypatch):
    """The policy statement itself must not trip the policy's own guard."""
    assert "policy.md" not in _citation_hits(lint, repo_with_citations, monkeypatch)


def test_citation_failure_names_every_offender(lint, repo_with_citations, monkeypatch):
    """Two offenders, two reported: a rule that stops at the first hit turns a
    cleanup pass into a guessing game."""
    out = _citation_hits(lint, repo_with_citations, monkeypatch)
    assert "2 citation(s)" in out, out


def test_allowlist_covers_the_rule_s_own_implementation(lint):
    """The lint and these tests necessarily contain the pattern they forbid."""
    for path in lint.PLAN_CITATION_ALLOWLIST:
        assert (REPO_ROOT / path).exists(), (
            f"{path} is allowlisted but does not exist; a stale entry silently "
            f"widens the exemption if that path is ever recreated"
        )
