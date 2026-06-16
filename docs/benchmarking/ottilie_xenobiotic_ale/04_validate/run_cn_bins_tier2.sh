#!/usr/bin/env bash
# Generate cn_bins_continuous.csv (bin-level CNR matrix) for Tier 2, then run CN cohort matrix
# Date: 2026-05-28
set -euo pipefail

source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

# 1. Build CN matrix including bin-level .cnr data (no --skip-cnr)
python bin/build_cn_matrix.py --output-dir output_ottilie_tier2 --fai data/ottilie/S288C_reference/S288C_R64.fa.fai --ploidy 1

FAI=data/ottilie/S288C_reference/S288C_R64.fa.fai
CN_DIR=output_ottilie_tier2/cn_matrices
RESULTS=docs/benchmarking/ottilie_xenobiotic_ale/04_validate/tier2_results

# 2. Run CN cohort matrix (requires cn_bins_continuous.csv from step 1)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cn_cohort_matrix.py \
    --cn-dir ${CN_DIR} \
    --csv ${RESULTS}/cn_cohort_matrix.csv

# 3. Collapsed CN cohort matrices (sensitive + stringent) with chr_length
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cn_cohort_matrix.py \
    --cn-dir ${CN_DIR} \
    --csv ${RESULTS}/cn_cohort_collapsed_sensitive.csv \
    --collapse --fai ${FAI} --segments sensitive

python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cn_cohort_matrix.py \
    --cn-dir ${CN_DIR} \
    --csv ${RESULTS}/cn_cohort_collapsed_stringent.csv \
    --collapse --fai ${FAI} --segments stringent
