"""LaunchPad plugin stack adapters.

Each concrete adapter exposes the functions contracted in contracts.py.
The composer (polyglot.py) merges outputs from multiple adapters when the
detector reports polyglot.

Adapters are intentionally thin — they return defaults for their stack,
not project-specific values. Project-specific data comes from the stack
detector's parsed manifests (composed by /lp-define into the final
canonical docs).
"""
