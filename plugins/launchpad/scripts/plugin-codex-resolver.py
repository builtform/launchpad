"""Secure, deterministic LaunchPad source resolver for the Codex adapter.

The resolver is deliberately read-only. It anchors roots with directory file
descriptors, rejects symlinks, reads immutable snapshots, and requires a fresh
expected digest before returning canonical bytes. Markdown bodies remain
opaque and are never interpreted or executed here.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import dataclasses
import hashlib
import hmac
import importlib.util
import json
import os
import secrets
import stat
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final, NoReturn, Protocol, cast

SCRIPT_REAL_PATH: Final = Path(os.path.realpath(__file__))
SCRIPT_DIR: Final = SCRIPT_REAL_PATH.parent
PLUGIN_ROOT: Final = SCRIPT_DIR.parent
PROTOCOL_MODULE_PATH: Final = SCRIPT_DIR / "plugin-codex-protocol.py"


def _load_protocol_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "launchpad_codex_protocol_for_resolver", PROTOCOL_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load the LaunchPad Codex protocol module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load_protocol_module()


class ResolverError(ValueError):
    """Stable resolver failure with protocol-owned reporting classification."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.reporting_class = _PROTOCOL.load_protocol().reporting_class_for_error(code)


def _fail(code: str, message: str) -> NoReturn:
    raise ResolverError(code, message)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class _DuplicateJsonKey(ValueError):
    pass


def _strict_json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _identity(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _fd_flags(*, directory: bool = False) -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    return flags


def _validate_absolute_path(path: Path) -> Path:
    raw = os.fspath(path)
    if not path.is_absolute() or any(
        ord(char) < 32 or ord(char) == 127 for char in raw
    ):
        _fail("ROOT_INVALID", "root must be an absolute path without controls")
    lexical = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in lexical.parts[1:]):
        _fail("ROOT_INVALID", "root contains an ambiguous path component")
    return Path(os.path.normpath(raw))


def _validate_relative_path(value: str, *, max_depth: int) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        _fail("PATH_INVALID", "relative path is required")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        _fail("PATH_INVALID", "relative path contains a control character")
    if ":" in value.split("/", 1)[0]:
        _fail("PATH_INVALID", "URI schemes are not supported")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _fail("PATH_ESCAPE", "path must remain beneath its anchored owner")
    if len(path.parts) > max_depth:
        _fail("LIMIT_EXCEEDED", "path depth exceeds the protocol limit")
    return path.parts


@dataclass
class AnchoredRoot:
    """An already-open root directory and its immutable identity."""

    path: Path
    fd: int
    info: os.stat_result

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> AnchoredRoot:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


def _anchor_directory(path: Path) -> AnchoredRoot:
    canonical = _validate_absolute_path(path)
    current = os.open("/", _fd_flags(directory=True))
    try:
        for component in canonical.parts[1:]:
            try:
                before = os.stat(component, dir_fd=current, follow_symlinks=False)
            except OSError:
                _fail("ROOT_INVALID", "root cannot be opened")
            if stat.S_ISLNK(before.st_mode):
                _fail("PATH_SYMLINK", "root contains a symlink")
            if not stat.S_ISDIR(before.st_mode):
                _fail("ROOT_INVALID", "root component is not a directory")
            try:
                child = os.open(component, _fd_flags(directory=True), dir_fd=current)
            except OSError:
                _fail("ROOT_INVALID", "root cannot be opened")
            after = os.fstat(child)
            if _identity(before) != _identity(after):
                os.close(child)
                _fail("PATH_RACE", "root changed while it was anchored")
            os.close(current)
            current = child
        info = os.fstat(current)
        return AnchoredRoot(canonical, current, info)
    except BaseException:
        os.close(current)
        raise


@dataclass(frozen=True)
class Snapshot:
    relative_path: str
    content: bytes
    digest: str
    size: int
    device: int
    inode: int


RaceHook = Callable[[str], None]


def _revalidate_links(
    links: Sequence[tuple[int, str, int, tuple[int, int, int]]],
) -> None:
    for parent_fd, name, opened_fd, expected in links:
        try:
            named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            opened = os.fstat(opened_fd)
        except OSError:
            _fail("PATH_RACE", "path changed during the immutable read")
        if stat.S_ISLNK(named.st_mode):
            _fail("PATH_SYMLINK", "path changed into a symlink")
        if _identity(named) != expected or _identity(opened) != expected:
            _fail("PATH_RACE", "path identity changed during the immutable read")


def _revalidate_root(root: AnchoredRoot) -> None:
    try:
        with _anchor_directory(root.path) as reopened:
            matches = _identity(reopened.info) == _identity(root.info)
    except ResolverError:
        _fail("PATH_RACE", "anchored root path changed during the operation")
    if not matches:
        _fail("PATH_RACE", "anchored root identity changed during the operation")


def _open_relative_directory(
    root: AnchoredRoot, parts: Sequence[str]
) -> tuple[int, list[tuple[int, str, int, tuple[int, int, int]]]]:
    current = os.dup(root.fd)
    links: list[tuple[int, str, int, tuple[int, int, int]]] = []
    try:
        if _identity(os.fstat(current)) != _identity(root.info):
            _fail("PATH_RACE", "anchored root identity changed")
        for component in parts:
            try:
                before = os.stat(component, dir_fd=current, follow_symlinks=False)
            except FileNotFoundError:
                _fail("SOURCE_NOT_FOUND", "path does not exist")
            except OSError:
                _fail("PATH_INVALID", "path cannot be inspected")
            if stat.S_ISLNK(before.st_mode):
                _fail("PATH_SYMLINK", "symlink traversal is forbidden")
            if not stat.S_ISDIR(before.st_mode):
                _fail("SOURCE_TYPE_INVALID", "ancestor is not a directory")
            try:
                child = os.open(component, _fd_flags(directory=True), dir_fd=current)
            except OSError:
                _fail("PATH_RACE", "ancestor changed while it was opened")
            expected = _identity(before)
            if _identity(os.fstat(child)) != expected:
                os.close(child)
                _fail("PATH_RACE", "ancestor identity changed while it was opened")
            links.append((current, component, child, expected))
            current = child
        return current, links
    except BaseException:
        _close_links(current, links)
        raise


def _close_links(
    current: int, links: Sequence[tuple[int, str, int, tuple[int, int, int]]]
) -> None:
    closed: set[int] = set()
    for parent_fd, _name, opened_fd, _expected in reversed(links):
        if opened_fd not in closed:
            os.close(opened_fd)
            closed.add(opened_fd)
        if parent_fd not in closed:
            os.close(parent_fd)
            closed.add(parent_fd)
    if current not in closed:
        os.close(current)


def _read_snapshot(
    root: AnchoredRoot,
    relative_path: str,
    *,
    maximum_bytes: int,
    maximum_depth: int,
    race_hook: RaceHook | None = None,
) -> Snapshot:
    parts = _validate_relative_path(relative_path, max_depth=maximum_depth)
    parent, links = _open_relative_directory(root, parts[:-1])
    file_fd = -1
    try:
        leaf = parts[-1]
        if race_hook is not None:
            race_hook("before_leaf_open")
        try:
            before = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            _fail("SOURCE_NOT_FOUND", "source does not exist")
        except OSError:
            _fail("PATH_INVALID", "source cannot be inspected")
        if stat.S_ISLNK(before.st_mode):
            _fail("PATH_SYMLINK", "symlink sources are forbidden")
        if not stat.S_ISREG(before.st_mode):
            _fail("SOURCE_TYPE_INVALID", "source must be a regular file")
        if before.st_size > maximum_bytes:
            _fail("SOURCE_TOO_LARGE", "source exceeds its byte limit")
        try:
            file_fd = os.open(leaf, _fd_flags(), dir_fd=parent)
        except OSError:
            _fail("PATH_RACE", "source changed while it was opened")
        opened = os.fstat(file_fd)
        expected = _identity(before)
        if _identity(opened) != expected or not stat.S_ISREG(opened.st_mode):
            _fail("PATH_RACE", "source identity changed while it was opened")
        if race_hook is not None:
            race_hook("after_leaf_open")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, min(65536, maximum_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum_bytes:
                _fail("SOURCE_TOO_LARGE", "source exceeds its byte limit")
        if race_hook is not None:
            race_hook("after_read")
        finished = os.fstat(file_fd)
        if (
            _identity(finished) != expected
            or finished.st_size != opened.st_size
            or total != finished.st_size
        ):
            _fail("PATH_RACE", "source changed while it was read")
        try:
            named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        except OSError:
            _fail("PATH_RACE", "source was renamed during the immutable read")
        if _identity(named) != expected:
            _fail("PATH_RACE", "source name changed during the immutable read")
        _revalidate_links(links)
        _revalidate_root(root)
        content = b"".join(chunks)
        try:
            content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            _fail("SOURCE_INVALID_UTF8", "source is not valid UTF-8")
        return Snapshot(
            relative_path=relative_path,
            content=content,
            digest=_sha256(content),
            size=len(content),
            device=finished.st_dev,
            inode=finished.st_ino,
        )
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        _close_links(parent, links)


def _list_directory(
    root: AnchoredRoot, relative_path: str, *, maximum_depth: int
) -> tuple[str, ...]:
    parts = (
        _validate_relative_path(relative_path, max_depth=maximum_depth)
        if relative_path
        else ()
    )
    current, links = _open_relative_directory(root, parts)
    try:
        try:
            names = os.listdir(current)
        except OSError:
            _fail("PATH_INVALID", "directory cannot be listed")
        _revalidate_links(links)
        _revalidate_root(root)
        return tuple(sorted(names))
    finally:
        _close_links(current, links)


def _stat_relative(
    root: AnchoredRoot, relative_path: str, *, maximum_depth: int
) -> os.stat_result:
    parts = _validate_relative_path(relative_path, max_depth=maximum_depth)
    parent, links = _open_relative_directory(root, parts[:-1])
    try:
        try:
            info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            _fail("SOURCE_NOT_FOUND", "path does not exist")
        except OSError:
            _fail("PATH_INVALID", "path cannot be inspected")
        _revalidate_links(links)
        _revalidate_root(root)
        return info
    finally:
        _close_links(parent, links)


@dataclass(frozen=True)
class Catalog:
    plugin_version: str
    protocol_version: str
    metadata_digest: str
    commands: Mapping[str, Any]
    skills: Mapping[str, Any]
    agents: Mapping[str, Any]
    project_skills: Mapping[str, Any]
    project_agents: Mapping[str, Any]
    warnings: tuple[str, ...]
    invalid_entries: tuple[str, ...]
    project_root: Any | None

    @property
    def all_sources(self) -> tuple[Any, ...]:
        values: list[Any] = []
        for table in (
            self.commands,
            self.skills,
            self.agents,
            self.project_skills,
            self.project_agents,
        ):
            values.extend(table.values())
        return tuple(sorted(values, key=lambda item: (item.kind, item.resource_id)))


@dataclass(frozen=True)
class SourceRead:
    record: Any
    content: str
    content_bytes: bytes


@dataclass(frozen=True)
class ResourceRead:
    record: Any
    content: str
    content_bytes: bytes


def _mapping(values: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(sorted(values.items())))


class SecureResolver:
    """Session-scoped resolver with an immutable built-in catalog."""

    def __init__(self) -> None:
        self.protocol = _PROTOCOL.load_protocol()
        self._plugin_path = PLUGIN_ROOT
        self._canonical_prefix = self._canonical_catalog_prefix(self._plugin_path)
        self._fixture = False
        self._builtin_catalog: Catalog | None = None
        self._catalog_cache: dict[tuple[str, str], Catalog] = {}

    @classmethod
    def for_test(cls, plugin_root: Path) -> SecureResolver:
        """Create a fixture resolver without weakening the production anchor."""
        resolver = cls.__new__(cls)
        resolver.protocol = _PROTOCOL.load_protocol(
            plugin_root / "codex" / "adapter-protocol.json"
        )
        resolver._plugin_path = _validate_absolute_path(plugin_root)
        resolver._canonical_prefix = resolver._canonical_catalog_prefix(
            resolver._plugin_path
        )
        resolver._fixture = True
        resolver._builtin_catalog = None
        resolver._catalog_cache = {}
        return resolver

    def _canonical_catalog_prefix(self, plugin_root: Path) -> str:
        if (plugin_root / ".claude-plugin" / "plugin.json").is_file():
            return ""
        value = self.protocol.packaging["canonical_package_prefix"]
        if not isinstance(value, str):
            _fail("PROTOCOL_FILE_INVALID", "canonical package prefix is invalid")
        return value

    def _builtin_path(self, relative: str) -> str:
        if not self._canonical_prefix:
            return relative
        return f"{self._canonical_prefix}/{relative}"

    def _path_depth_limit(self, origin: str) -> int:
        base = self.protocol.limits["catalog_depth"]
        if origin != "built_in" or not self._canonical_prefix:
            return base
        return base + len(PurePosixPath(self._canonical_prefix).parts)

    def _source_limit(self) -> int:
        return (
            self.protocol.limits["frontmatter_bytes"]
            + self.protocol.limits["body_bytes"]
            + 16
        )

    def _record_from_snapshot(
        self,
        snapshot: Snapshot,
        *,
        resource_id: str,
        kind: str,
        origin: str,
        require_metadata: bool,
    ) -> Any:
        try:
            frontmatter, _body = _PROTOCOL.extract_frontmatter(
                snapshot.content, self.protocol
            )
        except _PROTOCOL.ProtocolValidationError as exc:
            _fail(exc.code, str(exc))
        if require_metadata:
            try:
                metadata, _body = _PROTOCOL.normalize_document_metadata(
                    snapshot.content, self.protocol
                )
            except _PROTOCOL.ProtocolValidationError as exc:
                _fail(exc.code, str(exc))
            if metadata.component_kind != kind:
                _fail("METADATA_INVALID", "component kind differs from its tier")
            metadata_digest = _sha256(_canonical_json(dataclasses.asdict(metadata)))
        else:
            namespace = frontmatter.get(self.protocol.metadata_namespace)
            if namespace is not None:
                try:
                    metadata = _PROTOCOL.normalize_metadata(namespace, self.protocol)
                except _PROTOCOL.ProtocolValidationError as exc:
                    _fail(exc.code, str(exc))
                if metadata.component_kind != kind:
                    _fail("METADATA_INVALID", "component kind differs from its tier")
            metadata_digest = _sha256(_canonical_json(dict(frontmatter)))
        declared_name = frontmatter.get("name")
        if kind != "command" and declared_name != resource_id:
            _fail("METADATA_INVALID", "definition name differs from its source ID")
        if kind == "command" and declared_name not in {None, resource_id}:
            _fail("METADATA_INVALID", "command name differs from its source ID")
        user_invocable = origin == "built_in" and (
            kind == "command"
            or (kind == "skill" and frontmatter.get("user-invocable", True) is True)
        )
        return _PROTOCOL.normalize_resolver_source_record(
            {
                "resource_id": resource_id,
                "kind": kind,
                "origin": origin,
                "source_path": snapshot.relative_path,
                "source_digest": snapshot.digest,
                "metadata_digest": metadata_digest,
                "size": snapshot.size,
                "user_invocable": user_invocable,
                "quarantined": origin == "project",
            },
            self.protocol,
        )

    def _inspect_path(
        self,
        root: AnchoredRoot,
        relative_path: str,
        *,
        resource_id: str,
        kind: str,
        origin: str,
        require_metadata: bool,
        race_hook: RaceHook | None = None,
    ) -> Any:
        snapshot = _read_snapshot(
            root,
            relative_path,
            maximum_bytes=self._source_limit(),
            maximum_depth=self._path_depth_limit(origin),
            race_hook=race_hook,
        )
        return self._record_from_snapshot(
            snapshot,
            resource_id=resource_id,
            kind=kind,
            origin=origin,
            require_metadata=require_metadata,
        )

    def _walk_agents(
        self,
        root: AnchoredRoot,
        base: str,
        *,
        require_lp_prefix: bool,
        missing_ok: bool = False,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        files: list[str] = []
        invalid: list[str] = []
        maximum_depth = (
            self._path_depth_limit("built_in")
            if self._canonical_prefix
            and (
                base == self._canonical_prefix
                or base.startswith(f"{self._canonical_prefix}/")
            )
            else self.protocol.limits["catalog_depth"]
        )

        def walk(relative: str, depth: int) -> None:
            if depth > maximum_depth:
                invalid.append(f"{relative}:LIMIT_EXCEEDED")
                return
            try:
                names = _list_directory(root, relative, maximum_depth=maximum_depth)
            except ResolverError as exc:
                if missing_ok and relative == base and exc.code == "SOURCE_NOT_FOUND":
                    return
                invalid.append(f"{relative}:{exc.code}")
                return
            for name in names:
                if name.startswith("."):
                    continue
                child = f"{relative}/{name}" if relative else name
                try:
                    info = _stat_relative(root, child, maximum_depth=maximum_depth)
                except ResolverError as exc:
                    invalid.append(f"{child}:{exc.code}")
                    continue
                if stat.S_ISLNK(info.st_mode):
                    invalid.append(f"{child}:PATH_SYMLINK")
                elif stat.S_ISDIR(info.st_mode):
                    walk(child, depth + 1)
                elif (
                    stat.S_ISREG(info.st_mode)
                    and name.endswith(".md")
                    and (not require_lp_prefix or name.startswith("lp-"))
                ):
                    files.append(child)

        walk(base, len(PurePosixPath(base).parts))
        return tuple(sorted(files)), tuple(sorted(invalid))

    def _build_builtins(self) -> Catalog:
        commands: dict[str, Any] = {}
        skills: dict[str, Any] = {}
        agents: dict[str, Any] = {}
        invalid: list[str] = []
        with _anchor_directory(self._plugin_path) as root:
            commands_root = self._builtin_path("commands")
            for name in _list_directory(
                root,
                commands_root,
                maximum_depth=self._path_depth_limit("built_in"),
            ):
                if not (name.startswith("lp-") and name.endswith(".md")):
                    continue
                path = f"{commands_root}/{name}"
                try:
                    snapshot = _read_snapshot(
                        root,
                        path,
                        maximum_bytes=self._source_limit(),
                        maximum_depth=self._path_depth_limit("built_in"),
                    )
                    if not snapshot.content.startswith(b"---\n"):
                        continue
                    resource_id = name.removesuffix(".md")
                    record = self._record_from_snapshot(
                        snapshot,
                        resource_id=resource_id,
                        kind="command",
                        origin="built_in",
                        require_metadata=True,
                    )
                    self._insert_unique(commands, record)
                except ResolverError as exc:
                    invalid.append(f"{path}:{exc.code}")
            skills_root = self._builtin_path("skills")
            for name in _list_directory(
                root,
                skills_root,
                maximum_depth=self._path_depth_limit("built_in"),
            ):
                if not name.startswith("lp-"):
                    continue
                path = f"{skills_root}/{name}/SKILL.md"
                try:
                    record = self._inspect_path(
                        root,
                        path,
                        resource_id=name,
                        kind="skill",
                        origin="built_in",
                        require_metadata=True,
                    )
                    self._insert_unique(skills, record)
                except ResolverError as exc:
                    invalid.append(f"{path}:{exc.code}")
            agent_paths, agent_invalid = self._walk_agents(
                root, self._builtin_path("agents"), require_lp_prefix=True
            )
            invalid.extend(agent_invalid)
            for path in agent_paths:
                resource_id = PurePosixPath(path).stem
                try:
                    record = self._inspect_path(
                        root,
                        path,
                        resource_id=resource_id,
                        kind="agent",
                        origin="built_in",
                        require_metadata=True,
                    )
                    self._insert_unique(agents, record)
                except ResolverError as exc:
                    invalid.append(f"{path}:{exc.code}")
            version = self._plugin_version(root)
        self._enforce_table_bounds(commands, skills, agents)
        metadata_digest = self._catalog_digest(commands, skills, agents, {}, {})
        return Catalog(
            plugin_version=version,
            protocol_version=self.protocol.protocol_version,
            metadata_digest=metadata_digest,
            commands=_mapping(commands),
            skills=_mapping(skills),
            agents=_mapping(agents),
            project_skills=_mapping({}),
            project_agents=_mapping({}),
            warnings=(),
            invalid_entries=tuple(sorted(set(invalid))),
            project_root=None,
        )

    def _plugin_version(self, root: AnchoredRoot) -> str:
        snapshot = _read_snapshot(
            root,
            ".codex-plugin/plugin.json",
            maximum_bytes=self.protocol.limits["yaml_scalar_bytes"],
            maximum_depth=self.protocol.limits["catalog_depth"],
        )
        try:
            manifest = json.loads(
                snapshot.content, object_pairs_hook=_strict_json_pairs
            )
        except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey):
            _fail("CATALOG_INVALID", "Codex plugin manifest is invalid")
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("version"), str
        ):
            _fail("CATALOG_INVALID", "Codex plugin manifest version is invalid")
        return manifest["version"]

    def _insert_unique(self, table: dict[str, Any], record: Any) -> None:
        if record.resource_id in table:
            table.pop(record.resource_id)
            _fail("SOURCE_DUPLICATE", "duplicate definition within one precedence tier")
        table[record.resource_id] = record

    def _enforce_table_bounds(self, *tables: Mapping[str, Any]) -> None:
        for table in tables:
            if len(table) > self.protocol.limits["definitions_per_type"]:
                _fail("LIMIT_EXCEEDED", "definition tier exceeds its catalog limit")

    def _catalog_digest(self, *tables: Mapping[str, Any]) -> str:
        payload = [
            [dataclasses.asdict(record) for record in table.values()]
            for table in tables
        ]
        return _sha256(_canonical_json(payload))

    def builtin_catalog(self) -> Catalog:
        if self._builtin_catalog is None:
            self._builtin_catalog = self._build_builtins()
            key = (
                self._builtin_catalog.plugin_version,
                self._builtin_catalog.metadata_digest,
            )
            self._catalog_cache[key] = self._builtin_catalog
        return self._builtin_catalog

    def refresh(self) -> Catalog:
        """Start a new immutable built-in snapshot for an explicit session refresh."""
        self._builtin_catalog = self._build_builtins()
        key = (
            self._builtin_catalog.plugin_version,
            self._builtin_catalog.metadata_digest,
        )
        self._catalog_cache[key] = self._builtin_catalog
        return self._builtin_catalog

    def anchor_project_root(self, project_root: Path) -> Any:
        """Anchor one explicit absolute active workspace and bind its identity."""
        with _anchor_directory(project_root) as root:
            for marker in (".git", ".launchpad/config.yml"):
                info = _stat_relative(
                    root,
                    marker,
                    maximum_depth=self.protocol.limits["catalog_depth"],
                )
                if marker == ".git":
                    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                        _fail("ROOT_INVALID", "Git marker has an invalid type")
                elif not stat.S_ISREG(info.st_mode):
                    _fail("ROOT_INVALID", "LaunchPad config is not a regular file")
            identity_payload = {
                "canonical_root": os.fspath(root.path),
                "device": root.info.st_dev,
                "inode": root.info.st_ino,
            }
            repository_identity = _sha256(_canonical_json(identity_payload))
            return _PROTOCOL.normalize_project_root_record(
                {
                    "canonical_root": os.fspath(root.path),
                    "repository_identity": repository_identity,
                    "root_device": root.info.st_dev,
                    "root_inode": root.info.st_ino,
                },
                self.protocol,
            )

    def resolve_project_root(
        self,
        active_workspace: Path,
        *,
        explicit_root: Path | None = None,
    ) -> Any:
        """Resolve one project only inside an authenticated active workspace."""
        workspace = _validate_absolute_path(active_workspace)
        if explicit_root is not None:
            explicit = _validate_absolute_path(explicit_root)
            if not explicit.is_relative_to(workspace):
                _fail("PATH_ESCAPE", "project root escapes the active workspace")
            return self.anchor_project_root(explicit)
        candidates: list[Any] = []
        with _anchor_directory(workspace) as root:
            maximum_depth = self.protocol.limits["catalog_depth"]

            def walk(relative: str, depth: int) -> None:
                if depth > maximum_depth:
                    return
                try:
                    names = _list_directory(root, relative, maximum_depth=maximum_depth)
                except ResolverError:
                    return
                if ".git" in names and ".launchpad" in names:
                    candidate_path = workspace / relative if relative else workspace
                    try:
                        candidates.append(self.anchor_project_root(candidate_path))
                    except ResolverError:
                        pass
                for name in names:
                    if name.startswith("."):
                        continue
                    child = f"{relative}/{name}" if relative else name
                    try:
                        info = _stat_relative(root, child, maximum_depth=maximum_depth)
                    except ResolverError:
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        walk(child, depth + 1)

            walk("", 0)
        unique = {item.repository_identity: item for item in candidates}
        if not unique:
            _fail(
                "ROOT_INVALID", "no LaunchPad Git root exists in the active workspace"
            )
        if len(unique) != 1:
            _fail(
                "ROOT_AMBIGUOUS", "multiple project roots exist in the active workspace"
            )
        return next(iter(unique.values()))

    def _project_tables(
        self, project: Any
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        skills: dict[str, Any] = {}
        agents: dict[str, Any] = {}
        invalid: list[str] = []
        with _anchor_directory(Path(project.canonical_root)) as root:
            if _identity(root.info) != (
                project.root_device,
                project.root_inode,
                stat.S_IFDIR,
            ):
                _fail("PATH_RACE", "project root identity changed")
            try:
                skill_names = _list_directory(
                    root,
                    ".claude/skills",
                    maximum_depth=self.protocol.limits["catalog_depth"],
                )
            except ResolverError as exc:
                skill_names = ()
                if exc.code != "SOURCE_NOT_FOUND":
                    invalid.append(f".claude/skills:{exc.code}")
            for name in skill_names:
                if self.protocol.name_pattern.fullmatch(name) is None:
                    invalid.append(f".claude/skills/{name}:PATH_INVALID")
                    continue
                path = f".claude/skills/{name}/SKILL.md"
                try:
                    record = self._inspect_path(
                        root,
                        path,
                        resource_id=name,
                        kind="skill",
                        origin="project",
                        require_metadata=False,
                    )
                    self._insert_unique(skills, record)
                except ResolverError as exc:
                    invalid.append(f"{path}:{exc.code}")
            agent_paths, agent_invalid = self._walk_agents(
                root,
                ".claude/agents",
                require_lp_prefix=False,
                missing_ok=True,
            )
            invalid.extend(agent_invalid)
            for path in agent_paths:
                resource_id = PurePosixPath(path).stem
                try:
                    record = self._inspect_path(
                        root,
                        path,
                        resource_id=resource_id,
                        kind="agent",
                        origin="project",
                        require_metadata=False,
                    )
                    self._insert_unique(agents, record)
                except ResolverError as exc:
                    invalid.append(f"{path}:{exc.code}")
        self._enforce_table_bounds(skills, agents)
        return skills, agents, invalid

    def catalog(self, project_root: Path | None = None) -> Catalog:
        builtins = self.builtin_catalog()
        if project_root is None:
            return builtins
        project = self.anchor_project_root(project_root)
        skills, agents, invalid = self._project_tables(project)
        warnings = [
            f"built-in {kind} {resource_id} wins project collision"
            for kind, builtins_table, project_table in (
                ("skill", builtins.skills, skills),
                ("agent", builtins.agents, agents),
            )
            for resource_id in sorted(set(builtins_table) & set(project_table))
        ]
        digest = self._catalog_digest(
            builtins.commands, builtins.skills, builtins.agents, skills, agents
        )
        key = (project.repository_identity, digest)
        if key in self._catalog_cache:
            return self._catalog_cache[key]
        catalog = Catalog(
            plugin_version=builtins.plugin_version,
            protocol_version=self.protocol.protocol_version,
            metadata_digest=digest,
            commands=builtins.commands,
            skills=builtins.skills,
            agents=builtins.agents,
            project_skills=_mapping(skills),
            project_agents=_mapping(agents),
            warnings=tuple(warnings),
            invalid_entries=tuple(sorted((*builtins.invalid_entries, *invalid))),
            project_root=project,
        )
        self._catalog_cache[key] = catalog
        return catalog

    def resolve(
        self,
        kind: str,
        identifier: str,
        *,
        project_root: Path | None = None,
        reference_class: str = "exact",
        internal: bool = True,
    ) -> Any:
        """Resolve a declared source with fixed, collision-safe precedence."""
        if kind not in self.protocol.component_kinds:
            _fail("PROTOCOL_VALUE_INVALID", "unknown component kind")
        catalog = self.catalog(project_root)
        return self._resolve_from_catalog(
            catalog,
            kind,
            identifier,
            reference_class=reference_class,
            internal=internal,
        )

    def _resolve_from_catalog(
        self,
        catalog: Catalog,
        kind: str,
        identifier: str,
        *,
        reference_class: str = "exact",
        internal: bool = True,
    ) -> Any:
        """Resolve against one already-built immutable catalog snapshot."""
        if reference_class == "explicit_path":
            parts = _validate_relative_path(
                identifier, max_depth=self._path_depth_limit("built_in")
            )
            matches = [
                item
                for item in catalog.all_sources
                if item.source_path == "/".join(parts)
            ]
            if len(matches) != 1:
                _fail("SOURCE_NOT_FOUND", "explicit canonical path does not resolve")
            record = matches[0]
            if record.kind != kind:
                _fail("SOURCE_NOT_FOUND", "explicit path resolves to another kind")
            return record
        if reference_class == "logical":
            if (
                kind != "skill"
                or self.protocol.name_pattern.fullmatch(identifier) is None
            ):
                _fail(
                    "PATH_INVALID", "logical references are valid only for skill names"
                )
            identifier = f"lp-{identifier}"
        elif reference_class != "exact":
            _fail("PROTOCOL_VALUE_INVALID", "unknown reference classification")
        if self.protocol.name_pattern.fullmatch(identifier) is None:
            _fail("PATH_INVALID", "identifier does not match the protocol grammar")
        if kind == "command":
            record = catalog.commands.get(identifier)
            if record is None:
                _fail("UNKNOWN_COMMAND", "command is not a released built-in")
            return record
        builtins = catalog.skills if kind == "skill" else catalog.agents
        projects = catalog.project_skills if kind == "skill" else catalog.project_agents
        if identifier in builtins:
            record = builtins[identifier]
            if kind == "skill" and not internal and not record.user_invocable:
                _fail(
                    "SKILL_NOT_USER_INVOCABLE",
                    "built-in skill metadata forbids direct invocation",
                )
            return record
        record = projects.get(identifier)
        if record is None:
            _fail(
                "UNKNOWN_SKILL" if kind == "skill" else "SOURCE_NOT_FOUND",
                f"{kind} is unknown",
            )
        if kind == "skill" and not internal:
            _fail(
                "PROJECT_EXTENSION_NOT_PUBLIC",
                "project skills are internal dependencies only",
            )
        return record

    def inspect(
        self,
        kind: str,
        identifier: str,
        *,
        project_root: Path | None = None,
        reference_class: str = "exact",
        internal: bool = True,
    ) -> Any:
        return self.resolve(
            kind,
            identifier,
            project_root=project_root,
            reference_class=reference_class,
            internal=internal,
        )

    def inspect_batch(
        self,
        kind: str,
        identifiers: Sequence[str],
        *,
        project_root: Path | None = None,
        internal: bool = True,
    ) -> tuple[Any, ...]:
        if len(identifiers) > self.protocol.limits["definitions_per_type"]:
            _fail("LIMIT_EXCEEDED", "batch inspection exceeds its definition limit")
        if len(set(identifiers)) != len(identifiers):
            _fail("SOURCE_DUPLICATE", "batch inspection contains a duplicate ID")
        if not identifiers:
            return ()
        if kind not in self.protocol.component_kinds:
            _fail("PROTOCOL_VALUE_INVALID", "unknown component kind")
        catalog = self.catalog(project_root)
        return tuple(
            self._resolve_from_catalog(
                catalog,
                kind,
                identifier,
                internal=internal,
            )
            for identifier in identifiers
        )

    def _selection_record(
        self,
        source: Any,
        *,
        selection_source: str,
        selector_path: str,
        selector_key: str,
        selector_digest: str,
    ) -> Any:
        payload = {
            "resource_id": source.resource_id,
            "kind": source.kind,
            "selection_source": selection_source,
            "selector_path": selector_path,
            "selector_key": selector_key,
            "selector_digest": selector_digest,
        }
        return _PROTOCOL.normalize_project_selection_record(
            {**payload, "selection_digest": _sha256(_canonical_json(payload))},
            self.protocol,
        )

    def select_project_agent_from_roster(
        self,
        project_root: Path,
        *,
        roster_field: str,
        agent_id: str,
    ) -> Any:
        """Prove exact project-agent selection by the bounded project roster."""
        if (
            roster_field not in self.protocol.project_extension_roster_fields
            or not roster_field.endswith("_agents")
        ):
            _fail("RESOURCE_UNTRUSTED", "field is not a project extension roster")
        source = self.resolve("agent", agent_id, project_root=project_root)
        if source.origin != "project":
            _fail("RESOURCE_UNTRUSTED", "built-in agents do not use project admission")
        project = self.anchor_project_root(project_root)
        with _anchor_directory(Path(project.canonical_root)) as root:
            snapshot = _read_snapshot(
                root,
                ".launchpad/agents.yml",
                maximum_bytes=self.protocol.limits["yaml_aggregate_bytes"],
                maximum_depth=self.protocol.limits["catalog_depth"],
            )
        try:
            roster = _PROTOCOL.strict_load_yaml(
                snapshot.content,
                source_limit="yaml_aggregate_bytes",
                allowed_fields=self.protocol.project_extension_roster_fields,
                contract=self.protocol,
            )
        except _PROTOCOL.ProtocolValidationError as exc:
            _fail(exc.code, str(exc))
        selected = roster.get(roster_field)
        if not isinstance(selected, list):
            _fail("RESOURCE_UNTRUSTED", "project roster field must be a list")
        if len(selected) > self.protocol.limits["definitions_per_type"]:
            _fail("LIMIT_EXCEEDED", "project roster exceeds its definition limit")
        if any(
            not isinstance(value, str)
            or self.protocol.name_pattern.fullmatch(value) is None
            for value in selected
        ):
            _fail("RESOURCE_UNTRUSTED", "project roster contains an invalid agent ID")
        if len(selected) != len(set(selected)):
            _fail("SOURCE_DUPLICATE", "project roster contains a duplicate agent ID")
        if agent_id not in selected:
            _fail("RESOURCE_UNTRUSTED", "project agent is not explicitly rostered")
        return self._selection_record(
            source,
            selection_source="roster",
            selector_path=".launchpad/agents.yml",
            selector_key=roster_field,
            selector_digest=snapshot.digest,
        )

    def select_project_reference(
        self,
        owner: Any,
        source: Any,
        *,
        project_root: Path,
    ) -> Any:
        """Prove an exact project extension was named by canonical metadata."""
        if owner.origin != "built_in" or source.origin != "project":
            _fail("RESOURCE_UNTRUSTED", "project references require a canonical owner")
        declarations = self._owner_declarations(owner, project_root=None)
        values = declarations.skills if source.kind == "skill" else declarations.agents
        if source.resource_id not in values:
            _fail(
                "RESOURCE_UNTRUSTED", "project extension is not explicitly referenced"
            )
        self.anchor_project_root(project_root)
        return self._selection_record(
            source,
            selection_source="canonical_reference",
            selector_path=owner.source_path,
            selector_key="skills" if source.kind == "skill" else "agents",
            selector_digest=owner.source_digest,
        )

    def verify_project_selection(
        self,
        selection: Any,
        source: Any,
        *,
        project_root: Path,
    ) -> None:
        """Revalidate the exact selector digest immediately before admission."""
        if (
            selection.resource_id != source.resource_id
            or selection.kind != source.kind
            or source.origin != "project"
        ):
            _fail("APPROVAL_SCOPE_MISMATCH", "selection does not bind this source")
        if selection.selection_source == "roster":
            if (
                selection.selector_key
                not in self.protocol.project_extension_roster_fields
            ):
                _fail("RESOURCE_UNTRUSTED", "selection roster key is invalid")
            project = self.anchor_project_root(project_root)
            with _anchor_directory(Path(project.canonical_root)) as root:
                snapshot = _read_snapshot(
                    root,
                    selection.selector_path,
                    maximum_bytes=self.protocol.limits["yaml_aggregate_bytes"],
                    maximum_depth=self.protocol.limits["catalog_depth"],
                )
            if snapshot.digest != selection.selector_digest:
                _fail(
                    "SOURCE_DIGEST_MISMATCH", "project selector changed after approval"
                )
            try:
                roster = _PROTOCOL.strict_load_yaml(
                    snapshot.content,
                    source_limit="yaml_aggregate_bytes",
                    allowed_fields=self.protocol.project_extension_roster_fields,
                    contract=self.protocol,
                )
            except _PROTOCOL.ProtocolValidationError as exc:
                _fail(exc.code, str(exc))
            selected = roster.get(selection.selector_key)
            if not isinstance(selected, list) or source.resource_id not in selected:
                _fail("RESOURCE_UNTRUSTED", "project source is no longer rostered")
            return
        owner_matches = [
            item
            for item in self.builtin_catalog().all_sources
            if item.source_path == selection.selector_path
        ]
        if len(owner_matches) != 1:
            _fail("RESOURCE_UNTRUSTED", "canonical selector no longer resolves")
        owner = owner_matches[0]
        if owner.source_digest != selection.selector_digest:
            _fail("SOURCE_DIGEST_MISMATCH", "canonical selector changed after approval")
        declarations = self._owner_declarations(owner, project_root=None)
        selected = (
            declarations.skills
            if selection.selector_key == "skills"
            else declarations.agents
        )
        if source.resource_id not in selected:
            _fail("RESOURCE_UNTRUSTED", "project source is no longer referenced")

    def _root_for_record(self, record: Any, project_root: Path | None) -> AnchoredRoot:
        if record.origin == "built_in":
            return _anchor_directory(self._plugin_path)
        if project_root is None:
            _fail("ROOT_INVALID", "project source requires an explicit project root")
        project = self.anchor_project_root(project_root)
        return _anchor_directory(Path(project.canonical_root))

    def read(
        self,
        record: Any,
        *,
        expected_digest: str,
        project_root: Path | None = None,
        race_hook: RaceHook | None = None,
    ) -> SourceRead:
        """Read the exact UTF-8 bytes from a fresh descriptor-pinned snapshot."""
        if record.origin == "project":
            _fail(
                "APPROVAL_REQUIRED",
                "quarantined project bytes require authenticated admission",
            )
        return self._read_exact(
            record,
            expected_digest=expected_digest,
            project_root=project_root,
            race_hook=race_hook,
        )

    def _read_exact(
        self,
        record: Any,
        *,
        expected_digest: str,
        project_root: Path | None = None,
        race_hook: RaceHook | None = None,
    ) -> SourceRead:
        if expected_digest != record.source_digest:
            _fail("SOURCE_DIGEST_MISMATCH", "expected digest differs from inspection")
        with self._root_for_record(record, project_root) as root:
            snapshot = _read_snapshot(
                root,
                record.source_path,
                maximum_bytes=self._source_limit(),
                maximum_depth=self._path_depth_limit(record.origin),
                race_hook=race_hook,
            )
        if snapshot.digest != expected_digest:
            _fail("SOURCE_DIGEST_MISMATCH", "source changed after inspection")
        return SourceRead(
            record=record,
            content=snapshot.content.decode("utf-8", errors="strict"),
            content_bytes=snapshot.content,
        )

    def _owner_declarations(self, owner: Any, *, project_root: Path | None) -> Any:
        source = self._read_exact(
            owner,
            expected_digest=owner.source_digest,
            project_root=project_root,
        )
        try:
            metadata, _body = _PROTOCOL.normalize_document_metadata(
                source.content_bytes, self.protocol
            )
        except _PROTOCOL.ProtocolValidationError as exc:
            _fail(exc.code, str(exc))
        return metadata.direct

    def _resource_location(
        self, owner: Any, relative_path: str, declarations: Any
    ) -> tuple[str, str]:
        _validate_relative_path(
            relative_path, max_depth=self.protocol.limits["catalog_depth"]
        )
        declared_family: str | None = None
        for family in ("references", "assets", "scripts"):
            if relative_path in getattr(declarations, family):
                if declared_family is not None:
                    _fail(
                        "SOURCE_AMBIGUOUS", "resource is declared in multiple families"
                    )
                declared_family = family
        if declared_family is None:
            _fail("RESOURCE_UNDECLARED", "resource is not declared by its owner")
        if declared_family in {"references", "assets"} and owner.kind == "skill":
            base = PurePosixPath(owner.source_path).parent
            resolved = (base / relative_path).as_posix()
            owner_root = base.as_posix()
        else:
            resolved = PurePosixPath(relative_path).as_posix()
            owner_root = ""
        resolved_parts = _validate_relative_path(
            resolved, max_depth=self._path_depth_limit(owner.origin)
        )
        if owner_root:
            root_parts = PurePosixPath(owner_root).parts
            if tuple(resolved_parts[: len(root_parts)]) != root_parts:
                _fail("PATH_ESCAPE", "resource escapes its owner root")
        return resolved, declared_family

    def inspect_resource(
        self,
        owner: Any,
        relative_path: str,
        *,
        project_root: Path | None = None,
        race_hook: RaceHook | None = None,
    ) -> Any:
        declarations = self._owner_declarations(owner, project_root=project_root)
        resolved, _family = self._resource_location(owner, relative_path, declarations)
        with self._root_for_record(owner, project_root) as root:
            snapshot = _read_snapshot(
                root,
                resolved,
                maximum_bytes=self.protocol.limits["body_bytes"],
                maximum_depth=self._path_depth_limit(owner.origin),
                race_hook=race_hook,
            )
        return _PROTOCOL.normalize_resolver_resource_record(
            {
                "owner_id": owner.resource_id,
                "owner_kind": owner.kind,
                "origin": owner.origin,
                "relative_path": relative_path,
                "source_digest": snapshot.digest,
                "size": snapshot.size,
                "quarantined": owner.origin == "project",
            },
            self.protocol,
        )

    def read_resource(
        self,
        owner: Any,
        resource: Any,
        *,
        expected_digest: str,
        project_root: Path | None = None,
        race_hook: RaceHook | None = None,
    ) -> ResourceRead:
        if resource.origin == "project":
            _fail(
                "APPROVAL_REQUIRED",
                "quarantined project resources require a separate authenticated envelope",
            )
        if owner.resource_id != resource.owner_id or owner.kind != resource.owner_kind:
            _fail("RESOURCE_UNDECLARED", "resource owner binding differs")
        if expected_digest != resource.source_digest:
            _fail("SOURCE_DIGEST_MISMATCH", "expected resource digest differs")
        declarations = self._owner_declarations(owner, project_root=project_root)
        resolved, _family = self._resource_location(
            owner, resource.relative_path, declarations
        )
        with self._root_for_record(owner, project_root) as root:
            snapshot = _read_snapshot(
                root,
                resolved,
                maximum_bytes=self.protocol.limits["body_bytes"],
                maximum_depth=self._path_depth_limit(owner.origin),
                race_hook=race_hook,
            )
        if snapshot.digest != expected_digest:
            _fail("SOURCE_DIGEST_MISMATCH", "resource changed after inspection")
        return ResourceRead(
            record=resource,
            content=snapshot.content.decode("utf-8", errors="strict"),
            content_bytes=snapshot.content,
        )


class InteractiveEventVerifier(Protocol):
    """Host-owned verifier; repository data cannot implement this boundary."""

    def __call__(self, event: str, record: Any) -> bool: ...


@dataclass(frozen=True)
class ApprovalEnvelope:
    record: Any
    token: str


@dataclass(frozen=True)
class AdmittedProjectPrompt:
    admission: Any
    source: Any
    content_bytes: bytes
    structured_data: str


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode(value: str, *, error_code: str = "APPROVAL_INVALID") -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except (UnicodeEncodeError, ValueError, binascii.Error):
        _fail(error_code, "approval token encoding is invalid")
    if not hmac.compare_digest(_b64_encode(decoded), value):
        _fail(error_code, "approval token encoding is not canonical")
    return decoded


class ProjectTrustAuthority:
    """In-memory, one-use admission authority with no durable trust cache."""

    def __init__(
        self,
        *,
        interactive_verifier: InteractiveEventVerifier | None = None,
        session_secret: bytes | None = None,
    ) -> None:
        self.protocol = _PROTOCOL.load_protocol()
        self._interactive_verifier = interactive_verifier
        self._secret = session_secret or secrets.token_bytes(32)
        if len(self._secret) < 32:
            _fail("APPROVAL_INVALID", "session secret is too short")
        self._issued: dict[str, Any] = {}
        self._consumed: set[str] = set()
        self._headless_replay: set[str] = set()

    def _record(
        self,
        source: Any,
        project: Any,
        selection: Any,
        *,
        requested_capability: str,
        run_id: str,
        child_id: str,
        workflow_id: str,
        repository_ref: str,
        admission_source: str,
        nonce: str | None,
        expires_at: int,
    ) -> Any:
        if selection.resource_id != source.resource_id or selection.kind != source.kind:
            _fail(
                "APPROVAL_SCOPE_MISMATCH", "selection does not bind this project source"
            )
        return _PROTOCOL.normalize_project_admission_record(
            {
                "nonce": nonce or secrets.token_hex(32),
                "expires_at": expires_at,
                "repository_identity": project.repository_identity,
                "canonical_root_digest": _sha256(
                    project.canonical_root.encode("utf-8")
                ),
                "relative_path": source.source_path,
                "kind": source.kind,
                "content_digest": source.source_digest,
                "selection_digest": selection.selection_digest,
                "protocol_version": self.protocol.protocol_version,
                "requested_capability": requested_capability,
                "run_id": run_id,
                "child_id": child_id,
                "workflow_id": workflow_id,
                "repository_ref": repository_ref,
                "source": admission_source,
            },
            self.protocol,
        )

    def _seal(self, record: Any) -> ApprovalEnvelope:
        payload = _canonical_json(dataclasses.asdict(record))
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        token = f"{_b64_encode(payload)}.{_b64_encode(signature)}"
        self._issued[record.nonce] = record
        return ApprovalEnvelope(record=record, token=token)

    def approve_interactive(
        self,
        source: Any,
        project: Any,
        selection: Any,
        *,
        requested_capability: str,
        run_id: str,
        child_id: str,
        workflow_id: str,
        repository_ref: str,
        host_event: str,
        now: int | None = None,
        ttl_seconds: int | None = None,
    ) -> ApprovalEnvelope:
        if source.origin != "project" or not source.quarantined:
            _fail(
                "APPROVAL_INVALID",
                "only quarantined project definitions need admission",
            )
        if self._interactive_verifier is None:
            _fail(
                "HOST_NO_AUTHENTICATED_PROJECT_PROMPT_ADMISSION",
                "host-authenticated interactive admission is unavailable",
            )
        if (
            not isinstance(host_event, str)
            or not host_event
            or len(host_event.encode("utf-8"))
            > self.protocol.limits["yaml_scalar_bytes"]
        ):
            _fail("APPROVAL_INVALID", "host event is invalid or oversized")
        issued_at = int(time.time()) if now is None else now
        maximum_ttl = self.protocol.limits["project_approval_ttl_seconds"]
        ttl = maximum_ttl if ttl_seconds is None else ttl_seconds
        if ttl < 1 or ttl > maximum_ttl:
            _fail("APPROVAL_INVALID", "approval TTL is outside the protocol bound")
        record = self._record(
            source,
            project,
            selection,
            requested_capability=requested_capability,
            run_id=run_id,
            child_id=child_id,
            workflow_id=workflow_id,
            repository_ref=repository_ref,
            admission_source="interactive",
            nonce=None,
            expires_at=issued_at + ttl,
        )
        if not self._interactive_verifier(host_event, record):
            _fail("APPROVAL_INVALID", "host event did not authenticate this admission")
        return self._seal(record)

    def approve_headless(
        self,
        source: Any,
        project: Any,
        selection: Any,
        *,
        requested_capability: str,
        run_id: str,
        child_id: str,
        workflow_id: str,
        repository_ref: str,
        signed_policy: str,
        verifier: HeadlessPolicyVerifier,
        now: int | None = None,
    ) -> ApprovalEnvelope:
        if source.origin != "project" or not source.quarantined:
            _fail(
                "APPROVAL_INVALID",
                "only quarantined project definitions need admission",
            )
        record = verifier.verify(
            signed_policy,
            source,
            project,
            selection,
            requested_capability=requested_capability,
            run_id=run_id,
            child_id=child_id,
            workflow_id=workflow_id,
            repository_ref=repository_ref,
            now=now,
        )
        if record.nonce in self._headless_replay:
            _fail("APPROVAL_REPLAYED", "headless policy nonce was already admitted")
        self._headless_replay.add(record.nonce)
        return self._seal(record)

    def consume(
        self,
        envelope_token: str,
        source: Any,
        project: Any,
        selection: Any,
        *,
        requested_capability: str,
        run_id: str,
        child_id: str,
        workflow_id: str,
        repository_ref: str,
        now: int | None = None,
    ) -> Any:
        if (
            len(envelope_token.encode("utf-8"))
            > self.protocol.limits["yaml_scalar_bytes"]
        ):
            _fail("APPROVAL_INVALID", "approval token exceeds its size bound")
        try:
            payload_text, signature_text = envelope_token.split(".", 1)
        except ValueError:
            _fail("APPROVAL_INVALID", "approval token shape is invalid")
        payload = _b64_decode(payload_text)
        signature = _b64_decode(signature_text)
        expected_signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            _fail("APPROVAL_INVALID", "approval token signature is invalid")
        try:
            raw = json.loads(payload, object_pairs_hook=_strict_json_pairs)
            record = _PROTOCOL.normalize_project_admission_record(raw, self.protocol)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            _DuplicateJsonKey,
            _PROTOCOL.ProtocolValidationError,
        ):
            _fail("APPROVAL_INVALID", "approval token payload is invalid")
        if record.nonce in self._consumed:
            _fail("APPROVAL_REPLAYED", "approval was already consumed")
        if self._issued.get(record.nonce) != record:
            _fail("APPROVAL_INVALID", "approval was not issued by this session")
        current_time = int(time.time()) if now is None else now
        if current_time >= record.expires_at:
            _fail("APPROVAL_EXPIRED", "approval has expired")
        expected = {
            "repository_identity": project.repository_identity,
            "canonical_root_digest": _sha256(project.canonical_root.encode("utf-8")),
            "relative_path": source.source_path,
            "kind": source.kind,
            "content_digest": source.source_digest,
            "selection_digest": selection.selection_digest,
            "protocol_version": self.protocol.protocol_version,
            "requested_capability": requested_capability,
            "run_id": run_id,
            "child_id": child_id,
            "workflow_id": workflow_id,
            "repository_ref": repository_ref,
        }
        if any(getattr(record, key) != value for key, value in expected.items()):
            _fail(
                "APPROVAL_SCOPE_MISMATCH",
                "approval does not match the requested envelope",
            )
        self._consumed.add(record.nonce)
        return record


class HeadlessPolicyVerifier:
    """Verifier for one fixed, administrator-owned, read-only secret mount."""

    def __init__(self, secret_file: Path) -> None:
        self.secret_file = _validate_absolute_path(secret_file)

    def _secret(self, project: Any) -> bytes:
        if self.secret_file.is_relative_to(Path(project.canonical_root)):
            _fail(
                "HEADLESS_POLICY_INVALID", "policy secret cannot be repository content"
            )
        parent = self.secret_file.parent
        with _anchor_directory(parent) as root:
            info = _stat_relative(root, self.secret_file.name, maximum_depth=1)
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                _fail("HEADLESS_POLICY_INVALID", "policy secret must be a regular file")
            if (
                info.st_uid not in {0, os.geteuid()}
                or stat.S_IMODE(info.st_mode) != 0o400
            ):
                _fail(
                    "HEADLESS_POLICY_INVALID", "policy secret owner or mode is invalid"
                )
            snapshot = _read_snapshot(
                root,
                self.secret_file.name,
                maximum_bytes=4096,
                maximum_depth=1,
            )
        secret = snapshot.content.rstrip(b"\n")
        if len(secret) < 32:
            _fail("HEADLESS_POLICY_INVALID", "policy secret is too short")
        return secret

    def verify(
        self,
        token: str,
        source: Any,
        project: Any,
        selection: Any,
        *,
        requested_capability: str,
        run_id: str,
        child_id: str,
        workflow_id: str,
        repository_ref: str,
        now: int | None = None,
    ) -> Any:
        protocol = _PROTOCOL.load_protocol()
        if len(token.encode("utf-8")) > protocol.limits["yaml_scalar_bytes"]:
            _fail("HEADLESS_POLICY_INVALID", "headless policy exceeds its size bound")
        try:
            payload_text, signature_text = token.split(".", 1)
        except ValueError:
            _fail("HEADLESS_POLICY_INVALID", "headless policy shape is invalid")
        payload = _b64_decode(payload_text, error_code="HEADLESS_POLICY_INVALID")
        signature = _b64_decode(signature_text, error_code="HEADLESS_POLICY_INVALID")
        expected = hmac.new(self._secret(project), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            _fail("HEADLESS_POLICY_INVALID", "headless policy signature is invalid")
        try:
            raw = json.loads(payload, object_pairs_hook=_strict_json_pairs)
            record = _PROTOCOL.normalize_project_admission_record(raw)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            _DuplicateJsonKey,
            _PROTOCOL.ProtocolValidationError,
        ):
            _fail("HEADLESS_POLICY_INVALID", "headless policy payload is invalid")
        if record.source != "headless":
            _fail("HEADLESS_POLICY_INVALID", "headless policy source differs")
        current_time = int(time.time()) if now is None else now
        if current_time >= record.expires_at:
            _fail("APPROVAL_EXPIRED", "headless policy has expired")
        if (
            record.expires_at - current_time
            > protocol.limits["project_approval_ttl_seconds"]
        ):
            _fail("HEADLESS_POLICY_INVALID", "headless policy expiry exceeds its bound")
        expected_values = {
            "repository_identity": project.repository_identity,
            "canonical_root_digest": _sha256(project.canonical_root.encode("utf-8")),
            "relative_path": source.source_path,
            "kind": source.kind,
            "content_digest": source.source_digest,
            "selection_digest": selection.selection_digest,
            "protocol_version": _PROTOCOL.load_protocol().protocol_version,
            "requested_capability": requested_capability,
            "run_id": run_id,
            "child_id": child_id,
            "workflow_id": workflow_id,
            "repository_ref": repository_ref,
        }
        if any(getattr(record, key) != value for key, value in expected_values.items()):
            _fail("APPROVAL_SCOPE_MISMATCH", "headless policy scope differs")
        return record


def admit_project_source(
    resolver: SecureResolver,
    authority: ProjectTrustAuthority,
    source: Any,
    project_root: Path,
    envelope: ApprovalEnvelope,
    selection: Any,
    *,
    requested_capability: str,
    run_id: str,
    child_id: str,
    workflow_id: str,
    repository_ref: str,
    now: int | None = None,
) -> AdmittedProjectPrompt:
    """Admit exactly one immutable project prompt as escaped bounded data."""
    if source.origin != "project" or not source.quarantined:
        _fail("APPROVAL_INVALID", "source is not a quarantined project definition")
    project = resolver.anchor_project_root(project_root)
    resolver.verify_project_selection(
        selection,
        source,
        project_root=project_root,
    )
    fresh = resolver._read_exact(
        source,
        expected_digest=envelope.record.content_digest,
        project_root=project_root,
    )
    admission = authority.consume(
        envelope.token,
        source,
        project,
        selection,
        requested_capability=requested_capability,
        run_id=run_id,
        child_id=child_id,
        workflow_id=workflow_id,
        repository_ref=repository_ref,
        now=now,
    )
    data = {
        "classification": "untrusted_project_prompt_data",
        "capability_envelope": requested_capability,
        "content": fresh.content,
        "digest": source.source_digest,
        "kind": source.kind,
        "source_id": source.resource_id,
    }
    return AdmittedProjectPrompt(
        admission=admission,
        source=source,
        content_bytes=fresh.content_bytes,
        structured_data=_canonical_json(data).decode("utf-8"),
    )


def _jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        dataclass_value = cast(Any, value)
        return {
            key: _jsonable(item)
            for key, item in dataclasses.asdict(dataclass_value).items()
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _catalog_json(catalog: Catalog) -> dict[str, object]:
    return {
        "plugin_version": catalog.plugin_version,
        "protocol_version": catalog.protocol_version,
        "metadata_digest": catalog.metadata_digest,
        "commands": [_jsonable(item) for item in catalog.commands.values()],
        "skills": [_jsonable(item) for item in catalog.skills.values()],
        "agents": [_jsonable(item) for item in catalog.agents.values()],
        "project_skills": [_jsonable(item) for item in catalog.project_skills.values()],
        "project_agents": [_jsonable(item) for item in catalog.project_agents.values()],
        "warnings": list(catalog.warnings),
        "invalid_entries": list(catalog.invalid_entries),
        "project_root": _jsonable(catalog.project_root),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("catalog", "inventory", "check"):
        command = subparsers.add_parser(action)
        command.add_argument("--project-root", type=Path)
        if action == "check":
            command.add_argument("--strict", action="store_true")
    for action in ("inspect", "resolve", "read"):
        command = subparsers.add_parser(action)
        command.add_argument("kind", choices=("command", "skill", "agent"))
        command.add_argument("identifier")
        command.add_argument("--project-root", type=Path)
        command.add_argument(
            "--reference-class",
            choices=("exact", "explicit_path", "logical"),
            default="exact",
        )
        command.add_argument("--public", action="store_true")
        if action == "read":
            command.add_argument("--expected-digest", required=True)
    batch = subparsers.add_parser("inspect-batch")
    batch.add_argument("kind", choices=("command", "skill", "agent"))
    batch.add_argument("identifiers", nargs="+")
    batch.add_argument("--project-root", type=Path)
    batch.add_argument("--public", action="store_true")
    for action in ("inspect-resource", "read-resource"):
        command = subparsers.add_parser(action)
        command.add_argument(
            "--owner-kind", choices=("command", "skill", "agent"), required=True
        )
        command.add_argument("--owner-id", required=True)
        command.add_argument("--relative-path", required=True)
        command.add_argument("--project-root", type=Path)
        if action == "read-resource":
            command.add_argument("--expected-digest", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    resolver = SecureResolver()
    try:
        if args.action in {"catalog", "inventory", "check"}:
            catalog = resolver.catalog(args.project_root)
            if args.action == "check" and args.strict and catalog.invalid_entries:
                _fail("CATALOG_INVALID", "strict catalog check found invalid entries")
            result: object = _catalog_json(catalog)
        elif args.action in {"inspect", "resolve", "read"}:
            record = resolver.resolve(
                args.kind,
                args.identifier,
                project_root=args.project_root,
                reference_class=args.reference_class,
                internal=not args.public,
            )
            if args.action == "read":
                if record.origin == "project":
                    _fail(
                        "APPROVAL_REQUIRED",
                        "project source requires authenticated admission",
                    )
                read = resolver.read(record, expected_digest=args.expected_digest)
                result = {"record": _jsonable(read.record), "content": read.content}
            else:
                result = _jsonable(record)
        elif args.action == "inspect-batch":
            result = _jsonable(
                resolver.inspect_batch(
                    args.kind,
                    args.identifiers,
                    project_root=args.project_root,
                    internal=not args.public,
                )
            )
        else:
            owner = resolver.resolve(
                args.owner_kind,
                args.owner_id,
                project_root=args.project_root,
                internal=True,
            )
            resource = resolver.inspect_resource(
                owner,
                args.relative_path,
                project_root=args.project_root,
            )
            if args.action == "read-resource":
                if resource.origin == "project":
                    _fail(
                        "APPROVAL_REQUIRED",
                        "project resource requires authenticated admission",
                    )
                read_resource = resolver.read_resource(
                    owner,
                    resource,
                    expected_digest=args.expected_digest,
                    project_root=args.project_root,
                )
                result = {
                    "record": _jsonable(read_resource.record),
                    "content": read_resource.content,
                }
            else:
                result = _jsonable(resource)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ResolverError as exc:
        print(
            json.dumps(
                {
                    "code": exc.code,
                    "message": str(exc),
                    "reporting_class": exc.reporting_class,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AdmittedProjectPrompt",
    "ApprovalEnvelope",
    "Catalog",
    "HeadlessPolicyVerifier",
    "ProjectTrustAuthority",
    "ResolverError",
    "ResourceRead",
    "SecureResolver",
    "SourceRead",
    "admit_project_source",
    "main",
]
