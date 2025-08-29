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
    # ========================================
    # SAMPLE INDEX DETERMINATION
    # ========================================
    # FreeBayes VCFs contain multiple samples, need to determine which column corresponds to tumor vs normal
    bcftools query -l $vcf > samples.txt
    
    # Find tumor and normal sample indices (1-based from bcftools query -l)
    TUMOR_IDX=\$(grep -n "$tumor_sample_name" samples.txt | cut -d: -f1)
    NORMAL_IDX=\$(grep -n "$normal_sample_name" samples.txt | cut -d: -f1)
    
    # Convert to 0-based indexing for bcftools filtering expressions
    TUMOR_IDX=\$((TUMOR_IDX-1))
    NORMAL_IDX=\$((NORMAL_IDX-1))
    
    echo "Tumor index: \$TUMOR_IDX" > ${prefix}.sample_order.txt
    echo "Normal index: \$NORMAL_IDX" >> ${prefix}.sample_order.txt
    
    # ========================================
    # ALLELE FREQUENCY-BASED SOMATIC FILTERING
    # ========================================
    # Migration from GT-based to AF-based filtering for better sensitivity
    echo "Using AF-based somatic filtering with multi-allelic splitting" >> ${prefix}.sample_order.txt
    
    # STRATEGY: Multi-allelic splitting followed by AF-based filtering
    # 1. FreeBayes can call multiple alternate alleles at single position (e.g., A→T,G)  
    # 2. AO field contains comma-separated values for each alternate allele
    # 3. bcftools norm -m- splits multi-allelic records into separate single-allelic records
    # 4. After splitting, AO[sample:0] accesses the single alternate allele observation count
    # 
    # EXAMPLE: Position AECK01000002:547636
    # Before: REF=AGTATAC ALT=TGTGTAT,AGTGTAC AO=12,5 (multi-allelic)
    # After:  Record1: REF=AGTATAC ALT=TGTGTAT AO=12 (bi-allelic)
    #         Record2: REF=AGTATAC ALT=AGTGTAC AO=5  (bi-allelic)
    # ========================================
    # THREE-STEP FILTERING PIPELINE
    # ========================================
    
    # STEP 1: Apply initial quality filters (from task.ext.args)
    # Typical filters: QUAL>=20, DP>=15, MQM>=20, etc.
    bcftools view \\
        $args \\
        $vcf \\
        -O z \\
    # STEP 2: Split multi-allelic sites into separate records  
    # This converts variants like "A→T,G" into two records: "A→T" and "A→G"
    # Critical for proper AO field handling since AO becomes single-valued after splitting
    | bcftools norm -m- -O z \\
    # STEP 3: Apply somatic variant filters based on allele frequencies
    # AF calculation: AO/(AO+RO) where AO=alternate obs, RO=reference obs
    # After splitting, AO[sample:0] accesses the single alternate allele count
    | bcftools view \\
        -i "(FORMAT/AO[\$NORMAL_IDX:0]/(FORMAT/AO[\$NORMAL_IDX:0]+FORMAT/RO[\$NORMAL_IDX]) < 0.10 || FORMAT/AO[\$NORMAL_IDX:0] = 0) && FORMAT/AO[\$TUMOR_IDX:0]/(FORMAT/AO[\$TUMOR_IDX:0]+FORMAT/RO[\$TUMOR_IDX]) > 0.05 && (FORMAT/AO[\$TUMOR_IDX:0]/(FORMAT/AO[\$TUMOR_IDX:0]+FORMAT/RO[\$TUMOR_IDX]) - FORMAT/AO[\$NORMAL_IDX:0]/(FORMAT/AO[\$NORMAL_IDX:0]+FORMAT/RO[\$NORMAL_IDX])) > 0.05 && FORMAT/DP[\$TUMOR_IDX] >= 10 && FORMAT/DP[\$NORMAL_IDX] >= 8" \\
        -O z \\
        -o ${prefix}.somatic.vcf.gz
        
    # FILTER CRITERIA EXPLANATION:
    # 1. Normal AF < 0.10 (10%) OR AO = 0: Variant absent/rare in normal sample
    # 2. Tumor AF > 0.05 (5%): Variant present with minimum frequency in tumor
    # 3. AF difference > 0.05 (5%): Significant increase from normal to tumor  
    # 4. Depth filters: Minimum coverage for reliable calling (tumor≥10, normal≥8)
    bcftools index -t ${prefix}.somatic.vcf.gz
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}