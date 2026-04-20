#!/usr/bin/env bash
# =============================================================================
# Upload canonical copy of adipic acid ALE data to Azure Blob Storage
# Preserves folder structure so samplesheet paths work without modification
#
# Authentication (choose one):
#   1. SAS token:  export AZURE_SAS_TOKEN="sv=2022-11-02&ss=b&srt=co&..."
#   2. Azure AD:   azcopy login --tenant-id <your-tenant-id>
#
# Usage:
#   bash bin/prepare_input/upload_adipic_acid_ale_benchmark.sh           # Dry run
#   bash bin/prepare_input/upload_adipic_acid_ale_benchmark.sh --execute # Upload
#
# Destination mirrors local data/data_a_paper/ structure:
#   aledata/Yeast/adipic_acid_ale_benchmark/data_a_paper/
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
    # Strip leading '?' if present
    SAS_SUFFIX="?${AZURE_SAS_TOKEN#\?}"
    echo "Auth: Using SAS token"
else
    echo "Auth: Using Azure AD (azcopy login)"
fi

# --- Verify local data exists ---
if [[ ! -d "${LOCAL_DATA}" ]]; then
    echo "ERROR: Local data directory not found: ${LOCAL_DATA}"
    exit 1
fi

echo "=== Upload Plan ==="
echo "Source:      ${LOCAL_DATA}"
echo "Destination: ${BLOB_BASE}/data_a_paper/"
echo ""

# Count files
n_clonal=$(ls "${LOCAL_DATA}"/*.fastq.gz 2>/dev/null | wc -l)
n_spore=$(find "${LOCAL_DATA}/spore_seq/Adipic_acid" -name "*.fastq.gz" 2>/dev/null | wc -l)
echo "Clonal FASTQs:     ${n_clonal}"
echo "Spore-seq FASTQs:  ${n_spore}"
echo "Total FASTQs:      $((n_clonal + n_spore))"
echo ""

# --- Dry run by default ---
if [[ "${1:-}" != "--execute" ]]; then
    echo "DRY RUN — add --execute to actually upload"
    echo ""
    DRYRUN="--dry-run"
else
    echo "UPLOADING..."
    echo ""
    DRYRUN=""
fi

# Upload samplesheet
azcopy copy \
    "${LOCAL_DATA}/samplesheet_gen2_allNormal_changePloidy.csv" \
    "${BLOB_BASE}/data_a_paper/samplesheet_gen2_allNormal_changePloidy.csv${SAS_SUFFIX}" \
    ${DRYRUN}

# Upload clonal FASTQs (flat in data_a_paper/)
azcopy copy \
    "${LOCAL_DATA}/*.fastq.gz" \
    "${BLOB_BASE}/data_a_paper/${SAS_SUFFIX}" \
    --include-pattern "*.fastq.gz" \
    ${DRYRUN}

# Upload spore-seq FASTQs (preserve batch subfolder structure)
# Use /* to copy contents of spore_seq/ into destination, avoiding doubled spore_seq/spore_seq/
azcopy copy \
    "${LOCAL_DATA}/spore_seq/*" \
    "${BLOB_BASE}/data_a_paper/spore_seq/${SAS_SUFFIX}" \
    --recursive \
    --include-pattern "*.fastq.gz" \
    ${DRYRUN}

# Upload reference genome and annotation
azcopy copy \
    "${LOCAL_REF}/draft_ref52.fasta" \
    "${BLOB_BASE}/BakerYeast_reference/draft_ref52.fasta${SAS_SUFFIX}" \
    ${DRYRUN}

azcopy copy \
    "${LOCAL_REF}/draft_ref52.gff3" \
    "${BLOB_BASE}/BakerYeast_reference/draft_ref52.gff3${SAS_SUFFIX}" \
    ${DRYRUN}

# Upload SnpEff cache (recursive)
azcopy copy \
    "${LOCAL_REF}/snpeff_cache/*" \
    "${BLOB_BASE}/BakerYeast_reference/snpeff_cache/${SAS_SUFFIX}" \
    --recursive \
    ${DRYRUN}

echo ""
echo "=== Done ==="
echo "Blob location: ${BLOB_BASE}/data_a_paper/"
echo "               ${BLOB_BASE}/BakerYeast_reference/"
