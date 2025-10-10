process BCFTOOLS_FILTER_NORMAL {
    tag "$meta.id"
    label 'process_low'
    
    conda "bioconda::bcftools=1.17"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/5a/5acacb55c52bec97c61fd34ffa8721fce82ce823005793592e2a80bf71632cd0/data':
        'community.wave.seqera.io/library/bcftools:1.21--4335bec1d7b44d11' }"

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path("*.normal.vcf.gz"), emit: vcf
    tuple val(meta), path("*.normal.vcf.gz.tbi"), emit: tbi
    path "versions.yml", emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    """
    # ========================================
    # GERMLINE QUALITY FILTERING FOR FREEBAYES
    # ========================================
    # Apply quality filters to FreeBayes germline VCF
    # Filters configured in: conf/modules/custom_freebayes_filter.config
    #
    # NOTE: Multi-allelic sites are preserved in output
    # For multi-allelic splitting, see: docs/manual_vcf_operations.md
    # ========================================

    bcftools view \\
        $args \\
        -O z \\
        -o ${prefix}.normal.vcf.gz \\
        $vcf

    bcftools index -t ${prefix}.normal.vcf.gz
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}