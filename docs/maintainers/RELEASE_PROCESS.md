# Release Process (LaunchPad maintainers)

> **Audience:** LaunchPad maintainers shipping new versions of the plugin and template.
>
> **Not for downstream projects** scaffolded from LaunchPad. The v2.x kernel renderer never ships `docs/maintainers/` to downstream projects (the directory exists only in the LaunchPad source tree). Downstream projects choose their own release process (or none). v2.1 (BL-247) decommissioned the legacy `init-project.sh` flow that historically stripped this directory at init time; pin to v2.0.x for that flow.

LaunchPad ships versioned releases via the GitHub release flow. Every release follows this exact sequence to ensure each tag has hand-authored release notes published as a durable artifact in the repo.

Codex adapter releases: bump `plugins/launchpad/.claude-plugin/plugin.json` and `plugins/launchpad/.codex-plugin/plugin.json` together, then complete the checks below before tagging. They require a logged-in Codex command line, `jq`, and the release branch, tag, or commit in `<release-ref>`. This direct install from the LaunchPad repository is the maintainer test route. Users install through the BuiltForm marketplace.

```bash
# Install check: install the release candidate and verify the required installed files.
codex plugin marketplace add https://github.com/builtform/launchpad.git --ref <release-ref> --json
PLUGIN_PATH=$(codex plugin add launchpad@launchpad --json | jq -r '.installedPath')
codex plugin list
test -f "$PLUGIN_PATH/codex/skills/lp/SKILL.md"
test -f "$PLUGIN_PATH/scripts/plugin-codex-router.py"
test -d "$PLUGIN_PATH/commands"

# Help check: run live help and compare its helper inventory with the installed files.
codex exec '$launchpad:lp help'
diff <(find "$PLUGIN_PATH/commands" -maxdepth 1 -type f -name '*.md' -exec basename {} .md \; | sort) <(python3 "$PLUGIN_PATH/scripts/plugin-codex-router.py" inventory --kind command --json | jq -r '.items[].id' | sort)

# Record the host-generated direct entries for this Codex version.
codex debug prompt-input 'list' | grep -o 'launchpad:source-command-[a-z0-9-]*' | sort -u

codex plugin remove launchpad@launchpad --json
codex plugin marketplace remove launchpad --json
```

The install check passes when the plugin advertises `launchpad:lp` and all three installed-path checks exit zero. The help check passes when the transcript contains the helper's raw inventory JSON, the final message is a readable list, and `diff` exits zero.

After tagging, move the BuiltForm marketplace pin. In the `builtform/marketplace` repository, set the `ref` of the `launchpad` entry in `.claude-plugin/marketplace.json` to the new tag and merge that change. Users on both hosts receive the release only after this step. Then confirm the user install route once on Codex:

```bash
codex plugin marketplace add builtform/marketplace
codex plugin add launchpad@builtform
codex exec '$launchpad:lp help'
codex plugin remove launchpad@builtform
codex plugin marketplace remove builtform
```

Whenever these checks are rerun, update the "As of" and "Last checked" dates and the Codex version in `README.md` and `docs/guides/HOW_IT_WORKS.md`.

## Why this process exists

A tag without hand-authored notes leaves two bad options: accept GitHub's auto-generated diff as the project's first impression of the release (looks amateurish), or backfill notes via a follow-up PR after the release is already public. Pre-writing the notes file is the cheapest way to avoid both failure modes.

The MemPalace open-source pattern study (`docs/reports/launchpad_reports/2026-04-24-mempalace-open-source-pattern-study.md`, §10 item 8) documents this rule at length. The CI gate in `.github/workflows/release-notes-check.yml` enforces it mechanically; this doc explains the why and walks through the full sequence.

---

## Sequence for a new version `vX.Y.Z`

### 1. Branch + draft release notes (always together)

Create a release branch with the version embedded in the name:

```bash
git switch -c chore/vX.Y.Z-<short-summary>
```

**Draft `docs/releases/vX.Y.Z.md` as the first commit on the branch — before implementing the actual changes.** The release-notes-check CI workflow refuses to merge a release-named PR that does not include this file.

The notes can be sketched at draft quality — a placeholder structure with sections you'll fill in as the PR matures. What matters is that the file exists when the PR is opened. Refine the content as the PR's commits add detail.

Recommended sections (Keep-a-Changelog flavored, but only include the ones that apply):

- `## Security` — CVE remediations, security-relevant fixes
- `## Added` — new features
- `## Improved` — enhancements to existing features
- `## Documentation` — doc-only changes
- `## Internal` — refactors, dep bumps that don't change external behavior
- `## Upgrading from vX.Y.(Z-1)` — migration guidance, if applicable
- `## Full changelog` — link to `CHANGELOG.md`

### 2. Implement the changes

CVE fixes, feature work, doc updates — whatever the release contains.

Update the release-notes file as you go. By the time the PR is review-ready, the notes should match the actual changes.

### 2a. Re-validate and re-stamp the OPERATIONS §4 freshness docs (before tagging)

`v2-release.yml` runs two release-time freshness gates that hard-fail the tag if any `last_validated:` date is older than the 30-day window on the tagged commit:

- **Step 5** (`plugin-v2-handshake-lint.py --check-freshness`): the catalog/pattern subset (`scaffolders.yml`, `category-patterns.yml`, `scaffolders/*-pattern.md`), plus their schema and `knowledge_anchor_sha256` integrity.
- **Step 6** (`plugin-freshness-check.py --gating`): the full §4 target set, which additionally covers `pillar-framework.md` and the `SCAFFOLD_HANDSHAKE.md` / `SCAFFOLD_OPERATIONS.md` contract docs.

These gates fire on tag push, so the docs must already be fresh on the commit you tag. Do this re-stamp **on the release branch** (it must land on `main` before step 6 of this sequence), not after tagging. Preview what is stale locally first:

```bash
python plugins/launchpad/scripts/plugin-freshness-check.py --gating
```

For each flagged file, **re-read it and confirm it still accurately describes current behavior** (this is a real re-validation, not a date bump) before updating its date:

- **Catalog/pattern docs** (`scaffolders.yml`, `category-patterns.yml`, `pillar-framework.md`, `scaffolders/*-pattern.md`): bump `last_validated:` to today. Re-stamping a `*-pattern.md` changes its content hash, so re-pin the matching `knowledge_anchor_sha256` in `scaffolders.yml` (`plugin-v2-handshake-lint.py` prints the expected hash).
- **Contract docs** (`SCAFFOLD_HANDSHAKE.md`, `SCAFFOLD_OPERATIONS.md`): per OPERATIONS §4, re-stamp these in their **own dedicated commit** with subject `chore(v2): re-stamp HANDSHAKE/OPERATIONS last_validated, no contract change` and a `Restamp-Affirmation: <prior-SHA> -> <new-SHA>` trailer. The commit must touch only the `last_validated:` frontmatter line (no body diff).

Confirm both gates are green before proceeding:

```bash
python plugins/launchpad/scripts/plugin-v2-handshake-lint.py --check-freshness   # exit 0
python plugins/launchpad/scripts/plugin-freshness-check.py --gating              # exit 0
```

### 3. Open the PR

Branch name like `chore/vX.Y.Z-…` triggers `release-notes-check.yml`, which validates that `docs/releases/vX.Y.Z.md` exists.

### 4. Both AI reviewers post advisory comments

Codex (line-level / narrow lane) and Greptile (codebase-wide / cross-file lane) both review every PR. Both are advisory — neither blocks merge — and they cover complementary lanes. Address signal, ignore noise.

The required CI checks (Type Check, Lint, Build, Test, Repo Structure, Install) remain the merge gate.

### 5. Squash-merge to `main`

Use GitHub's "Squash and merge" button. The squash commit on `main` becomes the `vX.Y.Z` content.

### 6. Pull, tag, push

Pull `main` to get the squash commit, then tag **the squash commit specifically** (not just `HEAD`):

```bash
git checkout main && git pull --ff-only
git log --oneline -1                # confirm SQUASH_SHA
git tag -a vX.Y.Z -m "vX.Y.Z — short message" <SQUASH_SHA>
git push origin vX.Y.Z
```

The tag push triggers `release-notes-check.yml` once more as a belt-and-suspenders verification. If something has gone wrong (e.g., the tag is on the wrong commit), this is the last gate before publication.

### 7. Publish the GitHub Release

```bash
gh release create vX.Y.Z -F docs/releases/vX.Y.Z.md
```

The hand-authored notes file becomes the published release body.

### 8. Verify

- Check that any subsumed Dependabot PRs auto-close (their proposed bumps are now on `main`)
- Re-pull the vulnerability list (`gh api repos/<org>/<repo>/dependabot/alerts`) to confirm CVE count change
- Update `CHANGELOG.md` if the release introduces breaking changes worth a top-level summary

---

## Defense layers

| Layer           | What                                                                                                                     | Where                                                              |
| --------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| **CI gate**     | `release-notes-check.yml` fails any release PR or tag push without `docs/releases/v<VERSION>.md`                         | `.github/workflows/release-notes-check.yml`                        |
| **Memory rule** | Future Claude Code sessions read a feedback memory before acting; rule reminds to draft the file at branch-creation time | `~/.claude/projects/.../memory/feedback_release_notes_required.md` |
| **This doc**    | Explicit step-by-step checklist for human maintainers                                                                    | `docs/maintainers/RELEASE_PROCESS.md`                              |

These three together form the systematic fix for the v1.0.1 oversight (release PR opened without the release-notes file). Any one layer alone could fail; the combination is robust.

---

## Why this directory is removed from downstream

Downstream projects scaffolded from LaunchPad may have:

- Their own release conventions (some don't tag at all; some use different formats; some keep release notes only in `CHANGELOG.md`)
- Different visibility (private projects shouldn't have maintainer process docs visible)
- No need for the `release-notes-check.yml` workflow

Imposing LaunchPad's release process on downstream would be a workflow tax we have no right to charge. The v2.x kernel renderer never ships `release-notes-check.yml` or `docs/maintainers/` to downstream projects (those exist only in the LaunchPad source tree), so downstream starts clean and chooses its own process. (v2.1 BL-247 decommissioned the legacy `init-project.sh` flow that previously achieved the same result via init-time deletion.)
