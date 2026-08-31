// Guard for SVDB_MERGE --same_order: svdb never checks sample-column NAMES — with
// misaligned columns it exits 0 and silently assigns genotypes by POSITION under the
// first file's header (proved in 04_validate/sv_merge_bench/, finding F6). Both inputs
// are sorted by sample name upstream (joint Manta CRAMs via groupTuple(sort), TIDDIT
// via SVDB_MERGE sort_inputs), so a mismatch here means that invariant broke — fail loudly.
process CHECK_SV_SAMPLE_ORDER {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/../../nf-core/svdb/merge/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/f5/f59712ead354411dd8bea4918d777737ca4ef2ad1360289507fe35acb688e74f/data':
        'community.wave.seqera.io/library/bcftools_svdb:12db401acbacc624' }"

    input:
    tuple val(meta), path(manta_vcf), path(tiddit_vcf)

    output:
    tuple val(meta), path(manta_vcf), path(tiddit_vcf), emit: vcfs
    path "versions.yml"                               , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    bcftools query -l ${manta_vcf}  > manta_samples.txt
    bcftools query -l ${tiddit_vcf} > tiddit_samples.txt
    if ! diff manta_samples.txt tiddit_samples.txt; then
        echo "ERROR: sample columns differ between ${manta_vcf} and ${tiddit_vcf} —" \\
             "svdb --same_order would silently mislabel genotypes (bench finding F6)." >&2
        exit 1
    fi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bcftools: \$(bcftools --version 2>&1 | head -n1 | sed 's/^.*bcftools //; s/ .*\$//')
    END_VERSIONS
    """
}
