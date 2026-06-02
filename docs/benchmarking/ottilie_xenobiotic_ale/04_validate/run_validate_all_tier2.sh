#!/usr/bin/env bash
# Run full validation suite for Ottilie Tier 2 (86 samples)
# Date: 2026-05-28, re-run 2026-05-29
# Re-run: 2026-06-01 — after soft filter fix (vc.isSNP()/vc.isIndel() in joint_germline.config)
#
# First run used --skip-cnr (via validate_all.py default), which skipped
# building the bin-level continuous CN matrix from .md.cnr files. This caused
# the CN cohort matrix step (cn_cohort_matrix.py) to fail because it requires
# cn_bins_continuous.csv as input.
#
# Fix: run build_cn_matrix.py without --skip-cnr separately (see run_cn_bins_tier2.sh),
# then re-run cn_cohort_matrix.py. All 6/6 validation steps now pass.
#
# Re-run 2026-05-29: validate_all.py fixed to handle both 'coverage' and
# 'chr_affected_pct' column names from cnv_concordance.csv, so the "Chr affected"
# column in VALIDATION_REPORT.md now shows correct values (e.g. 58% for partial
# chr XII duplications in Etoposide samples).
set -euo pipefail

source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
cd /home/azureuser/Docs/ALE_nextflow

RESULTS_DIR=docs/benchmarking/ottilie_xenobiotic_ale/04_validate/tier2_results

# 1. Full validation suite (all FILTER values)
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/validate_all.py \
    --output-dir output_ottilie_tier2 \
    --results-dir "${RESULTS_DIR}" \
    --ploidy 1 \
    --save-vcfs

# 2. PASS-only SNV/INDEL sensitivity (measures soft filter impact)
echo ""
echo "================================================================================"
echo "PASS-ONLY SNV/INDEL SENSITIVITY"
echo "================================================================================"
python docs/benchmarking/ottilie_xenobiotic_ale/04_validate/snv_indel_concordance.py \
    --output-dir output_ottilie_tier2 \
    --dictionary data/ottilie/sample_name_dictionary.csv \
    --parent NODRUG-GM2 \
    --pass-only

# 3. Soft filter PASS rates by variant type
echo ""
echo "================================================================================"
echo "SOFT FILTER PASS RATES (joint VCF)"
echo "================================================================================"
JOINT_VCF=output_ottilie_tier2/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
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
