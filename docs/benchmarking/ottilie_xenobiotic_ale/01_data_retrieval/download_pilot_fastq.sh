#!/usr/bin/env bash
# Download FASTQ files for Stage A pilot samples from SRA.
#
# Prerequisites:
#   conda activate ottilie-benchmark  (sra-tools=3.2.1 required; 3.4.1 segfaults)
#
# Usage:
#   cd <repo_root>
#   bash bin/benchmarking/ottilie_xenobiotic_ale/download_pilot_fastq.sh
#
# Samples:
#   Parent:  NODRUG--GM2         (SRR10985539) - ABC16-Green Monster un-evolved control
#   SNV #1:  Doxorubicin-16--R2b (SRR10985527) - 23 mutations, EAW304
#   SNV #2:  Carmaphycin--R9-2   (SRR10985678) - 15 mutations, EAW131
#   CNV #1:  CBR110-15-R3a       (SRR10985585) - ChrI aneuploidy, EAW744
#
# Expected: ~2.7 GB compressed SRA → ~5-6 GB uncompressed FASTQ → ~2 GB gzipped
# Runtime:  ~2-5 min per sample depending on network speed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUTDIR="$REPO_ROOT/data/ottilie/fastq"
mkdir -p "$OUTDIR"

# Pilot sample accessions (ordered for deterministic execution)
SRRS=("SRR10985539" "SRR10985527" "SRR10985678" "SRR10985585")
NAMES=("NODRUG--GM2" "Doxorubicin-16--R2b" "Carmaphycin--R9-2" "CBR110-15-R3a")

TOTAL=${#SRRS[@]}
for i in "${!SRRS[@]}"; do
    SRR="${SRRS[$i]}"
    NAME="${NAMES[$i]}"
    NUM=$((i + 1))
    echo "============================================"
    echo "[$NUM/$TOTAL] $NAME ($SRR)"
    echo "============================================"

    # Skip if already downloaded
    if [[ -f "$OUTDIR/${SRR}_1.fastq.gz" && -f "$OUTDIR/${SRR}_2.fastq.gz" ]]; then
        echo "  Already exists, skipping."
        continue
    fi

    # Clean up any partial files from previous attempts
    rm -f "$OUTDIR/${SRR}_1.fastq" "$OUTDIR/${SRR}_2.fastq" \
          "$OUTDIR/${SRR}_1.fastq.gz" "$OUTDIR/${SRR}_2.fastq.gz"
    rm -rf "$OUTDIR/fasterq.tmp."*

    # Download and convert to FASTQ
    echo "  Downloading and converting to FASTQ..."
    fasterq-dump "$SRR" \
        --split-files \
        --outdir "$OUTDIR" \
        --threads 4

    # Verify both files exist before compressing
    if [[ ! -f "$OUTDIR/${SRR}_1.fastq" || ! -f "$OUTDIR/${SRR}_2.fastq" ]]; then
        echo "  ERROR: Expected paired-end files not found after fasterq-dump"
        ls -la "$OUTDIR/${SRR}"* 2>/dev/null || true
        exit 1
    fi

    # Compress sequentially (parallel gzip causes issues in some shell contexts)
    echo "  Compressing R1..."
    gzip -f "$OUTDIR/${SRR}_1.fastq"
    echo "  Compressing R2..."
    gzip -f "$OUTDIR/${SRR}_2.fastq"

    # Report
    echo "  Done:"
    ls -lh "$OUTDIR/${SRR}_1.fastq.gz" "$OUTDIR/${SRR}_2.fastq.gz"
    echo ""
done

echo "============================================"
echo "All $TOTAL pilot samples downloaded."
echo ""
ls -lh "$OUTDIR"/*.fastq.gz
echo "============================================"
