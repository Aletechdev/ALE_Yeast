// Build SV cohort matrix from per-sample SURVIVOR-merged VCFs
// Wraps bin/sv_cohort_matrix.py — runs cohort-level SURVIVOR merge
// and maps events back to per-sample callers
//
// sv_cohort_matrix.py expects: sv_merged_dir/{sample}/{sample}.survivor.union_pass.vcf.gz
// This process stages flat VCFs into that directory structure before running.
process BUILD_SV_COHORT {
    tag 'sv_cohort'
    label 'process_low'

    conda 'bioconda::survivor=1.0.7 bioconda::bcftools=1.20 conda-forge::pandas'
    container null  // No single biocontainer has all three; use conda

    input:
    path vcf_files   // flat list of per-sample merged VCFs + TBIs

    output:
    path "sv_cohort_matrix_union.csv",      emit: union_csv
    path "sv_cohort_matrix_union_pass.csv", emit: union_pass_csv
    path "versions.yml",                    emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Stage flat VCFs into sv_merged/{sample}/ directory structure
    # Expected filenames: {sample}.survivor.union_pass.vcf.gz + .tbi
    mkdir -p sv_merged
    for f in *.vcf.gz; do
        [ ! -f "\$f" ] && continue
        # Extract sample name: {sample}.survivor.union_pass.vcf.gz -> {sample}
        sample=\$(echo "\$f" | sed 's/.survivor.union_pass.vcf.gz\$//')
        mkdir -p "sv_merged/\${sample}"
        ln -s "../../\$f" "sv_merged/\${sample}/\$f"
        if [ -f "\${f}.tbi" ]; then
            ln -s "../../\${f}.tbi" "sv_merged/\${sample}/\${f}.tbi"
        fi
    done

    # Run for union (all calls, using union_pass VCFs as source — they're what we have)
    sv_cohort_matrix.py \\
        --output-dir . \\
        --sv-merged-dir sv_merged \\
        --source union_pass \\
        --csv sv_cohort_matrix_union_pass.csv

    # Also produce union CSV (same source, different label for dashboard)
    cp sv_cohort_matrix_union_pass.csv sv_cohort_matrix_union.csv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version 2>&1 | sed 's/Python //')
        sv_cohort_matrix: "1.0"
        survivor: \$(SURVIVOR 2>&1 | grep -i 'version' | head -1 | sed 's/.*Version: //' || echo "1.0.7")
    END_VERSIONS
    """
}
