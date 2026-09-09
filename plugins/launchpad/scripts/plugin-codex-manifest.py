"""Project LaunchPad's Codex manifest and sealed package without rescanning."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Final, NoReturn

from atomic_io import atomic_write_replace, atomic_write_replace_batch

SCRIPT_REAL_PATH: Final = Path(os.path.realpath(__file__))
SCRIPT_DIR: Final = SCRIPT_REAL_PATH.parent
PLUGIN_ROOT: Final = SCRIPT_DIR.parent
PROTOCOL_PATH: Final = SCRIPT_DIR / "plugin-codex-protocol.py"
SUPPORT_PATH: Final = SCRIPT_DIR / "plugin-codex-support.py"
RESOLVER_PATH: Final = SCRIPT_DIR / "plugin-codex-resolver.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load_module("launchpad_codex_protocol_for_manifest", PROTOCOL_PATH)
_RESOLVER = _load_module("launchpad_codex_resolver_for_manifest", RESOLVER_PATH)


class ManifestError(ValueError):
    """Stable manifest or package-projection failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> NoReturn:
    raise ManifestError(code, message)


class _DuplicateJsonKey(ValueError):
    pass


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
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


def _snapshot(root: Path, relative: str, maximum_bytes: int) -> Any:
    try:
        with _RESOLVER._anchor_directory(root) as anchored:
            return _RESOLVER._read_snapshot(
                anchored,
                relative,
                maximum_bytes=maximum_bytes,
                maximum_depth=_PROTOCOL.load_protocol().limits["catalog_depth"] + 4,
            )
    except _RESOLVER.ResolverError as exc:
        _fail(exc.code, str(exc))


def _load_strict_object(raw: bytes, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_strict_pairs)
    except (_DuplicateJsonKey, UnicodeDecodeError, json.JSONDecodeError):
        _fail("RECORD_INVALID", f"{name} is not strict JSON")
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _fail("RECORD_INVALID", f"{name} must be an object")
    return value


def _protocol_manifest_contract(
    protocol: Any,
) -> tuple[tuple[str, ...], Mapping[str, Any]]:
    shared = protocol.packaging.get("manifest_shared_fields")
    host = protocol.packaging.get("manifest_host_fields")
    if (
        not isinstance(shared, tuple)
        or shared != tuple(sorted(set(shared)))
        or any(not isinstance(item, str) for item in shared)
        or not isinstance(host, Mapping)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in host.items()
        )
    ):
        _fail("PROTOCOL_FILE_INVALID", "manifest projection authority is invalid")
    return shared, host


def projected_manifest(source_root: Path = PLUGIN_ROOT) -> dict[str, object]:
    protocol = _PROTOCOL.load_protocol(source_root / "codex" / "adapter-protocol.json")
    shared, host = _protocol_manifest_contract(protocol)
    snapshot = _snapshot(
        source_root,
        ".claude-plugin/plugin.json",
        protocol.limits["documentation_file_bytes"],
    )
    source = _load_strict_object(snapshot.content, "Claude manifest")
    if set(source) != set(shared):
        _fail(
            "RECORD_INVALID", "Claude manifest fields differ from the projection schema"
        )
    result: dict[str, object] = {}
    string_limit = protocol.limits["diagnostic_field_characters"]
    for field in shared:
        value = source[field]
        if field in {
            "name",
            "description",
            "version",
            "homepage",
            "repository",
            "license",
        }:
            if not isinstance(value, str) or not value or len(value) > string_limit:
                _fail("RECORD_INVALID", f"Claude manifest field {field} is invalid")
        elif field == "author":
            if (
                not isinstance(value, Mapping)
                or set(value) != {"name", "url"}
                or any(not isinstance(item, str) or not item for item in value.values())
            ):
                _fail("RECORD_INVALID", "Claude manifest author is invalid")
        elif field == "keywords":
            if (
                not isinstance(value, list)
                or len(value) > protocol.limits["definitions_per_type"]
                or any(
                    not isinstance(item, str) or not item or len(item) > string_limit
                    for item in value
                )
                or len(value) != len(set(value))
            ):
                _fail("RECORD_INVALID", "Claude manifest keywords are invalid")
        result[field] = value
    result.update(host)
    return result


def manifest_bytes(source_root: Path = PLUGIN_ROOT) -> bytes:
    return _pretty_json(projected_manifest(source_root))


def sync_manifest(
    source_root: Path,
    target_root: Path,
    *,
    write: bool,
) -> bool:
    if source_root.is_symlink() or target_root.is_symlink():
        _fail("PATH_SYMLINK", "manifest roots cannot be symlinks")
    source = source_root.resolve(strict=True)
    target = target_root.resolve(strict=True)
    expected = manifest_bytes(source)
    relative = ".codex-plugin/plugin.json"
    path = target / relative
    if not path.exists():
        if not write:
            return False
    else:
        current = _snapshot(
            target,
            relative,
            _PROTOCOL.load_protocol(source / "codex" / "adapter-protocol.json").limits[
                "documentation_file_bytes"
            ],
        )
        _load_strict_object(current.content, "Codex manifest")
        if current.content == expected:
            return True
        if not write:
            return False
    if target == PLUGIN_ROOT.resolve(strict=True):
        _fail("PATH_INVALID", "Section 5 cannot write the production Codex manifest")
    atomic_write_replace(path, expected, mode=0o644, trusted_root=target)
    verified = _snapshot(target, relative, len(expected))
    if verified.content != expected or _load_strict_object(
        verified.content, "Codex manifest"
    ) != projected_manifest(source):
        _fail("INTEGRITY_MISMATCH", "written Codex manifest did not verify")
    return True


def _support_module() -> Any:
    return _load_module("launchpad_codex_support_for_manifest", SUPPORT_PATH)


def _safe_destination_path(root: Path, relative: str) -> Path:
    lexical = PurePosixPath(relative)
    if lexical.is_absolute() or any(part in {"", ".", ".."} for part in lexical.parts):
        _fail("PATH_ESCAPE", "package path escapes its root")
    return root.joinpath(*lexical.parts)


def _package_records(
    bundle: Any, source_root: Path, *, include_generated: bool
) -> tuple[tuple[str, str, int], ...]:
    protocol = _PROTOCOL.load_protocol(source_root / "codex" / "adapter-protocol.json")
    records = [
        (item.path, item.digest, item.size) for item in bundle.runtime.runtime_files
    ]
    if include_generated:
        for path in bundle.runtime.generated_slots:
            snapshot = _snapshot(
                source_root,
                path,
                protocol.limits["documentation_file_bytes"],
            )
            records.append((path, snapshot.digest, snapshot.size))
    paths = [item[0] for item in records]
    if len(paths) != len(set(paths)):
        _fail("INTEGRITY_MISMATCH", "package file set contains duplicates")
    return tuple(sorted(records))


def project_package(
    bundle: Any,
    source_root: Path,
    destination_root: Path,
    *,
    include_generated: bool,
) -> tuple[str, ...]:
    support = _support_module()
    support.verify_runtime_set(bundle, source_root)
    destination = destination_root.resolve(strict=True)
    if destination == source_root.resolve(strict=True):
        _fail("PATH_INVALID", "package destination must be disposable")
    records = _package_records(bundle, source_root, include_generated=include_generated)
    batch: dict[Path, bytes] = {}
    for path, digest, size in records:
        snapshot = _snapshot(source_root, path, max(size, 1))
        if snapshot.digest != digest or snapshot.size != size:
            _fail("INTEGRITY_MISMATCH", "sealed package source changed")
        batch[_safe_destination_path(destination, path)] = snapshot.content
    atomic_write_replace_batch(batch, default_mode=0o644, trusted_root=destination)
    check_package(bundle, destination, include_generated=include_generated)
    return tuple(path for path, _digest, _size in records)


def _walk_package(root: Path) -> tuple[str, ...]:
    result: list[str] = []
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*directories, *files):
            path = current_path / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                _fail("PATH_SYMLINK", "package contains a symlink")
        for name in files:
            relative = (current_path / name).relative_to(root).as_posix()
            if ".tmp" in name and name.startswith("."):
                _fail("INTEGRITY_MISMATCH", "package contains an interrupted write")
            result.append(relative)
    return tuple(sorted(result))


def check_package(
    bundle: Any,
    package_root: Path,
    *,
    include_generated: bool,
) -> tuple[str, ...]:
    records = _package_records(
        bundle, package_root, include_generated=include_generated
    )
    expected = tuple(item[0] for item in records)
    actual = _walk_package(package_root)
    if actual != expected:
        _fail("INTEGRITY_MISMATCH", "package closure differs from the sealed file set")
    for path, digest, size in records:
        snapshot = _snapshot(package_root, path, max(size, 1))
        if snapshot.digest != digest or snapshot.size != size:
            _fail("INTEGRITY_MISMATCH", "packaged file differs from its sealed record")
    conventional = (
        "hooks/hooks.json",
        ".mcp.json",
        ".app.json",
    )
    if set(actual) & set(conventional):
        _fail("INTEGRITY_MISMATCH", "undeclared conventional Codex surface packaged")
    return actual


def artifact_digest(
    bundle: Any,
    package_root: Path,
    *,
    include_generated: bool = True,
) -> str:
    paths = check_package(bundle, package_root, include_generated=include_generated)
    records = []
    for path in paths:
        snapshot = _snapshot(
            package_root,
            path,
            _PROTOCOL.load_protocol(
                package_root / "codex" / "adapter-protocol.json"
            ).limits["documentation_file_bytes"],
        )
        records.append({"path": path, "digest": snapshot.digest, "size": snapshot.size})
    return _sha256(_canonical_json({"domain": "artifact_digest", "files": records}))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync = subparsers.add_parser("sync-codex-manifest")
    sync.add_argument("--source-root", type=Path, default=PLUGIN_ROOT)
    sync.add_argument("--target-root", type=Path, required=True)
    mode = sync.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    package = subparsers.add_parser("package")
    package.add_argument("--evidence", type=Path, required=True)
    package.add_argument("--source-root", type=Path, required=True)
    package.add_argument("--destination-root", type=Path, required=True)
    package.add_argument("--include-generated", action="store_true")
    check = subparsers.add_parser("check-package")
    check.add_argument("--evidence", type=Path, required=True)
    check.add_argument("--package-root", type=Path, required=True)
    check.add_argument("--include-generated", action="store_true")
    digest = subparsers.add_parser("artifact-digest")
    digest.add_argument("--evidence", type=Path, required=True)
    digest.add_argument("--package-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "sync-codex-manifest":
            matches = sync_manifest(
                args.source_root,
                args.target_root,
                write=args.write,
            )
            if args.check and not matches:
                _fail("INTEGRITY_MISMATCH", "Codex manifest is absent or stale")
            result: object = {
                "status": "ok",
                "manifest": projected_manifest(args.source_root),
            }
        else:
            support = _support_module()
            bundle = support.load_bundle(
                args.evidence,
                protocol_path=(
                    args.source_root if args.command == "package" else args.package_root
                )
                / "codex"
                / "adapter-protocol.json",
            )
            if args.command == "package":
                paths = project_package(
                    bundle,
                    args.source_root,
                    args.destination_root,
                    include_generated=args.include_generated,
                )
                result = {"status": "ok", "paths": list(paths)}
            elif args.command == "check-package":
                paths = check_package(
                    bundle,
                    args.package_root,
                    include_generated=args.include_generated,
                )
                result = {"status": "ok", "paths": list(paths)}
            else:
                result = {
                    "artifact_digest": artifact_digest(bundle, args.package_root),
                    "storage": "detached_attestation_only",
                }
        sys.stdout.buffer.write(_pretty_json(result))
        return 0
    except (ManifestError, _PROTOCOL.ProtocolValidationError) as exc:
        code = getattr(exc, "code", "UNKNOWN_ERROR")
        sys.stderr.buffer.write(
            _pretty_json(
                {
                    "error": code,
                    "message": str(exc),
                    "reporting_class": _PROTOCOL.load_protocol().reporting_class_for_error(
                        code
                    ),
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
