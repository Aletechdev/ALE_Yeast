#!/usr/bin/env bash
# Validation suite for the Ottilie Pilot (4 samples) on the CURRENT recipe — results v3.
# Date: 2026-09-09 — v3: the current recipe (fastp trimming on since 948163c, HC hard filter out since 4acec56)
# Lineage: v2 wrapper (2026-05-28 / 2026-06-01) with only the output/results dirs changed.
# Pipeline output: output_ottilie_pilot_2026-09-09/ (run_ottilie_pilot.sh, commit d4efac9, 287 tasks).
#
# Writes to pilot_results_v3/ so pilot_results_v2/ (pre-trimming, hard filter on) stays intact.
# Script changes vs the original pilot run (inherited from v2):
#   - cnv_concordance.py: added event_category, chr_affected_pct, partial_details columns
#   - snv_indel_concordance.py: added snv_indel_missed.csv for undetected variant details
#   - validate_all.py: restructured report (undetected events in sections 1-2, full tables in section 3)
set -euo pipefail

source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

RESULTS_DIR=docs/benchmarking/ottilie_xenobiotic_ale/04_validate/pilot_results_v3

# 1. Full validation suite (all FILTER values)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/validate_all.py \
    --output-dir output_ottilie_pilot_2026-09-09 \
    --results-dir "${RESULTS_DIR}" \
    --ploidy 1 \
    --save-vcfs

# 2. PASS-only SNV/INDEL sensitivity (measures soft filter impact)
echo ""
echo "================================================================================"
echo "PASS-ONLY SNV/INDEL SENSITIVITY"
echo "================================================================================"
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/snv_indel_concordance.py \
    --output-dir output_ottilie_pilot_2026-09-09 \
    --dictionary data/ottilie/sample_name_dictionary.csv \
    --parent NODRUG-GM2 \
    --pass-only

# 3. Soft filter PASS rates by variant type
echo ""
echo "================================================================================"
echo "SOFT FILTER PASS RATES (joint VCF)"
echo "================================================================================"
JOINT_VCF=output_ottilie_pilot_2026-09-09/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
echo "FILTER distribution:"
bcftools query -f '%FILTER\n' "${JOINT_VCF}" | sort | uniq -c | sort -rn
echo ""
echo "PASS by variant type:"
bcftools view -f PASS "${JOINT_VCF}" | bcftools query -f '%REF\t%ALT\n' | \
    awk '{if(length($1)==1 && length($2)==1) snp++; else indel++} END {
        print "  SNP PASS:   " snp+0; print "  INDEL PASS: " indel+0}'
echo "Total by variant type:"
bcftools query -f '%REF\t%ALT\n' "${JOINT_VCF}" | \
    awk '{if(length($1)==1 && length($2)==1) snp++; else indel++} END {
        print "  SNP total:   " snp+0; print "  INDEL total: " indel+0}'
