"""Secret scanner -- post-render pass across every canonical doc before write.

Complements manifest_stripper.py: stripping removes known-secret-bearing
FIELDS at parse time; scanning catches remaining PATTERNS in the rendered
output (e.g. a user-written README excerpt that happens to contain an AWS
key).

Patterns come from `.launchpad/secret-patterns.txt` (one regex per line,
blank lines and lines starting with `#` ignored). When that file is absent,
the plugin-shipped `BUNDLED_DEFAULT_PATTERNS` constant is the fallback so
the gate never silently degrades to "no patterns to apply" on a fresh
greenfield first render (Phase 8.5 plan section 3.10 DA5 lock).

Compiled patterns are cached at module level (Phase 8.5 plan section 3.8
DA3 lock): `_load_patterns_cached(file, mtime_ns)` re-compiles only when
the patterns file's mtime changes. Cumulative gate cost on a 30-file
scaffold stays under 300ms (asserted by
test_phase8_5_decommission.test_write_batch_perf_under_300ms_30file_scaffold).

Behavior:
  - Return list of matches (pattern, line number, redacted preview)
  - Empty list = safe to write
  - Non-empty list = caller decides: refuse, warn-and-prompt, or allow with confirmation
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path

# Conservative built-in patterns. Lower risk of false negatives than a
# completely empty default. Projects can still override via secret-patterns.txt.
#
# Phase 8.5 plan section 3.10: this constant is the fallback the
# render_batch gate uses when `.launchpad/secret-patterns.txt` is absent
# (e.g., fresh greenfield first render before infrastructure overlay
# materializes the user-tunable file). CODEOWNERS-protected so a malicious
# PR cannot silently empty it.
_BUILTIN_PATTERNS = (
    # Generic env-var form with obvious secret key
    r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-+/=]{16,}[\"']?",
    # AWS access keys
    r"AKIA[0-9A-Z]{16}",
    r"aws_secret_access_key\s*=\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?",
    # GitHub tokens
    r"gh[pousr]_[A-Za-z0-9]{36,}",
    # Stripe
    r"sk_(live|test)_[A-Za-z0-9]{24,}",
    r"rk_(live|test)_[A-Za-z0-9]{24,}",
    r"whsec_[A-Za-z0-9]{24,}",
    # Anthropic / OpenAI
    r"sk-ant-[A-Za-z0-9_\-]{30,}",
    r"sk-(proj-)?[A-Za-z0-9]{40,}",
    # Slack
    r"xox[pbosa]-[A-Za-z0-9\-]{10,}",
    # DB connection strings with embedded credentials
    r"(postgres|mysql|mongodb)://[^/\s:@]+:[^/\s@]+@",
)

BUNDLED_DEFAULT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p) for p in _BUILTIN_PATTERNS
)


class SecretScannerNotConfiguredError(RuntimeError):
    """Raised when both `.launchpad/secret-patterns.txt` is absent AND
    `BUNDLED_DEFAULT_PATTERNS` is empty. Phase 8.5 plan section 3.10
    fail-closed contract: gate refuses to run rather than silently
    degrading to "no patterns to apply"."""


@dataclass
class SecretMatch:
    pattern: str
    line_no: int
    preview: str  # first 80 chars of the matched line, with the match itself replaced by <REDACTED>


@functools.lru_cache(maxsize=8)
def _load_patterns_cached(
    patterns_file: Path | None,
    mtime_ns: int,
) -> tuple[re.Pattern[str], ...]:
    """Compile patterns once per (file, mtime). Cache invalidates on file
    mtime change so a user edit to `.launchpad/secret-patterns.txt` takes
    effect on the next render-batch invocation without process restart.
    """
    if patterns_file is None or not patterns_file.is_file():
        compiled = BUNDLED_DEFAULT_PATTERNS
    else:
        text = patterns_file.read_text(encoding="utf-8")
        user_compiled: list[re.Pattern[str]] = []
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                user_compiled.append(re.compile(stripped))
            except re.error:
                # Skip malformed user patterns rather than fail the whole
                # scan; secret-patterns.txt is user-editable.
                continue
        compiled = BUNDLED_DEFAULT_PATTERNS + tuple(user_compiled)

    if not compiled:
        raise SecretScannerNotConfiguredError(
            "secret scanner has no patterns to apply "
            "(.launchpad/secret-patterns.txt absent AND "
            "BUNDLED_DEFAULT_PATTERNS empty). "
            "Re-install plugin: claude /plugin install launchpad."
        )
    return compiled


def load_patterns(
    patterns_file: Path | None = None,
) -> list[re.Pattern[str]]:
    """Load secret patterns. Returns the bundled defaults when
    `patterns_file` is absent or None.

    The returned list is cache-backed; identical invocations across the
    process lifetime return the same compiled-pattern objects without
    re-compiling. Cache key includes the patterns file's mtime so a user
    edit invalidates the cache automatically.
    """
    if patterns_file is None or not patterns_file.is_file():
        return list(_load_patterns_cached(None, 0))
    mtime_ns = patterns_file.stat().st_mtime_ns
    return list(_load_patterns_cached(patterns_file, mtime_ns))


def scan(
    content: str,
    patterns: list[re.Pattern[str]] | None = None,
    patterns_file: Path | None = None,
    source: str | None = None,
) -> list[SecretMatch]:
    """Scan rendered content for secret patterns. Returns list of matches;
    empty list means clean.

    Accepts either a pre-compiled pattern list or a patterns file; if both
    provided, the pre-compiled list wins. `source` is an optional path
    label used by callers for finding-grouping.
    """
    del source  # accepted for caller-friendly signatures; not used in match shape
    if patterns is None:
        patterns = load_patterns(patterns_file)

    matches: list[SecretMatch] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        for pat in patterns:
            if pat.search(line):
                # Build a redacted preview: replace every match of the pattern
                # in the line with the literal string "<REDACTED>", then
                # truncate to 80 chars. The previous form (line.strip()[:80])
                # leaked the secret's first 80 chars when the secret started
                # at column 0 of the line.
                redacted = pat.sub("<REDACTED>", line)
                preview = redacted.strip()[:80]
                matches.append(
                    SecretMatch(pattern=pat.pattern, line_no=line_no, preview=preview)
                )
                break  # one hit per line is enough to flag it
    return matches


def format_matches(matches: list[SecretMatch]) -> str:
    """Human-readable summary of matches for user prompts. Deliberately
    doesn't include the actual secret values."""
    if not matches:
        return "(no secret patterns matched)"
    lines = [f"Found {len(matches)} possible secret(s):"]
    for m in matches:
        lines.append(
            f"  line {m.line_no}: {m.preview!r} (matched pattern /{m.pattern[:40]}.../)"
        )
    return "\n".join(lines)


__all__ = [
    "BUNDLED_DEFAULT_PATTERNS",
    "SecretMatch",
    "SecretScannerNotConfiguredError",
    "format_matches",
    "load_patterns",
    "scan",
]
