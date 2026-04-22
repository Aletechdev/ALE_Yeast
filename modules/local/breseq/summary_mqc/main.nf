process BRESEQ_SUMMARY_MQC {
    tag "$meta.id"
    label 'process_single'

    conda "bioconda::breseq=0.39.0"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/breseq:0.39.0--hdcf5f25_2' :
        'quay.io/biocontainers/breseq:0.39.0--hdcf5f25_2' }"

    input:
    tuple val(meta), path(summary_json), path(gd)

    output:
    tuple val(meta), path("*.breseq_mqc.tsv"), emit: mqc
    path "versions.yml",                       emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    breseq_mqc_summary.py \\
        --summary ${summary_json} \\
        --gd ${gd} \\
        --sample ${meta.id}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python3 --version 2>&1 | sed 's/Python //')
    END_VERSIONS
    """
}
