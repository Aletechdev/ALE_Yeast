#!/usr/bin/env bash
# Loss audit for --joint_manta on the 4-sample pilot: per-sample Manta (from the pilot pipeline
# output) vs one standalone joint Manta run over the same four --save_mapped CRAMs.
#
# The joint run is done here directly in the Manta container — no pipeline rerun — with the same
# inputs the pipeline uses: the pilot reference and one --callRegions interval per contig (what
# Sarek derives from the .fai when no --intervals is given). Output + audit tables go to
# pilot_results_v2/manta_joint_audit/. Results are discussed in pilot_results_v2/NOTES.md.
#
# MODE selects Manta's configuration for the joint run (all four are kept under
# manta_joint_audit/<MODE>/ — see NOTES.md for what each one showed):
#   default    Manta 1.6.0 defaults (= what MANTA_GERMLINE runs today)
#   noedgecap  graphNodeMaxEdgeCount = 0   (breakend-hub edge cap off)
#   exome      --exome                     (Manta's depth filters off; nothing else)
#   both       --exome + graphNodeMaxEdgeCount = 0
#   cap30      --exome + graphNodeMaxEdgeCount = 30  (identical output to `both` on the pilot; the proposed setting)
#
# Usage (repo root, docker available):  04_validate/run_manta_joint_audit_pilot.sh [MODE] [pilot_outdir]
set -euo pipefail
mode=${1:-default}

repo=$(cd "$(dirname "$0")/../../../.." && pwd)
pilot=${2:-$repo/output_ottilie_pilot_2026-08-26}
ref=$repo/data/ottilie/S288C_reference
here=$(cd "$(dirname "$0")" && pwd)
out=$here/pilot_results_v2/manta_joint_audit/$mode
work=$(mktemp -d)
samples=(NODRUG-GM2 Doxorubicin16-R2b Carmaphycin-R9-2 CBR110-15-R3a)

MANTA=quay.io/biocontainers/manta:1.6.0--h9ee0642_1              # = modules/nf-core/manta/germline
HTSLIB=community.wave.seqera.io/library/bcftools_htslib:0a3fa2654b52006f

mkdir -p "$out"
awk 'BEGIN{OFS="\t"}{print $1,0,$2}' "$ref/S288C_R64.fa.fai" > "$work/callregions.bed"
docker run --rm -v "$work:/d" -w /d "$HTSLIB" sh -c 'bgzip -f callregions.bed && tabix -f -p bed callregions.bed.gz'

extra=""
case "$mode" in
    default)   ;;
    noedgecap) extra="--config manta_noedgecap.ini" ;;
    exome)     extra="--exome" ;;
    both)      extra="--exome --config manta_noedgecap.ini" ;;
    cap30)     extra="--exome --config manta_cap30.ini" ;;
    *) echo "unknown MODE $mode" >&2; exit 2 ;;
esac
# Manta's own default ini with the edge cap switched off (only knob changed).
docker run --rm "$MANTA" sh -c 'cat $(dirname $(readlink -f $(which configManta.py)))/configManta.py.ini' \
    | sed -E 's/^graphNodeMaxEdgeCount = 10$/graphNodeMaxEdgeCount = 0/' > "$work/manta_noedgecap.ini"
grep -q '^graphNodeMaxEdgeCount = 0$' "$work/manta_noedgecap.ini"
sed -E 's/^graphNodeMaxEdgeCount = 0$/graphNodeMaxEdgeCount = 30/' "$work/manta_noedgecap.ini" > "$work/manta_cap30.ini"

bams=(); for s in "${samples[@]}"; do bams+=(--bam "/cram/$s/$s.sorted.cram"); done
docker run --rm -v "$work:/d" -v "$ref:/ref:ro" -v "$pilot/preprocessing/mapped:/cram:ro" -w /d "$MANTA" \
    sh -c "configManta.py $extra ${bams[*]} --reference /ref/S288C_R64.fa --runDir manta --callRegions callregions.bed.gz \
           && python manta/runWorkflow.py -m local -j 4"
cp "$work/manta/results/variants/diploidSV.vcf.gz"     "$out/Ottilie_pilot.manta.diploid_sv.vcf.gz"
cp "$work/manta/results/variants/diploidSV.vcf.gz.tbi" "$out/Ottilie_pilot.manta.diploid_sv.vcf.gz.tbi"

singles=(); for s in "${samples[@]}"; do singles+=(--single "$s=$pilot/variant_calling/manta/$s/$s.manta.diploid_sv.vcf.gz"); done
python "$here/manta_joint_vs_single.py" \
    --joint "$out/Ottilie_pilot.manta.diploid_sv.vcf.gz" "${singles[@]}" \
    --joint-sample-prefix Ottilie_pilot_ --out "$out"

rm -rf "$work"
echo "audit tables: $out/summary.tsv, $out/details_<sample>.tsv"
