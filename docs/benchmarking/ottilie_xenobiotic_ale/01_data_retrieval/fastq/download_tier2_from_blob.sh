#!/usr/bin/env bash
# Download Tier 2 FASTQ files from Azure Blob Storage (aledata account).
#
# Source: aledata (account) / aledata (container) / Yeast/ottilie_xenobiotic_ale/fastq/
# The blob contains all 363 samples; this script downloads only the 86 Tier 2 SRRs.
#
# Prerequisites:
#   az login  (must be authenticated to Azure CLI)
#   python docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/truth_set/select_tier2_crispr_validated.py  (generates the clone CSV)
#
# Usage:
#   cd <repo_root>
#   bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/fastq/download_tier2_from_blob.sh
#
# Options:
#   --dry-run    Show what would be downloaded without downloading
#
# Disk space: ~40 GB gzipped FASTQs (no temp space needed unlike SRA download)
# Runtime:    ~15-30 min (same-region Azure transfer)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
OUTDIR="$REPO_ROOT/data/ottilie/fastq"
CLONE_CSV="$REPO_ROOT/data/ottilie/tier2_crispr_validated_clones.csv"
PARENT_SRR="SRR10985539"  # NODRUG--GM2, shared with Tier 1

STORAGE_ACCOUNT="aledata"
CONTAINER="aledata"
BLOB_PREFIX="Yeast/ottilie_xenobiotic_ale/fastq"

DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
    esac
done

# --- Validate inputs ---
if [[ ! -f "$CLONE_CSV" ]]; then
    echo "ERROR: $CLONE_CSV not found."
    echo "Run: python docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/truth_set/select_tier2_crispr_validated.py"
    exit 1
fi

# Check az login
if ! az account show &>/dev/null; then
    echo "ERROR: Not logged in to Azure CLI. Run: az login"
    exit 1
fi

mkdir -p "$OUTDIR"

# --- Parse SRR accessions from CSV (skip header, skip empty) ---
SRRS=()
NAMES=()
while IFS=, read -r clone_name eaw_id compound total_mutations crispr_validated selection_reason srr_accession rest; do
    [[ "$clone_name" == "clone_name" ]] && continue
    [[ -z "$srr_accession" || "$srr_accession" == "" ]] && continue
    SRRS+=("$srr_accession")
    NAMES+=("$clone_name")
done < "$CLONE_CSV"

# Add parent if not already in list
parent_found=false
for srr in "${SRRS[@]}"; do
    [[ "$srr" == "$PARENT_SRR" ]] && parent_found=true && break
done
if [[ "$parent_found" == "false" ]]; then
    SRRS=("$PARENT_SRR" "${SRRS[@]}")
    NAMES=("NODRUG--GM2(parent)" "${NAMES[@]}")
fi

# Deduplicate
declare -A SEEN
UNIQUE_SRRS=()
UNIQUE_NAMES=()
for i in "${!SRRS[@]}"; do
    srr="${SRRS[$i]}"
    if [[ -z "${SEEN[$srr]:-}" ]]; then
        SEEN[$srr]=1
        UNIQUE_SRRS+=("$srr")
        UNIQUE_NAMES+=("${NAMES[$i]}")
    fi
done

TOTAL=${#UNIQUE_SRRS[@]}
ALREADY=0
TO_DOWNLOAD=0

echo "============================================"
echo "Tier 2 FASTQ Download (from Azure Blob)"
echo "  Source:  ${STORAGE_ACCOUNT}/${CONTAINER}/${BLOB_PREFIX}/"
echo "  Samples: $TOTAL (from $CLONE_CSV)"
echo "  Output:  $OUTDIR"
echo "============================================"

# --- Count what needs downloading ---
for i in "${!UNIQUE_SRRS[@]}"; do
    SRR="${UNIQUE_SRRS[$i]}"
    if [[ -f "$OUTDIR/${SRR}_1.fastq.gz" && -f "$OUTDIR/${SRR}_2.fastq.gz" ]]; then
        ALREADY=$((ALREADY + 1))
    else
        TO_DOWNLOAD=$((TO_DOWNLOAD + 1))
    fi
done

echo "  Already downloaded: $ALREADY"
echo "  To download:        $TO_DOWNLOAD"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo "--- DRY RUN: listing samples ---"
    for i in "${!UNIQUE_SRRS[@]}"; do
        SRR="${UNIQUE_SRRS[$i]}"
        NAME="${UNIQUE_NAMES[$i]}"
        if [[ -f "$OUTDIR/${SRR}_1.fastq.gz" && -f "$OUTDIR/${SRR}_2.fastq.gz" ]]; then
            STATUS="EXISTS"
        else
            STATUS="DOWNLOAD"
        fi
        printf "  %-15s %-35s %s\n" "$SRR" "$NAME" "$STATUS"
    done
    echo ""
    echo "Rerun without --dry-run to start download."
    exit 0
fi

if [[ "$TO_DOWNLOAD" -eq 0 ]]; then
    echo "All $TOTAL samples already downloaded. Nothing to do."
    exit 0
fi

# --- Download loop ---
DOWNLOADED=0
FAILED=0
SKIPPED=0

for i in "${!UNIQUE_SRRS[@]}"; do
    SRR="${UNIQUE_SRRS[$i]}"
    NAME="${UNIQUE_NAMES[$i]}"
    NUM=$((i + 1))

    # Skip if already downloaded
    if [[ -f "$OUTDIR/${SRR}_1.fastq.gz" && -f "$OUTDIR/${SRR}_2.fastq.gz" ]]; then
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    echo "[$NUM/$TOTAL] $NAME ($SRR)  [downloaded: $DOWNLOADED, skipped: $SKIPPED, failed: $FAILED]"

    FAIL=false
    for READ in 1 2; do
        BLOB_NAME="${BLOB_PREFIX}/${SRR}_${READ}.fastq.gz"
        DEST="$OUTDIR/${SRR}_${READ}.fastq.gz"

        if ! az storage blob download \
            --account-name "$STORAGE_ACCOUNT" \
            --container-name "$CONTAINER" \
            --name "$BLOB_NAME" \
            --file "$DEST" \
            --auth-mode login \
            --no-progress \
            -o none 2>/dev/null; then
            echo "  ERROR: Failed to download $BLOB_NAME"
            rm -f "$DEST"
            FAIL=true
            break
        fi
    done

    if [[ "$FAIL" == "true" ]]; then
        FAILED=$((FAILED + 1))
        rm -f "$OUTDIR/${SRR}_1.fastq.gz" "$OUTDIR/${SRR}_2.fastq.gz"
        continue
    fi

    DOWNLOADED=$((DOWNLOADED + 1))
    R1_SIZE=$(ls -lh "$OUTDIR/${SRR}_1.fastq.gz" | awk '{print $5}')
    R2_SIZE=$(ls -lh "$OUTDIR/${SRR}_2.fastq.gz" | awk '{print $5}')
    echo "  Done: R1=${R1_SIZE}, R2=${R2_SIZE}"
done

echo ""
echo "============================================"
echo "Tier 2 download complete."
echo "  Total:      $TOTAL"
echo "  Downloaded: $DOWNLOADED"
echo "  Skipped:    $SKIPPED (already existed)"
echo "  Failed:     $FAILED"
if [[ "$FAILED" -gt 0 ]]; then
    echo ""
    echo "WARNING: $FAILED samples failed. Rerun to retry (idempotent)."
fi
echo ""
ls "$OUTDIR"/*.fastq.gz | wc -l | xargs -I{} echo "FASTQ files in $OUTDIR: {} files"
du -sh "$OUTDIR"
echo "============================================"
