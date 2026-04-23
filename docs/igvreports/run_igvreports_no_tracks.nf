#!/usr/bin/env nextflow
/*
 * Standalone IGVReports test workflow — VCF only, no CRAM tracks
 * Quick run to evaluate the report format.
 *
 * Usage:
 *   bash docs/igvreports/run_igvreports_no_tracks.sh
 */

nextflow.enable.dsl = 2

params.vcf    = null
params.fasta  = null
params.fai    = null
params.outdir = 'docs/igvreports/output_no_tracks'

include { IGVREPORTS } from '../../modules/nf-core/igvreports/main'

workflow {

    ch_fasta = Channel.value(
        [ [id: 'draft_ref52'], file(params.fasta), file(params.fai) ]
    )

    // No tracks — pass empty lists
    ch_input = Channel.value(
        [ [id: 'joint_haplotypecaller_no_tracks'], file(params.vcf), [], [] ]
    )

    IGVREPORTS( ch_input, ch_fasta )
}
