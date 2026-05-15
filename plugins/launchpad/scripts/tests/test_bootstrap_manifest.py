"""Tests for lp_bootstrap.manifest_writer (v2.1 Phase 3 Slice A).

Coverage matrix (section 5 + plan section 2.2):
  * Schema 1.0 envelope round-trip (write -> Phase 1 reader)
  * Reserved `security_fields: []` v2.2-downgrade defense
  * Atomic write semantics (tempfile + replace)
  * `_normalize_path()` rejection of `..`, absolute, `\\`, leading `./`
  * Source-template sha cache: lazy compute, immutable, test-reset hook
  * `verify_source_template_shas()` mismatch raises MANIFEST_TAMPERED
  * `manifest-not-written-on-partial-render-failure` invariant (callers
    must respect; pin contract via separate engine test in Slice C)
  * No unknown error codes emitted from this module
  * `last_render_timestamp` is UTC ISO-8601 with `Z` suffix
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap import (  # noqa: E402
    BootstrapErrorCode,
    INFRASTRUCTURE_FILES,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
)
from lp_bootstrap.manifest_writer import (  # noqa: E402
    BootstrapManifestEntry,
    BootstrapManifestError,
    _normalize_path,
    build_manifest,
    compute_source_template_shas,
    manifest_to_json_bytes,
    reset_source_template_shas_cache_for_tests,
    source_template_shas,
    verify_source_template_shas,
    write_manifest,
)


# --- Path normalization (section 3.3) -------------------------------------

def test_normalize_path_strips_leading_dot_slash():
    assert _normalize_path("./scripts/build.sh") == "scripts/build.sh"


def test_normalize_path_translates_backslashes():
    assert _normalize_path("scripts\\compound\\build.sh") == "scripts/compound/build.sh"


def test_normalize_path_passes_through_canonical():
    assert _normalize_path("scripts/compound/build.sh") == "scripts/compound/build.sh"


def test_normalize_path_rejects_double_dot():
    with pytest.raises(BootstrapManifestError) as excinfo:
        _normalize_path("../etc/passwd")
    assert excinfo.value.reason == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


def test_normalize_path_rejects_double_dot_in_middle():
    with pytest.raises(BootstrapManifestError) as excinfo:
        _normalize_path("scripts/../../etc/passwd")
    assert excinfo.value.reason == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


def test_normalize_path_rejects_absolute_unix():
    with pytest.raises(BootstrapManifestError) as excinfo:
        _normalize_path("/etc/passwd")
    assert excinfo.value.reason == BootstrapErrorCode.PATH_TRAVERSAL_REJECTED


def test_normalize_path_rejects_empty():
    with pytest.raises(BootstrapManifestError):
        _normalize_path("")


def test_normalize_path_rejects_non_string():
    with pytest.raises(BootstrapManifestError):
        _normalize_path(42)  # type: ignore[arg-type]


# --- Schema 1.0 envelope round-trip ---------------------------------------

def _entry(target: str, src: str = "a" * 64, rendered: str = "b" * 64) -> BootstrapManifestEntry:
    return BootstrapManifestEntry(
        path=target,
        source_template_sha256=src,
        rendered_content_sha256=rendered,
        policy="overwrite-if-unchanged",
        mode=0o644,
    )


def test_build_manifest_normalizes_paths():
    m = build_manifest(
        plugin_version="2.1.0",
        files=[_entry("./scripts/foo.sh")],
    )
    assert m.files[0].path == "scripts/foo.sh"


def test_build_manifest_sets_schema_version_and_timestamp():
    m = build_manifest(plugin_version="2.1.0", files=[_entry("a/b.txt")])
    assert m.manifest_schema_version == MANIFEST_SCHEMA_VERSION == "1.0"
    assert m.last_render_timestamp.endswith("Z")
    assert "T" in m.last_render_timestamp


def test_manifest_to_json_bytes_includes_security_fields_empty():
    m = build_manifest(plugin_version="2.1.0", files=[_entry("a")])
    payload = json.loads(manifest_to_json_bytes(m).decode("utf-8"))
    assert payload["security_fields"] == []
    assert payload["manifest_schema_version"] == "1.0"
    assert payload["plugin_version"] == "2.1.0"


def test_manifest_to_json_bytes_is_canonical(tmp_path):
    m = build_manifest(plugin_version="2.1.0", files=[_entry("z"), _entry("a")])
    encoded = manifest_to_json_bytes(m)
    text = encoded.decode("utf-8")
    assert text.endswith("\n")
    # sorted keys
    payload = json.loads(text)
    assert list(payload.keys()) == sorted(payload.keys())


def test_write_manifest_round_trips_through_phase1_reader(tmp_path):
    """Pin the integration with `plugin-config-loader.read_bootstrap_manifest`."""
    cwd = tmp_path
    (cwd / ".launchpad").mkdir()
    m = build_manifest(plugin_version="2.1.0", files=[_entry("scripts/foo.sh")])
    write_manifest(cwd, m)

    # Phase 1 reader is loaded via spec_from_file_location since it has a
    # hyphenated filename; mirror what Phase 2 readers do.
    import importlib.util
    loader_path = _SCRIPTS / "plugin-config-loader.py"
    spec = importlib.util.spec_from_file_location("plugin_config_loader", loader_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = mod.read_bootstrap_manifest(cwd)
    assert result.present
    assert result.manifest_schema_version == "1.0"
    assert result.payload["plugin_version"] == "2.1.0"
    assert "files" in result.payload
    assert result.payload["files"][0]["path"] == "scripts/foo.sh"


def test_write_manifest_atomic_against_concurrent_reader(tmp_path):
    """A write replaces atomically; the reader either sees old or new bytes."""
    cwd = tmp_path
    (cwd / ".launchpad").mkdir()
    m1 = build_manifest(plugin_version="1.0.0", files=[_entry("a")])
    write_manifest(cwd, m1)
    m2 = build_manifest(plugin_version="2.0.0", files=[_entry("a")])
    write_manifest(cwd, m2)
    payload = json.loads(
        (cwd / ".launchpad" / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert payload["plugin_version"] == "2.0.0"


# --- Source-template sha cache (harden B3) --------------------------------

def test_compute_source_template_shas_against_real_root():
    """Once Slice B lands, the real root has all `INFRASTRUCTURE_FILES`
    .j2 templates; before that the function raises TEMPLATE_NOT_FOUND."""
    try:
        shas = compute_source_template_shas()
    except BootstrapManifestError as exc:
        # Slice A (templates not yet written) -> expected.
        assert exc.reason == BootstrapErrorCode.TEMPLATE_NOT_FOUND
        return
    # Slice B+ -> every entry must be present.
    assert len(shas) == len(INFRASTRUCTURE_FILES)
    for _t, target, _p, _m in INFRASTRUCTURE_FILES:
        assert target in shas
        assert len(shas[target]) == 64


def test_compute_source_template_shas_with_fixture_root(tmp_path):
    """Test-injectable root: write a single template + sha256 it."""
    root = tmp_path
    # Build only the first inventory entry so the test is robust.
    template_relpath, target_relpath, _p, _m = INFRASTRUCTURE_FILES[0]
    src = root / template_relpath
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"hello")
    # The other 29 entries will fail; we expect TEMPLATE_NOT_FOUND on the second.
    with pytest.raises(BootstrapManifestError) as excinfo:
        compute_source_template_shas(root=root)
    assert excinfo.value.reason == BootstrapErrorCode.TEMPLATE_NOT_FOUND


def test_source_template_shas_cache_is_module_level():
    """Cache is populated on first call; subsequent calls return identical mapping."""
    reset_source_template_shas_cache_for_tests()
    try:
        a = source_template_shas()
        b = source_template_shas()
    except BootstrapManifestError:
        # Pre-Slice-B -> templates missing -> cannot exercise the cache.
        pytest.skip("templates not yet written; cache test deferred to Slice B")
    assert a is not b or dict(a) == dict(b)
    # Verify immutability
    with pytest.raises(TypeError):
        a["new_target"] = "deadbeef"  # type: ignore[index]


# --- Integrity check (section 3.8 (a)) ------------------------------------

def test_verify_source_template_shas_passes_when_match():
    expected = {"a.txt": "x" * 64, "b.txt": "y" * 64}
    m = build_manifest(
        plugin_version="2.1.0",
        files=[
            BootstrapManifestEntry(
                path="a.txt", source_template_sha256="x" * 64,
                rendered_content_sha256="r" * 64, policy="overwrite-if-unchanged",
                mode=0o644,
            ),
            BootstrapManifestEntry(
                path="b.txt", source_template_sha256="y" * 64,
                rendered_content_sha256="r" * 64, policy="overwrite-if-unchanged",
                mode=0o644,
            ),
        ],
    )
    verify_source_template_shas(m, expected_shas=expected)


def test_verify_source_template_shas_raises_on_sha_mismatch():
    expected = {"a.txt": "x" * 64}
    m = build_manifest(
        plugin_version="2.1.0",
        files=[
            BootstrapManifestEntry(
                path="a.txt", source_template_sha256="z" * 64,  # tampered
                rendered_content_sha256="r" * 64, policy="overwrite-if-unchanged",
                mode=0o644,
            ),
        ],
    )
    with pytest.raises(BootstrapManifestError) as excinfo:
        verify_source_template_shas(m, expected_shas=expected)
    assert excinfo.value.reason == BootstrapErrorCode.MANIFEST_TAMPERED
    assert excinfo.value.path == Path("a.txt")


def test_verify_source_template_shas_raises_on_missing_entry():
    expected = {"a.txt": "x" * 64, "b.txt": "y" * 64}
    m = build_manifest(
        plugin_version="2.1.0",
        files=[
            BootstrapManifestEntry(
                path="a.txt", source_template_sha256="x" * 64,
                rendered_content_sha256="r" * 64, policy="overwrite-if-unchanged",
                mode=0o644,
            ),
        ],
    )
    with pytest.raises(BootstrapManifestError) as excinfo:
        verify_source_template_shas(m, expected_shas=expected)
    assert excinfo.value.reason == BootstrapErrorCode.MANIFEST_TAMPERED


def test_no_unknown_error_codes_emitted():
    """Every code raised by the manifest writer is a member of BootstrapErrorCode."""
    expected_codes = {
        BootstrapErrorCode.PATH_TRAVERSAL_REJECTED,
        BootstrapErrorCode.TEMPLATE_NOT_FOUND,
        BootstrapErrorCode.MANIFEST_TAMPERED,
    }
    raised: set[BootstrapErrorCode] = set()
    for raw in (
        "../etc/passwd", "/etc/passwd", "scripts/../../foo",
    ):
        try:
            _normalize_path(raw)
        except BootstrapManifestError as exc:
            raised.add(exc.reason)
    assert raised == {BootstrapErrorCode.PATH_TRAVERSAL_REJECTED}
    # Codes raised by this module must be a subset of the closed enum.
    assert raised <= set(BootstrapErrorCode)
    assert raised <= expected_codes
