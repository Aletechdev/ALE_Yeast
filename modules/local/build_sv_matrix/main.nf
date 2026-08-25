// Build SV cohort matrix CSV from SURVIVOR cohort-merged VCF
// and per-sample SURVIVOR VCFs (for caller resolution via proximity_match)
process BUILD_SV_MATRIX {
    tag "sv_matrix_${merge_mode}"
    label 'process_low'

    conda 'conda-forge::pandas=2.2.1'
    container 'quay.io/biocontainers/pandas:2.2.1'

    input:
    path(cohort_vcf)        // cohort-merged plain VCF from SURVIVOR_COHORT_MERGE
    path(sample_vcfs)       // collected plain VCFs from SURVIVOR_SV_MERGE
    val(merge_mode)         // 'union_pass' or 'union'

    output:
    path("sv_cohort_matrix_${merge_mode}.csv"), emit: csv
    path "versions.yml",                        emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    sv_cohort_matrix.py \\
        --cohort-vcf ${cohort_vcf} \\
        --sample-vcfs *.survivor.*.vcf \\
        --csv sv_cohort_matrix_${merge_mode}.csv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version 2>&1 | sed 's/Python //')
        sv_cohort_matrix: "2.1"
    END_VERSIONS
    """
}
