//
// SPLIT JOINT VCF INTO INDIVIDUAL SAMPLE VCFs (Channel-Based Version)
//
// Extracts individual sample VCFs from joint germline calling output
// Uses existing sample metadata from cram_variant_calling channel
// More NextFlow-correct: no string parsing, uses structured metadata
//

include { BCFTOOLS_VIEW     } from '../../../modules/nf-core/bcftools/view/main'
include { BCFTOOLS_REHEADER } from '../../../modules/nf-core/bcftools/reheader/main'
include { TABIX_TABIX       } from '../../../modules/nf-core/tabix/tabix/main'

workflow SPLIT_JOINT_VCF {
    take:
    joint_vcf_tbi  // channel: [ meta_joint, vcf, tbi ]
    cram           // channel: [ meta_sample, cram, crai ] - contains original sample metadata

    main:
    versions = Channel.empty()

    // Extract patient from joint VCF meta
    // Join with individual sample metadata from cram channel
    samples_for_split = joint_vcf_tbi
        .map { meta_joint, vcf, tbi ->
            // Extract patient/experiment ID from joint calling meta
            [ meta_joint.patient, meta_joint, vcf, tbi ]
        }
        .combine(
            cram.map { meta_sample, cram_file, crai_file ->
                // Extract patient and sample metadata
                [ meta_sample.patient, meta_sample ]
            },
            by: 0  // Join on patient ID (first element)
        )
        .map { patient, meta_joint, vcf, tbi, meta_sample ->
            // Create new meta combining joint VCF info and sample metadata
            [
                meta_joint + meta_sample + [
                    id: meta_sample.sample,                      // Clean sample ID (no patient prefix)
                    variantcaller: meta_joint.variantcaller,     // Preserve variant caller info
                    source: 'joint_calling',                     // Track origin
                    bcftools_sample: "${meta_sample.patient}_${meta_sample.sample}",  // Full name in VCF header
                    original_sample: "${meta_sample.patient}_${meta_sample.sample}"   // For reheader mapping
                ],
                vcf,
                tbi
            ]
        }

    // Step 1: Extract each sample using bcftools view
    samples_for_bcftools = samples_for_split.map { meta, vcf, tbi ->
        [
            meta,
            vcf,
            tbi,
            [],  // regions
            []   // targets
        ]
    }

    BCFTOOLS_VIEW(samples_for_bcftools)

    // Step 2: Rename sample in VCF header using bcftools reheader
    // This removes the patient prefix from the sample name
    vcf_for_reheader = BCFTOOLS_VIEW.out.vcf.map { meta, vcf ->
        [
            meta,
            vcf,
            []  // fai (not needed for sample renaming)
        ]
    }

    BCFTOOLS_REHEADER(vcf_for_reheader)

    // Step 3: Index the renamed and compressed VCF
    TABIX_TABIX(BCFTOOLS_REHEADER.out.vcf)

    versions = versions.mix(BCFTOOLS_VIEW.out.versions.first())
    versions = versions.mix(BCFTOOLS_REHEADER.out.versions.first())
    versions = versions.mix(TABIX_TABIX.out.versions.first())

    emit:
    vcf      = BCFTOOLS_REHEADER.out.vcf  // channel: [ meta, vcf ] - with renamed samples
    tbi      = TABIX_TABIX.out.tbi        // channel: [ meta, tbi ]
    versions = versions                    // channel: [ versions.yml ]
}
