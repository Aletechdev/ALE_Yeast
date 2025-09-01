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
    
    # Three-step filtering pipeline for Mutect2
    # Step 1: Apply quality filters  
    # Step 2: Split multi-allelic sites
    # Step 3: Apply somatic AF-based filters
    bcftools view \\
        $args \\
        $vcf \\
        -O z \\
    | bcftools norm -m- -O z \\
    | bcftools view \\
        -i "FORMAT/AF[\$TUMOR_IDX:0] > 0.05 && (FORMAT/AF[\$TUMOR_IDX:0] - FORMAT/AF[\$NORMAL_IDX:0]) > 0.05 && FORMAT/DP[\$TUMOR_IDX] >= 10 && FORMAT/DP[\$NORMAL_IDX] >= 8" \\
        -O z \\
        -o ${prefix}.somatic.vcf.gz
        
    # FILTER CRITERIA EXPLANATION:
    # 1. Tumor AF > 0.05 (5%): Variant present with minimum frequency in tumor
    # 2. AF difference > 0.05 (5%): Significant increase from normal to tumor  
    # 3. Depth filters: Minimum coverage for reliable calling (tumor≥10, normal≥8)
    bcftools index -t ${prefix}.somatic.vcf.gz
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}