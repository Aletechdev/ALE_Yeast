#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# main_path="/Users/zhiweili/Documents/Repo/NF_ALE/data/data_a_paper"
# main_path="/Users/zhlia/Documents/GitRepo/NF_ALE/data/data_a_paper"
main_path="$(cd "$SCRIPT_DIR/../../data/data_a_paper" && pwd)"

SEED=18
NUM_READS=2000
OUT_DIR="$main_path/sub_sample"

# 1. Clonal samples (flat directory)
echo "=== Subsampling clonal samples ==="
sh "$SCRIPT_DIR/subset_fastq.sh" "$main_path" "$OUT_DIR" $SEED $NUM_READS

# 2. Spore-seq population samples (one subdirectory per batch)
echo "=== Subsampling spore-seq Adipic_acid population samples ==="
for batch_dir in "$main_path"/spore_seq/Adipic_acid/batch1PS_*; do
    echo "  Processing $(basename "$batch_dir") ..."
    sh "$SCRIPT_DIR/subset_fastq.sh" "$batch_dir" "$OUT_DIR" $SEED $NUM_READS
done

echo "=== Done. Subsampled files in $OUT_DIR ==="
