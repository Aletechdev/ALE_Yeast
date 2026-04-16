#!/bin/bash
# Upload test data to Azure Blob Storage for Seqera Platform demo
#
# Prerequisites:
#   - Azure CLI installed: az login
#   - azcopy installed: https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10
#   - Storage account accessible from Seqera compute environment
#
# Usage:
#   export STORAGE_ACCOUNT="your-storage-account-name"
#   bash bin/upload_test_data_azure.sh

set -euo pipefail

# --- Configuration ---
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:?Error: Set STORAGE_ACCOUNT environment variable}"
CONTAINER="${BLOB_CONTAINER:-aletest}"

# Resolve repo root from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BLOB_BASE="https://${STORAGE_ACCOUNT}.blob.core.windows.net/${CONTAINER}"

echo "=== Upload test data to Azure Blob Storage ==="
echo "Storage account: ${STORAGE_ACCOUNT}"
echo "Container:       ${CONTAINER}"
echo "Source:          ${REPO_ROOT}/assets/"
echo ""

# --- Create container (ignore if exists) ---
echo "Creating container '${CONTAINER}'..."
az storage container create \
    --name "${CONTAINER}" \
    --account-name "${STORAGE_ACCOUNT}" \
    --auth-mode login \
    2>/dev/null || echo "Container already exists or creation skipped"

# --- Upload reads (FASTQs + samplesheets) ---
echo ""
echo "Uploading reads..."
azcopy copy \
    "${REPO_ROOT}/assets/reads/" \
    "${BLOB_BASE}/assets/reads/" \
    --recursive

# --- Upload references (fasta, gff3, snpeff_cache) ---
echo ""
echo "Uploading references..."
azcopy copy \
    "${REPO_ROOT}/assets/references/draft_ref52.fasta" \
    "${BLOB_BASE}/assets/references/draft_ref52.fasta"

azcopy copy \
    "${REPO_ROOT}/assets/references/draft_ref52.gff3" \
    "${BLOB_BASE}/assets/references/draft_ref52.gff3"

echo ""
echo "Uploading chromosomes (required for Control-FREEC --chr_dir)..."
azcopy copy \
    "${REPO_ROOT}/assets/references/chromosomes/" \
    "${BLOB_BASE}/assets/references/chromosomes/" \
    --recursive

echo ""
echo "Uploading snpeff_cache..."
azcopy copy \
    "${REPO_ROOT}/assets/references/snpeff_cache/" \
    "${BLOB_BASE}/assets/references/snpeff_cache/" \
    --recursive

# --- Verify ---
echo ""
echo "=== Verification ==="
echo "Listing uploaded blobs:"
az storage blob list \
    --container-name "${CONTAINER}" \
    --account-name "${STORAGE_ACCOUNT}" \
    --auth-mode login \
    --output table \
    --query "[].{Name:name, Size:properties.contentLength}" \
    | head -30

echo ""
echo "=== Done ==="
echo ""
echo "Blob paths for Seqera launch:"
echo "  input:        az://${CONTAINER}/assets/reads/samplesheet_azure.csv"
echo "  fasta:        az://${CONTAINER}/assets/references/draft_ref52.fasta"
echo "  genbank:      az://${CONTAINER}/assets/references/draft_ref52.gff3"
echo "  chr_dir:      az://${CONTAINER}/assets/references/chromosomes"
echo "  snpeff_cache: az://${CONTAINER}/assets/references/snpeff_cache"
echo "  outdir:       az://${CONTAINER}/output_seqera_test"
