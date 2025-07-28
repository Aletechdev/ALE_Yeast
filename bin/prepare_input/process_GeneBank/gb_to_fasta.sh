#!/bin/bash

# Usage: ./gb_to_fasta.sh input.gb output.fasta

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 input.gb output.fasta" >&2
    exit 1
fi

INPUT_GB=$(realpath "$1")
OUTPUT_FASTA="$2"
INPUT_DIR=$(dirname "$INPUT_GB")
OUTPUT_DIR=$(dirname "$OUTPUT_FASTA")
OUTPUT_FILENAME=$(basename "$OUTPUT_FASTA")

mkdir -p "$OUTPUT_DIR"

docker run --rm --platform=linux/amd64 \
    -v "$INPUT_DIR":/data/in:ro \
    -v "$OUTPUT_DIR":/data/out \
    staphb/any2fasta:0.4.2 \
    sh -c "any2fasta /data/in/$(basename "$INPUT_GB") > /data/out/$OUTPUT_FILENAME"
