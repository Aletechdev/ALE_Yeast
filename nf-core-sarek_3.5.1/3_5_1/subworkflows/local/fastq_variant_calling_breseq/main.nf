//
// BRESEQ variant calling from FASTQ files
//
// Runs breseq directly on trimmed FASTQs (bypasses BWA alignment).
// Supports clonal (default) and population (-p) modes via meta.clonal_or_population.
//

include { BRESEQ                              } from '../../../modules/local/breseq/main'
include { GDTOOLS_CONVERT                     } from '../../../modules/local/gdtools/convert/main'
include { TABIX_BGZIPTABIX as TABIX_BGZIPTABIX_BRESEQ } from '../../../modules/nf-core/tabix/bgziptabix/main'

workflow FASTQ_VARIANT_CALLING_BRESEQ {
    take:
    reads       // channel: [mandatory] [ meta, [reads] ] - per-lane trimmed FASTQs
    genbank     // path: reference file (GenBank, GFF3, or FASTA)

    main:
    versions = Channel.empty()

    // =========================================================================
    // STEP 1: Group reads by sample (collect all lanes)
    // =========================================================================
    // After FASTP, reads are per-lane:
    //   [meta{sample:'A1-F6-I1-R1', lane:'L001'}, [R1_L001.fq.gz, R2_L001.fq.gz]]
    //   [meta{sample:'A1-F6-I1-R1', lane:'L002'}, [R1_L002.fq.gz, R2_L002.fq.gz]]
    // breseq needs all lanes per sample in a single invocation.
    //
    // This follows the lane-grouping pattern from sarek/main.nf:289-296.

    // Count lanes per sample for groupKey (prevents stalling)
    reads
        .map { meta, fastqs ->
            [ meta.subMap('patient', 'sample'), fastqs ]
        }
        .groupTuple()
        .map { meta, reads_list ->
            [ meta, reads_list.size() ]
        }
        .set { sample_lane_counts }

    // Group reads by sample, flatten all lane FASTQs into single list
    reads_for_breseq = reads
        .map { meta, fastqs ->
            def group_key = meta.subMap('patient', 'sample')
            def new_meta = meta.subMap('patient', 'sample', 'sex', 'status', 'ploidy', 'clonal_or_population') + [
                id: meta.sample,
                variantcaller: 'breseq'
            ]
            [ group_key, new_meta, fastqs ]
        }
        .combine(sample_lane_counts, by: 0)
        .map { group_key, meta, fastqs, n_lanes ->
            [ groupKey(meta, n_lanes), fastqs ]
        }
        .groupTuple()
        .map { meta, reads_nested ->
            [ meta, reads_nested.flatten() ]
        }

    // =========================================================================
    // STEP 2: Run breseq
    // =========================================================================
    BRESEQ(reads_for_breseq, genbank)
    versions = versions.mix(BRESEQ.out.versions.first())

    // =========================================================================
    // STEP 3: Convert annotated GD to VCF
    // =========================================================================
    GDTOOLS_CONVERT(BRESEQ.out.annotated_gd, genbank)
    versions = versions.mix(GDTOOLS_CONVERT.out.versions.first())

    // =========================================================================
    // STEP 4: bgzip + index VCF
    // =========================================================================
    TABIX_BGZIPTABIX_BRESEQ(GDTOOLS_CONVERT.out.vcf)
    versions = versions.mix(TABIX_BGZIPTABIX_BRESEQ.out.versions.first())

    emit:
    gd           = BRESEQ.out.gd                     // channel: [ meta, output.gd ]
    annotated_gd = BRESEQ.out.annotated_gd           // channel: [ meta, annotated.gd ]
    html_report  = BRESEQ.out.html_report            // channel: [ meta, index.html ]
    summary      = BRESEQ.out.summary                // channel: [ meta, summary.json ]
    vcf          = TABIX_BGZIPTABIX_BRESEQ.out.gz_tbi // channel: [ meta, vcf.gz, tbi ]
    versions                                         // channel: [ versions.yml ]
}
