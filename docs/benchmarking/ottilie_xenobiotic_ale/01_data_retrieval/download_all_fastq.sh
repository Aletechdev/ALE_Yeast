#!/usr/bin/env bash
# Download ALL 363 Ottilie FASTQ files from SRA in batches, uploading each batch to Azure Blob.
#
# Strategy: Download ~50 samples at a time, upload to blob, delete local files, repeat.
# This keeps disk usage under ~50 GB per batch (avg ~1 GB/sample as FASTQ).
#
# Prerequisites:
#   conda activate ottilie-benchmark   (sra-tools=3.2.1 required; 3.4.1 segfaults)
#   .env file in repo root with AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_KEY
#
# Usage:
#   bash bin/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/download_all_fastq.sh [batch_size] [start_from]
#
# Arguments:
#   batch_size  - Number of samples per batch (default: 50)
#   start_from  - Resume from this sample number, 1-indexed (default: 1)
#
# Example:
#   bash download_all_fastq.sh 50 101   # Resume from sample 101

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
RUNINFO="${REPO_ROOT}/data/ottilie/PRJNA590203_runinfo.csv"
OUTDIR="${REPO_ROOT}/data/ottilie/fastq_all"
LOGFILE="${OUTDIR}/download_log.txt"

BATCH_SIZE="${1:-50}"
START_FROM="${2:-1}"

# Azure Blob destination
BLOB_CONTAINER="aledata"
BLOB_PREFIX="Yeast/ottilie_xenobiotic_ale/fastq"

# Load Azure credentials from .env
ENV_FILE="${REPO_ROOT}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found. Create it with:"
    echo "  AZURE_STORAGE_ACCOUNT=aledata"
    echo "  AZURE_STORAGE_KEY=<your-access-key>"
    exit 1
fi
source "${ENV_FILE}"
if [[ -z "${AZURE_STORAGE_ACCOUNT:-}" || -z "${AZURE_STORAGE_KEY:-}" ]]; then
    echo "ERROR: AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_KEY must be set in ${ENV_FILE}"
    exit 1
fi
export AZURE_STORAGE_ACCOUNT AZURE_STORAGE_KEY

mkdir -p "${OUTDIR}"

# Extract all SRR accessions (skip header)
mapfile -t ALL_SRRS < <(awk -F',' 'NR>1 {print $1}' "${RUNINFO}")
TOTAL=${#ALL_SRRS[@]}

echo "=== Ottilie FASTQ Batch Download ==="
echo "Total samples: ${TOTAL}"
echo "Batch size: ${BATCH_SIZE}"
echo "Starting from: ${START_FROM}"
echo "Local staging: ${OUTDIR}"
echo "Blob destination: ${BLOB_CONTAINER}/${BLOB_PREFIX}"
echo "Log file: ${LOGFILE}"
echo ""

# Check Azure storage auth
echo "Checking Azure storage authentication..."
if ! az storage container show --name "${BLOB_CONTAINER}" --account-name "${AZURE_STORAGE_ACCOUNT}" --account-key "${AZURE_STORAGE_KEY}" --query name -o tsv &>/dev/null; then
    echo "ERROR: Azure storage authentication failed. Check credentials in ${ENV_FILE}"
    exit 1
fi
echo "Azure storage authentication OK"
echo ""

# Process in batches
batch_num=0
for ((i = START_FROM - 1; i < TOTAL; i += BATCH_SIZE)); do
    batch_num=$((batch_num + 1))
    batch_end=$((i + BATCH_SIZE))
    [ $batch_end -gt $TOTAL ] && batch_end=$TOTAL

    echo "============================================"
    echo "BATCH ${batch_num}: samples $((i + 1))-${batch_end} of ${TOTAL}"
    echo "============================================"

    batch_success=0
    batch_fail=0

    for ((j = i; j < batch_end; j++)); do
        SRR="${ALL_SRRS[$j]}"
        NUM=$((j + 1))

        echo "  [$NUM/${TOTAL}] ${SRR}..."

        # Skip if already uploaded (check log)
        if grep -q "^UPLOADED ${SRR}$" "${LOGFILE}" 2>/dev/null; then
            echo "    Already uploaded, skipping."
            continue
        fi

        # Skip if local files exist (from interrupted batch)
        if [[ -f "${OUTDIR}/${SRR}_1.fastq.gz" && -f "${OUTDIR}/${SRR}_2.fastq.gz" ]]; then
            echo "    Local files exist, will upload with batch."
            batch_success=$((batch_success + 1))
            continue
        fi

        # Clean up partial files
        rm -f "${OUTDIR}/${SRR}_1.fastq" "${OUTDIR}/${SRR}_2.fastq" \
              "${OUTDIR}/${SRR}_1.fastq.gz" "${OUTDIR}/${SRR}_2.fastq.gz"
        rm -rf "${OUTDIR}/fasterq.tmp."*

        # Download
        if ! fasterq-dump "${SRR}" --split-files --outdir "${OUTDIR}" --threads 4 2>&1; then
            echo "    ERROR: fasterq-dump failed for ${SRR}"
            echo "FAILED_DOWNLOAD ${SRR}" >> "${LOGFILE}"
            batch_fail=$((batch_fail + 1))
            continue
        fi

        # Verify paired-end files
        if [[ ! -f "${OUTDIR}/${SRR}_1.fastq" || ! -f "${OUTDIR}/${SRR}_2.fastq" ]]; then
            echo "    ERROR: Missing paired-end files for ${SRR}"
            echo "FAILED_MISSING ${SRR}" >> "${LOGFILE}"
            batch_fail=$((batch_fail + 1))
            continue
        fi

        # Compress (pigz for parallel gzip, fallback to gzip)
        GZIP_CMD="gzip"
        command -v pigz &>/dev/null && GZIP_CMD="pigz -p 4"
        ${GZIP_CMD} -f "${OUTDIR}/${SRR}_1.fastq" &
        ${GZIP_CMD} -f "${OUTDIR}/${SRR}_2.fastq" &
        wait
        batch_success=$((batch_success + 1))
    done

    echo ""
    echo "  Batch ${batch_num} download complete: ${batch_success} OK, ${batch_fail} failed"

    # Upload batch to Azure Blob
    if [ ${batch_success} -gt 0 ] && ls "${OUTDIR}"/*.fastq.gz 1>/dev/null 2>&1; then
        echo "  Uploading batch ${batch_num} to Azure Blob..."
        if az storage blob upload-batch \
            --account-name "${AZURE_STORAGE_ACCOUNT}" \
            --account-key "${AZURE_STORAGE_KEY}" \
            --destination "${BLOB_CONTAINER}" \
            --destination-path "${BLOB_PREFIX}" \
            --source "${OUTDIR}" \
            --pattern "*.fastq.gz" \
            --overwrite 2>&1; then

            # Log uploaded files and delete local copies
            for f in "${OUTDIR}"/*.fastq.gz; do
                srr=$(basename "$f" | sed 's/_[12]\.fastq\.gz$//')
                # Only log as uploaded if both R1 and R2 exist
                if [[ -f "${OUTDIR}/${srr}_1.fastq.gz" && -f "${OUTDIR}/${srr}_2.fastq.gz" ]]; then
                    echo "UPLOADED ${srr}" >> "${LOGFILE}"
                fi
            done
            echo "  Upload complete. Cleaning local files..."
            rm -f "${OUTDIR}"/*.fastq.gz
        else
            echo "  ERROR: Upload failed! Keeping local files for retry."
            echo "  Fix the issue and re-run with: bash $0 ${BATCH_SIZE} $((i + 1))"
            exit 1
        fi
    fi

    echo "  Disk usage after cleanup: $(du -sh "${OUTDIR}" | cut -f1)"
    echo ""
done

echo "============================================"
echo "ALL DONE"
echo "Total: ${TOTAL} samples"
echo "Uploaded to: ${BLOB_CONTAINER}/${BLOB_PREFIX}/"
echo ""
echo "Summary:"
grep -c "^UPLOADED" "${LOGFILE}" 2>/dev/null && echo " uploaded" || echo "0 uploaded"
grep -c "^FAILED" "${LOGFILE}" 2>/dev/null && echo " failed" || echo "0 failed"
echo ""
echo "Failed samples (if any):"
grep "^FAILED" "${LOGFILE}" 2>/dev/null || echo "  None"
echo "============================================"
