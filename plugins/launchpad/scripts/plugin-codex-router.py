"""Resolve LaunchPad canonical files for the Codex router skill."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import NoReturn

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_ROOT = PLUGIN_ROOT / "commands"
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class RouterError(Exception):
    """Expected router failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


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


def _frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _fail("invalid_utf8", f"canonical file is not valid UTF-8: {path}")
    except OSError as exc:
        _fail("read_failed", f"could not read canonical file: {path}", reason=str(exc))

    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}

    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return metadata
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = _parse_scalar(value)

    _fail("malformed_frontmatter", f"canonical file has unclosed frontmatter: {path}")


def _command_paths() -> list[Path]:
    if not COMMANDS_ROOT.is_dir():
        _fail(
            "missing_root", f"canonical command directory is missing: {COMMANDS_ROOT}"
        )
    return sorted(COMMANDS_ROOT.glob("*.md"), key=lambda path: path.name)


def _record(path: Path) -> dict[str, str]:
    metadata = _frontmatter(path)
    command_id = metadata.get("name", path.stem)
    return {
        "description": metadata.get("description", ""),
        "id": command_id,
        "kind": "command",
        "origin": "built_in",
        "path": str(path.resolve()),
    }


def _inventory(kind: str) -> dict[str, object]:
    if kind != "command":
        _fail("unsupported_kind", f"inventory kind is not available yet: {kind}")
    return {"items": [_record(path) for path in _command_paths()], "kind": kind}


def _canonical_command_id(name: str) -> str:
    if not NAME_PATTERN.fullmatch(name):
        _fail(
            "invalid_name",
            "command name must contain only lowercase letters, digits, and hyphens",
            name=name,
        )
    return name if name.startswith("lp-") else f"lp-{name}"


def _resolve_command(name: str) -> dict[str, str]:
    command_id = _canonical_command_id(name)
    path = COMMANDS_ROOT / f"{command_id}.md"
    root_real = COMMANDS_ROOT.resolve()

    if path.is_symlink() or not path.is_file():
        available = [candidate.stem for candidate in _command_paths()]
        suggestions = difflib.get_close_matches(command_id, available, n=3, cutoff=0.6)
        _fail(
            "not_found",
            f"canonical command does not exist: {command_id}",
            id=command_id,
            suggestions=suggestions,
        )

    path_real = path.resolve()
    if not path_real.is_relative_to(root_real):
        _fail(
            "outside_root", f"canonical command resolves outside its root: {command_id}"
        )

    record = _record(path_real)
    if record["id"] != command_id:
        _fail(
            "id_mismatch",
            f"canonical command id does not match its filename: {command_id}",
            frontmatter_id=record["id"],
        )
    return record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)

    inventory = actions.add_parser("inventory", help="list canonical files")
    inventory.add_argument("--kind", required=True)
    inventory.add_argument("--json", action="store_true")

    resolve = actions.add_parser("resolve", help="resolve one canonical file")
    resolve.add_argument("kind")
    resolve.add_argument("name")
    resolve.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "inventory":
            result = _inventory(args.kind)
        elif args.action == "resolve" and args.kind == "command":
            result = _resolve_command(args.name)
        else:
            _fail("unsupported_kind", f"resolve kind is not available yet: {args.kind}")
    except RouterError as exc:
        error = {"code": exc.code, "message": exc.message, **exc.details}
        print(json.dumps({"error": error}, sort_keys=True), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
