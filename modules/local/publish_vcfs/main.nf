// Organize annotated VCFs for download, renaming for user-friendly access
process PUBLISH_VCFS {
    tag 'vcf_files'
    label 'process_low'

    conda 'bioconda::bcftools=1.20'
    container 'quay.io/biocontainers/bcftools:1.20--h8b25389_0'

    input:
    tuple val(meta_cohort), path(cohort_vcf), path(cohort_tbi)
    path hc_vcfs
    path cnvkit_vcfs
    path manta_vcfs
    path tiddit_vcfs
    path tiddit_pass_vcfs

    output:
    path "haplotypecaller/*",  emit: hc
    path "cnvkit/*",           emit: cnvkit
    path "manta/*",            emit: manta
    path "tiddit/*",           emit: tiddit
    path "README.md",          emit: readme
    path "versions.yml",       emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    mkdir -p haplotypecaller cnvkit manta tiddit

    cp ${cohort_vcf} haplotypecaller/cohort_haplotypecaller_annotated.vcf.gz
    cp ${cohort_tbi} haplotypecaller/cohort_haplotypecaller_annotated.vcf.gz.tbi

    for f in ${hc_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz\$//' | sed 's/.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "haplotypecaller/\${sample}_haplotypecaller_annotated.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "haplotypecaller/\${sample}_haplotypecaller_annotated.vcf.gz"
        fi
    done

    for f in ${cnvkit_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.cnvcall_snpEff.ann.vcf.gz\$//' | sed 's/.cnvcall_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "cnvkit/\${sample}_cnvkit.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "cnvkit/\${sample}_cnvkit.vcf.gz"
        fi
    done

    for f in ${manta_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.manta.diploid_sv_snpEff.ann.vcf.gz\$//' | sed 's/.manta.diploid_sv_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "manta/\${sample}_manta.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "manta/\${sample}_manta.vcf.gz"
        fi
    done

    for f in ${tiddit_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.tiddit_snpEff.ann.vcf.gz\$//' | sed 's/.tiddit_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "tiddit/\${sample}_tiddit.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "tiddit/\${sample}_tiddit.vcf.gz"
        fi
    done

    for f in ${tiddit_pass_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.tiddit.pass.vcf.gz\$//' | sed 's/.tiddit.pass.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "tiddit/\${sample}_tiddit_pass.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "tiddit/\${sample}_tiddit_pass.vcf.gz"
        fi
    done

    cat > README.md << 'EOF'
# VCF Downloads

Pre-normalization annotated VCF files organized by variant caller.
See index.html methodology section for processing details.
EOF

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version | head -1 | sed 's/bcftools //')
    END_VERSIONS
    """
}
