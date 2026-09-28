#!/bin/bash
# Doc-drift check: the docs that COPY something derivable from the tree must agree with the tree.
#
# Why (2026-09-28): a feature commit updated every doc its plan named and still left five copies
# stale — two module inventories, the unit-test map's prose copy, an "all modules untested" claim
# and the known-differences table — because the doc list came from the plan, not from the diff.
# Everything below is derived from the tree and compared with its documented copy, so a new module,
# config, test or doc cannot be committed without its row. What needs judgement (prose a change
# makes false, a count quoted in several docs) is the commit-review skill's job
# (.claude/skills/commit-review/SKILL.md); this script decides only what a script can decide.
#
#   bin/check_doc_drift.sh          exit 0 = in sync; 2 = drift, one "DRIFT: <file>: <fix>" line each
#
# Run by bin/check_snapshot_staged.sh on every commit (milliseconds). It reads the WORKING TREE, so
# stage the fix it asks for. Checks:
#   1. modules/local/, subworkflows/local/, conf/ — every fork-added path (one upstream sarek 3.5.1
#      does not ship) is a row of the matching "ADDED" table in SAREK_MODIFICATIONS.md, every row
#      names an existing path, and the counts in the section heading and in the Summary table equal
#      the row count. A row is `| `<name>` | ... |`, the name written as below: a directory's
#      basename, or a conf file's path relative to conf/.
#   2. tests/ — every nextflow_process / nextflow_workflow test is a value of the commit gate's
#      TESTMAP (so its "Module test: <name> green" trailer is demanded), every TESTMAP path and test
#      exists, and every tests/*.nf.test is named in testing_best_practices.md (§11 layer table).
#   3. docs/ — every docs/usage/*.md and docs/dev-practices/*.md is linked from docs/README.md.
set -u
cd "$(git rev-parse --show-toplevel)" || exit 1

MODS=docs/dev-practices/SAREK_MODIFICATIONS.md
TESTING=docs/dev-practices/testing_best_practices.md
INDEX=docs/README.md
GATE=bin/check_snapshot_staged.sh

# What upstream sarek 3.5.1 ships in the directories the fork adds to — the GitHub listing of tag
# 3.5.1, taken 2026-09-28. Re-derive at a rebase:
#   curl -s "https://api.github.com/repos/nf-core/sarek/contents/<dir>?ref=<tag>" \
#     | python -c 'import json,sys; print(" ".join(e["name"] for e in json.load(sys.stdin)))'
UPSTREAM_MODULES_LOCAL='add_info_to_vcf create_intervals_bed samtools'
UPSTREAM_SUBWORKFLOWS_LOCAL='annotation_cache_initialisation bam_applybqsr bam_applybqsr_spark bam_baserecalibrator bam_baserecalibrator_spark bam_convert_samtools bam_joint_calling_germline_gatk bam_joint_calling_germline_sentieon bam_markduplicates bam_markduplicates_spark bam_merge_index_samtools bam_sentieon_dedup bam_variant_calling_cnvkit bam_variant_calling_deepvariant bam_variant_calling_freebayes bam_variant_calling_germline_all bam_variant_calling_germline_manta bam_variant_calling_haplotypecaller bam_variant_calling_indexcov bam_variant_calling_mpileup bam_variant_calling_sentieon_dnascope bam_variant_calling_sentieon_haplotyper bam_variant_calling_single_strelka bam_variant_calling_single_tiddit bam_variant_calling_somatic_all bam_variant_calling_somatic_ascat bam_variant_calling_somatic_controlfreec bam_variant_calling_somatic_manta bam_variant_calling_somatic_mutect2 bam_variant_calling_somatic_strelka bam_variant_calling_somatic_tiddit bam_variant_calling_tumor_only_all bam_variant_calling_tumor_only_controlfreec bam_variant_calling_tumor_only_lofreq bam_variant_calling_tumor_only_manta bam_variant_calling_tumor_only_mutect2 channel_align_create_csv channel_applybqsr_create_csv channel_baserecalibrator_create_csv channel_markduplicates_create_csv channel_variant_calling_create_csv cram_merge_index_samtools cram_qc_mosdepth_samtools cram_sampleqc download_cache_snpeff_vep fastq_align_bwamem_mem2_dragmap_sentieon fastq_create_umi_consensus_fgbio post_variantcalling prepare_genome prepare_intervals prepare_reference_cnvkit samplesheet_to_channel utils_nfcore_sarek_pipeline vcf_annotate_all vcf_annotate_bcftools vcf_concatenate_germline vcf_qc_bcftools_vcftools vcf_variant_filtering_gatk'
UPSTREAM_CONF='base.config igenomes.config igenomes_ignored.config test.config test_full.config test_full_germline.config test_full_germline_ncbench_agilent.config'
# conf/modules/<name>.config
UPSTREAM_CONF_MODULES='aligner alignment_to_fastq annotate ascat cnvkit controlfreec deepvariant download_cache freebayes haplotypecaller indexcov joint_germline lofreq manta markduplicates modules mpileup msisensorpro mutect2 ngscheckmate post_variant_calling prepare_genome prepare_intervals prepare_recalibration recalibrate sentieon_dedup sentieon_dnascope sentieon_dnascope_joint_germline sentieon_haplotyper sentieon_haplotyper_joint_germline strelka tiddit trimming umi'
# conf/test/<name>.config
UPSTREAM_CONF_TEST='alignment_from_everything alignment_to_fastq annotation no_intervals pair recalibrate_bam recalibrate_cram save_bam_mapped sentieon_dedup_bam sentieon_dedup_cram skip_bqsr skip_markduplicates split_fastq targeted tools tools_germline tools_germline_deepvariant tools_somatic tools_somatic_ascat tools_tumoronly trimming umi use_gatk_spark variantcalling_channels'

fail=0
drift() { fail=1; echo "DRIFT: $*" >&2; }
in_list() { local x=$1; shift; case " $* " in *" $x "*) return 0 ;; *) return 1 ;; esac; }

# --- 1. inventories -------------------------------------------------------------------------------
# rows of the table under an "ADDED" heading of SAREK_MODIFICATIONS.md: the first backticked cell
table_rows()    { awk -v h="$1" '$0 ~ h { p = 1; next } p && /^## / { exit } p && /^\| `/ { sub(/^\| `/, ""); sub(/`.*/, ""); print }' "$MODS"; }
heading_count() { grep -oE "$1[^0-9]*[0-9]+" "$MODS" | grep -oE '[0-9]+$' | head -1; }
summary_count() { grep -E "^\| \`$1\` \|" "$MODS" | head -1 | awk -F '|' '{ gsub(/ /, "", $3); print $3 }'; }

check_inventory() {   # label, heading regex, Summary-row key, then the fork-added names from the tree
    local label=$1 heading=$2 key=$3; shift 3
    local -a tree=("$@") rows=()
    mapfile -t rows < <(table_rows "$heading")
    if [ ${#rows[@]} -eq 0 ]; then drift "$MODS: no table rows under the heading /$heading/ ($label)"; return; fi
    local p
    for p in "${tree[@]}"; do in_list "$p" "${rows[@]}" || drift "$MODS: the $label ADDED table has no row for \`$p\` (in the tree, undocumented)"; done
    for p in "${rows[@]}"; do in_list "$p" "${tree[@]}" || drift "$MODS: $label ADDED table row \`$p\` names nothing in the tree (removed or renamed) — delete or fix the row"; done
    local n=${#rows[@]} h s
    h=$(heading_count "$heading"); s=$(summary_count "$key")
    [ "$h" = "$n" ] || drift "$MODS: the $label ADDED heading says ${h:-?}, the table has $n rows"
    [ "$s" = "$n" ] || drift "$MODS: the Summary row for \`$key\` says ${s:-?} added, the table has $n rows"
}

fork_modules=(); for d in modules/local/*/;      do n=$(basename "$d"); in_list "$n" $UPSTREAM_MODULES_LOCAL      || fork_modules+=("$n"); done
fork_subwfs=();  for d in subworkflows/local/*/; do n=$(basename "$d"); in_list "$n" $UPSTREAM_SUBWORKFLOWS_LOCAL || fork_subwfs+=("$n");  done
fork_conf=()
while IFS= read -r f; do
    rel=${f#conf/}
    case "$rel" in
        modules/*) in_list "$(basename "$rel" .config)" $UPSTREAM_CONF_MODULES || fork_conf+=("$rel") ;;
        test/*)    in_list "$(basename "$rel" .config)" $UPSTREAM_CONF_TEST    || fork_conf+=("$rel") ;;
        *)         in_list "$rel" $UPSTREAM_CONF                                || fork_conf+=("$rel") ;;
    esac
done < <(find conf -type f \( -name '*.config' -o -name '*.yml' \) | sort)

check_inventory 'modules/local/'      '^## `modules/local/` — ADDED'      'modules/local/'      "${fork_modules[@]}"
check_inventory 'subworkflows/local/' '^## `subworkflows/local/` — ADDED' 'subworkflows/local/' "${fork_subwfs[@]}"
check_inventory 'conf/'               '^## `conf/` — ADDED'               'conf/'               "${fork_conf[@]}"

# --- 2. tests vs the commit gate's TESTMAP and the testing guide ----------------------------------
mapped=()
while IFS= read -r e; do
    [ -z "$e" ] && continue
    p=$(sed -E "s/^\['([^']+)'\]=.*/\1/" <<<"$e"); t=${e##*=}
    [ -e "$p" ] || drift "$GATE: TESTMAP path '$p' does not exist"
    [ -f "tests/$t.nf.test" ] || drift "$GATE: TESTMAP names tests/$t.nf.test, which does not exist"
    mapped+=("$t")
done < <(grep -oE "\['[^']+'\]=[A-Za-z0-9_]+" "$GATE")
[ ${#mapped[@]} -gt 0 ] || drift "$GATE: no TESTMAP entries parsed (format changed?)"
for f in tests/*.nf.test; do
    t=$(basename "$f" .nf.test)
    kind=$(grep -m1 -oE '^nextflow_(process|workflow|pipeline|function)' "$f")
    case "$kind" in
        nextflow_process|nextflow_workflow)
            in_list "$t" "${mapped[@]}" || drift "$GATE: $f is a $kind test but no TESTMAP entry maps a path to '$t' (its 'Module test: $t green' trailer is never demanded)" ;;
    esac
    grep -qF -- "\`$t\`" "$TESTING" || drift "$TESTING: does not name \`$t\` (§11 layer table)"
done

# --- 3. docs index ---------------------------------------------------------------------------------
for f in docs/usage/*.md docs/dev-practices/*.md; do
    rel=${f#docs/}
    grep -qF -- "($rel)" "$INDEX" || drift "$INDEX: no link to $f"
done

if [ "$fail" -ne 0 ]; then
    echo "check_doc_drift: the tree and its documented copies disagree — fix each DRIFT line above and stage it (docs/dev-practices/testing_best_practices.md §12)." >&2
    exit 2
fi
exit 0
