#!/usr/bin/env bash
# Joint vs per-sample Manta audit at cohort scale — regenerates manta_joint_at_scale{,_hs}/
#
# Compares one joint Manta call against the per-sample calls made from the SAME CRAMs, per sample:
# which per-sample PASS records survive into the joint VCF, which joint-only genotypes appear, and
# how breakpoints and per-sample evidence shift. Writes summary.tsv (committed) + details_<sample>.tsv (not
# committed — this script is the record of how to remake them).
#
# The joint VCFs come from runs made with `--step variant_calling --tools manta [--joint_manta]`
# over the 86 Tier-2 md.crams; the per-sample baseline is the Tier-2 pipeline output.
#
# REGENERATION IS VERIFIED, NOT ASSUMED (2026-09-07): re-running this against the retained inputs
# reproduced all 86 details_*.tsv plus summary.tsv BYTE-IDENTICALLY. That is why the details are
# deleted and gitignored rather than committed.
#
# ⚠️ It needs THREE input sets kept on disk. Delete or archive any of them and the details stop being
# locally regenerable:
#     output_ottilie_tier2/variant_calling/manta/*/   86 per-sample baseline VCFs
#     output_manta_joint_test/                        joint Manta, default settings
#     output_manta_joint_test_hs/                     joint Manta, --manta_high_sensitivity
# 2026-09-09: output_ottilie_tier2/preprocessing/ (the 86 CRAMs + indexes, 43 GB) was ARCHIVED to
# az://aledata/Yeast/archive-projects/ottilie_tier2/preprocessing/ (Cool tier, file by file) and
# deleted locally; variant_calling/manta/ and the rest (~1 GB) stay on disk. The CRAMs are the input
# of this script and of make_cohort_samplesheet.py -- restore them first:
#     azcopy copy "https://aledata.blob.core.windows.net/aledata/Yeast/archive-projects/ottilie_tier2/preprocessing" output_ottilie_tier2/ --recursive   # after `azcopy login`; Cool tier, ~43 GB
# Findings: manta_joint_at_scale/REPORT.md · guidance: docs/variant-calling/manta/manta_calling_modes.md
#
# Usage: bash run_manta_joint_at_scale.sh [default|hs|both]     (default: both)
set -euo pipefail

REPO=/home/azureuser/Docs/ALE_nextflow
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-both}"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate "${REPO}/../../miniforge3/envs/nf-env" 2>/dev/null || conda activate nf-env
cd "${REPO}"

# per-sample baseline: one --single arg per Tier-2 sample
single_args=()
for d in output_ottilie_tier2/variant_calling/manta/*/; do
    s=$(basename "$d")
    v="${d}${s}.manta.diploid_sv.vcf.gz"
    [ -f "$v" ] && single_args+=(--single "${s}=${v}")
done
echo "per-sample baseline VCFs: $(( ${#single_args[@]} / 2 ))"

run_audit () {   # $1 = joint VCF dir, $2 = output dir
    python "${SCRIPT_DIR}/manta_joint_vs_single.py" \
        --joint "$1/Ottilie_tier2.manta.diploid_sv.vcf.gz" \
        --joint-sample-prefix Ottilie_tier2_ \
        "${single_args[@]}" \
        --out "$2"
}

if [ "$MODE" = default ] || [ "$MODE" = both ]; then
    echo "== default-settings joint Manta =="
    run_audit output_manta_joint_test/variant_calling/manta/Ottilie_tier2 \
              "${SCRIPT_DIR}/manta_joint_at_scale"
fi
if [ "$MODE" = hs ] || [ "$MODE" = both ]; then
    echo "== --manta_high_sensitivity joint Manta =="
    run_audit output_manta_joint_test_hs/variant_calling/manta/Ottilie_tier2 \
              "${SCRIPT_DIR}/manta_joint_at_scale_hs"
fi
