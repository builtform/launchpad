"""Phase 6 v2.1 -- Rails detection groundwork via Gemfile manifest.

Tests against `plugin-stack-detector.py:detect_from_manifest` dispatch at
lines 413-424 (post-Phase-6 edit). Each test feeds a fixture Gemfile and
asserts the dispatched stack id + frameworks list.
"""
from __future__ import annotations

import importlib.util
import shutil
import tempfile
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "plugin_stack_detector", _SCRIPTS / "plugin-stack-detector.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

detect_from_manifest = _mod.detect_from_manifest


@pytest.fixture
def gemfile_dir():
    d = Path(tempfile.mkdtemp(prefix="lp-phase6-rails-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_rails_gemfile_returns_rails_stack(gemfile_dir: Path):
    """A Gemfile that lists `gem "rails"` dispatches to stack=rails."""
    gemfile = gemfile_dir / "Gemfile"
    gemfile.write_text(
        'source "https://rubygems.org"\n'
        'gem "rails", "~> 7.1"\n'
        'gem "puma"\n',
        encoding="utf-8",
    )
    out = detect_from_manifest(gemfile)
    assert out["stack"] == "rails"
    assert "rails" in out["frameworks"]


def test_rails_single_quote_gem_line_detected(gemfile_dir: Path):
    """Single-quoted `gem 'rails'` is also recognized (regex covers both)."""
    gemfile = gemfile_dir / "Gemfile"
    gemfile.write_text(
        "source 'https://rubygems.org'\n"
        "gem 'rails', '~> 7.0'\n",
        encoding="utf-8",
    )
    out = detect_from_manifest(gemfile)
    assert out["stack"] == "rails"


def test_sinatra_gemfile_falls_through_to_generic_ruby(gemfile_dir: Path):
    """A Gemfile without `gem "rails"` falls through to the existing
    generic+ruby branch — Phase 6 ships detection groundwork only."""
    gemfile = gemfile_dir / "Gemfile"
    gemfile.write_text(
        'source "https://rubygems.org"\n'
        'gem "sinatra"\n'
        'gem "rack"\n',
        encoding="utf-8",
    )
    out = detect_from_manifest(gemfile)
    assert out["stack"] == "generic"
    assert "ruby" in out["frameworks"]
    assert "rails" not in out["frameworks"]
