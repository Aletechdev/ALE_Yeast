process GATK4_VARIANTFILTRATION {
    tag "${meta.id}"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    // ALE: the image of the other GATK modules in this tree, not upstream's gatk4_gcnvkernel (GATK
    // 4.6.2.0, 2 GB, this module only). A cold node then pulls nothing extra for this step; the
    // filtered records are identical (docs/dev-practices/SAREK_MODIFICATIONS.md, PATCHED).
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/gatk4:4.5.0.0--py36hdfd78af_0':
        'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0' }"

    input:
    tuple val(meta), path(vcf), path(tbi)
    tuple val(meta2), path(fasta)
    tuple val(meta3), path(fai)
    tuple val(meta4), path(dict)
    tuple val(meta5), path(gzi)

    output:
    tuple val(meta), path("*.vcf.gz"), emit: vcf
    tuple val(meta), path("*.tbi"),    emit: tbi
    path "versions.yml",               emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"

    // Infer .dict file name that gatk expects, even if ends in .fasta.gz
    def dict_name = fasta.getBaseName()
    if (dict_name ==~ /^.*\.(fasta|fna|fa)$/) {
        dict_name = dict_name.replaceAll(/\.(fasta|fna|fa)$/, "")
    }
    dict_name = "${dict_name}.dict"

    def avail_mem = 3072
    if (!task.memory) {
        log.info('[GATK VariantFiltration] Available memory not known - defaulting to 3GB. Specify process memory requirements to change this.')
    }
    else {
        avail_mem = (task.memory.mega * 0.8).intValue()
    }
    """
    # Make sure the .dict file is named correctly
    if [[ ${dict_name} != ${dict} ]]; then
        ln -s ${dict} ${dict_name}
    fi

    gatk --java-options "-Xmx${avail_mem}M -XX:-UsePerfData" \\
        VariantFiltration \\
        --variant ${vcf} \\
        --output ${prefix}.vcf.gz \\
        --reference ${fasta} \\
        --tmp-dir . \\
        ${args}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$(echo \$(gatk --version 2>&1) | sed 's/^.*(GATK) v//; s/ .*\$//')
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo "" | gzip > ${prefix}.vcf.gz
    touch ${prefix}.vcf.gz.tbi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$(echo \$(gatk --version 2>&1) | sed 's/^.*(GATK) v//; s/ .*\$//')
    END_VERSIONS
    """
}
