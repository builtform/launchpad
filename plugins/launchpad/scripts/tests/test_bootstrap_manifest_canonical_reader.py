"""Tests for `read_bootstrap_manifest()` 4-rule acceptance ladder.

V3 plan §11.7 + HANDSHAKE §10.v2.1:
  * file missing -> present=False, payload={}
  * manifest_schema_version absent or "1.0" -> full read; required fields
    plugin_version, last_render_timestamp, files
  * "1.x" x>0 -> forward-compat with INFO listing unknown fields
  * major>=2 -> ConfigError fail-closed
  * malformed -> ConfigError fail-closed

The manifest is forward-prep at Phase 1: /lp-bootstrap (Phase 3+) writes
the first one. Until then this reader is exercised only against test
fixtures and the absent-file case.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_spec = importlib.util.spec_from_file_location(
    "plugin_config_loader", _SCRIPTS / "plugin-config-loader.py"
)
plugin_config_loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin_config_loader)


ConfigError = plugin_config_loader.ConfigError
read_bootstrap_manifest = plugin_config_loader.read_bootstrap_manifest


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir(parents=True, exist_ok=True)
    target = launchpad / "bootstrap-manifest.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _well_formed_v10_manifest() -> dict:
    return {
        "manifest_schema_version": "1.0",
        "plugin_version": "2.1.0",
        "last_render_timestamp": "2026-05-05T12:00:00Z",
        "files": [],
    }


def test_absent_file_returns_present_false(tmp_path: Path) -> None:
    result = read_bootstrap_manifest(tmp_path)
    assert result.present is False
    assert result.payload == {}
    assert result.manifest_schema_version is None


def test_well_formed_v10_manifest_reads_clean(tmp_path: Path) -> None:
    _write_manifest(tmp_path, _well_formed_v10_manifest())
    result = read_bootstrap_manifest(tmp_path)

    assert result.present is True
    assert result.manifest_schema_version == "1.0"
    assert result.warnings == []
    assert result.infos == []
    assert result.payload["plugin_version"] == "2.1.0"


def test_v10_required_fields_enforced(tmp_path: Path) -> None:
    incomplete = {"manifest_schema_version": "1.0", "files": []}
    _write_manifest(tmp_path, incomplete)
    with pytest.raises(ConfigError) as exc:
        read_bootstrap_manifest(tmp_path)
    msg = str(exc.value)
    assert "plugin_version" in msg or "last_render_timestamp" in msg


def test_v10_files_must_be_list(tmp_path: Path) -> None:
    bad = {
        "manifest_schema_version": "1.0",
        "plugin_version": "2.1.0",
        "last_render_timestamp": "2026-05-05T12:00:00Z",
        "files": "not-a-list",
    }
    _write_manifest(tmp_path, bad)
    with pytest.raises(ConfigError) as exc:
        read_bootstrap_manifest(tmp_path)
    assert "must be a list" in str(exc.value)


def test_absent_manifest_schema_version_treated_as_v10(tmp_path: Path) -> None:
    """When the field is absent, the reader treats the file as v1.0 and
    enforces the v1.0 required-field set, fail-closing on missing fields.

    This is the brownfield case: a hand-edited manifest without an
    explicit schema_version still has to satisfy v1.0 required-field
    contracts so downstream consumers can rely on the shape.
    """
    payload_v10_no_field = {
        "plugin_version": "2.1.0",
        "last_render_timestamp": "2026-05-05T12:00:00Z",
        "files": [],
    }
    _write_manifest(tmp_path, payload_v10_no_field)
    result = read_bootstrap_manifest(tmp_path)
    assert result.manifest_schema_version is None
    assert result.payload["plugin_version"] == "2.1.0"


def test_v11_forward_compat_emits_info(tmp_path: Path) -> None:
    payload = _well_formed_v10_manifest()
    payload["manifest_schema_version"] = "1.1"
    payload["future_field"] = "yes"
    _write_manifest(tmp_path, payload)
    result = read_bootstrap_manifest(tmp_path)
    assert result.manifest_schema_version == "1.1"
    assert result.warnings == []
    assert len(result.infos) == 1
    assert "future_field" in result.infos[0]


def test_major_v2_fails_closed(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"manifest_schema_version": "2.0"})
    with pytest.raises(ConfigError) as exc:
        read_bootstrap_manifest(tmp_path)
    assert "major version >= 2" in str(exc.value)


def test_malformed_manifest_schema_version_fails_closed(tmp_path: Path) -> None:
    _write_manifest(tmp_path, {"manifest_schema_version": "garbage"})
    with pytest.raises(ConfigError) as exc:
        read_bootstrap_manifest(tmp_path)
    assert "malformed" in str(exc.value).lower() or "expected" in str(exc.value).lower()


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    (launchpad / "bootstrap-manifest.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        read_bootstrap_manifest(tmp_path)
    assert "JSON parse error" in str(exc.value)


def test_non_mapping_top_level_fails_closed(tmp_path: Path) -> None:
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    (launchpad / "bootstrap-manifest.json").write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        read_bootstrap_manifest(tmp_path)
    assert "mapping" in str(exc.value)
