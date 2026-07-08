// Sort, bgzip and tabix-index GFF3 gene annotation for igv-reports
process PREPARE_GFF3 {
    tag 'gene_annotations'
    label 'process_low'

    conda 'bioconda::htslib=1.21'
    container 'quay.io/biocontainers/htslib:1.21--h566b1c6_1'

    input:
    path gff3

    output:
    tuple path("genes.sorted.gff3.gz"), path("genes.sorted.gff3.gz.tbi"), emit: gff3
    path "versions.yml",                                                   emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    (grep "^#" ${gff3}; grep -v "^#" ${gff3} | sort -k1,1 -k4,4n) \
        | bgzip > genes.sorted.gff3.gz
    tabix -p gff genes.sorted.gff3.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        htslib: \$(tabix --version | head -1 | sed 's/.*tabix (htslib) //')
    END_VERSIONS
    """
}
