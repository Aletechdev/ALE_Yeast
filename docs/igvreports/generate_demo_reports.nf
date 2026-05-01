#!/usr/bin/env nextflow
/*
 * Generate IGVReports DEMO for ALE experiment (I1 samples only):
 *   - Cohort-level report with Tabulator.js template (virtual scrolling + column filters)
 *   - Per-sample reports with CRAM pileups + GFF3 gene track
 *   - Multi-allelic splitting with bcftools norm -m- (preserves ORIG_ALT)
 *   - Auto-generated index.html with styled navigation
 *
 * Key differences from generate_all_reports.nf:
 *   - igv-reports v1.16.0 (Tabulator template support)
 *   - bcftools norm -m- for multi-allelic splitting
 *   - --tabulator + --filter-config for cohort report
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
params.outdir              = 'docs/igvreports/demo'
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

    output:
    path "cohort_report.html"

    script:
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tabulator \\
        --filter-config ${filter_config} \\
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \\
        --sample-columns GT AD DP GQ VAF \\
        --flanking 500 \\
        --title "Cohort - Joint HaplotypeCaller (Yeast ALE)" \\
        --output cohort_report.html
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

    output:
    path "${meta.id}_report.html"

    script:
    """
    create_report ${vcf} \\
        --fasta ${fasta} \\
        --tracks ${gff3_gz} ${cram} \\
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \\
        --sample-columns GT AD DP GQ VAF \\
        --flanking 500 \\
        --title "${meta.id} - HaplotypeCaller (Yeast ALE)" \\
        --output ${meta.id}_report.html
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

    publishDir "${params.outdir}", mode: 'copy'

    input:
    path cohort_report
    path sample_reports
    val variant_counts  // map of sample_id -> count

    output:
    path "index.html"

    script:
    def count_map = variant_counts

    def sample_rows = sample_reports.collect { f ->
        def name = f.name.replace('_report.html', '')
        def type = name.startsWith('A0-') ? 'Ancestral' : 'Evolved'
        // Extract ALE lineage from sample name: A{n}-F{n} pattern
        def lineage = name.startsWith('A0-') ? 'CEN.PK parent' : name.replaceAll(/^(A\d+)-F(\d+).*/, '$1 (Flask $2)')
        def variants = count_map[name] ?: '?'
        "<tr><td><a href=\"samples/${f.name}\">${name}</a></td><td>${type}</td><td>${lineage}</td><td>${variants}</td></tr>"
    }.sort().join('\n                ')

    """
    cat <<'HTMLEOF' > index.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ALE Variant Review - IGVReports Demo</title>
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
        .note { color: #586069; font-size: 0.9em; margin-top: 4px; }
    </style>
</head>
<body>
    <h1>ALE Variant Review - IGVReports Demo</h1>
    <p>Variants called using <a href="https://gatk.broadinstitute.org/hc/en-us/articles/5358864757787-HaplotypeCaller">GATK HaplotypeCaller</a>
        joint germline calling (GATK best practices), annotated with
        <a href="https://pcingola.github.io/SnpEff/">SnpEff</a>.
        Reports generated with <a href="https://github.com/igvteam/igv-reports">igv-reports</a> v1.16.0.</p>
    <p class="note">New to VCF format? See the <a href="https://gatk.broadinstitute.org/hc/en-us/articles/360035531692-VCF-Variant-Call-Format">GATK VCF introduction</a>.</p>

    <div>
        <h2>Cohort Overview</h2>
        <a class="report-link" href="cohort_report.html">
            Cohort variant table (all variants, all 17 samples)
            <span class="meta">Tabulator.js with column filters + ANN columns (GENE, EFFECTS, IMPACT) + per-sample GT/AD/DP/GQ/VAF</span>
        </a>
        <p class="note">Multi-allelic variants split into biallelic rows (bcftools norm -m-). ORIG_ALT column shows original multi-allelic context for split records.</p>
    </div>

    <div>
        <h2>Per-Sample Reports (with IGV read pileups + gene track)</h2>
        <p class="note">Demo subset: I1 replicates only (one per ALE lineage).
            I2/I3 replicates are excluded from this demo due to large HTML file sizes (135-196 MB per report)
            caused by higher ploidy configuration that reports lower frequency mutations.</p>
        <p class="note">Per-sample VCFs include all variants (soft-filtered, not hard-filtered).
            The VCF_FILTER column shows quality flags (PASS, QD_filter, MQ_filter, etc.) but no variants are removed.</p>
        <table>
            <thead><tr><th>Sample</th><th>Type</th><th>ALE Lineage</th><th>Variants</th></tr></thead>
            <tbody>
                ${sample_rows}
            </tbody>
        </table>
    </div>

    <div style="color: #586069; font-size: 0.85em; margin-top: 40px; border-top: 1px solid #e1e4e8; padding-top: 12px;">
        Generated from SnpEff-annotated HaplotypeCaller joint germline calling.<br>
        Per-sample reports include GFF3 gene track + CRAM read pileups + FORMAT/VAF.<br>
        Multi-allelic variants split with bcftools norm -m- (ORIG_ALT preserves original context).<br>
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

    // Filter config for Tabulator
    ch_filter_config = Channel.value(file(params.filter_config))

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

    // --- Cohort report (Tabulator template) ---
    IGVREPORTS_COHORT(ch_branched.cohort, ch_fasta, ch_filter_config)

    // --- Per-sample reports ---
    ch_samples_prepared = ch_branched.sample

    // Join with CRAMs
    ch_samples_with_cram = ch_samples_prepared
        .map { meta, vcf, tbi ->
            def cram = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram")
            def crai = file("${params.cram_dir}/${meta.id}/${meta.id}.md.cram.crai")
            [ meta, vcf, tbi, cram, crai ]
        }

    IGVREPORTS_SAMPLE(ch_samples_with_cram, ch_gff3_indexed, ch_fasta)

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

    // --- Generate index.html ---
    GENERATE_INDEX(
        IGVREPORTS_COHORT.out.collect(),
        IGVREPORTS_SAMPLE.out.collect(),
        ch_count_map
    )
}
