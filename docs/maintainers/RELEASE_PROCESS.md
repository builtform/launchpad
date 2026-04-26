# Release Process (LaunchPad maintainers)

> **Audience:** LaunchPad maintainers shipping new versions of the plugin and template.
>
> **Not for downstream projects** scaffolded from LaunchPad — `scripts/setup/init-project.sh` removes the entire `docs/maintainers/` directory during project initialization. Downstream projects choose their own release process (or none).

LaunchPad ships versioned releases via the GitHub release flow. Every release follows this exact sequence to ensure each tag has hand-authored release notes published as a durable artifact in the repo.

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

Imposing LaunchPad's release process on downstream would be a workflow tax we have no right to charge. `init-project.sh` removes both the `release-notes-check.yml` workflow and the entire `docs/maintainers/` directory at init time, so downstream projects start clean and choose their own process.
