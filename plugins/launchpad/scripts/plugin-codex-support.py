"""Deterministic support, evidence, digest, and documentation producer.

The producer is the only component that turns the audited canonical graph into
stage-typed runtime records. Consumers receive an exact path/digest set and do
not rediscover or retraverse canonical definitions.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import os
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final, NoReturn

from atomic_io import (
    _assert_path_safe,
    atomic_write_replace,
    atomic_write_replace_batch,
)

SCRIPT_REAL_PATH: Final = Path(os.path.realpath(__file__))
SCRIPT_DIR: Final = SCRIPT_REAL_PATH.parent
PLUGIN_ROOT: Final = SCRIPT_DIR.parent
REPOSITORY_ROOT: Final = PLUGIN_ROOT.parents[1]
PROTOCOL_PATH: Final = SCRIPT_DIR / "plugin-codex-protocol.py"
CORPUS_PATH: Final = SCRIPT_DIR / "plugin-codex-corpus.py"
RESOLVER_PATH: Final = SCRIPT_DIR / "plugin-codex-resolver.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load_module("launchpad_codex_protocol_for_support", PROTOCOL_PATH)
_CORPUS = _load_module("launchpad_codex_corpus_for_support", CORPUS_PATH)
_RESOLVER = _load_module("launchpad_codex_resolver_for_support", RESOLVER_PATH)


class SupportError(ValueError):
    """Stable support/evidence failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.reporting_class = _PROTOCOL.load_protocol().reporting_class_for_error(code)


def _fail(code: str, message: str) -> NoReturn:
    raise SupportError(code, message)


class _DuplicateJsonKey(ValueError):
    pass


def _strict_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey(key)
        value[key] = item
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list, frozenset)):
        return [_jsonable(item) for item in value]
    return value


def _strict_load_json(path: Path, *, maximum_bytes: int) -> object:
    _assert_path_safe(path, path.parent.resolve(strict=True))
    try:
        before = path.lstat()
    except OSError:
        _fail("SOURCE_NOT_FOUND", f"cannot read {path.name}")
    if stat.S_ISLNK(before.st_mode):
        _fail("PATH_SYMLINK", f"{path.name} is a symlink")
    if not stat.S_ISREG(before.st_mode):
        _fail("SOURCE_TYPE_INVALID", f"{path.name} is not a regular file")
    try:
        raw = path.read_bytes()
    except OSError:
        _fail("SOURCE_NOT_FOUND", f"cannot read {path.name}")
    if len(raw) > maximum_bytes:
        _fail("SOURCE_TOO_LARGE", f"{path.name} exceeds its size limit")
    try:
        after = path.stat(follow_symlinks=False)
    except OSError:
        _fail("PATH_RACE", f"{path.name} changed while it was read")
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        _fail("PATH_RACE", f"{path.name} changed while it was read")
    try:
        return json.loads(raw, object_pairs_hook=_strict_json_pairs)
    except (_DuplicateJsonKey, UnicodeDecodeError, json.JSONDecodeError):
        _fail("RECORD_INVALID", f"{path.name} is not strict JSON")


def _packaging_sequence(protocol: Any, field: str) -> tuple[str, ...]:
    value = protocol.packaging.get(field)
    if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
        _fail("PROTOCOL_FILE_INVALID", f"packaging.{field} must be a string array")
    if value != tuple(sorted(set(value))):
        _fail("PROTOCOL_FILE_INVALID", f"packaging.{field} must be sorted and unique")
    return value


def generated_slots(protocol: Any | None = None) -> tuple[str, ...]:
    return _packaging_sequence(protocol or _PROTOCOL.load_protocol(), "generated_slots")


def _snapshot(root: Path, relative_path: str, maximum_bytes: int) -> Any:
    try:
        with _RESOLVER._anchor_directory(root) as anchored:
            return _RESOLVER._read_snapshot(
                anchored,
                relative_path,
                maximum_bytes=maximum_bytes,
                maximum_depth=_PROTOCOL.load_protocol(
                    root / "codex" / "adapter-protocol.json"
                ).limits["catalog_depth"]
                + 4,
            )
    except _RESOLVER.ResolverError as exc:
        _fail(exc.code, str(exc))


@dataclass(frozen=True)
class SupportBundle:
    schema_version: int
    runtime: Any
    compatibility_predicates: tuple[Any, ...]
    qualifications: tuple[Any, ...]


def bundle_as_dict(bundle: SupportBundle) -> dict[str, object]:
    value = _jsonable(bundle)
    if not isinstance(value, dict):
        raise TypeError("support bundle serialization failed")
    return value


def _normalize_bundle(
    value: object, *, protocol_path: Path | None = None
) -> SupportBundle:
    protocol = _PROTOCOL.load_protocol(protocol_path)
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "runtime",
        "compatibility_predicates",
        "qualifications",
    }:
        _fail("RECORD_INVALID", "support bundle fields differ")
    if value["schema_version"] != 1:
        _fail("PROTOCOL_VERSION_UNSUPPORTED", "support bundle schema is unsupported")
    runtime = _PROTOCOL.normalize_runtime_record(value["runtime"], protocol)
    predicates_raw = value["compatibility_predicates"]
    qualifications_raw = value["qualifications"]
    if not isinstance(predicates_raw, list) or not isinstance(qualifications_raw, list):
        _fail("RECORD_INVALID", "predicates and qualifications must be arrays")
    predicates = tuple(
        _PROTOCOL.normalize_compatibility_predicate_record(item, protocol)
        for item in predicates_raw
    )
    qualifications = tuple(
        _PROTOCOL.normalize_qualification_record(item, protocol)
        for item in qualifications_raw
    )
    predicate_ids = [item.predicate_id for item in predicates]
    qualification_ids = [item.qualification_id for item in qualifications]
    if predicate_ids != sorted(predicate_ids) or len(predicate_ids) != len(
        set(predicate_ids)
    ):
        _fail("RECORD_INVALID", "predicates must be unique and sorted")
    if qualification_ids != sorted(qualification_ids) or len(qualification_ids) != len(
        set(qualification_ids)
    ):
        _fail("RECORD_INVALID", "qualifications must be unique and sorted")
    if set(runtime.qualification_ids) != set(qualification_ids):
        _fail("INTEGRITY_MISMATCH", "runtime qualification IDs differ")
    if any(
        item.runtime_payload_digest != runtime.runtime_payload_digest
        for item in qualifications
    ):
        _fail("INTEGRITY_MISMATCH", "qualification binds another runtime payload")
    root_ids = set(runtime.root_ids)
    if any(item.resource_id not in root_ids for item in predicates):
        _fail("RECORD_INVALID", "predicate references a non-root resource")
    if any(
        not set(item.qualification_ids).issubset(qualification_ids)
        for item in predicates
    ):
        _fail("INTEGRITY_MISMATCH", "predicate references an unknown qualification")
    support = {item.resource_id: item for item in runtime.support}
    for resource_id in root_ids:
        rules = [item for item in predicates if item.resource_id == resource_id]
        if not rules:
            _fail("RECORD_INVALID", "every root requires a compatibility predicate")
        states = {
            (item.base_support_state, item.blocked_reason_codes, item.fallback)
            for item in rules
        }
        if len(states) != 1 or resource_id not in support:
            _fail("RECORD_INVALID", "predicate and support state differ")
        state, reasons, fallback = next(iter(states))
        record = support[resource_id]
        if (
            state != record.base_support_state
            or reasons != record.blocked_reason_codes
            or fallback != record.fallback
        ):
            _fail("INTEGRITY_MISMATCH", "predicate and support state differ")
    return SupportBundle(1, runtime, predicates, qualifications)


def load_bundle(path: Path, *, protocol_path: Path | None = None) -> SupportBundle:
    protocol = _PROTOCOL.load_protocol(protocol_path)
    raw = _strict_load_json(
        path, maximum_bytes=protocol.limits["documentation_file_bytes"]
    )
    return _normalize_bundle(raw, protocol_path=protocol_path)


def _reachable_nodes(runtime: Any, protocol: Any) -> tuple[Any, ...]:
    by_id = {node.id: node for node in runtime.nodes}
    visited: set[str] = set()
    pending = list(runtime.root_ids)
    edge_count = 0
    while pending:
        resource_id = pending.pop()
        if resource_id in visited:
            continue
        node = by_id.get(resource_id)
        if node is None:
            _fail("INTEGRITY_MISMATCH", "graph edge references an absent node")
        visited.add(resource_id)
        children = (*node.direct.commands, *node.direct.skills, *node.direct.agents)
        edge_count += len(children) + node.direct.count
        if edge_count > protocol.limits["aggregate_edges"]:
            _fail("LIMIT_EXCEEDED", "graph edge budget exceeded")
        pending.extend(children)
    return tuple(by_id[item] for item in sorted(visited))


def _owned_path(node: Any, family: str, value: str) -> str:
    lexical = PurePosixPath(value)
    if family in {"references", "assets"} and node.kind == "skill":
        return (PurePosixPath(node.source_path).parent / lexical).as_posix()
    return lexical.as_posix()


def _runtime_paths(runtime: Any, protocol: Any) -> tuple[str, ...]:
    paths = set(_packaging_sequence(protocol, "runtime_helpers"))
    paths.add(".codex-plugin/plugin.json")
    for node in _reachable_nodes(runtime, protocol):
        paths.add(node.source_path)
        for family, values in (
            ("references", node.direct.references),
            ("assets", node.direct.assets),
            ("scripts", node.direct.scripts),
        ):
            paths.update(_owned_path(node, family, value) for value in values)
    if paths & set(generated_slots(protocol)):
        _fail("PROTOCOL_FILE_INVALID", "runtime and generated package domains overlap")
    return tuple(sorted(paths))


def _seal_runtime_files(
    plugin_root: Path, runtime: Any, protocol: Any
) -> tuple[Any, ...]:
    maximum = max(
        protocol.limits["body_bytes"] + protocol.limits["frontmatter_bytes"],
        protocol.limits["documentation_file_bytes"],
    )
    records = []
    for path in _runtime_paths(runtime, protocol):
        snapshot = _snapshot(plugin_root, path, maximum)
        records.append(
            _PROTOCOL.normalize_runtime_file_record(
                {"path": path, "digest": snapshot.digest, "size": snapshot.size},
                protocol,
            )
        )
    return tuple(records)


def _runtime_digest(files: Sequence[Any], protocol: Any) -> str:
    payload = {
        "domain": "runtime_payload_digest",
        "protocol_version": protocol.protocol_version,
        "files": [_jsonable(item) for item in files],
    }
    return _sha256(_canonical_json(payload))


def _blocked_predicates(runtime: Any, protocol: Any) -> tuple[Any, ...]:
    nodes = {node.id: node for node in runtime.nodes}
    records = []
    for resource_id in runtime.root_ids:
        node = nodes[resource_id]
        records.append(
            _PROTOCOL.normalize_compatibility_predicate_record(
                {
                    "predicate_id": f"{resource_id}-default",
                    "resource_id": resource_id,
                    "host": "*",
                    "operating_system": "*",
                    "required_capabilities": list(node.capabilities.required),
                    "tool_versions": {},
                    "base_support_state": "blocked",
                    "blocked_reason_codes": ["WORKFLOW_DEPENDENCY_CLOSURE_UNPROVEN"],
                    "fallback": node.capabilities.fallback,
                    "qualification_ids": [],
                },
                protocol,
            )
        )
    return tuple(records)


def _support_from_predicates(
    predicates: Sequence[Any], protocol: Any
) -> tuple[Any, ...]:
    by_resource: dict[str, Any] = {}
    for item in predicates:
        prior = by_resource.setdefault(item.resource_id, item)
        if (
            prior.base_support_state,
            prior.blocked_reason_codes,
            prior.fallback,
        ) != (
            item.base_support_state,
            item.blocked_reason_codes,
            item.fallback,
        ):
            _fail("RECORD_INVALID", "predicates disagree on immutable base support")
    return tuple(
        _PROTOCOL.normalize_support_record(
            {
                "resource_id": item.resource_id,
                "base_support_state": item.base_support_state,
                "blocked_reason_codes": list(item.blocked_reason_codes),
                "fallback": item.fallback,
            },
            protocol,
        )
        for item in sorted(by_resource.values(), key=lambda value: value.resource_id)
    )


def build_inventory(plugin_root: Path = PLUGIN_ROOT) -> SupportBundle:
    audit = _CORPUS.audit_corpus(plugin_root)
    runtime = audit.inventory
    predicates = _blocked_predicates(
        runtime,
        _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json"),
    )
    raw = _jsonable(runtime)
    assert isinstance(raw, dict)
    raw["support"] = [
        _jsonable(item)
        for item in _support_from_predicates(
            predicates,
            _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json"),
        )
    ]
    normalized = _PROTOCOL.normalize_runtime_record(
        raw, _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json")
    )
    return SupportBundle(1, normalized, predicates, ())


def build_test_candidate(
    plugin_root: Path,
    *,
    release_stage: str = "dogfood",
) -> SupportBundle:
    protocol_path = plugin_root / "codex" / "adapter-protocol.json"
    protocol = _PROTOCOL.load_protocol(protocol_path)
    audit = _CORPUS.audit_corpus(plugin_root)
    inventory = audit.inventory
    files = _seal_runtime_files(plugin_root, inventory, protocol)
    digest = _runtime_digest(files, protocol)
    predicates = tuple(
        sorted(
            _blocked_predicates(inventory, protocol),
            key=lambda item: item.predicate_id,
        )
    )
    raw = _jsonable(inventory)
    assert isinstance(raw, dict)
    raw.update(
        {
            "stage": "test_candidate",
            "release_stage": release_stage,
            "runtime_payload_digest": digest,
            "runtime_files": [_jsonable(item) for item in files],
            "support": [
                _jsonable(item)
                for item in _support_from_predicates(predicates, protocol)
            ],
            "generated_slots": list(generated_slots(protocol)),
        }
    )
    runtime = _PROTOCOL.normalize_runtime_record(raw, protocol)
    return _normalize_bundle(
        {
            "schema_version": 1,
            "runtime": _jsonable(runtime),
            "compatibility_predicates": [_jsonable(item) for item in predicates],
            "qualifications": [],
        },
        protocol_path=protocol_path,
    )


def promote_release(
    candidate: SupportBundle, qualification_input: object
) -> SupportBundle:
    runtime = candidate.runtime
    if runtime.stage != "test_candidate" or runtime.runtime_payload_digest is None:
        _fail("RECORD_STAGE_INVALID", "only a test candidate can be promoted")
    if not isinstance(qualification_input, Mapping) or set(qualification_input) != {
        "compatibility_predicates",
        "qualifications",
    }:
        _fail("RECORD_INVALID", "qualification input fields differ")
    predicates_raw = qualification_input["compatibility_predicates"]
    qualifications_raw = qualification_input["qualifications"]
    if not isinstance(predicates_raw, list) or not isinstance(qualifications_raw, list):
        _fail("RECORD_INVALID", "qualification arrays are required")
    protocol = _PROTOCOL.load_protocol()
    predicates = tuple(
        _PROTOCOL.normalize_compatibility_predicate_record(item, protocol)
        for item in predicates_raw
    )
    qualifications = tuple(
        _PROTOCOL.normalize_qualification_record(item, protocol)
        for item in qualifications_raw
    )
    raw = _jsonable(runtime)
    assert isinstance(raw, dict)
    raw.update(
        {
            "stage": "release",
            "support": [
                _jsonable(item)
                for item in _support_from_predicates(predicates, protocol)
            ],
            "qualification_ids": sorted(
                item.qualification_id for item in qualifications
            ),
        }
    )
    release = _PROTOCOL.normalize_runtime_record(raw, protocol)
    return _normalize_bundle(
        {
            "schema_version": 1,
            "runtime": _jsonable(release),
            "compatibility_predicates": [
                _jsonable(item)
                for item in sorted(predicates, key=lambda item: item.predicate_id)
            ],
            "qualifications": [
                _jsonable(item)
                for item in sorted(
                    qualifications, key=lambda item: item.qualification_id
                )
            ],
        }
    )


def evidence_bytes(bundle: SupportBundle) -> bytes:
    if bundle.runtime.stage != "release":
        _fail("RECORD_STAGE_INVALID", "only release evidence is packageable")
    return _pretty_json(bundle_as_dict(bundle))


def evidence_digest(bundle: SupportBundle) -> str:
    return _sha256(evidence_bytes(bundle))


def verify_runtime_set(bundle: SupportBundle, plugin_root: Path) -> None:
    if bundle.runtime.stage == "inventory":
        _fail("RECORD_STAGE_INVALID", "inventory has no sealed runtime set")
    protocol = _PROTOCOL.load_protocol(plugin_root / "codex" / "adapter-protocol.json")
    actual = []
    for record in bundle.runtime.runtime_files:
        snapshot = _snapshot(
            plugin_root,
            record.path,
            max(protocol.limits["documentation_file_bytes"], record.size),
        )
        actual.append(
            _PROTOCOL.normalize_runtime_file_record(
                {"path": record.path, "digest": snapshot.digest, "size": snapshot.size},
                protocol,
            )
        )
    if [_jsonable(item) for item in actual] != [
        _jsonable(item) for item in bundle.runtime.runtime_files
    ]:
        _fail("INTEGRITY_MISMATCH", "sealed runtime file set changed")
    if _runtime_digest(actual, protocol) != bundle.runtime.runtime_payload_digest:
        _fail("INTEGRITY_MISMATCH", "runtime payload digest changed")
    if bundle.runtime.generated_slots != generated_slots(protocol):
        _fail("INTEGRITY_MISMATCH", "generated package slots changed")


def select_compatibility_predicate(
    bundle: SupportBundle,
    resource_id: str,
    *,
    host: str,
    operating_system: str,
    capabilities: Sequence[str],
    tool_versions: Mapping[str, str],
) -> Any:
    candidates = []
    available = set(capabilities)
    for item in bundle.compatibility_predicates:
        if item.resource_id != resource_id:
            continue
        if item.host not in {"*", host} or item.operating_system not in {
            "*",
            operating_system,
        }:
            continue
        if any(
            tool_versions.get(key) != value for key, value in item.tool_versions.items()
        ):
            continue
        missing = set(item.required_capabilities) - available
        score = (
            int(item.host != "*"),
            int(item.operating_system != "*"),
            len(item.tool_versions),
            len(item.required_capabilities),
        )
        candidates.append((score, item, missing))
    if not candidates:
        _fail("CAPABILITY_BLOCKED", "no compatible support predicate")
    best_score = max(item[0] for item in candidates)
    best = [item for item in candidates if item[0] == best_score]
    if len(best) != 1:
        _fail("RECORD_INVALID", "compatible support predicate is ambiguous")
    predicate, missing = best[0][1], best[0][2]
    if missing:
        return _PROTOCOL.normalize_availability_record(
            {
                "resource_id": resource_id,
                "applicability": "applicable",
                "effective_availability": "blocked",
                "reason_codes": ["CAPABILITY_BLOCKED"],
            }
        )
    if predicate.base_support_state == "blocked":
        return _PROTOCOL.normalize_availability_record(
            {
                "resource_id": resource_id,
                "applicability": "applicable",
                "effective_availability": "blocked",
                "reason_codes": list(predicate.blocked_reason_codes),
            }
        )
    return _PROTOCOL.normalize_availability_record(
        {
            "resource_id": resource_id,
            "applicability": "applicable",
            "effective_availability": "available",
            "reason_codes": [],
        }
    )


def apply_overlay(base: Any, overlay: Any) -> Any:
    """Apply a non-persisted overlay that can preserve or downgrade only."""
    if base.resource_id != overlay.resource_id:
        _fail("RECORD_INVALID", "overlay resource differs")
    if (
        base.effective_availability == "blocked"
        and overlay.effective_availability == "available"
    ):
        _fail("CAPABILITY_BLOCKED", "an overlay cannot promote blocked support")
    return overlay


def _render_summary(bundle: SupportBundle) -> str:
    supported = sum(
        item.base_support_state == "supported" for item in bundle.runtime.support
    )
    blocked = len(bundle.runtime.support) - supported
    return (
        "Codex compatibility is generated from sealed release evidence.\n\n"
        f"- Release stage: `{bundle.runtime.release_stage}`\n"
        f"- Protocol: `{bundle.runtime.protocol_version}`\n"
        f"- Supported entries: {supported}\n"
        f"- Blocked entries: {blocked}\n"
        f"- Qualification records: {len(bundle.qualifications)}"
    )


def _render_matrix(bundle: SupportBundle) -> str:
    lines = [
        "| Resource | Base support | Fallback | Qualifications |",
        "| --- | --- | --- | --- |",
    ]
    by_resource: dict[str, set[str]] = {item: set() for item in bundle.runtime.root_ids}
    for predicate in bundle.compatibility_predicates:
        by_resource[predicate.resource_id].update(predicate.qualification_ids)
    for item in bundle.runtime.support:
        qualifications = ", ".join(sorted(by_resource[item.resource_id])) or "None"
        lines.append(
            f"| `{item.resource_id}` | {item.base_support_state} | "
            f"{item.fallback} | {qualifications} |"
        )
    return "\n".join(lines)


def _replace_region(source: bytes, region: str, rendered: str, maximum: int) -> bytes:
    try:
        text = source.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _fail("SOURCE_INVALID_UTF8", "documentation is not UTF-8")
    begin = f"<!-- BEGIN LAUNCHPAD GENERATED:{region} -->"
    end = f"<!-- END LAUNCHPAD GENERATED:{region} -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        _fail("RECORD_INVALID", "documentation markers must occur exactly once")
    start = text.index(begin) + len(begin)
    finish = text.index(end)
    if finish < start:
        _fail("RECORD_INVALID", "documentation markers are malformed")
    replacement = f"\n{rendered.rstrip()}\n"
    encoded = (text[:start] + replacement + text[finish:]).encode("utf-8")
    if len(encoded) > maximum:
        _fail("LIMIT_EXCEEDED", "rendered documentation exceeds its file limit")
    return encoded


def render_documents(
    bundle: SupportBundle,
    docs_root: Path,
    *,
    write: bool,
) -> tuple[str, ...]:
    if bundle.runtime.stage != "release":
        _fail("RECORD_STAGE_INVALID", "documentation requires release evidence")
    if docs_root.is_symlink():
        _fail("PATH_SYMLINK", "documentation root is a symlink")
    canonical_docs_root = docs_root.resolve(strict=True)
    if canonical_docs_root == REPOSITORY_ROOT.resolve(strict=True):
        _fail("PATH_INVALID", "Section 5 may render fixture documentation only")
    protocol = _PROTOCOL.load_protocol()
    regions = protocol.packaging.get("documentation_regions")
    if not isinstance(regions, Mapping) or set(regions) != {
        "README.md",
        "docs/guides/HOW_IT_WORKS.md",
    }:
        _fail("PROTOCOL_FILE_INVALID", "documentation region authority is invalid")
    rendered_by_region = {
        "codex-beta-summary": _render_summary(bundle),
        "codex-support-matrix": _render_matrix(bundle),
    }
    batch: dict[Path, bytes] = {}
    changed: list[str] = []
    aggregate = 0
    for relative, region in sorted(regions.items()):
        if not isinstance(relative, str) or not isinstance(region, str):
            _fail("PROTOCOL_FILE_INVALID", "documentation region is invalid")
        target = canonical_docs_root / relative
        _assert_path_safe(target, canonical_docs_root)
        try:
            before = target.stat(follow_symlinks=False)
            original = target.read_bytes()
            after = target.stat(follow_symlinks=False)
        except OSError:
            _fail("SOURCE_NOT_FOUND", "fixture documentation cannot be read")
        if not stat.S_ISREG(before.st_mode) or (
            before.st_dev,
            before.st_ino,
            before.st_size,
        ) != (after.st_dev, after.st_ino, after.st_size):
            _fail("PATH_RACE", "fixture documentation changed while it was read")
        aggregate += len(original)
        if aggregate > protocol.limits["documentation_aggregate_bytes"]:
            _fail("LIMIT_EXCEEDED", "documentation aggregate exceeds its limit")
        replacement = _replace_region(
            original,
            region,
            rendered_by_region[region],
            protocol.limits["documentation_file_bytes"],
        )
        if replacement != original:
            changed.append(relative)
            batch[target] = replacement
    if write and batch:
        atomic_write_replace_batch(
            batch,
            default_mode=0o644,
            trusted_root=canonical_docs_root,
        )
    return tuple(changed)


def write_bundle(bundle: SupportBundle, path: Path, *, trusted_root: Path) -> None:
    content = (
        evidence_bytes(bundle)
        if bundle.runtime.stage == "release"
        else _pretty_json(bundle_as_dict(bundle))
    )
    atomic_write_replace(path, content, mode=0o644, trusted_root=trusted_root)
    loaded = load_bundle(
        path,
        protocol_path=trusted_root / "codex" / "adapter-protocol.json"
        if (trusted_root / "codex" / "adapter-protocol.json").is_file()
        else None,
    )
    if bundle_as_dict(loaded) != bundle_as_dict(bundle):
        _fail("INTEGRITY_MISMATCH", "written support bundle did not verify")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "test-candidate"):
        command = subparsers.add_parser(name)
        command.add_argument("--plugin-root", type=Path, default=PLUGIN_ROOT)
        command.add_argument("--output", type=Path)
        command.add_argument("--release-stage", default="dogfood")
    generate = subparsers.add_parser("generate")
    generate.add_argument("--candidate", type=Path, required=True)
    generate.add_argument("--qualifications", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--evidence", type=Path, required=True)
    check.add_argument("--plugin-root", type=Path, required=True)
    render = subparsers.add_parser("render-docs")
    render.add_argument("--evidence", type=Path, required=True)
    render.add_argument("--docs-root", type=Path, required=True)
    mode = render.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inventory":
            bundle = build_inventory(args.plugin_root)
            output = _pretty_json(bundle_as_dict(bundle))
        elif args.command == "test-candidate":
            bundle = build_test_candidate(
                args.plugin_root, release_stage=args.release_stage
            )
            output = _pretty_json(bundle_as_dict(bundle))
        elif args.command == "generate":
            candidate = load_bundle(args.candidate)
            raw = _strict_load_json(
                args.qualifications,
                maximum_bytes=_PROTOCOL.load_protocol().limits[
                    "documentation_file_bytes"
                ],
            )
            bundle = promote_release(candidate, raw)
            write_bundle(bundle, args.output, trusted_root=args.output.parent)
            output = _pretty_json(
                {"evidence_digest": evidence_digest(bundle), "output": str(args.output)}
            )
        elif args.command == "check":
            bundle = load_bundle(
                args.evidence,
                protocol_path=args.plugin_root / "codex" / "adapter-protocol.json",
            )
            verify_runtime_set(bundle, args.plugin_root)
            output = _pretty_json(
                {
                    "status": "ok",
                    "runtime_payload_digest": bundle.runtime.runtime_payload_digest,
                    "generated_slots": list(bundle.runtime.generated_slots),
                }
            )
        else:
            bundle = load_bundle(args.evidence)
            changed = render_documents(bundle, args.docs_root, write=args.write)
            if args.check and changed:
                _fail("INTEGRITY_MISMATCH", "generated documentation is stale")
            output = _pretty_json({"status": "ok", "changed": list(changed)})
        if getattr(args, "output", None) is not None and args.command in {
            "inventory",
            "test-candidate",
        }:
            atomic_write_replace(
                args.output,
                output,
                mode=0o644,
                trusted_root=args.output.parent,
            )
        else:
            sys.stdout.buffer.write(output)
        return 0
    except (SupportError, _PROTOCOL.ProtocolValidationError) as exc:
        code = getattr(exc, "code", "UNKNOWN_ERROR")
        error = {
            "error": code,
            "message": str(exc),
            "reporting_class": _PROTOCOL.load_protocol().reporting_class_for_error(
                code
            ),
        }
        sys.stderr.buffer.write(_pretty_json(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
