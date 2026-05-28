#!/usr/bin/env bash
# Run full validation suite for Ottilie Tier 2 (86 samples)
# Date: 2026-05-28
#
# First run used --skip-cnr (via validate_all.py default), which skipped
# building the bin-level continuous CN matrix from .md.cnr files. This caused
# the CN cohort matrix step (cn_cohort_matrix.py) to fail because it requires
# cn_bins_continuous.csv as input.
#
# Fix: run build_cn_matrix.py without --skip-cnr separately (see run_cn_bins_tier2.sh),
# then re-run cn_cohort_matrix.py. All 6/6 validation steps now pass.
set -euo pipefail

source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/validate_all.py \
    --output-dir output_ottilie_tier2 \
    --results-dir docs/benchmarking/ottilie_xenobiotic_ale/04_validate/tier2_results \
    --ploidy 1 \
    --save-vcfs
