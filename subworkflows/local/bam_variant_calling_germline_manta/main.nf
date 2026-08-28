//
// Manta germline variant calling
//
// For all modules here:
// A when clause condition is defined in the conf/modules.config to determine if the module should be run

include { MANTA_GERMLINE } from '../../../modules/nf-core/manta/germline/main'

// Seems to be the consensus on upstream modules implementation too
workflow BAM_VARIANT_CALLING_GERMLINE_MANTA {
    take:
    cram          // channel: [mandatory] [ meta, cram, crai ]
    fasta         // channel: [mandatory] [ meta, fasta ]
    fasta_fai     // channel: [mandatory] [ meta, fasta_fai ]
    intervals     // channel: [mandatory] [ interval.bed.gz, interval.bed.gz.tbi] or [ [], []] if no intervals; intervals file contains all intervals
    joint_manta   // boolean: [mandatory] [default: false] one multi-sample Manta run per patient instead of one per sample

    main:
    versions = Channel.empty()

    // Joint mode: group every sample of a patient into one Manta run (Manta genotypes all of them at
    // every candidate). Meta is reduced to patient-level keys, id = patient, so groupTuple has one
    // key per patient and the outputs publish under variant_calling/manta/<patient>/.
    cram_to_call = joint_manta
        ? cram.map { meta, cram_file, crai_file -> [ meta.subMap('patient') + [ id: meta.patient ], cram_file, crai_file ] }.groupTuple()
        : cram

    // Combine cram and intervals, account for 0 intervals
    cram_intervals = cram_to_call.combine(intervals).map{ it ->
        bed_gz = it.size() > 3 ? it[3] : []
        bed_tbi = it.size() > 3 ? it[4] : []

        [it[0], it[1], it[2], bed_gz, bed_tbi]
    }

    MANTA_GERMLINE(cram_intervals, fasta, fasta_fai, [])

    small_indels_vcf   = MANTA_GERMLINE.out.candidate_small_indels_vcf
    sv_vcf             = MANTA_GERMLINE.out.candidate_sv_vcf
    diploid_sv_vcf     = MANTA_GERMLINE.out.diploid_sv_vcf
    diploid_sv_vcf_tbi = MANTA_GERMLINE.out.diploid_sv_vcf_tbi

    // Only diploid SV should get annotated
    // add variantcaller to meta map
    vcf = diploid_sv_vcf.map{ meta, vcf -> [ meta + [ variantcaller:'manta' ], vcf ] }
    tbi = diploid_sv_vcf_tbi.map{ meta, tbi -> [ meta + [ variantcaller:'manta' ], tbi ] }

    versions = versions.mix(MANTA_GERMLINE.out.versions)

    emit:
    vcf
    tbi

    versions
}
