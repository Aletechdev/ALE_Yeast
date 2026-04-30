#!/bin/bash
# Proof-of-concept: single-sample igvreports with CRAM track
# Uses A1-F6-I1-R1 (evolved clone) — 113 variants + 1 CRAM
#
# Usage: bash docs/igvreports/run_single_sample_poc.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SAMPLE="A1-F6-I1-R1"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

# Pre-process: add per-sample AF to VCF
VCF_IN="${REPO_ROOT}/output_all/variant_calling/haplotypecaller/individual_from_joint/${SAMPLE}/${SAMPLE}.haplotypecaller.from_joint_calling.vcf.gz"
VCF_WITH_AF="${REPO_ROOT}/docs/igvreports/output_single_sample/${SAMPLE}_with_af.vcf.gz"

mkdir -p "${REPO_ROOT}/docs/igvreports/output_single_sample"

bcftools +fill-tags "${VCF_IN}" -Oz -o "${VCF_WITH_AF}" -- -t FORMAT/VAF
bcftools index -t "${VCF_WITH_AF}"

# Run igvreports directly (no Nextflow overhead for this quick test)
docker run --rm \
    -v "${REPO_ROOT}:${REPO_ROOT}" \
    -u "$(id -u):$(id -g)" \
    quay.io/biocontainers/igv-reports:1.12.0--pyh7cba7a3_0 \
    create_report "${VCF_WITH_AF}" \
        --fasta "${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta" \
        --tracks "${REPO_ROOT}/output_all/preprocessing/markduplicates/${SAMPLE}/${SAMPLE}.md.cram" \
        --info-columns FILTER AC AF DP QD MQ FS SOR \
        --sample-columns GT AD DP GQ VAF \
        --flanking 500 \
        --title "${SAMPLE} - HaplotypeCaller (from joint calling)" \
        --output "${REPO_ROOT}/docs/igvreports/output_single_sample/${SAMPLE}_report.html"

echo "Done: docs/igvreports/output_single_sample/${SAMPLE}_report.html"
