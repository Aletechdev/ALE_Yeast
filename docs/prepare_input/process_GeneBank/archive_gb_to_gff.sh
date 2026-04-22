#!/bin/bash

# Usage: ./gb_to_fasta.sh input.gb output.fasta

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 input.gb output.gff" >&2
    exit 1
fi

INPUT_GB=$(realpath "$1")
OUTPUT_GFF="$2"
INPUT_DIR=$(dirname "$INPUT_GB")
OUTPUT_DIR=$(dirname "$OUTPUT_GFF")
OUTPUT_FILENAME=$(basename "$OUTPUT_GFF")

mkdir -p "$OUTPUT_DIR"
docker run --rm --platform=linux/amd64 \
    -v "$(dirname "$1"):/data/in:ro" \
    -v "$(dirname "$2"):/data/out" \
    bioperl/bioperl:stable \
    sh -c "bp_genbank2gff3.pl /data/in/$(basename "$1") -out stdout" # > /data/out/$(basename "$2")"