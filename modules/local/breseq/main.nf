process BRESEQ {
    tag "$meta.id"
    label 'process_high'

    conda "bioconda::breseq=0.39.0"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/breseq:0.39.0--hdcf5f25_2' :
        'quay.io/biocontainers/breseq:0.39.0--hdcf5f25_2' }"

    input:
    tuple val(meta), path(reads)
    path(reference)

    output:
    tuple val(meta), path("${prefix}/output/output.gd"),    emit: gd
    tuple val(meta), path("${prefix}/data/annotated.gd"),   emit: annotated_gd
    tuple val(meta), path("${prefix}/output/index.html"),   emit: html_report
    tuple val(meta), path("${prefix}/output/summary.json"), emit: summary
    tuple val(meta), path("${prefix}/output/**"),            emit: output_dir
    path "versions.yml",                                    emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    prefix = task.ext.prefix ?: "${meta.id}"
    def population_flag = meta.clonal_or_population == 'population' ? '-p' : ''
    def parallel_flag = task.cpus > 1 ? "-j ${task.cpus}" : ''

    """
    breseq \\
        ${population_flag} \\
        ${parallel_flag} \\
        -r ${reference} \\
        ${args} \\
        -o ${prefix} \\
        ${reads}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        breseq: \$(breseq --version 2>&1 | head -n1 | sed 's/.*breseq //')
    END_VERSIONS
    """
}
