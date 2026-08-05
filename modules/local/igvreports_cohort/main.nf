// Generate cohort-level igv-reports HTML with custom Tabulator template
process IGVREPORTS_COHORT {
    tag 'cohort'
    label 'process_low'

    conda 'bioconda::igv-reports=1.16.0'
    container 'quay.io/biocontainers/igv-reports:1.16.0--pyh7e72e81_0'

    input:
    tuple val(meta), path(vcf), path(tbi)
    tuple path(gff3_gz), path(gff3_tbi)
    tuple path(fasta), path(fai)
    path filter_config
    path template

    output:
    path "cohort_report.html", emit: report
    path "versions.yml",       emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    // The gene track is this report's ONLY track, so when --report_gff3 is unset (gff3_gz is
    // []) the whole flag must go; `--tracks` with no value is a create_report usage error.
    def tracks_arg = gff3_gz ? "--tracks ${gff3_gz}" : ''
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        ${tracks_arg} \\
        --template ${template} \\
        --filter-config ${filter_config} \\
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \\
        --sample-columns GT VAF \\
        --flanking 500 \\
        --title "Cohort - Joint HaplotypeCaller (Yeast ALE)" \\
        --output cohort_report.html

    # Set VCF download link
    sed -i 's|@VCF_HREF@|vcf/haplotypecaller/cohort_haplotypecaller_annotated.vcf.gz|g' cohort_report.html
    sed -i 's|@VCF_FILENAME@|cohort_haplotypecaller_annotated.vcf.gz|g' cohort_report.html

    # Strip IGV session data (table-only cohort report)
    sed -i 's|const sessionDictionary = .*|const sessionDictionary = {};|' cohort_report.html

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        igv-reports: \$(pip show igv-reports 2>/dev/null | grep Version | sed 's/Version: //' || echo "1.16.0")
    END_VERSIONS
    """
}
