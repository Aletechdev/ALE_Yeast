//
// SPLIT JOINT VCF INTO INDIVIDUAL SAMPLE VCFs (Channel-Based Version)
//
// Extracts individual sample VCFs from joint germline calling output
// Uses existing sample metadata from cram_variant_calling channel
// More NextFlow-correct: no string parsing, uses structured metadata
// Keeps original sample names in VCF for traceability
//

include { BCFTOOLS_VIEW   } from '../../../modules/nf-core/bcftools/view/main'
include { BCFTOOLS_FILTER } from '../../../modules/nf-core/bcftools/filter/main'

workflow SPLIT_JOINT_VCF {
    take:
    joint_vcf_tbi  // channel: [ meta_joint, vcf, tbi ]
    cram           // channel: [ meta_sample, cram, crai ] - contains original sample metadata

    main:
    versions = Channel.empty()

    // Extract patient from joint VCF meta and combine with individual sample metadata
    // Use cross product (combine without 'by') then filter to match patient
    samples_for_split = joint_vcf_tbi
        .combine(cram)  // Create all combinations
        .view { meta_joint, vcf, tbi, meta_sample, cram_file, crai_file ->
            "SPLIT_JOINT_VCF combine: joint=${meta_joint.id}, sample=${meta_sample.sample}, joint_patient=${meta_joint.patient}, sample_patient=${meta_sample.patient}"
        }
        .filter { meta_joint, vcf, tbi, meta_sample, cram_file, crai_file ->
            // For joint calling, joint VCF has patient="all_samples"
            // Just accept all combinations since joint VCF contains all samples
            def joint_patient = meta_joint.patient ?: meta_joint.id
            def sample_patient = meta_sample.patient ?: (meta_sample.experiment ?: meta_sample.id)

            // If joint_patient is "all_samples", accept all samples
            def match = (joint_patient == "all_samples" || joint_patient == sample_patient)

            if (match) {
                log.info "SPLIT_JOINT_VCF: Matched ${meta_sample.sample} to joint VCF ${meta_joint.id}"
            }
            match
        }
        .map { meta_joint, vcf, tbi, meta_sample, cram_file, crai_file ->
            // Create new meta combining joint VCF info and sample metadata
            // Use meta_sample.patient (e.g., "ALE_Exp1"), NOT meta_joint.patient (which is "all_samples")
            def patient = meta_sample.patient ?: meta_sample.id
            def bcftools_sample_name = "${patient}_${meta_sample.sample}"

            log.info "SPLIT_JOINT_VCF DEBUG: sample=${meta_sample.sample}, meta_sample.patient=${meta_sample.patient}, bcftools_sample=${bcftools_sample_name}"

            [
                meta_joint + meta_sample + [
                    id: meta_sample.sample,                      // Sample ID for file naming
                    patient: patient,                            // Use original patient ID
                    variantcaller: meta_joint.variantcaller,     // Preserve variant caller info
                    source: 'joint_calling',                     // Track origin
                    bcftools_sample: bcftools_sample_name        // Full name for extraction (e.g., "ALE_Exp1_A0-F0-I1-R1")
                ],
                vcf,
                tbi
            ]
        }

    // Extract each sample using bcftools view
    vcf_tuple = samples_for_split.map { meta, vcf, tbi -> [ meta, vcf, tbi ] }
    regions = Channel.value([])
    targets = Channel.value([])
    samples = Channel.value([])

    BCFTOOLS_VIEW(vcf_tuple, regions, targets, samples)

    // Filter to keep only variants where the sample has non-reference genotype
    // This removes variants where the sample is 0/0 or 0|0 (reference homozygote)
    // Add empty TBI channel since bcftools filter expects [meta, vcf, tbi]
    vcf_for_filter = BCFTOOLS_VIEW.out.vcf.map { meta, vcf -> [ meta, vcf, [] ] }

    BCFTOOLS_FILTER(vcf_for_filter)

    versions = versions.mix(BCFTOOLS_VIEW.out.versions.first())
    versions = versions.mix(BCFTOOLS_FILTER.out.versions.first())

    emit:
    vcf      = BCFTOOLS_FILTER.out.vcf  // channel: [ meta, vcf ] - filtered, ready for annotation
    tbi      = BCFTOOLS_FILTER.out.tbi  // channel: [ meta, tbi ] - tabix index
    versions = versions                  // channel: [ versions.yml ]
}
