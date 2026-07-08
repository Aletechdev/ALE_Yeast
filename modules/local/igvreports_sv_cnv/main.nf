// Generate per-sample SV/CNV igv-reports HTML
// Handles CNVKit (with BedGraph coverage tracks), Manta, and TIDDIT
process IGVREPORTS_SV_CNV {
    tag "${meta.id}_${meta.caller}"
    label 'process_low'

    conda 'bioconda::igv-reports=1.16.0'
    container 'quay.io/biocontainers/igv-reports:1.16.0--pyh7e72e81_0'

    input:
    tuple val(meta), path(vcf), path(tbi), path(cram), path(crai), path(depth_bg), path(log2_bg)
    tuple path(gff3_gz), path(gff3_tbi)
    tuple path(fasta), path(fai)
    path template

    output:
    path "${meta.id}_${meta.caller}_report.html", emit: report
    path "versions.yml",                           emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def has_bedgraph = depth_bg.name != 'NO_DEPTH_BG'
    def flanking = has_bedgraph ? 50000 : 500
    def maxlen_arg = has_bedgraph ? "--maxlen 2000000" : ""
    def strip_session = !has_bedgraph && meta.caller != 'manta' && meta.caller != 'tiddit'
    def want_alignment = meta.caller in ['manta', 'tiddit']
    def tracks = has_bedgraph ? "${gff3_gz} ${depth_bg} ${log2_bg}" : (want_alignment ? "${gff3_gz} ${cram}" : "${gff3_gz}")
    def info_cols = meta.caller == 'cnvkit'
        ? "ANN VCF_FILTER SVTYPE SVLEN FOLD_CHANGE FOLD_CHANGE_LOG PROBES"
        : "ANN VCF_FILTER SVTYPE SVLEN"
    def sample_cols = meta.caller == 'cnvkit'
        ? "GT CNQ"
        : meta.caller == 'tiddit'
        ? "GT DV RV DR RR COV LQ"
        : "GT GQ PL PR SR"
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tracks ${tracks} \\
        --template ${template} \\
        --info-columns ${info_cols} \\
        --sample-columns ${sample_cols} \\
        --flanking ${flanking} \\
        ${maxlen_arg} \\
        --title "${meta.id} - ${meta.caller_label} (Yeast ALE)" \\
        --output ${meta.id}_${meta.caller}_report.html

    # Post-process: set custom height and colors for bedgraph coverage tracks
    if [ "${has_bedgraph}" = "true" ]; then
        python3 ${projectDir}/postprocess_cnvkit_report.py ${meta.id}_${meta.caller}_report.html
    fi

    # Strip IGV session data only for callers without alignment view support
    if [ "${strip_session}" = "true" ]; then
        sed -i 's|const sessionDictionary = .*|const sessionDictionary = {};|' ${meta.id}_${meta.caller}_report.html
    fi

    # Set VCF download link and report type
    if [ "${meta.caller}" = "tiddit" ]; then
        sed -i 's|@VCF_HREF@|../vcf/tiddit/${meta.id}_tiddit_pass.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
        sed -i 's|@VCF_FILENAME@|${meta.id}_tiddit_pass.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
        sed -i 's|@VCF_RAW_HREF@|../vcf/tiddit/${meta.id}_tiddit.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
        sed -i 's|@VCF_RAW_FILENAME@|${meta.id}_tiddit.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
    else
        sed -i 's|@VCF_HREF@|../vcf/${meta.caller}/${meta.id}_${meta.caller}.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
        sed -i 's|@VCF_FILENAME@|${meta.id}_${meta.caller}.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
        sed -i 's|@VCF_RAW_HREF@||g' ${meta.id}_${meta.caller}_report.html
        sed -i 's|@VCF_RAW_FILENAME@||g' ${meta.id}_${meta.caller}_report.html
    fi
    if [ "${has_bedgraph}" = "true" ]; then
        sed -i 's|@REPORT_TYPE@|cnvkit_coverage|g' ${meta.id}_${meta.caller}_report.html
    elif [ "${want_alignment}" = "true" ]; then
        sed -i 's|@REPORT_TYPE@|sv_alignment|g' ${meta.id}_${meta.caller}_report.html
    else
        sed -i 's|@REPORT_TYPE@|sv_cnv|g' ${meta.id}_${meta.caller}_report.html
    fi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        igv-reports: \$(pip show igv-reports 2>/dev/null | grep Version | sed 's/Version: //' || echo "1.16.0")
    END_VERSIONS
    """
}
