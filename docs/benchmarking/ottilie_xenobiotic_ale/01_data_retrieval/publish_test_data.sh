#!/usr/bin/env bash
# Publish the ottilie e2e test-data to Azure Blob in BOTH shapes, behind a stable PUBLIC (no-SAS) URL:
#   1. ottilie_test_data.tar.gz   — one atomic bundle for local onboarding / CI (download-then-run)
#   2. files/**                   — the individual file/folder tree for Seqera/Batch per-file staging
#   3. snpeff_cache.tar.gz        — cache-only tarball; Seqera fallback when a snpeff_cache *directory*
#                                   won't stage cleanly from a URL (point --snpeff_cache at the untarred dir)
#   4. SHA256SUMS                 — covers the individual files AND both tarballs, so a consumer can prove
#                                   the tarball unpacks to exactly the individual set (they never drift)
#   5. samplesheet_test_blob.csv  — samplesheet whose fastq_1/fastq_2 are the public per-file URLs (Seqera)
#
# Content is PRJNA590203 (public SRA) + public S288C reference/annotation → safe to be world-readable;
# the URL is stable, unauthenticated, and needs no SAS to distribute or rotate. See DATA_PROVENANCE.md.
#
# PROVISIONING IS OWNED BY infra/azure/ — the storage account + public 'releases' container (publicAccess
# 'blob') are created by infra/azure/deploy.sh from the ARM template. THIS script only UPLOADS content;
# it never creates or re-permissions the container (so it can't flip the deployed 'blob' access level).
#
# Requires: az CLI (`az login`), a populated data/ottilie/, tar, sha256sum. Uploads use shared-key auth
# (AUTH=key) — works with control-plane access + the account's allowSharedKeyAccess=true, no data-plane
# RBAC role needed. Set AUTH=login to use AAD instead (needs a Storage Blob Data role).
#
# Usage (from repo root):
#   bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/publish_test_data.sh
# Override target (e.g. a new version prefix, or a different host):
#   ACCOUNT=aletestdatapublic CONTAINER=releases PREFIX=ottilie/v2  bash .../publish_test_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
SRC="$REPO_ROOT/data/ottilie"

ACCOUNT="${ACCOUNT:-aletestdatapublic}"
CONTAINER="${CONTAINER:-releases}"
PREFIX="${PREFIX:-ottilie/v1}"                  # versioned → a re-host under v2 never breaks pinned runs
AUTH="${AUTH:-key}"                             # 'key' = shared-key (default, needs no data-plane role); 'login' = AAD
STAGE="${STAGE:-$REPO_ROOT/.ottilie_publish}"   # small: tarballs + SHA + url-samplesheet only (not the 402 MB copied)
BASE_URL="https://${ACCOUNT}.blob.core.windows.net/${CONTAINER}/${PREFIX}"

# ---------------------------------------------------------------------------
# Phase 0 — preflight (data present + container provisioned)
# ---------------------------------------------------------------------------
command -v az >/dev/null || { echo "ERROR: az CLI not found (az login required)." >&2; exit 1; }
[[ -d "$SRC/fastq_test" && -d "$SRC/S288C_reference_test" && -f "$SRC/S288C_reference/S288C_R64.gff3" ]] || {
    echo "ERROR: data/ottilie/ not populated. Run generate_test_data.sh (or download_test_data.sh) first." >&2
    exit 1
}

# The account + container are provisioned by infra/azure/deploy.sh — verify the container exists rather
# than creating it here (keeps provisioning in one place, and preserves the deployed public-access level).
EXISTS="$(az storage container exists --account-name "$ACCOUNT" --name "$CONTAINER" \
    --auth-mode "$AUTH" --query exists -o tsv 2>/dev/null || echo error)"
if [[ "$EXISTS" != "true" ]]; then
    echo "ERROR: container '$CONTAINER' not found on account '$ACCOUNT' (exists=$EXISTS)." >&2
    echo "       Provision it first: bash infra/azure/deploy.sh   (see infra/azure/README.md)" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Phase 1 — build tarballs, checksums, URL samplesheet (no 402 MB copy)
# ---------------------------------------------------------------------------
rm -rf "$STAGE"; mkdir -p "$STAGE"
echo "Building bundle + cache tarball ..."
tar -czf "$STAGE/ottilie_test_data.tar.gz" -C "$SRC" \
    fastq_test S288C_reference_test S288C_reference/S288C_R64.gff3
tar -czf "$STAGE/snpeff_cache.tar.gz" -C "$SRC/S288C_reference_test" snpeff_cache

echo "Writing SHA256SUMS (blob-relative paths) ..."
{
    # individual files → mirror the 'files/…' blob layout
    ( cd "$SRC" && find fastq_test S288C_reference_test S288C_reference/S288C_R64.gff3 -type f -print0 \
        | sort -z | xargs -0 sha256sum ) | awk '{print $1"  files/"$2}'
    ( cd "$STAGE" && sha256sum ottilie_test_data.tar.gz snpeff_cache.tar.gz )
} > "$STAGE/SHA256SUMS"

echo "Writing blob-URL samplesheet (for Seqera per-file staging) ..."
FQ="$BASE_URL/files/fastq_test"
cat > "$STAGE/samplesheet_test_blob.csv" <<CSV
experiment,sample,status,clonal_or_population,ploidy,sex,lane,fastq_1,fastq_2
Ottilie_test,NODRUG-GM2,0,clonal,1,XX,L001,$FQ/NODRUG-GM2_chrI_IV_VII_XV_R1.fastq.gz,$FQ/NODRUG-GM2_chrI_IV_VII_XV_R2.fastq.gz
Ottilie_test,CBR110-15-R3a,0,clonal,1,XX,L001,$FQ/CBR110-15-R3a_chrI_IV_VII_XV_R1.fastq.gz,$FQ/CBR110-15-R3a_chrI_IV_VII_XV_R2.fastq.gz
CSV

# ---------------------------------------------------------------------------
# Phase 2 — upload BOTH shapes under the versioned prefix
# ---------------------------------------------------------------------------
echo "Uploading individual file tree → $PREFIX/files/ ..."
az storage blob upload-batch --account-name "$ACCOUNT" --auth-mode "$AUTH" --overwrite \
    --destination "$CONTAINER" --destination-path "$PREFIX/files/fastq_test" \
    --source "$SRC/fastq_test" -o none
az storage blob upload-batch --account-name "$ACCOUNT" --auth-mode "$AUTH" --overwrite \
    --destination "$CONTAINER" --destination-path "$PREFIX/files/S288C_reference_test" \
    --source "$SRC/S288C_reference_test" -o none
az storage blob upload --account-name "$ACCOUNT" --auth-mode "$AUTH" --overwrite \
    --container-name "$CONTAINER" --name "$PREFIX/files/S288C_reference/S288C_R64.gff3" \
    --file "$SRC/S288C_reference/S288C_R64.gff3" -o none

echo "Uploading tarballs + SHA256SUMS + url-samplesheet → $PREFIX/ ..."
az storage blob upload-batch --account-name "$ACCOUNT" --auth-mode "$AUTH" --overwrite \
    --destination "$CONTAINER" --destination-path "$PREFIX" --source "$STAGE" -o none

# ---------------------------------------------------------------------------
# Phase 3 — verify the public (no-SAS) URL actually serves
# ---------------------------------------------------------------------------
echo ""
echo "Verifying public read (no credentials) ..."
if curl -fsSL "$BASE_URL/SHA256SUMS" -o /dev/null; then
    echo "  OK: $BASE_URL/SHA256SUMS is publicly readable."
else
    echo "  WARNING: public GET failed — check the container public-access level (infra/azure)." >&2
fi

cat <<EOF

Published under: $BASE_URL
  ottilie_test_data.tar.gz     full bundle (local onboarding / CI)
  snpeff_cache.tar.gz          cache-only (Seqera dir-staging fallback)
  files/**                     individual tree (Seqera per-file staging)
  SHA256SUMS                   integrity for both shapes
  samplesheet_test_blob.csv    Seqera samplesheet (per-file public URLs)

Local run:   bash $SCRIPT_DIR/download_test_data.sh
Seqera:      use samplesheet_test_blob.csv; for --snpeff_cache try the files/ dir URL first,
             fall back to snpeff_cache.tar.gz (untar → point at the snpeff_cache/ dir).
EOF
rm -rf "$STAGE"
