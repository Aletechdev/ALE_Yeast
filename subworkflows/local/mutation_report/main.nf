/*
 * MUTATION_REPORT — Generate multi-caller mutation report dashboard
 *
 * Integrates CN/SV data generation, igv-reports HTML, and index dashboard
 * into a single subworkflow that runs after the main Sarek pipeline.
 *
 * Gated behind --generate_reports flag in main.nf.
 *
 * Auto-discovers VCF/CRAM paths from pipeline output using params.tools
 * and params.skip_tools (see Step 4 of the plan).
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
include { BUILD_SV_COHORT    } from '../../../modules/local/build_sv_cohort/main'

workflow MUTATION_REPORT {
    take:
    pipeline_outdir   // val: pipeline output root (e.g., output_ottilie)
    samplesheet       // path: CSV with sample metadata (params.input)
    fasta             // tuple: [path(fasta), path(fai)]
    gff3              // path: gene annotation GFF3

    main:
    versions = Channel.empty()

    // =========================================================================
    // 1. Parse configuration from params
    // =========================================================================

    def tool_list = params.tools ? params.tools.split(',').collect { it.trim() } : []
    def skip_list = params.skip_tools ? params.skip_tools.split(',').collect { it.trim() } : []

    // Annotation detection (mirrors workflows/sarek/main.nf:901)
    def annotation_tool = null
    if (tool_list.contains('snpeff')) {
        annotation_tool = 'snpeff'
    } else if (tool_list.contains('vep')) {
        log.warn "MUTATION_REPORT: VEP annotation detected — VCF suffix patterns not yet tested."
        annotation_tool = 'vep'
    } else if (tool_list.contains('bcfann')) {
        log.warn "MUTATION_REPORT: bcfann detected — falling back to unannotated VCF paths."
        annotation_tool = null
    }
    def has_annotation = (annotation_tool != null)

    // Tool availability
    def has_cnvkit = tool_list.contains('cnvkit')
    def has_manta  = tool_list.contains('manta')
    def has_tiddit = tool_list.contains('tiddit')
    def has_haplotypecaller = tool_list.contains('haplotypecaller')

    // CRAM subdirectory (depends on which preprocessing steps were skipped)
    def cram_subdir
    if (skip_list.contains('markduplicates')) {
        cram_subdir = 'mapped'
    } else if (skip_list.contains('baserecalibrator')) {
        cram_subdir = 'markduplicates'
    } else {
        cram_subdir = 'recalibrated'
    }

    // Path resolution
    def outdir = file(pipeline_outdir)
    def vcf_root = has_annotation ? "${outdir}/annotation" : "${outdir}/variant_calling"
    def cram_dir = "${outdir}/preprocessing/${cram_subdir}"
    def cnvkit_dir = "${outdir}/variant_calling/cnvkit"
    def multiqc_dir = "${outdir}/multiqc/multiqc_data"

    // VCF filename suffix patterns (annotated vs raw)
    def vcf_suffixes = [
        haplotypecaller: has_annotation
            ? '.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz'
            : '.haplotypecaller.from_joint_calling.vcf.gz',
        cnvkit: has_annotation
            ? '.cnvcall_snpEff.ann.vcf.gz'
            : '.cnvcall.vcf',
        manta: has_annotation
            ? '.manta.diploid_sv_snpEff.ann.vcf.gz'
            : '.manta.diploid_sv.vcf.gz',
        tiddit: has_annotation
            ? '.tiddit_snpEff.ann.vcf.gz'
            : '.tiddit.vcf.gz',
    ]

    // CRAM suffix (markduplicates produces .md.cram)
    def cram_suffix = cram_subdir == 'markduplicates' ? '.md.cram' : '.cram'

    // =========================================================================
    // 2. Log resolved configuration
    // =========================================================================

    log.info "MUTATION_REPORT: pipeline output  = ${outdir}"
    log.info "MUTATION_REPORT: VCF source       = ${has_annotation ? "annotation/ (${annotation_tool})" : 'variant_calling/ (raw)'}"
    log.info "MUTATION_REPORT: CRAM source      = preprocessing/${cram_subdir}/"
    log.info "MUTATION_REPORT: tools enabled     = ${tool_list.join(', ')}"

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
    // 3. Parse sample list from samplesheet
    // =========================================================================

    // Extract unique sample names from the samplesheet CSV
    ch_sample_list = Channel.fromPath(samplesheet)
        .splitCsv(header: true)
        .map { row -> row.sample }
        .unique()
        .toList()

    // =========================================================================
    // 4. GFF3 preparation
    // =========================================================================

    PREPARE_GFF3(gff3)
    ch_gff3_indexed = PREPARE_GFF3.out.gff3
    versions = versions.mix(PREPARE_GFF3.out.versions)

    // Reference tuple for downstream processes
    ch_fasta = Channel.value(fasta)

    // =========================================================================
    // 5. Report-specific params (templates, scripts)
    // =========================================================================

    // These paths are relative to projectDir or provided via params
    ch_filter_config   = Channel.value(file(params.report_filter_config))
    ch_template        = Channel.value(file(params.report_cohort_template))
    ch_sample_template = Channel.value(file(params.report_sample_template))
    ch_index_script    = Channel.value(file(params.report_index_script))
    ch_templates_dir   = Channel.value(file(params.report_templates_dir))

    // =========================================================================
    // 6. Build HaplotypeCaller VCF channels (if enabled)
    // =========================================================================

    if (has_haplotypecaller) {

        // Joint VCF (cohort)
        def joint_vcf_dir = has_annotation
            ? "${vcf_root}/haplotypecaller/joint_variant_calling"
            : "${outdir}/variant_calling/haplotypecaller/joint_variant_calling"
        def joint_prefix = 'HaplotypeCaller_joint_calling_soft_filtered'
        def joint_suffix = has_annotation ? '_snpEff.ann.vcf.gz' : '.vcf.gz'
        def joint_vcf_path = "${joint_vcf_dir}/${joint_prefix}${joint_suffix}"

        ch_joint_vcf = Channel.of([
            [id: 'cohort'],
            file(joint_vcf_path),
            file("${joint_vcf_path}.tbi")
        ])

        // Per-sample HaplotypeCaller VCFs
        ch_sample_hc_vcfs = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    def hc_dir = "${vcf_root}/haplotypecaller/${sample}"
                    def vcf_path = "${hc_dir}/${sample}${vcf_suffixes.haplotypecaller}"
                    [ [id: sample, caller: 'haplotypecaller', caller_label: 'HaplotypeCaller'],
                      file(vcf_path), file("${vcf_path}.tbi") ]
                }
            }

        // Per-sample annotated VCFs for PUBLISH_VCFS
        ch_hc_annotated = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    def hc_dir = "${vcf_root}/haplotypecaller/${sample}"
                    def vcf_path = "${hc_dir}/${sample}${vcf_suffixes.haplotypecaller}"
                    [ file(vcf_path), file("${vcf_path}.tbi") ]
                }
            }

        // CRAMs for per-sample reports
        ch_crams = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    [ sample,
                      file("${cram_dir}/${sample}/${sample}${cram_suffix}"),
                      file("${cram_dir}/${sample}/${sample}${cram_suffix}.crai") ]
                }
            }

    } else {
        ch_joint_vcf = Channel.empty()
        ch_sample_hc_vcfs = Channel.empty()
        ch_hc_annotated = Channel.empty()
        ch_crams = Channel.empty()
    }

    // =========================================================================
    // 7. Build CNVKit/Manta/TIDDIT VCF channels (if enabled)
    // =========================================================================

    if (has_cnvkit) {
        ch_cnvkit_vcfs = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    def vcf_path = "${vcf_root}/cnvkit/${sample}/${sample}${vcf_suffixes.cnvkit}"
                    [ [id: sample, caller: 'cnvkit', caller_label: 'CNVKit'],
                      file(vcf_path), file("${vcf_path}.tbi") ]
                }
            }

        // CNR files for BedGraph tracks
        ch_cnr_files = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    [ [id: sample], file("${cnvkit_dir}/${sample}/${sample}.md.cnr") ]
                }
            }
    } else {
        ch_cnvkit_vcfs = Channel.empty()
        ch_cnr_files = Channel.empty()
    }

    if (has_manta) {
        ch_manta_vcfs = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    def vcf_path = "${vcf_root}/manta/${sample}/${sample}${vcf_suffixes.manta}"
                    [ [id: sample, caller: 'manta', caller_label: 'Manta'],
                      file(vcf_path), file("${vcf_path}.tbi") ]
                }
            }
    } else {
        ch_manta_vcfs = Channel.empty()
    }

    if (has_tiddit) {
        ch_tiddit_vcfs = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    def vcf_path = "${vcf_root}/tiddit/${sample}/${sample}${vcf_suffixes.tiddit}"
                    [ [id: sample, caller: 'tiddit', caller_label: 'TIDDIT'],
                      file(vcf_path), file("${vcf_path}.tbi") ]
                }
            }
    } else {
        ch_tiddit_vcfs = Channel.empty()
    }

    // =========================================================================
    // 8. CN matrix generation (CNVKit)
    // =========================================================================

    if (has_cnvkit) {
        // build_cn_matrix.py needs the cnvkit output dir structure
        ch_cn_input = ch_sample_list.map { samples ->
            [ [id: 'all_samples'], file(cnvkit_dir) ]
        }

        BUILD_CN_MATRIX(ch_cn_input, file(fasta[1]))  // fasta[1] = .fai
        versions = versions.mix(BUILD_CN_MATRIX.out.versions)

        // Build cohort matrix from the bin-level output
        BUILD_CN_COHORT(BUILD_CN_MATRIX.out.cn_matrices.map { meta, dir -> dir }, file(fasta[1]))
        versions = versions.mix(BUILD_CN_COHORT.out.versions)

        ch_cn_data = BUILD_CN_COHORT.out.collapsed
            .mix(BUILD_CN_COHORT.out.full)
            .collect()
    } else {
        ch_cn_data = Channel.empty()
    }

    // =========================================================================
    // 9. SV merge + cohort matrix (Manta/TIDDIT)
    // =========================================================================

    if (has_manta && has_tiddit) {
        // Get raw (unannotated) Manta + TIDDIT VCFs for SURVIVOR merge
        def sv_vc_dir = "${outdir}/variant_calling"

        // Per-sample: filter → merge
        ch_sv_manta_raw = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    def vcf_path = "${sv_vc_dir}/manta/${sample}/${sample}.manta.diploid_sv.vcf.gz"
                    [ [id: sample, caller: 'manta'], file(vcf_path), file("${vcf_path}.tbi") ]
                }
            }

        ch_sv_tiddit_raw = ch_sample_list
            .flatMap { samples ->
                samples.collect { sample ->
                    def vcf_path = "${sv_vc_dir}/tiddit/${sample}/${sample}.tiddit.vcf.gz"
                    [ [id: sample, caller: 'tiddit'], file(vcf_path), file("${vcf_path}.tbi") ]
                }
            }

        // PASS-filter both callers (nf-core bcftools/view with ext.args)
        FILTER_SV_VCF_MANTA(ch_sv_manta_raw, [], [], [])
        FILTER_SV_VCF_TIDDIT(ch_sv_tiddit_raw, [], [], [])
        versions = versions.mix(FILTER_SV_VCF_MANTA.out.versions.first())

        // Decompress raw VCFs (no PASS filter) for unfiltered union merge
        DECOMPRESS_SV_MANTA(ch_sv_manta_raw, [], [], [])
        DECOMPRESS_SV_TIDDIT(ch_sv_tiddit_raw, [], [], [])

        // Pair Manta + TIDDIT per sample for SURVIVOR merge (PASS-filtered)
        ch_manta_filtered = FILTER_SV_VCF_MANTA.out.vcf
            .map { meta, vcf -> [ meta.id, vcf ] }
        ch_tiddit_filtered = FILTER_SV_VCF_TIDDIT.out.vcf
            .map { meta, vcf -> [ meta.id, vcf ] }

        ch_sv_paired_pass = ch_manta_filtered
            .join(ch_tiddit_filtered)
            .map { id, manta_vcf, tiddit_vcf ->
                [ [id: id, merge_mode: 'union_pass'], manta_vcf, tiddit_vcf ]
            }

        // Pair raw (unfiltered) for union merge
        ch_manta_raw_vcf = DECOMPRESS_SV_MANTA.out.vcf
            .map { meta, vcf -> [ meta.id, vcf ] }
        ch_tiddit_raw_vcf = DECOMPRESS_SV_TIDDIT.out.vcf
            .map { meta, vcf -> [ meta.id, vcf ] }

        ch_sv_paired_union = ch_manta_raw_vcf
            .join(ch_tiddit_raw_vcf)
            .map { id, manta_vcf, tiddit_vcf ->
                [ [id: id, merge_mode: 'union'], manta_vcf, tiddit_vcf ]
            }

        SURVIVOR_SV_MERGE_PASS(ch_sv_paired_pass)
        SURVIVOR_SV_MERGE_UNION(ch_sv_paired_union)
        versions = versions.mix(SURVIVOR_SV_MERGE_PASS.out.versions.first())

        // Compress + index merged VCFs (bgzip + tabix, htslib container)
        BGZIPTABIX_SV_PASS(SURVIVOR_SV_MERGE_PASS.out.vcf)
        BGZIPTABIX_SV_UNION(SURVIVOR_SV_MERGE_UNION.out.vcf)
        versions = versions.mix(BGZIPTABIX_SV_PASS.out.versions.first())

        // Collect compressed VCFs as flat list for BUILD_SV_COHORT
        ch_pass_vcfs = BGZIPTABIX_SV_PASS.out.gz_tbi
            .flatMap { meta, vcf, tbi -> [ vcf, tbi ] }
            .collect()
        ch_union_vcfs = BGZIPTABIX_SV_UNION.out.gz_tbi
            .flatMap { meta, vcf, tbi -> [ vcf, tbi ] }
            .collect()

        BUILD_SV_COHORT(ch_pass_vcfs, ch_union_vcfs)
        versions = versions.mix(BUILD_SV_COHORT.out.versions)

        ch_sv_data = BUILD_SV_COHORT.out.union_csv
            .mix(BUILD_SV_COHORT.out.union_pass_csv)
            .collect()
    } else {
        ch_sv_data = Channel.empty()
    }

    // =========================================================================
    // 10. TIDDIT PASS filtering (for reports)
    // =========================================================================

    if (has_tiddit) {
        FILTER_PASS_VCF(ch_tiddit_vcfs)
        ch_tiddit_pass = FILTER_PASS_VCF.out.vcf
        ch_pass_stats = FILTER_PASS_VCF.out.stats.collect().ifEmpty(file("NO_FILE"))
        versions = versions.mix(FILTER_PASS_VCF.out.versions.first())
    } else {
        ch_tiddit_pass = Channel.empty()
        ch_pass_stats = Channel.value(file("NO_FILE"))
    }

    // =========================================================================
    // 11. Publish pre-norm annotated VCFs
    // =========================================================================

    if (has_haplotypecaller) {
        PUBLISH_VCFS(
            ch_joint_vcf,
            ch_hc_annotated.collect(),
            has_cnvkit ? ch_cnvkit_vcfs.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([]),
            has_manta ? ch_manta_vcfs.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([]),
            has_tiddit ? ch_tiddit_vcfs.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([]),
            has_tiddit ? ch_tiddit_pass.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect() : Channel.value([])
        )
        versions = versions.mix(PUBLISH_VCFS.out.versions)
    }

    // =========================================================================
    // 12. Prepare VCFs for igv-reports (multi-allelic split, VAF, FILTER→INFO)
    // =========================================================================

    if (has_haplotypecaller) {
        ch_all_vcfs = ch_joint_vcf
            .mix(ch_sample_hc_vcfs)
            .mix(ch_cnvkit_vcfs)
            .mix(ch_manta_vcfs)
            .mix(has_tiddit ? ch_tiddit_pass : Channel.empty())

        ch_all_prepared = PREPARE_VCF(ch_all_vcfs)
        versions = versions.mix(PREPARE_VCF.out.versions.first())

        // Branch into cohort, HC sample, and SV/CNV channels
        ch_all_prepared.vcf.branch {
            cohort: it[0].id == 'cohort'
            sv_cnv: it[0].caller in ['cnvkit', 'manta', 'tiddit']
            sample: true
        }.set { ch_branched }

        // =====================================================================
        // 13. Cohort report
        // =====================================================================

        IGVREPORTS_COHORT(ch_branched.cohort, ch_gff3_indexed, ch_fasta, ch_filter_config, ch_template)
        versions = versions.mix(IGVREPORTS_COHORT.out.versions)

        // =====================================================================
        // 14. Per-sample HaplotypeCaller reports
        // =====================================================================

        ch_samples_with_cram = ch_branched.sample
            .map { meta, vcf, tbi ->
                def cram = file("${cram_dir}/${meta.id}/${meta.id}${cram_suffix}")
                def crai = file("${cram_dir}/${meta.id}/${meta.id}${cram_suffix}.crai")
                [ meta, vcf, tbi, cram, crai ]
            }

        IGVREPORTS_SAMPLE(ch_samples_with_cram, ch_gff3_indexed, ch_fasta, ch_filter_config, ch_sample_template)
        versions = versions.mix(IGVREPORTS_SAMPLE.out.versions.first())

        // =====================================================================
        // 15. CNVKit BedGraph + SV/CNV per-sample reports
        // =====================================================================

        if (has_cnvkit) {
            CNR_TO_BEDGRAPH(ch_cnr_files)
            ch_bedgraph_map = CNR_TO_BEDGRAPH.out.bedgraph
                .map { meta, depth_bg, log2_bg -> [ meta.id, depth_bg, log2_bg ] }
            versions = versions.mix(CNR_TO_BEDGRAPH.out.versions.first())
        }

        ch_sv_cnv_with_cram = ch_branched.sv_cnv
            .map { meta, vcf, tbi ->
                def cram = file("${cram_dir}/${meta.id}/${meta.id}${cram_suffix}")
                def crai = file("${cram_dir}/${meta.id}/${meta.id}${cram_suffix}.crai")
                [ meta, vcf, tbi, cram, crai ]
            }

        if (has_cnvkit) {
            ch_sv_cnv_with_cram.branch {
                cnvkit: it[0].caller == 'cnvkit'
                other: true
            }.set { ch_sv_cnv_branched }

            ch_cnvkit_with_bg = ch_sv_cnv_branched.cnvkit
                .map { meta, vcf, tbi, cram, crai -> [ meta.id, meta, vcf, tbi, cram, crai ] }
                .join(ch_bedgraph_map)
                .map { id, meta, vcf, tbi, cram, crai, depth_bg, log2_bg ->
                    [ meta, vcf, tbi, cram, crai, depth_bg, log2_bg ]
                }

            ch_other_sv = ch_sv_cnv_branched.other
                .map { meta, vcf, tbi, cram, crai ->
                    [ meta, vcf, tbi, cram, crai, file('NO_DEPTH_BG'), file('NO_LOG2_BG') ]
                }

            ch_sv_cnv_all = ch_cnvkit_with_bg.mix(ch_other_sv)
        } else {
            ch_sv_cnv_all = ch_sv_cnv_with_cram
                .map { meta, vcf, tbi, cram, crai ->
                    [ meta, vcf, tbi, cram, crai, file('NO_DEPTH_BG'), file('NO_LOG2_BG') ]
                }
        }

        IGVREPORTS_SV_CNV(ch_sv_cnv_all, ch_gff3_indexed, ch_fasta, ch_sample_template)
        versions = versions.mix(IGVREPORTS_SV_CNV.out.versions.first())

        // =====================================================================
        // 16. Generate index.html dashboard
        // =====================================================================

        ch_multiqc_data = Channel.value(file(multiqc_dir))

        // Collect CN/SV data + pass_stats into a single channel for data/ staging
        ch_cnv_sv_data = ch_cn_data
            .mix(ch_sv_data)
            .mix(ch_pass_stats)
            .collect()
            .ifEmpty(file("NO_FILE"))

        ch_all_sample_reports = IGVREPORTS_SAMPLE.out.report
            .mix(IGVREPORTS_SV_CNV.out.report)
            .collect()

        ch_prepared_cohort_vcf = ch_branched.cohort.map { meta, vcf, tbi -> vcf }

        ch_mqc_report_path = Channel.value(params.report_multiqc_path ?: "")

        GENERATE_INDEX(
            IGVREPORTS_COHORT.out.report.collect(),
            ch_all_sample_reports,
            ch_multiqc_data,
            ch_index_script,
            ch_templates_dir,
            ch_cnv_sv_data,
            ch_mqc_report_path,
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
