// Convert CNVKit .cnr to BedGraph tracks for igv-reports embedding
process CNR_TO_BEDGRAPH {
    tag "$meta.id"
    label 'process_low'

    // Pure awk — no container needed

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
        | sort -k1,1 -k2,2n > ${meta.id}.depth.bedgraph

    # Log2 ratio track (column 6): copy number ratio vs reference
    tail -n +2 ${cnr} | awk -F'\\t' 'BEGIN{OFS="\\t"} {print \$1,\$2,\$3,\$6}' \
        | sort -k1,1 -k2,2n > ${meta.id}.log2.bedgraph

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gawk: \$(awk -Wversion 2>&1 | sed '1!d; s/.*Awk //; s/,.*//' || echo "unknown")
    END_VERSIONS
    """
}
