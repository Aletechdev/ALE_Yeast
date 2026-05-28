#!/usr/bin/env bash
# Re-run validation suite for Ottilie Pilot (4 samples) with updated scripts
# Date: 2026-05-28
#
# Writes to pilot_results_v2/ to preserve original pilot_results/.
# Changes vs original pilot run:
#   - cnv_concordance.py: added event_category, chr_affected_pct, partial_details columns
#   - snv_indel_concordance.py: added snv_indel_missed.csv for undetected variant details
#   - validate_all.py: restructured report (undetected events in sections 1-2, full tables in section 3)
set -euo pipefail

source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/validate_all.py \
    --output-dir output_ottilie \
    --results-dir docs/benchmarking/ottilie_xenobiotic_ale/04_validate/pilot_results_v2 \
    --ploidy 1 \
    --save-vcfs
