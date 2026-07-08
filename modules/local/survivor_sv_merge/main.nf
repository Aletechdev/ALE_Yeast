// SURVIVOR merge — merge Manta + TIDDIT VCFs for a single sample
// Takes pre-filtered/decompressed plain VCFs from FILTER_SV_VCF
process SURVIVOR_SV_MERGE {
    tag "$meta.id"
    label 'process_low'

    conda 'bioconda::survivor=1.0.7 bioconda::htslib=1.20'
    container 'quay.io/biocontainers/survivor:1.0.7--h077b44d_7'

    input:
    tuple val(meta), path(manta_vcf), path(tiddit_vcf)

    output:
    tuple val(meta), path("${prefix}.vcf.gz"), path("${prefix}.vcf.gz.tbi"), emit: vcf
    path "versions.yml",                                                      emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def min_callers = task.ext.min_callers ?: 1
    prefix = "${meta.id}.survivor.${meta.merge_mode ?: 'union'}"
    """
    # Create filelist for SURVIVOR
    echo "${manta_vcf}" > filelist.txt
    echo "${tiddit_vcf}" >> filelist.txt

    # SURVIVOR merge: max_dist=1000 min_callers take_type=1 take_strand=0 estimate_dist=0 min_size=50
    SURVIVOR merge filelist.txt 1000 ${min_callers} 1 0 0 50 merged_raw.vcf

    # Sort, compress and index
    grep '^#' merged_raw.vcf > header.vcf
    grep -v '^#' merged_raw.vcf | sort -k1,1V -k2,2n > body.vcf
    cat header.vcf body.vcf | bgzip > ${prefix}.vcf.gz
    tabix -p vcf ${prefix}.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        survivor: \$(SURVIVOR 2>&1 | grep -i 'version' | head -1 | sed 's/.*Version: //' || echo "1.0.7")
    END_VERSIONS
    """
}
