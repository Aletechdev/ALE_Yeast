// SURVIVOR cohort merge — merge per-sample SURVIVOR VCFs into a single cohort VCF
// Input: collected plain VCFs from SURVIVOR_SV_MERGE + merge_mode label
// Output: single cohort-merged plain VCF for BUILD_SV_MATRIX
process SURVIVOR_COHORT_MERGE {
    tag "cohort_${merge_mode}"
    label 'process_low'

    conda 'bioconda::survivor=1.0.7'
    container 'quay.io/biocontainers/survivor:1.0.7--h077b44d_7'

    input:
    path(sample_vcfs)       // collected plain VCFs from SURVIVOR_SV_MERGE
    val(merge_mode)         // 'union_pass' or 'union'

    output:
    path("cohort_merged_${merge_mode}.vcf"), emit: vcf
    path "versions.yml",                     emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # Create filelist for SURVIVOR (one VCF per line)
    ls *.vcf > filelist.txt

    # SURVIVOR merge: max_dist=1000 min_callers=1 take_type=1 take_strand=0 estimate_dist=0 min_size=50
    SURVIVOR merge filelist.txt 1000 1 1 0 0 50 merged_raw.vcf

    # Sort (POSIX-compatible, no GNU -V flag)
    grep '^#' merged_raw.vcf > header.vcf
    grep -v '^#' merged_raw.vcf | sort -k1,1d -k2,2n > body.vcf
    cat header.vcf body.vcf > cohort_merged_${merge_mode}.vcf

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        survivor: \$(SURVIVOR 2>&1 | grep -i 'version' | head -1 | sed 's/.*Version: //' || echo "1.0.7")
    END_VERSIONS
    """
}
