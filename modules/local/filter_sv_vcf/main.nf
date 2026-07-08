// Decompress and optionally PASS-filter SV VCFs for SURVIVOR merge
// Produces plain-text VCFs that SURVIVOR can read
process FILTER_SV_VCF {
    tag "${meta.id}_${meta.caller}"
    label 'process_low'

    conda 'bioconda::bcftools=1.20'
    container 'quay.io/biocontainers/bcftools:1.20--h8b25389_0'

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path("${meta.id}.${meta.caller}.filtered.vcf"), emit: vcf
    path "versions.yml",                                              emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def pass_filter = task.ext.pass_only ? "-f PASS" : ""
    """
    bcftools view ${pass_filter} ${vcf} -Ov -o ${meta.id}.${meta.caller}.filtered.vcf

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version | head -1 | sed 's/bcftools //')
    END_VERSIONS
    """
}
