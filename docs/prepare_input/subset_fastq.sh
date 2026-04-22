#!/bin/bash

# Usage: ./subset_fastq.sh <input_folder> <output_folder> <seed> <num_reads>
# Example: ./subset_fastq.sh ./input_fastq ./output_fastq 42 10000

set -e

INPUT_DIR="$1"
OUTPUT_DIR="$2"
SEED="$3"
NUM_READS="$4"

mkdir -p "$OUTPUT_DIR"

for fq in "$INPUT_DIR"/*.fastq.gz; do
    fname=$(basename "$fq")
    outfq="$OUTPUT_DIR/$fname"
    # Subset using seqtk in Docker
    docker run --rm -i \
        --platform=linux/amd64 \
        -v "$INPUT_DIR":/data/in:ro \
        -v "$OUTPUT_DIR":/data/out \
        staphb/seqtk:1.4 \
        bash -c "seqtk sample -s$SEED /data/in/$fname $NUM_READS | gzip > /data/out/SubSample$fname"
done