process GDTOOLS_CONVERT {
    tag "$meta.id"
    label 'process_single'

    conda "bioconda::breseq=0.39.0"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/breseq:0.39.0--hdcf5f25_2' :
        'quay.io/biocontainers/breseq:0.39.0--hdcf5f25_2' }"

    input:
    tuple val(meta), path(gd)
    path(reference)

    output:
    tuple val(meta), path("*.breseq.vcf"), emit: vcf
    path "versions.yml",                   emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def prefix = task.ext.prefix ?: "${meta.id}"

    """
    gdtools CONVERT \\
        -f VCF \\
        -r ${reference} \\
        -o ${prefix}.breseq.vcf \\
        ${gd}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gdtools: \$(gdtools --version 2>&1 | head -n1 | sed 's/.*gdtools //')
    END_VERSIONS
    """
}
