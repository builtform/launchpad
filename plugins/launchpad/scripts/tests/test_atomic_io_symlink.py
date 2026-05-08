"""v2.1.0 atomic_io symlink-rejection tests (Codex P1 #1 fold).

Pins the §2.1 / §3.4 contract from
`docs/plans/launchpad_plans/2026-05-08-v2.1.0-atomic-io-symlink-and-kernel-drift-fix-plan.md`:

  * `atomic_write_excl`, `atomic_write_replace`, `atomic_write_replace_batch`
    refuse to write through a symlinked ancestor or symlinked target.
  * `atomic_write_excl` adds `O_NOFOLLOW` as belt-and-braces.
  * Defense-in-depth `relative_to(trusted_root)` catches the
    absolute-path-through-symlink case.
  * Batch refuse-all unlinks all earlier-staged tempfiles.
  * The optional `trusted_root=None` default emits a `RuntimeWarning`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from atomic_io import (  # noqa: E402
    atomic_write_excl,
    atomic_write_replace,
    atomic_write_replace_batch,
)


def _call_excl(target: Path, *, trusted_root: Path | None) -> None:
    atomic_write_excl(target, b"hello\n", trusted_root=trusted_root)


def _call_replace(target: Path, *, trusted_root: Path | None) -> None:
    atomic_write_replace(target, b"hello\n", trusted_root=trusted_root)


def _call_batch(target: Path, *, trusted_root: Path | None) -> None:
    atomic_write_replace_batch({target: b"hello\n"}, trusted_root=trusted_root)


_HELPERS = (
    pytest.param(_call_excl, id="atomic_write_excl"),
    pytest.param(_call_replace, id="atomic_write_replace"),
    pytest.param(_call_batch, id="atomic_write_replace_batch"),
)


# ---------------------------------------------------------------------------
# §3.4 #1 — symlinked ancestor refused (parametrized over 3 helpers)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("helper", _HELPERS)
def test_atomic_io_rejects_symlink_ancestor(tmp_path, helper):
    """A symlinked ancestor (e.g., `.github -> /tmp/outside`) MUST be
    refused. `_assert_path_safe` walks the parent chain up to
    `trusted_root` and refuses on the first symlink ancestor.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / ".github"
    link.symlink_to(outside, target_is_directory=True)

    target = link / "ci.yml"

    with pytest.raises(OSError) as excinfo:
        helper(target, trusted_root=tmp_path)
    assert "symlinked" in str(excinfo.value).lower()

    # No file written through the symlink either side.
    assert not (outside / "ci.yml").exists()
    assert not (link / "ci.yml").exists() or (link / "ci.yml").is_symlink() is False


# ---------------------------------------------------------------------------
# §3.4 #2 — target itself a symlink refused (parametrized over 3 helpers)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("helper", _HELPERS)
def test_atomic_io_rejects_target_symlink(tmp_path, helper):
    """A symlinked target (`cwd/.launchpad/scaffold-decision.json -> /tmp/loot`)
    MUST be refused. The pre-check + `O_NOFOLLOW` together close the
    target-itself redirection vector.
    """
    loot = tmp_path / "loot"
    loot.write_bytes(b"original\n")

    target_dir = tmp_path / ".launchpad"
    target_dir.mkdir()
    target = target_dir / "scaffold-decision.json"
    target.symlink_to(loot)

    with pytest.raises(OSError):
        helper(target, trusted_root=tmp_path)

    # The redirection target is byte-for-byte unchanged.
    assert loot.read_bytes() == b"original\n"


# ---------------------------------------------------------------------------
# §3.4 #3 — absolute path outside trusted_root rejected (defense-in-depth)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("helper", _HELPERS)
def test_atomic_io_rejects_absolute_path_outside_trusted_root(
    tmp_path, helper, tmp_path_factory
):
    """An absolute target outside `trusted_root` MUST be refused, even when
    no ancestor is itself a symlink. The defense-in-depth
    `target_abs.parent.resolve().relative_to(trusted_root)` catches this.
    """
    outside = tmp_path_factory.mktemp("outside")
    target = outside / "leaked.txt"

    with pytest.raises(OSError) as excinfo:
        helper(target, trusted_root=tmp_path)
    assert "escapes" in str(excinfo.value).lower() or "trusted_root" in str(
        excinfo.value
    )

    assert not target.exists()


# ---------------------------------------------------------------------------
# §3.4 #4 — atomic_write_excl O_NOFOLLOW belt-and-braces
# ---------------------------------------------------------------------------
def test_atomic_write_excl_O_NOFOLLOW(tmp_path, monkeypatch):
    """If `_assert_path_safe` is bypassed, `O_NOFOLLOW` must still raise
    `OSError(ELOOP)` when `target` is a symlink. We monkey-patch
    `_assert_path_safe` to a no-op so the inner `os.open` flag is what
    surfaces the rejection.
    """
    import atomic_io

    loot = tmp_path / "loot"
    loot.write_bytes(b"original\n")
    target = tmp_path / "target.txt"
    target.symlink_to(loot)

    monkeypatch.setattr(atomic_io, "_assert_path_safe", lambda *_a, **_kw: None)

    with pytest.raises(OSError) as excinfo:
        atomic_write_excl(target, b"hello\n", trusted_root=tmp_path)

    # O_NOFOLLOW raises ELOOP (or, on some platforms, EMLINK / EEXIST).
    # The salient assertion: `loot` was not overwritten.
    assert loot.read_bytes() == b"original\n"
    # Sanity: the raised error is an OSError of some flavor.
    assert isinstance(excinfo.value, OSError)


# ---------------------------------------------------------------------------
# §3.4 #5 — batch refuse-all unlinks earlier-staged tempfiles
# ---------------------------------------------------------------------------
def test_atomic_write_replace_batch_refuse_all_unlinks_staged(tmp_path):
    """Stage 3 targets where #2 has a symlinked ancestor. Assert NO
    tempfiles remain anywhere on disk after the refuse-all -- the
    earlier-staged tempfile for #1 must be unlinked when #2 raises.
    """
    outside = tmp_path / "outside"
    outside.mkdir()

    good_dir_1 = tmp_path / "first"
    good_dir_1.mkdir()
    good_dir_3 = tmp_path / "third"
    good_dir_3.mkdir()

    bad_link = tmp_path / "second"
    bad_link.symlink_to(outside, target_is_directory=True)

    target_1 = good_dir_1 / "a.txt"
    target_2 = bad_link / "b.txt"
    target_3 = good_dir_3 / "c.txt"

    batch = {
        target_1: b"alpha\n",
        target_2: b"bravo\n",
        target_3: b"charlie\n",
    }

    with pytest.raises(OSError):
        atomic_write_replace_batch(batch, trusted_root=tmp_path)

    # No targets written.
    assert not target_1.exists()
    assert not target_3.exists()
    # No tempfiles remain in `first/`, `third/`, or `outside/`.
    leftover_temps: list[Path] = []
    for d in (good_dir_1, good_dir_3, outside):
        leftover_temps.extend(p for p in d.iterdir() if p.name.endswith(".tmp"))
    assert leftover_temps == [], (
        f"refuse-all left tempfiles behind: {leftover_temps!r}"
    )


# ---------------------------------------------------------------------------
# §3.4 #6 — RuntimeWarning when trusted_root defaulted (production-misuse loud)
# ---------------------------------------------------------------------------
def test_atomic_io_emits_runtimewarning_when_trusted_root_default(tmp_path, monkeypatch):
    """Production callers MUST pass `trusted_root` explicitly. The optional
    default exists only for low-level test callers; missing it must be loud.
    """
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "x.txt"

    with pytest.warns(RuntimeWarning, match="trusted_root not passed"):
        atomic_write_replace(target, b"hello\n")

    assert target.read_bytes() == b"hello\n"
