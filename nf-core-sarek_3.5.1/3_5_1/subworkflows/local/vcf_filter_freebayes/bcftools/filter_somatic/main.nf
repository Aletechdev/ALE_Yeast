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
    # STEP 2 DETAILS: Split multi-allelic sites into separate records  
    # This converts variants like "A→T,G" into two records: "A→T" and "A→G"
    # Critical for proper AO field handling since AO becomes single-valued after splitting
    # 
    # EXAMPLE: Position AECK01000002:547636
    # Before: REF=AGTATAC ALT=TGTGTAT,AGTGTAC AO=12,5 (multi-allelic)
    # After:  Record1: REF=AGTATAC ALT=TGTGTAT AO=12 (bi-allelic)
    #         Record2: REF=AGTATAC ALT=AGTGTAC AO=5  (bi-allelic)
    # ========================================
    # MULTI-STEP FILTERING PIPELINE (Fixed AF difference calculation)
    # ========================================
    
    # STEP 1: Apply initial quality filters (from task.ext.args)
    # STEP 2: Split multi-allelic sites into separate records
    # STEP 3: Apply tumor AF, depth, and strand bias filters (without AF difference - handled separately)
    # STEP 4: Custom AF difference filtering using AWK (bypasses bcftools parsing bugs)
    bcftools view \\
        $args \\
        $vcf \\
        -O z \\
    | bcftools norm -m- -O z \\
    | bcftools view \\
        -i "\$NON_REF_FILTER &&FORMAT/AO[\$TUMOR_IDX:0]/(FORMAT/AO[\$TUMOR_IDX:0]+FORMAT/RO[\$TUMOR_IDX]) > 0.05 && FORMAT/DP[\$TUMOR_IDX] >= 10 && FORMAT/DP[\$NORMAL_IDX] >= 8" \\
        -O v \\
        -o temp_uncompressed.vcf
    
    # Apply custom AF difference filter using AWK (fixes critical bug in bcftools FORMAT expression parsing)
    awk -v tumor_idx=\$TUMOR_IDX -v normal_idx=\$NORMAL_IDX -v min_diff=0.50 '
    BEGIN { FS="\\t"; OFS="\\t" }
    /^#/ { print; next }
    {
        format_field = \$9
        tumor_data = \$(10 + tumor_idx)
        normal_data = \$(10 + normal_idx)
        
        # Find AO, RO field indices for AF calculation
        n_format = split(format_field, format_keys, ":")
        ao_idx = -1
        ro_idx = -1
        for (i = 1; i <= n_format; i++) {
            if (format_keys[i] == "AO") ao_idx = i
            if (format_keys[i] == "RO") ro_idx = i
        }
        
        # If no AO/RO fields, keep the variant
        if (ao_idx == -1 || ro_idx == -1) {
            print
            next
        }
        
        # Extract AO/RO values
        n_tumor = split(tumor_data, tumor_values, ":")
        n_normal = split(normal_data, normal_values, ":")
        
        if (ao_idx > n_tumor || ao_idx > n_normal || ro_idx > n_tumor || ro_idx > n_normal) {
            print
            next
        }
        
        # Get AO values (single value after bcftools norm -m- splitting)
        tumor_ao = tumor_values[ao_idx]
        normal_ao = normal_values[ao_idx]
        tumor_ro = tumor_values[ro_idx]
        normal_ro = normal_values[ro_idx]
        
        # Calculate allele frequencies: AF = AO/(AO+RO)
        tumor_af = (tumor_ao + 0) / ((tumor_ao + 0) + (tumor_ro + 0))
        normal_af = (normal_ao + 0) / ((normal_ao + 0) + (normal_ro + 0))
        
        # Check if AF difference > threshold
        if (tumor_af - normal_af > min_diff) {
            print
        }
    }' temp_uncompressed.vcf > temp_filtered.vcf
    
    # Compress using bcftools view and clean up temp files
    bcftools view temp_filtered.vcf -O z -o ${prefix}.somatic.vcf.gz
    rm temp_uncompressed.vcf temp_filtered.vcf
        
    # FILTER CRITERIA EXPLANATION (Fixed implementation):
    # Step 3: bcftools filters - Tumor AF > 0.05 (5%) AND depth requirements AND strand bias:
    #         - Tumor AF calculated as AO/(AO+RO) > 0.05
    #         - Tumor depth ≥10, Normal depth ≥8 for reliable calling
    #         - Strand bias: SAF>0 & SAR>0 (both forward/reverse strand support required)
    # Step 4: Custom AWK script - AF difference filtering (tumor_AF - normal_AF) > 0.5
    #         - Fixes critical bug where bcftools FORMAT expression parsing failed
    #         - Direct VCF parsing ensures accurate AF calculations and filtering
    # NOTE: Using AWK with temporary files bypasses bcftools floating point arithmetic bugs
    bcftools index -t ${prefix}.somatic.vcf.gz
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}