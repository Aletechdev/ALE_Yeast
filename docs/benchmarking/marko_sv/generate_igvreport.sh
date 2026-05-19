#!/bin/bash
set -euo pipefail

# Generate IGVReports for Marko SV benchmark sample (SRR6281661, E. coli K-12 MG1655)
# Produces two reports:
#   1. SNP/InDel report from HaplotypeCaller annotated VCF (76 variants)
#   2. SV report from SURVIVOR merged union VCF (DEL + INV breakpoints with CRAM pileups)
# Reuses the custom template from docs/igvreports/
#
# Requires: conda activate nf-env (bcftools, tabix, igv-reports, bgzip)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SAMPLE="SRR6281661"
OUTDIR="${REPO_ROOT}/docs/benchmarking/marko_sv/sv_comparison"

# --- Shared input files ---
CRAM="${REPO_ROOT}/output_marko_sv/preprocessing/markduplicates/${SAMPLE}/${SAMPLE}.md.cram"
CRAI="${CRAM}.crai"
FASTA="${REPO_ROOT}/data/marko_SV/reference/genbank_processed/escherichia_coli_str_k_12_substr_mg1655.fasta"
FAI="${FASTA}.fai"
GFF3="${REPO_ROOT}/data/marko_SV/reference/genbank_processed/escherichia_coli_str_k_12_substr_mg1655.gff3"
TEMPLATE="${REPO_ROOT}/docs/igvreports/custom_template_sample.html"
FILTER_CONFIG="${REPO_ROOT}/docs/igvreports/filter_config.yaml"

# --- Report-specific inputs ---
HC_VCF="${REPO_ROOT}/output_marko_sv/annotation/haplotypecaller/${SAMPLE}/${SAMPLE}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz"
SV_VCF="${REPO_ROOT}/docs/benchmarking/marko_sv/sv_comparison/merged_union.vcf"

# --- Validate inputs ---
for f in "$HC_VCF" "$SV_VCF" "$CRAM" "$CRAI" "$FASTA" "$FAI" "$GFF3" "$TEMPLATE" "$FILTER_CONFIG"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Missing input: $f" >&2
        exit 1
    fi
done

mkdir -p "$OUTDIR"
WORKDIR=$(mktemp -d)
trap "rm -rf $WORKDIR" EXIT

# =========================================================================
# Shared: Sort and index GFF3
# =========================================================================
echo "Preparing GFF3 gene annotations..."
(grep "^#" "$GFF3"; grep -v "^#" "$GFF3" | sort -k1,1 -k4,4n) \
    | bgzip > "${WORKDIR}/genes.sorted.gff3.gz"
tabix -p gff "${WORKDIR}/genes.sorted.gff3.gz"

# Helper to embed base64 VCF into report
embed_vcf() {
    local vcf_path="$1" html_path="$2" vcf_name="$3"
    python3 -c "
import base64, sys
vcf_path, html_path, vcf_name = sys.argv[1], sys.argv[2], sys.argv[3]
with open(vcf_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
with open(html_path, 'r') as f:
    html = f.read()
html = html.replace('@VCF_BASE64@', b64)
html = html.replace('@VCF_FILENAME@', vcf_name)
with open(html_path, 'w') as f:
    f.write(html)
print(f'  Embedded {len(b64)//1024} KB base64 as {vcf_name}')
" "$vcf_path" "$html_path" "$vcf_name"
}

# =========================================================================
# Report 1: SNP/InDel (HaplotypeCaller)
# =========================================================================
echo ""
echo "=== Report 1: SNP/InDel (HaplotypeCaller) ==="

echo "  Preparing HC VCF..."
bcftools norm -m- --old-rec-tag ORIG_ALT --force "$HC_VCF" -Oz -o "${WORKDIR}/hc_split.vcf.gz"
tabix -p vcf "${WORKDIR}/hc_split.vcf.gz"

bcftools view "${WORKDIR}/hc_split.vcf.gz" \
    | awk 'BEGIN{OFS="\t"}
        /^##/{print; next}
        /^#CHROM/{
            print "##INFO=<ID=VCF_FILTER,Number=1,Type=String,Description=\"Original VCF FILTER value\">"
            print; next
        }
        {
            filt=$7
            gsub(/;/, ",", filt)
            $8="VCF_FILTER=" filt ";" $8
            print
        }' \
    | bgzip > "${WORKDIR}/hc_with_filter.vcf.gz"
tabix -p vcf "${WORKDIR}/hc_with_filter.vcf.gz"

bcftools +fill-tags "${WORKDIR}/hc_with_filter.vcf.gz" -Oz -o "${WORKDIR}/hc_prepared.vcf.gz" -- -t FORMAT/VAF
tabix -p vcf "${WORKDIR}/hc_prepared.vcf.gz"

echo "  Generating report..."
create_report "${WORKDIR}/hc_prepared.vcf.gz" \
    --fasta "$FASTA" \
    --tracks "${WORKDIR}/genes.sorted.gff3.gz" "$CRAM" \
    --template "$TEMPLATE" \
    --filter-config "$FILTER_CONFIG" \
    --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \
    --sample-columns GT AD DP GQ VAF \
    --flanking 500 \
    --title "${SAMPLE} - HaplotypeCaller SNP/InDel (E. coli K-12)" \
    --output "${OUTDIR}/${SAMPLE}_report.html"

embed_vcf "${WORKDIR}/hc_prepared.vcf.gz" "${OUTDIR}/${SAMPLE}_report.html" "${SAMPLE}.hc.prepared.vcf.gz"
HC_COUNT=$(bcftools view -H "${WORKDIR}/hc_prepared.vcf.gz" | wc -l)
echo "  Done: ${HC_COUNT} variants → ${OUTDIR}/${SAMPLE}_report.html"

# =========================================================================
# Report 2: Structural Variants (SURVIVOR merged union)
# =========================================================================
echo ""
echo "=== Report 2: Structural Variants (SURVIVOR union) ==="

# The SURVIVOR VCF uses symbolic alleles (<DEL>, <INV>) and BND notation.
# We need to compress + index it, and add SUPP/SUPP_VEC to INFO columns.
# igv-reports will show the breakpoint region with CRAM pileup.
echo "  Preparing SV VCF..."
bgzip -c "$SV_VCF" > "${WORKDIR}/sv.vcf.gz"
tabix -p vcf "${WORKDIR}/sv.vcf.gz"

echo "  Generating report..."
create_report "${WORKDIR}/sv.vcf.gz" \
    --fasta "$FASTA" \
    --tracks "${WORKDIR}/genes.sorted.gff3.gz" "$CRAM" \
    --template "$TEMPLATE" \
    --info-columns SVTYPE SVLEN SUPP SUPP_VEC CHR2 END CIPOS CIEND STRANDS \
    --flanking 1000 \
    --title "${SAMPLE} - Structural Variants / SURVIVOR union (E. coli K-12)" \
    --output "${OUTDIR}/${SAMPLE}_sv_report.html"

embed_vcf "${WORKDIR}/sv.vcf.gz" "${OUTDIR}/${SAMPLE}_sv_report.html" "${SAMPLE}.survivor_union.vcf.gz"
SV_COUNT=$(bcftools view -H "${WORKDIR}/sv.vcf.gz" | wc -l)
echo "  Done: ${SV_COUNT} SVs → ${OUTDIR}/${SAMPLE}_sv_report.html"

# =========================================================================
echo ""
echo "=== All reports generated ==="
echo "  SNP/InDel: ${OUTDIR}/${SAMPLE}_report.html (${HC_COUNT} variants)"
echo "  SV:        ${OUTDIR}/${SAMPLE}_sv_report.html (${SV_COUNT} SVs)"
