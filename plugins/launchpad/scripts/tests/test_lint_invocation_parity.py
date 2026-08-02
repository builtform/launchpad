"""Ruff classification must not depend on how ruff was invoked.

INCIDENT (2026-08-01). CLAUDE.md's Python Definition of Done documented
`cd plugins/launchpad/scripts && ruff check .`; CI lints from the repo root
with an explicit `--config`. Same ruff (0.16.0 pinned), same tree, opposite
verdicts: the repo-root form passed while the cd-in form reported 13 I001
findings. An agent executing the DoD verbatim during v2.1.11 release
verification hit it and came within one step of "fixing" nine files CI had
already accepted. At v2.1.10 the same invocation reported 151 findings, so
the drift was at least two releases old.

MECHANISM. Ruff anchors first-party import detection (`src`, feeding
isort/I001) at the PROJECT ROOT. Under config discovery that is the directory
containing pyproject.toml; when `--config <path>` is passed it becomes the
PROCESS WORKING DIRECTORY. So the cwd is a symptom and `--config` is the
variable: two invocations from the same directory disagree if one passes it.

FIX. `[tool.ruff.lint.isort] known-first-party` enumerates the package's own
top-level names. A literal name list is consulted before any path resolution,
so it is immune to `src`, to the cwd, and to `--config` alike. A multi-valued
`src` was measured to produce an identical sort at one line instead of
seventeen, but post-sort it reports findings on a clean tree from a third
cwd, relocating the incident rather than removing it.

NOTE ON THIS FILE. `plugins/launchpad/scripts/tests/` is excluded from ruff
(`pyproject.toml` extend-exclude), from bandit, and from the lefthook ruff
hooks, so the file enforcing lint hygiene is not itself linted. It asserts
only about the linted surface.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

# tests/ live at plugins/launchpad/scripts/tests/, so the repo root is 4 up.
# Resolve by locating a known repo-root marker rather than trusting the count:
# this repo has a documented history of a parents[N] off-by-one.
_SCRIPTS = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SCRIPTS.parents[2]
_PYPROJECT = _SCRIPTS / "pyproject.toml"
_REQUIREMENTS_IN = _SCRIPTS / "requirements.in"

# Excluded from the first-party enumeration. `__pycache__` is a valid Python
# identifier so it survives the isidentifier() filter and must be named here.
_NOT_FIRST_PARTY = {"_vendor", "tests", "__pycache__"}

# `tomllib` is stdlib from 3.11. pyproject pins target-version = "py311" and
# CI runs 3.13, so the bare import is safe. (plugin-stack-detector.py carries a
# `tomli` fallback shim for scripts invoked under a bare `python3`; that does
# not apply to the pytest environment, which is the pinned interpreter.)


def _ruff_available() -> bool:
    """House probe form (cf. test_astro_walk_scope_v214.py)."""
    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "--version"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


_RUFF_MISSING = not _ruff_available()
_SKIP_REASON = "ruff not importable via sys.executable -m ruff"

# Never skip in CI: this guard is the only thing standing between the repo and
# a silent return of the incident, and a skip is invisible under `pytest -q`.
if _RUFF_MISSING and os.environ.get("CI"):
    raise RuntimeError(
        "ruff is not importable but CI is set; the lint-parity guard cannot be skipped in CI"
    )


def _load_ruff_config() -> dict:
    with _PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["tool"]["ruff"]


def _filesystem_first_party() -> set[str]:
    """Top-level importable names of this package, by filesystem shape.

    Criterion: importable by that top-level name from linted code. NOT
    "is it lint-excluded", which is an orthogonal axis: extend-exclude
    selects which FILES ruff lints, while known-first-party classifies an
    import NAME wherever it appears in any linted file.
    """
    modules = {p.stem for p in _SCRIPTS.glob("*.py") if p.stem.isidentifier()}
    packages = {
        d.name
        for d in _SCRIPTS.iterdir()
        if d.is_dir() and (d / "__init__.py").exists() and d.name not in _NOT_FIRST_PARTY
    }
    return modules | packages


def _run_ruff(cwd: Path, args: list[str], cache_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "RUFF_CACHE_DIR": str(cache_dir)}
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


@pytest.fixture(scope="module")
def ruff_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scoped so the cells share one cache.

    Not function-scoped: that would force a cold full-tree lint per cell.
    Not the repo's own .ruff_cache: CI_CD.md records that ruff write-locks it,
    which is why lefthook serialises its two ruff hooks, and a concurrent
    commit-and-push across worktrees would race.
    """
    return tmp_path_factory.mktemp("ruff-cache")


@pytest.fixture(scope="module")
def third_cwd(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A cwd that is NOT an ancestor of the repo.

    Ancestry is a property of the (cwd, tree) PAIR, never of a directory name.
    Two live counterexamples from this fix's own development: `/tmp` resolves
    to `/private/tmp` on macOS and is an ancestor of scratch trees created
    there, and `$HOME` is an ancestor of a repo checked out beneath it (as on
    CI, where HOME=/home/runner sits above /home/runner/work/). Both produced
    a false PASS. The assertion below is why this cell cannot silently go
    inert.
    """
    d = tmp_path_factory.mktemp("third-cwd").resolve()
    assert not _REPO_ROOT.resolve().is_relative_to(d), (
        f"third-cwd cell is inert: {d} is an ancestor of {_REPO_ROOT}, so a "
        "cwd-anchored per-file-ignores pattern would still match and the cell "
        "could not fail. Choose a cwd outside the repo's ancestry."
    )
    return d


def _cells(third: Path) -> dict[str, tuple[Path, list[str]]]:
    """The invocation forms that exist, plus one that must stay equivalent."""
    return {
        # Verbatim CI: .github/workflows/v2-handshake-lint.yml
        "ci-form": (_REPO_ROOT, ["check", "--config", str(_PYPROJECT), str(_SCRIPTS)]),
        # Verbatim CLAUDE.md / AGENTS.md Definition of Done
        "dod-form": (_SCRIPTS, ["check", "."]),
        # Not a form anyone runs today. It is the only cell that catches a
        # cwd-anchored per-file-ignores key or a revert to `src` inference.
        "third-cwd": (third, ["check", "--config", str(_PYPROJECT), str(_SCRIPTS)]),
    }


def _findings(proc: subprocess.CompletedProcess[str]) -> set[tuple[str, str, int, int]]:
    """Normalised finding set.

    `filename` is absolute and identical across cells (measured), so it needs
    no path normalisation. `code` is null for syntax errors, so it is coerced
    before entering a set that gets sorted in a failure message.
    """
    payload = json.loads(proc.stdout or "[]")
    return {
        (
            f["filename"],
            f.get("code") or "SYNTAX",
            f["location"]["row"],
            f["location"]["column"],
        )
        for f in payload
    }


@pytest.mark.skipif(_RUFF_MISSING, reason=_SKIP_REASON)
def test_ruff_pin_matches_requirements() -> None:
    """The parity result is only authoritative under the pinned ruff.

    CI and lefthook both invoke a bare `ruff` from PATH while this file uses
    `sys.executable -m ruff`. If those resolve to different binaries, the
    guard proves parity for something the gates do not run.
    """
    pinned = re.search(r"^ruff==([\d.]+)", _REQUIREMENTS_IN.read_text(), re.M)
    assert pinned, "no ruff==<version> pin found in requirements.in"
    reported = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout
    assert pinned.group(1) in reported, (
        f"ruff version mismatch: requirements.in pins {pinned.group(1)}, "
        f"`python -m ruff` reports {reported.strip()!r}. Every finding count "
        "in this suite is version-specific."
    )


@pytest.mark.slow
@pytest.mark.skipif(_RUFF_MISSING, reason=_SKIP_REASON)
def test_ruff_classification_is_invocation_independent(
    ruff_cache: Path, third_cwd: Path
) -> None:
    """Every invocation form must resolve the same first-party classification.

    Two assertions, deliberately separate. The settings comparison is the
    primary one because it is non-vacuous on a clean tree: a finding-set
    comparison post-fix is `set() == set()` and would pass even if
    classification had diverged.
    """
    cells = _cells(third_cwd)
    settings: dict[str, str] = {}
    for name, (cwd, args) in cells.items():
        proc = _run_ruff(cwd, [*args, "--show-settings"], ruff_cache)
        block = re.search(r"linter\.isort\.known_modules = \{.*?\n\}", proc.stdout, re.S)
        assert block, (
            f"could not read linter.isort.known_modules from `ruff --show-settings` "
            f"in cell {name!r}. `--show-settings` is a debug pretty-print with no "
            f"stability guarantee; if its format moved, re-verify parity by hand and "
            f"update this parser.\nstdout head:\n{proc.stdout[:400]}"
        )
        settings[name] = re.sub(r"\s+", " ", block.group(0))

    baseline = settings["ci-form"]
    # Non-empty guard: with `known-first-party` absent (a revert to `src`
    # inference) every cell resolves an empty map, and a bare equality
    # assertion would read `{} == {}` and pass on the reverted config.
    assert "=>" in baseline, (
        "known_modules resolved EMPTY in the ci-form cell: the "
        "[tool.ruff.lint.isort] known-first-party enumeration is not in "
        "effect, so classification has fallen back to cwd-dependent `src` "
        "inference. This is the incident condition."
    )
    for name in ("dod-form", "third-cwd"):
        assert settings[name] == baseline, (
            f"CLASSIFICATION DIVERGED between 'ci-form' and {name!r}.\n"
            f"  ci-form : {baseline}\n"
            f"  {name:8}: {settings[name]}\n"
            "Ruff is classifying this package's own modules differently "
            "depending on invocation form, which is the 2026-08-01 incident. "
            "Check that known-first-party is still present and that no `src` "
            "key was reintroduced."
        )

    findings = {
        name: _findings(_run_ruff(cwd, [*args, "--output-format=json"], ruff_cache))
        for name, (cwd, args) in cells.items()
    }
    ci = findings["ci-form"]
    for name in ("dod-form", "third-cwd"):
        assert findings[name] == ci, (
            f"PARITY BROKEN between 'ci-form' and {name!r}.\n"
            f"  only in ci-form : {sorted(ci - findings[name])}\n"
            f"  only in {name:8}: {sorted(findings[name] - ci)}\n"
            "The two invocations disagree about what is a violation. If the "
            "divergence is confined to the per-file-ignores files, a "
            "multi-segment glob key has been reintroduced; those keys anchor "
            "at the project root and stop matching from a non-ancestor cwd. "
            "Use bare basenames."
        )


@pytest.mark.skipif(_RUFF_MISSING, reason=_SKIP_REASON)
def test_known_first_party_matches_filesystem() -> None:
    """The enumeration is the cost of the fix; this keeps it honest."""
    ruff_cfg = _load_ruff_config()

    isort_cfg = ruff_cfg.get("lint", {}).get("isort", {})
    assert isort_cfg, "[tool.ruff.lint.isort] table is missing from pyproject.toml"
    configured = set(isort_cfg.get("known-first-party", []))
    # Guard the guard: two empty sets compare equal, so a renamed key read
    # through .get(..., []) would make the equality below vacuously true.
    assert configured, "known-first-party is missing or empty"

    on_disk = _filesystem_first_party()
    assert on_disk, "filesystem enumeration came back empty; the glob is stale"

    assert configured == on_disk, (
        "known-first-party has drifted from the filesystem.\n"
        f"  in config, not on disk: {sorted(configured - on_disk)}\n"
        f"  on disk, not in config: {sorted(on_disk - configured)}\n"
        "Add a newly-created top-level module or package to the list in "
        "pyproject.toml, or remove the stale entry. Note a new HYPHENATED "
        "plugin-*.py script needs no entry: it is not importable by that name."
    )

    # `src` must stay unset. With it set, any name NOT in the list above falls
    # back to path inference, which is anchor-dependent and re-splits.
    assert "src" not in ruff_cfg, (
        "[tool.ruff] src was reintroduced. Classification for any name absent "
        "from known-first-party would fall back to cwd-dependent inference."
    )


@pytest.mark.skipif(_RUFF_MISSING, reason=_SKIP_REASON)
def test_per_file_ignore_basenames_are_unique() -> None:
    """Bare basenames suppress on ANY file of that name in the linted surface.

    They are bare deliberately: a multi-segment key anchors at the project
    root, which under `--config` is the process cwd, so it silently stops
    matching from a non-ancestor cwd. The cost of that choice is this
    assertion.
    """
    per_file = _load_ruff_config().get("lint", {}).get("per-file-ignores", {})
    basenames = [k for k in per_file if "/" not in k]
    assert basenames, "expected bare-basename per-file-ignores keys; none found"

    for key in basenames:
        matches = [
            p
            for p in _SCRIPTS.rglob(key)
            if not any(part in _NOT_FIRST_PARTY for part in p.parts)
        ]
        assert len(matches) == 1, (
            f"per-file-ignores key {key!r} matches {len(matches)} files in the "
            f"linted surface: {[str(m.relative_to(_SCRIPTS)) for m in matches]}.\n"
            "A bare basename suppresses its rules on every match, so a "
            "same-named file elsewhere would silently inherit the suppression. "
            "Rename the new file, or narrow this key and re-measure parity "
            "from a non-ancestor cwd (multi-segment keys are cwd-anchored)."
        )


def test_no_top_level_module_shadows_stdlib() -> None:
    """Independent of the parity mechanism; cheap, and closes a real hole.

    A dozen-plus modules do `sys.path.insert(0, _SCRIPTS_DIR)`, putting this
    directory ahead of the stdlib PROCESS-WIDE for every subsequent import. A
    future top-level `secrets.py`, `token.py` or `hashlib.py` here would
    silently shadow the stdlib module inside the decision-hash and nonce
    paths.

    `sys.stdlib_module_names` reflects the RUNNING interpreter, so this cannot
    catch a module removed after the 3.11 floor (PEP 594 dropped ~19 in 3.13)
    when run on a newer one. Do not hardcode its size; it is version-specific.
    """
    collisions = sorted(_filesystem_first_party() & set(sys.stdlib_module_names))
    assert not collisions, (
        f"top-level module(s) shadow the stdlib: {collisions}.\n"
        "Because this directory is inserted at sys.path[0], these would take "
        "precedence over the stdlib for every import in the process, "
        "including inside security-relevant hashing and nonce code. Rename."
    )
