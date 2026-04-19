---
name: lp-imgup
description: "Lightweight image hosting for quick sharing. Upload screenshots and small files to public hosting services (pixhost, catbox, imagebin, beeimg) without cloud provider setup. Returns public URLs for embedding in markdown. Process skill loaded by /lp-feature-video as alternative to rclone."
---
# imgup — Quick Image Hosting

Lightweight process skill for uploading images to public hosting services. No cloud provider setup needed — just upload and get a URL.

## When to Use imgup vs rclone

| Scenario                  | Use        |
| ------------------------- | ---------- |
| Quick screenshot sharing  | **imgup**  |
| Small files (< 10MB)      | **imgup**  |
| PR description embeds     | **imgup**  |
| Design documentation      | **imgup**  |
| Video uploads             | **rclone** |
| Persistent storage needed | **rclone** |
| Large files (> 10MB)      | **rclone** |
| Private/authenticated     | **rclone** |

## Supported Hosts

### pixhost (recommended — no API key required)

```bash
# Upload via curl
curl -F "img=@screenshot.png" https://api.pixhost.to/images -F "content_type=0"
```

Returns JSON with `show_url` (view page) and `th_url` (direct image link).

### catbox

```bash
# Upload to catbox (200MB max, no expiry)
curl -F "reqtype=fileupload" -F "fileToUpload=@screenshot.png" https://catbox.moe/user/api.php
```

Returns direct URL.

### imagebin

```bash
# Upload to imagebin
curl -F "image=@screenshot.png" https://imagebin.ca/upload.php
```

### beeimg

```bash
# Upload to beeimg
curl -F "image=@screenshot.png" https://beeimg.com/api/upload/
```

## Usage Pattern

```bash
# 1. Take screenshot (or use existing file)
# 2. Upload
URL=$(curl -sF "img=@.harness/screenshots/feature.png" https://api.pixhost.to/images -F "content_type=0" | jq -r '.show_url')

# 3. Use in markdown
echo "![Feature Screenshot]($URL)"
```

## Output for PR/Docs

After uploading, format for embedding:

```markdown
![Feature Demo](https://img.pixhost.to/images/xxx/screenshot.png)
```

For multiple screenshots:

```markdown
| View    | Screenshot       |
| ------- | ---------------- |
| Mobile  | ![Mobile](url1)  |
| Desktop | ![Desktop](url2) |
```

## Limitations

- **No persistent storage guarantees** — images may be removed after inactivity
- **Public only** — no authentication or private uploads
- **Size limits** — typically 10-200MB depending on host
- **No versioning** — upload creates a new URL each time
- For persistent, authenticated storage, use the `rclone` skill instead
