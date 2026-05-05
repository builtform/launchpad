"""pin_registry.py shape + lookup contract tests.

Phase 4 plan §3.2: pin_registry is the single source of truth for upstream
commit SHAs. Each pin must dual-resolve cleanly and match the 40-char hex
regex; per-adapter SHA constants are forbidden (covered by
tests/test_no_floating_tag_pins.py).
"""
from __future__ import annotations

import pytest

from plugin_stack_adapters.pin_registry import (
    InvalidPinShaError,
    Pin,
    PinNotFoundError,
    _PINS,
    _SHA_RE,
    all_pins,
    get_pin,
)


def test_pins_dict_has_at_least_five_entries():
    assert len(_PINS) >= 5, _PINS


def test_every_pin_sha_matches_40char_hex_regex():
    for key, pin in _PINS.items():
        assert _SHA_RE.match(pin["sha"]), f"{key} sha {pin['sha']!r} fails regex"


def test_every_pin_repo_url_is_https_github():
    for key, pin in _PINS.items():
        assert pin["repo_url"].startswith("https://github.com/"), (
            f"{key} repo_url {pin['repo_url']!r} not on github.com"
        )


def test_every_pin_license_is_non_empty():
    for key, pin in _PINS.items():
        assert pin["license"], f"{key} license is empty"


def test_every_pin_attestation_ref_in_closed_set():
    for key, pin in _PINS.items():
        assert pin["attestation_ref"] in {"unsigned", "verified"}, (
            f"{key} attestation_ref {pin['attestation_ref']!r} out of range"
        )


def test_get_pin_nextjs_standalone_returns_next_forge():
    pin = get_pin("nextjs_standalone")
    assert pin["repo_url"] == "https://github.com/vercel/next-forge"
    assert pin["license"] == "MIT"


def test_get_pin_astro_docs_returns_starlight():
    pin = get_pin("astro", "docs")
    assert pin["repo_url"] == "https://github.com/withastro/starlight"


def test_astro_blog_and_marketing_share_repo_but_distinct_keys():
    blog = get_pin("astro", "blog")
    marketing = get_pin("astro", "marketing")
    assert blog["repo_url"] == marketing["repo_url"]
    assert ("astro", "blog") in _PINS
    assert ("astro", "marketing") in _PINS


def test_get_pin_nonexistent_raises_pin_not_found():
    with pytest.raises(PinNotFoundError):
        get_pin("nonexistent_adapter")


def test_all_pins_returns_full_inventory_as_tuples():
    rows = all_pins()
    assert len(rows) == len(_PINS)
    for adapter_id, sub_id, pin in rows:
        assert isinstance(adapter_id, str)
        assert sub_id is None or isinstance(sub_id, str)
        assert isinstance(pin["sha"], str)
