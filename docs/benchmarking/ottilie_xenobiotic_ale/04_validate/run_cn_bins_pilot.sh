#!/usr/bin/env bash
# Generate CN matrices for Ottilie Pilot (4 samples) and copy to ottilie_4samples/data/
# Date: 2026-06-10
set -euo pipefail

source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

FAI=data/ottilie/S288C_reference/S288C_R64.fa.fai
CN_DIR=output_ottilie/cn_matrices
DEST=docs/igvreports/ottilie_4samples/data

mkdir -p ${DEST}

# 1. Build CN matrix including bin-level .cnr data (no --skip-cnr)
python bin/build_cn_matrix.py --output-dir output_ottilie --fai ${FAI}

# 2. Run CN cohort matrix (requires cn_bins_continuous.csv from step 1)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cn_cohort_matrix.py \
    --cn-dir ${CN_DIR} \
    --csv ${DEST}/cn_cohort_matrix.csv

# 3. Collapsed CN cohort matrix with chr_length
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/cn_cohort_matrix.py \
    --cn-dir ${CN_DIR} \
    --csv ${DEST}/cn_cohort_collapsed.csv \
    --collapse --fai ${FAI}

# 4. Copy chr summary files from cn_matrices to dest (dashboard uses stringent only)
cp ${CN_DIR}/cn_chr_summary_sensitive.csv ${DEST}/
cp ${CN_DIR}/cn_chr_summary_stringent.csv ${DEST}/

echo ""
echo "============================================"
echo "Output files in ${DEST}/:"
ls -lh ${DEST}/cn_*.csv
