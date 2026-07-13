//
// FreeBayes-specific VCF filtering subworkflow
// NOTE: FreeBayes runs in germline-only mode per CLAUDE.md
// All samples processed through filter_normal pathway (somatic mode disabled)
//

include { BCFTOOLS_FILTER_NORMAL } from '../../../subworkflows/local/vcf_filter_freebayes/bcftools/filter_normal/main'

workflow VCF_FILTER_FREEBAYES {
    take:
    ch_vcf_tbi    // channel: [ val(meta), path(vcf), path(tbi) ]
    
    main:
    ch_versions = Channel.empty()
    
    // Filter FreeBayes VCFs only
    ch_freebayes_vcfs = ch_vcf_tbi.filter{ meta, vcf, tbi ->
        meta.variantcaller == 'freebayes' || vcf.name.contains('freebayes')
    }
    ch_freebayes_vcfs.map{ meta, vcf, tbi ->
        def new_id = vcf.name - '.vcf.gz'  // "A5-F4-I1-R1_vs_A0-F0-I1-R1.freebayes_snpEff.ann"
        [meta + [id: "${new_id}.quality_filtered"], vcf, tbi]
        }.set{ ch_for_basic_filter }

    // Apply germline quality filters for FreeBayes
    // FreeBayes-specific filters: QUAL>=20, DP>=10, AF>=0.05
    // Also filter out reference calls and low-confidence variants

    BCFTOOLS_FILTER_NORMAL(ch_for_basic_filter)

    ch_versions = ch_versions.mix(BCFTOOLS_FILTER_NORMAL.out.versions.first())

    // Create channel with filtered VCFs and their indices
    ch_filtered_vcfs = BCFTOOLS_FILTER_NORMAL.out.vcf.join(
        BCFTOOLS_FILTER_NORMAL.out.tbi,
        failOnDuplicate: true,
        failOnMismatch: true
    )

    emit:
    vcf_filtered     = ch_filtered_vcfs           // channel: [ val(meta), path(vcf), path(tbi) ]
    versions         = ch_versions                // channel: [ path(versions.yml) ]
}