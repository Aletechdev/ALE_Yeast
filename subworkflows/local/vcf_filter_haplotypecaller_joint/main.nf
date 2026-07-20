//
// HaplotypeCaller Individual VCF (from joint calling) hard filtering subworkflow
// Applies sample-specific quality filters (FORMAT/GQ, FORMAT/DP)
// Removes failing variants entirely for clean MultiQC reporting
//

include { BCFTOOLS_HARD_FILTER_JOINT } from '../../../subworkflows/local/vcf_filter_haplotypecaller_joint/bcftools/hard_filter/main'

workflow VCF_FILTER_HAPLOTYPECALLER_JOINT {
    take:
    ch_vcf_tbi    // channel: [ val(meta), path(vcf), path(tbi) ]

    main:
    ch_versions = Channel.empty()

    // Filter only HaplotypeCaller individual VCFs from joint calling
    ch_joint_individual_vcfs = ch_vcf_tbi.filter{ meta, vcf, tbi ->
        (meta.variantcaller == 'haplotypecaller' && meta.source == 'joint_calling') ||
        vcf.name.contains('from_joint_calling')
    }

    // Keep original metadata (suffix will be added by process)
    ch_joint_individual_vcfs.map{ meta, vcf, tbi ->
        def new_id = "${meta.id}.haplotypecaller.from_joint_calling"
        [meta + [id: new_id], vcf, tbi]
    }.set{ ch_for_hard_filter }

    // Apply sample-level hard filters
    // FORMAT/GQ>=20, FORMAT/DP>=8, FILTER="PASS"
    // Removes variants entirely (no --set-GTs) for clean counts
    BCFTOOLS_HARD_FILTER_JOINT(ch_for_hard_filter)

    ch_versions = ch_versions.mix(BCFTOOLS_HARD_FILTER_JOINT.out.versions)

    // Create channel with filtered VCFs and their indices
    ch_filtered_vcfs = BCFTOOLS_HARD_FILTER_JOINT.out.vcf.join(
        BCFTOOLS_HARD_FILTER_JOINT.out.tbi,
        failOnDuplicate: true,
        failOnMismatch: true
    )

    emit:
    vcf_filtered     = ch_filtered_vcfs           // channel: [ val(meta), path(vcf), path(tbi) ]
    versions         = ch_versions                // channel: [ path(versions.yml) ]
}
