// Generate Jinja2-based multi-caller dashboard index.html
process GENERATE_INDEX {
    tag 'index'
    label 'process_low'

    // No container — runs on host Python (nf-env has jinja2 + pandas)

    input:
    path cohort_report
    path sample_reports
    path multiqc_data_dir
    path generate_index_script
    path templates_dir
    path cnv_sv_data, stageAs: "data/*"   // CN/SV CSVs + pass_stats staged into data/ subdir
    val multiqc_report_path
    path prepared_cohort_vcf

    output:
    path "index.html",    emit: index
    path "versions.yml",  emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def has_cnv_sv = cnv_sv_data instanceof List ? cnv_sv_data.any { it.name != 'NO_FILE' } : cnv_sv_data.name != 'NO_FILE'
    def cnv_sv_arg = has_cnv_sv ? "--cnv-sv-data-dir data" : ""
    def mqc_path_arg = multiqc_report_path ? "--multiqc-report-path '${multiqc_report_path}'" : ""
    def prepared_vcf_arg = prepared_cohort_vcf.name != 'NO_FILE' ? "--prepared-vcf ${prepared_cohort_vcf}" : ""
    // Discover pass_stats TSVs from the staged data/ directory
    def data_files = cnv_sv_data instanceof List ? cnv_sv_data : [cnv_sv_data]
    def stats_files = data_files.findAll { it.name.endsWith('.pass_stats.tsv') && it.name != 'NO_FILE' }
    def pass_stats_arg = stats_files ? "--pass-stats ${stats_files.collect { 'data/' + it.name }.join(' ')}" : ""
    def python_bin = task.ext.python_bin ?: 'python'

    """
    # Create samples/ symlinks so discover_igv_reports() can find reports
    mkdir -p samples
    for f in *_report.html; do
        [ -f "\$f" ] && [ "\$f" != "cohort_report.html" ] && ln -sf "../\$f" "samples/\$f" || true
    done

    ${python_bin} ${generate_index_script} \\
        --multiqc-dir ${multiqc_data_dir} \\
        --output index.html \\
        --cohort-report ${cohort_report} \\
        --sample-reports-dir samples \\
        --templates-dir ${templates_dir} \\
        ${cnv_sv_arg} ${mqc_path_arg} ${prepared_vcf_arg} ${pass_stats_arg}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(${python_bin} --version 2>&1 | sed 's/Python //')
    END_VERSIONS
    """
}
