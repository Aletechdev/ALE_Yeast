// Generate per-sample igv-reports HTML with CRAM pileup and gene track
process IGVREPORTS_SAMPLE {
    tag "$meta.id"
    label 'process_low'

    conda 'bioconda::igv-reports=1.16.0'
    container 'quay.io/biocontainers/igv-reports:1.16.0--pyh7e72e81_0'

    input:
    tuple val(meta), path(vcf), path(tbi), path(cram), path(crai)
    tuple path(gff3_gz), path(gff3_tbi)
    tuple path(fasta), path(fai)
    path filter_config
    path template

    output:
    path "${meta.id}_hc_report.html", emit: report
    path "versions.yml",              emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    // Gene track is optional (--report_gff3 unset -> gff3_gz is []). The CRAM is always
    // present, so --tracks never ends up empty here.
    def gff3_track = gff3_gz ? "${gff3_gz} " : ''
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tracks ${gff3_track}${cram} \\
        --template ${template} \\
        --filter-config ${filter_config} \\
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \\
        --sample-columns GT AD DP GQ VAF \\
        --flanking 500 \\
        --title "${meta.id} - HaplotypeCaller (Yeast ALE)" \\
        --output ${meta.id}_hc_report.html

    sed -i 's|@VCF_HREF@|../vcf/haplotypecaller/${meta.id}_haplotypecaller_annotated.vcf.gz|g' ${meta.id}_hc_report.html
    sed -i 's|@VCF_FILENAME@|${meta.id}_haplotypecaller_annotated.vcf.gz|g' ${meta.id}_hc_report.html
    sed -i 's|@REPORT_TYPE@|haplotypecaller|g' ${meta.id}_hc_report.html

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        igv-reports: \$(pip show igv-reports 2>/dev/null | grep Version | sed 's/Version: //' || echo "1.16.0")
    END_VERSIONS
    """
}
