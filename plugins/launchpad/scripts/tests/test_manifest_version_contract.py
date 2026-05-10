"""Manifest-version-contract test (BL-319, v2.1.2).

Asserts plugin.json `version` equals the LATEST non-placeholder
`## [v<version>]` heading in CHANGELOG.md. Placeholder blocks (Phase 0
skeletons whose body lacks any `### ` Keep-a-Changelog subheading) are
skipped so the test passes at intermediate phase commits AND fails on
the H.3 scenario (plugin.json lagging the latest documented release).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# Walk up from tests/ → scripts/ → launchpad/ → plugins/ → repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PLUGIN_JSON = _REPO_ROOT / "plugins" / "launchpad" / ".claude-plugin" / "plugin.json"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_RELEASES_DIR = _REPO_ROOT / "docs" / "releases"

# Strict X.Y.Z semver only (project convention; rejects pre-release suffixes).
_HEADING_RE = re.compile(r"^## \[v?(\d+\.\d+\.\d+)\]\s*$", re.MULTILINE)
# Any `### ` subheading counts as "real content" — covers both Keep-a-Changelog
# vocabulary (Added/Changed/Removed/Fixed/Deprecated/Security) AND project
# conventions like `### For LaunchPad users (...)` used in v2.1.x CHANGELOG.
_REAL_SUBHEADING_RE = re.compile(r"^### \S", re.MULTILINE)


def _parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a `X.Y.Z` semver into a sortable 3-tuple."""
    parts = version_str.split(".")
    assert len(parts) == 3, f"expected X.Y.Z semver; got {version_str!r}"
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError as exc:
        raise AssertionError(
            f"version {version_str!r} contains non-integer component (pre-release "
            f"suffixes like -rc1 are unsupported by this gate)"
        ) from exc


def _read_plugin_version(plugin_json_path: Path) -> str:
    data = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    assert "version" in data, f"plugin.json missing 'version' key at {plugin_json_path}"
    version = data["version"]
    assert isinstance(version, str), (
        f"plugin.json 'version' must be string; got {type(version).__name__}: {version!r}"
    )
    return version


def _changelog_blocks(changelog_text: str) -> list[tuple[str, str]]:
    """Return [(version_str, block_body), ...] in the order they appear in CHANGELOG."""
    blocks: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(changelog_text))
    for i, match in enumerate(matches):
        version = match.group(1)
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog_text)
        body = changelog_text[body_start:body_end].strip()
        blocks.append((version, body))
    return blocks


def _is_placeholder(block_body: str) -> bool:
    """True iff body lacks any `### ` subheading.

    A real release block has at least one `### ` subheading (whether
    Keep-a-Changelog vocabulary like `### Added` or project-specific like
    `### For LaunchPad users`). Handles single-comment, multi-comment,
    blank, prose-only, and TBD-style placeholders uniformly.
    """
    return _REAL_SUBHEADING_RE.search(block_body) is None


def _latest_non_placeholder_version(changelog_text: str) -> str | None:
    """Return the semver-greatest version from non-placeholder blocks, or None."""
    blocks = _changelog_blocks(changelog_text)
    real = [v for v, body in blocks if not _is_placeholder(body)]
    if not real:
        return None
    return max(real, key=_parse_version)


def _assert_contract(plugin_json_path: Path, changelog_path: Path) -> None:
    """Single source of truth for the contract; called by positive + negative tests."""
    assert changelog_path.exists(), (
        f"CHANGELOG.md not found at {changelog_path}; path resolution drifted"
    )
    plugin_version = _read_plugin_version(plugin_json_path)
    changelog = changelog_path.read_text(encoding="utf-8")
    latest = _latest_non_placeholder_version(changelog)
    assert latest is not None, (
        "CHANGELOG.md has no non-placeholder version blocks; cannot determine target"
    )
    assert plugin_version == latest, (
        f"plugin.json version {plugin_version!r} does not match latest "
        f"non-placeholder CHANGELOG heading [v{latest}]. Either bump plugin.json "
        f"to {latest} OR populate the [v{plugin_version}] block in CHANGELOG.md."
    )


# --- Positive tests (run against working tree) ----------------------------


def test_plugin_json_matches_latest_non_placeholder_changelog_heading() -> None:
    """plugin.json.version MUST equal the latest non-placeholder CHANGELOG heading."""
    _assert_contract(_PLUGIN_JSON, _CHANGELOG)


def test_release_notes_file_exists_for_plugin_json_version() -> None:
    """`docs/releases/v<version>.md` MUST exist for plugin.json version."""
    plugin_version = _read_plugin_version(_PLUGIN_JSON)
    release_notes = _RELEASES_DIR / f"v{plugin_version}.md"
    assert release_notes.is_file(), (
        f"docs/releases/v{plugin_version}.md missing or not a regular file. "
        f"Author it (see docs/releases/v2.1.1.md as template) or roll plugin.json back."
    )


# --- Negative tests (tmp_path-driven; no working-tree mutation) -----------


@pytest.mark.parametrize(
    "fake_version,fake_changelog,expected_msg_fragment",
    [
        # H.3 scenario: plugin.json lags the latest non-placeholder block.
        ("2.1.0", "## [v2.1.1]\n\n### Added\n- entry\n\n## [v2.1.0]\n\n### Added\n- entry\n", "does not match latest"),
        # Hand-edited future block: plugin.json older than newest documented.
        ("2.1.1", "## [v3.0.0]\n\n### Added\n- entry\n\n## [v2.1.1]\n\n### Added\n- entry\n", "does not match latest"),
        # Plugin.json version absent from CHANGELOG entirely.
        ("9.9.9", "## [v2.1.1]\n\n### Added\n- entry\n", "does not match latest"),
    ],
    ids=["lags_latest", "future_block_drift", "version_absent"],
)
def test_negative_plugin_json_lags_or_drifts(
    fake_version: str, fake_changelog: str, expected_msg_fragment: str, tmp_path: Path
) -> None:
    """Negative: synthetic plugin.json + CHANGELOG combinations MUST fail the contract."""
    fake_plugin = tmp_path / "plugin.json"
    fake_plugin.write_text(json.dumps({"version": fake_version}), encoding="utf-8")
    fake_cl = tmp_path / "CHANGELOG.md"
    fake_cl.write_text(fake_changelog, encoding="utf-8")

    with pytest.raises(AssertionError) as excinfo:
        _assert_contract(fake_plugin, fake_cl)
    assert expected_msg_fragment in str(excinfo.value)


def test_negative_placeholder_only_changelog_raises(tmp_path: Path) -> None:
    """Negative: CHANGELOG with only placeholder blocks raises 'no non-placeholder' error."""
    fake_plugin = tmp_path / "plugin.json"
    fake_plugin.write_text(json.dumps({"version": "2.1.2"}), encoding="utf-8")
    fake_cl = tmp_path / "CHANGELOG.md"
    # Multiple placeholder blocks (HTML comment + TBD-style + blank) — all must skip.
    fake_cl.write_text(
        "## [v2.1.2]\n\n<!-- placeholder -->\n\n## [v2.1.1]\n\nTBD\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="no non-placeholder version blocks"):
        _assert_contract(fake_plugin, fake_cl)
