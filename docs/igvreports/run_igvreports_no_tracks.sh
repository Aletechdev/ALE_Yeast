#!/bin/bash
# Quick igvreports run — VCF + reference only, no CRAM tracks
# Much faster; good for evaluating the report format first.
#
# Usage: bash docs/igvreports/run_igvreports_no_tracks.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

nextflow run "${REPO_ROOT}/docs/igvreports/run_igvreports_no_tracks.nf" \
    -c "${REPO_ROOT}/docs/igvreports/nextflow.config" \
    --vcf "${REPO_ROOT}/output_all/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz" \
    --fasta "${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta" \
    --fai "${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta.fai" \
    --outdir "${REPO_ROOT}/docs/igvreports/output_no_tracks" \
    -w "${REPO_ROOT}/docs/igvreports/work_no_tracks"
