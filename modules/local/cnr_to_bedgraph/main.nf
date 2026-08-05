// Convert CNVKit .cnr to BedGraph tracks for igv-reports embedding
process CNR_TO_BEDGRAPH {
    tag "$meta.id"
    label 'process_low'

    // Pure awk/sort — but a container is still REQUIRED.
    // Declaring none works with the local executor (Nextflow runs the command directly on the
    // host, where awk and sort exist), but every Azure Batch / cloud task must run in a
    // container, so the process fails at submission with:
    //     No container image specified for process ...:CNR_TO_BEDGRAPH
    //
    // gawk specifically, NOT the nf-core ubuntu image: that ships mawk, which would make the
    // conda path (gawk) and the container path (mawk) different tools, and would make the
    // versions.yml line below mislabel mawk as gawk (its sed expects GNU Awk output).
    conda "conda-forge::gawk=5.3.0"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/gawk:5.3.0' :
        'quay.io/biocontainers/gawk:5.3.0' }"

    input:
    tuple val(meta), path(cnr)

    output:
    tuple val(meta), path("${meta.id}.depth.bedgraph"), path("${meta.id}.log2.bedgraph"), emit: bedgraph
    path "versions.yml",                                                                   emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Depth track (column 5): absolute read depth per bin
    tail -n +2 ${cnr} | awk -F'\\t' 'BEGIN{OFS="\\t"} {print \$1,\$2,\$3,\$5}' \
        | LC_ALL=C sort -k1,1 -k2,2n > ${meta.id}.depth.bedgraph

    # Log2 ratio track (column 6): copy number ratio vs reference
    tail -n +2 ${cnr} | awk -F'\\t' 'BEGIN{OFS="\\t"} {print \$1,\$2,\$3,\$6}' \
        | LC_ALL=C sort -k1,1 -k2,2n > ${meta.id}.log2.bedgraph

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gawk: \$(awk -Wversion 2>&1 | sed '1!d; s/.*Awk //; s/,.*//' || echo "unknown")
    END_VERSIONS
    """
}
