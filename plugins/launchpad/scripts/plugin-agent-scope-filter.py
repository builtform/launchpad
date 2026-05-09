"""v2.1 Phase 6 -- Agent scope filter.

Loads + caches `plugins/launchpad/agents/**/*.md` frontmatter, exposes
`filter_agents_by_stacks(agent_names, stacks) -> list[str]` for use by
`/lp-review` Step 3 and `/lp-harden-plan` Step 3 dispatch.

Design (cycle-3 strip-back; cycle-4 LOCKED v5):
  * Plugin-tree only (no project-local `.claude/agents/**` walk; deferred
    to v2.2 BL alongside project-local CODEOWNERS governance).
  * Module-level `STACK_SCOPE_REGEX` (cycle-3 perf P1-2).
  * `lru_cache(maxsize=None)` on `_load_agent_index`. Returns
    `MappingProxyType` (immutable view; cycle-2 security).
  * `_safe_candidate` symlink rejection mirrors `plugin-stack-detector.py:194-208`.
  * Bounded `stack:[a-z_]{1,32}` regex (cycle-3 security P1-NEW-A: ReDoS bound).
  * `MAX_AGENT_FRONTMATTER_BYTES = 64_000` defense-in-depth post-CODEOWNERS-bypass.
  * `EmptyFilterResultError` v2.1 trigger path: only fires when ALL input
    names are missing from the index (no stack:<id> agents in v2.1 per
    cycle-3 axis-mismatch fix). Forward-compat for v2.2 language-specific
    reviewers — do NOT remove as apparent dead code.
  * Missing-name UX: WARN + drop (cycle-3 spec-flow P1-2). Caller reads
    `last_dropped_names()` for partial-drop banner emission.

Imported via `importlib.util.spec_from_file_location` from tests +
orchestrators (hyphenated filename mirrors `plugin-config-loader.py` etc.).

NO disk cache (cycle-1 simplicity dropped). NO scope_filter enum / min-floor /
bypass env (cycle-2 simplicity dropped). NO schema_version field (cycle-3
simplicity P1-S2 dropped).
"""

from __future__ import annotations

import functools
import logging
import re
import sys
import threading
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType

import yaml

try:
    from yaml import CSafeLoader as _SafeLoader  # type: ignore
except ImportError:  # pragma: no cover -- libyaml unavailable on host
    from yaml import SafeLoader as _SafeLoader  # type: ignore

# ---------------------------------------------------------------------------
# Module-level constants (cycle-3 perf P1-2)
# ---------------------------------------------------------------------------

STACK_SCOPE_REGEX = re.compile(
    r"^(core_pipeline|stack:any|stack:[a-z_]{1,32}|design_quality|skill_quality)$"
)

MAX_AGENT_FRONTMATTER_BYTES = 64_000

_LOGGER = logging.getLogger("plugin_agent_scope_filter")

_PLUGIN_AGENTS_ROOT = (Path(__file__).resolve().parent.parent / "agents").resolve()

_AGENT_SUBDIRS: tuple[str, ...] = (
    "research",
    "review",
    "resolve",
    "design",
    "skills",
    "document-review",
)

# Last-call accessors for the orchestrator banner (Slice E partial-drop).
_lock = threading.Lock()
_last_dropped: list[str] = []


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EmptyFilterResultError(RuntimeError):
    """Raised when filter_agents_by_stacks() empties a non-empty input.

    v2.1 trigger path: ALL input agent names are missing from the agent
    index (e.g., agents.yml typo for every name). Forward-compat for v2.2
    when language-specific reviewers ship with stack:<id> classification.
    Caller catches and emits the FALLBACK banner per §3.3.
    """


class FrontmatterTooLargeError(ValueError):
    """Frontmatter window exceeds MAX_AGENT_FRONTMATTER_BYTES cap."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_candidate(candidate: Path, root_real: Path) -> Path | None:
    """Reject symlinks, non-files, and out-of-root resolved paths.

    Mirrors `plugin-stack-detector.py:194-208`. Hostile agents tree could
    smuggle frontmatter via `lp-evil.md -> /etc/secret-config` otherwise.
    """
    try:
        if candidate.is_symlink():
            return None
        if not candidate.is_file():
            return None
        real = candidate.resolve(strict=True)
        if not real.is_relative_to(root_real):
            return None
        return candidate
    except (OSError, ValueError):
        return None


def _read_frontmatter_bytes(path: Path) -> bytes:
    """Read up to MAX_AGENT_FRONTMATTER_BYTES + 1 bytes; raise if cap exceeded."""
    with path.open("rb") as fh:
        raw = fh.read(MAX_AGENT_FRONTMATTER_BYTES + 1)
    if len(raw) > MAX_AGENT_FRONTMATTER_BYTES:
        raise FrontmatterTooLargeError(
            f"{path}: frontmatter window exceeds {MAX_AGENT_FRONTMATTER_BYTES} bytes"
        )
    return raw


def _extract_frontmatter_dict(path: Path) -> dict | None:
    """Parse the leading `---\\n...\\n---\\n` window via yaml.safe_load + CSafeLoader.

    Returns None when the file has no frontmatter window (treated as
    `stack:any` + DEBUG by the caller, per DA1 default).
    """
    raw = _read_frontmatter_bytes(path)
    text = raw.decode("utf-8", errors="strict")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        end = text.find("\n---", 4)
        if end == -1:
            return None
    body = text[4:end]
    parsed = yaml.load(body, Loader=_SafeLoader)  # noqa: S506 -- CSafeLoader/SafeLoader only  # nosec B506 -- _SafeLoader binding indirection (CSafeLoader|SafeLoader); bandit doesn't trace import alias (cf. BL-<TBD> | HANDSHAKE §2 | plan §6 alternatives table).
    if not isinstance(parsed, dict):
        return None
    return parsed


@functools.cache
def _load_agent_index() -> Mapping[str, dict[str, str]]:
    """Walk plugin agent tree (depth-1 subdirs only) + return immutable index.

    Returned shape: `{agent_name: {"path": str, "stack_scope": str}}`.

    Default for missing/invalid frontmatter: `stack:any` + DEBUG log
    (DA1 default; forward-compat with future frontmatter additions).

    Symlinks rejected via `_safe_candidate`. Out-of-bounds frontmatter
    raises FrontmatterTooLargeError up to the caller.
    """
    index: dict[str, dict[str, str]] = {}
    root_real = _PLUGIN_AGENTS_ROOT
    if not root_real.is_dir():
        # No plugin tree visible — return empty index. Filter callers
        # will WARN+drop every name and raise EmptyFilterResultError.
        return MappingProxyType({})
    for sub in _AGENT_SUBDIRS:
        sub_dir = root_real / sub
        if not sub_dir.is_dir() or sub_dir.is_symlink():
            continue
        for candidate in sorted(sub_dir.iterdir(), key=lambda p: p.name):
            if not candidate.name.endswith(".md"):
                continue
            safe = _safe_candidate(candidate, root_real)
            if safe is None:
                _LOGGER.debug("rejected agent file (symlink/realpath): %s", candidate)
                continue
            try:
                fm = _extract_frontmatter_dict(safe)
            except FrontmatterTooLargeError as exc:
                _LOGGER.warning("agent frontmatter exceeds cap; skipping: %s", exc)
                continue
            name = (fm or {}).get("name") or safe.stem
            scope = (fm or {}).get("stack_scope")
            if not isinstance(scope, str) or not STACK_SCOPE_REGEX.fullmatch(scope):
                _LOGGER.debug(
                    "agent %s has missing/invalid stack_scope; defaulting to stack:any",
                    name,
                )
                scope = "stack:any"
            index[str(name)] = {"path": str(safe), "stack_scope": scope}
    return MappingProxyType(index)


def _active_stack_enum() -> frozenset[str]:
    """Lazy import of STACK_ID_ACTIVE_ENUM so module import does not pull in
    the Jinja renderer. Fetched on every filter call (cheap dict lookup
    amortizes across the lru_cached enum frozenset)."""
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from plugin_default_generators._renderer_base import STACK_ID_ACTIVE_ENUM

    return STACK_ID_ACTIVE_ENUM


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def filter_agents_by_stacks(
    agent_names: Iterable[str], stacks: Iterable[str]
) -> list[str]:
    """Filter agent names by stack_scope classification.

    Inclusion rules (DA2):
      * `core_pipeline`: always include
      * `stack:any`: always include
      * `stack:<id>`: include iff `<id>` in `stacks`
      * `design_quality` + `skill_quality`: NEVER include (callers pre-filter)

    Missing-name handling: WARN + drop (cycle-3 spec-flow P1-2). Caller
    reads `last_dropped_names()` for partial-drop banner.

    Empty input list returns []. Empty stacks is allowed (returns only
    core_pipeline + stack:any agents).

    Raises:
      ValueError: stack id not in STACK_ID_ACTIVE_ENUM.
      EmptyFilterResultError: empty result + non-empty input. Forward-compat
        v2.1 trigger path is ALL names missing.
    """
    names = list(agent_names)
    stack_list = list(stacks)
    if not names:
        return []
    active_enum = _active_stack_enum()
    bogus = [s for s in stack_list if s not in active_enum]
    if bogus:
        raise ValueError(
            f"unknown stack id(s) {bogus!r}; expected one of {sorted(active_enum)}"
        )
    index = _load_agent_index()
    survivors: list[str] = []
    dropped: list[str] = []
    stacks_set = set(stack_list)
    for name in names:
        meta = index.get(name)
        if meta is None:
            _LOGGER.warning(
                "stack-filter: dropping unknown agent name %r (not in plugin index)",
                name,
            )
            dropped.append(name)
            continue
        scope = meta["stack_scope"]
        if scope == "core_pipeline":
            survivors.append(name)
        elif scope == "stack:any":
            survivors.append(name)
        elif scope.startswith("stack:") and scope != "stack:any":
            stack_id = scope.split(":", 1)[1]
            if stack_id in stacks_set:
                survivors.append(name)
        # design_quality + skill_quality NEVER survive — callers pre-filter.
    with _lock:
        _last_dropped.clear()
        _last_dropped.extend(dropped)
    survivors_sorted = sorted(survivors)
    if not survivors_sorted:
        raise EmptyFilterResultError(
            f"filter dropped every agent in input {names!r} for stacks "
            f"{stack_list!r}; v2.1 trigger path = all names missing from index"
        )
    return survivors_sorted


def last_dropped_names() -> list[str]:
    """Return names dropped in the most recent successful filter call.

    Used by `/lp-review` + `/lp-harden-plan` Step 3 to emit the
    PARTIAL-DROP banner per §3.3 (cycle-4 spec-flow P2-B).
    """
    with _lock:
        return list(_last_dropped)


__all__ = [
    "STACK_SCOPE_REGEX",
    "MAX_AGENT_FRONTMATTER_BYTES",
    "EmptyFilterResultError",
    "FrontmatterTooLargeError",
    "filter_agents_by_stacks",
    "last_dropped_names",
    "_load_agent_index",
]
