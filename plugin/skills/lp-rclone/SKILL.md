---
name: lp-rclone
description: "Cloud file management using rclone. Covers setup checking, installation, remote configuration (S3, R2, B2, GDrive, Dropbox), common operations (copy, sync, ls, move), large file handling, and verification. Process skill loaded by /lp-feature-video for cloud storage upload."
---
# rclone — Cloud File Management

Process skill for managing files across cloud storage providers using rclone.

## Setup Checking

Before any operation, verify rclone is available:

```bash
# Check if installed
which rclone && rclone version

# Check configured remotes
rclone listremotes

# Test a specific remote
rclone lsd remote-name:
```

## Installation

```bash
# macOS
brew install rclone

# Linux (apt)
sudo apt install rclone

# Universal script
curl https://rclone.org/install.sh | sudo bash
```

## Remote Configuration

Configure remotes interactively with `rclone config` or by editing `~/.config/rclone/rclone.conf`.

### Common Providers

**Amazon S3 / S3-compatible:**

```ini
[myremote]
type = s3
provider = AWS          # or Cloudflare, DigitalOcean, Backblaze, etc.
access_key_id = xxx
secret_access_key = xxx
region = us-east-1
endpoint =              # Required for non-AWS (e.g., https://xxx.r2.cloudflarestorage.com)
```

**Cloudflare R2:**

```ini
[r2]
type = s3
provider = Cloudflare
access_key_id = xxx
secret_access_key = xxx
endpoint = https://ACCOUNT_ID.r2.cloudflarestorage.com
```

**Google Drive:**

```ini
[gdrive]
type = drive
client_id = xxx
client_secret = xxx
scope = drive
```

**Dropbox:**

```ini
[dropbox]
type = dropbox
client_id = xxx
client_secret = xxx
```

## Common Operations

```bash
# Upload file(s) to remote
rclone copy local/path remote:bucket/path

# Sync directory (make remote match local — deletes extra files on remote)
rclone sync local/path remote:bucket/path

# List files
rclone ls remote:bucket/path      # with sizes
rclone lsf remote:bucket/path     # filenames only

# Move files (copy + delete source)
rclone move local/path remote:bucket/path

# Delete from remote
rclone delete remote:bucket/path
```

## Useful Flags

```bash
--progress          # Show transfer progress
--transfers 4       # Parallel transfers (default 4)
--checkers 8        # Parallel checkers (default 8)
--dry-run           # Preview without executing
--verbose           # Detailed logging
--max-size 100M     # Skip files larger than 100MB
--include "*.mp4"   # Only match specific patterns
--exclude "*.tmp"   # Skip specific patterns
```

## Large File Handling

```bash
# Chunked uploads (for large files)
rclone copy bigfile.mp4 remote:bucket/ --s3-chunk-size 100M

# Bandwidth limiting
rclone copy . remote:bucket/ --bwlimit 10M

# Resume interrupted transfers
rclone copy . remote:bucket/ --retries 3 --retries-sleep 10s
```

## Verification

```bash
# Compare source and destination
rclone check local/path remote:bucket/path

# Hash verification
rclone hashsum MD5 remote:bucket/path
```

## Troubleshooting

- **Auth failures**: Re-run `rclone config` to refresh tokens
- **Permission errors**: Check bucket policy / IAM permissions
- **Rate limiting**: Add `--tpslimit 10` to throttle requests
- **Timeout**: Add `--timeout 30m` for slow connections
- **Debug**: Use `--verbose --dump headers` for detailed diagnostics
