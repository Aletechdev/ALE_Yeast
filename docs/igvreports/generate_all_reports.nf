#!/usr/bin/env nextflow
/*
 * Generate IGVReports for ALE experiment:
 *   - Cohort-level report (no tracks, all samples in table)
 *   - Per-sample reports (with CRAM pileups + GFF3 gene track)
 *   - Auto-generated index.html
 *
 * Usage:
 *   bash docs/igvreports/generate_all_reports.sh
 */

nextflow.enable.dsl = 2

// --- Parameters ---
params.annotated_joint_vcf = null
params.annotation_dir      = null   // dir containing {sample}/{sample}...snpEff.ann.vcf.gz
params.cram_dir            = null   // dir containing {sample}/{sample}.md.cram
params.gff3                = null
params.fasta               = null
params.fai                 = null
params.outdir              = 'docs/igvreports/output'
params.samples             = null   // comma-separated sample IDs

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
    # Keep header lines, then sort body by chrom and position
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
    # Step 1: Copy FILTER column into INFO/VCF_FILTER (igvreports can't read fixed FILTER column)
    # Replace semicolons in FILTER values with commas to avoid INFO field delimiter conflicts
    bcftools view ${vcf} \\
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

    # Step 2: Add per-sample VAF (variant allele frequency from AD)
    bcftools +fill-tags tmp_with_filter.vcf.gz -Oz -o ${meta.id}.prepared.vcf.gz -- -t FORMAT/VAF
    tabix -p vcf ${meta.id}.prepared.vcf.gz

    rm tmp_with_filter.vcf.gz tmp_with_filter.vcf.gz.tbi
    """
}

process IGVREPORTS_COHORT {
    tag 'cohort'
    label 'process_low'

    container 'quay.io/biocontainers/igv-reports:1.12.0--pyh7cba7a3_0'

    publishDir "${params.outdir}", mode: 'copy'

    input:
    tuple val(meta), path(vcf), path(tbi)
    tuple path(fasta), path(fai)

    output:
    path "cohort_report.html"

    script:
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --info-columns ANN VCF_FILTER AC AF DP QD MQ \\
        --sample-columns GT AD DP GQ VAF \\
        --flanking 500 \\
        --title "Cohort - Joint HaplotypeCaller (Yeast ALE)" \\
        --output cohort_report.html
    """
}

process IGVREPORTS_SAMPLE {
    tag "$meta.id"
    label 'process_low'

    container 'quay.io/biocontainers/igv-reports:1.12.0--pyh7cba7a3_0'

    publishDir "${params.outdir}/samples", mode: 'copy'

    input:
    tuple val(meta), path(vcf), path(tbi), path(cram), path(crai)
    tuple path(gff3_gz), path(gff3_tbi)
    tuple path(fasta), path(fai)

    output:
    path "${meta.id}_report.html"

    script:
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tracks ${gff3_gz} ${cram} \\
        --info-columns ANN VCF_FILTER AC AF DP QD MQ \\
        --sample-columns GT AD DP GQ VAF \\
        --flanking 500 \\
        --title "${meta.id} - HaplotypeCaller (Yeast ALE)" \\
        --output ${meta.id}_report.html
    """
}

process GENERATE_INDEX {
    tag 'index'
    label 'process_low'

    publishDir "${params.outdir}", mode: 'copy'

    input:
    path cohort_report
    path sample_reports

    output:
    path "index.html"

    script:
    // Build sample links from collected report filenames
    def sample_links = sample_reports.collect { f ->
        def name = f.name.replace('_report.html', '')
        def type = name.startsWith('A0-') ? 'Ancestral' : 'Evolved'
        "<tr><td><a href=\"samples/${f.name}\">${name}</a></td><td>${type}</td></tr>"
    }.sort().join('\n                ')

    """
    cat <<'HTMLEOF' > index.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ALE Variant Review - IGVReports</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
        h1 { border-bottom: 2px solid #0366d6; padding-bottom: 8px; }
        h2 { margin-top: 32px; color: #24292e; }
        a { color: #0366d6; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .report-link { display: block; padding: 8px 12px; margin: 4px 0; border-radius: 4px; background: #f6f8fa; }
        .report-link:hover { background: #e1e4e8; }
        .meta { color: #586069; font-size: 0.9em; margin-left: 8px; }
        table { border-collapse: collapse; width: 100%; margin-top: 8px; }
        th, td { text-align: left; padding: 6px 12px; border: 1px solid #e1e4e8; }
        th { background: #f6f8fa; }
    </style>
</head>
<body>
    <h1>ALE Variant Review - IGVReports</h1>
    <p>SnpEff-annotated HaplotypeCaller variants with gene annotations and read pileups.</p>

    <div>
        <h2>Cohort Overview</h2>
        <a class="report-link" href="cohort_report.html">
            Cohort variant table (all variants, all samples)
            <span class="meta">Sortable table with ANN columns (GENE, EFFECTS, IMPACT) + per-sample GT/AD/DP/GQ/VAF</span>
        </a>
    </div>

    <div>
        <h2>Per-Sample Reports (with IGV read pileups + gene track)</h2>
        <table>
            <thead><tr><th>Sample</th><th>Type</th></tr></thead>
            <tbody>
                ${sample_links}
            </tbody>
        </table>
    </div>

    <div style="color: #586069; font-size: 0.85em; margin-top: 40px; border-top: 1px solid #e1e4e8; padding-top: 12px;">
        Generated from SnpEff-annotated HaplotypeCaller joint germline calling.<br>
        Per-sample reports include GFF3 gene track + CRAM read pileups + FORMAT/VAF.<br>
        Reference: draft_ref52.fasta
    </div>
</body>
</html>
HTMLEOF
    """
}

// --- Workflow ---

workflow {

    // Reference genome
    ch_fasta = Channel.value([ file(params.fasta), file(params.fai) ])

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

    // --- Cohort report ---
    IGVREPORTS_COHORT(ch_branched.cohort, ch_fasta)

    // --- Per-sample ---
    ch_samples_prepared = ch_branched.sample

    // Join with CRAMs
    ch_samples_with_cram = ch_samples_prepared
        .map { meta, vcf, tbi ->
            def cram = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram")
            def crai = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram.crai")
            [ meta, vcf, tbi, cram, crai ]
        }

    IGVREPORTS_SAMPLE(ch_samples_with_cram, ch_gff3_indexed, ch_fasta)

    // --- Generate index.html ---
    GENERATE_INDEX(
        IGVREPORTS_COHORT.out.collect(),
        IGVREPORTS_SAMPLE.out.collect()
    )
}
