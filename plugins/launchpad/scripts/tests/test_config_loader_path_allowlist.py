"""Phase 5 v2.1 (DA4) -- `--get-config-value <PATH>` allowlist regex tests.

Single parametrized test exercising the rejected path shapes (per cycle-1
simplicity P3): `..`, leading dot, trailing dot, double-dot, uppercase,
slash, length >256 bytes, depth >5; plus one accept case at depth 5.

The pre-load validator is in `_validate_config_path` -- the test invokes
the CLI end-to-end so it covers both the `argparse → main()` wiring and
the validator's locked error messages.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
LOADER = str(PLUGIN_SCRIPTS / "plugin-config-loader.py")


def _make_fixture() -> Path:
    """Minimal config.yml so the loader does not error out before the
    --get-config-value branch fires. Path validation runs BEFORE config
    load (security F4) so this fixture is mostly insurance."""
    d = Path(tempfile.mkdtemp(prefix="lp-phase5-allowlist-"))
    (d / ".launchpad").mkdir()
    (d / ".launchpad" / "config.yml").write_text(
        'commands:\n  test: ["pnpm test"]\n', encoding="utf-8",
    )
    return d


@pytest.mark.parametrize(
    "path, expected_exit, error_substring",
    [
        ("..",                                 2, "invalid config path"),
        (".commands",                          2, "invalid config path"),
        ("commands.",                          2, "invalid config path"),
        ("commands..test",                     2, "invalid config path"),
        ("Commands.test",                      2, "invalid config path"),
        ("commands/test",                      2, "invalid config path"),
        ("a" * 300,                            2, "exceeds 256 bytes"),
        ("a.b.c.d.e.f",                        2, "invalid config path"),
        # Accept case at depth 5 -- regex `{0,4}` allows up to 5 segments.
        ("a.b.c.d.e",                          2, "not found"),  # path valid; missing key → exit 2
    ],
    ids=[
        "double-dot-traversal",
        "leading-dot",
        "trailing-dot",
        "double-dot-internal",
        "uppercase-rejected",
        "slash-rejected",
        "length-cap-exceeded",
        "depth-six-rejected",
        "depth-five-accepted-by-regex",
    ],
)
def test_path_allowlist_rejects_or_accepts(
    path: str, expected_exit: int, error_substring: str,
):
    """Single parametrized test. Length-cap case asserts the locked error
    does NOT echo the rejected input (cycle-2 P2-B input-echo guard)."""
    fixture = _make_fixture()
    try:
        r = subprocess.run(
            [
                sys.executable, LOADER,
                f"--repo-root={fixture}",
                f"--get-config-value={path}",
            ],
            capture_output=True, text=True,
        )
        assert r.returncode == expected_exit, (
            f"path={path!r}: expected exit {expected_exit}, got {r.returncode}. "
            f"stderr: {r.stderr[:400]}"
        )
        assert error_substring in r.stderr, (
            f"path={path!r}: stderr should contain {error_substring!r}; "
            f"got: {r.stderr[:400]}"
        )
        # cycle-2 P2-B: length-cap message MUST NOT echo the input bytes
        # (pre-regex content is not yet validated for terminal-control
        # chars or escape sequences).
        if error_substring == "exceeds 256 bytes":
            assert path not in r.stderr, (
                "length-cap error echoed the rejected input -- cycle-2 P2-B "
                "input-echo guard violated"
            )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)
