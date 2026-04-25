#!/usr/bin/env python3
"""Regression test: scripts/setup/init-project.sh seeds .launchpad/agents.yml
with the lp- prefix on every agent name.

The /lp-review and /lp-harden-plan resolvers look up `{name}.md` directly
in ${CLAUDE_PLUGIN_ROOT}/agents/** and .claude/agents/**. The on-disk agent
files all carry the lp- prefix, so the values seeded into agents.yml MUST
also carry the prefix. A previous regression seeded unprefixed names like
'pattern-finder' here, causing freshly initialized template projects to
silently skip every default agent.

This test parses init-project.sh, locates the embedded agents.yml HEREDOC,
and asserts that every agent-name entry under review_*, harden_plan_* and
harden_document_* keys begins with 'lp-'. It also cross-checks that every
seeded name has a corresponding agent file in plugins/launchpad/agents/.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
INIT_SH = REPO_ROOT / "scripts" / "setup" / "init-project.sh"
AGENTS_DIR = REPO_ROOT / "plugins" / "launchpad" / "agents"

# Keys whose values are agent-name lists (not branch names, not [] sentinels).
AGENT_KEYS = (
    "review_agents",
    "review_db_agents",
    "review_design_agents",
    "harden_plan_agents",
    "harden_plan_conditional_agents",
    "harden_document_agents",
)

HEREDOC_RE = re.compile(r"<<'AYEOF'\n(.*?)\nAYEOF", re.DOTALL)


def extract_heredoc(text: str) -> str:
    m = HEREDOC_RE.search(text)
    if not m:
        raise AssertionError("init-project.sh does not contain the expected <<'AYEOF' heredoc")
    return m.group(1)


def parse_agents_yml(yml_text: str) -> dict[str, list[str]]:
    """Cheap YAML parser tailored to the heredoc shape (top-level keys, '- name'
    list items, line comments). Avoids a yaml import so the test can run in
    minimal environments."""
    result: dict[str, list[str]] = {}
    current_key: str | None = None
    for raw in yml_text.splitlines():
        # Strip line comments (we don't allow inline values with # to be quoted as data here).
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        m_key = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if m_key:
            current_key = m_key.group(1)
            inline = m_key.group(2).strip()
            # `key: []` style: empty list, not an agent-list-following-key.
            if inline.startswith("[") and inline.endswith("]"):
                result[current_key] = []
                current_key = None
            else:
                result[current_key] = []
            continue
        m_item = re.match(r"^\s+-\s+(\S+)\s*$", line)
        if m_item and current_key:
            result[current_key].append(m_item.group(1))
    return result


def main() -> int:
    if not INIT_SH.is_file():
        print(f"FAIL: init-project.sh not found at {INIT_SH}")
        return 1

    text = INIT_SH.read_text(encoding="utf-8")
    yml = extract_heredoc(text)
    parsed = parse_agents_yml(yml)

    errors: list[str] = []
    seen_any_agent = False

    for key in AGENT_KEYS:
        if key not in parsed:
            errors.append(f"missing key {key!r} in seeded agents.yml")
            continue
        for name in parsed[key]:
            seen_any_agent = True
            if not name.startswith("lp-"):
                errors.append(f"{key}: agent {name!r} missing lp- prefix")
                continue
            agent_file = list(AGENTS_DIR.rglob(f"{name}.md"))
            if not agent_file:
                errors.append(
                    f"{key}: agent {name!r} has no matching file in plugins/launchpad/agents/"
                )

    if not seen_any_agent:
        errors.append("no agent names parsed from the seeded heredoc — parser regression?")

    if errors:
        print("FAIL: init agents.yml seed")
        for e in errors:
            print(f"  - {e}")
        return 1

    total = sum(len(parsed[k]) for k in AGENT_KEYS if k in parsed)
    print(f"PASS: init agents.yml seed ({total} agent names, all lp- prefixed and resolvable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
