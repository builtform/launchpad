"""Merge LaunchPad's autonomous-mode settings template into ``.claude/settings.json``.

BL-372: closes the per-Skill-invocation permission-prompt gap that breaks
``/lp-build``'s autonomous-execution contract. When the user opts into
autonomous mode (``.launchpad/autonomous-ack.md`` exists), ``/lp-bootstrap``
proposes merging this module's template into the user's
``.claude/settings.json`` so the ``/lp-build`` -> ``/lp-inf`` -> ``/lp-review``
-> ``/lp-resolve-todo-parallel`` -> ``/lp-test-browser`` -> ``/lp-ship``
chain runs without 5-7 per-run permission prompts.

The brief at BL-372 originally suggested
``plugin_stack_adapters/claude_settings_merger.py``; the module lives
inside ``lp_bootstrap/`` instead for the same reason the BL-370 proposer
moved here: bootstrap-flow logic, covered by the ``/lp_bootstrap/``
directory CODEOWNERS rule, sibling to the other bootstrap-tier writers
allowlisted for ``atomic_write_replace``.

The brief also assumed a per-skill ``Skill(launchpad:lp-inf)`` allowlist
syntax. The Context7-fetched ``settings.json`` docs only show TOOL-level
entries (``"Skill"``, ``"Bash"``, ``"Edit"``, ``"WebFetch"``, ...) plus
the scoped ``"Bash(git:*)"`` form. The shipped template uses the tool-
level shape; per-skill granularity is not currently supported by Claude
Code's permission model.

Merge contract
==============

The merger preserves user customizations:

* Dict values recurse; never replace a user dict with the template's.
* ``permissions.allow`` / ``permissions.ask`` / ``permissions.deny`` lists
  union per-entry, but the merger does NOT broaden a tightened user rule.
  If the user already pinned ``"Bash(git:*)"``, the merger does not add
  bare ``"Bash"`` (which would broaden permissions).
* Other lists union by exact match.
* Existing scalar values win; the merger never overwrites them.

CLI
===

``python -m lp_bootstrap.claude_settings_merger --json [--cwd <p>]``
    Prints structured JSON for ``/lp-bootstrap`` to consume
    (ack_present, settings_present, missing_entries).

``python -m lp_bootstrap.claude_settings_merger --apply [--cwd <p>]``
    Performs the merge (atomic-replace) and prints the target path.
    Refuses when ``.launchpad/autonomous-ack.md`` is absent.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Sibling-script imports.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import atomic_write_replace  # noqa: E402

# ``plugins/launchpad/templates/`` sits at ``<plugin_root>/templates/``;
# resolve relative to this module so the file is picked up regardless of
# the caller's cwd.
_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "templates"
    / "claude-settings-autonomous.json"
)

_AUTONOMOUS_ACK_PATH = ".launchpad/autonomous-ack.md"
_CLAUDE_SETTINGS_PATH = ".claude/settings.json"
_SKIPPED_MARKER_PATH = ".launchpad/autonomous-settings-merge.skipped"

# Permission-allowlist keys that share the "do-not-broaden" rule.
_PERMISSION_KEYS = frozenset({"allow", "ask", "deny"})

# Match a tool entry's bare tool name (everything before "(" or end-of-string).
_TOOL_PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\b")


def template_path() -> Path:
    return _TEMPLATE_PATH


def autonomous_ack_path(repo_root: Path) -> Path:
    return repo_root / _AUTONOMOUS_ACK_PATH


def claude_settings_path(repo_root: Path) -> Path:
    return repo_root / _CLAUDE_SETTINGS_PATH


def skipped_marker_path(repo_root: Path) -> Path:
    return repo_root / _SKIPPED_MARKER_PATH


def autonomous_ack_present(repo_root: Path) -> bool:
    return autonomous_ack_path(repo_root).is_file()


def skipped_marker_present(repo_root: Path) -> bool:
    return skipped_marker_path(repo_root).is_file()


def claude_settings_present(repo_root: Path) -> bool:
    return claude_settings_path(repo_root).is_file()


def load_template() -> dict[str, Any]:
    """Read and parse the bundled autonomous-mode template."""
    try:
        return json.loads(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"autonomous-mode template missing at {_TEMPLATE_PATH!s}; "
            "the LaunchPad install is corrupt."
        ) from exc


def _read_existing(repo_root: Path) -> dict[str, Any]:
    path = claude_settings_path(repo_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"existing {path} is not valid JSON; resolve manually before re-running"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(
            f"existing {path} root must be a JSON object; got {type(data).__name__}"
        )
    return data


def _bare_tool_name(entry: str) -> str | None:
    match = _TOOL_PREFIX_RE.match(entry)
    return match.group(1) if match else None


def _merge_permission_list(
    existing: list[Any],
    incoming: list[Any],
    *,
    sibling_lists: dict[str, list[Any]] | None = None,
) -> tuple[list[Any], list[str]]:
    """Union ``incoming`` into ``existing`` without broadening user rules.

    Returns the merged list AND the entries actually added (in template
    order) so the proposer can show the user exactly what will change.

    Two suppression rules apply (BL-372 v2, PR #76 review):

    1. **Do-not-broaden** (original v1): if the user already pinned a
       scoped form like ``Bash(git:*)``, do NOT add the bare ``Bash``
       from the template (which would broaden permissions).
    2. **Cross-list contradiction guard** (Codex P2 PR #76): if the
       user explicitly listed an entry under a sibling permission key
       (e.g. ``deny: ["WebFetch"]``), do NOT add the same entry under
       ``allow`` even if the template ships it. Adding ``WebFetch`` to
       ``allow`` while the user has it in ``deny`` produces a
       contradictory policy whose resolution depends on Claude Code's
       precedence semantics, which the merger should NEVER force.
       Matching is by bare-tool prefix (``WebFetch(read:*)`` in ``deny``
       suppresses bare ``WebFetch`` in ``allow``) so scoped sibling
       rules still win.
    """
    out = list(existing)
    existing_strs = [e for e in out if isinstance(e, str)]
    pinned_tools = {
        _bare_tool_name(e)
        for e in existing_strs
        # Only the comprehension's filter is needed; the
        # ``_bare_tool_name`` helper never returns ``None`` for a string
        # starting with a tool-name char (the v1 ``pinned_tools.discard(None)``
        # call was unreachable per simplicity-reviewer P1 PR #76).
        if "(" in e and _bare_tool_name(e) is not None
    }
    sibling_bare_names: set[str] = set()
    sibling_exact: set[str] = set()
    for entries in (sibling_lists or {}).values():
        for entry in entries:
            if not isinstance(entry, str):
                continue
            sibling_exact.add(entry)
            bare = _bare_tool_name(entry)
            if bare is not None:
                sibling_bare_names.add(bare)
    added: list[str] = []
    for entry in incoming:
        if not isinstance(entry, str):
            if entry not in out:
                out.append(entry)
            continue
        if entry in out:
            continue
        bare = _bare_tool_name(entry)
        # Rule 1: refuse to add a bare tool entry when the user already
        # has a tightened form for the same tool.
        if "(" not in entry and bare in pinned_tools:
            continue
        # Rule 2: refuse to add an entry that is contradicted by a
        # sibling permission key (typical case: template wants
        # ``allow: ["WebFetch"]`` but the user has ``deny: ["WebFetch"]``
        # or ``deny: ["WebFetch(read:*)"]``).
        if entry in sibling_exact:
            continue
        if bare is not None and bare in sibling_bare_names:
            continue
        out.append(entry)
        added.append(entry)
    return out, added


def _merge_dicts(
    existing: dict[str, Any], template: dict[str, Any], *, path: str = ""
) -> tuple[dict[str, Any], list[str]]:
    """Recursive deep-merge; returns merged dict + dotted-path "added" entries."""
    merged: dict[str, Any] = copy.deepcopy(existing)
    additions: list[str] = []
    for key, tmpl_val in template.items():
        sub_path = f"{path}.{key}" if path else key

        # BL-372 v2 (PR #76 review): the permission-list contract is the
        # same whether the user already has the list or the template is
        # introducing it. Both cases need the cross-list contradiction
        # guard so a template entry the user has denied is not silently
        # added, AND both cases must use exact-match `path == "permissions"`
        # so future nested keys (e.g. `hooks.permissions.allow`) do not
        # trigger this rule. Collapsed into a single branch in cycle 2
        # (simplicity-reviewer P2 PR #76) so the contract is expressed
        # once, not twice.
        if (
            key in _PERMISSION_KEYS
            and path == "permissions"
            and isinstance(tmpl_val, list)
        ):
            cur_value = merged.get(key)
            cur_list: list[Any] = list(cur_value) if isinstance(cur_value, list) else []
            sibling_lists = {
                other_key: merged[other_key]
                for other_key in _PERMISSION_KEYS
                if other_key != key
                and other_key in merged
                and isinstance(merged[other_key], list)
            }
            merged_list, added_entries = _merge_permission_list(
                cur_list, tmpl_val, sibling_lists=sibling_lists
            )
            merged[key] = merged_list
            additions.extend(f"{sub_path}[{entry!r}]" for entry in added_entries)
            continue

        if key not in merged:
            merged[key] = copy.deepcopy(tmpl_val)
            additions.append(sub_path)
            continue
        cur = merged[key]
        if isinstance(cur, dict) and isinstance(tmpl_val, dict):
            sub_merged, sub_added = _merge_dicts(cur, tmpl_val, path=sub_path)
            merged[key] = sub_merged
            additions.extend(sub_added)
            continue
        if isinstance(cur, list) and isinstance(tmpl_val, list):
            # Generic list-merge by exact-match union (non-permission lists).
            extras: list[Any] = [item for item in tmpl_val if item not in cur]
            if extras:
                merged[key] = [*cur, *extras]
                additions.extend(f"{sub_path}[{item!r}]" for item in extras)
            continue
        # Scalar collision: existing wins. No change, no addition.
    return merged, additions


def plan_merge(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Return ``(merged_dict, existing_dict, additions)`` for the proposer.

    Performs the merge in-memory without touching disk so the slash
    command can show the user exactly what will change before they
    confirm.
    """
    template = load_template()
    existing = _read_existing(repo_root)
    merged, additions = _merge_dicts(existing, template)
    return merged, existing, additions


def apply_merge(repo_root: Path) -> Path:
    """Merge the template into ``.claude/settings.json`` atomically.

    Refuses when ``.launchpad/autonomous-ack.md`` is absent so the
    autonomous-mode opt-in is never bypassed implicitly.
    """
    if not autonomous_ack_present(repo_root):
        raise PermissionError(
            f"refusing to write {claude_settings_path(repo_root)}: "
            f"{_AUTONOMOUS_ACK_PATH} is not present. Create the "
            "autonomous-ack file (see /lp-bootstrap autonomous-mode "
            "section) before merging the autonomous-mode permission "
            "template."
        )
    merged, _existing, _added = plan_merge(repo_root)
    target = claude_settings_path(repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(merged, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_replace(target, body, trusted_root=repo_root)
    return target


def write_skipped_marker(repo_root: Path) -> Path:
    """Write the permanent opt-out sentinel (BL-372 v2, Greptile P2).

    Mirrors BL-370's ``preflight.config.skipped`` pattern so a user who
    declines the settings merge can stop the re-prompt loop on future
    ``/lp-bootstrap`` runs without removing ``autonomous-ack.md``
    (which would also disable autonomous-mode entirely). Removing the
    sentinel re-opens the prompt.
    """
    target = skipped_marker_path(repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (
        b"# User declined the LaunchPad autonomous-mode settings merge at\n"
        b"# /lp-bootstrap. Delete this file to be re-prompted on the next\n"
        b"# /lp-bootstrap run.\n"
    )
    atomic_write_replace(target, body, trusted_root=repo_root)
    return target


def summarize(repo_root: Path) -> dict[str, Any]:
    """Structured-output entry point for ``/lp-bootstrap`` to consume."""
    ack = autonomous_ack_present(repo_root)
    has_settings = claude_settings_present(repo_root)
    skipped = skipped_marker_present(repo_root)
    summary: dict[str, Any] = {
        "ack_present": ack,
        "settings_present": has_settings,
        "skipped_marker_present": skipped,
        "template_path": str(_TEMPLATE_PATH),
        "settings_path": str(claude_settings_path(repo_root)),
    }
    if not ack or skipped:
        summary["additions"] = []
        summary["already_satisfied"] = False
        return summary
    try:
        _merged, _existing, additions = plan_merge(repo_root)
    except (ValueError, json.JSONDecodeError) as exc:
        summary["error"] = str(exc)
        summary["additions"] = []
        summary["already_satisfied"] = False
        return summary
    summary["additions"] = additions
    summary["already_satisfied"] = len(additions) == 0
    return summary


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lp_bootstrap.claude_settings_merger",
        description=(
            "Merge LaunchPad's autonomous-mode permission template into "
            "`.claude/settings.json`. Invoked by /lp-bootstrap; see BL-372."
        ),
    )
    # BL-372 v2 (PR #76 review, pattern-finder P2): use the same
    # `--repo-root` + `LP_REPO_ROOT` env-var fallback as the rest of the
    # LaunchPad CLI surface. `--cwd` remains as a hidden compatibility
    # alias for out-of-tree callers.
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(os.environ.get("LP_REPO_ROOT", os.getcwd())),
        help=("Project root (default: $LP_REPO_ROOT or current working directory)."),
    )
    p.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON summary of the proposed merge.",
    )
    group.add_argument(
        "--apply",
        action="store_true",
        help="Merge the template into `.claude/settings.json` atomically.",
    )
    group.add_argument(
        "--write-skipped",
        action="store_true",
        help=(
            "Write the permanent opt-out marker so future bootstrap "
            "runs do not re-prompt. Mirrors BL-370's "
            "`preflight.config.skipped` pattern."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    raw_root = args.cwd if args.cwd is not None else args.repo_root
    repo_root: Path = raw_root.resolve()

    if args.apply:
        try:
            target = apply_merge(repo_root)
        except PermissionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 65
        except (ValueError, FileNotFoundError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 65
        print(str(target))
        return 0

    if args.write_skipped:
        target = write_skipped_marker(repo_root)
        print(str(target))
        return 0

    summary = summarize(repo_root)
    if args.json:
        json.dump(summary, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    if not summary["ack_present"]:
        print(f"autonomous-ack absent: {_AUTONOMOUS_ACK_PATH} is not present.")
        return 0
    additions = summary.get("additions") or []
    if not additions:
        print("Claude Code settings already cover the autonomous-mode template.")
        return 0
    print(f"Proposing additions to {summary['settings_path']}:")
    for entry in additions:
        print(f"  + {entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
