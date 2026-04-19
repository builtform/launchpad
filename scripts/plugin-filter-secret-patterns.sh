#!/usr/bin/env bash
# Filter secret-patterns.txt to generic-only entries for the plugin bundle.
#
# The source file at .launchpad/secret-patterns.txt may accumulate
# LaunchPad-internal vendor patterns over time. This script emits only
# generic OWASP / gitleaks-community patterns that are safe to ship.
#
# Strategy: emit a known-safe baseline. Ignore the input file entirely
# for v0.1 — hand-maintained baseline guarantees no internal leakage.
set -euo pipefail

SRC="${1:?usage: $0 <source secret-patterns.txt>}"

# Known-safe generic baseline — maintained in this script, not sourced from .launchpad.
# POSIX ERE compatible (grep -E, no PCRE features like (?i), \s, \b).
cat <<'EOF'
# Generic secret patterns shipped with the launchpad plugin.
# Baseline maintained in scripts/plugin-filter-secret-patterns.sh.
# Covers common tokens; projects should extend via their own .launchpad/secret-patterns.txt.

# AWS
AKIA[0-9A-Z]{16}

# Google
AIza[0-9A-Za-z_-]{35}

# Stripe
sk_live_[0-9a-zA-Z]{24,}
sk_test_[0-9a-zA-Z]{24,}
pk_live_[0-9a-zA-Z]{24,}

# GitHub
ghp_[A-Za-z0-9]{36}
gho_[A-Za-z0-9]{36}
ghs_[A-Za-z0-9]{36}

# Slack
xox[baprs]-[0-9a-zA-Z]{10,}

# Private keys (opening header — OPENSSH/RSA/EC/DSA/PGP variants all caught)
-----BEGIN .* PRIVATE KEY-----
-----BEGIN PRIVATE KEY-----
EOF

# Note: $SRC is intentionally ignored for v0.1 (safe-by-baseline).
# If we ever want to merge project-specific patterns, add a curated allow-list here.
_=$SRC  # acknowledge param (silence unused-var lint)
