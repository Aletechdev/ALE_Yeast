#!/usr/bin/env python3
"""
Create bar chart comparing total mutation counts:
AMP (Legacy Pipeline) vs Joint-GATK-HC (ANP)
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Verified data from source files:
# AMP CSV: 784 rows (awk) - 1 header = 783 mutations
# Joint VCF: 340 variants (bcftools view -H | wc -l)
amp_total = 783
vcf_total = 340

# Set up presentation style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 14,
    'axes.labelsize': 16,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#333333',
    'axes.linewidth': 1.5,
})

# Create figure
fig, ax = plt.subplots(figsize=(8, 7))
fig.patch.set_facecolor('white')

# Bar positions
bar_width = 0.5
x = np.arange(2)

# Create bars - neutral grey for both
bars = ax.bar(x, [amp_total, vcf_total], bar_width,
              color='#7F8C8D',
              edgecolor='white', linewidth=2)

# Add value labels on top of bars
for bar, val in zip(bars, [amp_total, vcf_total]):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 15,
            f'{val}', ha='center', va='bottom',
            fontsize=20, fontweight='bold')

# Customize plot
ax.set_ylabel('Number of Mutations', fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(['Breseq + GATK-HC\n(AMP)', 'Joint-GATK-HC\n(ANP)'], fontweight='bold')
ax.set_ylim(0, amp_total * 1.15)

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.tick_params(axis='both', which='both', length=5)

plt.tight_layout()

# Save
output_dir = 'comparison'
import os
os.makedirs(output_dir, exist_ok=True)

plt.savefig(f'{output_dir}/total_mutation_comparison.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig(f'{output_dir}/total_mutation_comparison.pdf', bbox_inches='tight',
            facecolor='white', edgecolor='none')

plt.style.use('default')
print("Bar chart saved to:")
print(f"  - {output_dir}/total_mutation_comparison.png")
print(f"  - {output_dir}/total_mutation_comparison.pdf")
print(f"\nVerified counts:")
print(f"  AMP (from CSV): {amp_total} mutations")
print(f"  Joint-GATK-HC (from VCF): {vcf_total} variants")
