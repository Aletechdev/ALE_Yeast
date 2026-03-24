#!/usr/bin/env bash
# =============================================================================
# Download adipic acid ALE data from Azure Blob Storage
# Places files in the expected data/ directory for the pipeline
#
# Authentication (choose one):
#   1. SAS token:  export AZURE_SAS_TOKEN="sv=2022-11-02&ss=b&srt=co&..."
#   2. Azure AD:   azcopy login --tenant-id <your-tenant-id>
#
# Usage:
#   bash bin/prepare_input/download_adipic_acid_ale_benchmark.sh           # Dry run
#   bash bin/prepare_input/download_adipic_acid_ale_benchmark.sh --execute # Download
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_DATA="${BASE}/data/data_a_paper"
LOCAL_REF="${BASE}/data/BakerYeast_reference"
BLOB_BASE="https://aledata.blob.core.windows.net/aledata/Yeast/adipic_acid_ale_benchmark"

# --- SAS token support ---
SAS_SUFFIX=""
if [[ -n "${AZURE_SAS_TOKEN:-}" ]]; then
    SAS_SUFFIX="?${AZURE_SAS_TOKEN#\?}"
    echo "Auth: Using SAS token"
else
    echo "Auth: Using Azure AD (azcopy login)"
fi

# Create target directories
mkdir -p "${LOCAL_DATA}/spore_seq/Adipic_acid"

echo "=== Download Plan ==="
echo "Source:      ${BLOB_BASE}/"
echo "Destination: ${LOCAL_DATA}"
echo "             ${LOCAL_REF}"
echo ""

# --- Dry run by default ---
if [[ "${1:-}" != "--execute" ]]; then
    echo "DRY RUN — add --execute to actually download"
    echo ""
    DRYRUN="--dry-run"
else
    echo "DOWNLOADING..."
    echo ""
    DRYRUN=""
fi

# Download FASTQ data and samplesheet
azcopy copy \
    "${BLOB_BASE}/data_a_paper/*${SAS_SUFFIX}" \
    "${LOCAL_DATA}/" \
    --recursive \
    ${DRYRUN}

# Download reference genome, annotation, and SnpEff cache
mkdir -p "${LOCAL_REF}/snpeff_cache"
azcopy copy \
    "${BLOB_BASE}/BakerYeast_reference/*${SAS_SUFFIX}" \
    "${LOCAL_REF}/" \
    --recursive \
    ${DRYRUN}

echo ""
echo "=== Done ==="
echo "Files downloaded to: ${LOCAL_DATA}"
echo "                     ${LOCAL_REF}"
echo ""
echo "Next steps:"
echo "  1. Run pipeline:    bash bin/CENPK_run_sarek_351_all.sh"
echo "  2. Run benchmarks:  See bin/benchmarking/adipic_acid_ale/README.md"
