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

# Extract AF data from the Mutect2 VCF
vcf_file = '/home/azureuser/Docs/ALE_nextflow/output_all/variant_calling/mutect2/A1-F6-I1-R1_vs_A0-F0-I1-R1/A1-F6-I1-R1_vs_A0-F0-I1-R1.mutect2.vcf.gz'
output_file = '/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/paper_a/mutect_2/variant_af_mutect2.tsv'

# First split multi-allelic variants, then extract AF data
split_vcf = '/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/paper_a/mutect_2/A1-F6-I1-R1_vs_A0-F0-I1-R1.mutect2.split.vcf.gz'
cmd1 = f"source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env && bcftools norm -m- -O z {vcf_file} > {split_vcf}"
subprocess.run(cmd1, shell=True, executable='/bin/bash')

# Extract AF and TLOD data using bcftools (Mutect2 has FORMAT/AF and INFO/TLOD fields)
cmd2 = f"source ~/miniforge3/etc/profile.d/conda.sh && conda activate nf-env && bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL\\t%TLOD[\\t%AF]\\n' {split_vcf} > {output_file}"
subprocess.run(cmd2, shell=True, executable='/bin/bash')

# Read the AF data
data = pd.read_csv(output_file, 
                   sep='\t', header=None,
                   names=['CHROM', 'POS', 'REF', 'ALT', 'QUAL', 'TLOD', 'normal_AF', 'tumor_AF'])

print(f"Total variants: {len(data)}")
print("First few rows:")
print(data.head())
print("\nData types:")
print(data.dtypes)

# Convert columns to numeric, handle QUAL separately (many are ".")
data['normal_AF'] = pd.to_numeric(data['normal_AF'], errors='coerce')
data['tumor_AF'] = pd.to_numeric(data['tumor_AF'], errors='coerce')
data['TLOD'] = pd.to_numeric(data['TLOD'], errors='coerce')
data['QUAL'] = pd.to_numeric(data['QUAL'], errors='coerce')  # This will make "." into NaN

# Remove rows where AF or TLOD values are NaN
data = data.dropna(subset=['normal_AF', 'tumor_AF', 'TLOD'])
print(f"After numeric conversion and NaN removal: {len(data)}")

# Apply filters: AF difference > 0.05 and TLOD >= 6.3
data_filtered = data[(data['tumor_AF'] - data['normal_AF'] > 0.05) & (data['TLOD'] >= 6.3)]
print(f"After AF difference > 0.05 and TLOD >= 6.3 filters: {len(data_filtered)}")

# Keep both filtered and unfiltered data for comparison
data_all = data.copy()  # Keep all data for scatter plot
data = data_filtered    # Use filtered data for statistics

print(f"Final variant count: {len(data)}")
print(f"Starting strain AF range: {data['normal_AF'].min():.4f} - {data['normal_AF'].max():.4f}")
print(f"Mutated strain AF range: {data['tumor_AF'].min():.4f} - {data['tumor_AF'].max():.4f}")

# Define benchmark mutations
# Note: chr13:107031 has different representations in FreeBayes vs Mutect2
benchmark_positions = [
    ('chr12', 171072, 'C', 'T'),
    ('chr13', 2746, 'A', 'C'),
    ('chr13', 107031, 'TCG', 'ACG'),    # FreeBayes representation
    ('chr13', 107031, 'T', 'A'),        # Mutect2 representation (same mutation)
    ('chr15', 783260, 'G', 'A')
]

# Create a column to identify benchmark mutations in both datasets
data_all['is_benchmark'] = False
data['is_benchmark'] = False

for chrom, pos, ref, alt in benchmark_positions:
    mask_all = (data_all['CHROM'] == chrom) & (data_all['POS'] == pos) & (data_all['REF'] == ref) & (data_all['ALT'] == alt)
    mask_filtered = (data['CHROM'] == chrom) & (data['POS'] == pos) & (data['REF'] == ref) & (data['ALT'] == alt)
    data_all.loc[mask_all, 'is_benchmark'] = True
    data.loc[mask_filtered, 'is_benchmark'] = True

benchmark_all = data_all[data_all['is_benchmark']]
benchmark_filtered = data[data['is_benchmark']]

print(f"Found {data_all['is_benchmark'].sum()} benchmark mutations in all variants")
print(f"Found {data['is_benchmark'].sum()} benchmark mutations in filtered variants")

# Create scatter plot with wider figure to accommodate legend and stats
fig, ax = plt.subplots(figsize=(14, 8))

# Plot all variants using colorblind-safe colors
regular_all = data_all[~data_all['is_benchmark']]
scatter_all = ax.scatter(regular_all['normal_AF'], regular_all['tumor_AF'], 
                        alpha=0.3, s=8, c='#1f77b4', edgecolors='none',  # Blue (colorblind-safe)
                        label=f'All variants (n={len(regular_all):,})')

# Highlight filtered variants with colorblind-safe orange
regular_filtered = data[~data['is_benchmark']]
if len(regular_filtered) > 0:
    scatter_filtered = ax.scatter(regular_filtered['normal_AF'], regular_filtered['tumor_AF'], 
                                alpha=0.7, s=15, c='#ff7f0e', edgecolors='none',  # Orange (colorblind-safe)
                                label=f'AF diff > 0.05 & TLOD ≥ 6.3 (n={len(regular_filtered)})')

# Plot benchmark mutations with distinct colors and larger size
if len(benchmark_all) > 0:
    scatter_benchmark = ax.scatter(benchmark_all['normal_AF'], benchmark_all['tumor_AF'], 
                                 alpha=0.9, s=100, c='red', edgecolors='black', linewidth=2,
                                 marker='*', label=f'Benchmark mutations (n={len(benchmark_all)})')
    
    # Add text labels for benchmark mutations
    for idx, row in benchmark_all.iterrows():
        # Check if this benchmark passed the filter
        passed_filter = row['CHROM'] in data['CHROM'].values and \
                       any((data['CHROM'] == row['CHROM']) & 
                           (data['POS'] == row['POS']) & 
                           (data['REF'] == row['REF']) & 
                           (data['ALT'] == row['ALT']))
        
        filter_status = "✓" if passed_filter else "✗"
        ax.annotate(f"{row['CHROM']}:{row['POS']}\n{row['REF']}→{row['ALT']} {filter_status}", 
                   (row['normal_AF'], row['tumor_AF']),
                   xytext=(5, 5), textcoords='offset points',
                   fontsize=8, fontweight='bold', color='darkred',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor='yellow', alpha=0.7))

# Add reference line
ax.plot([0, 0.95], [0.05, 1], 'g--', linewidth=1, alpha=0.7, label='y = x + 0.05')

# Set labels and title
ax.set_xlabel('Starting strain Allele Frequency (AF)', fontsize=12)
ax.set_ylabel('Mutated Strain Allele Frequency (AF)', fontsize=12)
ax.set_title(f'Mutect2 Allele Frequency Distribution\n(n={len(data_all):,} total variants, {len(data):,} filtered)', 
             fontsize=14, pad=20)

# Set axis limits
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

# Add grid
ax.grid(True, alpha=0.3)

# Add legend outside the plot area
ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')

# Calculate and display statistics for filtered data
if len(data) > 0:
    somatic_variants = (data['normal_AF'] == 0).sum()
    shared_variants = (data['normal_AF'] > 0).sum()
    correlation = data['normal_AF'].corr(data['tumor_AF'])
    
    # Calculate variants passing each filter separately
    af_diff_only = ((data_all['tumor_AF'] - data_all['normal_AF']) > 0.05).sum()
    both_filters = len(data)  # This is already the count passing both filters
    
    stats_text = f"""Filtering Statistics:
Total variants: {len(data_all):,}
AF diff > 0.05: {af_diff_only:,} variants ({af_diff_only/len(data_all)*100:.1f}%)
AF diff > 0.05 & TLOD ≥ 6.3: {both_filters:,} variants ({both_filters/len(data_all)*100:.1f}%)

Shared (Starting strain AF > 0): {shared_variants:,} ({shared_variants/len(data)*100:.1f}%)
Correlation coefficient: {correlation:.3f}
TLOD range: {data['TLOD'].min():.1f} - {data['TLOD'].max():.1f}

Starting strain AF - Mean: {data['normal_AF'].mean():.3f}, Median: {data['normal_AF'].median():.3f}
Mutated strain AF - Mean: {data['tumor_AF'].mean():.3f}, Median: {data['tumor_AF'].median():.3f}"""
else:
    af_diff_only = ((data_all['tumor_AF'] - data_all['normal_AF']) > 0.05).sum()
    stats_text = f"""Filtering Statistics:
Total variants: {len(data_all):,}
AF diff > 0.05: {af_diff_only:,} variants ({af_diff_only/len(data_all)*100:.1f}%)
AF diff > 0.05 & TLOD ≥ 6.3: 0 variants (0.0%)

No variants pass both filtering criteria."""

ax.text(1.02, 0.5, stats_text, transform=ax.transAxes, fontsize=10,
        verticalalignment='center', bbox=dict(boxstyle="round", facecolor='lightblue', alpha=0.8))

# Make plot square
ax.set_aspect('equal')

plt.tight_layout()
plt.subplots_adjust(right=0.65)  # Make room for legend and stats on the right
plt.savefig('/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/paper_a/mutect_2/scatter_AF_comparison_mutect2.png', 
            dpi=600, bbox_inches='tight', facecolor='white')
plt.savefig('/home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/paper_a/mutect_2/scatter_AF_comparison_mutect2.pdf', 
            dpi=600, bbox_inches='tight', facecolor='white')

print(f"\nMutect2 scatter plot saved to: /home/azureuser/Docs/ALE_nextflow/bin/investigate_filter/paper_a/mutect_2/scatter_AF_comparison_mutect2.png")

# Additional analysis
print(f"\n=== MUTECT2 SCATTER PLOT ANALYSIS ===")
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