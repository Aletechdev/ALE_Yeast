#!/bin/bash

# Filter FreeBayes results script
# This script demonstrates different filtering approaches for FreeBayes VCF files

# Set paths
INPUT_DIR="/home/azureuser/Docs/NF_ALE/output/annotation/freebayes"
OUTPUT_DIR="/home/azureuser/Docs/NF_ALE/output/variant_calling_filtered/freebayes"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "Starting FreeBayes VCF filtering..."

# Function to filter a single VCF file
filter_vcf() {
    local input_file="$1"
    local output_prefix="$2"
    local sample_name="$3"
    
    echo "Processing: $sample_name"
    
    # 1. Basic quality filters
    bcftools filter \
        -i 'QUAL>=20 && INFO/DP>=10 && INFO/AF>=0.05' \
        -o "${output_prefix}.quality_filtered.vcf.gz" \
        -O z \
        "$input_file"
    
    # Index the filtered VCF
    tabix -p vcf "${output_prefix}.quality_filtered.vcf.gz"
    
    # 2. Filter for high-impact variants (missense, nonsense, frameshift, etc.)
    bcftools filter \
        -i 'QUAL>=20 && INFO/DP>=10 && INFO/AF>=0.05' \
        "$input_file" | \
    bcftools +split-vep -f '%CHROM\t%POS\t%ID\t%REF\t%ALT\t%QUAL\t%FILTER\t%INFO\t%FORMAT[\t%SAMPLE=%GT]\t%CSQ\n' -d | \
    awk -F'\t' '$10 ~ /missense_variant|nonsense|stop_gained|stop_lost|frameshift_variant|splice_donor_variant|splice_acceptor_variant/' \
        > "${output_prefix}.high_impact.txt"
    
    # 3. Extract variants with functional consequences
    bcftools +split-vep \
        -f '%CHROM:%POS\t%REF>%ALT\t%Consequence\t%SYMBOL\t%Feature\t%HGVSc\t%HGVSp\t%AF\t%DP\t%QUAL\n' \
        -d \
        "${output_prefix}.quality_filtered.vcf.gz" > "${output_prefix}.functional_summary.txt"
    
    # 4. Count variants by consequence type
    echo "=== Variant Counts for $sample_name ===" > "${output_prefix}.summary.txt"
    echo "Total variants after quality filtering:" >> "${output_prefix}.summary.txt"
    bcftools view -H "${output_prefix}.quality_filtered.vcf.gz" | wc -l >> "${output_prefix}.summary.txt"
    echo "" >> "${output_prefix}.summary.txt"
    
    echo "Variants by consequence type:" >> "${output_prefix}.summary.txt"
    if [ -f "${output_prefix}.functional_summary.txt" ]; then
        cut -f3 "${output_prefix}.functional_summary.txt" | sort | uniq -c | sort -nr >> "${output_prefix}.summary.txt"
    fi
    
    echo "Completed processing: $sample_name"
}

# Process all FreeBayes annotated VCF files
for sample_dir in "$INPUT_DIR"/*/; do
    if [ -d "$sample_dir" ]; then
        sample_name=$(basename "$sample_dir")
        
        # Find the annotated VCF file (preferring the unfiltered one for custom filtering)
        vcf_file="$sample_dir/${sample_name}.freebayes_snpEff.ann.vcf.gz"
        
        if [ -f "$vcf_file" ]; then
            output_prefix="$OUTPUT_DIR/${sample_name}"
            filter_vcf "$vcf_file" "$output_prefix" "$sample_name"
        else
            echo "Warning: VCF file not found for $sample_name"
        fi
    fi
done

# Create a combined summary report
echo "Creating combined summary report..."
echo "=== FreeBayes Filtering Summary Report ===" > "$OUTPUT_DIR/combined_summary.txt"
echo "Generated on: $(date)" >> "$OUTPUT_DIR/combined_summary.txt"
echo "" >> "$OUTPUT_DIR/combined_summary.txt"

for summary_file in "$OUTPUT_DIR"/*.summary.txt; do
    if [ -f "$summary_file" ]; then
        cat "$summary_file" >> "$OUTPUT_DIR/combined_summary.txt"
        echo "" >> "$OUTPUT_DIR/combined_summary.txt"
    fi
done

echo "FreeBayes filtering completed!"
echo "Results saved in: $OUTPUT_DIR"
echo "Check combined_summary.txt for overview of all samples"