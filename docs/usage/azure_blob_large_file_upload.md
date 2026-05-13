# Uploading Large Files to Azure Blob Storage

## Problem

Uploading files >50 GB from an Azure VM using `az storage blob upload` or `azcopy` with
`--auth-mode login` (Entra ID / OAuth) fails due to MSAL token cache lock contention.

## Symptoms

### `az storage blob upload` (default multi-connection)
```
portalocker.exceptions.LockException: [Errno 11] Resource temporarily unavailable
```
Multiple upload threads compete for `~/.local/share/msal_extension/msal_cache.lock`
when refreshing OAuth tokens.

### `azcopy` with `AZCOPY_AUTO_LOGIN_TYPE=AZCLI`
```
400 The specified blob or block content is invalid.
X-Ms-Error-Code: InvalidBlobOrBlock
```
azcopy delegates token refresh to the same az CLI cache, causing the same lock
contention during parallel block staging. Increasing `--block-size-mb` (64, 256)
delays the failure but doesn't fix it.

## Root Cause

Both tools default to multi-threaded uploads. Each thread refreshes OAuth tokens
through the shared MSAL token cache file, which uses file-level locking. With large
files (many blocks), the concurrent lock requests exceed retry limits.

## Solution

Use `az storage blob upload` with `--max-connections 1`:

```bash
# Clear any stale lock first
rm -f ~/.local/share/msal_extension/msal_cache.lock

# Upload with single connection
az storage blob upload \
    --account-name <account> \
    --container-name <container> \
    --name "<blob/path/filename>" \
    --file <local_path> \
    --auth-mode login \
    --tier Cool \
    --overwrite true \
    --max-connections 1 \
    --no-progress
```

### Why this works
- Single connection = single token refresh path = no lock contention
- Trade-off: slower throughput (~30-60 min for 100 GB on same-region Azure transfer)
- `--tier Cool` recommended for archival data (cheaper storage, slightly higher access cost)

### Verify after upload
```bash
az storage blob show \
    --account-name <account> \
    --container-name <container> \
    --name "<blob/path/filename>" \
    --auth-mode login \
    --query "{size:properties.contentLength, tier:properties.blobTier}" \
    -o json
```
Compare `size` against `ls -l <local_file>` to confirm byte-exact match.

## Environment

- Azure CLI 2.x with `az login` (Entra ID auth)
- azcopy 10.32.x with `AZCOPY_AUTO_LOGIN_TYPE=AZCLI`
- Storage account: StorageV2 (GPv2), Standard_LRS
- Tested with files ~100 GB (May 2026)

## Alternatives (not tested)

- **SAS token auth**: Bypasses MSAL entirely — `azcopy` with a SAS URL would avoid the lock issue
  and allow full parallel throughput.
- **Managed identity**: May handle token caching differently, but untested for large uploads.
- **Split + upload**: `split -b 20G file.tar.gz file.tar.gz.part_` then upload parts individually.
  More complex but allows parallel uploads of separate files.
