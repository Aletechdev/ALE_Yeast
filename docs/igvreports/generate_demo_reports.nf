#!/usr/bin/env nextflow
/*
 * Generate IGVReports DEMO for ALE experiment (I1 samples only):
 *   - Cohort-level report with custom Tabulator.js template (sticky pagination,
 *     resizable table/IGV split, CSV export, VCF download, ANN column formatters)
 *   - Per-sample reports with CRAM pileups + GFF3 gene track
 *   - Multi-allelic splitting with bcftools norm -m- (preserves ORIG_ALT)
 *   - Auto-generated index.html with styled navigation
 *
 * Key differences from generate_all_reports.nf:
 *   - igv-reports v1.16.0 (custom template support)
 *   - bcftools norm -m- for multi-allelic splitting
 *   - Custom HTML template with embedded Tabulator column settings
 *   - ORIG_ALT INFO column to track split records
 *   - Styled index.html matching demo/index.html
 *
 * Usage:
 *   bash docs/igvreports/generate_demo_reports.sh
 */

nextflow.enable.dsl = 2

// --- Parameters ---
params.annotated_joint_vcf = null
params.annotation_dir      = null   // dir containing {sample}/{sample}...snpEff.ann.vcf.gz
params.cram_dir            = null   // dir containing {sample}/{sample}.md.cram
params.gff3                = null
params.fasta               = null
params.fai                 = null
params.filter_config       = null   // Tabulator filter config YAML
params.custom_template     = null   // Custom HTML template for cohort report
params.sample_template     = null   // Custom HTML template for per-sample reports (1:1 split)
params.outdir              = 'docs/igvreports/demo'
params.samples             = null   // comma-separated sample IDs
params.multiqc_data_dir    = null   // path to multiqc_data/ directory (for multi-caller index)
params.generate_index_script = null // path to generate_index.py
params.cnv_sv_data_dir     = null   // optional: directory with CN/SV cohort matrix CSVs
params.multiqc_report_path = null   // optional: relative path to multiqc_report.html from outdir
params.python_bin          = 'python' // python binary for GENERATE_INDEX (must have pandas, jinja2)
params.show_sensitive      = false   // show sensitive CN / unfiltered SV tabs (debug mode)

// --- Processes ---

process PREPARE_GFF3 {
    tag 'gene_annotations'
    label 'process_low'

    container 'quay.io/biocontainers/htslib:1.21--h566b1c6_1'

    input:
    path gff3

    output:
    tuple path("genes.sorted.gff3.gz"), path("genes.sorted.gff3.gz.tbi")

    script:
    """
    (grep "^#" ${gff3}; grep -v "^#" ${gff3} | sort -k1,1 -k4,4n) \
        | bgzip > genes.sorted.gff3.gz
    tabix -p gff genes.sorted.gff3.gz
    """
}

process PREPARE_VCF {
    tag "$meta.id"
    label 'process_low'

    container 'quay.io/biocontainers/bcftools:1.20--h8b25389_0'

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta), path("${meta.id}.prepared.vcf.gz"), path("${meta.id}.prepared.vcf.gz.tbi")

    script:
    """
    # Step 1: Split multi-allelic sites into biallelic rows
    # --old-rec-tag ORIG_ALT preserves original record info
    # --force needed for HaplotypeCaller PL tag cardinality issues
    bcftools norm -m- --old-rec-tag ORIG_ALT --force ${vcf} -Oz -o tmp_split.vcf.gz
    tabix -p vcf tmp_split.vcf.gz

    # Step 2: Copy FILTER column into INFO/VCF_FILTER
    # (igvreports only reads INFO dict, not fixed FILTER column)
    # Replace semicolons in FILTER values with commas to avoid INFO delimiter conflicts
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

    # Step 3: Add per-sample VAF (variant allele frequency from AD)
    bcftools +fill-tags tmp_with_filter.vcf.gz -Oz -o ${meta.id}.prepared.vcf.gz -- -t FORMAT/VAF
    tabix -p vcf ${meta.id}.prepared.vcf.gz

    rm -f tmp_split.vcf.gz tmp_split.vcf.gz.tbi tmp_with_filter.vcf.gz tmp_with_filter.vcf.gz.tbi
    """
}

process IGVREPORTS_COHORT {
    tag 'cohort'
    label 'process_low'

    container 'quay.io/biocontainers/igv-reports:1.16.0--pyh7e72e81_0'

    publishDir "${params.outdir}", mode: 'copy'

    input:
    tuple val(meta), path(vcf), path(tbi)
    tuple path(gff3_gz), path(gff3_tbi)
    tuple path(fasta), path(fai)
    path filter_config
    path template

    output:
    path "cohort_report.html"

    script:
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tracks ${gff3_gz} \\
        --template ${template} \\
        --filter-config ${filter_config} \\
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \\
        --sample-columns GT VAF \\
        --flanking 500 \\
        --title "Cohort - Joint HaplotypeCaller (Yeast ALE)" \\
        --output cohort_report.html

    # Embed base64-encoded VCF for download button
    python3 -c "
import base64, sys
vcf_path, html_path, vcf_name = sys.argv[1], sys.argv[2], sys.argv[3]
with open(vcf_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
with open(html_path, 'r') as f:
    html = f.read()
html = html.replace('@VCF_BASE64@', b64)
html = html.replace('@VCF_FILENAME@', vcf_name)
with open(html_path, 'w') as f:
    f.write(html)
print(f'Embedded {len(b64)//1024} KB base64 as {vcf_name}')
" ${vcf} cohort_report.html ${vcf.name}
    """
}

process IGVREPORTS_SAMPLE {
    tag "$meta.id"
    label 'process_low'

    container 'quay.io/biocontainers/igv-reports:1.16.0--pyh7e72e81_0'

    publishDir "${params.outdir}/samples", mode: 'copy'

    input:
    tuple val(meta), path(vcf), path(tbi), path(cram), path(crai)
    tuple path(gff3_gz), path(gff3_tbi)
    tuple path(fasta), path(fai)
    path filter_config
    path template

    output:
    path "${meta.id}_report.html"

    script:
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tracks ${gff3_gz} ${cram} \\
        --template ${template} \\
        --filter-config ${filter_config} \\
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \\
        --sample-columns GT AD DP GQ VAF \\
        --flanking 500 \\
        --title "${meta.id} - HaplotypeCaller (Yeast ALE)" \\
        --output ${meta.id}_report.html

    # Embed base64-encoded VCF for download button
    python3 -c "
import base64, sys
vcf_path, html_path, vcf_name = sys.argv[1], sys.argv[2], sys.argv[3]
with open(vcf_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
with open(html_path, 'r') as f:
    html = f.read()
html = html.replace('@VCF_BASE64@', b64)
html = html.replace('@VCF_FILENAME@', vcf_name)
with open(html_path, 'w') as f:
    f.write(html)
print(f'Embedded {len(b64)//1024} KB base64 as {vcf_name}')
" ${vcf} ${meta.id}_report.html ${vcf.name}
    """
}

process IGVREPORTS_SV_CNV {
    tag "$meta.id"
    label 'process_low'

    container 'quay.io/biocontainers/igv-reports:1.16.0--pyh7e72e81_0'

    publishDir "${params.outdir}/samples", mode: 'copy'

    input:
    tuple val(meta), path(vcf), path(tbi), path(cram), path(crai)
    tuple path(gff3_gz), path(gff3_tbi)
    tuple path(fasta), path(fai)
    path template

    output:
    path "${meta.id}_${meta.caller}_report.html"

    script:
    def info_cols = meta.caller == 'cnvkit'
        ? "ANN VCF_FILTER SVTYPE SVLEN FOLD_CHANGE FOLD_CHANGE_LOG PROBES"
        : "ANN VCF_FILTER SVTYPE SVLEN EVENT"
    def sample_cols = meta.caller == 'cnvkit'
        ? "GT"
        : "GT GQ PR SR"
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tracks ${gff3_gz} ${cram} \\
        --template ${template} \\
        --info-columns ${info_cols} \\
        --sample-columns ${sample_cols} \\
        --flanking 500 \\
        --title "${meta.id} - ${meta.caller_label} (Yeast ALE)" \\
        --output ${meta.id}_${meta.caller}_report.html

    # Embed base64-encoded VCF for download button
    python3 -c "
import base64, sys
vcf_path, html_path, vcf_name = sys.argv[1], sys.argv[2], sys.argv[3]
with open(vcf_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
with open(html_path, 'r') as f:
    html = f.read()
html = html.replace('@VCF_BASE64@', b64)
html = html.replace('@VCF_FILENAME@', vcf_name)
with open(html_path, 'w') as f:
    f.write(html)
print(f'Embedded {len(b64)//1024} KB base64 as {vcf_name}')
" ${vcf} ${meta.id}_${meta.caller}_report.html ${vcf.name}
    """
}

process GENERATE_INDEX {
    tag 'index'
    label 'process_low'

    // No container — runs on host Python (nf-env has jinja2 + pandas)

    publishDir "${params.outdir}", mode: 'copy'

    input:
    path cohort_report
    path sample_reports
    path multiqc_data_dir
    path generate_index_script
    path templates_dir
    path cnv_sv_data_dir  // optional: CN/SV cohort matrix CSVs (use [] for none)
    val multiqc_report_path  // optional: relative path to multiqc_report.html

    output:
    path "index.html"

    script:
    def cnv_sv_arg = cnv_sv_data_dir.name != 'NO_FILE' ? "--cnv-sv-data-dir ${cnv_sv_data_dir}" : ""
    def mqc_path_arg = multiqc_report_path ? "--multiqc-report-path '${multiqc_report_path}'" : ""
    def sensitive_arg = params.show_sensitive ? "--show-sensitive" : ""

    """
    # Run the Jinja2-based index generator
    ${params.python_bin ?: 'python'} ${generate_index_script} \\
        --multiqc-dir ${multiqc_data_dir} \\
        --output index.html \\
        --cohort-report ${cohort_report} \\
        --sample-reports-dir samples \\
        --templates-dir ${templates_dir} \\
        ${cnv_sv_arg} ${mqc_path_arg} ${sensitive_arg}

    # Create samples/ symlink so relative links in index.html work at publish time
    # (sample reports are staged flat by Nextflow, but published into samples/)
    mkdir -p samples
    for f in *_report.html; do
        [ -f "\$f" ] && [ "\$f" != "cohort_report.html" ] && ln -sf "../\$f" "samples/\$f" || true
    done
    """
}

// --- Workflow ---

workflow {

    // Reference genome
    ch_fasta = Channel.value([ file(params.fasta), file(params.fai) ])

    // Filter config for Tabulator
    ch_filter_config = Channel.value(file(params.filter_config))

    // Custom HTML templates
    ch_template = Channel.value(file(params.custom_template))
    ch_sample_template = Channel.value(file(params.sample_template))

    // --- GFF3 gene annotation track ---
    ch_gff3_indexed = PREPARE_GFF3(file(params.gff3))

    // --- Build all VCFs channel (cohort + samples) ---
    def sample_list = params.samples.tokenize(',')

    ch_joint_vcf = Channel.of([
        [id: 'cohort'],
        file(params.annotated_joint_vcf),
        file("${params.annotated_joint_vcf}.tbi")
    ])

    ch_sample_vcfs = Channel.fromList(sample_list)
        .map { sample ->
            def vcf = file("${params.annotation_dir}/${sample}.haplotypecaller.from_joint_calling/${sample}.haplotypecaller.from_joint_calling.hard_filtered_snpEff.ann.vcf.gz")
            def tbi = file("${params.annotation_dir}/${sample}.haplotypecaller.from_joint_calling/${sample}.haplotypecaller.from_joint_calling.hard_filtered_snpEff.ann.vcf.gz.tbi")
            [ [id: sample, caller: 'haplotypecaller', caller_label: 'HaplotypeCaller'], vcf, tbi ]
        }

    // annotation_dir points to .../annotation/haplotypecaller; parent is .../annotation/
    def annotation_root = file(params.annotation_dir).parent

    ch_cnvkit_vcfs = Channel.fromList(sample_list)
        .map { sample ->
            def vcf = file("${annotation_root}/cnvkit/${sample}/${sample}.cnvcall_snpEff.ann.vcf.gz")
            def tbi = file("${annotation_root}/cnvkit/${sample}/${sample}.cnvcall_snpEff.ann.vcf.gz.tbi")
            [ [id: sample, caller: 'cnvkit', caller_label: 'CNVKit'], vcf, tbi ]
        }

    ch_manta_vcfs = Channel.fromList(sample_list)
        .map { sample ->
            def vcf = file("${annotation_root}/manta/${sample}/${sample}.manta.diploid_sv_snpEff.ann.vcf.gz")
            def tbi = file("${annotation_root}/manta/${sample}/${sample}.manta.diploid_sv_snpEff.ann.vcf.gz.tbi")
            [ [id: sample, caller: 'manta', caller_label: 'Manta'], vcf, tbi ]
        }

    // Single PREPARE_VCF call with all VCFs mixed
    ch_all_prepared = PREPARE_VCF(
        ch_joint_vcf.mix(ch_sample_vcfs, ch_cnvkit_vcfs, ch_manta_vcfs)
    )

    // Branch into cohort, HC sample, and SV/CNV channels
    ch_all_prepared.branch {
        cohort: it[0].id == 'cohort'
        sv_cnv: it[0].caller in ['cnvkit', 'manta']
        sample: true
    }.set { ch_branched }

    // --- Cohort report (custom template) ---
    IGVREPORTS_COHORT(ch_branched.cohort, ch_gff3_indexed, ch_fasta, ch_filter_config, ch_template)

    // --- Per-sample reports ---
    ch_samples_prepared = ch_branched.sample

    // Join with CRAMs
    ch_samples_with_cram = ch_samples_prepared
        .map { meta, vcf, tbi ->
            def cram = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram")
            def crai = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram.crai")
            [ meta, vcf, tbi, cram, crai ]
        }

    IGVREPORTS_SAMPLE(ch_samples_with_cram, ch_gff3_indexed, ch_fasta, ch_filter_config, ch_sample_template)

    // --- CNVKit and Manta per-sample reports ---
    ch_sv_cnv_with_cram = ch_branched.sv_cnv
        .map { meta, vcf, tbi ->
            def cram = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram")
            def crai = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram.crai")
            [ meta, vcf, tbi, cram, crai ]
        }

    IGVREPORTS_SV_CNV(ch_sv_cnv_with_cram, ch_gff3_indexed, ch_fasta, ch_sample_template)

    // --- Generate index.html (Jinja2-based multi-caller dashboard) ---
    ch_multiqc_data = Channel.value(file(params.multiqc_data_dir))
    ch_generate_script = Channel.value(file(params.generate_index_script))
    ch_templates = Channel.value(file("${projectDir}/templates"))

    // Optional CN/SV data directory
    ch_cnv_sv_data = params.cnv_sv_data_dir
        ? Channel.value(file(params.cnv_sv_data_dir))
        : Channel.value(file("NO_FILE"))

    // Optional MultiQC report relative path
    ch_mqc_report_path = Channel.value(params.multiqc_report_path ?: "")

    ch_all_sample_reports = IGVREPORTS_SAMPLE.out
        .mix(IGVREPORTS_SV_CNV.out)
        .collect()

    GENERATE_INDEX(
        IGVREPORTS_COHORT.out.collect(),
        ch_all_sample_reports,
        ch_multiqc_data,
        ch_generate_script,
        ch_templates,
        ch_cnv_sv_data,
        ch_mqc_report_path
    )
}
