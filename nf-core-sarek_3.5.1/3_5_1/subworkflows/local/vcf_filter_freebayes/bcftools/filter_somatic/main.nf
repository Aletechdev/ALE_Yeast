process BCFTOOLS_FILTER_SOMATIC {
    tag "$meta.id"
    label 'process_low'
    
    conda "bioconda::bcftools=1.17"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/5a/5acacb55c52bec97c61fd34ffa8721fce82ce823005793592e2a80bf71632cd0/data':
        'community.wave.seqera.io/library/bcftools:1.21--4335bec1d7b44d11' }"

    input:
    tuple val(meta), path(vcf), path(tbi)
    val tumor_sample_name   // e.g., "ALE_Exp1_A4-F5-I1-R1"
    val normal_sample_name  // e.g., "ALE_Exp1_A0-F0-I1-R1"

    output:
    tuple val(meta), path("*.somatic.vcf.gz"), emit: vcf
    tuple val(meta), path("*.somatic.vcf.gz.tbi"), emit: tbi
    path "*.sample_order.txt", emit: sample_info
    path "versions.yml", emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    
    """
    # Get sample order and find indices
    bcftools query -l $vcf > samples.txt
    
    # Find tumor and normal indices
    TUMOR_IDX=\$(grep -n "$tumor_sample_name" samples.txt | cut -d: -f1)
    NORMAL_IDX=\$(grep -n "$normal_sample_name" samples.txt | cut -d: -f1)
    
    # Convert to 0-based indexing
    TUMOR_IDX=\$((TUMOR_IDX-1))
    NORMAL_IDX=\$((NORMAL_IDX-1))
    
    echo "Tumor index: \$TUMOR_IDX" > ${prefix}.sample_order.txt
    echo "Normal index: \$NORMAL_IDX" >> ${prefix}.sample_order.txt
    
    # Create ploidy-aware GT filter based on meta.ploidy
    PLOIDY=${meta.ploidy}
    
    # Define reference genotype (all reference alleles) based on ploidy
    if [ "\$PLOIDY" -eq 1 ]; then
        REF_GT="0"
        NON_REF_FILTER="GT[\$TUMOR_IDX] != '.' && GT[\$TUMOR_IDX] != '0'"
    elif [ "\$PLOIDY" -eq 2 ]; then
        REF_GT="0/0"
        NON_REF_FILTER="GT[\$TUMOR_IDX] != '.' && GT[\$TUMOR_IDX] != '0/0'"
    else
        # For higher ploidy, construct reference GT (e.g., 0/0/0 for ploidy=3)
        REF_GT=\$(python3 -c "print('/'.join(['0'] * \$PLOIDY))")
        NON_REF_FILTER="GT[\$TUMOR_IDX] != '.' && GT[\$TUMOR_IDX] != '\$REF_GT'"
    fi
    
    echo "Using ploidy: \$PLOIDY, Reference GT: \$REF_GT" >> ${prefix}.sample_order.txt
    
    # Apply quality filters first, then somatic genotype filters
    bcftools view \\
        $args \\
        $vcf \\
        -O z \\
    | bcftools view \\
        -i "\$NON_REF_FILTER && GT[\$NORMAL_IDX] = '\$REF_GT' && FORMAT/DP[\$TUMOR_IDX] >= 10 && FORMAT/DP[\$NORMAL_IDX] >= 8" \\
        -O z \\
        -o ${prefix}.somatic.vcf.gz
    bcftools index -t ${prefix}.somatic.vcf.gz
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}