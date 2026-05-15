"""v2.1.4 BL-328 regression: AstroAdapter must scope D9.1 symlink rejection
to the sub-template subtree it copies out, not the whole fetched tree.

Three tests per the v2.1.4 fix plan:

  * `test_astro_marketing_against_real_pin` — clones the actual pinned
    withastro/astro SHA and runs `AstroAdapter(sub_template_id="marketing")`
    end-to-end. Pre-fix this raised
    `TemplateCacheError(reason="disallowed_entry_in_fetched_template")`
    because the upstream tree contains test-fixture symlinks under
    `packages/`. Post-fix this passes. Network-gated; skipped offline.

  * `test_astro_marketing_synthetic_symlink_outside_subtree` — synthetic
    fetcher mirrors withastro/astro shape: symlinks live OUTSIDE
    `examples/portfolio`. Post-fix: scaffold succeeds. This is the
    primary regression we ship.

  * `test_astro_marketing_rejects_synthetic_symlink_inside_subtree` —
    synthetic fetcher plants a symlink INSIDE `examples/portfolio`.
    Fix MUST still reject via TemplateCacheError; the security
    invariant "no symlinks inside the path we copy from" is preserved.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters.astro import AstroAdapter  # noqa: E402
from plugin_stack_adapters.contracts import AdapterScaffoldError  # noqa: E402
from plugin_stack_adapters.pin_registry import get_pin  # noqa: E402


@pytest.fixture
def cache_root_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "lp-template-cache"
    monkeypatch.setenv("LAUNCHPAD_CACHE_DIR", str(root))
    return root


def _write_synth_astro_tree(target: Path, *, with_inside_symlink: bool) -> None:
    """Mirror the relevant shape of withastro/astro@<pin>.

    `examples/portfolio` and `examples/blog` are populated with regular
    files; `packages/astro/test/fixtures/...` always contains the
    real-tree symlink (the bug case). When `with_inside_symlink=True`
    we also plant a symlink INSIDE `examples/portfolio` to assert the
    fix still rejects there.
    """
    portfolio_pkg = target / "examples" / "portfolio" / "package.json"
    portfolio_pkg.parent.mkdir(parents=True, exist_ok=True)
    portfolio_pkg.write_bytes(b'{"name": "@example/portfolio"}\n')
    (target / "examples" / "portfolio" / "src" / "pages").mkdir(
        parents=True, exist_ok=True
    )
    (target / "examples" / "portfolio" / "src" / "pages" / "index.astro").write_bytes(
        b"---\n---\n<h1>portfolio</h1>\n"
    )
    blog_pkg = target / "examples" / "blog" / "package.json"
    blog_pkg.parent.mkdir(parents=True, exist_ok=True)
    blog_pkg.write_bytes(b'{"name": "@example/blog"}\n')

    fixtures_dir = (
        target
        / "packages"
        / "astro"
        / "test"
        / "fixtures"
        / "content-collections"
        / "src"
        / "content"
    )
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    real_target = (
        target
        / "packages"
        / "astro"
        / "test"
        / "fixtures"
        / "symlinked-collections"
        / "content-collection"
    )
    real_target.mkdir(parents=True, exist_ok=True)
    (real_target / "post.md").write_text("# real\n", encoding="utf-8")
    os.symlink(
        "../../symlinked-collections/content-collection",
        str(fixtures_dir / "with-symlinked-content"),
    )

    if with_inside_symlink:
        os.symlink(
            "../portfolio/package.json",
            str(target / "examples" / "portfolio" / "evil-link.json"),
        )


def test_astro_marketing_synthetic_symlink_outside_subtree(
    tmp_path: Path, cache_root_tmp: Path
):
    """Primary v2.1.4 regression: symlinks OUTSIDE the copied sub-template
    subtree must NOT cause the cache fetch to reject."""
    project = tmp_path / "project"
    adapter = AstroAdapter(
        sub_template_id="marketing",
        fetcher=lambda t: _write_synth_astro_tree(t, with_inside_symlink=False),
    )
    adapter.scaffold_into(project)
    assert (project / "package.json").is_file()
    assert (project / "src" / "pages" / "index.astro").is_file()


def test_astro_blog_synthetic_symlink_outside_subtree(
    tmp_path: Path, cache_root_tmp: Path
):
    """Same regression for the `blog` sub-template (different walk_scope)."""
    project = tmp_path / "project"
    adapter = AstroAdapter(
        sub_template_id="blog",
        fetcher=lambda t: _write_synth_astro_tree(t, with_inside_symlink=False),
    )
    adapter.scaffold_into(project)
    assert (project / "package.json").is_file()


def test_astro_marketing_rejects_synthetic_symlink_inside_subtree(
    tmp_path: Path, cache_root_tmp: Path
):
    """Security invariant preserved: symlinks INSIDE the copied subtree
    must STILL be rejected by the scoped walk."""
    project = tmp_path / "project"
    adapter = AstroAdapter(
        sub_template_id="marketing",
        fetcher=lambda t: _write_synth_astro_tree(t, with_inside_symlink=True),
    )
    with pytest.raises(AdapterScaffoldError) as excinfo:
        adapter.scaffold_into(project)
    assert excinfo.value.reason == "template_cache_fetch_failed"
    cause = excinfo.value.__cause__
    assert cause is not None
    assert getattr(cause, "reason", None) == "disallowed_entry_in_fetched_template"
    assert getattr(cause, "entry_kind", None) == "symlink"


def _git_available() -> bool:
    try:
        subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def _can_reach_github() -> bool:
    if os.environ.get("LP_OFFLINE_TESTS") == "1":
        return False
    try:
        result = subprocess.run(
            ["git", "ls-remote", "https://github.com/withastro/astro", "HEAD"],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.mark.parametrize(
    "bad_scope",
    [
        "",
        "/abs/path",
        "../escape",
        "examples/../etc",
        "a/./b",
        "examples//portfolio",
        "examples/portfolio\x00",
        "examples/portfolio with space",
        "x" * 257,
    ],
)
def test_template_cache_validate_walk_scope_rejects(bad_scope: str):
    """v2.1.4 BL-328: walk_scope validation refuses traversal /
    absolute / NUL / oversize / non-portable inputs."""
    from template_cache._store import TemplateCacheError, _validate_walk_scope

    with pytest.raises(TemplateCacheError) as excinfo:
        _validate_walk_scope(bad_scope)
    assert excinfo.value.reason == "invalid_walk_scope"


@pytest.mark.parametrize(
    "good_scope",
    [
        "examples/portfolio",
        "examples/blog",
        "src",
        "a-b_c.d",
        "x" * 256,
    ],
)
def test_template_cache_validate_walk_scope_accepts(good_scope: str):
    from template_cache._store import _validate_walk_scope

    _validate_walk_scope(good_scope)


def test_template_cache_walk_scope_path_missing_in_pin(
    tmp_path: Path, cache_root_tmp: Path
):
    """When walk_scope points at a subpath the upstream tree does not
    contain (future bad pin), fetch refuses cleanly and surfaces a
    `walk_scope_path_missing` reason rather than walking the whole tree."""
    from template_cache import TemplateCacheError, fetch

    def empty_fetcher(target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / "README.md").write_bytes(b"# upstream\n")

    with pytest.raises(TemplateCacheError) as excinfo:
        fetch(
            "https://github.com/example/repo",
            "0" * 40,
            fetcher=empty_fetcher,
            walk_scope="examples/portfolio",
        )
    assert excinfo.value.reason == "walk_scope_path_missing"


@pytest.mark.parametrize(
    "bad_scope",
    [
        "",
        "/abs/path",
        "../escape",
        "examples/../etc",
        "a/./b",
        "examples//portfolio",
        "examples/portfolio\x00",
        "examples/portfolio with space",
        "x" * 257,
    ],
)
def test_template_cache_verify_rejects_bad_walk_scope(bad_scope: str):
    """v2.1.4 Codex PR #67 P2-A regression: `verify(walk_scope=...)` must
    apply the same `_validate_walk_scope` rejection that `fetch()` does
    at the cache boundary. Pre-fix, traversal-shaped scopes were silently
    forwarded to `_entry_files_match_manifest` which would join them onto
    `entry_dir` directly. Post-fix, the validator fires before the join."""
    from template_cache import TemplateCacheError, verify

    with pytest.raises(TemplateCacheError) as excinfo:
        verify(
            "https://github.com/example/repo",
            "0" * 40,
            walk_scope=bad_scope,
        )
    assert excinfo.value.reason == "invalid_walk_scope"


def test_template_cache_verify_accepts_good_walk_scope(
    tmp_path: Path, cache_root_tmp: Path
):
    """Sanity: a well-formed `walk_scope` reaches the manifest check and
    returns False (entry not present in the tempdir cache root) — i.e.,
    no validation rejection, just a normal cache miss."""
    from template_cache import verify

    assert (
        verify(
            "https://github.com/example/repo",
            "0" * 40,
            walk_scope="examples/portfolio",
        )
        is False
    )


@pytest.mark.slow
@pytest.mark.skipif(not _git_available(), reason="git not available")
@pytest.mark.skipif(not _can_reach_github(), reason="github.com unreachable")
def test_astro_marketing_against_real_pin(tmp_path: Path, cache_root_tmp: Path):
    """End-to-end against the actual pinned withastro/astro SHA.

    Uses a depth-1 fetch + checkout so the real upstream tree (with the
    real symlinks under packages/astro/test/fixtures/) is materialized
    in the cache, then runs AstroAdapter('marketing').scaffold_into.

    Pre-fix: raises AdapterScaffoldError wrapping
    TemplateCacheError(reason='disallowed_entry_in_fetched_template').
    Post-fix: succeeds.
    """
    pin = get_pin("astro", "marketing")

    def real_fetcher(target: Path) -> None:
        # Depth-1 fetch + checkout the pinned SHA. Mirrors what
        # template_cache._resolver.git_clone_depth_one does in production.
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=str(target),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "fetch", "--quiet", "--depth", "1", pin["repo_url"], pin["sha"]],
            cwd=str(target),
            check=True,
            capture_output=True,
            timeout=300,
        )
        subprocess.run(
            ["git", "checkout", "--quiet", pin["sha"]],
            cwd=str(target),
            check=True,
            capture_output=True,
        )
        # Drop the .git dir so it doesn't appear in the cache manifest.
        shutil.rmtree(target / ".git")

    project = tmp_path / "project"
    adapter = AstroAdapter(sub_template_id="marketing", fetcher=real_fetcher)
    adapter.scaffold_into(project)
    # Real `examples/portfolio/package.json` exists in the pin.
    assert (project / "package.json").is_file()
