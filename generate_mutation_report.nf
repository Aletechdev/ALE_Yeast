#!/usr/bin/env nextflow
/*
 * Standalone launcher for the MUTATION_REPORT subworkflow.
 *
 * Generates the igv-reports mutation dashboard from existing pipeline output,
 * without re-running the full Sarek pipeline.  Reads VCF/CRAM paths from
 * params.outdir using params.tools / params.skip_tools for auto-discovery.
 *
 * Usage:
 *   bash docs/igvreports/generate_ottilie_reports.sh
 *
 * Or directly:
 *   nextflow run generate_mutation_report.nf \
 *       -c nextflow.config \
 *       --outdir output_ottilie \
 *       --input data/ottilie/samplesheet_pilot.csv \
 *       --fasta data/ottilie/S288C_reference/S288C_R64.fa \
 *       --fasta_fai data/ottilie/S288C_reference/S288C_R64.fa.fai \
 *       --report_gff3 data/ottilie/S288C_reference/S288C_R64.gff3 \
 *       --tools haplotypecaller,cnvkit,manta,tiddit,snpeff \
 *       --skip_tools baserecalibrator \
 *       --report_outdir docs/igvreports/ottilie_4samples \
 *       -profile conda \
 *       -resume
 */

nextflow.enable.dsl = 2

include { MUTATION_REPORT } from './subworkflows/local/mutation_report/main'

workflow {
    def report_fasta = file(params.fasta)
    def report_fai   = file(params.fasta_fai)

    // Standalone mode: the pipeline is not re-run, so read the MultiQC report from
    // the existing output dir. `file().exists()` is cloud-aware (works on az://,
    // s3://, etc.); fall back to a NO_FILE sentinel when absent.
    def mqc_file = file("${params.outdir}/multiqc/multiqc_report.html")
    def ch_multiqc_report = Channel.value(mqc_file.exists() ? mqc_file : file("NO_FILE"))

    MUTATION_REPORT(
        params.outdir,
        params.input,
        [ report_fasta, report_fai ],
        file(params.report_gff3),
        ch_multiqc_report
    )
}
