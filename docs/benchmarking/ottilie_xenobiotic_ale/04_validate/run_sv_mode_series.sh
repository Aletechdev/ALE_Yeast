#!/usr/bin/env bash
# Produce the SV pass table in all three Manta modes for one cohort size.
#
# Why: per-sample vs joint vs joint+high-sensitivity Manta give near-identical ROW COUNTS while
# saying completely different things about which events are clone-specific. The comparison has to
# be made on the merged deliverable, at more than one cohort size, because the two modes' error
# curves run in opposite directions (per-sample's false specificity grows with N; joint's discovery
# suppression only appears at large N). Scored by compare_sv_pass_tables.py; findings in
# manta_joint_at_scale/REPORT.md; guidance in docs/variant-calling/manta/manta_calling_modes.md.
#
# Cohort sizes used: 2 and 4 (test set / pilot, aligned from FASTQ) and 16/48/86 (subsets of the
# Tier-2 md.crams entered at --step variant_calling).
#
# Usage:
#   run_sv_mode_series.sh <samplesheet.csv> <outdir-prefix> [workdir]
#
# The samplesheet must be a CRAM sheet (experiment,sample,status,clonal_or_population,ploidy,sex,cram,crai).
# IMPORTANT: its `experiment` column must match the experiment encoded in the CRAMs' @RG SM tags
# (the joint-VCF split looks for "<experiment>_<sample>"), and keeping it constant across cohort
# sizes lets the per-sample TIDDIT tasks cache-hit between runs. See troubleshooting.md.
set -euo pipefail

SHEET="${1:?usage: run_sv_mode_series.sh <samplesheet.csv> <outdir-prefix> [workdir]}"
PREFIX="${2:?missing outdir prefix}"
REPO=/home/azureuser/Docs/ALE_nextflow
WORK="${3:-${REPO}/work_sv_modes}"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env
export NXF_VER=25.10.4
cd "${REPO}"

base=(-profile azureD4as,docker -w "${WORK}" --step variant_calling --input "${SHEET}"
      --genome null --igenomes_ignore
      --fasta "${REPO}/data/ottilie/S288C_reference/S288C_R64.fa"
      --tools manta,tiddit --split_fastq 0 --generate_reports
      --report_gff3 "${REPO}/data/ottilie/S288C_reference/S288C_R64.gff3" -resume)

echo "== per-sample Manta =="
nextflow run "${REPO}/main.nf" "${base[@]}" --joint_manta false --outdir "${PREFIX}_persample"
echo "== joint Manta, default settings =="
nextflow run "${REPO}/main.nf" "${base[@]}" --joint_manta        --outdir "${PREFIX}_jointdefault"
echo "== joint Manta, high sensitivity =="
nextflow run "${REPO}/main.nf" "${base[@]}" --joint_manta --manta_high_sensitivity \
                                                          --outdir "${PREFIX}_joinths"

echo
echo "Score the three tables with:"
echo "  python $(dirname "$0")/compare_sv_pass_tables.py --parent NODRUG-GM2 \\"
echo "      --mode \"per-sample=${PREFIX}_persample\" \\"
echo "      --mode \"joint default=${PREFIX}_jointdefault\" \\"
echo "      --mode \"joint high-sens=${PREFIX}_joinths\""
