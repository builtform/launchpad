"""v2.1 Codex PR #50 D7 regression: version_drift_log unified schema.

Tests:
  * Names variant when pii_opt_in=True
  * Fingerprint variant when pii_opt_in=False
  * Tagged-union signature: helper picks redaction; caller serializes
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lp_bootstrap.version_drift import (  # noqa: E402
    Fingerprint,
    Names,
    compute_identity_fields_changed,
)


def test_names_variant_when_pii_opt_in_true():
    prior = {"a": "1", "b": "2"}
    current = {"a": "1", "b": "3"}
    result = compute_identity_fields_changed(prior, current, pii_opt_in=True)
    assert isinstance(result, Names)
    assert result.names == ("b",)


def test_fingerprint_variant_when_pii_opt_in_false():
    prior = {"a": "1", "b": "2"}
    current = {"a": "1", "b": "3"}
    result = compute_identity_fields_changed(prior, current, pii_opt_in=False)
    assert isinstance(result, Fingerprint)
    assert result.digest.startswith("sha256:")
    assert re.fullmatch(r"sha256:[a-f0-9]{16}", result.digest)


def test_no_changes_yields_empty_names():
    prior = {"a": "1"}
    current = {"a": "1"}
    result = compute_identity_fields_changed(prior, current, pii_opt_in=True)
    assert isinstance(result, Names)
    assert result.names == ()


def test_added_keys_detected():
    prior = {"a": "1"}
    current = {"a": "1", "b": "2"}
    result = compute_identity_fields_changed(prior, current, pii_opt_in=True)
    assert isinstance(result, Names)
    assert result.names == ("b",)


def test_removed_keys_detected():
    prior = {"a": "1", "b": "2"}
    current = {"a": "1"}
    result = compute_identity_fields_changed(prior, current, pii_opt_in=True)
    assert isinstance(result, Names)
    assert result.names == ("b",)


def test_fingerprint_stable_for_same_input():
    f1 = compute_identity_fields_changed({"a": "1"}, {"a": "2"}, pii_opt_in=False)
    f2 = compute_identity_fields_changed({"a": "1"}, {"a": "2"}, pii_opt_in=False)
    assert f1.digest == f2.digest
