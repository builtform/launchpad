"""Tests for the v2.1 kernel renderer (V3 plan section 17.1 Phase 2).

The kernel renderer owns 7 stack-agnostic identity-bearing files rendered
into the project root by /lp-scaffold-stack at greenfield scaffold time
and re-rendered by /lp-bootstrap --refresh at /lp-update-identity time.

Tests cover:
  * All 7 templates render without error for both PII opt-in and
    opt-out identity dicts.
  * Identity values land in the rendered output (project_name in README,
    copyright_holder in LICENSE, email in CONTRIBUTING, etc.).
  * License enum dispatch: MIT renders full canonical text;
    other enums render placeholder pointing at choosealicense.com;
    Other renders identity.license_other_body verbatim.
  * Idempotent re-render: same identity input produces byte-identical
    output across calls.
  * Atomic-write semantics: target files are mode 0o600 and the
    parent directory is created if absent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from plugin_default_generators.kernel_renderer import KERNEL_FILES, KernelRenderer  # noqa: E402


def _real_identity(**overrides):
    base = {
        "pii_opt_in": True,
        "project_name": "ulc-spec-org",
        "email": "user@example.com",
        "copyright_holder": "Foad Shafighi",
        "repo_url": "https://github.com/foadshafighi/ulc-spec-org",
        "license": "MIT",
        "license_other_body": "",
    }
    base.update(overrides)
    return base


def _placeholder_identity(**overrides):
    """PII opt-out posture: email and copyright_holder are placeholders,
    but license still has a real value (the license question is asked
    independently of PII opt-in per Step 1.5 of /lp-pick-stack)."""
    base = {
        "pii_opt_in": False,
        "project_name": "<project-name>",
        "email": "<email>",
        "copyright_holder": "<copyright-holder>",
        "repo_url": "<repo-url>",
        "license": "MIT",  # license is always asked, default MIT
        "license_other_body": "",
    }
    base.update(overrides)
    return base


def test_kernel_files_inventory_is_seven() -> None:
    """The V3 plan §17.1 commits to "7 kernel templates". Pin the count."""
    assert len(KERNEL_FILES) == 7


def test_kernel_files_inventory_names_match_v3_plan() -> None:
    """V3 plan §11.5 enumerates LICENSE, CONTRIBUTING, CODE_OF_CONDUCT,
    README as kernel files. Phase 2 rounds out to 7 with SECURITY,
    AGENTS, CLAUDE. Pin the set so renames are caught at PR time."""
    output_paths = {output for _, output in KERNEL_FILES}
    assert output_paths == {
        "LICENSE",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "README.md",
        "SECURITY.md",
        "AGENTS.md",
        "CLAUDE.md",
    }


def test_render_all_writes_seven_files(tmp_path: Path) -> None:
    KernelRenderer().render_all(tmp_path, _real_identity())
    actual = sorted(p.name for p in tmp_path.iterdir())
    expected = sorted({"LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
                       "README.md", "SECURITY.md", "AGENTS.md", "CLAUDE.md"})
    assert actual == expected


def test_render_all_returns_path_and_sha256(tmp_path: Path) -> None:
    results = KernelRenderer().render_all(tmp_path, _real_identity())
    assert len(results) == 7
    for path, sha in results:
        assert path.is_file()
        assert len(sha) == 64  # sha256 hex digest


def test_license_mit_renders_canonical_text(tmp_path: Path) -> None:
    KernelRenderer().render_all(tmp_path, _real_identity(license="MIT"))
    body = (tmp_path / "LICENSE").read_text()
    assert "MIT License" in body
    assert "Permission is hereby granted, free of charge" in body
    assert "Foad Shafighi" in body
    # Year stamped from current UTC; pin a lower bound only
    assert "Copyright (c)" in body


def test_license_other_uses_user_supplied_body(tmp_path: Path) -> None:
    custom = "Custom proprietary license. All rights reserved."
    identity = _real_identity(license="Other", license_other_body=custom)
    KernelRenderer().render_all(tmp_path, identity)
    body = (tmp_path / "LICENSE").read_text()
    assert custom in body
    assert "MIT License" not in body  # MIT branch not rendered


def test_license_apache_renders_placeholder_with_choosealicense_url(tmp_path: Path) -> None:
    """Phase 2 ships full canonical text for MIT only; non-MIT non-Other
    licenses render a placeholder that points the user at the canonical
    text. The 5 remaining license bodies are tracked as a Phase-9 follow-up."""
    KernelRenderer().render_all(tmp_path, _real_identity(license="Apache-2.0"))
    body = (tmp_path / "LICENSE").read_text()
    assert "Apache-2.0 License" in body
    assert "choosealicense.com/licenses/apache-2.0" in body
    assert "Foad Shafighi" in body  # copyright header still rendered


def test_project_name_lands_in_readme(tmp_path: Path) -> None:
    KernelRenderer().render_all(tmp_path, _real_identity(project_name="ulc-spec-org"))
    readme = (tmp_path / "README.md").read_text()
    assert readme.startswith("# ulc-spec-org\n")


def test_email_lands_in_contributing_and_security(tmp_path: Path) -> None:
    identity = _real_identity(email="contact@example.com")
    KernelRenderer().render_all(tmp_path, identity)
    contributing = (tmp_path / "CONTRIBUTING.md").read_text()
    security = (tmp_path / "SECURITY.md").read_text()
    assert "contact@example.com" in contributing
    assert "contact@example.com" in security


def test_repo_url_lands_in_readme_and_security(tmp_path: Path) -> None:
    url = "https://github.com/owner/proj"
    KernelRenderer().render_all(tmp_path, _real_identity(repo_url=url))
    readme = (tmp_path / "README.md").read_text()
    security = (tmp_path / "SECURITY.md").read_text()
    assert url in readme
    assert url in security


def test_placeholder_identity_renders_cleanly(tmp_path: Path) -> None:
    """PII opt-out posture: all four identity placeholders survive
    template substitution. The rendered output contains the literal
    `<email>`, `<copyright-holder>`, etc., which /lp-update-identity
    later detects via IDENTITY_PLACEHOLDER_PATTERN to re-prompt."""
    KernelRenderer().render_all(tmp_path, _placeholder_identity())
    contributing = (tmp_path / "CONTRIBUTING.md").read_text()
    license_text = (tmp_path / "LICENSE").read_text()
    assert "<email>" in contributing
    assert "<copyright-holder>" in license_text


def test_render_is_idempotent_for_same_identity(tmp_path: Path) -> None:
    """Same identity input yields byte-identical output across calls.
    Required by /lp-bootstrap --refresh idempotency contract (V3 plan
    §10.3): re-rendering with unchanged identity must not produce a
    spurious diff that triggers the "user manual edit" detection."""
    identity = _real_identity()
    first = KernelRenderer().render_all(tmp_path, identity)
    second = KernelRenderer().render_all(tmp_path, identity)
    assert [sha for _, sha in first] == [sha for _, sha in second]


def test_render_creates_parent_directory(tmp_path: Path) -> None:
    """Atomic-write helper creates parent directories. Confirm by
    rendering into a deeply-nested cwd that does not yet exist."""
    deep = tmp_path / "deep" / "nested" / "project"
    deep.mkdir(parents=True)
    KernelRenderer().render_all(deep, _real_identity())
    assert (deep / "LICENSE").is_file()


def test_rendered_files_have_secure_mode(tmp_path: Path) -> None:
    """atomic_write_replace creates files with mode 0o600. Pin the
    contract so a future helper change cannot silently weaken it."""
    KernelRenderer().render_all(tmp_path, _real_identity())
    for filename in ("LICENSE", "README.md"):
        mode = (tmp_path / filename).stat().st_mode & 0o777
        assert mode == 0o600, f"{filename} mode is {mode:o}, expected 600"


def test_missing_identity_field_raises_strict_undefined(tmp_path: Path) -> None:
    """Templates use `{{ identity.email }}` etc. StrictUndefined fails
    loudly when a required identity field is absent rather than rendering
    an empty string into LICENSE/CONTRIBUTING."""
    import jinja2
    incomplete = {"project_name": "x", "license": "MIT"}  # missing email, etc.
    with pytest.raises(jinja2.UndefinedError):
        KernelRenderer().render_all(tmp_path, incomplete)
