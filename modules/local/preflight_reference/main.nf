// yAMP preflight, task level: do the reference files handed to the pipeline agree with each other?
//
// A task rather than a DAG-build check, so cloud paths (az://, s3://) are staged like any other
// input and the check runs in the QC-only run as well. Its only output is a MultiQC custom-content
// table — nothing downstream depends on it, so adding it changed no other task's inputs or hashes.
// conf/modules/preflight.config terminates the run on a failed check and echoes the verdict lines.
// The checks themselves: bin/preflight_reference.sh. User page: docs/usage/preflight_checks.md.
process PREFLIGHT_REFERENCE {
    tag "reference"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/gawk:5.3.0' :
        'biocontainers/gawk:5.3.0' }"

    input:
    path fasta
    path gff3    // [] when --report_gff3 is unset: the FASTA-vs-GFF3 row then reads SKIPPED

    output:
    path "preflight_reference_mqc.tsv", emit: mqc
    path "versions.yml",                emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def gff3_arg = gff3 ? "--gff3 ${gff3}" : ''
    """
    preflight_reference.sh --fasta ${fasta} ${gff3_arg} --out preflight_reference_mqc.tsv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gawk: \$(gawk --version | sed '1!d; s/^GNU Awk //; s/,.*//')
    END_VERSIONS
    """
}
