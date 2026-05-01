#!/bin/bash
set -euo pipefail

# Generate IGVReports DEMO: I1 samples only with Tabulator template + multi-allelic splitting
# Requires: conda activate nf-env (nextflow + docker)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

# I1 replicates only (one per ALE lineage, ~77 MB total)
SAMPLES="A0-F0-I1-R1,A1-F6-I1-R1,A3-F3-I1-R1,A4-F5-I1-R1,A5-F4-I1-R1,A6-F6-I1-R1"

nextflow run "${REPO_ROOT}/docs/igvreports/generate_demo_reports.nf" \
    -c "${REPO_ROOT}/docs/igvreports/nextflow.config" \
    --annotated_joint_vcf "${REPO_ROOT}/output_all/annotation/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz" \
    --annotation_dir "${REPO_ROOT}/output_all/annotation/haplotypecaller" \
    --cram_dir "${REPO_ROOT}/output_all/preprocessing/markduplicates" \
    --gff3 "${REPO_ROOT}/data/BakerYeast_reference/snpeff_cache/data/draft_ref.52/draft_ref52.gff3" \
    --fasta "${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta" \
    --fai "${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta.fai" \
    --filter_config "${REPO_ROOT}/docs/igvreports/filter_config.yaml" \
    --outdir "${REPO_ROOT}/docs/igvreports/demo" \
    --samples "${SAMPLES}" \
    -resume

echo ""
echo "Done! Open docs/igvreports/demo/index.html"
