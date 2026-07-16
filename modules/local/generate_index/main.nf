// Generate Jinja2-based multi-caller dashboard index.html
process GENERATE_INDEX {
    tag 'index'
    label 'process_low'

    // generate_index.py needs only pandas + jinja2. No slim biocontainer bundles both,
    // so we ship a self-owned image built from containers/generate_index/Dockerfile.
    // Canonical: public Docker Hub. Backup/mirror: ghcr.io/aletechdev/ale-reports:1.0.0
    // (private). Both are published by .github/workflows/build-generate-index-container.yml.
    // On -profile conda/wave the conda directive drives the build; the container is ignored.
    // On -profile docker/singularity the container is used. See
    // docs/generate_mutation_report/generate_index_container.md.
    //
    // SINGLE source of truth for the image tag = params.report_container (nextflow.config).
    // Bump the release tag THERE, not here — this directive just reads it (no hidden override).
    conda 'conda-forge::pandas conda-forge::jinja2'
    container "${ params.report_container }"

    input:
    path cohort_report
    path sample_reports
    path multiqc_data_dir
    path generate_index_script
    path templates_dir
    path cnv_sv_data, stageAs: "data/*"   // CN/SV CSVs + pass_stats staged into data/ subdir
    path multiqc_report                   // real multiqc_report.html file (or NO_FILE sentinel)
    path prepared_cohort_vcf

    output:
    path "index.html",          emit: index
    path "multiqc_report.html", emit: multiqc, optional: true
    path "versions.yml",        emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def has_cnv_sv = cnv_sv_data instanceof List ? cnv_sv_data.any { it.name != 'NO_FILE' } : cnv_sv_data.name != 'NO_FILE'
    def cnv_sv_arg = has_cnv_sv ? "--cnv-sv-data-dir data" : ""
    // Link to the co-published multiqc_report.html when the real file is provided.
    def has_multiqc = multiqc_report.name != 'NO_FILE'
    def mqc_path_arg = has_multiqc ? "--multiqc-report-path '${multiqc_report.name}'" : ""
    def prepared_vcf_arg = prepared_cohort_vcf.name != 'NO_FILE' ? "--prepared-vcf ${prepared_cohort_vcf}" : ""
    // Discover pass_stats TSVs from the staged data/ directory.
    def data_files = cnv_sv_data instanceof List ? cnv_sv_data : [cnv_sv_data]
    def stats_files = data_files.findAll { it.name.endsWith('.pass_stats.tsv') && it.name != 'NO_FILE' }
    // Files are staged via `stageAs: "data/*"`, so it.name already includes the `data/` prefix.
    def pass_stats_arg = stats_files ? "--pass-stats ${stats_files.collect { it.name }.join(' ')}" : ""
    def python_bin = task.ext.python_bin ?: 'python'

    """
    # Create samples/ symlinks so discover_igv_reports() can find reports.
    # Exclude cohort and multiqc reports (they are not per-sample reports).
    mkdir -p samples
    for f in *_report.html; do
        [ -f "\$f" ] && [ "\$f" != "cohort_report.html" ] && [ "\$f" != "multiqc_report.html" ] \\
            && ln -sf "../\$f" "samples/\$f" || true
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
