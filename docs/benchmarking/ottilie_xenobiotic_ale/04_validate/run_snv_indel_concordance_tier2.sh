#!/usr/bin/env bash
# run_snv_indel_concordance_tier2.sh — Generate Tier 2 SNV/INDEL concordance report
#
# Usage:
#   source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
#   bash 04_validate/run_snv_indel_concordance_tier2.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${SCRIPT_DIR}/tier2_results"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

mkdir -p "${RESULTS_DIR}"

echo "=== SNV/INDEL Concordance — Tier 2 ==="

python "${SCRIPT_DIR}/snv_indel_concordance.py" \
    --output-dir "${REPO_ROOT}/output_ottilie_tier2" \
    --csv "${RESULTS_DIR}/snv_indel_concordance_tier2.csv" \
    2>&1 | tee "${RESULTS_DIR}/snv_indel_concordance_tier2.log"

echo ""
echo "=== Investigating missed variants ==="

bash "${SCRIPT_DIR}/investigate_missed_snv_indel.sh" "${REPO_ROOT}/output_ottilie_tier2"

echo ""
echo "Results in: ${RESULTS_DIR}/"
ls -lh "${RESULTS_DIR}/"
