# Secret scanner tuning

LaunchPad's v2.1 render-batch flow runs every kernel and adapter render through a full-batch secret scanner before any `os.replace` writes to disk. A single pattern hit refuses the entire batch atomically (no partial writes). This guide covers how to tune the scanner against false positives without weakening the gate.

## Allowlist mechanisms

The scanner supports three suppression mechanisms. Pick the one that scopes most tightly to the actual false positive.

### Jinja-comment allowlist

Inside a `.j2` template, mark a line as scanner-exempt with a Jinja comment:

```jinja
{# secret-allowlist: openai-test-key #}
example_key = "sk-test_REDACTED"
```

The comment binds the allowlist to the literal line below it. Use this when the false positive is template-local and intentional (a documented example value baked into the canonical template).

### File-path-glob allowlist

Append glob patterns to `.launchpad/secret-allowlist.txt` to exclude entire files or path trees:

```
docs/guides/SECRET_SCANNER_TUNING.md
plugins/launchpad/scripts/tests/fixtures/**/*.example
```

Use this for fixture directories, documentation that intentionally shows secret-pattern shapes, or example projects bundled for tutorial purposes.

### Regex allowlist

Append regex patterns to `.launchpad/secret-allowlist.txt`:

```
^# Example: sk-test_[A-Za-z0-9_-]+\$REDACTED\$$
```

Use this only when the false positive shape is well-defined and cannot be captured by a glob. Anchor the pattern with `^` and `$` to avoid accidental over-matching.

For the canonical implementation, see `plugins/launchpad/scripts/secret_allowlist.py`. For the catalog of patterns the scanner enforces, see `.launchpad/secret-patterns.txt`.

## Tuning workflow

When the scanner refuses a render batch:

1. Read the scanner output. It names the pattern that matched and the file:line of the hit.
2. Categorize the finding:
   - **True positive**: a real secret leaked into the template or adapter. Remove it; do NOT allowlist.
   - **False positive on a documented example**: use the Jinja-comment allowlist if the line is template-local, or the file-path-glob if the whole file is intentionally an example.
   - **False positive on a fixture**: file-path-glob over the fixture directory.
3. Add the smallest allowlist entry that suppresses the finding. Avoid suppressing whole pattern classes if a single-file glob suffices.
4. Re-run the render batch. The scanner re-evaluates against the updated allowlist.
5. Commit the allowlist change in the same PR as the source change so the suppression has an audit trail.

For regression prevention, the allowlist file is part of the v2.1 audit-log enforcement surface (CODEOWNERS-protected); allowlist additions require maintainer review.

## Defense-in-depth framing

The render-batch scanner is one layer of secret protection. It is not the only layer:

- **Pre-commit hooks**. The lefthook `secret-scan` step runs the same pattern catalog against staged changes before any commit lands. This catches secrets leaked into hand-edits, not just template renders.
- **`git-secrets`**. A separate community tool that registers as a git hook and refuses commits containing common secret shapes (AWS keys, GitHub tokens, etc.). LaunchPad does not bundle it; install it as a complement, not a replacement.
- **GitHub secret-scanning**. GitHub's server-side scanner runs against the public default branch and notifies maintainers if a leaked secret matches a partner-vendor pattern (Stripe, AWS, etc.). Free for public repos.
- **Inline trust-model summary**. See [docs/releases/v2.1.0.md](../releases/v2.1.0.md) for the v2.1 trust-model framing, including the secret-scanner gate's place in the broader posture.

The render-batch scanner is the LaunchPad-specific layer. The other three layers protect surfaces LaunchPad does not own (hand-edits, leaked credentials in unrelated commits, server-side scanning).

## Warning: do not use prefix-only allowlists

A prefix-only regex allowlist like `^# Example: sk-` suppresses ANY line starting with `# Example: sk-`, regardless of what follows. An attacker who leaks a real OpenAI key can prefix it with `# Example: sk-` and bypass the scanner.

**Bad**:

```
^# Example: sk-
```

**Good**:

```
^# Example: sk-test_[A-Za-z0-9_-]+\$REDACTED\$$
```

The good form anchors the END of the line with a literal `$REDACTED$` token. A real leaked key would not contain that suffix, so the allowlist cannot be weaponized.

For documented secret-pattern examples, always:

1. Anchor both `^` and `$` of the pattern.
2. Use a literal `$REDACTED$` token (or `REDACTED` followed by a word boundary) as the trailing recognizable shape.
3. Prefer file-path-glob over regex for fixture exclusions; the glob is harder to weaponize because it requires write access to the fixture directory.

If a regex allowlist cannot be anchored end-of-line (e.g., the pattern legitimately appears mid-paragraph in prose), reconsider whether the file should be allowlisted at the file-path-glob level instead.
