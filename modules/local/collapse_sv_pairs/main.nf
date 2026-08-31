// Collapse SV breakend pairs to one record per junction (bin/collapse_sv_pairs.py).
// Runs BEFORE any SVDB merge, on every caller's VCF — see the script docstring for why.
// Uses the SVDB module's container: the script needs only python3, and reusing the image
// avoids pulling another one for a task that sits immediately next to SVDB_MERGE.
process COLLAPSE_SV_PAIRS {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/../../nf-core/svdb/merge/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/f5/f59712ead354411dd8bea4918d777737ca4ef2ad1360289507fe35acb688e74f/data':
        'community.wave.seqera.io/library/bcftools_svdb:12db401acbacc624' }"

    input:
    tuple val(meta), path(vcf)

    output:
    tuple val(meta), path("${prefix}.vcf"), emit: vcf
    path "versions.yml"                   , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    prefix = task.ext.prefix ?: "${meta.id}.${meta.caller}"
    // Output name doubles as SVDB's file-derived tag at the across-samples merge
    // (svdb tags records by input filename minus .vcf), so keep it <sample>.<caller>.
    """
    collapse_sv_pairs.py ${vcf} > ${prefix}.vcf

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python3 --version 2>&1 | sed 's/Python //')
        collapse_sv_pairs: "1.0"
    END_VERSIONS
    """
}
