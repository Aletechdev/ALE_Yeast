#!/bin/bash
set -euo pipefail

# Generate IGVReports for Ottilie xenobiotic ALE pilot (4 samples)
# using the MUTATION_REPORT subworkflow via generate_mutation_report.nf.
#
# This replaces generate_ottilie_reports.sh (which calls generate_demo_reports.nf
# with inline processes).  The subworkflow auto-discovers VCF/CRAM paths from
# the pipeline output directory using --tools and --skip_tools.
#
# Compare output against docs/igvreports/ottilie_4samples/ (old pipeline) to
# validate equivalence before archiving generate_demo_reports.nf.
#
# Requires: conda activate nf-env (nextflow)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

OUTDIR="${REPO_ROOT}/docs/igvreports/ottilie_4samples_v2"

# Copy MultiQC report to output dir (so relative link works)
mkdir -p "${OUTDIR}"
cp "${REPO_ROOT}/output_ottilie/multiqc/multiqc_report.html" "${OUTDIR}/multiqc_report.html"

# --- Run MUTATION_REPORT subworkflow ---
nextflow run "${REPO_ROOT}/generate_mutation_report.nf" \
    -c "${REPO_ROOT}/nextflow.config" \
    --outdir "${REPO_ROOT}/output_ottilie" \
    --input "${REPO_ROOT}/data/ottilie/samplesheet_pilot.csv" \
    --fasta "${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.fa" \
    --fasta_fai "${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.fa.fai" \
    --report_gff3 "${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.gff3" \
    --tools "haplotypecaller,cnvkit,manta,tiddit,snpeff" \
    --skip_tools "baserecalibrator" \
    --report_outdir "${OUTDIR}" \
    --report_filter_config "${REPO_ROOT}/docs/igvreports/filter_config.yaml" \
    --report_cohort_template "${REPO_ROOT}/docs/igvreports/custom_template.html" \
    --report_sample_template "${REPO_ROOT}/docs/igvreports/custom_template_sample.html" \
    --report_index_script "${REPO_ROOT}/docs/igvreports/generate_index.py" \
    --report_templates_dir "${REPO_ROOT}/docs/igvreports/templates" \
    --report_multiqc_path "multiqc_report.html" \
    --split_haplotypecaller_joint_vcf \
    -profile conda \
    -work-dir "${REPO_ROOT}/work_igvreports_v2" \
    -resume

# --- Post-process: inject variant counts ---
echo ""
echo "Injecting variant counts into cohort_report.html..."
JOINT_VCF="${REPO_ROOT}/output_ottilie/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz"
PREPARED_VCF="${OUTDIR}/prepare/cohort.prepared.vcf.gz"

PASS_COUNT=$(bcftools view -f PASS -H "${PREPARED_VCF}" | wc -l)
TOTAL_COUNT=$(bcftools view -H "${PREPARED_VCF}" | wc -l)
PRENORM_COUNT=$(bcftools view -H "${JOINT_VCF}" | wc -l)

sed -i "s|@PASS_COUNT@|${PASS_COUNT}|g" "${OUTDIR}/cohort_report.html"
sed -i "s|@TOTAL_COUNT@|${TOTAL_COUNT}|g" "${OUTDIR}/cohort_report.html"
sed -i "s|@PRENORM_COUNT@|${PRENORM_COUNT}|g" "${OUTDIR}/cohort_report.html"
echo "  Quality-filtered: ${PASS_COUNT}, Total: ${TOTAL_COUNT}, Pre-normalization: ${PRENORM_COUNT}"

# --- Regenerate index.html (standalone, picks up template changes) ---
echo ""
echo "Regenerating index.html (standalone, picks up template changes)..."
PASS_STATS_FILES=(${OUTDIR}/data/*.pass_stats.tsv)
PASS_STATS_ARG=""
if [ -f "${PASS_STATS_FILES[0]}" ]; then
    PASS_STATS_ARG="--pass-stats ${PASS_STATS_FILES[*]}"
fi

python "${REPO_ROOT}/docs/igvreports/generate_index.py" \
    --multiqc-dir "${REPO_ROOT}/output_ottilie/multiqc/multiqc_data" \
    --output "${OUTDIR}/index.html" \
    --cohort-report "${OUTDIR}/cohort_report.html" \
    --sample-reports-dir "${OUTDIR}/samples" \
    --templates-dir "${REPO_ROOT}/docs/igvreports/templates" \
    --cnv-sv-data-dir "${OUTDIR}/data" \
    --multiqc-report-path "multiqc_report.html" \
    --joint-vcf "${JOINT_VCF}" \
    --prepared-vcf "${PREPARED_VCF}" \
    ${PASS_STATS_ARG}

echo ""
echo "Done! Open docs/igvreports/ottilie_4samples_v2/index.html"
echo ""
echo "To compare with old pipeline output:"
echo "  diff -rq ${OUTDIR}/data/ docs/igvreports/ottilie_4samples/data/"
