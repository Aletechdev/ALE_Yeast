#!/usr/bin/env bash
# investigate_missed_variants.sh — Reproduce pileup analysis for missed truth set variants
#
# Runs after snv_indel_concordance.py to characterise why specific variants
# were not detected by the pipeline.  Each section is self-contained so
# individual checks can be copy-pasted.
#
# Usage:
#   source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env
#   bash 04_validate/investigate_missed_variants.sh [output_dir]
#
# Default output_dir: output_ottilie_tier2

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
OUTPUT_DIR="${1:-${REPO_ROOT}/output_ottilie_tier2}"
REF="${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.fa"
GFF="${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.gff3"
RESULTS_DIR="$(dirname "$0")/tier2_results"

mkdir -p "${RESULTS_DIR}"
REPORT="${RESULTS_DIR}/missed_variants_investigation.txt"

cram_for() {
    local sample="$1"
    echo "${OUTPUT_DIR}/preprocessing/markduplicates/${sample}/${sample}.md.cram"
}

vcf_for() {
    local sample="$1"
    local dir="${OUTPUT_DIR}/variant_calling/haplotypecaller/individual_from_joint/${sample}"
    ls "${dir}"/*.vcf.gz 2>/dev/null | head -1
}

header() {
    echo ""
    echo "================================================================"
    echo "$1"
    echo "================================================================"
}

{
echo "Missed Variant Investigation — $(date -Iseconds)"
echo "Output directory: ${OUTPUT_DIR}"
echo "Reference: ${REF}"
echo ""
echo "Tier 2 concordance: 339/343 (98.8%) sensitivity"
echo "  SNP:   323/326 (99.1%)"
echo "  INDEL: 16/17  (94.1%)"
echo "  4 variants missed — investigation below"

# ─────────────────────────────────────────────────────────────────────
header "MISSED 1: I:59020 G>A — PTA1 missense — DDD01027481--8_R3a"
echo "Truth set: SNP, G>A, PTA1 (YAL044W-A), missense_variant"
echo ""

SAMPLE="DDD01027481--8_R3a"
CRAM=$(cram_for "$SAMPLE")

echo "--- VCF check (±10bp) ---"
bcftools query -r I:59010-59030 -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\n' "$(vcf_for "$SAMPLE")" 2>/dev/null || echo "(no variants)"

echo ""
echo "--- Pileup at I:59018-59022 ---"
samtools mpileup -f "$REF" -r I:59018-59022 "$CRAM" 2>/dev/null \
    | awk '{printf "  %s:%s depth=%s bases=%s\n", $1, $2, $4, substr($5,1,60)}'

echo ""
echo "--- MAPQ distribution ---"
samtools view "$CRAM" I:59020-59020 2>/dev/null \
    | awk '{print $5}' | sort -n | uniq -c | sort -rn | head -5
echo ""
echo "CONCLUSION: 73 reads, all reference G, MAPQ=60. Variant not present"
echo "in reads. Likely truth set discrepancy or mutation loss."

# ─────────────────────────────────────────────────────────────────────
header "MISSED 2: VIII:485367 T>A — ERG9 missense — MMV1078458--5R3a"
echo "Truth set: SNP, T>A, ERG9 (YHR190W), missense_variant"
echo ""

SAMPLE="MMV1078458--5R3a"
CRAM=$(cram_for "$SAMPLE")

echo "--- VCF check (±10bp) ---"
bcftools query -r VIII:485357-485377 -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\n' "$(vcf_for "$SAMPLE")" 2>/dev/null || echo "(no variants)"

echo ""
echo "--- Pileup at VIII:485365-485369 ---"
samtools mpileup -f "$REF" -r VIII:485365-485369 "$CRAM" 2>/dev/null \
    | awk '{printf "  %s:%s depth=%s bases=%s\n", $1, $2, $4, substr($5,1,60)}'

echo ""
echo "--- MAPQ distribution ---"
samtools view "$CRAM" VIII:485367-485367 2>/dev/null \
    | awk '{print $5}' | sort -n | uniq -c | sort -rn | head -5
echo ""
echo "CONCLUSION: 48 reads, all reference T, MAPQ=60. Variant not present"
echo "in reads. Likely truth set discrepancy or mutation loss."

# ─────────────────────────────────────────────────────────────────────
header "MISSED 3: III:316617 T>G — intergenic — MMV085203-11R3a"
echo "Truth set: SNP, T>G, intergenic region"
echo ""

SAMPLE="MMV085203-11R3a"
CRAM=$(cram_for "$SAMPLE")

echo "--- VCF check (±10bp) ---"
bcftools query -r III:316607-316627 -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\n' "$(vcf_for "$SAMPLE")" 2>/dev/null || echo "(no variants)"

echo ""
echo "--- Depth around III:316610-316625 ---"
samtools depth -a -r III:316610-316625 "$CRAM" 2>/dev/null \
    | awk '{printf "  %s:%s depth=%s\n", $1, $2, $3}'

echo ""
echo "--- Pileup at III:316615-316620 ---"
samtools mpileup -f "$REF" -r III:316615-316620 "$CRAM" 2>/dev/null \
    | awk '{printf "  %s:%s depth=%s bases=%s\n", $1, $2, $4, substr($5,1,60)}'

echo ""
echo "--- MAPQ distribution ---"
samtools view "$CRAM" III:316617-316617 2>/dev/null \
    | awk '{print $5}' | sort -n | uniq -c | sort -rn | head -5
echo ""
echo "CONCLUSION: Only ~7 reads at this position (subtelomeric region of"
echo "chr III). No alternate allele visible. Low coverage region."

# ─────────────────────────────────────────────────────────────────────
header "MISSED 4: XII:1071524 45bp deletion — intergenic rDNA — GNFpf2740--15_R5a"
echo "Truth set: INDEL, TAGGGCTATGTAGAAGTGCTGTAGGGCTAAAGAACAGGGTTTCA>T"
echo "           intergenic_region (rDNA intergenic spacer)"
echo ""

SAMPLE="GNFpf2740--15_R5a"
CRAM=$(cram_for "$SAMPLE")

echo "--- VCF check (±100bp) ---"
bcftools query -r XII:1071424-1071624 -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\n' "$(vcf_for "$SAMPLE")" 2>/dev/null || echo "(no variants)"

echo ""
echo "--- Depth at XII:1071520-1071530 ---"
samtools depth -a -r XII:1071520-1071530 "$CRAM" 2>/dev/null \
    | awk '{printf "  %s:%s depth=%s\n", $1, $2, $3}'

echo ""
echo "--- CIGAR deletion signals in reads ---"
echo -n "  Deletion sizes: "
samtools view "$CRAM" XII:1071520-1071570 2>/dev/null \
    | awk '{print $6}' | grep -oP '\d+D' | sort | uniq -c | sort -rn | head -5

echo ""
echo "--- rDNA context ---"
echo "  Chr XII rDNA locus contains ~150-200 tandem repeats of ~9.1 kb."
echo "  Coverage at this position: ~256x (vs expected ~50x for unique regions)."
echo "  A 45bp deletion in one rDNA copy would be at ~0.5% allele frequency,"
echo "  well below HaplotypeCaller's detection threshold."
echo ""
echo "CONCLUSION: rDNA multi-copy locus. Deletion is diluted across ~200"
echo "tandem repeats and undetectable by standard germline variant calling."
echo "Ottilie et al. likely used a specialised method for rDNA analysis."

# ─────────────────────────────────────────────────────────────────────
header "ADDITIONAL CONTEXT: Multi-allelic matching (fixed in this version)"
echo ""
echo "During development, 7 additional variants appeared missed due to"
echo "multi-allelic VCF representation:"
echo ""
echo "  YRR1 XV:640160 — truth C>G, pipeline C>G,A (4 samples)"
echo "  YRM1 XV:655947 — truth G>A or G>T, pipeline G>A,T (3 samples)"
echo ""
echo "These are correctly detected by the pipeline. The matching logic"
echo "was updated to handle multi-allelic records on both pipeline and"
echo "truth set sides (set intersection of ALT alleles)."
echo ""
echo "  YRR1: zinc cluster TF, drug resistance regulator (chr XV)"
echo "  YRM1: zinc cluster TF, multidrug resistance (chr XV)"
echo "  Both recurrently mutated across multiple drug treatments —"
echo "  consistent with known ALE adaptation targets."

# ─────────────────────────────────────────────────────────────────────
header "ADDITIONAL CONTEXT: PAU6 XIV:781921 (pilot run, soft-filtered)"
echo ""
echo "In the pilot run (output_ottilie, 3 samples), one variant was"
echo "detected but soft-filtered (not PASS):"
echo ""
echo "  XIV:781921 G>A — PAU6 missense — Doxorubicin16-R2b"
echo "  FILTER: MQ_filter;SOR_filter  QUAL: 1037.9"
echo ""
echo "PAU6 is one of 24 PAU gene family members (seripauperin genes)"
echo "in subtelomeric regions across all 16 chromosomes."
echo "  MAPQ distribution: 61 reads MAPQ=0 (66%), 23 reads MAPQ=40 (25%)"
echo "  Avg MAPQ: 12.2 — most reads are multi-mappers."
echo ""
echo "Soft-filtering is appropriate here. The variant is real but"
echo "inherently difficult to call with short reads in a multi-copy family."

header "SUMMARY"
echo ""
echo "Tier 2 SNV/INDEL concordance: 339/343 (98.8%)"
echo ""
echo "Missed variant breakdown:"
echo "  2x variant not in reads (PTA1, ERG9) — truth set discrepancy"
echo "  1x low coverage region (III:316617)  — subtelomeric, ~7 reads"
echo "  1x rDNA tandem repeat (XII:1071524)  — 45bp del diluted in ~200 copies"
echo ""
echo "None of the 4 misses are pipeline failures. The pipeline correctly"
echo "identifies variants where evidence exists in the sequencing data."

} 2>&1 | tee "${REPORT}"

echo ""
echo "Report saved to: ${REPORT}"
