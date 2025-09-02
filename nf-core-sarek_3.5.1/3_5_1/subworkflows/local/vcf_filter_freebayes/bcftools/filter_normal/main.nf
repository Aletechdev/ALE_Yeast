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
    # ALLELE FREQUENCY-BASED SOMATIC FILTERING
    # ========================================
    # Migration from GT-based to AF-based filtering for better sensitivity
    # STRATEGY: Multi-allelic splitting followed by AF-based filtering
    # 1. FreeBayes can call multiple alternate alleles at single position (e.g., A→T,G)  
    # 2. AO field contains comma-separated values for each alternate allele
    # 3. bcftools norm -m- splits multi-allelic records into separate single-allelic records
    # 4. After splitting, AO[sample:0] accesses the single alternate allele observation count
    # 
    # STEP 2 DETAILS: Split multi-allelic sites into separate records  
    # This converts variants like "A→T,G" into two records: "A→T" and "A→G"
    # Critical for proper AO field handling since AO becomes single-valued after splitting
    # 
    # EXAMPLE: Position AECK01000002:547636
    # Before: REF=AGTATAC ALT=TGTGTAT,AGTGTAC AO=12,5 (multi-allelic)
    # After:  Record1: REF=AGTATAC ALT=TGTGTAT AO=12 (bi-allelic)
    #         Record2: REF=AGTATAC ALT=AGTGTAC AO=5  (bi-allelic)
    # ========================================
    # THREE-STEP FILTERING PIPELINE
    # ========================================
    
    
    # STEP 1: Split multi-allelic sites into separate records
    # STEP 2: Apply initial quality filters (from task.ext.args)

    bcftools norm -m- $vcf -O z \\
    | bcftools view \\
        $args \\
        -O z \\
        -o ${prefix}.normal.vcf.gz
        

    bcftools index -t ${prefix}.normal.vcf.gz
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}