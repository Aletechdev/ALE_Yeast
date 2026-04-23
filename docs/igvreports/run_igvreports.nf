#!/usr/bin/env nextflow
/*
 * Standalone IGVReports test workflow
 * Generates an interactive HTML report from an existing VCF + CRAM tracks.
 *
 * Usage:
 *   bash docs/igvreports/run_igvreports.sh
 */

nextflow.enable.dsl = 2

params.vcf       = null   // path to VCF (or VCF.gz)
params.fasta     = null   // reference FASTA
params.fai       = null   // reference .fai index
params.cram_dir  = null   // directory containing *.md.cram + *.md.cram.crai
params.outdir    = 'docs/igvreports/output'

// Import the nf-core igvreports module (relative to repo root)
include { IGVREPORTS } from '../../modules/nf-core/igvreports/main'

workflow {

    // --- Reference genome ---
    ch_fasta = Channel.value(
        [ [id: 'draft_ref52'], file(params.fasta), file(params.fai) ]
    )

    // --- Collect all CRAM tracks + indices as lists ---
    cram_files = Channel.fromPath("${params.cram_dir}/**/*.md.cram")
                        .collect()
                        .map { files -> [files] }
    crai_files = Channel.fromPath("${params.cram_dir}/**/*.md.cram.crai")
                        .collect()
                        .map { files -> [files] }

    // --- Build the input tuple: [meta, sites, tracks[], tracks_indices[]] ---
    ch_input = cram_files
        .combine(crai_files)
        .map { crams, crais ->
            def meta = [id: 'joint_haplotypecaller']
            [ meta, file(params.vcf), crams, crais ]
        }

    IGVREPORTS( ch_input, ch_fasta )
}
