// Build per-sample CN matrices from CNVKit output
// Wraps bin/build_cn_matrix.py — produces segment and bin-level matrices
process BUILD_CN_MATRIX {
    tag "$meta.id"
    label 'process_low'

    conda 'conda-forge::pandas conda-forge::numpy'
    container 'quay.io/biocontainers/pandas:2.2.1'

    input:
    tuple val(meta), path(cnvkit_dir)  // sample cnvkit output dir with .cns/.cnr files
    path fai                           // reference .fai for chromosome lengths

    output:
    tuple val(meta), path("cn_matrices"), emit: cn_matrices
    path "versions.yml",                  emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # build_cn_matrix.py discovers .cns/.cnr from variant_calling/cnvkit/{sample}/
    # Create expected directory structure for the script
    mkdir -p variant_calling/cnvkit/${meta.id}
    ln -s \$(readlink -f ${cnvkit_dir})/*.cns variant_calling/cnvkit/${meta.id}/ 2>/dev/null || true
    ln -s \$(readlink -f ${cnvkit_dir})/*.cnr variant_calling/cnvkit/${meta.id}/ 2>/dev/null || true

    build_cn_matrix.py --output-dir . --fai ${fai}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version 2>&1 | sed 's/Python //')
        build_cn_matrix: "1.0"
    END_VERSIONS
    """
}
