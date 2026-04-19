#!/usr/bin/env python3
"""
Rewrite agent names in agents.yml to be lp-prefixed for plugin seeding.

Input:  path to .launchpad/agents.yml (source — unprefixed names)
Output: stdout (prefixed, schema_version stamped)

Only list items under known agent-list keys are rewritten.
protected_branches is preserved verbatim (branch names, not agents).
Comments and already-prefixed names pass through unchanged.
"""

import re
import sys
from pathlib import Path

PREFIX = "lp-"

AGENT_LIST_KEYS = {
    "review_agents",
    "review_db_agents",
    "review_design_agents",
    "review_copy_agents",
    "harden_plan_agents",
    "harden_plan_conditional_agents",
    "harden_document_agents",
}

KEY_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:")
LIST_ITEM_RE = re.compile(r"^(\s*-\s+)([a-z][a-z0-9-]*)(\s*(?:#.*)?)$")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: plugin-rewrite-agents-yml.py <path-to-agents.yml>", file=sys.stderr)
        return 2

    src = Path(sys.argv[1])
    print("# schema_version: 1")

    in_agent_list = False
    for line in src.read_text().splitlines():
        key_match = KEY_RE.match(line)
        if key_match:
            in_agent_list = key_match.group(1) in AGENT_LIST_KEYS
            print(line)
            continue

        if in_agent_list:
            item_match = LIST_ITEM_RE.match(line)
            if item_match:
                dash, name, trailer = item_match.groups()
                if not name.startswith(PREFIX):
                    name = PREFIX + name
                print(f"{dash}{name}{trailer}")
                continue

        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
