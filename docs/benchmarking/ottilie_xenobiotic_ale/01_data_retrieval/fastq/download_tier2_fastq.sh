#!/usr/bin/env bash
# Download FASTQ files for Tier 2 benchmark samples from SRA.
#
# Tier 2 = 85 clones: 64 CRISPR-validated (Sup 7→4) + 21 CNV-only (Sup 5)
# Selected by: select_tier2_crispr_validated.py
# Input:       data/ottilie/tier2_crispr_validated_clones.csv
#
# Prerequisites:
#   conda activate ottilie-benchmark  (sra-tools=3.2.1 required; 3.4.1 segfaults)
#   python docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/truth_set/select_tier2_crispr_validated.py  (generates the clone CSV)
#
# Usage:
#   cd <repo_root>
#   bash docs/benchmarking/ottilie_xenobiotic_ale/01_data_retrieval/fastq/download_tier2_fastq.sh
#
# Options:
#   --dry-run    Show what would be downloaded without downloading
#   --resume     Skip already-downloaded samples (default behavior)
#
# Disk space:
#   ~40 GB gzipped FASTQs + ~120 GB peak temp during fasterq-dump (sequential)
#   Ensure ≥160 GB free before starting.
#
# Runtime: ~3-5 hours for 85 samples (depends on network speed)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
OUTDIR="$REPO_ROOT/data/ottilie/fastq"
CLONE_CSV="$REPO_ROOT/data/ottilie/tier2_crispr_validated_clones.csv"
PARENT_SRR="SRR10985539"  # NODRUG--GM2, shared with Tier 1

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

mkdir -p "$OUTDIR"

# --- Parse SRR accessions from CSV (skip header, skip empty/NA) ---
SRRS=()
NAMES=()
while IFS=, read -r clone_name eaw_id compound total_mutations crispr_validated selection_reason srr_accession rest; do
    # Skip header
    [[ "$clone_name" == "clone_name" ]] && continue
    # Skip rows without SRR
    [[ -z "$srr_accession" || "$srr_accession" == "" ]] && continue
    SRRS+=("$srr_accession")
    NAMES+=("$clone_name")
done < "$CLONE_CSV"

# Add parent if not already in list
parent_found=false
for srr in "${SRRS[@]}"; do
    if [[ "$srr" == "$PARENT_SRR" ]]; then
        parent_found=true
        break
    fi
done
if [[ "$parent_found" == "false" ]]; then
    SRRS=("$PARENT_SRR" "${SRRS[@]}")
    NAMES=("NODRUG--GM2(parent)" "${NAMES[@]}")
fi

# Deduplicate (some SRRs may appear twice if a sample has multiple clone names)
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
TOTAL_SIZE_MB=0

echo "============================================"
echo "Tier 2 FASTQ Download"
echo "  Samples: $TOTAL (from $CLONE_CSV)"
echo "  Output:  $OUTDIR"
echo "============================================"

# --- Check disk space ---
AVAIL_GB=$(df --output=avail -BG "$OUTDIR" | tail -1 | tr -d ' G')
echo "  Available disk: ${AVAIL_GB} GB"
if [[ "$AVAIL_GB" -lt 160 ]]; then
    echo "  WARNING: <160 GB free. fasterq-dump needs ~120 GB temp space."
    echo "  Consider freeing disk or using --dry-run first."
fi
echo ""

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

    echo "============================================"
    echo "[$NUM/$TOTAL] $NAME ($SRR)  [downloaded: $DOWNLOADED, skipped: $SKIPPED, failed: $FAILED]"
    echo "============================================"

    # Clean up any partial files from previous attempts
    rm -f "$OUTDIR/${SRR}_1.fastq" "$OUTDIR/${SRR}_2.fastq" \
          "$OUTDIR/${SRR}_1.fastq.gz" "$OUTDIR/${SRR}_2.fastq.gz"
    rm -rf "$OUTDIR/fasterq.tmp."*

    # Download and convert to FASTQ
    echo "  Downloading and converting to FASTQ..."
    if ! fasterq-dump "$SRR" \
        --split-files \
        --outdir "$OUTDIR" \
        --threads 4; then
        echo "  ERROR: fasterq-dump failed for $SRR"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Verify both files exist before compressing
    if [[ ! -f "$OUTDIR/${SRR}_1.fastq" || ! -f "$OUTDIR/${SRR}_2.fastq" ]]; then
        echo "  ERROR: Expected paired-end files not found after fasterq-dump"
        ls -la "$OUTDIR/${SRR}"* 2>/dev/null || true
        FAILED=$((FAILED + 1))
        continue
    fi

    # Compress sequentially (parallel gzip causes issues in some shell contexts)
    echo "  Compressing R1..."
    gzip -f "$OUTDIR/${SRR}_1.fastq"
    echo "  Compressing R2..."
    gzip -f "$OUTDIR/${SRR}_2.fastq"

    DOWNLOADED=$((DOWNLOADED + 1))

    # Report
    echo "  Done:"
    ls -lh "$OUTDIR/${SRR}_1.fastq.gz" "$OUTDIR/${SRR}_2.fastq.gz"
    echo ""
done

echo "============================================"
echo "Tier 2 download complete."
echo "  Total:      $TOTAL"
echo "  Downloaded: $DOWNLOADED"
echo "  Skipped:    $SKIPPED (already existed)"
echo "  Failed:     $FAILED"
echo ""
if [[ "$FAILED" -gt 0 ]]; then
    echo "WARNING: $FAILED samples failed. Rerun to retry (idempotent)."
fi
echo ""
ls "$OUTDIR"/*.fastq.gz | wc -l | xargs -I{} echo "FASTQ files in $OUTDIR: {} files"
du -sh "$OUTDIR"
echo "============================================"
