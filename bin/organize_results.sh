#!/bin/bash
# Organize variant calling results for manual review
# Creates a structured view of key results

OUTPUT_DIR="/home/azureuser/Docs/ALE_nextflow/output"
REVIEW_DIR="$OUTPUT_DIR/manual_review"

echo "=== Organizing ALE Variant Results for Manual Review ==="

# Create review directory structure
mkdir -p "$REVIEW_DIR"/{high_confidence_variants,copy_number_plots,summary_reports}

# Copy high-confidence filtered variants (most important for manual review)
echo "1. Copying high-confidence somatic variants..."
find "$OUTPUT_DIR/annotation" -name "*.quality_filtered.somatic_snpEff.ann.vcf.gz" -exec cp {} "$REVIEW_DIR/high_confidence_variants/" \;
find "$OUTPUT_DIR/annotation" -name "*.quality_filtered.somatic_snpEff.ann.vcf.gz.tbi" -exec cp {} "$REVIEW_DIR/high_confidence_variants/" \;

# Copy CNV plots for visual inspection
echo "2. Copying copy number visualization plots..."
find "$OUTPUT_DIR/variant_calling/cnvkit" -name "*-diagram.pdf" -exec cp {} "$REVIEW_DIR/copy_number_plots/" \;
find "$OUTPUT_DIR/variant_calling/cnvkit" -name "*-scatter.png" -exec cp {} "$REVIEW_DIR/copy_number_plots/" \;

# Copy key summary files
echo "3. Copying summary reports..."
cp "$OUTPUT_DIR/variant_summary.csv" "$REVIEW_DIR/summary_reports/" 2>/dev/null || echo "variant_summary.csv not found"
cp "$OUTPUT_DIR/file_index.csv" "$REVIEW_DIR/summary_reports/" 2>/dev/null || echo "file_index.csv not found"
cp "$OUTPUT_DIR/multiqc/multiqc_report.html" "$REVIEW_DIR/summary_reports/" 2>/dev/null || echo "MultiQC report not found"

# Create README for review directory
cat > "$REVIEW_DIR/README.md" << 'EOF'
# ALE Variant Calling Results - Manual Review Guide

## Directory Structure

### `high_confidence_variants/`
**Priority: HIGH** - Start here for manual review
- Contains quality-filtered, annotated somatic variants
- Files: `*.quality_filtered.somatic_snpEff.ann.vcf.gz`
- Use: `bcftools view` or `zcat` to examine variants
- Focus on: High/Moderate impact variants in genes

### `copy_number_plots/`  
**Priority: MEDIUM** - Visual inspection of CNV patterns
- CNV diagrams: `*-diagram.pdf` (genome-wide CNV profile)
- Scatter plots: `*-scatter.png` (log2 ratio vs position)
- Look for: Large deletions/amplifications, chromosome-level changes

### `summary_reports/`
**Priority: LOW** - Overview and quality metrics
- `variant_summary.csv`: Variant counts by sample/tool
- `file_index.csv`: Complete file listing
- `multiqc_report.html`: Quality control overview

## Quick Start Manual Review

1. **Check variant summary**: Open `summary_reports/variant_summary.csv`
2. **Review high-impact variants**: 
   ```bash
   # Example: View high-impact variants in sample A1-F6
   bcftools view high_confidence_variants/A1-F6-I1-R1_vs_A0-F0-I1-R1.mutect2.quality_filtered.somatic_snpEff.ann.vcf.gz | grep -E "(HIGH|MODERATE)"
   ```
3. **Visual CNV inspection**: Open PDF files in `copy_number_plots/`
4. **Cross-reference**: Compare variants between tools (FreeBayes vs Mutect2)

## Key Findings Summary

Based on initial analysis:
- **SNV/Indel**: 0 high-confidence somatic variants detected (may need filter adjustment)
- **CNV Events**: 1-13 copy number changes per sample (A5-F4 and A0-F0 highest)
- **Recommendation**: Check filter stringency, review raw VCF files

## Tools for Variant Review
```bash
# View variants with impact annotation
bcftools view file.vcf.gz | grep "ANN=" | head -10

# Count variants by impact
bcftools query -f '%INFO/ANN\n' file.vcf.gz | cut -d'|' -f3 | sort | uniq -c

# Extract high-impact variants
bcftools view -i 'INFO/ANN~"HIGH"' file.vcf.gz
```
EOF

# Generate file listing
echo "4. Creating file inventory..."
echo "# Manual Review File Inventory - $(date)" > "$REVIEW_DIR/file_inventory.txt"
echo "" >> "$REVIEW_DIR/file_inventory.txt"
echo "## High Confidence Variants" >> "$REVIEW_DIR/file_inventory.txt"
ls -lh "$REVIEW_DIR/high_confidence_variants/" >> "$REVIEW_DIR/file_inventory.txt"
echo "" >> "$REVIEW_DIR/file_inventory.txt"
echo "## Copy Number Plots" >> "$REVIEW_DIR/file_inventory.txt" 
ls -lh "$REVIEW_DIR/copy_number_plots/" >> "$REVIEW_DIR/file_inventory.txt"

echo ""
echo "=== Organization Complete ==="
echo "Manual review directory created: $REVIEW_DIR"
echo "Key files:"
echo "  - High-confidence variants: $(ls $REVIEW_DIR/high_confidence_variants/*.vcf.gz 2>/dev/null | wc -l) files"
echo "  - CNV plots: $(ls $REVIEW_DIR/copy_number_plots/*.{pdf,png} 2>/dev/null | wc -l) files"
echo "  - Summary reports: $(ls $REVIEW_DIR/summary_reports/* 2>/dev/null | wc -l) files"
echo ""
echo "Start manual review with: $REVIEW_DIR/README.md"