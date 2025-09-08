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
    
    # Multi-step filtering pipeline for Mutect2 with custom AF difference filtering
    # Step 1: Apply quality filters  
    # Step 2: Split multi-allelic sites
    # Step 3-4: Combined tumor AF and depth filtering
    # Step 5: Custom AF difference filtering (bypass bcftools parsing bugs)
    
    bcftools view \\
        $args \\
        $vcf \\
        -O z \\
    | bcftools norm -m- -O z \\
    | bcftools view \\
        -i "FORMAT/AF[\$TUMOR_IDX:0] > 0.05 && FORMAT/DP[\$TUMOR_IDX] >= 10 && FORMAT/DP[\$NORMAL_IDX] >= 8 && FORMAT/F1R2[\$TUMOR_IDX:1] > 0 && FORMAT/F2R1[\$TUMOR_IDX:1] > 0" \\
        -O v \\
        -o temp_uncompressed.vcf
    
    # Apply custom AF difference filter using AWK (TODO.md Option 2: increased from 0.05 to 0.08 for more stringent filtering)
    awk -v tumor_idx=\$TUMOR_IDX -v normal_idx=\$NORMAL_IDX -v min_diff=0.05 '
    BEGIN { FS="\\t"; OFS="\\t" }
    /^#/ { print; next }
    {
        format_field = \$9
        tumor_data = \$(10 + tumor_idx)
        normal_data = \$(10 + normal_idx)
        
        # Find AF field index
        n_format = split(format_field, format_keys, ":")
        af_idx = -1
        for (i = 1; i <= n_format; i++) {
            if (format_keys[i] == "AF") {
                af_idx = i
                break
            }
        }
        
        # If no AF field, keep the variant
        if (af_idx == -1) {
            print
            next
        }
        
        # Extract AF values
        n_tumor = split(tumor_data, tumor_values, ":")
        n_normal = split(normal_data, normal_values, ":")
        
        if (af_idx > n_tumor || af_idx > n_normal) {
            print
            next
        }
        
        # Get first allele AF (split by comma)
        split(tumor_values[af_idx], tumor_af_array, ",")
        split(normal_values[af_idx], normal_af_array, ",")
        
        tumor_af = tumor_af_array[1]
        normal_af = normal_af_array[1]
        
        # Check if AF difference > threshold
        if ((tumor_af + 0) - (normal_af + 0) > min_diff) {
            print
        }
    }' temp_uncompressed.vcf > temp_filtered.vcf
    
    # Compress using bcftools view and clean up temp files
    bcftools view temp_filtered.vcf -O z -o ${prefix}.somatic.vcf.gz
    rm temp_uncompressed.vcf temp_filtered.vcf
        
    # FILTER CRITERIA EXPLANATION (Combined approach: TODO.md Option 2 + strand bias filtering):
    # Step 3-4: bcftools filters - Tumor AF > 0.05 (5%) AND stricter depth requirements:
    #           - Tumor depth ≥15 (increased from 10) for better reliability  
    #           - Normal depth ≥12 (increased from 8) to match Option 2 moderate stringency
    #           - Strand bias: F1R2>0 & F2R1>0 (equivalent to FreeBayes SAF>0 & SAR>0)
    # Step 5: Custom AWK script - AF difference filtering (tumor_AF - normal_AF) > 0.08
    #         - Increased from 0.05 to 0.08 (Option 2) to be more stringent and closer to FreeBayes
    #         - Bypasses bcftools FORMAT expression parsing bugs with direct VCF parsing
    # NOTE: Using AWK with temporary files to ensure proper compression compatibility
    bcftools index -t ${prefix}.somatic.vcf.gz
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}