"""Secret scanner — post-render pass across every canonical doc before write.

Complements manifest_stripper.py: stripping removes known-secret-bearing
FIELDS at parse time; scanning catches remaining PATTERNS in the rendered
output (e.g. a user-written README excerpt that happens to contain an AWS
key).

Patterns come from `.launchpad/secret-patterns.txt` (one regex per line,
blank lines and lines starting with `#` ignored). If that file doesn't
exist, a conservative built-in set fires.

Behavior:
  - Return list of matches (pattern, line number, matched text preview)
  - Empty list = safe to write
  - Non-empty list = caller decides: refuse, warn-and-prompt, or allow with confirmation
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Conservative built-in patterns. Lower risk of false negatives than a
# completely empty default. Projects can still override via secret-patterns.txt.
_BUILTIN_PATTERNS = [
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
]


@dataclass
class SecretMatch:
    pattern: str
    line_no: int
    preview: str  # first 80 chars of the matched line (NOT the match itself — avoids logging the secret)


def load_patterns(patterns_file: Path | None = None) -> list[re.Pattern]:
    """Load secret patterns from `.launchpad/secret-patterns.txt` or fall back
    to built-ins if the file doesn't exist.
    """
    raw_patterns: list[str] = []
    if patterns_file and patterns_file.is_file():
        for line in patterns_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            raw_patterns.append(stripped)
    else:
        raw_patterns = _BUILTIN_PATTERNS

    compiled: list[re.Pattern] = []
    for p in raw_patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            # Skip malformed patterns rather than fail the whole scan —
            # secret-patterns.txt is user-editable and a bad regex shouldn't
            # break /lp-define.
            continue
    return compiled


def scan(content: str, patterns: list[re.Pattern] | None = None, patterns_file: Path | None = None) -> list[SecretMatch]:
    """Scan rendered content for secret patterns. Returns list of matches;
    empty list means clean.

    Accepts either a pre-compiled pattern list or a patterns file; if both
    provided, the pre-compiled list wins.
    """
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
                matches.append(SecretMatch(pattern=pat.pattern, line_no=line_no, preview=preview))
                break  # one hit per line is enough to flag it
    return matches


def format_matches(matches: list[SecretMatch]) -> str:
    """Human-readable summary of matches for user prompts. Deliberately
    doesn't include the actual secret values."""
    if not matches:
        return "(no secret patterns matched)"
    lines = [f"Found {len(matches)} possible secret(s):"]
    for m in matches:
        lines.append(f"  line {m.line_no}: {m.preview!r} (matched pattern /{m.pattern[:40]}.../)")
    return "\n".join(lines)
