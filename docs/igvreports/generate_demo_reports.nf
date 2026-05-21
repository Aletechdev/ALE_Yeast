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
    tuple path(fasta), path(fai)
    path filter_config
    path template

    output:
    path "cohort_report.html"

    script:
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --template ${template} \\
        --filter-config ${filter_config} \\
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \\
        --sample-columns GT AD DP GQ VAF \\
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

process COUNT_VARIANTS {
    tag "$meta.id"
    label 'process_low'

    container 'quay.io/biocontainers/bcftools:1.20--h8b25389_0'

    input:
    tuple val(meta), path(vcf), path(tbi)

    output:
    tuple val(meta.id), env(VARIANT_COUNT)

    script:
    """
    VARIANT_COUNT=\$(bcftools view -H ${vcf} | wc -l | tr -d '[:space:]')
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
    val variant_counts  // map of sample_id -> count
    path multiqc_data_dir
    path generate_index_script
    path templates_dir

    output:
    path "index.html"

    script:
    // Write variant counts to JSON for the Python script
    def counts_json = new groovy.json.JsonBuilder(variant_counts).toString()

    """
    # Write variant counts from Nextflow to a temp JSON file
    cat <<'COUNTJSON' > variant_counts.json
${counts_json}
COUNTJSON

    # Run the Jinja2-based index generator
    python3 ${generate_index_script} \\
        --multiqc-dir ${multiqc_data_dir} \\
        --output index.html \\
        --cohort-report ${cohort_report} \\
        --sample-reports-dir samples \\
        --variant-counts-json variant_counts.json \\
        --templates-dir ${templates_dir}

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
            def vcf = file("${params.annotation_dir}/${sample}/${sample}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz")
            def tbi = file("${params.annotation_dir}/${sample}/${sample}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz.tbi")
            [ [id: sample], vcf, tbi ]
        }

    // Single PREPARE_VCF call with all VCFs mixed
    ch_all_prepared = PREPARE_VCF(ch_joint_vcf.mix(ch_sample_vcfs))

    // Branch into cohort and sample channels
    ch_all_prepared.branch {
        cohort: it[0].id == 'cohort'
        sample: true
    }.set { ch_branched }

    // --- Cohort report (custom template) ---
    IGVREPORTS_COHORT(ch_branched.cohort, ch_fasta, ch_filter_config, ch_template)

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

    // --- Count variants per sample for index ---
    COUNT_VARIANTS(ch_samples_prepared)

    // Collect counts into a map: {sample_id: count}
    ch_count_map = COUNT_VARIANTS.out
        .collect()
        .map { list ->
            def m = [:]
            // list is flattened: [id1, count1, id2, count2, ...]
            for (int i = 0; i < list.size(); i += 2) {
                m[list[i]] = list[i+1].trim()
            }
            m
        }

    // --- Generate index.html (Jinja2-based multi-caller dashboard) ---
    ch_multiqc_data = Channel.value(file(params.multiqc_data_dir))
    ch_generate_script = Channel.value(file(params.generate_index_script))
    ch_templates = Channel.value(file("${projectDir}/docs/igvreports/templates"))

    GENERATE_INDEX(
        IGVREPORTS_COHORT.out.collect(),
        IGVREPORTS_SAMPLE.out.collect(),
        ch_count_map,
        ch_multiqc_data,
        ch_generate_script,
        ch_templates
    )
}
