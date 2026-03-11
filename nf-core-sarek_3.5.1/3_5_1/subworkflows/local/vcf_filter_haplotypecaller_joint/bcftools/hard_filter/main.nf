process BCFTOOLS_HARD_FILTER_JOINT {
    tag "$meta.id"
    label 'process_low'

    conda "bioconda::bcftools=1.17"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/5a/5acacb55c52bec97c61fd34ffa8721fce82ce823005793592e2a80bf71632cd0/data':
        'community.wave.seqera.io/library/bcftools:1.21--4335bec1d7b44d11' }"

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path("*.hard_filtered.vcf.gz"), emit: vcf
    tuple val(meta), path("*.hard_filtered.vcf.gz.tbi"), emit: tbi
    path "versions.yml", emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    """
    # ========================================
    # HARD FILTERING FOR INDIVIDUAL VCFs FROM JOINT CALLING
    # ========================================
    # Step 1: Split multi-allelic variants into bi-allelic records
    # Step 2: Apply sample-specific quality filters (FORMAT/GQ, FORMAT/DP)
    # Filters configured in: conf/modules/custom_haplotypecaller_joint_filter.config
    #
    # NOTE: Removes variants entirely (no --set-GTs), for clean MultiQC reporting
    # This ensures accurate variant counts across pipeline stages
    # ========================================

    # Split multi-allelic sites into bi-allelic records
    bcftools norm \\
        --force \\
        -m - \\
        -O z \\
        -o ${prefix}.normalized.vcf.gz \\
        $vcf

    # Apply hard filters on normalized VCF
    bcftools filter \\
        $args \\
        -O z \\
        -o ${prefix}.hard_filtered.vcf.gz \\
        ${prefix}.normalized.vcf.gz

    bcftools index -t ${prefix}.hard_filtered.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}
