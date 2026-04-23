#!/bin/bash
# Quick standalone run of igvreports on the joint HaplotypeCaller VCF
# Generates a self-contained HTML report for interactive variant review
#
# Usage: bash docs/igvreports/run_igvreports.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

nextflow run "${REPO_ROOT}/docs/igvreports/run_igvreports.nf" \
    -c "${REPO_ROOT}/docs/igvreports/nextflow.config" \
    --vcf "${REPO_ROOT}/output_all/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz" \
    --fasta "${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta" \
    --fai "${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta.fai" \
    --cram_dir "${REPO_ROOT}/output_all/preprocessing/markduplicates" \
    --outdir "${REPO_ROOT}/docs/igvreports/output" \
    -w "${REPO_ROOT}/docs/igvreports/work" \
    -resume
