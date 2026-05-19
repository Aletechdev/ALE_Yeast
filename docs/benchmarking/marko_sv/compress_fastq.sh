#!/usr/bin/env bash
# Compress raw FASTQ files to .fastq.gz using pigz (parallel gzip)
# Source: data/marko_SV/fastq/

set -euo pipefail

FASTQ_DIR="/home/azureuser/Docs/ALE_nextflow/data/marko_SV/fastq"

cd "$FASTQ_DIR"

for f in *.fastq; do
    [ -f "$f" ] || continue
    echo "Compressing $f ..."
    pigz -p 4 "$f"
done

echo "Done. Compressed files:"
ls -lh "$FASTQ_DIR"/*.fastq.gz
