"""Identity placeholder policy and preview/write validation parity."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from lp_pick_stack.decision_writer import IDENTITY_PLACEHOLDERS as P
from lp_update_identity import IdentityUpdateErrorCode, IdentityUpdateStatus
from lp_update_identity.engine import run_update_identity
from test_update_identity_engine import (
    _mit_identity,
    _seed_full_scaffold,
    _seed_legacy_v1_0_envelope,
)

_IN = _mit_identity()
_OUT = dict(_IN, pii_opt_in=False, email=P["email"], copyright_holder=P["copyright_holder"], repo_url=P["repo_url"])
_URL = "https://github.com/example/updated-project"

_CASES = [
    pytest.param(_OUT, dict(_OUT, repo_url=_URL), None, ["repo_url"], id="repo-url-while-opted-out"),
    pytest.param(_OUT, dict(_OUT, email="new@example.com"), "email", None, id="email-requires-opt-in"),
    pytest.param(_OUT, dict(_OUT, pii_opt_in=True, email="new@example.com", copyright_holder="New Owner"), None, None, id="opt-in-with-real-values"),
    pytest.param(_OUT, dict(_OUT, pii_opt_in=True, copyright_holder="New Owner"), "email", None, id="opt-in-needs-real-email"),
    pytest.param(_OUT, dict(_OUT, copyright_holder="<Alice Smith>"), "copyright_holder", None, id="noncanonical-copyright-placeholder"),
    pytest.param(dict(_IN, repo_url=P["repo_url"]), dict(_IN, repo_url=P["repo_url"], project_name="renamed-project"), None, ["project_name"], id="untouched-repo-placeholder"),
    pytest.param(_IN, dict(_IN, email=P["email"]), "email", None, id="email-downgrade"),
    pytest.param(_IN, dict(_IN, repo_url=P["repo_url"]), "repo_url", None, id="repo-downgrade"),
    pytest.param(_IN, dict(_IN, email="<x>"), "email", None, id="noncanonical-email-placeholder"),
    pytest.param(_IN, dict(_IN, copyright_holder="<a>b>"), "copyright_holder", None, id="nested-bracket-placeholder"),
    pytest.param(_IN, dict(_OUT), "email", None, id="opt-out-after-opt-in"),
    pytest.param(dict(_IN, email=P["email"], repo_url=P["repo_url"]), dict(_IN, email=P["email"], repo_url=_URL), None, ["repo_url"], id="legacy-inconsistent-email-untouched"),
    pytest.param(None, dict(_OUT), None, ["project_name", "license"], id="legacy-envelope-no-identity"),
    pytest.param(_OUT, dict(_OUT, copyright_holder="New Owner"), "copyright_holder", None, id="copyright-requires-opt-in"),
    pytest.param(dict(_OUT, pii_opt_in=True), dict(_OUT), "pii_opt_in", None, id="legacy-placeholder-opt-out-still-refused"),
]


@pytest.mark.parametrize(("sealed", "updated", "error_field", "expected_fields"), _CASES)
def test_identity_update_preview_write_parity(tmp_path: Path, sealed, updated, error_field, expected_fields):
    outcomes = []
    for dry in (True, False):
        root = tmp_path / ("preview" if dry else "write")
        root.mkdir(mode=0o700)
        if sealed is None:
            _seed_legacy_v1_0_envelope(root, with_identity=False)
        else:
            _seed_full_scaffold(root, sealed)
        before = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()
        }
        result = run_update_identity(
            root, dict(updated), dry_run=dry, quiet=True,
            stdout=io.StringIO(), stderr=io.StringIO(),
        )
        outcomes.append((result.status, result.error_code, result.fields_changed))
        if error_field:
            assert result.status is None
            assert result.error_code == IdentityUpdateErrorCode.IDENTITY_VALIDATION_FAILED
            assert result.error_message == f"identity.{error_field} failed validation"
            assert result.fields_changed == []
            for value in updated.values():
                if isinstance(value, str) and value:
                    assert value not in result.error_message
        else:
            assert result.status == IdentityUpdateStatus.UPDATED, result
            assert result.error_code is None
            if expected_fields is not None:
                assert result.fields_changed == expected_fields
            if not dry and "repo_url" in result.fields_changed:
                assert updated["repo_url"] in (root / "README.md").read_text(encoding="utf-8")
        if dry or error_field:
            after = {
                p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob("*") if p.is_file()
            }
            assert after == before
    assert outcomes[0] == outcomes[1]
