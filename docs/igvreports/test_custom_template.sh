#!/bin/bash
set -euo pipefail

# Pilot test: custom Tabulator template with sticky pagination
# Uses the already-prepared VCF from the demo workflow

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate nf-env

# Use the prepared cohort VCF from the demo run (already split + VAF added)
PREPARED_VCF="${REPO_ROOT}/docs/igvreports/demo/prepare/cohort.prepared.vcf.gz"
FASTA="${REPO_ROOT}/data/BakerYeast_reference/draft_ref52.fasta"
TEMPLATE="${REPO_ROOT}/docs/igvreports/custom_template.html"
FILTER_CONFIG="${REPO_ROOT}/docs/igvreports/filter_config.yaml"
OUTDIR="${REPO_ROOT}/docs/igvreports/tmp"

# Check if prepared VCF exists, otherwise use raw annotated joint VCF
if [ ! -f "$PREPARED_VCF" ]; then
    echo "Prepared VCF not found at: $PREPARED_VCF"
    echo "Listing demo/prepare/:"
    ls -la "${REPO_ROOT}/docs/igvreports/demo/prepare/" 2>/dev/null || echo "  (dir not found)"
    exit 1
fi

echo "=== Pilot: Custom template with sticky pagination ==="
echo "Input: $PREPARED_VCF"
echo "Template: $TEMPLATE"
echo ""

# Generate report with all variants, no alignment tracks
docker run --rm \
    -v "${REPO_ROOT}:${REPO_ROOT}" \
    -w "${REPO_ROOT}" \
    quay.io/biocontainers/igv-reports:1.16.0--pyh7e72e81_0 \
    create_report "$PREPARED_VCF" \
        --fasta "$FASTA" \
        --template "$TEMPLATE" \
        --filter-config "$FILTER_CONFIG" \
        --info-columns ANN VCF_FILTER ORIG_ALT AC AF DP QD MQ \
        --sample-columns GT AD DP GQ VAF \
        --flanking 500 \
        --title "Cohort All Variants (Yeast ALE)" \
        --output "${OUTDIR}/cohort_custom_template.html"

# Fix ownership (docker may create as root)
if [ ! -w "${OUTDIR}/cohort_custom_template.html" ]; then
    sudo chown "$(id -u):$(id -g)" "${OUTDIR}/cohort_custom_template.html"
fi

# Inject base64-encoded VCF into the HTML (replaces @VCF_BASE64@ and @VCF_FILENAME@)
echo "Embedding VCF file ($(du -h "$PREPARED_VCF" | cut -f1) gzipped)..."
python3 -c "
import base64, sys
vcf_path = sys.argv[1]
html_path = sys.argv[2]
vcf_name = sys.argv[3]

with open(vcf_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

with open(html_path, 'r') as f:
    html = f.read()

html = html.replace('@VCF_BASE64@', b64)
html = html.replace('@VCF_FILENAME@', vcf_name)

with open(html_path, 'w') as f:
    f.write(html)

print(f'  Embedded {len(b64)//1024} KB base64 as {vcf_name}')
" "$PREPARED_VCF" "${OUTDIR}/cohort_custom_template.html" "cohort.prepared.vcf.gz"

echo ""
echo "Done! Output: docs/igvreports/tmp/cohort_custom_template.html"
echo "Size: $(du -h "${OUTDIR}/cohort_custom_template.html" | cut -f1)"
