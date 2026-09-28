#!/usr/bin/env bash
# yAMP preflight, task level: do the reference files handed to the pipeline agree with each other?
#
# Runs inside PREFLIGHT_REFERENCE (modules/local/preflight_reference) — a task rather than a
# DAG-build check, so cloud paths are staged like any other input. User page:
# docs/usage/preflight_checks.md.
#
# One check today, one row in the MultiQC table this writes. A new check is a new function below,
# one more verdict row, and a fixture pair under tests/fixtures/preflight_reference/.
#
#   FASTA vs GFF3 contig names — the GFF3 given as --report_gff3 is the gene track of the mutation
#     report, so its contig names must be the FASTA's. ERROR when the two share no name: the track
#     would be empty and nothing downstream would complain. Otherwise OK; when some GFF3 contigs have
#     no FASTA sequence the row says which — their features are simply not shown, the normal picture
#     for a chromosome-subset reference (the release test set is one: 4 chromosomes against the
#     full-genome GFF3). FASTA contigs without annotation (cassettes, plasmids) are not reported.
#     Both deliberate (decision 2026-09-28: ship the case that is silent today, refine when a real
#     input error shows the need — e.g. a partial naming mismatch such as Mito vs chrM). Same
#     no-shared-name rule as docs/prepare_input/build_snpeff_cache.sh applies to the cache build.
#     An embedded ##FASTA section (SGD and GenBank-converted GFF3 files) is ignored.
#
# Console: verdict lines only (ERROR — and WARN, should a future check use it — prefixed
# [yAMP preflight]). A clean reference prints nothing, so "no [yAMP preflight] line" keeps meaning
# "clean". Exit 0 on OK / WARN / SKIPPED, 65
# (EX_DATAERR) on ERROR — outside the pipeline's retry range (130–145, 104); the process's
# errorStrategy is 'terminate' (conf/modules/preflight.config).
#
# Usage: preflight_reference.sh --fasta ref.fa [--gff3 genes.gff3] [--out preflight_reference_mqc.tsv]

set -euo pipefail

fasta='' gff3='' out='preflight_reference_mqc.tsv'
while [[ $# -gt 0 ]]; do
    case "$1" in
        --fasta) fasta=$2; shift 2 ;;
        --gff3)  gff3=$2;  shift 2 ;;
        --out)   out=$2;   shift 2 ;;
        *) echo "preflight_reference.sh: unknown argument '$1'" >&2; exit 2 ;;
    esac
done
[[ -n "$fasta" ]] || { echo "preflight_reference.sh: --fasta is required" >&2; exit 2; }
[[ -r "$fasta" ]] || { echo "preflight_reference.sh: cannot read FASTA '$fasta'" >&2; exit 2; }
[[ -z "$gff3" || -r "$gff3" ]] || { echo "preflight_reference.sh: cannot read GFF3 '$gff3'" >&2; exit 2; }

errors=0
rows=()

# verdict STATUS CHECK DETAIL — one table row; WARN and ERROR also go to the console (ERROR to stderr too)
verdict() {
    local status=$1 check=$2 detail=$3
    rows+=("${check}"$'\t'"${status}"$'\t'"${detail}")
    case "$status" in
        WARN)  echo "[yAMP preflight] WARN  ${check}: ${detail}" ;;
        ERROR) echo "[yAMP preflight] ERROR ${check}: ${detail}"
               echo "[yAMP preflight] ERROR ${check}: ${detail}" >&2
               errors=$((errors + 1)) ;;
    esac
}

# Contig names, sorted unique (for comm). FASTA: the first token of each header line.
# GFF3: column 1 of the feature lines, stopping at an embedded ##FASTA section.
fasta_contigs() { gawk '/^>/ { sub(/^>/, ""); print $1 }' "$1" | sort -u; }
gff3_contigs()  { gawk -F '\t' '/^##FASTA/ { exit } /^#/ || /^[[:space:]]*$/ { next } { print $1 }' "$1" | sort -u; }

# list FILE — the first 10 names of a one-per-line file, comma separated, "…" when there are more
list() {
    local n s
    n=$(wc -l < "$1")
    s=$(head -n 10 "$1" | paste -sd ',' - | sed 's/,/, /g')
    (( n > 10 )) && s="${s}, …"
    printf '%s' "$s"
}

check_fasta_vs_gff3() {
    local check='FASTA vs GFF3 contig names'
    if [[ -z "$gff3" ]]; then
        verdict SKIPPED "$check" "--report_gff3 not set: the mutation report has no gene track, nothing to compare"
        return
    fi
    local fa_name gff_name n_fasta n_gff3 n_shared n_missing
    fa_name=$(basename "$fasta"); gff_name=$(basename "$gff3")
    fasta_contigs "$fasta" > fasta.contigs
    gff3_contigs  "$gff3"  > gff3.contigs
    comm -13 fasta.contigs gff3.contigs > gff3_only.contigs
    n_fasta=$(wc -l < fasta.contigs); n_gff3=$(wc -l < gff3.contigs)
    n_shared=$(comm -12 fasta.contigs gff3.contigs | wc -l); n_missing=$(wc -l < gff3_only.contigs)

    if (( n_gff3 == 0 )); then
        verdict ERROR "$check" "no feature line in ${gff_name} (comments only, or empty): the gene track of the mutation report would be empty"
    elif (( n_shared == 0 )); then
        verdict ERROR "$check" "none of the ${n_gff3} contig name(s) in ${gff_name} ($(list gff3.contigs)) is a contig of ${fa_name} ($(list fasta.contigs)): the gene track of the mutation report would be empty. Rename the contigs of one file to the other's convention (docs/usage/prepare_reference.md)"
    elif (( n_missing > 0 )); then
        verdict OK "$check" "${n_shared} of ${n_fasta} FASTA contig(s) annotated; ${n_missing} of ${n_gff3} contig name(s) in ${gff_name} have no sequence in ${fa_name} ($(list gff3_only.contigs)) — their features are not shown, as expected for a chromosome-subset reference"
    else
        verdict OK "$check" "all ${n_gff3} contig name(s) of ${gff_name} are contigs of ${fa_name} (${n_fasta} contigs)"
    fi
}

check_fasta_vs_gff3

{
    cat <<'HEADER'
# id: 'yamp_preflight_reference'
# section_name: 'yAMP preflight: reference'
# description: "Do the reference files handed to the pipeline agree with each other? Checked at the start of the run, before alignment (docs/usage/preflight_checks.md). ERROR stops the run; WARN and ERROR lines are also printed on the console with the [yAMP preflight] prefix."
# plot_type: 'table'
# pconfig:
#     id: 'yamp_preflight_reference_table'
#     namespace: 'yAMP preflight'
#     sort_rows: false
# headers:
#     status:
#         title: 'Status'
#         description: 'OK, WARN, ERROR or SKIPPED'
#     detail:
#         title: 'Detail'
#         description: 'What was compared and what was found'
HEADER
    printf 'Check\tstatus\tdetail\n'
    printf '%s\n' "${rows[@]}"
} > "$out"

if (( errors > 0 )); then
    echo "[yAMP preflight] ${errors} reference check(s) failed — stopping the run (table: ${out})" >&2
    exit 65
fi
