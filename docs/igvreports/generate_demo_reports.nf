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

    publishDir "${params.outdir}/prepare", mode: 'copy'

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

    # Set VCF download link (file-based, replaces base64 embedding)
    sed -i 's|@VCF_HREF@|vcf/haplotypecaller/cohort_haplotypecaller_annotated.vcf.gz|g' cohort_report.html
    sed -i 's|@VCF_FILENAME@|cohort_haplotypecaller_annotated.vcf.gz|g' cohort_report.html
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

    # Set VCF download link and report type
    sed -i 's|@VCF_HREF@|../vcf/haplotypecaller/${meta.id}_haplotypecaller_annotated.vcf.gz|g' ${meta.id}_report.html
    sed -i 's|@VCF_FILENAME@|${meta.id}_haplotypecaller_annotated.vcf.gz|g' ${meta.id}_report.html
    sed -i 's|@REPORT_TYPE@|haplotypecaller|g' ${meta.id}_report.html
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

    # Set VCF download link and report type
    sed -i 's|@VCF_HREF@|../vcf/${meta.caller}/${meta.id}_${meta.caller}.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
    sed -i 's|@VCF_FILENAME@|${meta.id}_${meta.caller}.vcf.gz|g' ${meta.id}_${meta.caller}_report.html
    sed -i 's|@REPORT_TYPE@|sv_cnv|g' ${meta.id}_${meta.caller}_report.html
    """
}

process PUBLISH_VCFS {
    tag 'vcf_files'
    label 'process_low'

    container 'quay.io/biocontainers/bcftools:1.20--h8b25389_0'

    publishDir "${params.outdir}/vcf", mode: 'copy'

    input:
    tuple val(meta_cohort), path(cohort_vcf), path(cohort_tbi)
    path hc_vcfs      // flattened list: [sample1.vcf.gz, sample1.vcf.gz.tbi, sample2.vcf.gz, ...]
    path cnvkit_vcfs   // flattened list
    path manta_vcfs    // flattened list
    path tiddit_vcfs   // flattened list

    output:
    path "haplotypecaller/*",  emit: hc
    path "cnvkit/*",           emit: cnvkit
    path "manta/*",            emit: manta
    path "tiddit/*",           emit: tiddit
    path "README.md",          emit: readme

    script:
    """
    mkdir -p haplotypecaller cnvkit manta tiddit

    # Cohort HaplotypeCaller VCF
    cp ${cohort_vcf} haplotypecaller/cohort_haplotypecaller_annotated.vcf.gz
    cp ${cohort_tbi} haplotypecaller/cohort_haplotypecaller_annotated.vcf.gz.tbi

    # Per-sample HaplotypeCaller VCFs (rename for consistency)
    for f in ${hc_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        # Extract sample name: {sample}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz -> {sample}
        sample=\$(echo "\$base" | sed 's/.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz\$//' | sed 's/.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "haplotypecaller/\${sample}_haplotypecaller_annotated.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "haplotypecaller/\${sample}_haplotypecaller_annotated.vcf.gz"
        fi
    done

    # Per-sample CNVKit VCFs
    for f in ${cnvkit_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.cnvcall_snpEff.ann.vcf.gz\$//' | sed 's/.cnvcall_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "cnvkit/\${sample}_cnvkit.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "cnvkit/\${sample}_cnvkit.vcf.gz"
        fi
    done

    # Per-sample Manta VCFs
    for f in ${manta_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.manta.diploid_sv_snpEff.ann.vcf.gz\$//' | sed 's/.manta.diploid_sv_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "manta/\${sample}_manta.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "manta/\${sample}_manta.vcf.gz"
        fi
    done

    # Per-sample TIDDIT VCFs
    for f in ${tiddit_vcfs}; do
        [ ! -f "\$f" ] && continue
        base=\$(basename "\$f")
        sample=\$(echo "\$base" | sed 's/.tiddit_snpEff.ann.vcf.gz\$//' | sed 's/.tiddit_snpEff.ann.vcf.gz.tbi\$//')
        if echo "\$base" | grep -q '.tbi\$'; then
            cp "\$f" "tiddit/\${sample}_tiddit.vcf.gz.tbi"
        elif echo "\$base" | grep -q '.vcf.gz\$'; then
            cp "\$f" "tiddit/\${sample}_tiddit.vcf.gz"
        fi
    done

    cat > README.md << 'EOF'
# VCF Downloads

Pre-normalization annotated VCF files organized by variant caller.
These are the canonical variant calls suitable for sharing and downstream analysis.

## haplotypecaller/

- **cohort_haplotypecaller_annotated.vcf.gz**: Joint HaplotypeCaller VCF (all samples),
  soft-filtered (GATK VariantFiltration), annotated with SnpEff.
- **{sample}_haplotypecaller_annotated.vcf.gz**: Per-sample VCFs extracted from the joint
  VCF. Non-reference genotypes only (ref-homozygous sites removed). SnpEff annotated.
  No hard filter applied — all variants where the sample has a non-ref genotype are included.

### Processing chain for per-sample VCFs:
1. Joint calling (GATK HaplotypeCaller → GenotypeGVCFs)
2. Soft filtering (GATK VariantFiltration: QD, FS, SOR, MQ filters)
3. Sample extraction (bcftools view -s)
4. Ref-genotype removal (bcftools filter: keep GT != 0/0)
5. Annotation (SnpEff)

## cnvkit/

- **{sample}_cnvkit.vcf.gz**: CNVKit copy number calls, SnpEff annotated.

## manta/

- **{sample}_manta.vcf.gz**: Manta structural variant calls (diploid_sv), SnpEff annotated.

## tiddit/

- **{sample}_tiddit.vcf.gz**: TIDDIT structural variant calls, SnpEff annotated.

## IGV Report Display VCFs

The IGV reports use a _post-processed_ version of these VCFs for the interactive table:
1. `bcftools norm -m-` (multi-allelic splitting — increases row count)
2. FILTER column promoted to INFO/VCF_FILTER
3. `bcftools +fill-tags FORMAT/VAF` added

These display VCFs are internal to the reports and not published here.
To reproduce, see the methodology section in index.html.
EOF
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
    path prepared_cohort_vcf  // post-norm prepared VCF for accurate row counting

    output:
    path "index.html"

    script:
    def cnv_sv_arg = cnv_sv_data_dir.name != 'NO_FILE' ? "--cnv-sv-data-dir ${cnv_sv_data_dir}" : ""
    def mqc_path_arg = multiqc_report_path ? "--multiqc-report-path '${multiqc_report_path}'" : ""
    def sensitive_arg = params.show_sensitive ? "--show-sensitive" : ""
    def prepared_vcf_arg = prepared_cohort_vcf.name != 'NO_FILE' ? "--prepared-vcf ${prepared_cohort_vcf}" : ""

    """
    # Run the Jinja2-based index generator
    ${params.python_bin ?: 'python'} ${generate_index_script} \\
        --multiqc-dir ${multiqc_data_dir} \\
        --output index.html \\
        --cohort-report ${cohort_report} \\
        --sample-reports-dir samples \\
        --templates-dir ${templates_dir} \\
        ${cnv_sv_arg} ${mqc_path_arg} ${sensitive_arg} ${prepared_vcf_arg}

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

    // --- Publish pre-norm annotated VCFs to vcf/ folder ---
    // HC per-sample: non-ref annotated VCFs (no hard filter, for download/sharing)
    ch_hc_annotated = Channel.fromList(sample_list)
        .map { sample ->
            def vcf = file("${params.annotation_dir}/${sample}/${sample}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz")
            def tbi = file("${params.annotation_dir}/${sample}/${sample}.haplotypecaller.from_joint_calling_snpEff.ann.vcf.gz.tbi")
            [ vcf, tbi ]
        }

    // TIDDIT per-sample annotated VCFs
    ch_tiddit_vcfs = Channel.fromList(sample_list)
        .map { sample ->
            def vcf = file("${annotation_root}/tiddit/${sample}/${sample}.tiddit_snpEff.ann.vcf.gz")
            def tbi = file("${annotation_root}/tiddit/${sample}/${sample}.tiddit_snpEff.ann.vcf.gz.tbi")
            [ vcf, tbi ]
        }

    PUBLISH_VCFS(
        ch_joint_vcf,
        ch_hc_annotated.flatMap { vcf, tbi -> [vcf, tbi] }.collect(),
        ch_cnvkit_vcfs.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect(),
        ch_manta_vcfs.flatMap { meta, vcf, tbi -> [vcf, tbi] }.collect(),
        ch_tiddit_vcfs.flatMap { vcf, tbi -> [vcf, tbi] }.collect()
    )

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

    // Prepared cohort VCF for accurate post-norm row counting
    ch_prepared_cohort_vcf = ch_branched.cohort.map { meta, vcf, tbi -> vcf }

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
        ch_mqc_report_path,
        ch_prepared_cohort_vcf.collect()
    )
}
