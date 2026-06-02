#!/usr/bin/env bash
# verify_soft_filter_fix.sh
#
# Spot-check script to verify the SNP/INDEL soft filter fix
# (vc.isSNP()/vc.isIndel() replacing broken TYPE==SNP/TYPE==INDEL)
#
# Run AFTER re-running the pipeline with the updated joint_germline.config.
#
# Usage:
#   source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
#   bash docs/variant-calling/haplotypecaller/verify_soft_filter_fix.sh <joint_vcf>
#
# Example:
#   bash docs/variant-calling/haplotypecaller/verify_soft_filter_fix.sh \
#     output_ottilie_tier2/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz
#
# Reference: https://gatk.broadinstitute.org/hc/en-us/articles/360035531112
#   Section [C]: SNP filters — QD<2, QUAL<30, SOR>3, FS>60, MQ<40, MQRankSum<-12.5, ReadPosRankSum<-8
#   Section [D]: INDEL filters — QD<2, QUAL<30, FS>200, ReadPosRankSum<-20 (NO SOR, MQ, MQRankSum)

set -euo pipefail

JV="${1:?Usage: $0 <joint_soft_filtered.vcf.gz>}"

if [ ! -f "$JV" ]; then
    echo "ERROR: File not found: $JV"
    exit 1
fi

PASS=0
FAIL=0

check_variant() {
    local id=$1 chrom_pos=$2 expected_filter=$3 description=$4
    local chrom="${chrom_pos%%:*}"
    local pos="${chrom_pos##*:}"
    local start=$((pos - 2))
    local end=$((pos + 2))

    local actual_filter
    actual_filter=$(bcftools query -r "$chrom:$start-$end" -f '%CHROM:%POS\t%FILTER\n' "$JV" 2>/dev/null \
        | grep "^${chrom}:${pos}" | head -1 | cut -f2)

    if [ -z "$actual_filter" ]; then
        echo "  [$id] SKIP   $chrom_pos — variant not found in VCF"
        return
    fi

    if [ "$actual_filter" = "$expected_filter" ]; then
        echo "  [$id] PASS   $chrom_pos  FILTER=$actual_filter  ($description)"
        ((PASS++)) || true
    else
        echo "  [$id] FAIL   $chrom_pos  expected=$expected_filter  got=$actual_filter  ($description)"
        ((FAIL++)) || true
    fi
}

echo "=============================================================================="
echo "Soft Filter Fix Verification — $(date)"
echo "VCF: $JV"
echo "=============================================================================="

# ── Overall statistics ──────────────────────────────────────────────────────

echo ""
echo "── Overall FILTER distribution ──"
echo ""
total=$(bcftools view -H "$JV" | wc -l)
pass_count=$(bcftools view -f PASS -H "$JV" | wc -l)
nonpass=$((total - pass_count))
echo "  Total variants: $total"
echo "  PASS:           $pass_count ($(awk "BEGIN{printf \"%.1f\", $pass_count/$total*100}")%)"
echo "  Non-PASS:       $nonpass ($(awk "BEGIN{printf \"%.1f\", $nonpass/$total*100}")%)"
echo ""
echo "  Filter tag counts:"
bcftools query -f '%FILTER\n' "$JV" | tr ';' '\n' | sort | uniq -c | sort -rn | head -15
echo ""

# ── SNP vs INDEL breakdown ──────────────────────────────────────────────────

echo "── SNP vs INDEL PASS rates ──"
echo ""
bcftools query -f '%REF\t%ALT\t%FILTER\n' "$JV" | python3 -c "
import sys
snp_pass = snp_fail = indel_pass = indel_fail = 0
for line in sys.stdin:
    ref, alt, filt = line.strip().split('\t')
    is_indel = len(ref) != len(alt)
    is_pass = filt == 'PASS'
    if is_indel:
        if is_pass: indel_pass += 1
        else: indel_fail += 1
    else:
        if is_pass: snp_pass += 1
        else: snp_fail += 1
snp_total = snp_pass + snp_fail
indel_total = indel_pass + indel_fail
print(f'  SNPs:   {snp_pass}/{snp_total} PASS ({snp_pass/snp_total*100:.1f}%)')
print(f'  INDELs: {indel_pass}/{indel_total} PASS ({indel_pass/indel_total*100:.1f}%)')
print()
print(f'  Expected after fix:')
print(f'    SNPs:   ~similar to before (SNP filters unchanged)')
print(f'    INDELs: ~97% PASS (up from ~74% before fix)')
"
echo ""

# ── Spot-check: INDELs that should be RECOVERED ────────────────────────────

echo "── Spot-check: INDELs recovered from wrong SNP filters ──"
echo ""
check_variant "S1" "III:325"        "PASS"       "INDEL C>CA, was SOR_filter (SOR=3.12), no SOR for INDELs"
check_variant "S2" "IV:1034111"     "PASS"       "INDEL ATG>A, was SOR_filter (SOR=3.13), no SOR for INDELs"
check_variant "S3" "VIII:562551"    "PASS"       "INDEL TG>T, was MQ_filter;SOR_filter (SOR=3.03,MQ=39), no SOR/MQ for INDELs"
check_variant "S4" "XIII:924388"    "PASS"       "INDEL GGTGTGGT>G, was MQ_filter (MQ=39.8), no MQ for INDELs"
check_variant "S5" "VIII:562385"    "QD_filter"  "INDEL AT>A, was MQ_filter;QD_filter (MQ=39.9), MQ removed but QD stays"
check_variant "S6" "XII:48855"      "PASS"       "INDEL C>CAAAA..., was FS_filter (FS=175.2<200), INDEL threshold is 200"
check_variant "S7" "IV:1525384"     "PASS"       "INDEL TGGGTGTGTG>T, was FS_filter;SOR_filter (FS=128,SOR=4.62), both removed"
echo ""

# ── Spot-check: SNPs that should STILL BE FILTERED ─────────────────────────

echo "── Spot-check: SNPs still correctly filtered ──"
echo ""
check_variant "S8"  "III:322"       "SOR_filter"              "SNP A>C (SOR=3.00), SNP SOR>3 still applies"
check_variant "S9"  "XI:666812"     "MQ_filter;SOR_filter"    "SNP T>G (SOR=3.01,MQ=35.2), both SNP filters apply"
check_variant "S10" "XI:524060"     "SOR_filter"              "SNP G>T (SOR=3.09), SNP SOR>3 still applies"
echo ""

# ── Spot-check: SNPs that should STILL BE PASS ─────────────────────────────

echo "── Spot-check: SNPs still correctly PASS ──"
echo ""
check_variant "S11" "XV:60240"      "PASS"  "SNP C>T (SOR=2.93), below SOR>3 threshold"
check_variant "S12" "XI:524066"     "PASS"  "SNP A>T (SOR=2.92), below SOR>3 threshold"
check_variant "S13" "IV:1525340"    "PASS"  "SNP C>A (SOR=2.90), below SOR>3 threshold"
echo ""

# ── Spot-check: Truth set INDEL #11 ────────────────────────────────────────

echo "── Spot-check: Truth set mutation #11 (HygromycinB INDEL) ──"
echo ""
# This is checked on the per-sample individual VCF, not the joint VCF
# The joint VCF position should also show the change
check_variant "T11" "XIV:572448"    "PASS"  "Truth INDEL CTT>C (SOR=5.421), was SOR_filter, no SOR for INDELs"
echo ""

# ── Check INDEL-specific filters are actually firing ────────────────────────

echo "── INDEL-specific filters firing? (were no-ops before fix) ──"
echo ""
fs_indel_count=$(bcftools query -f '%FILTER\n' "$JV" | grep -c "FS_INDEL_filter" || true)
rprs_indel_count=$(bcftools query -f '%FILTER\n' "$JV" | grep -c "ReadPosRankSum_INDEL_filter" || true)
echo "  FS_INDEL_filter (FS>200 for INDELs):              $fs_indel_count variants"
echo "  ReadPosRankSum_INDEL_filter (RPRS<-20 for INDELs): $rprs_indel_count variants"
if [ "$fs_indel_count" -gt 0 ] || [ "$rprs_indel_count" -gt 0 ]; then
    echo "  STATUS: INDEL-specific filters are now working!"
else
    echo "  WARNING: No INDEL-specific filters fired. Check if any INDELs have FS>200 or RPRS<-20."
fi
echo ""

# ── Summary ─────────────────────────────────────────────────────────────────

echo "=============================================================================="
echo "RESULTS: $PASS passed, $FAIL failed out of $((PASS + FAIL)) spot-checks"
echo "=============================================================================="
if [ "$FAIL" -eq 0 ]; then
    echo "All spot-checks passed! Filter fix is working correctly."
else
    echo "WARNING: $FAIL spot-check(s) failed. Review above for details."
fi
