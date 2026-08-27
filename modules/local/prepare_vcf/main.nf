// Pre-process VCFs for igv-reports display:
//   - Multi-allelic splitting (bcftools norm -m-)
//   - FILTER column promotion to INFO/VCF_FILTER
//   - Per-sample VAF calculation
//
// Runs once per (sample x caller) - HC joint, HC per-sample, CNVKit, Manta, TIDDIT - so the tag and
// the output name carry BOTH ids. A meta.id-only name made the tasks indistinguishable in the trace
// and let four tasks race for one publish target (see conf/modules/mutation_report.config).
process PREPARE_VCF {
    tag "${meta.id}_${meta.caller}"
    label 'process_low'

    conda 'bioconda::bcftools=1.20'
    container 'quay.io/biocontainers/bcftools:1.20--h8b25389_0'

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path("${prefix}.prepared.vcf.gz"), path("${prefix}.prepared.vcf.gz.tbi"), emit: vcf
    path "versions.yml",                                                                        emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    prefix = "${meta.id}.${meta.caller}"
    """
    # Step 1: Split multi-allelic sites into biallelic rows
    bcftools norm -m- --old-rec-tag ORIG_ALT --force ${vcf} -Oz -o tmp_split_raw.vcf.gz
    tabix -p vcf tmp_split_raw.vcf.gz

    # Step 1b: For per-sample VCFs, remove rows where GT became ref after splitting
    if [ "${meta.id}" != "cohort" ]; then
        bcftools view -e 'GT="ref"' tmp_split_raw.vcf.gz -Oz -o tmp_split.vcf.gz
    else
        mv tmp_split_raw.vcf.gz tmp_split.vcf.gz
    fi
    tabix -p vcf tmp_split.vcf.gz

    # Step 2: Copy FILTER column into INFO/VCF_FILTER
    bcftools view tmp_split.vcf.gz \\
        | awk 'BEGIN{OFS="\\t"}
            /^##/{print; next}
            /^#CHROM/{
                print "##INFO=<ID=VCF_FILTER,Number=1,Type=String,Description=\\"Original VCF FILTER value\\">"
                print; next
            }
            {
                filt=\$7
                gsub(/;/, ",", filt)
                \$8="VCF_FILTER=" filt ";" \$8
                print
            }' \\
        | bgzip > tmp_with_filter.vcf.gz
    tabix -p vcf tmp_with_filter.vcf.gz

    # Step 3: Add per-sample VAF
    bcftools +fill-tags tmp_with_filter.vcf.gz -Oz -o ${prefix}.prepared.vcf.gz -- -t FORMAT/VAF
    tabix -p vcf ${prefix}.prepared.vcf.gz

    rm -f tmp_split_raw.vcf.gz tmp_split_raw.vcf.gz.tbi tmp_split.vcf.gz tmp_split.vcf.gz.tbi tmp_with_filter.vcf.gz tmp_with_filter.vcf.gz.tbi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version | head -1 | sed 's/bcftools //')
    END_VERSIONS
    """
}
