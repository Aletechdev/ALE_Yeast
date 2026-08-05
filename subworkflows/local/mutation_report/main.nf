/*
 * MUTATION_REPORT — Generate multi-caller mutation report dashboard
 *
 * Integrates CN/SV data generation, igv-reports HTML, and index dashboard
 * into a single subworkflow that runs after the main Sarek pipeline.
 *
 * Gated behind --generate_reports in workflows/sarek/main.nf (inline, clean-run correct)
 * or launched standalone via generate_mutation_report.nf (rebuilds channels from disk).
 *
 * CHANNEL-BASED: consumes pipeline OUTPUT CHANNELS (workdir files, DAG-ordered)
 * instead of re-reading published files from params.outdir — no publishDir race.
 */

include { PREPARE_GFF3       } from '../../../modules/local/prepare_gff3/main'
include { PREPARE_VCF        } from '../../../modules/local/prepare_vcf/main'
include { IGVREPORTS_COHORT  } from '../../../modules/local/igvreports_cohort/main'
include { IGVREPORTS_SAMPLE  } from '../../../modules/local/igvreports_sample/main'
include { IGVREPORTS_SV_CNV  } from '../../../modules/local/igvreports_sv_cnv/main'
include { CNR_TO_BEDGRAPH    } from '../../../modules/local/cnr_to_bedgraph/main'
include { FILTER_PASS_VCF    } from '../../../modules/local/filter_pass_vcf/main'
include { PUBLISH_VCFS       } from '../../../modules/local/publish_vcfs/main'
include { GENERATE_INDEX     } from '../../../modules/local/generate_index/main'
include { BUILD_CN_MATRIX    } from '../../../modules/local/build_cn_matrix/main'
include { BUILD_CN_COHORT    } from '../../../modules/local/build_cn_cohort/main'
include { BCFTOOLS_VIEW as FILTER_SV_VCF_MANTA  } from '../../../modules/nf-core/bcftools/view/main'
include { BCFTOOLS_VIEW as FILTER_SV_VCF_TIDDIT } from '../../../modules/nf-core/bcftools/view/main'
include { BCFTOOLS_VIEW as DECOMPRESS_SV_MANTA  } from '../../../modules/nf-core/bcftools/view/main'
include { BCFTOOLS_VIEW as DECOMPRESS_SV_TIDDIT } from '../../../modules/nf-core/bcftools/view/main'
include { SURVIVOR_SV_MERGE as SURVIVOR_SV_MERGE_PASS  } from '../../../modules/local/survivor_sv_merge/main'
include { SURVIVOR_SV_MERGE as SURVIVOR_SV_MERGE_UNION } from '../../../modules/local/survivor_sv_merge/main'
include { TABIX_BGZIPTABIX as BGZIPTABIX_SV_PASS  } from '../../../modules/nf-core/tabix/bgziptabix/main'
include { TABIX_BGZIPTABIX as BGZIPTABIX_SV_UNION } from '../../../modules/nf-core/tabix/bgziptabix/main'
include { SURVIVOR_COHORT_MERGE as SURVIVOR_COHORT_MERGE_PASS  } from '../../../modules/local/survivor_cohort_merge/main'
include { SURVIVOR_COHORT_MERGE as SURVIVOR_COHORT_MERGE_UNION } from '../../../modules/local/survivor_cohort_merge/main'
include { BUILD_SV_MATRIX as BUILD_SV_MATRIX_PASS  } from '../../../modules/local/build_sv_matrix/main'
include { BUILD_SV_MATRIX as BUILD_SV_MATRIX_UNION } from '../../../modules/local/build_sv_matrix/main'

workflow MUTATION_REPORT {
    take:
    report_vcfs         // channel: [ meta, vcf, tbi ]  combined annotated-or-raw VCFs for IGV reports;
                        //          meta carries variantcaller + (for HC) hc_kind. Branched internally.
    cram                // channel: [ meta, cram, crai ]  per-sample alignments (meta.id = sample)
    vcf_manta_raw       // channel: [ meta, vcf ]  RAW manta (SURVIVOR SV merge — always raw, see D4)
    vcf_tiddit_raw      // channel: [ meta, vcf ]  RAW tiddit (SURVIVOR SV merge — always raw, see D4)
    cnvkit_cnr          // channel: [ meta, .md.cnr ]  bin-level coverage (bedgraph + CN matrix)
    cnvkit_cns_batch    // channel: [ meta, [*.cns] ]   batch segments incl .md.call.cns (CN matrix)
    cnvkit_cns_germline // channel: [ meta, .md.germline.call.cns ]  CI-filtered segments (CN matrix)
    multiqc_data        // channel: MultiQC *_data dir (GENERATE_INDEX metrics)
    multiqc_report      // channel: MultiQC report file(s) — ordering edge + linked from index.html
    fasta               // channel: value [ path(fasta), path(fai) ]
    gff3                // path:     gene annotation GFF3

    main:
    versions = Channel.empty()

    // =========================================================================
    // 1. Tool availability — from params (param reads, NOT path reads: no race)
    // =========================================================================

    def tool_list = params.tools ? params.tools.split(',').collect { it.trim() } : []
    def has_cnvkit          = tool_list.contains('cnvkit')
    def has_manta           = tool_list.contains('manta')
    def has_tiddit          = tool_list.contains('tiddit')
    def has_haplotypecaller = tool_list.contains('haplotypecaller')

    if (!has_haplotypecaller) {
        log.warn "MUTATION_REPORT: haplotypecaller not in params.tools — " +
                 "cohort and per-sample SNV/INDEL reports will be skipped."
    }
    if (!has_manta && !has_tiddit) {
        log.warn "MUTATION_REPORT: neither manta nor tiddit in params.tools — " +
                 "SV reports and SV cohort matrix will be skipped."
    }
    if (!has_cnvkit) {
        log.warn "MUTATION_REPORT: cnvkit not in params.tools — " +
                 "CN matrix, coverage reports, and aneuploidy section will be skipped."
    }

    // =========================================================================
    // 2. GFF3 preparation + static report assets (pipeline assets, not outputs)
    // =========================================================================

    // The gene track is OPTIONAL. With --report_gff3 unset, skip the sort/bgzip/tabix step
    // and feed the downstream `tuple path(gff3_gz), path(gff3_tbi)` a pair of empty lists —
    // the Nextflow idiom for an absent optional path. Both render falsy in the module script
    // blocks, which then drop the track from --tracks.
    //
    // `[]` declares no file at all, so nothing has to stage (or exist) on a remote work dir —
    // the same idiom used for the absent coverage tracks below.
    if (params.report_gff3) {
        PREPARE_GFF3(gff3)
        ch_gff3_indexed = PREPARE_GFF3.out.gff3
        versions = versions.mix(PREPARE_GFF3.out.versions)
    } else {
        log.warn "MUTATION_REPORT: --report_gff3 not set — reports will be generated " +
                 "WITHOUT the gene annotation track."
        ch_gff3_indexed = Channel.value([ [], [] ])
    }

    ch_fasta = fasta                        // value channel: [ path(fasta), path(fai) ]
    ch_fai   = fasta.map { it[1] }           // value channel: path(fai)

    ch_filter_config   = Channel.value(file(params.report_filter_config))
    ch_template        = Channel.value(file(params.report_cohort_template))
    ch_sample_template = Channel.value(file(params.report_sample_template))
    ch_index_script    = Channel.value(file(params.report_index_script))
    ch_templates_dir   = Channel.value(file(params.report_templates_dir))

    // =========================================================================
    // 3. Reconstruct per-caller VCF channels from the combined input channel
    // =========================================================================
    //
    // Branch on channel metadata (variantcaller + hc_kind), NOT filenames. Defensive:
    //   - joint HC (hc_kind == 'joint')     → cohort report
    //   - hard-filtered HC (sample_hard)    → dropped (report uses soft, per generate_index.py)
    //   - any other HC (soft/single/absent) → per-sample report
    //   - cnvkit / manta / tiddit           → SV/CNV reports
    // Any non-report caller (freebayes, mutect2, deepvariant, …) is filtered out here, so the
    // caller can pass the whole annotated/raw VCF channel without pre-filtering.

    ch_report_known = report_vcfs
        .filter { meta, vcf, tbi ->
            meta.variantcaller in ['haplotypecaller', 'cnvkit', 'manta', 'tiddit'] &&
            !(meta.variantcaller == 'haplotypecaller' && meta.hc_kind == 'sample_hard')
        }
        .map { meta, vcf, tbi ->
            def rmeta
            if (meta.variantcaller == 'haplotypecaller' && meta.hc_kind == 'joint') {
                rmeta = [ id: 'cohort',  caller: 'haplotypecaller', caller_label: 'HaplotypeCaller' ]
            } else if (meta.variantcaller == 'haplotypecaller') {
                rmeta = [ id: meta.id,   caller: 'haplotypecaller', caller_label: 'HaplotypeCaller' ]
            } else if (meta.variantcaller == 'cnvkit') {
                rmeta = [ id: meta.id,   caller: 'cnvkit',          caller_label: 'CNVKit' ]
            } else if (meta.variantcaller == 'manta') {
                rmeta = [ id: meta.id,   caller: 'manta',           caller_label: 'Manta' ]
            } else {
                rmeta = [ id: meta.id,   caller: 'tiddit',          caller_label: 'TIDDIT' ]
            }
            [ rmeta, vcf, tbi ]
        }

    ch_report_known
        .branch {
            joint:     it[0].id == 'cohort'
            cnvkit:    it[0].caller == 'cnvkit'
            manta:     it[0].caller == 'manta'
            tiddit:    it[0].caller == 'tiddit'
            hc_sample: true                       // remaining = per-sample haplotypecaller
        }
        .set { ch_caller }

    ch_joint_vcf      = ch_caller.joint
    ch_sample_hc_vcfs = ch_caller.hc_sample
    ch_cnvkit_vcfs    = ch_caller.cnvkit
    ch_manta_vcfs     = ch_caller.manta
    ch_tiddit_vcfs    = ch_caller.tiddit

    // Per-sample CRAM lookup keyed by sample id (join, no params.outdir reads)
    ch_cram_by_id = cram.map { meta, c, crai -> [ meta.id, c, crai ] }

    // =========================================================================
    // 4. CN matrix generation (CNVKit) — collected files staged into per-sample dirs
    // =========================================================================

    if (has_cnvkit) {
        // Collect the three per-sample CN files build_cn_matrix.py reads:
        //   .md.cnr (batch), .md.call.cns (in batch .cns list), .md.germline.call.cns (call)
        ch_cn_files = cnvkit_cnr.map { meta, f -> f }
            .mix(cnvkit_cns_batch.flatMap { meta, f -> f instanceof List ? f : [f] })
            .mix(cnvkit_cns_germline.map { meta, f -> f })
            .collect()
            .map { files -> [ [ id: 'all_samples' ], files ] }

        BUILD_CN_MATRIX(ch_cn_files, ch_fai)
        versions = versions.mix(BUILD_CN_MATRIX.out.versions)

        BUILD_CN_COHORT(BUILD_CN_MATRIX.out.cn_matrices.map { meta, dir -> dir }, ch_fai)
        versions = versions.mix(BUILD_CN_COHORT.out.versions)

        ch_cn_data = BUILD_CN_COHORT.out.collapsed
            .mix(BUILD_CN_COHORT.out.full)
            .mix(BUILD_CN_MATRIX.out.chr_summary)
            .collect()
    } else {
        ch_cn_data = Channel.empty()
    }

    // =========================================================================
    // 5. SV merge + cohort matrix (Manta/TIDDIT) — RAW inputs (SURVIVOR drops FILTER/ANN, D4)
    // =========================================================================

    if (has_manta && has_tiddit) {
        // bcftools view (-f PASS -Ov / -Ov) streams — no index needed, pass [] for the index slot.
        ch_sv_manta_raw  = vcf_manta_raw.map  { meta, vcf -> [ [ id: meta.id, caller: 'manta'  ], vcf, [] ] }
        ch_sv_tiddit_raw = vcf_tiddit_raw.map { meta, vcf -> [ [ id: meta.id, caller: 'tiddit' ], vcf, [] ] }

        // PASS-filter both callers
        FILTER_SV_VCF_MANTA(ch_sv_manta_raw, [], [], [])
        FILTER_SV_VCF_TIDDIT(ch_sv_tiddit_raw, [], [], [])
        versions = versions.mix(FILTER_SV_VCF_MANTA.out.versions)

        // Decompress raw VCFs (no PASS filter) for unfiltered union merge
        DECOMPRESS_SV_MANTA(ch_sv_manta_raw, [], [], [])
        DECOMPRESS_SV_TIDDIT(ch_sv_tiddit_raw, [], [], [])

        // Pair Manta + TIDDIT per sample for SURVIVOR merge (PASS-filtered)
        ch_manta_filtered  = FILTER_SV_VCF_MANTA.out.vcf.map  { meta, vcf -> [ meta.id, vcf ] }
        ch_tiddit_filtered = FILTER_SV_VCF_TIDDIT.out.vcf.map { meta, vcf -> [ meta.id, vcf ] }

        ch_sv_paired_pass = ch_manta_filtered
            .join(ch_tiddit_filtered)
            .map { id, manta_vcf, tiddit_vcf -> [ [ id: id, merge_mode: 'union_pass' ], manta_vcf, tiddit_vcf ] }

        // Pair raw (unfiltered) for union merge
        ch_manta_raw_vcf  = DECOMPRESS_SV_MANTA.out.vcf.map  { meta, vcf -> [ meta.id, vcf ] }
        ch_tiddit_raw_vcf = DECOMPRESS_SV_TIDDIT.out.vcf.map { meta, vcf -> [ meta.id, vcf ] }

        ch_sv_paired_union = ch_manta_raw_vcf
            .join(ch_tiddit_raw_vcf)
            .map { id, manta_vcf, tiddit_vcf -> [ [ id: id, merge_mode: 'union' ], manta_vcf, tiddit_vcf ] }

        SURVIVOR_SV_MERGE_PASS(ch_sv_paired_pass)
        SURVIVOR_SV_MERGE_UNION(ch_sv_paired_union)
        versions = versions.mix(SURVIVOR_SV_MERGE_PASS.out.versions)

        BGZIPTABIX_SV_PASS(SURVIVOR_SV_MERGE_PASS.out.vcf)
        BGZIPTABIX_SV_UNION(SURVIVOR_SV_MERGE_UNION.out.vcf)
        versions = versions.mix(BGZIPTABIX_SV_PASS.out.versions)

        ch_pass_plain  = SURVIVOR_SV_MERGE_PASS.out.vcf.map  { meta, vcf -> vcf }.collect()
        ch_union_plain = SURVIVOR_SV_MERGE_UNION.out.vcf.map { meta, vcf -> vcf }.collect()

        SURVIVOR_COHORT_MERGE_PASS(ch_pass_plain, 'union_pass')
        SURVIVOR_COHORT_MERGE_UNION(ch_union_plain, 'union')
        versions = versions.mix(SURVIVOR_COHORT_MERGE_PASS.out.versions)

        BUILD_SV_MATRIX_PASS(SURVIVOR_COHORT_MERGE_PASS.out.vcf, ch_pass_plain, 'union_pass')
        BUILD_SV_MATRIX_UNION(SURVIVOR_COHORT_MERGE_UNION.out.vcf, ch_union_plain, 'union')
        versions = versions.mix(BUILD_SV_MATRIX_PASS.out.versions)

        ch_sv_data = BUILD_SV_MATRIX_PASS.out.csv
            .mix(BUILD_SV_MATRIX_UNION.out.csv)
            .collect()
    } else {
        ch_sv_data = Channel.empty()
    }

    // =========================================================================
    // 6. TIDDIT PASS filtering (for per-sample reports)
    // =========================================================================

    if (has_tiddit) {
        FILTER_PASS_VCF(ch_tiddit_vcfs)
        ch_tiddit_pass = FILTER_PASS_VCF.out.vcf
        ch_pass_stats  = FILTER_PASS_VCF.out.stats.collect().ifEmpty(file("NO_FILE"))
        versions = versions.mix(FILTER_PASS_VCF.out.versions)
    } else {
        ch_tiddit_pass = Channel.empty()
        ch_pass_stats  = Channel.value(file("NO_FILE"))
    }

    // =========================================================================
    // 7. Publish pre-norm annotated VCFs
    // =========================================================================

    if (has_haplotypecaller) {
        PUBLISH_VCFS(
            ch_joint_vcf,
            ch_sample_hc_vcfs.map { meta, vcf, tbi -> [ vcf, tbi ] }.collect(),
            has_cnvkit ? ch_cnvkit_vcfs.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([]),
            has_manta  ? ch_manta_vcfs.flatMap  { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([]),
            has_tiddit ? ch_tiddit_vcfs.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([]),
            has_tiddit ? ch_tiddit_pass.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([])
        )
        versions = versions.mix(PUBLISH_VCFS.out.versions)
    }

    // =========================================================================
    // 8. Prepare VCFs for igv-reports (multi-allelic split, VAF, FILTER→INFO)
    // =========================================================================

    if (has_haplotypecaller) {
        ch_all_vcfs = ch_joint_vcf
            .mix(ch_sample_hc_vcfs)
            .mix(ch_cnvkit_vcfs)
            .mix(ch_manta_vcfs)
            .mix(has_tiddit ? ch_tiddit_pass : Channel.empty())

        ch_all_prepared = PREPARE_VCF(ch_all_vcfs)
        versions = versions.mix(PREPARE_VCF.out.versions)

        // Branch into cohort, HC sample, and SV/CNV channels
        ch_all_prepared.vcf.branch {
            cohort: it[0].id == 'cohort'
            sv_cnv: it[0].caller in ['cnvkit', 'manta', 'tiddit']
            sample: true
        }.set { ch_branched }

        // ---------------------------------------------------------------------
        // 9. Cohort report
        // ---------------------------------------------------------------------

        IGVREPORTS_COHORT(ch_branched.cohort, ch_gff3_indexed, ch_fasta, ch_filter_config, ch_template)
        versions = versions.mix(IGVREPORTS_COHORT.out.versions)

        // ---------------------------------------------------------------------
        // 10. Per-sample HaplotypeCaller reports (CRAM by channel join)
        // ---------------------------------------------------------------------

        // combine(by:0), NOT join: a sample may carry multiple report rows sharing meta.id,
        // and join is one-to-one (it would silently drop all but the first). combine matches
        // every row to its sample CRAM.
        ch_samples_with_cram = ch_branched.sample
            .map { meta, vcf, tbi -> [ meta.id, meta, vcf, tbi ] }
            .combine(ch_cram_by_id, by: 0)
            .map { id, meta, vcf, tbi, c, crai -> [ meta, vcf, tbi, c, crai ] }

        IGVREPORTS_SAMPLE(ch_samples_with_cram, ch_gff3_indexed, ch_fasta, ch_filter_config, ch_sample_template)
        versions = versions.mix(IGVREPORTS_SAMPLE.out.versions)

        // ---------------------------------------------------------------------
        // 11. CNVKit BedGraph + SV/CNV per-sample reports
        // ---------------------------------------------------------------------

        if (has_cnvkit) {
            CNR_TO_BEDGRAPH(cnvkit_cnr)
            ch_bedgraph_map = CNR_TO_BEDGRAPH.out.bedgraph
                .map { meta, depth_bg, log2_bg -> [ meta.id, depth_bg, log2_bg ] }
            versions = versions.mix(CNR_TO_BEDGRAPH.out.versions)
        }

        // Absent coverage tracks for callers with no CNVKit output. `[]` is the Nextflow
        // idiom for an optional path: it declares no file, so IGVREPORTS_SV_CNV sees a falsy
        // value and drops the track.
        //
        // Do NOT substitute a placeholder filename here. `file('NO_DEPTH_BG')` (no such file)
        // works on the local executor — Nextflow symlinks it, and `ln -s` to a missing target
        // succeeds — but with a remote work dir (az://, s3://) every input must be physically
        // copied, so FilePorter fails the task with:
        //     Can't stage file /path/NO_DEPTH_BG -- file does not exist
        // Found by the first Azure Batch run; the local test suite cannot catch it. `[]` has
        // nothing to stage and so avoids the problem entirely.
        no_depth_bg = []
        no_log2_bg  = []

        // combine(by:0), NOT join: sv_cnv carries cnvkit + manta + tiddit per sample (same meta.id).
        // join is one-to-one and would drop all but one caller per sample; combine attaches the
        // sample CRAM to every caller's row.
        ch_sv_cnv_with_cram = ch_branched.sv_cnv
            .map { meta, vcf, tbi -> [ meta.id, meta, vcf, tbi ] }
            .combine(ch_cram_by_id, by: 0)
            .map { id, meta, vcf, tbi, c, crai -> [ meta, vcf, tbi, c, crai ] }

        if (has_cnvkit) {
            ch_sv_cnv_with_cram.branch {
                cnvkit: it[0].caller == 'cnvkit'
                other: true
            }.set { ch_sv_cnv_branched }

            ch_cnvkit_with_bg = ch_sv_cnv_branched.cnvkit
                .map { meta, vcf, tbi, c, crai -> [ meta.id, meta, vcf, tbi, c, crai ] }
                .join(ch_bedgraph_map)
                .map { id, meta, vcf, tbi, c, crai, depth_bg, log2_bg ->
                    [ meta, vcf, tbi, c, crai, depth_bg, log2_bg ]
                }

            ch_other_sv = ch_sv_cnv_branched.other
                .map { meta, vcf, tbi, c, crai ->
                    [ meta, vcf, tbi, c, crai, no_depth_bg, no_log2_bg ]
                }

            ch_sv_cnv_all = ch_cnvkit_with_bg.mix(ch_other_sv)
        } else {
            ch_sv_cnv_all = ch_sv_cnv_with_cram
                .map { meta, vcf, tbi, c, crai ->
                    [ meta, vcf, tbi, c, crai, no_depth_bg, no_log2_bg ]
                }
        }

        IGVREPORTS_SV_CNV(ch_sv_cnv_all, ch_gff3_indexed, ch_fasta, ch_sample_template)
        versions = versions.mix(IGVREPORTS_SV_CNV.out.versions)

        // ---------------------------------------------------------------------
        // 12. Generate index.html dashboard
        // ---------------------------------------------------------------------

        ch_cnv_sv_data = ch_cn_data
            .mix(ch_sv_data)
            .mix(ch_pass_stats)
            .collect()
            .ifEmpty(file("NO_FILE"))

        ch_all_sample_reports = IGVREPORTS_SAMPLE.out.report
            .mix(IGVREPORTS_SV_CNV.out.report)
            .collect()

        ch_prepared_cohort_vcf = ch_branched.cohort.map { meta, vcf, tbi -> vcf }

        // MULTIQC.out.report is emitted as .toList() upstream → each emission is a list:
        // [] when skipped, or [report.html] otherwise.
        ch_multiqc_report = multiqc_report
            .map { rep ->
                def r = rep instanceof List ? rep : [rep]
                r ? file(r[0]) : file("NO_FILE")
            }
            .ifEmpty(file("NO_FILE"))

        GENERATE_INDEX(
            IGVREPORTS_COHORT.out.report.collect(),
            ch_all_sample_reports,
            multiqc_data,
            ch_index_script,
            ch_templates_dir,
            ch_cnv_sv_data,
            ch_multiqc_report,
            ch_prepared_cohort_vcf.collect()
        )
        versions = versions.mix(GENERATE_INDEX.out.versions)

        ch_report_index = GENERATE_INDEX.out.index

    } else {
        ch_report_index = Channel.empty()
    }

    emit:
    report_index = ch_report_index
    versions     = versions
}
