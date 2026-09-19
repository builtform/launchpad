"""Resolve and validate LaunchPad canonical files for the Codex router."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import NoReturn

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
COMMAND_REFERENCE_PATTERN = re.compile(r"/lp-[a-z0-9]+(?:-[a-z0-9]+)*")
CLAUDE_VARIABLE_PATTERN = re.compile(r"\$\{CLAUDE_[A-Z0-9_]+\}")
MCP_TOKEN_PATTERN = re.compile(r"mcp__[A-Za-z0-9_]+")
MAX_FILE_BYTES = 1_000_000

KNOWN_HOST_TOKENS = frozenset(
    {
        "${CLAUDE_PLUGIN_ROOT}",
        "AskUserQuestion",
        "allowed-tools",
        "mcp__*",
        "subagent_type",
    }
)

KIND_ROOTS = {
    "agent": "agents",
    "command": "commands",
    "skill": "skills",
}


class RouterError(Exception):
    """Expected router failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class RouterArgumentParser(argparse.ArgumentParser):
    """Convert argument failures into the router JSON error contract."""

    def error(self, message: str) -> NoReturn:
        raise RouterError("usage_error", message)


def _fail(code: str, message: str, **details: object) -> NoReturn:
    raise RouterError(code, message, **details)


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
        return parsed if isinstance(parsed, str) else value
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def _block_scalar(lines: list[str], style: str) -> str:
    content = textwrap.dedent("\n".join(lines)).splitlines()
    indicator = style[0]
    chomp = style[1:] if len(style) > 1 else ""

    if indicator == "|":
        result = "\n".join(content)
    else:
        paragraphs: list[str] = []
        current: list[str] = []
        for line in content:
            if line:
                current.append(line)
                continue
            if current:
                paragraphs.append(" ".join(current))
                current = []
            elif paragraphs and paragraphs[-1] != "":
                paragraphs.append("")
        if current:
            paragraphs.append(" ".join(current))
        result = "\n".join(paragraphs)

    if chomp == "+":
        return result + "\n"
    if chomp == "-":
        return result
    return result + "\n" if result else ""


def _parse_frontmatter(text: str, path: Path) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}

    try:
        end = lines.index("---", 1)
    except ValueError:
        _fail("malformed_frontmatter", f"frontmatter is not closed: {path}")

    metadata: dict[str, str] = {}
    index = 1
    while index < end:
        line = lines[index]
        if not line or line[0].isspace() or ":" not in line:
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value in {">", ">-", ">+", "|", "|-", "|+"}:
            block_lines: list[str] = []
            index += 1
            while index < end:
                candidate = lines[index]
                if candidate and not candidate[0].isspace():
                    break
                block_lines.append(candidate)
                index += 1
            metadata[key] = _block_scalar(block_lines, value)
            continue
        metadata[key] = _parse_scalar(value)
        index += 1
    return metadata


def _safe_text(path: Path, root: Path) -> tuple[Path, str]:
    try:
        root_real = root.resolve(strict=True)
    except OSError as exc:
        _fail("missing_root", f"canonical root is unavailable: {root}", reason=str(exc))
    if root.is_symlink() or not root_real.is_dir():
        _fail("unsafe_root", f"canonical root is not a regular directory: {root}")
    if path.is_symlink():
        _fail("symlink_rejected", f"canonical file is a symlink: {path}")
    try:
        path_real = path.resolve(strict=True)
    except OSError as exc:
        _fail("read_failed", f"canonical file is unavailable: {path}", reason=str(exc))
    if not path_real.is_relative_to(root_real):
        _fail("outside_root", f"canonical file resolves outside its root: {path}")
    if not path_real.is_file():
        _fail("not_regular_file", f"canonical path is not a regular file: {path}")

    try:
        with path_real.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        _fail("read_failed", f"could not read canonical file: {path}", reason=str(exc))
    if len(raw) > MAX_FILE_BYTES:
        _fail(
            "oversize",
            f"canonical file exceeds {MAX_FILE_BYTES} bytes: {path}",
            size=len(raw),
        )
    try:
        return path_real, raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail("invalid_utf8", f"canonical file is not valid UTF-8: {path}")


def _project_root(value: str | None) -> Path | None:
    if value is None:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        _fail("invalid_project_root", "project root must be an absolute path")
    if candidate.is_symlink():
        _fail("invalid_project_root", f"project root must not be a symlink: {value}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        _fail(
            "invalid_project_root",
            f"project root is unavailable: {value}",
            reason=str(exc),
        )
    if not resolved.is_dir():
        _fail("invalid_project_root", f"project root is not a directory: {value}")
    return resolved


def _root(kind: str, origin: str, project_root: Path | None) -> Path | None:
    dirname = KIND_ROOTS.get(kind)
    if dirname is None:
        _fail("unsupported_kind", f"unsupported canonical kind: {kind}")
    if origin == "built_in":
        return PLUGIN_ROOT / dirname
    if kind == "command" or project_root is None:
        return None
    candidate = project_root / ".claude" / dirname
    if candidate.is_symlink():
        _fail("unsafe_root", f"project extension root is a symlink: {candidate}")
    if not candidate.exists():
        return None
    if not candidate.is_dir():
        _fail("unsafe_root", f"project extension root is not a directory: {candidate}")
    candidate_real = candidate.resolve(strict=True)
    if not candidate_real.is_relative_to(project_root):
        _fail("unsafe_root", f"project extension root escapes the project: {candidate}")
    cursor = project_root
    for part in candidate.relative_to(project_root).parts:
        cursor /= part
        if cursor.is_symlink():
            _fail("unsafe_root", f"project extension path uses a symlink: {cursor}")
    return candidate_real


def _candidate_paths(kind: str, root: Path) -> list[Path]:
    if kind == "command":
        return sorted(root.glob("*.md"), key=lambda path: path.as_posix())
    if kind == "skill":
        return sorted(root.rglob("SKILL.md"), key=lambda path: path.as_posix())
    if kind == "agent":
        return sorted(root.rglob("*.md"), key=lambda path: path.as_posix())
    _fail("unsupported_kind", f"unsupported canonical kind: {kind}")


def _fallback_id(kind: str, path: Path) -> str:
    return path.parent.name if kind == "skill" else path.stem


def _record(kind: str, origin: str, path: Path, root: Path) -> dict[str, str]:
    path_real, text = _safe_text(path, root)
    metadata = _parse_frontmatter(text, path_real)
    item_id = metadata.get("name", _fallback_id(kind, path))
    if not NAME_PATTERN.fullmatch(item_id):
        _fail("invalid_id", f"canonical id is invalid: {item_id}", path=str(path_real))
    expected = _fallback_id(kind, path)
    if item_id != expected:
        _fail(
            "id_mismatch",
            f"canonical id does not match its path: {item_id}",
            id=item_id,
            expected=expected,
            path=str(path_real),
        )
    return {
        "description": metadata.get("description", "").rstrip("\n"),
        "id": item_id,
        "kind": kind,
        "origin": origin,
        "path": str(path_real),
    }


def _scan_root(kind: str, origin: str, root: Path) -> list[dict[str, str]]:
    if root.is_symlink() or not root.is_dir():
        _fail("unsafe_root", f"canonical root is not a regular directory: {root}")
    records = [
        _record(kind, origin, path, root) for path in _candidate_paths(kind, root)
    ]
    by_id: dict[str, list[str]] = {}
    for record in records:
        by_id.setdefault(record["id"], []).append(record["path"])
    duplicates = {item_id: paths for item_id, paths in by_id.items() if len(paths) > 1}
    if duplicates:
        item_id = sorted(duplicates)[0]
        _fail(
            "duplicate_id",
            f"canonical id is duplicated within {origin}: {item_id}",
            id=item_id,
            paths=sorted(duplicates[item_id]),
        )
    return records


def _project_records(
    kind: str, root: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, RouterError]]:
    records: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    issues: dict[str, RouterError] = {}
    for path in _candidate_paths(kind, root):
        fallback_id = _fallback_id(kind, path)
        try:
            records.append(_record(kind, "project", path, root))
        except RouterError as exc:
            skipped.append({"code": exc.code, "path": str(path)})
            if NAME_PATTERN.fullmatch(fallback_id):
                issues[fallback_id] = exc
            declared_id = exc.details.get("id")
            if isinstance(declared_id, str) and NAME_PATTERN.fullmatch(declared_id):
                issues[declared_id] = exc

    by_id: dict[str, list[dict[str, str]]] = {}
    for record in records:
        by_id.setdefault(record["id"], []).append(record)
    duplicate_ids = {item_id for item_id, items in by_id.items() if len(items) > 1}
    for item_id in sorted(duplicate_ids):
        paths = sorted(item["path"] for item in by_id[item_id])
        issue = RouterError(
            "duplicate_id",
            f"canonical id is duplicated within project: {item_id}",
            id=item_id,
            paths=paths,
        )
        issues[item_id] = issue
        skipped.extend({"code": issue.code, "path": path} for path in paths)
    records = [record for record in records if record["id"] not in duplicate_ids]
    return records, sorted(skipped, key=lambda item: item["path"]), issues


def _record_set(
    kind: str, project_root: Path | None
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, RouterError]]:
    built_in_root = _root(kind, "built_in", project_root)
    assert built_in_root is not None
    records = _scan_root(kind, "built_in", built_in_root)
    skipped: list[dict[str, str]] = []
    issues: dict[str, RouterError] = {}
    project_extension_root = _root(kind, "project", project_root)
    if project_extension_root is not None:
        project_records, skipped, issues = _project_records(
            kind, project_extension_root
        )
        records.extend(project_records)
    return (
        sorted(
            records,
            key=lambda item: (
                item["id"],
                0 if item["origin"] == "built_in" else 1,
            ),
        ),
        skipped,
        issues,
    )


def _records(kind: str, project_root: Path | None) -> list[dict[str, str]]:
    records, _, _ = _record_set(kind, project_root)
    return records


def _collision_report(records: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for record in records:
        grouped.setdefault(record["id"], []).append(record)
    return [
        {
            "id": item_id,
            "origins": [item["origin"] for item in items],
            "paths": [item["path"] for item in items],
        }
        for item_id, items in sorted(grouped.items())
        if len(items) > 1
    ]


def _inventory(kind: str, project_root: Path | None) -> dict[str, object]:
    records, skipped, _ = _record_set(kind, project_root)
    return {
        "collisions": _collision_report(records),
        "items": records,
        "kind": kind,
        "skipped": skipped,
    }


def _requested_id(kind: str, name: str) -> str:
    if not NAME_PATTERN.fullmatch(name):
        _fail(
            "invalid_name",
            "name must contain only lowercase letters, digits, and hyphens",
            name=name,
        )
    if kind == "command" and not name.startswith("lp-"):
        return f"lp-{name}"
    return name


def _resolve(kind: str, name: str, project_root: Path | None) -> dict[str, object]:
    item_id = _requested_id(kind, name)
    records, skipped, project_issues = _record_set(kind, project_root)
    matches = [record for record in records if record["id"] == item_id]
    if not matches:
        project_issue = project_issues.get(item_id)
        if project_issue is not None:
            project_issue.details["skipped"] = skipped
            raise project_issue
        available = sorted({record["id"] for record in records})
        suggestions = difflib.get_close_matches(item_id, available, n=3, cutoff=0.6)
        _fail(
            "not_found",
            f"canonical {kind} does not exist: {item_id}",
            id=item_id,
            skipped=skipped,
            suggestions=suggestions,
        )

    selected = next(
        (record for record in matches if record["origin"] == "built_in"), matches[0]
    )
    result: dict[str, object] = dict(selected)
    result["collisions"] = [
        {"origin": record["origin"], "path": record["path"]}
        for record in matches
        if record is not selected
    ]
    result["skipped"] = skipped
    return result


def _found_host_tokens(text: str) -> set[str]:
    tokens = set(CLAUDE_VARIABLE_PATTERN.findall(text))
    for token in ("AskUserQuestion", "allowed-tools", "subagent_type"):
        if token in text:
            tokens.add(token)
    if MCP_TOKEN_PATTERN.search(text):
        tokens.add("mcp__*")
    return tokens


def _lint(project_root: Path | None) -> dict[str, object]:
    records_by_kind = {
        kind: _records(kind, project_root) for kind in ("command", "skill", "agent")
    }
    for kind in ("command", "skill"):
        for record in records_by_kind[kind]:
            _resolve(kind, record["id"], project_root)

    found_tokens: set[str] = set()
    warnings: list[dict[str, str]] = []
    command_ids = {record["id"] for record in records_by_kind["command"]}
    for kind_records in records_by_kind.values():
        for record in kind_records:
            path = Path(record["path"])
            root = _root(record["kind"], record["origin"], project_root)
            assert root is not None
            _, text = _safe_text(path, root)
            found_tokens.update(_found_host_tokens(text))
            for reference in sorted(set(COMMAND_REFERENCE_PATTERN.findall(text))):
                command_id = reference.removeprefix("/")
                if command_id not in command_ids:
                    warnings.append(
                        {
                            "code": "unresolved_command_reference",
                            "path": str(path),
                            "token": reference,
                        }
                    )

    unknown = sorted(found_tokens - KNOWN_HOST_TOKENS)
    if unknown:
        _fail(
            "unknown_host_token",
            "add a contract row and a known-token entry",
            tokens=unknown,
        )
    return {
        "known_tokens": sorted(found_tokens),
        "status": "ok",
        "warnings": sorted(warnings, key=lambda item: (item["path"], item["token"])),
    }


def _parser() -> argparse.ArgumentParser:
    parser = RouterArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)

    inventory = actions.add_parser("inventory", help="list canonical files")
    inventory.add_argument("--kind", required=True)
    inventory.add_argument("--project-root")
    inventory.add_argument("--json", action="store_true")

    resolve = actions.add_parser("resolve", help="resolve one canonical file")
    resolve.add_argument("kind")
    resolve.add_argument("name")
    resolve.add_argument("--project-root")
    resolve.add_argument("--json", action="store_true")

    lint = actions.add_parser("lint", help="validate the canonical corpus")
    lint.add_argument("--project-root")
    lint.add_argument("--json", action="store_true")
    return parser


def _error_payload(exc: RouterError) -> dict[str, object]:
    return {"error": {"code": exc.code, "message": exc.message, **exc.details}}


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        project_root = _project_root(getattr(args, "project_root", None))
        if args.action == "inventory":
            result = _inventory(args.kind, project_root)
        elif args.action == "resolve":
            result = _resolve(args.kind, args.name, project_root)
        elif args.action == "lint":
            result = _lint(project_root)
        else:
            _fail("usage_error", f"unsupported action: {args.action}")
    except RouterError as exc:
        print(json.dumps(_error_payload(exc), sort_keys=True), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
