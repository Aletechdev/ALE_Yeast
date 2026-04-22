//
// CONTROLFREEC germline variant calling (single-sample mode)
//
// For all modules here:
// A when clause condition is defined in the conf/modules.config to determine if the module should be run

include { CONTROLFREEC_FREEC as FREEC_GERMLINE                     } from '../../../modules/nf-core/controlfreec/freec/main'
include { CONTROLFREEC_ASSESSSIGNIFICANCE as ASSESS_SIGNIFICANCE } from '../../../modules/nf-core/controlfreec/assesssignificance/main'
include { CONTROLFREEC_FREEC2BED as FREEC2BED                    } from '../../../modules/nf-core/controlfreec/freec2bed/main'
include { CONTROLFREEC_FREEC2CIRCOS as FREEC2CIRCOS              } from '../../../modules/nf-core/controlfreec/freec2circos/main'
include { CONTROLFREEC_MAKEGRAPH2 as MAKEGRAPH2                  } from '../../../modules/nf-core/controlfreec/makegraph2/main'

workflow BAM_VARIANT_CALLING_GERMLINE_CONTROLFREEC {
    take:
    controlfreec_input       // channel: [mandatory] [meta, [], pileup, [], [], [], []]
    fasta                    // channel: [mandatory]
    fasta_fai                // channel: [mandatory]
    dbsnp                    // channel: [mandatory]
    dbsnp_tbi                // channel: [mandatory]
    chr_files                // channel: [mandatory]
    mappability              // channel: [mandatory]
    intervals_bed            // channel: [optional]  Contains a bed file of all intervals combined provided with the cram input(s). Should be empty for WGS

    main:

    ch_versions = Channel.empty()

    FREEC_GERMLINE(controlfreec_input, fasta, fasta_fai, [], dbsnp, dbsnp_tbi, chr_files, mappability, intervals_bed, [])

    ASSESS_SIGNIFICANCE(FREEC_GERMLINE.out.CNV.join(FREEC_GERMLINE.out.ratio, failOnDuplicate: true, failOnMismatch: true))
    FREEC2BED(FREEC_GERMLINE.out.ratio)
    FREEC2CIRCOS(FREEC_GERMLINE.out.ratio)
    // Only run MAKEGRAPH2 for samples that have BAF files
    // This is cleaner than trying to handle empty BAF files
    ch_ratio_with_baf = FREEC_GERMLINE.out.ratio.join(FREEC_GERMLINE.out.BAF)

    MAKEGRAPH2(ch_ratio_with_baf)

    ch_versions = ch_versions.mix(FREEC_GERMLINE.out.versions)
    ch_versions = ch_versions.mix(ASSESS_SIGNIFICANCE.out.versions)
    ch_versions = ch_versions.mix(FREEC2BED.out.versions)
    ch_versions = ch_versions.mix(FREEC2CIRCOS.out.versions)
    ch_versions = ch_versions.mix(MAKEGRAPH2.out.versions)

    emit:
    versions = ch_versions
}
