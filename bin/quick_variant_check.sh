#!/bin/bash
# Quick variant inspection script for ALE results
# Provides rapid overview of key variants for manual checking

OUTPUT_DIR="/home/azureuser/Docs/ALE_nextflow/output"
REVIEW_DIR="$OUTPUT_DIR/manual_review/high_confidence_variants"

echo "=== Quick Variant Check for ALE Samples ==="
echo "Date: $(date)"
echo ""

# Check if bcftools is available
if ! command -v bcftools &> /dev/null; then
    echo "Warning: bcftools not found. Install for detailed variant analysis."
    echo "Falling back to basic checks..."
    USE_BCFTOOLS=false
else
    USE_BCFTOOLS=true
fi

# Function to check variants in a VCF file
check_variants() {
    local vcf_file="$1" 
    local sample_name="$2"
    local tool="$3"
    
    echo "--- $sample_name ($tool) ---"
    
    if [[ ! -f "$vcf_file" ]]; then
        echo "  File not found: $vcf_file"
        return
    fi
    
    if $USE_BCFTOOLS; then
        # Count total variants
        total_vars=$(bcftools view -H "$vcf_file" 2>/dev/null | wc -l)
        echo "  Total variants: $total_vars"
        
        if [[ $total_vars -gt 0 ]]; then
            # Count by variant type
            snps=$(bcftools view -H -v snps "$vcf_file" 2>/dev/null | wc -l)
            indels=$(bcftools view -H -v indels "$vcf_file" 2>/dev/null | wc -l)
            echo "  SNPs: $snps, Indels: $indels"
            
            # Count by impact (if SnpEff annotated)
            if bcftools view -h "$vcf_file" | grep -q "##INFO=<ID=ANN"; then
                high_impact=$(bcftools view -H "$vcf_file" 2>/dev/null | grep -c "HIGH" || echo "0")
                moderate_impact=$(bcftools view -H "$vcf_file" 2>/dev/null | grep -c "MODERATE" || echo "0")
                echo "  High impact: $high_impact, Moderate impact: $moderate_impact"
                
                # Show first few high-impact variants
                if [[ $high_impact -gt 0 ]]; then
                    echo "  High-impact variants (first 3):"
                    bcftools query -f '%CHROM:%POS %REF>%ALT %INFO/ANN\n' "$vcf_file" 2>/dev/null | \
                        grep "HIGH" | head -3 | \
                        while read line; do echo "    $line"; done
                fi
            fi
        fi
    else
        # Fallback: basic line counting
        if [[ "$vcf_file" == *.gz ]]; then
            total_vars=$(zcat "$vcf_file" | grep -v "^#" | wc -l)
        else
            total_vars=$(grep -v "^#" "$vcf_file" | wc -l)
        fi
        echo "  Total variants: $total_vars"
    fi
    echo ""
}

# Define samples
samples=("A1-F6-I1-R1" "A3-F3-I1-R1" "A4-F5-I1-R1" "A5-F4-I1-R1" "A6-F6-I1-R1" "A0-F0-I2-R1")
normal="A0-F0-I1-R1"

echo "Checking high-confidence somatic variants..."
echo "================================================"

for sample in "${samples[@]}"; do
    sample_vs_normal="${sample}_vs_${normal}"
    sample_short=$(echo $sample | sed 's/-I[12]-R1//')
    
    # Check FreeBayes results
    freebayes_file="$REVIEW_DIR/${sample_vs_normal}.freebayes.quality_filtered.somatic_snpEff.ann.vcf.gz"
    check_variants "$freebayes_file" "$sample_short" "FreeBayes"
    
    # Check Mutect2 results  
    mutect2_file="$REVIEW_DIR/${sample_vs_normal}.mutect2.quality_filtered.somatic_snpEff.ann.vcf.gz"
    check_variants "$mutect2_file" "$sample_short" "Mutect2"
done

echo "=== Summary Recommendations ==="
echo ""
echo "1. **No somatic SNVs/indels detected**: This could indicate:"
echo "   - Very stringent filtering (good for precision)"
echo "   - Possible over-filtering (check raw VCFs)"
echo "   - Low mutation rate in ALE samples"
echo ""
echo "2. **Copy number changes detected**: Focus on CNV plots"
echo "   - Review: $OUTPUT_DIR/manual_review/copy_number_plots/"
echo ""
echo "3. **Next steps for manual review:**
echo "   - Check raw VCFs: $OUTPUT_DIR/variant_calling/*/
echo "   - Adjust filters if needed: $OUTPUT_DIR/variant_calling_filtered/"
echo "   - Review MultiQC report: $OUTPUT_DIR/manual_review/summary_reports/multiqc_report.html"
echo ""
echo "4. **Quick commands for deeper inspection:**
echo "   # View raw variants (before filtering)"
echo "   bcftools view $OUTPUT_DIR/variant_calling/mutect2/A1-F6-I1-R1_vs_A0-F0-I1-R1/A1-F6-I1-R1_vs_A0-F0-I1-R1.mutect2.vcf.gz | head -20"
echo ""
echo "   # Check filter annotations"
echo "   bcftools view -f PASS $OUTPUT_DIR/variant_calling/mutect2/A1-F6-I1-R1_vs_A0-F0-I1-R1/A1-F6-I1-R1_vs_A0-F0-I1-R1.mutect2.vcf.gz"