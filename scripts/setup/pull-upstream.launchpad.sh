#!/usr/bin/env bash
# scripts/setup/pull-upstream.launchpad.sh (signpost stub; tracked for v2.1.1 deletion in v2.2 BL)
echo "pull-upstream.launchpad.sh removed in v2.1. Use: claude /plugin update launchpad" >&2
echo "If you need v0/v1 behavior, pin to v2.0.x: git checkout v2.0.x" >&2
exit 64  # EX_USAGE: distinguishable from generic exit 1 for CI scripts
