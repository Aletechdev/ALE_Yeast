#!/bin/bash
# Subsample paired-end FASTQ files for quick pipeline validation
#
# Uses seqtk with a fixed seed to ensure:
#   - Reproducible subsampling across runs
#   - Matched R1/R2 pairs (same seed on both files)
#
# Default: 500K read pairs per sample (~8x coverage for 12Mb yeast genome)
#
# Usage:
#   conda activate nf-env
#   bash subsample_fastq.sh [input_dir] [output_dir] [num_reads]
#
# Example:
#   bash subsample_fastq.sh data/ottilie/fastq data/ottilie/fastq_subsampled 500000

set -euo pipefail

INPUT_DIR="${1:-data/ottilie/fastq}"
OUTPUT_DIR="${2:-data/ottilie/fastq_subsampled}"
NUM_READS="${3:-500000}"
SEED=42

if ! command -v seqtk &> /dev/null; then
    echo "ERROR: seqtk not found. Install with: conda install -c bioconda seqtk"
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

# Find all R1 files and subsample both R1 and R2
for r1 in "${INPUT_DIR}"/*_1.fastq.gz; do
    base=$(basename "$r1" _1.fastq.gz)
    r2="${INPUT_DIR}/${base}_2.fastq.gz"

    if [ ! -f "$r2" ]; then
        echo "WARNING: No R2 found for ${base}, skipping"
        continue
    fi

    echo "Subsampling ${base} to ${NUM_READS} read pairs (seed=${SEED})..."
    seqtk sample -s${SEED} "$r1" ${NUM_READS} | gzip > "${OUTPUT_DIR}/${base}_1.fastq.gz" &
    seqtk sample -s${SEED} "$r2" ${NUM_READS} | gzip > "${OUTPUT_DIR}/${base}_2.fastq.gz" &
    wait
done

echo ""
echo "Subsampled files in ${OUTPUT_DIR}/:"
ls -lh "${OUTPUT_DIR}/"
echo ""
echo "Estimated coverage (12Mb yeast genome, 100bp reads):"
echo "  ${NUM_READS} read pairs x 2 x 100bp / 12,000,000bp = $(echo "scale=1; ${NUM_READS} * 200 / 12000000" | bc)x"
