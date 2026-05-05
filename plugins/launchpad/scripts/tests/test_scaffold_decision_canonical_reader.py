"""Tests for `read_scaffold_decision()` 4-rule acceptance ladder.

V3 plan §11.3 + HANDSHAKE §10.v2.1:
  * file missing -> present=False, payload={}
  * schema_version absent or "1.0" -> legacy 1.0 read with WARN
  * "1.1" -> full v2.1 read
  * "1.x" x>1 -> forward-compat with INFO listing unknown fields
  * major>=2 -> ConfigError fail-closed
  * malformed JSON -> ConfigError fail-closed
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

# plugin-config-loader.py uses a hyphenated filename; load via importlib.
_spec = importlib.util.spec_from_file_location(
    "plugin_config_loader", _SCRIPTS / "plugin-config-loader.py"
)
plugin_config_loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin_config_loader)


ConfigError = plugin_config_loader.ConfigError
read_scaffold_decision = plugin_config_loader.read_scaffold_decision


def _write_decision(tmp_path: Path, payload: dict) -> Path:
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir(parents=True, exist_ok=True)
    target = launchpad / "scaffold-decision.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_absent_file_returns_present_false(tmp_path: Path) -> None:
    result = read_scaffold_decision(tmp_path)
    assert result.present is False
    assert result.payload == {}
    assert result.schema_version is None
    assert result.warnings == []
    assert result.infos == []


def test_legacy_v10_envelope_reads_with_warn(tmp_path: Path) -> None:
    _write_decision(tmp_path, {"version": "1.0", "layers": []})
    result = read_scaffold_decision(tmp_path)

    assert result.present is True
    assert result.schema_version is None  # `schema_version` field is absent
    assert result.payload["version"] == "1.0"
    # Warning emitted because schema_version is absent
    assert len(result.warnings) == 1
    assert "absent" in result.warnings[0].lower() or "1.0" in result.warnings[0]


def test_explicit_v10_schema_version_also_emits_warn(tmp_path: Path) -> None:
    _write_decision(tmp_path, {"schema_version": "1.0", "version": "1.0"})
    result = read_scaffold_decision(tmp_path)
    assert result.schema_version == "1.0"
    assert len(result.warnings) == 1


def test_v11_envelope_reads_in_full_mode(tmp_path: Path) -> None:
    _write_decision(tmp_path, {
        "schema_version": "1.1",
        "version": "1.0",
        "plugin_version": "2.1.0",
        "layers": [{"stack": "next", "role": "fullstack", "path": "."}],
        "stacks": ["next"],
        "identity": {"pii_opt_in": False},
    })
    result = read_scaffold_decision(tmp_path)
    assert result.present is True
    assert result.schema_version == "1.1"
    assert result.warnings == []
    assert result.infos == []
    assert result.payload["plugin_version"] == "2.1.0"


def test_v12_forward_compat_emits_info_for_unknown_fields(tmp_path: Path) -> None:
    _write_decision(tmp_path, {
        "schema_version": "1.2",
        "version": "1.0",
        "future_field_alpha": True,
        "future_field_beta": "value",
    })
    result = read_scaffold_decision(tmp_path)
    assert result.schema_version == "1.2"
    assert result.warnings == []
    assert len(result.infos) == 1
    assert "future_field_alpha" in result.infos[0]
    assert "future_field_beta" in result.infos[0]


def test_major_v2_fails_closed(tmp_path: Path) -> None:
    _write_decision(tmp_path, {"schema_version": "2.0"})
    with pytest.raises(ConfigError) as exc:
        read_scaffold_decision(tmp_path)
    assert "major version >= 2" in str(exc.value)


def test_malformed_schema_version_fails_closed(tmp_path: Path) -> None:
    _write_decision(tmp_path, {"schema_version": "not-a-version"})
    with pytest.raises(ConfigError) as exc:
        read_scaffold_decision(tmp_path)
    assert "malformed" in str(exc.value).lower() or "expected" in str(exc.value).lower()


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    (launchpad / "scaffold-decision.json").write_text("not json {", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        read_scaffold_decision(tmp_path)
    assert "JSON parse error" in str(exc.value)


def test_non_mapping_top_level_fails_closed(tmp_path: Path) -> None:
    launchpad = tmp_path / ".launchpad"
    launchpad.mkdir()
    (launchpad / "scaffold-decision.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        read_scaffold_decision(tmp_path)
    assert "mapping" in str(exc.value)
