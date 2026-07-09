// Build SV cohort matrix from per-sample SURVIVOR-merged VCFs
// Wraps bin/sv_cohort_matrix.py — runs cohort-level SURVIVOR merge
// and maps events back to per-sample callers
//
// Takes two sets of VCFs: PASS-filtered (union_pass) and unfiltered (union)
// Produces separate cohort matrices for each.
process BUILD_SV_COHORT {
    tag 'sv_cohort'
    label 'process_low'

    conda 'bioconda::survivor=1.0.7 bioconda::bcftools=1.20 conda-forge::pandas'
    container null  // No single biocontainer has all three; use conda

    input:
    path pass_vcf_files    // flat list of PASS-filtered per-sample merged VCFs + TBIs
    path union_vcf_files   // flat list of unfiltered per-sample merged VCFs + TBIs

    output:
    path "sv_cohort_matrix_union.csv",      emit: union_csv
    path "sv_cohort_matrix_union_pass.csv", emit: union_pass_csv
    path "versions.yml",                    emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Stage PASS-filtered VCFs into sv_merged_pass/{sample}/
    mkdir -p sv_merged_pass
    for f in ${pass_vcf_files}; do
        [ ! -f "\$f" ] && continue
        [[ "\$f" != *.vcf.gz ]] && [[ "\$f" != *.vcf.gz.tbi ]] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.survivor.union_pass.vcf.gz\$//' | sed 's/.survivor.union_pass.vcf.gz.tbi\$//')
        mkdir -p "sv_merged_pass/\${sample}"
        ln -sf "\$(readlink -f \$f)" "sv_merged_pass/\${sample}/\${base}"
    done

    # Stage unfiltered VCFs into sv_merged_union/{sample}/
    mkdir -p sv_merged_union
    for f in ${union_vcf_files}; do
        [ ! -f "\$f" ] && continue
        [[ "\$f" != *.vcf.gz ]] && [[ "\$f" != *.vcf.gz.tbi ]] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.survivor.union.vcf.gz\$//' | sed 's/.survivor.union.vcf.gz.tbi\$//')
        mkdir -p "sv_merged_union/\${sample}"
        ln -sf "\$(readlink -f \$f)" "sv_merged_union/\${sample}/\${base}"
    done

    # PASS-filtered cohort matrix
    sv_cohort_matrix.py \\
        --output-dir . \\
        --sv-merged-dir sv_merged_pass \\
        --source union_pass \\
        --csv sv_cohort_matrix_union_pass.csv

    # Unfiltered cohort matrix
    sv_cohort_matrix.py \\
        --output-dir . \\
        --sv-merged-dir sv_merged_union \\
        --source union \\
        --csv sv_cohort_matrix_union.csv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version 2>&1 | sed 's/Python //')
        sv_cohort_matrix: "1.0"
        survivor: \$(SURVIVOR 2>&1 | grep -i 'version' | head -1 | sed 's/.*Version: //' || echo "1.0.7")
    END_VERSIONS
    """
}
