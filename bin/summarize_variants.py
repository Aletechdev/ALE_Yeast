#!/usr/bin/env python3
"""
Variant Summary Generator for ALE Project
Creates organized summary tables from Sarek variant calling results
"""

import os
import sys
import pandas as pd
import subprocess
from pathlib import Path

def count_variants_in_vcf(vcf_path):
    """Count variants in a VCF file"""
    try:
        if not os.path.exists(vcf_path):
            return 0
        
        # Use bcftools to count variants (excluding headers)
        result = subprocess.run(
            ['bcftools', 'view', '-H', str(vcf_path)], 
            capture_output=True, text=True, check=True
        )
        return len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
    except:
        # Fallback: count non-header lines
        try:
            with open(vcf_path, 'rt') if vcf_path.endswith('.vcf') else \
                 subprocess.Popen(['zcat', vcf_path], stdout=subprocess.PIPE, text=True) as f:
                if vcf_path.endswith('.vcf'):
                    lines = f.readlines()
                else:
                    lines = f.stdout.readlines()
                return sum(1 for line in lines if not line.startswith('#'))
        except:
            return 'Error'

def summarize_variants(output_dir):
    """Generate variant summary tables"""
    output_path = Path(output_dir)
    
    # Define samples (evolved strains)
    samples = ['A1-F6-I1-R1', 'A3-F3-I1-R1', 'A4-F5-I1-R1', 'A5-F4-I1-R1', 'A6-F6-I1-R1', 'A0-F0-I2-R1']
    normal = 'A0-F0-I1-R1'
    
    results = []
    
    for sample in samples:
        sample_vs_normal = f"{sample}_vs_{normal}"
        row = {'Sample': sample.replace('-I1-R1', '').replace('-I2-R1', '')}
        
        # SNV/Indel counts
        # FreeBayes filtered somatic
        freebayes_filtered = output_path / f"annotation/freebayes/{sample_vs_normal}.freebayes.quality_filtered"
        fb_file = freebayes_filtered / f"{sample_vs_normal}.freebayes.quality_filtered.somatic_snpEff.ann.vcf.gz"
        row['FreeBayes_Filtered'] = count_variants_in_vcf(fb_file)
        
        # Mutect2 filtered somatic  
        mutect2_filtered = output_path / f"annotation/mutect2/{sample_vs_normal}.mutect2.quality_filtered"
        m2_file = mutect2_filtered / f"{sample_vs_normal}.mutect2.quality_filtered.somatic_snpEff.ann.vcf.gz"
        row['Mutect2_Filtered'] = count_variants_in_vcf(m2_file)
        
        # Structural variants
        # Manta somatic SVs
        manta_sv = output_path / f"annotation/manta/{sample_vs_normal}"
        manta_file = manta_sv / f"{sample_vs_normal}.manta.somatic_sv_snpEff.ann.vcf.gz"
        row['Manta_SV'] = count_variants_in_vcf(manta_file)
        
        # Copy number events (Control-FREEC)
        controlfreec_dir = output_path / f"variant_calling/controlfreec/{sample_vs_normal}"
        cnv_file = controlfreec_dir / f"{sample_vs_normal}.tumor.mpileup.gz_CNVs"
        try:
            if cnv_file.exists():
                with open(cnv_file, 'r') as f:
                    cnv_count = sum(1 for line in f if not line.startswith('#'))
                row['CNV_Events'] = cnv_count
            else:
                row['CNV_Events'] = 0
        except:
            row['CNV_Events'] = 'Error'
            
        results.append(row)
    
    # Create summary DataFrame
    df = pd.DataFrame(results)
    
    # Add total columns
    numeric_cols = ['FreeBayes_Filtered', 'Mutect2_Filtered', 'Manta_SV', 'CNV_Events']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    df['Total_SNV_Indel'] = df['FreeBayes_Filtered'] + df['Mutect2_Filtered'] 
    df['Total_Variants'] = df['Total_SNV_Indel'] + df['Manta_SV']
    
    return df

def generate_file_index(output_dir):
    """Generate an index of key result files"""
    output_path = Path(output_dir)
    samples = ['A1-F6-I1-R1', 'A3-F3-I1-R1', 'A4-F5-I1-R1', 'A5-F4-I1-R1', 'A6-F6-I1-R1', 'A0-F0-I2-R1']
    normal = 'A0-F0-I1-R1'
    
    file_index = []
    
    for sample in samples:
        sample_vs_normal = f"{sample}_vs_{normal}"
        sample_short = sample.replace('-I1-R1', '').replace('-I2-R1', '')
        
        # High-priority files for manual review
        key_files = [
            # Filtered variants (highest priority)
            f"annotation/freebayes/{sample_vs_normal}.freebayes.quality_filtered/{sample_vs_normal}.freebayes.quality_filtered.somatic_snpEff.ann.vcf.gz",
            f"annotation/mutect2/{sample_vs_normal}.mutect2.quality_filtered/{sample_vs_normal}.mutect2.quality_filtered.somatic_snpEff.ann.vcf.gz",
            
            # Copy number plots (visual inspection)
            f"variant_calling/cnvkit/{sample_vs_normal}/{sample.replace('_vs_' + normal, '')}.md-diagram.pdf",
            f"variant_calling/cnvkit/{sample_vs_normal}/{sample.replace('_vs_' + normal, '')}.md-scatter.png",
            
            # Structural variants
            f"annotation/manta/{sample_vs_normal}/{sample_vs_normal}.manta.somatic_sv_snpEff.ann.vcf.gz",
        ]
        
        for file_path in key_files:
            full_path = output_path / file_path
            file_index.append({
                'Sample': sample_short,
                'File_Type': file_path.split('/')[1] + '_' + Path(file_path).stem.split('.')[-3] if 'annotation' in file_path else file_path.split('/')[1],
                'Priority': 'High' if 'quality_filtered' in file_path else 'Medium',
                'Path': str(full_path),
                'Exists': full_path.exists()
            })
    
    return pd.DataFrame(file_index)

if __name__ == "__main__":
    output_dir = "/home/azureuser/Docs/ALE_nextflow/output"
    
    print("=== ALE Variant Calling Summary ===\n")
    
    # Generate variant count summary
    print("1. Variant Counts by Sample and Tool:")
    summary_df = summarize_variants(output_dir)
    print(summary_df.to_string(index=False))
    print()
    
    # Save summary to CSV
    summary_path = Path(output_dir) / "variant_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"Summary saved to: {summary_path}")
    print()
    
    # Generate file index
    print("2. Key Files for Manual Review:")
    file_index = generate_file_index(output_dir)
    priority_files = file_index[file_index['Priority'] == 'High']
    print(priority_files[['Sample', 'File_Type', 'Exists', 'Path']].to_string(index=False))
    
    # Save file index
    index_path = Path(output_dir) / "file_index.csv" 
    file_index.to_csv(index_path, index=False)
    print(f"\nFull file index saved to: {index_path}")