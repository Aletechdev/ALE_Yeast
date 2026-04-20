#!/usr/bin/env bash
# Copy latest outputs from output_all/ to results/ for git tracking
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS="${SCRIPT_DIR}/results"
BASE="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

mkdir -p "${RESULTS}/tool_comparison"

cp "${BASE}/output_all/BENCHMARKING_SUMMARY.md" "${RESULTS}/"
cp "${BASE}/output_all/precision_recall_by_freq_bin.csv" "${RESULTS}/"
cp "${BASE}/output_all/variant_match_details.csv" "${RESULTS}/"
cp "${BASE}/output_all/tool_comparison/COMPARISON_REPORT.md" "${RESULTS}/tool_comparison/"
cp "${BASE}/output_all/tool_comparison/concordance_summary.csv" "${RESULTS}/tool_comparison/"
cp "${BASE}/output_all/tool_comparison/proximity_concordance_50bp.csv" "${RESULTS}/tool_comparison/"
cp "${BASE}/output_all/tool_comparison/resource_comparison.csv" "${RESULTS}/tool_comparison/"
cp "${BASE}/output_all/tool_comparison/variant_counts_per_sample.csv" "${RESULTS}/tool_comparison/"

echo "Results updated in ${RESULTS}/"
