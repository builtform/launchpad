"""Detect database changes from repository-relative paths without running project code."""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import json
import os
import re
import stat
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import NoReturn

_MAX_BYTES = 1024 * 1024
_MAX_DRIZZLE_GLOBS = 64
_EXCLUDED = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "site-packages",
    "__pycache__",
    "dist",
    "build",
}
_JS_EXTENSIONS = {".ts", ".js", ".mts", ".mjs", ".cts", ".cjs"}
_REGEX_PREFIXES = frozenset("=(:,[!&|?;+-*%<>^~/")
_REGEX_KEYWORDS = frozenset(
    {
        "return",
        "throw",
        "case",
        "yield",
        "await",
        "void",
        "typeof",
        "delete",
        "in",
        "instanceof",
    }
)
_DEFAULT_SCHEMA = (
    "src/schema.ts",
    "src/schema/**/*.ts",
    "src/db/schema.ts",
    "src/db/schema/**/*.ts",
)


def _relative(raw: str) -> str | None:
    if (
        not isinstance(raw, str)
        or raw.startswith("/")
        or ".." in raw.split("/")
        or any(ord(c) < 32 for c in raw)
    ):
        return None
    return PurePosixPath(raw).as_posix()


def _under(path: str, directory: str) -> bool:
    return directory == "." or path == directory or path.startswith(directory + "/")


def _join(root: str, relative: str) -> str | None:
    value = _relative(relative)
    if value is None:
        return None
    return (PurePosixPath(root) / value).as_posix()


def _matches(path: str, pattern: str) -> bool:
    """Match POSIX globs with bounded state propagation and zero-directory **/."""
    if not any(char in pattern for char in "*?["):
        if PurePosixPath(pattern).suffix:
            return path == pattern
        return _under(path, pattern) and PurePosixPath(path).suffix in _JS_EXTENSIONS
    # Each token visits at most len(path) + 1 states; no regex backtracking.
    reachable = {0}
    i = 0
    while i < len(pattern) and reachable:
        if pattern[i : i + 3] == "**/":
            following = set(reachable)
            in_component = False
            for index, char in enumerate(path):
                if char == "/":
                    if in_component:
                        following.add(index + 1)
                    in_component = False
                else:
                    in_component = in_component or index in following
            reachable = following
            i += 3
        elif pattern[i : i + 2] == "**":
            reachable = set(range(min(reachable), len(path) + 1))
            i += 2
        elif pattern[i] == "*":
            for index, char in enumerate(path):
                if char != "/" and index in reachable:
                    reachable.add(index + 1)
            i += 1
        else:
            part = pattern[i]
            if part == "[":
                start = i + 1
                if pattern[start : start + 1] == "!":
                    start += 1
                if pattern[start : start + 1] == "]":
                    start += 1
                end = pattern.find("]", start)
                if end != -1:
                    part = pattern[i : end + 1]
                    i = end
            reachable = {
                index + 1
                for index in reachable
                if index < len(path)
                and (
                    (part == "?" and path[index] != "/")
                    or (
                        len(part) > 1
                        and path[index] != "/"
                        and fnmatch.fnmatchcase(path[index], part)
                    )
                    or path[index] == part
                )
            }
            i += 1
    return i == len(pattern) and len(path) in reachable


def _literal(text: str, start: int) -> tuple[str, int] | None:
    """Read one unescaped string literal without copying the remaining source."""
    if start >= len(text) or text[start] not in "'\"`":
        return None
    end = text.find(text[start], start + 1)
    if end == -1:
        return None
    value = text[start + 1 : end]
    if (chr(36) + "{") in value or "\\" in value:
        return None
    return value, end + 1


def _field_start(text: str, key: str) -> int | None:
    """Locate a property in one forward pass, skipping comments and literals."""
    state = "code"
    previous = ""
    key_position = True
    pending_key = False
    want_value = False
    quote = ""
    literal_start = 0
    literal_key = False
    in_class = False
    i = 0
    while i < len(text):
        char = text[i]
        if state == "line_comment":
            if char in "\r\n":
                state = "code"
                key_position = True
            i += 1
            continue
        if state == "block_comment":
            if text.startswith("*/", i):
                state = "code"
                i += 2
            else:
                i += 1
            continue
        if state == "string":
            if char == "\\":
                i += 2
                continue
            if char == quote:
                pending_key = literal_key and text[literal_start + 1 : i] == key
                previous = "<literal>"
                key_position = False
                state = "code"
            i += 1
            continue
        if state == "regex":
            if char in "\r\n":
                state = "code"
                previous = "<regex>"
                key_position = True
            elif char == "\\":
                i += 2
                continue
            elif char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                i += 1
                while i < len(text) and text[i].isalpha():
                    i += 1
                state = "code"
                previous = "<regex>"
                continue
            i += 1
            continue

        if char.isspace():
            if char in "\r\n":
                key_position = True
            i += 1
            continue
        if text.startswith("//", i):
            state = "line_comment"
            i += 2
            continue
        if text.startswith("/*", i):
            state = "block_comment"
            i += 2
            continue
        if want_value:
            return i
        if char in "'\"`":
            state = "string"
            quote = char
            literal_start = i
            literal_key = key_position and char != "`"
            i += 1
            continue
        if char == "/" and (
            not previous or previous in _REGEX_PREFIXES or previous in _REGEX_KEYWORDS
        ):
            state = "regex"
            in_class = False
            pending_key = False
            key_position = False
            i += 1
            continue
        if char.isalnum() or char in "_$":
            start = i
            i += 1
            while i < len(text) and (text[i].isalnum() or text[i] in "_$"):
                i += 1
            previous = text[start:i]
            pending_key = key_position and previous == key
            key_position = False
            continue
        want_value = pending_key and char == ":"
        pending_key = False
        key_position = char in "{,"
        previous = char
        i += 1
    return None


def _space_end(text: str, start: int) -> int:
    """Skip whitespace and comment trivia with a forward-only cursor."""
    while start < len(text):
        if text[start].isspace():
            start += 1
        elif text.startswith("//", start):
            start += 2
            while start < len(text) and text[start] not in "\r\n":
                start += 1
        elif text.startswith("/*", start):
            end = text.find("*/", start + 2)
            start = len(text) if end == -1 else end + 2
        else:
            break
    return start


def _config_value(text: str, key: str) -> str | list[str] | None:
    """Read a static literal string or array using forward-only source offsets."""
    start = _field_start(text, key)
    if start is None:
        return None
    if text[start] == "[":
        start = _space_end(text, start + 1)
        values = []
        while start < len(text) and text[start] != "]":
            item = _literal(text, start)
            if item is None:
                return None
            value, start = item
            values.append(value)
            start = _space_end(text, start)
            if text.startswith(",", start):
                start = _space_end(text, start + 1)
            elif not text.startswith("]", start):
                return None
        if not text.startswith("]", start):
            return None
        start += 1
        result: str | list[str] = values
    else:
        item = _literal(text, start)
        if item is None:
            return None
        result, start = item
    start = _space_end(text, start)
    if start != len(text) and not (
        text[start] in ",}" or text.startswith(("//", "/*"), start)
    ):
        return None
    return result


def _has_glob(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _ancestors(path: str) -> Iterable[str]:
    """Yield repository-relative ancestor keys, deepest first."""
    while path != ".":
        yield path
        path = path.rpartition("/")[0] or "."
    yield "."


class _Patterns:
    """An ordered set with separate literal, folder and glob lookup indexes."""

    def __init__(self) -> None:
        self._ordered: dict[str, None] = {}
        self.files: set[str] = set()
        self.folders: set[str] = set()
        self.globs: list[str] = []

    def __len__(self) -> int:
        return len(self._ordered)

    def __contains__(self, pattern: str) -> bool:
        return pattern in self._ordered

    def append(self, pattern: str) -> None:
        if pattern in self._ordered:
            return
        self._ordered[pattern] = None
        if _has_glob(pattern):
            self.globs.append(pattern)
        elif PurePosixPath(pattern).suffix:
            self.files.add(pattern)
        else:
            self.folders.add(pattern)

    def extend(self, patterns: Iterable[str]) -> None:
        for pattern in patterns:
            self.append(pattern)

    def matches(self, path: str) -> bool:
        if path in self.files:
            return True
        if (
            self.folders
            and PurePosixPath(path).suffix in _JS_EXTENSIONS
            and any(parent in self.folders for parent in _ancestors(path))
        ):
            return True
        return any(_matches(path, pattern) for pattern in self.globs)


@dataclass
class _Instance:
    tool: str
    root: str
    patterns: _Patterns = field(default_factory=_Patterns)
    migrations: set[str] = field(default_factory=set)
    other: set[str] = field(default_factory=set)
    notes: set[str] = field(default_factory=set)
    changed_schema: set[str] = field(default_factory=set)
    changed_migrations: set[str] = field(default_factory=set)
    changed_other: set[str] = field(default_factory=set)


class _Repository:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.notes: dict[str, str] = {}
        self.files: set[str] = set()
        self.instances: dict[tuple[str, str], _Instance] = {}
        self.active: set[tuple[str, str]] = set()
        self._confined_cache: dict[str, bool] = {}
        self._exists_cache: dict[str, bool] = {}
        for folder, directories, files in os.walk(
            self.root, followlinks=False, onerror=self._walk_error
        ):
            directories[:] = sorted(
                d
                for d in directories
                if d not in _EXCLUDED and not self._is_symlink(Path(folder) / d)
            )
            for filename in sorted(files):
                path = Path(folder) / filename
                if not self._is_symlink(path) and self._is_regular_file(path):
                    self.files.add(path.relative_to(self.root).as_posix())

    def _is_regular_file(self, path: Path) -> bool:
        try:
            if stat.S_ISREG(path.lstat().st_mode):
                return True
            detail = "non-regular file"
        except (OSError, UnicodeError, ValueError) as exc:
            detail = type(exc).__name__
        name = path.relative_to(self.root).as_posix()
        self.notes[name] = f"unresolved file {name}: {detail}"
        return False

    def _is_symlink(self, path: Path) -> bool:
        try:
            return path.is_symlink()
        except (OSError, UnicodeError, ValueError):
            self.notes[path.relative_to(self.root).as_posix()] = (
                "unresolved file status"
            )
            return True

    def _walk_error(self, exc: OSError) -> None:
        self.notes["."] = f"unresolved directory listing: {exc.strerror}"

    def confined(self, name: str) -> bool:
        if name in self._confined_cache:
            return self._confined_cache[name]
        try:
            result = _relative(name) is not None and (
                self.root / name
            ).resolve().is_relative_to(self.root)
        except (OSError, UnicodeError, ValueError, RuntimeError):
            result = False
        self._confined_cache[name] = result
        return result

    def read(self, name: str) -> str | None:
        try:
            if not self.confined(name):
                self.notes[name] = f"unresolved file outside repository: {name}"
                return None
            if not self._is_regular_file(self.root / name):
                return None
            with (self.root / name).open("rb") as stream:
                content = stream.read(_MAX_BYTES + 1)
            if len(content) > _MAX_BYTES:
                self.notes[name] = f"unresolved file over 1 MiB: {name}"
                return None
            return content.decode("utf-8", errors="replace")
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            self.notes[name] = f"unresolved file {name}: {type(exc).__name__}"
            return None

    def exists(self, name: str) -> bool:
        if name in self._exists_cache:
            return self._exists_cache[name]
        try:
            result = self.confined(name) and (self.root / name).is_file()
        except (OSError, UnicodeError, ValueError, RuntimeError):
            self.notes[name] = f"unresolved file status: {name}"
            result = False
        self._exists_cache[name] = result
        return result

    def instance(self, tool: str, root: str) -> _Instance:
        key = (tool, root)
        if key not in self.instances:
            self.instances[key] = _Instance(tool, root)
        return self.instances[key]

    def add(self, instance: _Instance, kind: str, name: str) -> None:
        self.active.add((instance.tool, instance.root))
        if self.confined(name):
            getattr(instance, "changed_" + kind).add(name)
        elif not any(name in note for note in instance.notes):
            instance.notes.add(f"unresolved changed path outside repository: {name}")

    def output(self, changed: set[str]) -> list[dict]:
        active = {key: self.instances[key] for key in self.active}
        if not active:
            return []
        tools = {tool for tool, _ in active}
        schemas: dict[tuple[str, str], set[str]] = {key: set() for key in active}
        context_notes: dict[tuple[str, str], set[str]] = {key: set() for key in active}
        for path in self.files | changed:
            for tool in tools:
                for instance in _best(active, tool, path):
                    if instance.patterns.matches(path) and self.confined(path):
                        schemas[(instance.tool, instance.root)].add(path)
        for path, note in self.notes.items():
            if path == ".":
                for values in context_notes.values():
                    values.add(note)
            else:
                for tool in tools:
                    for instance in _best(active, tool, path):
                        context_notes[(instance.tool, instance.root)].add(note)
        results: dict[tuple[str, str], dict] = {}
        for key in sorted(self.active):
            instance = self.instances[key]
            notes = instance.notes | context_notes[key]
            root = instance.root
            if not self.confined(root):
                notes.add(f"unresolved root outside repository: {root}")
                root = "."
            schema = sorted(schemas[key])
            directories = sorted(instance.migrations)
            migrations = directories[0] if len(directories) == 1 else root
            if len(directories) > 1:
                notes.add("multiple migration directories: " + ", ".join(directories))
            if not self.confined(migrations):
                notes.add(f"unresolved migrations_dir outside repository: {migrations}")
                migrations = root
            result = {
                "tool": instance.tool,
                "root": root,
                "schema_paths": schema,
                "migrations_dir": migrations,
                "changed_schema": sorted(instance.changed_schema),
                "changed_migrations": sorted(instance.changed_migrations),
                "changed_other": sorted(instance.changed_other),
                "notes": sorted(notes),
            }
            previous = results.get((instance.tool, root))
            if previous:
                for field_name in (
                    "schema_paths",
                    "changed_schema",
                    "changed_migrations",
                    "changed_other",
                    "notes",
                ):
                    previous[field_name] = sorted(
                        set(previous[field_name]) | set(result[field_name])
                    )
                if previous["migrations_dir"] != migrations:
                    previous["migrations_dir"] = root
            else:
                results[(instance.tool, root)] = result
        return [results[key] for key in sorted(results)]


def _prisma_root(name: str) -> str:
    path = PurePosixPath(name)
    if "prisma" in path.parts:
        index = len(path.parts) - 1 - path.parts[::-1].index("prisma")
        return PurePosixPath(*path.parts[:index]).as_posix()
    if path.name == "migration_lock.toml":
        return path.parent.parent.as_posix()
    return path.parent.as_posix()


def _discover_prisma(repo: _Repository, changed: set[str]) -> None:
    paths = repo.files | changed
    configs: dict[str, set[str]] = {}
    for path in paths:
        parent, _, name = path.rpartition("/")
        if re.fullmatch(r"prisma\.config\.[^/]+", name):
            configs.setdefault(parent or ".", set()).add(path)
    for path in sorted(paths, key=lambda p: (not p.endswith("migration_lock.toml"), p)):
        lock = (
            PurePosixPath(path).name == "migration_lock.toml"
            and PurePosixPath(path).parent.name == "migrations"
        )
        if not path.endswith(".prisma") and not (lock and repo.exists(path)):
            continue
        root = _prisma_root(path)
        if path.endswith(".prisma") and "prisma" not in PurePosixPath(path).parts:
            anchored = _best(repo.instances, "prisma", path)
            if anchored:
                root = anchored[0].root
        instance = repo.instance("prisma", root)
        if path.endswith(".prisma"):
            instance.patterns.append(path)
        if lock:
            instance.migrations.add(PurePosixPath(path).parent.as_posix())
        elif not instance.migrations:
            instance.migrations.add(_join(root, "prisma/migrations") or root)
    for instance in repo.instances.values():
        if instance.tool != "prisma":
            continue
        instance.other.update(configs.get(instance.root, ()))


def _discover_drizzle(repo: _Repository, changed: set[str]) -> None:
    configs = sorted(
        p
        for p in repo.files | changed
        if re.fullmatch(
            r"drizzle\.config\.(?:ts|mts|cts|js|mjs|cjs)", PurePosixPath(p).name
        )
    )
    covered = set()
    for config in configs:
        root = PurePosixPath(config).parent.as_posix()
        instance = repo.instance("drizzle", root)
        instance.other.add(config)
        text = repo.read(config) or ""
        schema = _config_value(text, "schema")
        values = [schema] if isinstance(schema, str) else schema
        if values is not None:
            values = list(dict.fromkeys(values))
        raw_patterns = (
            [_join(root, value) for value in values] if values is not None else []
        )
        glob_entries = {p for p in raw_patterns if p is not None and _has_glob(p)}
        capped = len(glob_entries) > _MAX_DRIZZLE_GLOBS
        if capped:
            instance.notes.add(
                f"unresolved schema in {config}: more than 64 glob entries"
            )
        else:
            # Keep lexical patterns to claim an unsafe changed symlink without reading it.
            instance.patterns.extend(p for p in raw_patterns if p is not None)
        if capped:
            instance.patterns.extend(_join(root, p) or p for p in _DEFAULT_SCHEMA)
        elif values is None or any(
            p is None or not repo.confined(p) for p in raw_patterns
        ):
            instance.notes.add(
                f"unresolved schema in {config}: "
                + ", ".join(values or ["no literal value"])
            )
            instance.patterns.extend(_join(root, p) or p for p in _DEFAULT_SCHEMA)
        else:
            instance.notes.add(f"schema location read from {config}")
        out = _config_value(text, "out")
        out_path = _join(root, out) if isinstance(out, str) else None
        if out_path is None or not repo.confined(out_path):
            if out is not None or _field_start(text, "out") is not None:
                instance.notes.add(f"unresolved out in {config}")
            out_path = _join(root, "drizzle") or root
        instance.migrations.add(out_path)
        covered.add(out_path)
    for journal in sorted(repo.files):
        if (
            not journal.endswith("/meta/_journal.json")
            and journal != "meta/_journal.json"
        ):
            continue
        out = PurePosixPath(journal).parent.parent.as_posix()
        if out in covered:
            continue
        root = PurePosixPath(out).parent.as_posix()
        instance = repo.instance("drizzle", root)
        instance.migrations.add(out)
        instance.notes.add(f"migrations discovered from {journal}")


def _discover_alembic(repo: _Repository, changed: set[str]) -> None:
    folders = set()
    notes = set()
    configured_folder: str | None = None
    for path in repo.files:
        parent = PurePosixPath(path).parent
        if (
            PurePosixPath(path).name == "env.py"
            and parent.name in {"alembic", "migrations"}
            and len(parent.parts) <= 3
        ):
            folders.add(parent.as_posix())
    for path in changed:
        parent = PurePosixPath(path).parent
        if parent.name == "versions" and path.endswith(".py"):
            folders.add(parent.parent.as_posix())
    if repo.exists("alembic.ini"):
        text = repo.read("alembic.ini")
        if text is not None:
            try:
                config = configparser.ConfigParser(interpolation=None)
                config.read_string(text)
                value = config.get("alembic", "script_location", fallback="")
                location = _join(".", value.replace("%(here)s", "."))
                if location is not None and repo.confined(location):
                    folders.add(location)
                    configured_folder = location
                else:
                    notes.add("unresolved script_location in alembic.ini")
            except (configparser.Error, ValueError):
                notes.add("unresolved script_location in alembic.ini")
    for folder in sorted(folders):
        env = _join(folder, "env.py")
        template = _join(folder, "script.py.mako")
        if (
            env is None
            or template is None
            or not repo.exists(env)
            or not repo.exists(template)
        ):
            continue
        root = (
            "."
            if folder == configured_folder
            else PurePosixPath(folder).parent.as_posix()
        )
        instance = repo.instance("alembic", root)
        instance.migrations.add(_join(folder, "versions") or folder)
        instance.other.update({env, "alembic.ini"})
        instance.notes.update(notes)
        instance.notes.add("schema_paths contains only changed SQLAlchemy model files")


def _best(
    instances: dict[tuple[str, str], _Instance], tool: str, path: str
) -> list[_Instance]:
    """Find matching roots through bounded ancestor lookups, deepest first."""
    return [
        instance
        for root in _ancestors(path)
        if (instance := instances.get((tool, root))) is not None
    ]


def _layout(name: str, folder: str) -> tuple[str, str] | None:
    parts = PurePosixPath(name).parts
    if folder not in parts:
        return None
    index = len(parts) - 1 - parts[::-1].index(folder)
    return PurePosixPath(*parts[:index]).as_posix(), PurePosixPath(
        *parts[index + 1 :]
    ).as_posix()


def _django_app(repo: _Repository, name: str) -> tuple[str, str] | None:
    path = PurePosixPath(name)
    if path.name == "models.py":
        app, kind = path.parent, "schema"
    elif path.parent.name == "models" and path.suffix == ".py":
        app, kind = path.parent.parent, "schema"
    elif path.parent.name == "migrations" and re.fullmatch(r"\d{4}_.+\.py", path.name):
        app, kind = path.parent.parent, "migrations"
    else:
        return None
    if not repo.exists((app / "migrations/__init__.py").as_posix()):
        return None
    return app.as_posix(), kind


def detect(changed_paths: Iterable[str], repo_root: Path) -> dict:
    """Return deterministic, confined database-review context for changed paths."""
    repo = _Repository(Path(repo_root))
    changed: set[str] = set()
    ignored = 0
    for raw in changed_paths:
        if isinstance(raw, str) and not raw.strip():
            continue
        path = _relative(raw)
        if path is None:
            ignored += 1
        else:
            changed.add(path)

    _discover_prisma(repo, changed)
    _discover_drizzle(repo, changed)
    _discover_alembic(repo, changed)
    alembic_other: dict[str, list[_Instance]] = {}
    for instance in repo.instances.values():
        if instance.tool == "alembic":
            for path in instance.other:
                if not _under(path, instance.root):
                    alembic_other.setdefault(path, []).append(instance)
    django_models: dict[str, set[str]] | None = None
    for path in sorted(changed):
        claimed = False
        parent, _, basename = path.rpartition("/")
        parent = parent or "."
        grandparent = parent.rpartition("/")[0] or "."
        for instance in _best(repo.instances, "prisma", path):
            if path in instance.patterns:
                repo.add(instance, "schema", path)
            elif (
                path in instance.other
                or (basename == "migration_lock.toml" and parent in instance.migrations)
                or (
                    basename == "migration.sql"
                    and grandparent in instance.migrations
                    and repo.exists(_join(grandparent, "migration_lock.toml") or "")
                )
            ):
                repo.add(
                    instance,
                    "other"
                    if path.endswith("migration_lock.toml") or path in instance.other
                    else "migrations",
                    path,
                )
            else:
                continue
            claimed = True
            break
        if claimed:
            continue

        for instance in _best(repo.instances, "drizzle", path):
            if path in instance.other:
                kind = "other"
            elif instance.patterns.matches(path):
                kind = "schema"
            elif (
                parent in instance.migrations
                and path.endswith(".sql")
                and len(basename) > len(".sql")
            ):
                kind = "migrations"
            elif (
                parent.rpartition("/")[2] == "meta"
                and grandparent in instance.migrations
                and re.fullmatch(r"(?:_journal\.json|[^/]+_snapshot\.json)", basename)
            ):
                kind = "other"
            else:
                continue
            repo.add(instance, kind, path)
            claimed = True
            break
        if claimed:
            continue

        supabase = _layout(path, "supabase")
        if supabase:
            root, tail = supabase
            kind = (
                "schema"
                if tail.startswith("schemas/") and tail.endswith(".sql")
                else (
                    "migrations"
                    if re.fullmatch(r"migrations/[^/]+\.sql", tail)
                    else None
                )
            )
            if kind:
                instance = repo.instance("supabase", root)
                instance.patterns.append(_join(root, "supabase/schemas/**/*.sql") or "")
                instance.migrations.add(_join(root, "supabase/migrations") or root)
                instance.notes.add(
                    "Supabase migrations may be authoritative without declarative schemas"
                )
                repo.add(instance, kind, path)
                continue

        rails = _layout(path, "db")
        if rails:
            root, tail = rails
            kind = (
                "schema"
                if tail in {"schema.rb", "structure.sql"}
                else (
                    "migrations" if re.fullmatch(r"migrate/[^/]+\.rb", tail) else None
                )
            )
            if kind:
                instance = repo.instance("rails", root)
                instance.patterns.extend(
                    _join(root, p) or p for p in ("db/schema.rb", "db/structure.sql")
                )
                instance.migrations.add(_join(root, "db/migrate") or root)
                repo.add(instance, kind, path)
                continue

        alembic_instances = _best(repo.instances, "alembic", path)
        if path in alembic_other:
            alembic_instances = sorted(
                alembic_instances + alembic_other[path],
                key=lambda instance: (
                    -len(PurePosixPath(instance.root).parts),
                    instance.root,
                ),
            )
        for instance in alembic_instances:
            if path in instance.other:
                repo.add(instance, "other", path)
            elif (
                parent in instance.migrations
                and path.endswith(".py")
                and len(basename) > len(".py")
            ):
                repo.add(instance, "migrations", path)
            elif path.endswith(".py"):
                text = repo.read(path)
                if text is None:
                    instance.notes.add(
                        f"unresolved SQLAlchemy model classification: {path}"
                    )
                    repo.add(instance, "other", path)
                elif re.search(
                    r"(?m)^[ \t]*(?:from[ \t]+sqlalchemy(?:\.[\w.]+)?[ \t]+import|import[ \t]+sqlalchemy\b)",
                    text,
                ) and re.search(
                    r"\b(?:DeclarativeBase|declarative_base|mapped_column)\b|\bColumn\(",
                    text,
                ):
                    instance.patterns.append(path)
                    repo.add(instance, "schema", path)
                else:
                    continue
            else:
                continue
            claimed = True
            break
        if claimed:
            continue

        django = _django_app(repo, path)
        if django:
            app, kind = django
            root = PurePosixPath(app).parent.as_posix()
            instance = repo.instance("django", root)
            instance.migrations.add(_join(app, "migrations") or app)
            if django_models is None:
                django_models = {}
                for source in repo.files | changed:
                    info = _django_app(repo, source)
                    if info and info[1] == "schema":
                        model_root = PurePosixPath(info[0]).parent.as_posix()
                        django_models.setdefault(model_root, set()).add(source)
            if not instance.patterns:
                instance.patterns.extend(django_models.get(root, ()))
            repo.add(instance, kind, path)
            continue

        if path.endswith(".sql"):
            parent = PurePosixPath(path).parent
            for folder in (parent, *parent.parents):
                if folder.name in {"migrations", "migrate", "db", "sql"}:
                    instance = repo.instance("sql", folder.parent.as_posix())
                    instance.migrations.add(folder.as_posix())
                    instance.notes.add(
                        "plain SQL has no schema side; schema drift patterns 1 and 2 are not evaluated"
                    )
                    repo.add(instance, "migrations", path)
                    break

    projects = repo.output(changed)
    return {
        "detector_version": 1,
        "db_changes": bool(projects),
        "ignored_paths": ignored,
        "projects": projects,
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _main(argv: list[str] | None = None) -> int:
    parser = _Parser(prog="db_change_detector", exit_on_error=False)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--null", action="store_true")
    try:
        args = parser.parse_args(argv)
        root = Path(args.repo_root)
        if not root.is_dir():
            raise ValueError("--repo-root must be a directory")
    except (argparse.ArgumentError, OSError, ValueError) as exc:
        print(f"db_change_detector: {exc}", file=sys.stderr)
        return 2
    paths = sys.stdin.read().split("\0" if args.null else "\n")
    print(json.dumps(detect(paths, root), sort_keys=True))
    return 0


__all__ = ["detect"]


if __name__ == "__main__":
    raise SystemExit(_main())
