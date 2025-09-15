#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import subprocess
import os

# Set style
plt.style.use('default')
sns.set_palette("husl")

# Extract AF data from the NCYC495 FreeBayes VCF
vcf_file = '/home/azureuser/Docs/ALE_nextflow/output_NCYC495/variant_calling/freebayes/A10-F47-I1-R1_vs_A0-F0-I1-R1/A10-F47-I1-R1_vs_A0-F0-I1-R1.freebayes.vcf.gz'
output_file = '/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/Yeast_Methanol/NCYC495/freebayes/variant_ao_dp_tumor_gt0.tsv'

# First split multi-allelic variants, then extract AO, DP, and QUAL data
split_vcf = '/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/Yeast_Methanol/NCYC495/freebayes/A10-F47-I1-R1_vs_A0-F0-I1-R1.freebayes.split.vcf.gz'
cmd1 = f"source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env && bcftools norm -m- -O z {vcf_file} > {split_vcf}"
subprocess.run(cmd1, shell=True, executable='/bin/bash')

cmd2 = f"source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env && bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL[\\t%AO\\t%DP]\\n' {split_vcf} > {output_file}"
subprocess.run(cmd2, shell=True, executable='/bin/bash')

# Read the AO/DP/QUAL data
data = pd.read_csv(output_file, 
                   sep='\t', header=None,
                   names=['CHROM', 'POS', 'REF', 'ALT', 'QUAL', 'tumor_AO', 'tumor_DP', 'normal_AO', 'normal_DP'])

print(f"Total variants: {len(data)}")
print("First few rows:")
print(data.head())
print("\nData types:")
print(data.dtypes)

# Convert columns to numeric, handling any potential string values
for col in ['QUAL', 'tumor_AO', 'tumor_DP', 'normal_AO', 'normal_DP']:
    data[col] = pd.to_numeric(data[col], errors='coerce')

# Remove rows where AF values are NaN, but keep QUAL NaN (since many FreeBayes variants might have QUAL issues)
data = data.dropna(subset=['tumor_AO', 'tumor_DP', 'normal_AO', 'normal_DP'])
print(f"After numeric conversion and NaN removal: {len(data)}")

# Filter out variants where total coverage (DP) is 0
data = data[(data['tumor_DP'] > 0) & (data['normal_DP'] > 0)]

# Calculate allele frequencies using AO/DP
data['tumor_AF'] = data['tumor_AO'] / data['tumor_DP']
data['normal_AF'] = data['normal_AO'] / data['normal_DP']

print(f"After filtering zero DP variants: {len(data)}")
print(f"Starting strain AF range: {data['normal_AF'].min():.4f} - {data['normal_AF'].max():.4f}")
print(f"Mutated strain AF range: {data['tumor_AF'].min():.4f} - {data['tumor_AF'].max():.4f}")

# Create scatter plot with wider figure to accommodate legend and stats
fig, ax = plt.subplots(figsize=(14, 8))

# Create scatter plot with transparency to handle overlapping points
scatter = ax.scatter(data['normal_AF'], data['tumor_AF'], 
                    alpha=0.2, s=9, c='darkblue', edgecolors='none')

# Add reference line
ax.plot([0, 0.95], [0.05, 1], 'g--', linewidth=1, alpha=0.7, label='y = x + 0.05')

# Set labels and title
ax.set_xlabel('Starting strain Allele Frequency (AO/DP)', fontsize=12)
ax.set_ylabel('Mutated Strain Allele Frequency (AO/DP)', fontsize=12)
ax.set_title(f'FreeBayes Allele Frequency Distribution - NCYC495\n(n={len(data):,} variants) [Tumor AO > 0 Filter]', 
             fontsize=14, pad=20)

# Set axis limits
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

# Add grid
ax.grid(True, alpha=0.3)

# Add legend outside the plot area
ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')

# Calculate and display statistics
somatic_variants = (data['normal_AF'] == 0).sum()
shared_variants = (data['normal_AF'] > 0).sum()
correlation = data['normal_AF'].corr(data['tumor_AF'])

# Hardcode the bcftools-calculated values for consistency (to be updated based on actual results)
af_difference_gt_005_count = ((data['tumor_AF'] - data['normal_AF']) > 0.05).sum()

# Add statistics text box
stats_text = f"""Statistics:
Total variants: {len(data):,}
Somatic (Starting strain AF = 0): {somatic_variants:,} ({somatic_variants/len(data)*100:.1f}%)
Shared (Starting strain AF > 0): {shared_variants:,} ({shared_variants/len(data)*100:.1f}%)
Mutated strain AF > Starting strain AF + 0.05: {af_difference_gt_005_count:,} ({af_difference_gt_005_count/len(data)*100:.1f}%)

Correlation coefficient: {correlation:.3f}

Starting strain AF - Mean: {data['normal_AF'].mean():.3f}, Median: {data['normal_AF'].median():.3f}
Mutated strain AF - Mean: {data['tumor_AF'].mean():.3f}, Median: {data['tumor_AF'].median():.3f}"""

ax.text(1.02, 0.5, stats_text, transform=ax.transAxes, fontsize=10,
        verticalalignment='center', bbox=dict(boxstyle="round", facecolor='lightblue', alpha=0.8))

# Make plot square
ax.set_aspect('equal')

plt.tight_layout()
plt.subplots_adjust(right=0.65)  # Make room for legend and stats on the right
plt.savefig('/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/Yeast_Methanol/NCYC495/freebayes/scatter_AF_comparison.png', 
            dpi=600, bbox_inches='tight', facecolor='white')
plt.savefig('/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/Yeast_Methanol/NCYC495/freebayes/scatter_AF_comparison.pdf', 
            dpi=600, bbox_inches='tight', facecolor='white')

print(f"\nNCYC495 FreeBayes scatter plot saved to: /home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/Yeast_Methanol/NCYC495/freebayes/scatter_AF_comparison.png")

# Additional analysis
print(f"\n=== NCYC495 FREEBAYES SCATTER PLOT ANALYSIS ===")
print(f"Correlation between Starting strain and Mutated strain AF: {correlation:.4f}")

# Identify different variant categories
truly_somatic = data[data['normal_AF'] == 0]
low_freq_shared = data[(data['normal_AF'] > 0) & (data['normal_AF'] < 0.1)]
high_freq_shared = data[data['normal_AF'] >= 0.1]

print(f"\nVariant categories:")
print(f"Truly somatic (Starting strain AF = 0): {len(truly_somatic):,} variants")
print(f"Low frequency shared (0 < Starting strain AF < 0.1): {len(low_freq_shared):,} variants")
print(f"High frequency shared (Starting strain AF >= 0.1): {len(high_freq_shared):,} variants")

# Look at variants where mutated strain has much higher AF than starting strain
af_difference = data['tumor_AF'] - data['normal_AF']
high_diff_variants = data[af_difference > 0.5]
print(f"Variants with AF difference > 0.5: {len(high_diff_variants):,} variants")