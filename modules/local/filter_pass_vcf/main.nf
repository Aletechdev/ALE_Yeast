// Extract PASS-filtered variants and generate stats TSV
process FILTER_PASS_VCF {
    tag "${meta.id}_${meta.caller}"
    label 'process_low'

    conda 'bioconda::bcftools=1.20'
    container 'quay.io/biocontainers/bcftools:1.20--h8b25389_0'

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path("${meta.id}.${meta.caller}.pass.vcf.gz"), path("${meta.id}.${meta.caller}.pass.vcf.gz.tbi"), emit: vcf
    path "${meta.id}.${meta.caller}.pass_stats.tsv",                                                                    emit: stats
    path "versions.yml",                                                                                                 emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    bcftools view -f PASS ${vcf} -Oz -o ${meta.id}.${meta.caller}.pass.vcf.gz
    bcftools index -t ${meta.id}.${meta.caller}.pass.vcf.gz

    TOTAL=\$(bcftools view -H ${vcf} | wc -l)
    PASS=\$(bcftools view -H ${meta.id}.${meta.caller}.pass.vcf.gz | wc -l)
    printf "sample\\tcaller\\ttotal\\tpass\\n%s\\t%s\\t%d\\t%d\\n" "${meta.id}" "${meta.caller}" "\$TOTAL" "\$PASS" > ${meta.id}.${meta.caller}.pass_stats.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version | head -1 | sed 's/bcftools //')
    END_VERSIONS
    """
}
