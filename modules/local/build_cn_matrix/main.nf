// Build per-sample CN matrices from CNVKit output
// Wraps bin/build_cn_matrix.py — produces segment and bin-level matrices
process BUILD_CN_MATRIX {
    tag "$meta.id"
    label 'process_low'

    conda 'conda-forge::pandas conda-forge::numpy'
    container 'quay.io/biocontainers/pandas:2.2.1'

    input:
    tuple val(meta), path(cnvkit_files, stageAs: 'cnvkit_in/*')  // flat list: .md.cnr, .md.call.cns, .md.germline.call.cns (all samples)
    path fai                                                     // reference .fai for chromosome lengths

    output:
    tuple val(meta), path("cn_matrices"),               emit: cn_matrices
    path "cn_matrices/cn_chr_summary_germline.csv",     emit: chr_summary
    path "versions.yml",                                emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    """
    # build_cn_matrix.py discovers .cns/.cnr from variant_calling/cnvkit/{sample}/.
    # Reconstruct that layout from a flat collected filelist (channel-based, no params.outdir read).
    # Sample name = filename up to the first '.md.' token (e.g. CBR110-15-R3a.md.cnr → CBR110-15-R3a).
    mkdir -p variant_calling/cnvkit
    for f in cnvkit_in/*; do
        fname=\$(basename "\$f")
        sample="\${fname%%.md.*}"
        mkdir -p "variant_calling/cnvkit/\${sample}"
        ln -sf "\$(readlink -f "\$f")" "variant_calling/cnvkit/\${sample}/\${fname}"
    done

    build_cn_matrix.py --output-dir . --fai ${fai}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python --version 2>&1 | sed 's/Python //')
        build_cn_matrix: "1.0"
    END_VERSIONS
    """
}
