#!/usr/bin/env bash
# Generate SV cohort matrices for Ottilie Pilot (4 samples) and copy to ottilie_4samples/data/
# Date: 2026-06-11
set -euo pipefail

source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

DEST=docs/igvreports/ottilie_4samples/data
mkdir -p ${DEST}

# 1. Union (all calls, min_callers=1, no PASS filter) — with VCF
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_cohort_matrix.py \
    --output-dir output_ottilie \
    --source union \
    --csv ${DEST}/sv_cohort_matrix_union.csv \
    --vcf ${DEST}/sv_cohort_merged_union.vcf.gz

# 2. Union PASS-filtered — with VCF
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_cohort_matrix.py \
    --output-dir output_ottilie \
    --source union_pass \
    --csv ${DEST}/sv_cohort_matrix_union_pass.csv \
    --vcf ${DEST}/sv_cohort_merged_union_pass.vcf.gz

# 3. Base SV cohort matrix (same as validate_all.py produces)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_cohort_matrix.py \
    --output-dir output_ottilie \
    --csv ${DEST}/sv_cohort_matrix.csv

# 4. SV characterization (per-sample Manta+TIDDIT summary)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/sv_characterization.py \
    --output-dir output_ottilie \
    --csv ${DEST}/sv_characterization.csv

echo ""
echo "============================================"
echo "Output files in ${DEST}/:"
ls -lh ${DEST}/sv_*
