#!/bin/bash
set -euo pipefail

# Generate IGVReports for Ottilie xenobiotic ALE pilot (4 samples)
# with CN/SV cohort matrices + MultiQC integration
#
# Requires: conda activate nf-env (nextflow + docker)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

SAMPLES="CBR110-15-R3a,Carmaphycin-R9-2,Doxorubicin16-R2b,NODRUG-GM2"
OUTDIR="${REPO_ROOT}/docs/igvreports/ottilie_4samples"

# Copy MultiQC report to output dir (so relative link works)
cp "${REPO_ROOT}/output_ottilie/multiqc/multiqc_report.html" "${OUTDIR}/multiqc_report.html"

nextflow run "${REPO_ROOT}/docs/igvreports/generate_demo_reports.nf" \
    -c "${REPO_ROOT}/docs/igvreports/nextflow.config" \
    --annotated_joint_vcf "${REPO_ROOT}/output_ottilie/annotation/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered_snpEff.ann.vcf.gz" \
    --annotation_dir "${REPO_ROOT}/output_ottilie/annotation/haplotypecaller" \
    --cram_dir "${REPO_ROOT}/output_ottilie/preprocessing/markduplicates" \
    --gff3 "${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.gff3" \
    --fasta "${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.fa" \
    --fai "${REPO_ROOT}/data/ottilie/S288C_reference/S288C_R64.fa.fai" \
    --filter_config "${REPO_ROOT}/docs/igvreports/filter_config.yaml" \
    --custom_template "${REPO_ROOT}/docs/igvreports/custom_template.html" \
    --sample_template "${REPO_ROOT}/docs/igvreports/custom_template_sample.html" \
    --outdir "${OUTDIR}" \
    --samples "${SAMPLES}" \
    --multiqc_data_dir "${REPO_ROOT}/output_ottilie/multiqc/multiqc_data" \
    --generate_index_script "${REPO_ROOT}/docs/igvreports/generate_index.py" \
    --cnv_sv_data_dir "${OUTDIR}/data" \
    --multiqc_report_path "multiqc_report.html" \
    --python_bin "$(which python)" \
    -resume

echo ""
echo "Regenerating index.html (standalone, picks up template changes)..."
python "${REPO_ROOT}/docs/igvreports/generate_index.py" \
    --multiqc-dir "${REPO_ROOT}/output_ottilie/multiqc/multiqc_data" \
    --output "${OUTDIR}/index.html" \
    --cohort-report "${OUTDIR}/cohort_report.html" \
    --sample-reports-dir "${OUTDIR}/samples" \
    --templates-dir "${REPO_ROOT}/docs/igvreports/templates" \
    --cnv-sv-data-dir "${OUTDIR}/data" \
    --multiqc-report-path "multiqc_report.html" \
    --joint-vcf "${REPO_ROOT}/output_ottilie/variant_calling/haplotypecaller/joint_variant_calling/HaplotypeCaller_joint_calling_soft_filtered.vcf.gz"

echo ""
echo "Done! Open docs/igvreports/ottilie_4samples/index.html"