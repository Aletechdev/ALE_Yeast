// Build collapsed CN cohort matrix from bin-level continuous CN data
// Wraps bin/cn_cohort_matrix.py — collapses baseline bins and merges adjacent regions
process BUILD_CN_COHORT {
    tag 'cn_cohort'
    label 'process_low'

    conda 'conda-forge::pandas'
    container 'quay.io/biocontainers/pandas:2.2.1'

    input:
    path cn_matrices_dir   // directory containing cn_bins_continuous.csv
    path fai               // reference .fai for chromosome lengths

    output:
    path "cn_cohort_collapsed.csv", emit: collapsed
    path "cn_cohort_full.csv",      emit: full
    path "versions.yml",            emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Full (uncollapsed) cohort matrix
    cn_cohort_matrix.py \\
        --cn-dir ${cn_matrices_dir} \\
        --csv cn_cohort_full.csv

    # Collapsed matrix (baseline removed, adjacent merged)
    cn_cohort_matrix.py \\
        --cn-dir ${cn_matrices_dir} \\
        --csv cn_cohort_collapsed.csv \\
        --collapse \\
        --fai ${fai}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version 2>&1 | sed 's/Python //')
        cn_cohort_matrix: "1.0"
    END_VERSIONS
    """
}
