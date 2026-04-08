---
description: "Record a video walkthrough of a feature — captures screenshots via agent-browser, stitches into MP4+GIF via ffmpeg, uploads via rclone or imgup, and updates PR description."
---

# /feature-video

Record a video walkthrough of a feature for PR descriptions and design documentation.

## Usage

```
/feature-video              → auto-detect routes from changed files
/feature-video [url]        → record specific URL
/feature-video --pr         → record and update PR description
```

**Arguments:** `$ARGUMENTS` (optional URL or `--pr` flag)

---

## Dependencies

- **agent-browser** — for screenshot capture (required)
- **ffmpeg** — for video generation (required)
- **rclone** — for cloud upload (optional, preferred). Load `rclone` skill.
- **imgup** — for quick image hosting (fallback). Load `imgup` skill.

---

## Flow

### Step 1: Parse PR Context

- Read current branch name
- Read PR description (if exists): `gh pr view --json title,body`
- Get changed files: `git diff --name-only origin/main...HEAD`
- Map changed files to routes:
  - `apps/web/src/app/**/page.tsx` → URL paths (Next.js App Router convention)
  - e.g., `apps/web/src/app/dashboard/page.tsx` → `/dashboard`

### Step 2: Plan Shot List

- Identify key routes/components affected by changes
- Order shots for narrative flow (overview → detail → interaction)
- If URL provided via `$ARGUMENTS`, use that as the only target

### Step 3: Capture Screenshots

- Detect dev server: check if `pnpm dev` is running (port 3000)
  - **Do NOT start the dev server** — warn if not running and exit
- Navigate to each route via agent-browser
- Capture screenshots at key breakpoints (640, 1024, 1280px)
- Capture interaction states (hover, click, form fill) if applicable
- Save screenshots to `.harness/screenshots/` (ephemeral, gitignored)

### Step 4: Convert to Video

```bash
# Stitch screenshots into MP4 (3-5 seconds per frame)
ffmpeg -framerate 1/3 -pattern_type glob -i '.harness/screenshots/feature-*.png' \
  -c:v libx264 -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" \
  .harness/screenshots/feature-demo.mp4

# Generate GIF version (lower quality, smaller size, for inline preview)
ffmpeg -i .harness/screenshots/feature-demo.mp4 \
  -vf "fps=1,scale=800:-1:flags=lanczos" \
  .harness/screenshots/feature-demo.gif
```

### Step 5: Upload

- **IF rclone configured** (check `rclone listremotes`):
  - Upload MP4+GIF to configured remote
  - Load `rclone` skill for operation guidance
  - Return public URLs
- **ELSE:**
  - Upload via imgup (quick public hosting, no setup needed)
  - Load `imgup` skill for operation guidance
  - Return public URLs

### Step 6: Update PR Description

- **IF `--pr` flag AND PR exists:**
  - Append video embed to PR description via `gh pr edit`
  - Format: `![Feature Demo](gif_url)` inline + `[Full Video](mp4_url)` link
- **IF no PR:**
  - Output URLs for manual inclusion

---

## Wiring Points

1. `/harness:plan` Step 2d — design walkthrough after design approval (optional)
2. `/harness:build` after `/ship` — feature demo for PR (optional)
3. Standalone — record any feature at any time

---

## Notes

- Screenshots are saved to `.harness/screenshots/` which is gitignored
- MP4 and GIF files are also gitignored (`.harness/screenshots/*.mp4`, `.harness/screenshots/*.gif`)
- This command modifies PR descriptions (via `gh pr edit`) but does NOT modify code
- Dev server must be running — this command will NOT start it
