#!/bin/bash

# Process Ogataea polymorpha GenBank file
# Usage: ./process_ogataea.sh

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DATA_DIR="/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495"
readonly INPUT_GBK="$DATA_DIR/Ogataea_polymorpha_NCYC495.gbk"
readonly OUTPUT_DIR="/home/azureuser/Docs/ALE_nextflow/data/Yeast_methanol_RWTH/Ogataea_polymorpha_NCYC495/processed"

echo "[INFO] Processing Ogataea polymorpha GenBank file..."
echo "[INFO] Input: $INPUT_GBK"
echo "[INFO] Output: $OUTPUT_DIR"

# Run the automated processing script
"$SCRIPT_DIR/process_genbank_auto.sh" "$INPUT_GBK" "$OUTPUT_DIR"

echo "[INFO] Processing completed!"
echo "[INFO] Review results: $OUTPUT_DIR/PROCESSING_SUMMARY.md"