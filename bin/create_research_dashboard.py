#!/usr/bin/env python3
"""
Option 2: Research-Grade Dashboard for ALE Full Dataset
Creates curated variant comparison tables following bioinformatics best practices
"""

import os
import sys
import pandas as pd
import subprocess
from pathlib import Path
import json
from collections import defaultdict

def extract_research_variants(vcf_path, sample_name, tool):
    """Extract research-grade variants with relaxed filtering"""
    variants = []
    
    try:
        # Query for all variants with annotations (not just HIGH/MODERATE)
        cmd = [
            'bcftools', 'query', 
            '-f', '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\t%INFO/ANN\n',
            str(vcf_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
                
            fields = line.split('\t')
            if len(fields) < 7:
                continue
                
            chrom, pos, ref, alt, qual, filt, ann = fields
            
            # Parse SnpEff annotation
            if ann and ann != '.':
                ann_parts = ann.split('|')
                if len(ann_parts) >= 4:
                    impact = ann_parts[2] if len(ann_parts) > 2 else 'UNKNOWN'
                    gene_name = ann_parts[3] if len(ann_parts) > 3 else 'intergenic'
                    annotation = ann_parts[1] if len(ann_parts) > 1 else 'unknown'
                    
                    # Include all impacts for research (HIGH, MODERATE, LOW, MODIFIER)
                    variants.append({
                        'Sample': sample_name,
                        'Tool': tool,
                        'Chrom': chrom,
                        'Pos': int(pos),
                        'Ref': ref,
                        'Alt': alt,
                        'Quality': float(qual) if qual != '.' else 0,
                        'Filter': filt,
                        'Impact': impact,
                        'Gene': gene_name,
                        'Annotation': annotation,
                        'Variant_ID': f"{chrom}:{pos}:{ref}>{alt}",
                        'Key_Variant': impact in ['HIGH', 'MODERATE']  # Flag important variants
                    })
    except Exception as e:
        print(f"Warning: Could not process {vcf_path}: {e}")
    
    return variants

def create_tool_comparison_matrix(variants_df):
    """Create comprehensive tool comparison matrix"""
    if variants_df.empty:
        return pd.DataFrame()
    
    comparison_data = []
    
    for sample in variants_df['Sample'].unique():
        sample_variants = variants_df[variants_df['Sample'] == sample]
        
        # Get unique variants (by genomic position)
        unique_positions = sample_variants['Variant_ID'].unique()
        
        for variant_id in unique_positions:
            variant_data = sample_variants[sample_variants['Variant_ID'] == variant_id]
            
            # Get representative variant info (first occurrence)
            rep_variant = variant_data.iloc[0]
            
            # Check which tools detected this variant
            tools_detected = variant_data['Tool'].unique().tolist()
            
            # Determine confidence level
            if len(tools_detected) >= 2:
                confidence = 'HIGH'
            elif rep_variant['Impact'] in ['HIGH', 'MODERATE']:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'
            
            comparison_data.append({
                'Sample': sample,
                'Variant_ID': variant_id,
                'Chrom': rep_variant['Chrom'],
                'Pos': rep_variant['Pos'],
                'Ref_Alt': f"{rep_variant['Ref']}>{rep_variant['Alt']}",
                'Gene': rep_variant['Gene'],
                'Impact': rep_variant['Impact'],
                'Annotation': rep_variant['Annotation'],
                'FreeBayes': 'YES' if 'FreeBayes' in tools_detected else 'NO',
                'Mutect2': 'YES' if 'Mutect2' in tools_detected else 'NO',  
                'Tools_Count': len(tools_detected),
                'Confidence': confidence,
                'Priority': 1 if confidence == 'HIGH' else (2 if confidence == 'MEDIUM' else 3)
            })
    
    df = pd.DataFrame(comparison_data)
    return df.sort_values(['Sample', 'Priority', 'Pos'])

def create_gene_summary(variants_df):
    """Create gene-level summary of variants"""
    if variants_df.empty:
        return pd.DataFrame()
    
    gene_summary = []
    
    for sample in variants_df['Sample'].unique():
        sample_variants = variants_df[variants_df['Sample'] == sample]
        
        # Group by gene
        for gene in sample_variants['Gene'].unique():
            if gene == 'intergenic' or gene == '':
                continue
                
            gene_variants = sample_variants[sample_variants['Gene'] == gene]
            
            # Count by impact and tool
            high_impact = len(gene_variants[gene_variants['Impact'] == 'HIGH'])
            moderate_impact = len(gene_variants[gene_variants['Impact'] == 'MODERATE'])
            
            freebayes_count = len(gene_variants[gene_variants['Tool'] == 'FreeBayes'])
            mutect2_count = len(gene_variants[gene_variants['Tool'] == 'Mutect2'])
            
            gene_summary.append({
                'Sample': sample,
                'Gene': gene,
                'Total_Variants': len(gene_variants),
                'High_Impact': high_impact,
                'Moderate_Impact': moderate_impact,
                'FreeBayes_Count': freebayes_count,
                'Mutect2_Count': mutect2_count,
                'Both_Tools': 'YES' if freebayes_count > 0 and mutect2_count > 0 else 'NO'
            })
    
    df = pd.DataFrame(gene_summary)
    return df.sort_values(['Sample', 'Total_Variants'], ascending=[True, False])

def create_sample_summary(variants_df):
    """Create sample-level summary statistics"""
    if variants_df.empty:
        return pd.DataFrame()
    
    summary_data = []
    
    for sample in variants_df['Sample'].unique():
        sample_variants = variants_df[variants_df['Sample'] == sample]
        
        # Overall counts
        total_variants = len(sample_variants)
        unique_positions = sample_variants['Variant_ID'].nunique()
        
        # By impact
        high_impact = len(sample_variants[sample_variants['Impact'] == 'HIGH'])
        moderate_impact = len(sample_variants[sample_variants['Impact'] == 'MODERATE'])
        low_impact = len(sample_variants[sample_variants['Impact'] == 'LOW'])
        
        # By tool
        freebayes_variants = len(sample_variants[sample_variants['Tool'] == 'FreeBayes'])
        mutect2_variants = len(sample_variants[sample_variants['Tool'] == 'Mutect2'])
        
        # Genes affected
        genes_affected = sample_variants[sample_variants['Gene'] != 'intergenic']['Gene'].nunique()
        
        summary_data.append({
            'Sample': sample,
            'Total_Variant_Calls': total_variants,
            'Unique_Positions': unique_positions,
            'High_Impact': high_impact,
            'Moderate_Impact': moderate_impact,
            'Low_Impact': low_impact,
            'FreeBayes_Calls': freebayes_variants,
            'Mutect2_Calls': mutect2_variants,
            'Genes_Affected': genes_affected,
            'FB_M2_Ratio': f"{freebayes_variants}/{mutect2_variants}" if mutect2_variants > 0 else f"{freebayes_variants}/0"
        })
    
    return pd.DataFrame(summary_data)

def main():
    """Main research dashboard generation"""
    output_dir = Path("/home/azureuser/Docs/NF_ALE/output_all")
    dashboard_dir = Path("/home/azureuser/Docs/ALE_nextflow/output") / "research_dashboard"
    dashboard_dir.mkdir(exist_ok=True)
    
    print("=== Creating Research-Grade ALE Dashboard ===")
    print("Option 2: Curated Dashboard with Tool Comparison")
    print("Full dataset analysis with relaxed filtering\n")
    
    # Define samples and tools
    samples = ['A1-F6-I1-R1', 'A3-F3-I1-R1', 'A4-F5-I1-R1', 'A5-F4-I1-R1', 'A6-F6-I1-R1', 'A0-F0-I2-R1']
    normal = 'A0-F0-I1-R1'
    tools = ['freebayes']  # Start with FreeBayes since it has most variants
    
    all_variants = []
    
    # Extract variants from each tool/sample combination  
    for sample in samples:
        sample_vs_normal = f"{sample}_vs_{normal}"
        sample_short = sample.replace('-I1-R1', '').replace('-I2-R1', '')
        
        for tool in tools:
            # Use filtered, annotated VCFs from full dataset
            vcf_path = output_dir / f"annotation/{tool}/{sample_vs_normal}.{tool}.quality_filtered" / f"{sample_vs_normal}.{tool}.quality_filtered.somatic_snpEff.ann.vcf.gz"
            
            if vcf_path.exists():
                print(f"Processing: {sample_short} - {tool.capitalize()}")
                variants = extract_research_variants(vcf_path, sample_short, tool.capitalize())
                all_variants.extend(variants)
                print(f"  Found {len(variants)} variants")
            else:
                print(f"Warning: File not found - {vcf_path}")
    
    # Create analysis DataFrames
    print(f"\n=== Creating Analysis Tables ===")
    variants_df = pd.DataFrame(all_variants)
    
    if not variants_df.empty:
        print(f"Total variants extracted: {len(variants_df)}")
        
        # 1. Sample-level summary
        sample_summary = create_sample_summary(variants_df)
        
        # 2. Tool comparison matrix (top variants)
        comparison_df = create_tool_comparison_matrix(variants_df)
        
        # 3. Gene-level summary
        gene_summary = create_gene_summary(variants_df)
        
        # 4. High-priority variants (for manual review)
        high_priority = variants_df[
            (variants_df['Impact'].isin(['HIGH', 'MODERATE'])) &
            (variants_df['Gene'] != 'intergenic')
        ].copy()
        
        print(f"High priority variants: {len(high_priority)}")
        
        # Save all tables
        print(f"\n=== Saving Research Dashboard ===")
        
        # Sample summary
        sample_file = dashboard_dir / "sample_summary.csv"
        sample_summary.to_csv(sample_file, index=False)
        print(f"✓ Sample summary: {sample_file}")
        
        # Tool comparison
        if not comparison_df.empty:
            comp_file = dashboard_dir / "tool_comparison_detailed.csv"
            comparison_df.to_csv(comp_file, index=False)
            print(f"✓ Tool comparison: {comp_file}")
        
        # Gene summary
        if not gene_summary.empty:
            gene_file = dashboard_dir / "genes_affected.csv"
            gene_summary.to_csv(gene_file, index=False)
            print(f"✓ Gene analysis: {gene_file}")
        
        # High priority variants
        if not high_priority.empty:
            priority_file = dashboard_dir / "high_priority_variants.csv"
            high_priority.to_csv(priority_file, index=False)
            print(f"✓ Priority variants: {priority_file}")
        
        # Complete variant catalog
        all_file = dashboard_dir / "complete_variant_catalog.csv"
        variants_df.to_csv(all_file, index=False)
        print(f"✓ Complete catalog: {all_file}")
        
        # Create research guide
        readme_file = dashboard_dir / "RESEARCH_GUIDE.md"
        with open(readme_file, 'w') as f:
            f.write(f"""# ALE Research Dashboard - Option 2 Implementation

## Overview
This demonstrates **Option 2: Research-Grade Dashboard** approach for multi-sample, multi-tool VCF analysis.

**Dataset**: Full ALE results with {len(variants_df)} total variant calls across {len(sample_summary)} samples

## Files Created

### 1. `sample_summary.csv` - Sample-Level Overview
- Variant counts per sample and tool
- Impact distribution (HIGH/MODERATE/LOW)
- Genes affected per sample
- **Start here** for overall assessment

### 2. `tool_comparison_detailed.csv` - Cross-Tool Analysis  
- Variants detected by FreeBayes (Mutect2 coming)
- Confidence levels based on tool concordance
- Priority ranking for manual review
- **Use this** for method validation

### 3. `genes_affected.csv` - Gene-Level Analysis
- Variants grouped by gene
- Impact summary per gene per sample
- Tool concordance at gene level
- **Focus on** genes with multiple high-impact variants

### 4. `high_priority_variants.csv` - Manual Review Targets
- HIGH and MODERATE impact variants only
- Excluding intergenic variants
- **Priority list** for biological interpretation

### 5. `complete_variant_catalog.csv` - Full Dataset
- All variants with annotations
- Research-grade filtering (inclusive)
- Complete record for downstream analysis

## Key Findings

{sample_summary.to_string(index=False)}

## Research Workflow

### Phase 1: Overview Assessment
1. Review `sample_summary.csv` - Which samples have most variants?
2. Check `genes_affected.csv` - Which genes are repeatedly mutated?
3. Identify samples with unusual patterns

### Phase 2: Biological Interpretation  
1. Focus on `high_priority_variants.csv`
2. Cross-reference with ALE experimental conditions
3. Look for adaptation-relevant genes (metabolism, stress response)
4. Check for known ALE hotspots

### Phase 3: Method Validation
1. Use `tool_comparison_detailed.csv` when available
2. Validate high-impact variants with IGV
3. Consider experimental validation of key variants

## Advantages of This Approach

✅ **Clean, structured data** - Easy analysis in Excel/R/Python
✅ **Biological focus** - Prioritizes functional variants  
✅ **Scalable** - Can add more tools/samples easily
✅ **Reproducible** - Clear methodology and filtering
✅ **Research-friendly** - Balances discovery vs. precision

## Next Steps

1. **Add Mutect2 data** to tool comparison
2. **Integrate CNV results** from Control-FREEC  
3. **Add experimental metadata** (growth conditions, time points)
4. **Create visualization plots** (Manhattan plots, heatmaps)
5. **Export to analysis software** (R/Python for statistics)

This approach follows **community best practices** for research genomics while maintaining the flexibility needed for ALE studies.
""")
        print(f"✓ Research guide: {readme_file}")
        
        # Print summary to console
        print(f"\n=== Research Dashboard Summary ===")
        print("Sample Overview:")
        print(sample_summary.to_string(index=False))
        
        if not high_priority.empty:
            print(f"\nHigh Priority Variants: {len(high_priority)}")
            print("Top genes with HIGH/MODERATE impact variants:")
            top_genes = high_priority.groupby('Gene').size().sort_values(ascending=False).head(10)
            for gene, count in top_genes.items():
                print(f"  {gene}: {count} variants")
    
    else:
        print("No variants found in dataset")
    
    print(f"\nResearch dashboard created in: {dashboard_dir}")
    print("Start with: RESEARCH_GUIDE.md")

if __name__ == "__main__":
    main()