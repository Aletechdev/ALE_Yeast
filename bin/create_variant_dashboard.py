#!/usr/bin/env python3
"""
ALE Variant Dashboard Generator
Creates a curated, cleaned dashboard for cross-sample and cross-tool variant comparison
Follows bioinformatics best practices for multi-sample VCF organization
"""

import os
import sys
import pandas as pd
import subprocess
from pathlib import Path
import json
from collections import defaultdict

def parse_vcf_header(vcf_path):
    """Extract key information from VCF header"""
    info = {}
    try:
        cmd = ['bcftools', 'view', '-h', str(vcf_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        for line in result.stdout.split('\n'):
            if line.startswith('##source='):
                info['tool'] = line.split('=', 1)[1]
            elif line.startswith('##reference='):
                info['reference'] = line.split('=', 1)[1]
            elif line.startswith('##fileDate='):
                info['date'] = line.split('=', 1)[1]
                
        return info
    except:
        return {'tool': 'unknown', 'reference': 'unknown', 'date': 'unknown'}

def extract_high_impact_variants(vcf_path, sample_name, tool):
    """Extract high and moderate impact variants from annotated VCF"""
    variants = []
    
    try:
        # Query for variants with impact annotation
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
                # SnpEff format: Allele|Annotation|Impact|Gene_Name|Gene_ID|Feature_Type|Feature_ID|Transcript_BioType|Rank|HGVS.c|HGVS.p|cDNA.pos/cDNA.length|CDS.pos/CDS.length|AA.pos/AA.length|Distance|ERRORS/WARNINGS/INFO
                ann_parts = ann.split('|')
                if len(ann_parts) >= 4:
                    impact = ann_parts[2]
                    gene_name = ann_parts[3]
                    annotation = ann_parts[1]
                    
                    # Only keep HIGH and MODERATE impact variants
                    if impact in ['HIGH', 'MODERATE']:
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
                            'Variant_ID': f"{chrom}:{pos}:{ref}>{alt}"
                        })
    except Exception as e:
        print(f"Warning: Could not process {vcf_path}: {e}")
    
    return variants

def create_tool_comparison_matrix(variants_df):
    """Create tool comparison matrix for each variant"""
    if variants_df.empty:
        return pd.DataFrame()
    
    # Group by sample and variant
    comparison_data = []
    
    for sample in variants_df['Sample'].unique():
        sample_variants = variants_df[variants_df['Sample'] == sample]
        
        # Get unique variants (by position) 
        unique_variants = sample_variants.drop_duplicates(['Variant_ID'])
        
        for _, variant in unique_variants.iterrows():
            variant_id = variant['Variant_ID']
            
            # Check which tools detected this variant
            tools_detected = sample_variants[sample_variants['Variant_ID'] == variant_id]['Tool'].tolist()
            
            comparison_data.append({
                'Sample': sample,
                'Variant_ID': variant_id,
                'Chrom': variant['Chrom'],
                'Pos': variant['Pos'],
                'Gene': variant['Gene'],
                'Impact': variant['Impact'],
                'Annotation': variant['Annotation'],
                'FreeBayes': 'YES' if 'FreeBayes' in tools_detected else 'NO',
                'Mutect2': 'YES' if 'Mutect2' in tools_detected else 'NO',
                'Tool_Count': len(tools_detected),
                'Confidence': 'HIGH' if len(tools_detected) > 1 else 'MEDIUM'
            })
    
    return pd.DataFrame(comparison_data)

def generate_summary_statistics(variants_df, comparison_df):
    """Generate summary statistics for the dashboard"""
    stats = {}
    
    if variants_df.empty:
        return {
            'total_variants': 0,
            'samples_analyzed': 0,
            'tools_used': [],
            'impact_distribution': {},
            'tool_concordance': {},
            'recommendations': ['No variants detected - check filtering stringency']
        }
    
    stats['total_variants'] = len(variants_df)
    stats['samples_analyzed'] = variants_df['Sample'].nunique()
    stats['tools_used'] = variants_df['Tool'].unique().tolist()
    
    # Impact distribution
    impact_counts = variants_df['Impact'].value_counts().to_dict()
    stats['impact_distribution'] = impact_counts
    
    # Tool concordance
    if not comparison_df.empty:
        high_conf = len(comparison_df[comparison_df['Confidence'] == 'HIGH'])
        total = len(comparison_df)
        stats['tool_concordance'] = {
            'high_confidence_variants': high_conf,
            'total_unique_variants': total,
            'concordance_rate': f"{high_conf/total*100:.1f}%" if total > 0 else "0%"
        }
    
    # Generate recommendations
    recommendations = []
    if stats['total_variants'] == 0:
        recommendations.append("No high/moderate impact variants detected")
        recommendations.append("Consider checking raw VCFs or relaxing filters")
    elif stats['total_variants'] < 10:
        recommendations.append("Low variant count - typical for ALE with stringent filtering")
    
    if 'tool_concordance' in stats and stats['tool_concordance']['high_confidence_variants'] > 0:
        recommendations.append(f"Focus on {stats['tool_concordance']['high_confidence_variants']} high-confidence variants")
    
    stats['recommendations'] = recommendations
    
    return stats

def main():
    """Main dashboard generation function"""
    output_dir = Path("/home/azureuser/Docs/ALE_nextflow/output")
    dashboard_dir = output_dir / "variant_dashboard"
    dashboard_dir.mkdir(exist_ok=True)
    
    print("=== Creating ALE Variant Dashboard ===")
    print("Following bioinformatics best practices for multi-sample VCF organization\n")
    
    # Define samples and tools
    samples = ['A1-F6-I1-R1', 'A3-F3-I1-R1', 'A4-F5-I1-R1', 'A5-F4-I1-R1', 'A6-F6-I1-R1', 'A0-F0-I2-R1']
    normal = 'A0-F0-I1-R1'
    tools = ['freebayes', 'mutect2']
    
    all_variants = []
    
    # Extract variants from each tool/sample combination
    for sample in samples:
        sample_vs_normal = f"{sample}_vs_{normal}"
        sample_short = sample.replace('-I1-R1', '').replace('-I2-R1', '')
        
        for tool in tools:
            # Path to filtered, annotated VCF
            vcf_path = output_dir / f"annotation/{tool}/{sample_vs_normal}.{tool}.quality_filtered" / f"{sample_vs_normal}.{tool}.quality_filtered.somatic_snpEff.ann.vcf.gz"
            
            if vcf_path.exists():
                print(f"Processing: {sample_short} - {tool.capitalize()}")
                variants = extract_high_impact_variants(vcf_path, sample_short, tool.capitalize())
                all_variants.extend(variants)
            else:
                print(f"Warning: File not found - {vcf_path}")
    
    # Create DataFrames
    variants_df = pd.DataFrame(all_variants)
    
    # Create tool comparison matrix
    comparison_df = create_tool_comparison_matrix(variants_df)
    
    # Generate summary statistics
    summary_stats = generate_summary_statistics(variants_df, comparison_df)
    
    # Save results
    print(f"\n=== Saving Dashboard Files ===")
    
    # 1. All variants detailed table
    variants_file = dashboard_dir / "all_variants_detailed.csv"
    if not variants_df.empty:
        variants_df.to_csv(variants_file, index=False)
        print(f"✓ Detailed variants: {variants_file}")
    
    # 2. Tool comparison matrix  
    comparison_file = dashboard_dir / "tool_comparison_matrix.csv"
    if not comparison_df.empty:
        comparison_df.to_csv(comparison_file, index=False)
        print(f"✓ Tool comparison: {comparison_file}")
    
    # 3. Summary statistics
    summary_file = dashboard_dir / "summary_statistics.json"
    with open(summary_file, 'w') as f:
        json.dump(summary_stats, f, indent=2)
    print(f"✓ Summary stats: {summary_file}")
    
    # 4. Dashboard README
    readme_file = dashboard_dir / "README.md"
    with open(readme_file, 'w') as f:
        f.write(f"""# ALE Variant Analysis Dashboard

## Overview
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

**Key Statistics:**
- Total high/moderate impact variants: {summary_stats['total_variants']}
- Samples analyzed: {summary_stats['samples_analyzed']}
- Tools used: {', '.join(summary_stats['tools_used'])}

## Files in this Dashboard

### 1. `all_variants_detailed.csv`
- **Purpose**: Complete list of all HIGH and MODERATE impact variants
- **Use**: Detailed variant-by-variant analysis
- **Columns**: Sample, Tool, Position, Gene, Impact, Annotation, Quality scores

### 2. `tool_comparison_matrix.csv` 
- **Purpose**: Cross-tool variant comparison
- **Use**: Identify high-confidence variants (detected by multiple tools)
- **Priority**: Focus on variants with Tool_Count > 1

### 3. `summary_statistics.json`
- **Purpose**: Overview metrics and recommendations
- **Use**: Quick assessment of variant calling results

## Analysis Recommendations

{chr(10).join(['- ' + rec for rec in summary_stats['recommendations']])}

## Best Practices Applied

1. **Tool Concordance**: Variants detected by multiple tools have higher confidence
2. **Impact Prioritization**: Focus on HIGH > MODERATE > LOW impact variants  
3. **Quality Filtering**: Only quality-filtered, annotated variants included
4. **Cross-Sample Comparison**: Easy comparison across evolved strains

## Quick Analysis Commands

```bash
# View high-confidence variants (multiple tools)
grep "HIGH," tool_comparison_matrix.csv

# Count variants per sample
cut -d',' -f1 all_variants_detailed.csv | sort | uniq -c

# Find variants in specific genes
grep "gene_name" all_variants_detailed.csv
```

## Next Steps for Manual Review

1. **Start with high-confidence variants** (Tool_Count > 1)
2. **Prioritize HIGH impact** variants affecting gene function
3. **Cross-reference with ALE phenotypes** and adaptation pathways
4. **Validate interesting variants** with IGV or other tools
""")
    print(f"✓ Dashboard guide: {readme_file}")
    
    # Print summary to console
    print(f"\n=== Dashboard Summary ===")
    print(f"Total variants analyzed: {summary_stats['total_variants']}")
    if summary_stats['total_variants'] > 0:
        print(f"Impact distribution: {summary_stats['impact_distribution']}")
        if 'tool_concordance' in summary_stats:
            print(f"Tool concordance: {summary_stats['tool_concordance']['concordance_rate']}")
    
    print(f"\nDashboard created in: {dashboard_dir}")
    print("Start with: README.md for analysis guidance")

if __name__ == "__main__":
    main()